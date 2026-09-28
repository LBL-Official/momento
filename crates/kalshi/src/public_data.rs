//! Unsigned public Kalshi market-data HTTP. Research/backfill only.
//!
//! Official docs:
//! - https://docs.kalshi.com/getting_started/historical_data
//! - https://docs.kalshi.com/api-reference/market/get-markets
//! - https://docs.kalshi.com/api-reference/market/get-trades
//! - https://docs.kalshi.com/api-reference/market/get-market-order-book

use std::time::Duration;

use momento_core::error::VenueError;

use crate::http::agent;
use crate::types::{
    EVENTS_PATH, GetEventsResponse, GetMarketCandlesticksResponse, GetMarketResponse,
    GetMarketsResponse, GetOrderbookResponse, GetTradesResponse, HISTORICAL_CUTOFF_PATH,
    HISTORICAL_MARKETS_PATH, HISTORICAL_TRADES_PATH, HistoricalCutoffResponse, MARKETS_PATH,
    REST_PRODUCTION_ORIGIN, TRADES_PATH,
};

const PAGE_DELAY: Duration = Duration::from_millis(120);

/// Unsigned production REST client for public market data endpoints.
#[derive(Clone, Debug)]
pub struct PublicMarketClient {
    base: String,
    agent: ureq::Agent,
}

impl PublicMarketClient {
    pub fn production() -> Self {
        Self {
            base: REST_PRODUCTION_ORIGIN.to_string(),
            agent: agent(),
        }
    }

    /// Research ingest: same production host, longer timeout for large candle pages.
    pub fn production_research() -> Self {
        Self {
            base: REST_PRODUCTION_ORIGIN.to_string(),
            agent: ureq::AgentBuilder::new()
                .timeout(Duration::from_secs(90))
                .build(),
        }
    }

    pub fn with_base(base: impl Into<String>) -> Self {
        Self {
            base: base.into(),
            agent: agent(),
        }
    }

    pub fn get_historical_cutoff(&self) -> Result<HistoricalCutoffResponse, VenueError> {
        self.get_json(HISTORICAL_CUTOFF_PATH)
    }

    /// Returns HTTP status and body. Callers handle 429/5xx retries.
    pub fn get_status_body(&self, path: &str) -> Result<(u16, String), VenueError> {
        let url = format!("{}{path}", self.base);
        match self
            .agent
            .get(&url)
            .set("Accept", "application/json")
            .call()
        {
            Ok(resp) => {
                let status = resp.status();
                let body = resp
                    .into_string()
                    .map_err(|e| VenueError::MalformedResponse(e.to_string()))?;
                Ok((status, body))
            }
            Err(ureq::Error::Status(status, resp)) => {
                let body = resp.into_string().unwrap_or_default();
                Ok((status, body))
            }
            Err(ureq::Error::Transport(t)) => {
                let msg = t.to_string().to_ascii_lowercase();
                if msg.contains("timed out") || msg.contains("timeout") {
                    Err(VenueError::Timeout)
                } else {
                    Err(VenueError::MalformedResponse(t.to_string()))
                }
            }
        }
    }

    pub fn list_events(&self, query: &str) -> Result<GetEventsResponse, VenueError> {
        let path = if query.is_empty() {
            EVENTS_PATH.to_string()
        } else {
            format!("{EVENTS_PATH}?{query}")
        };
        self.get_json(&path)
    }

    pub fn get_event(&self, event_ticker: &str) -> Result<serde_json::Value, VenueError> {
        self.get_json(&format!("{EVENTS_PATH}/{event_ticker}"))
    }

    pub fn list_all_events(
        &self,
        base_query: String,
    ) -> Result<Vec<serde_json::Value>, VenueError> {
        let mut out = Vec::new();
        let mut cursor: Option<String> = None;
        let mut pages = 0u32;
        loop {
            pages += 1;
            if pages > 500 {
                return Err(VenueError::MalformedResponse(
                    "events pagination exceeded 500 pages; refusing silent truncate".into(),
                ));
            }
            let query = match &cursor {
                Some(c) => {
                    if base_query.is_empty() {
                        format!("cursor={c}")
                    } else {
                        format!("{base_query}&cursor={c}")
                    }
                }
                None => base_query.clone(),
            };
            let page = self.list_events(&query)?;
            out.extend(page.events);
            match page.cursor.filter(|c| !c.is_empty()) {
                Some(next) => {
                    cursor = Some(next);
                    std::thread::sleep(PAGE_DELAY);
                }
                None => break,
            }
        }
        Ok(out)
    }

    pub fn list_markets(&self, query: &str) -> Result<GetMarketsResponse, VenueError> {
        let path = if query.is_empty() {
            MARKETS_PATH.to_string()
        } else {
            format!("{MARKETS_PATH}?{query}")
        };
        self.get_json(&path)
    }

    pub fn list_historical_markets(&self, query: &str) -> Result<GetMarketsResponse, VenueError> {
        let path = if query.is_empty() {
            HISTORICAL_MARKETS_PATH.to_string()
        } else {
            format!("{HISTORICAL_MARKETS_PATH}?{query}")
        };
        self.get_json(&path)
    }

    pub fn get_market(&self, ticker: &str) -> Result<GetMarketResponse, VenueError> {
        self.get_json(&format!("{MARKETS_PATH}/{ticker}"))
    }

