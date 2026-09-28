//! Documented research dataset schema.

use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};

use momento_core::{GameId, MarketId};

pub const SCHEMA_VERSION: &str = "1.0.0";
pub const COLLECTOR_VERSION: &str = env!("CARGO_PKG_VERSION");

/// Immutable raw Kalshi payload plus collector envelope.
#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
pub struct RawMarketEvent {
    /// Collector receive time (RFC3339 UTC).
    pub received_at: DateTime<Utc>,
    /// `rest` | `websocket` | `historical_rest`
    pub source: String,
    /// Kalshi endpoint or WS message type.
    pub endpoint: String,
    /// Market ticker when known.
    pub ticker: Option<String>,
    /// Original JSON body from Kalshi.
    pub payload: serde_json::Value,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum NormalizedSource {
    RestSnapshot,
    WebSocketSnapshot,
    WebSocketDelta,
    RestCandlestick,
}

/// Per-market metadata preserved for identity and joins.
#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct MarketMetadata {
    pub game_id: u128,
    pub market_id: u128,
    pub ticker: String,
    pub event_ticker: String,
    pub series_ticker: String,
    /// Team/side label from Kalshi `subtitle` when present.
    pub side_label: Option<String>,
    pub status: Option<String>,
    pub open_time: Option<String>,
    pub close_time: Option<String>,
    pub settlement_ts: Option<String>,
    pub result: Option<String>,
}

impl MarketMetadata {
    pub fn game_id(&self) -> GameId {
        GameId::from_raw(self.game_id)
    }

    pub fn market_id(&self) -> MarketId {
        MarketId::from_raw(self.market_id)
    }
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct OrderbookLevel {
    /// YES-side price in integer cents when applicable.
    pub price_cents: u16,
    /// Contract quantity in hundredths (Kalshi fp × 100).
    pub quantity_hundredths: i64,
    /// `yes` or `no` book side.
    pub book_side: String,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct OrderbookEvent {
    pub exchange_timestamp_ms: Option<i64>,
    pub received_timestamp: DateTime<Utc>,
    pub ticker: String,
    pub market_id: u128,
    pub game_id: u128,
    pub event_type: String,
    pub source: NormalizedSource,
    pub sequence_number: Option<u64>,
    pub subscription_id: Option<u64>,
    pub yes_bid_cents: Option<u16>,
    pub yes_ask_cents: Option<u16>,
    pub yes_bid_depth_hundredths: Option<i64>,
    pub yes_ask_depth_hundredths: Option<i64>,
    pub levels: Vec<OrderbookLevel>,
    pub sequence_gap: bool,
    pub resync_count: u32,
    pub first_missing_sequence: Option<u64>,
    pub last_valid_sequence: Option<u64>,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct PublicTrade {
    pub exchange_timestamp: String,
    pub received_timestamp: DateTime<Utc>,
    pub ticker: String,
    pub market_id: u128,
    pub game_id: u128,
    pub trade_id: String,
    pub yes_price_cents: u16,
    pub quantity_hundredths: i64,
    pub taker_outcome_side: Option<String>,
    pub taker_book_side: Option<String>,
    pub is_block_trade: bool,
    pub source: String,
}
