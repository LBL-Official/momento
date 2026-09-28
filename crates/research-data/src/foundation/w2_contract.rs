//! Narrow contracts W2 may consume. W1 owns raw storage; W2 owns PBP/game-state.
//!
//! This module must not define MLB GameState, PBP events, or StateTransition.

use serde::{Deserialize, Serialize};

use super::observability::ObservabilityKind;
use super::starting_price::StartingPriceClass;

/// Immutable raw artifact pointer owned by W1. Not a W2 domain type.
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct RawArtifactRef {
    /// Lake directory name (`MLB`, `WNBA`). Not a canonical multi-sport domain enum.
    pub sport: String,
    pub path: String,
    pub sha256: Option<String>,
    pub layer: String,
    pub partition_date: Option<String>,
    pub observability: ObservabilityKind,
}

/// Kalshi-side identity only. `mlb_game_pk` is always unmapped in W1.
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct RawMarketIdentity {
    pub game_id: String,
    pub market_id: String,
    pub ticker: String,
    pub event_ticker: String,
    pub series: String,
    pub mlb_game_pk: Option<String>,
    pub starting_price_class: StartingPriceClass,
}

/// Generic raw kinds the lake may hold. Values are references, not reconstructed state.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum RawKind {
    Game,
    Market,
    Contract,
    Source,
    Observation,
    Trade,
    Quote,
    OrderbookObservation,
    RawArtifact,
    Provenance,
    Coverage,
    Settlement,
}

pub const W2_HANDOFF_NOTES: &str = "\
W2 must read RawArtifactRef + RawMarketIdentity from the W1 catalog. \
W2 must not rewrite gzip/parquet under the lake. \
W2 must not treat PARTITION_COMPLETE_V1 as PBP-complete or lifetime-complete. \
W2 owns MLB event/PBP/game-state types; W1 does not define them. \
L2_HISTORICAL_UNAVAILABLE unless a future WS capture artifact is catalogued separately.";