    pub fn get_historical_market(&self, ticker: &str) -> Result<GetMarketResponse, VenueError> {
        self.get_json(&format!("{HISTORICAL_MARKETS_PATH}/{ticker}"))
    }

    pub fn get_orderbook(
        &self,
        ticker: &str,
        depth: Option<u32>,
    ) -> Result<GetOrderbookResponse, VenueError> {
        let mut path = format!("{MARKETS_PATH}/{ticker}/orderbook");
        if let Some(depth) = depth {
            path.push_str(&format!("?depth={depth}"));
        }
        self.get_json(&path)
    }

    pub fn list_trades(&self, query: &str) -> Result<GetTradesResponse, VenueError> {
        let path = if query.is_empty() {
            TRADES_PATH.to_string()
        } else {
            format!("{TRADES_PATH}?{query}")
        };
        self.get_json(&path)
    }

    pub fn list_historical_trades(&self, query: &str) -> Result<GetTradesResponse, VenueError> {
        let path = if query.is_empty() {
            HISTORICAL_TRADES_PATH.to_string()
        } else {
            format!("{HISTORICAL_TRADES_PATH}?{query}")
        };
        self.get_json(&path)
    }

    pub fn get_candlesticks(
        &self,
        series_ticker: &str,
        ticker: &str,
        start_ts: i64,
        end_ts: i64,
        period_interval: u32,
    ) -> Result<GetMarketCandlesticksResponse, VenueError> {
        let path = format!(
            "/trade-api/v2/series/{series_ticker}/markets/{ticker}/candlesticks?start_ts={start_ts}&end_ts={end_ts}&period_interval={period_interval}"
        );
        self.get_json(&path)
    }

    pub fn get_historical_candlesticks(
        &self,
        ticker: &str,
        start_ts: i64,
        end_ts: i64,
        period_interval: u32,
    ) -> Result<GetMarketCandlesticksResponse, VenueError> {
        let path = format!(
            "/trade-api/v2/historical/markets/{ticker}/candlesticks?start_ts={start_ts}&end_ts={end_ts}&period_interval={period_interval}"
        );
        self.get_json(&path)
    }

    /// Raw historical candlesticks. Lands what Kalshi sent; does not invent OHLC.
    pub fn get_historical_candlesticks_value(
        &self,
        ticker: &str,
        start_ts: i64,
        end_ts: i64,
        period_interval: u32,
    ) -> Result<serde_json::Value, VenueError> {
        let path = format!(
            "/trade-api/v2/historical/markets/{ticker}/candlesticks?start_ts={start_ts}&end_ts={end_ts}&period_interval={period_interval}"
        );
        self.get_json(&path)
    }

    /// Paginate a markets query until the cursor is empty.
    pub fn list_all_markets(
        &self,
        base_query: String,
        historical: bool,
    ) -> Result<Vec<crate::types::KalshiMarket>, VenueError> {
        let mut out = Vec::new();
        let mut cursor: Option<String> = None;
        let mut pages = 0u32;
        loop {
            pages += 1;
            if pages > 500 {
                return Err(VenueError::MalformedResponse(
                    "markets pagination exceeded 500 pages; refusing silent truncate".into(),
                ));
            }
            let query = match &cursor {
                Some(c) => {
                    if base_query.is_empty() {
                        format!("cursor={c}")
                    } else {
                        format!("{base_query}&cursor={c}")
                    }
                }
                None => base_query.clone(),
            };
            let page = if historical {
                self.list_historical_markets(&query)?
            } else {
                self.list_markets(&query)?
            };
            out.extend(page.markets);
            match page.cursor.filter(|c| !c.is_empty()) {
                Some(next) => {
                    cursor = Some(next);
                    std::thread::sleep(PAGE_DELAY);
                }
                None => break,
            }
        }
        Ok(out)
    }

    /// Paginate trades for a ticker and time window.
    pub fn list_all_trades(
        &self,
        ticker: &str,
        min_ts: i64,
        max_ts: i64,
        historical: bool,
    ) -> Result<Vec<crate::types::KalshiTrade>, VenueError> {
        let mut out = Vec::new();
        let mut cursor: Option<String> = None;
        loop {
            let mut query = format!("ticker={ticker}&min_ts={min_ts}&max_ts={max_ts}&limit=1000");
            if let Some(c) = &cursor {
                query.push_str(&format!("&cursor={c}"));
            }
            let page = if historical {
                self.list_historical_trades(&query)?
            } else {
                self.list_trades(&query)?
            };
            out.extend(page.trades);
            match page.cursor.filter(|c| !c.is_empty()) {
                Some(next) => {
                    cursor = Some(next);
                    std::thread::sleep(PAGE_DELAY);
                }
                None => break,
            }
        }
        Ok(out)
    }

    fn get_json<T: serde::de::DeserializeOwned>(&self, path: &str) -> Result<T, VenueError> {
        let url = format!("{}{path}", self.base);
        let resp = self
            .agent
            .get(&url)
            .set("Accept", "application/json")
            .call()
            .map_err(|e| VenueError::MalformedResponse(e.to_string()))?;
        let status = resp.status();
        let body = resp
            .into_string()
            .map_err(|e| VenueError::MalformedResponse(e.to_string()))?;
        if status != 200 {
            return Err(VenueError::MalformedResponse(format!(
                "public HTTP {status}: {body}"
            )));
        }
        serde_json::from_str(&body).map_err(|e| VenueError::MalformedResponse(e.to_string()))
    }
}
