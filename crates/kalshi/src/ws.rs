//! Official WebSocket envelopes and the production market-data client.
//!
//! Production connects to `wss://external-api-ws.kalshi.com/trade-api/ws/v2`
//! with the same RSA-PSS headers as REST. Demo URLs are refused.

use std::net::TcpStream;
use std::time::Duration;

use momento_core::error::VenueError;
use tungstenite::stream::MaybeTlsStream;
use tungstenite::{Message, WebSocket, client::IntoClientRequest};

use crate::auth::{
    KalshiCredentials, KalshiEnvironment, refuse_if_demo, require_host_matches_credentials,
};
use crate::redact::redact_secrets;
use crate::types::{
    KalshiFill, OrderbookDeltaMsg, OrderbookSnapshotMsg, SubscribedMsg, WS_PRODUCTION,
    WS_SIGN_PATH, WsEnvelope,
};

const WS_IDLE_TIMEOUT: Duration = Duration::from_millis(250);

#[derive(Clone, Debug, Default)]
pub struct WsDedupe {
    last_seq: std::collections::HashMap<u64, u64>,
    seen_fill_ids: std::collections::HashSet<String>,
}

impl WsDedupe {
    pub fn new() -> Self {
        Self::default()
    }

    /// Returns true if this (sid, seq) is new. Duplicate seq is ignored.
    pub fn accept_seq(&mut self, sid: u64, seq: u64) -> bool {
        match self.last_seq.get(&sid) {
            Some(prev) if seq <= *prev => false,
            _ => {
                self.last_seq.insert(sid, seq);
                true
            }
        }
    }

    pub fn accept_fill_id(&mut self, id: &str) -> bool {
        self.seen_fill_ids.insert(id.to_string())
    }
}

pub fn parse_ws_frame(raw: &str) -> Result<WsEnvelope, VenueError> {
    serde_json::from_str(raw).map_err(|e| VenueError::MalformedResponse(e.to_string()))
}

pub fn parse_orderbook_delta(env: &WsEnvelope) -> Result<OrderbookDeltaMsg, VenueError> {
    if env.msg_type != "orderbook_delta" {
        return Err(VenueError::MalformedResponse(format!(
            "expected orderbook_delta, got {}",
            env.msg_type
        )));
    }
    msg_from_env(env)
}

pub fn parse_orderbook_snapshot(env: &WsEnvelope) -> Result<OrderbookSnapshotMsg, VenueError> {
    if env.msg_type != "orderbook_snapshot" {
        return Err(VenueError::MalformedResponse(format!(
            "expected orderbook_snapshot, got {}",
            env.msg_type
        )));
    }
    msg_from_env(env)
}

pub fn parse_subscribed(env: &WsEnvelope) -> Result<SubscribedMsg, VenueError> {
    if env.msg_type != "subscribed" {
        return Err(VenueError::MalformedResponse(format!(
            "expected subscribed, got {}",
            env.msg_type
        )));
    }
    msg_from_env(env)
}

pub fn parse_fill_msg(env: &WsEnvelope) -> Result<KalshiFill, VenueError> {
    if env.msg_type != "fill" {
        return Err(VenueError::MalformedResponse(format!(
            "expected fill, got {}",
            env.msg_type
        )));
    }
    msg_from_env(env)
}

fn msg_from_env<T: serde::de::DeserializeOwned>(env: &WsEnvelope) -> Result<T, VenueError> {
    let msg = env
        .msg
        .as_ref()
        .ok_or_else(|| VenueError::MalformedResponse(format!("{} missing msg", env.msg_type)))?;
    serde_json::from_value(msg.clone()).map_err(|e| VenueError::MalformedResponse(e.to_string()))
}

#[derive(Debug, PartialEq, Eq)]
pub enum WsRead {
    Idle,
    Text(String),
}

pub struct ProductionWs {
    socket: WebSocket<MaybeTlsStream<TcpStream>>,
    next_id: u64,
}

impl ProductionWs {
    pub fn connect(creds: &KalshiCredentials) -> Result<Self, VenueError> {
        Self::connect_url(creds, WS_PRODUCTION)
    }

    pub fn connect_url(creds: &KalshiCredentials, url: &str) -> Result<Self, VenueError> {
        if creds.environment() != KalshiEnvironment::Production {
            return Err(VenueError::EnvironmentMismatch);
        }
        refuse_if_demo(url)?;
        require_host_matches_credentials(creds.environment(), url)?;
        let signed = creds.sign("GET", WS_SIGN_PATH)?;
        let mut request = url
            .into_client_request()
            .map_err(|e| VenueError::MalformedResponse(e.to_string()))?;
        let headers = request.headers_mut();
        insert_header(headers, "KALSHI-ACCESS-KEY", &signed.key_id)?;
        insert_header(headers, "KALSHI-ACCESS-TIMESTAMP", &signed.timestamp_ms)?;
        insert_header(headers, "KALSHI-ACCESS-SIGNATURE", &signed.signature)?;
        let (mut socket, _resp) = tungstenite::connect(request)
            .map_err(|e| VenueError::MalformedResponse(redact_secrets(&e.to_string())))?;
        set_read_timeout(socket.get_mut(), WS_IDLE_TIMEOUT)?;
        Ok(Self { socket, next_id: 1 })
    }

