//! CTO-W4 — Kalshi market reconstruction from committed artifacts.
//!
//! Reconstructs per-contract [`MarketPath`]. Does not synchronize to PBP (W5),
//! estimate theta, or submit orders.

#![forbid(unsafe_code)]

pub mod capability;
pub mod cents;
pub mod completeness;
pub mod couple;
pub mod coverage;
pub mod error;
pub mod firewall;
pub mod gate;
pub mod inventory;
pub mod lake;
pub mod matched_paths;
pub mod price_path;
pub mod price_paths;
pub mod reader;
pub mod readiness;
pub mod reconstruct;
pub mod runner;
pub mod types;
pub mod versions;

pub use capability::{
    GateDecision, MarketCapabilityCard, MarketIdentityStatus, ResearchCapability, research_gate,
};
pub use error::W4Error;
pub use inventory::{UniverseInventory, run_universe_inventory};
pub use matched_paths::{MatchedTradeCoverage, run_matched_trade_reconstruction};
pub use price_path::{
    CandleObservation, L2SnapshotObservation, QuoteObservation, TradeObservation,
    chronological_candles, chronological_l2_snapshots, chronological_quotes, chronological_trades,
    first_trade, last_trade, observations_as_of, request_maker_fill_simulation,
    request_orderbook_microstructure, synthetic_bid_ask, trade_extrema_cents, trades_as_of,
};
pub use price_paths::{PricePathRunReport, run_price_path_reconstruction};
pub use readiness::{
    FIRST01_CONFIRM_CENTS, FIRST01_ENTRY_TOUCH_CENTS, FIRST01_LOCK_CENTS, FunnelCounts,
    MarketReadiness,
};
pub use runner::{W4RunConfig, W4RunResult, run_w4_reconstruction};
pub use types::{
    CoupledMarketEpisode, MarketCompleteness, MarketObservationKind, MarketPath, MarketPoint,
};
pub use versions::{ARTIFACT_VERSION, RECONSTRUCTION_VERSION, WATERFALL};
