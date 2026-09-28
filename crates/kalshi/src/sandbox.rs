//! Demo/sandbox HTTP and WebSocket. Production URLs are refused.

use std::net::TcpStream;
use std::time::Duration;

use momento_core::error::VenueError;
use tungstenite::stream::MaybeTlsStream;
use tungstenite::{Message, WebSocket, client::IntoClientRequest};

use crate::auth::{KalshiCredentials, KalshiEnvironment, refuse_if_production};
use crate::http::{agent, signed_execute};
use crate::redact::redact_secrets;
use crate::transport::{KalshiHttpRequest, KalshiTransport, TransportOutcome};
use crate::types::{REST_DEMO_ORIGIN, WS_DEMO_SHARED, WS_SIGN_PATH};
const WS_READ_TIMEOUT: Duration = Duration::from_secs(8);

pub struct SandboxHttpTransport {
    creds: KalshiCredentials,
    origin: String,
    agent: ureq::Agent,
}

impl SandboxHttpTransport {
    pub fn demo(creds: KalshiCredentials) -> Result<Self, VenueError> {
        Self::with_origin(creds, REST_DEMO_ORIGIN)
    }

    pub fn with_origin(creds: KalshiCredentials, origin: &str) -> Result<Self, VenueError> {
        if creds.environment() != KalshiEnvironment::Demo {
            return Err(VenueError::EnvironmentMismatch);
        }
        refuse_if_production(origin)?;
        Ok(Self {
            creds,
            origin: origin.trim_end_matches('/').to_string(),
            agent: agent(),
        })
    }

    pub fn origin(&self) -> &str {
        &self.origin
    }

    fn url_for(&self, path: &str) -> Result<String, VenueError> {
        let url = format!("{}{path}", self.origin);
        refuse_if_production(&url)?;
        Ok(url)
    }
}

impl KalshiTransport for SandboxHttpTransport {
    fn execute(&mut self, request: KalshiHttpRequest) -> TransportOutcome {
        match self.execute_inner(&request) {
            Ok(outcome) => outcome,
            Err(VenueError::Timeout) => TransportOutcome::Timeout,
            Err(other) => TransportOutcome::Http {
                status: 0,
                body: other.to_string(),
            },
        }
    }
}

impl SandboxHttpTransport {
    fn execute_inner(
        &mut self,
        request: &KalshiHttpRequest,
    ) -> Result<TransportOutcome, VenueError> {
        let url = self.url_for(&request.path)?;
        let path_for_sign = request.path.split('?').next().unwrap_or(&request.path);
        signed_execute(
            &self.agent,
            &self.creds,
            &request.method,
            &url,
            path_for_sign,
            request.body.as_deref(),
        )
    }
}

pub struct SandboxWs {
    socket: WebSocket<MaybeTlsStream<TcpStream>>,
}

impl SandboxWs {
    pub fn connect(creds: &KalshiCredentials) -> Result<Self, VenueError> {
        Self::connect_url(creds, WS_DEMO_SHARED)
    }

    pub fn connect_url(creds: &KalshiCredentials, url: &str) -> Result<Self, VenueError> {
        if creds.environment() != KalshiEnvironment::Demo {
            return Err(VenueError::EnvironmentMismatch);
        }
        refuse_if_production(url)?;
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
        set_read_timeout(socket.get_mut(), WS_READ_TIMEOUT)?;
        Ok(Self { socket })
    }

    pub fn subscribe_ticker(&mut self) -> Result<(), VenueError> {
        let cmd = serde_json::json!({
            "id": 1,
            "cmd": "subscribe",
            "params": { "channels": ["ticker"] }
        });
        self.socket
            .send(Message::Text(cmd.to_string().into()))
            .map_err(|e| VenueError::MalformedResponse(e.to_string()))?;
        Ok(())
    }

    pub fn read_text(&mut self) -> Result<Option<String>, VenueError> {
        match self.socket.read() {
            Ok(Message::Text(text)) => Ok(Some(text.to_string())),
            Ok(Message::Ping(p)) => {
                let _ = self.socket.send(Message::Pong(p));
                Ok(None)
            }
            Ok(Message::Close(_)) => Err(VenueError::Timeout),
            Ok(_) => Ok(None),
            Err(tungstenite::Error::Io(e))
                if e.kind() == std::io::ErrorKind::WouldBlock
                    || e.kind() == std::io::ErrorKind::TimedOut =>
            {
                Err(VenueError::Timeout)
            }
            Err(e) => Err(VenueError::MalformedResponse(redact_secrets(
                &e.to_string(),
            ))),
        }
    }

    pub fn close(mut self) {
        let _ = self.socket.close(None);
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