    pub fn subscribe_orderbook(&mut self, market_tickers: &[String]) -> Result<u64, VenueError> {
        if market_tickers.is_empty() {
            return Err(VenueError::MalformedResponse(
                "orderbook_delta requires market_tickers".into(),
            ));
        }
        let id = self.next_cmd_id();
        let cmd = serde_json::json!({
            "id": id,
            "cmd": "subscribe",
            "params": {
                "channels": ["orderbook_delta"],
                "market_tickers": market_tickers
            }
        });
        self.send_json(&cmd)?;
        Ok(id)
    }

    pub fn subscribe_fills(&mut self) -> Result<u64, VenueError> {
        let id = self.next_cmd_id();
        let cmd = serde_json::json!({
            "id": id,
            "cmd": "subscribe",
            "params": { "channels": ["fill"] }
        });
        self.send_json(&cmd)?;
        Ok(id)
    }

    pub fn add_markets(&mut self, sid: u64, market_tickers: &[String]) -> Result<u64, VenueError> {
        self.update_subscription(sid, "add_markets", market_tickers)
    }

    pub fn delete_markets(
        &mut self,
        sid: u64,
        market_tickers: &[String],
    ) -> Result<u64, VenueError> {
        self.update_subscription(sid, "delete_markets", market_tickers)
    }

    pub fn request_snapshot(
        &mut self,
        sid: u64,
        market_tickers: &[String],
    ) -> Result<u64, VenueError> {
        self.update_subscription(sid, "get_snapshot", market_tickers)
    }

    fn update_subscription(
        &mut self,
        sid: u64,
        action: &str,
        market_tickers: &[String],
    ) -> Result<u64, VenueError> {
        if market_tickers.is_empty() {
            return Err(VenueError::MalformedResponse(
                "update_subscription requires market_tickers".into(),
            ));
        }
        let id = self.next_cmd_id();
        let cmd = serde_json::json!({
            "id": id,
            "cmd": "update_subscription",
            "params": {
                "sids": [sid],
                "market_tickers": market_tickers,
                "action": action
            }
        });
        self.send_json(&cmd)?;
        Ok(id)
    }

    pub fn read(&mut self) -> Result<WsRead, VenueError> {
        match self.socket.read() {
            Ok(Message::Text(text)) => Ok(WsRead::Text(text.to_string())),
            Ok(Message::Ping(p)) => {
                let _ = self.socket.send(Message::Pong(p));
                Ok(WsRead::Idle)
            }
            Ok(Message::Pong(_)) | Ok(Message::Frame(_)) | Ok(Message::Binary(_)) => {
                Ok(WsRead::Idle)
            }
            Ok(Message::Close(_)) => Err(VenueError::MalformedResponse(
                "websocket closed by venue".into(),
            )),
            Err(tungstenite::Error::Io(e))
                if e.kind() == std::io::ErrorKind::WouldBlock
                    || e.kind() == std::io::ErrorKind::TimedOut =>
            {
                Ok(WsRead::Idle)
            }
            Err(e) => Err(VenueError::MalformedResponse(redact_secrets(
                &e.to_string(),
            ))),
        }
    }

    pub fn close(mut self) {
        let _ = self.socket.close(None);
    }

    fn next_cmd_id(&mut self) -> u64 {
        let id = self.next_id;
        self.next_id = self.next_id.saturating_add(1);
        id
    }

    fn send_json(&mut self, cmd: &serde_json::Value) -> Result<(), VenueError> {
        self.socket
            .send(Message::Text(cmd.to_string().into()))
            .map_err(|e| VenueError::MalformedResponse(redact_secrets(&e.to_string())))
    }
}

fn insert_header(
    headers: &mut tungstenite::http::HeaderMap,
    name: &'static str,
    value: &str,
) -> Result<(), VenueError> {
    use tungstenite::http::{HeaderName, HeaderValue};
    let name = HeaderName::from_bytes(name.as_bytes())
        .map_err(|e| VenueError::MalformedResponse(e.to_string()))?;
    let value =
        HeaderValue::from_str(value).map_err(|e| VenueError::MalformedResponse(e.to_string()))?;
    headers.insert(name, value);
    Ok(())
}

fn set_read_timeout(
    stream: &mut MaybeTlsStream<TcpStream>,
    timeout: Duration,
) -> Result<(), VenueError> {
    let tcp = match stream {
        MaybeTlsStream::Plain(s) => s,
        MaybeTlsStream::Rustls(s) => s.get_mut(),
        _ => {
            return Err(VenueError::Unsupported(
                "unexpected websocket TLS stream".into(),
            ));
        }
    };
    tcp.set_read_timeout(Some(timeout))
        .map_err(|e| VenueError::MalformedResponse(e.to_string()))?;
    Ok(())
}
