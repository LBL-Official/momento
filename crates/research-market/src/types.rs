//! W4 market-path types. Integer cents only. No f64.

use chrono::{DateTime, Utc};
use momento_research_data::foundation::{
    ObservabilityKind, StartingPriceClass, StartingPriceEvidence,
};
use momento_research_ingest::types::IdentityMapping;
use serde::{Deserialize, Serialize};

use crate::capability::MarketCapabilityCard;
use crate::error::W4Error;
use crate::versions::RECONSTRUCTION_VERSION;

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum MarketCompleteness {
    L2Complete,
    L2Partial,
    TradesOnly,
    CandlesOnly,
    MarketMetadataOnly,
    Unobserved,
}

impl MarketCompleteness {
    pub fn as_str(self) -> &'static str {
        match self {
            Self::L2Complete => "L2_COMPLETE",
            Self::L2Partial => "L2_PARTIAL",
            Self::TradesOnly => "TRADES_ONLY",
            Self::CandlesOnly => "CANDLES_ONLY",
            Self::MarketMetadataOnly => "MARKET_METADATA_ONLY",
            Self::Unobserved => "UNOBSERVED",
        }
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum MarketObservationKind {
    Metadata,
    Trade,
    Candle1m,
    TopOfBook,
    L2Delta,
    L2Snapshot,
    RestPitSnapshot,
}

impl MarketObservationKind {
    pub fn as_str(self) -> &'static str {
        match self {
            Self::Metadata => "METADATA",
            Self::Trade => "TRADE",
            Self::Candle1m => "CANDLE_1M",
            Self::TopOfBook => "TOP_OF_BOOK",
            Self::L2Delta => "L2_DELTA",
            Self::L2Snapshot => "L2_SNAPSHOT",
            Self::RestPitSnapshot => "REST_PIT_SNAPSHOT",
        }
    }

    pub fn is_game_time_l2(self) -> bool {
        matches!(self, Self::L2Delta | Self::L2Snapshot)
    }

    pub fn is_quote_or_l2(self) -> bool {
        matches!(self, Self::TopOfBook | Self::L2Delta | Self::L2Snapshot)
    }
}

/// Reject the LEGACY lie `event_type = candlestick` + `l2_snapshot`.
pub fn assert_event_type_legal(event_type: &str) -> Result<(), W4Error> {
    let et = event_type.to_ascii_lowercase();
    let candle = et.contains("candlestick") || et.contains("candle");
    let l2 = et.contains("l2_snapshot") || et.contains("l2-snapshot");
    if candle && l2 {
        return Err(W4Error::Reconstruction(
            "event_type candlestick + l2_snapshot is invalid".into(),
        ));
    }
    Ok(())
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum LifetimeCoverage {
    OpenToSettlement,
    SettlementDayOnly,
    Unknown,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum MissingSide {
    None,
    SecondYesContract,
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct CandleOhlcCents {
    pub yes_bid_open: Option<i32>,
    pub yes_bid_high: Option<i32>,
    pub yes_bid_low: Option<i32>,
    pub yes_bid_close: Option<i32>,
    pub yes_ask_open: Option<i32>,
    pub yes_ask_high: Option<i32>,
    pub yes_ask_low: Option<i32>,
    pub yes_ask_close: Option<i32>,
    pub yes_price_close: Option<i32>,
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct MarketPoint {
    pub ticker: String,
    pub event_ticker: String,
    pub market_id: String,
    pub exchange_timestamp: DateTime<Utc>,
    pub yes_bid_cents: Option<i32>,
    pub yes_ask_cents: Option<i32>,
    pub last_trade_cents: Option<i32>,
    pub quantity_hundredths: Option<i64>,
    pub trade_id: Option<String>,
    pub candle_ohlc: Option<CandleOhlcCents>,
    pub kind: MarketObservationKind,
    pub observability: ObservabilityKind,
    /// Evidence origin. Never used as the market-event clock.
    #[serde(default)]
    pub source: Option<String>,
    #[serde(default)]
    pub source_record_id: Option<String>,
    /// Envelope/collector retrieval clock. Never used to order or `as_of` the path.
    #[serde(default)]
    pub retrieval_timestamp: Option<DateTime<Utc>>,
}

impl MarketPoint {
    /// DERIVED spread only when both sides are quote/L2 OBSERVED and ask ≥ bid.
    pub fn derived_spread_cents(&self) -> Option<i32> {
        if !self.kind.is_quote_or_l2() {
            return None;
        }
        derived_spread_cents(self.yes_bid_cents, self.yes_ask_cents)
    }

    pub fn trade_price_cents(&self) -> Option<i32> {
        if self.kind == MarketObservationKind::Trade {
            self.last_trade_cents
        } else {
            None
        }
    }
}

pub fn derived_spread_cents(bid: Option<i32>, ask: Option<i32>) -> Option<i32> {
    match (bid, ask) {
        (Some(b), Some(a)) if a >= b => Some(a - b),
        _ => None,
    }
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct MarketPath {
    pub ticker: String,
    pub event_ticker: String,
    pub market_id: String,
    pub identity: IdentityMapping,
    pub game_pk: Option<String>,
    pub completeness: MarketCompleteness,
    pub open_time: Option<String>,
    pub close_time: Option<String>,
    pub settlement: Option<String>,
    pub points: Vec<MarketPoint>,
    pub starting_price_class: StartingPriceClass,
    pub starting_price: StartingPriceEvidence,
    pub lifetime_coverage: LifetimeCoverage,
    pub ingest_only_pit_count: usize,
    pub blocked_on_ingest_observations: bool,
    #[serde(default)]
    pub capability: MarketCapabilityCard,
    /// First/last *observation* clocks. Not market_open / market_close.
    #[serde(default)]
    pub observed_start: Option<DateTime<Utc>>,
    #[serde(default)]
    pub observed_end: Option<DateTime<Utc>>,
    #[serde(default)]
    pub reconstruction_version: String,
}

impl MarketPath {
    pub fn price_path_available(&self) -> bool {
        self.capability.price_path_research.permits_price_path()
    }

    pub fn orderbook_available(&self) -> bool {
        self.capability.orderbook_microstructure.is_allowed()
    }

    pub fn maker_simulation_available(&self) -> bool {
        self.capability.maker_fill_simulation.is_allowed()
    }

    pub fn game_id_linked(&self) -> bool {
        self.capability.game_id_linked_research.is_allowed()
    }

    pub fn with_observed_bounds(mut self) -> Self {
        let start = self.points.first().map(|p| p.exchange_timestamp);
        let end = self.points.last().map(|p| p.exchange_timestamp);
        self.observed_start = start;
        self.observed_end = end;
        if self.reconstruction_version.is_empty() {
            self.reconstruction_version = RECONSTRUCTION_VERSION.into();
        }
        self
    }
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct CoupledMarketEpisode {
    pub event_ticker: String,
    pub team_a_yes: Option<MarketPath>,
    pub team_b_yes: Option<MarketPath>,
    pub missing_side: MissingSide,
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct ReconstructionAnomaly {
    pub ticker: String,
    pub code: String,
    pub message: String,
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct ObservationBlocker {
    pub ticker: String,
    pub identity: IdentityMapping,
    pub completeness: MarketCompleteness,
    pub reason: String,
}
