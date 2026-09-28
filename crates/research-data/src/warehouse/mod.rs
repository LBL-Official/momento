//! Event-centric Kalshi `KXNBAGAME` historical warehouse.
//!
//! Historical data is 1-minute top-of-book candlesticks plus public trades.
//! Historical L2 is not available and is never fabricated.

mod catalog;
mod config;
mod derive;
mod error;
mod http;
mod identity;
mod ingest;
mod normalize;
mod parquet;
mod paths;
mod query;
mod runner;
mod types;
mod validate;

pub use config::{WarehouseConfig, canonicalize_season};
pub use error::WarehouseError;
pub use identity::{
    PhaseClass, TENNIS_COMPETITION_FROM_METADATA, TENNIS_COMPETITION_FROM_TITLE,
    TENNIS_COMPETITION_UNAVAILABLE, TennisCompetition, TennisSides, classify_tennis_phase,
    classify_tennis_phase_for_event, market_tennis_competitor, season_for_date_tennis,
    tennis_competition, tennis_competition_resolved, tennis_player_sides,
};
pub use query::{AlignedQuote, GameMarketData, NbaQuery};
pub use runner::{DryRunReport, NbaWarehouse};
pub use types::{
    MARKET_DATA_TYPE_CANDLE_TOB, MARKET_DATA_TYPE_L2_DELTA, MARKET_DATA_TYPE_L2_SNAPSHOT,
    NCAAB_SCHEMA_VERSION, SCHEMA_VERSION, SeasonPhase, TENNIS_SCHEMA_VERSION, WarehouseReport,
    dollars_to_e4,
};
pub use validate::render_report;
