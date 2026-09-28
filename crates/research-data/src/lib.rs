//! Historical Kalshi research data infrastructure.
//!
//! Isolated from live trading. Collects, stores, validates, and replays
//! official Kalshi market data for backtesting research.

#![forbid(unsafe_code)]

pub mod catalog;
pub mod checksum;
pub mod collector;
pub mod discovery;
pub mod export;
pub mod foundation;
pub mod identity;
pub mod manifest;
pub mod normalize;
pub mod orderbook;
pub mod paths;
pub mod raw;
pub mod replay;
pub mod schedule;
pub mod schema;
pub mod sport;
pub mod validate;
pub mod warehouse;

pub use catalog::ResearchCatalog;
pub use collector::{CollectDayReport, Collector, CollectorConfig};
pub use export::export_csv;
pub use foundation::{
    ARTIFACT_VERSION, ObservabilityKind, W1RunConfig, W1RunResult, WATERFALL, run_w1_foundation,
};
pub use identity::{DiscoveredMarket, metadata_from_kalshi, same_game_different_market};
pub use manifest::{CompletenessStatus, DailyManifest};
pub use normalize::{write_metadata_parquet, write_orderbook_parquet, write_trades_parquet};
pub use orderbook::{OrderbookReconstructor, detect_sequence_gap};
pub use paths::ResearchPaths;
pub use replay::{ReplayCursor, ReplayDataset};
pub use schedule::{backfill_dates, collection_schedule, next_collection_run};
pub use schema::{
    COLLECTOR_VERSION, MarketMetadata, NormalizedSource, OrderbookEvent, OrderbookLevel,
    PublicTrade, RawMarketEvent, SCHEMA_VERSION,
};
pub use sport::{
    ResearchSeason, ResearchSport, SERIES_ATP, SERIES_MLB, SERIES_NBA, SERIES_NCAAB, SERIES_NHL,
    SERIES_WNBA, SERIES_WTA,
};
pub use validate::{
    no_synthetic_rows, validate_discovered_pairing, validate_metadata, validate_orderbook,
    validate_trades,
};
pub use warehouse::{
    MARKET_DATA_TYPE_CANDLE_TOB, NCAAB_SCHEMA_VERSION, NbaQuery, NbaWarehouse, PhaseClass,
    SCHEMA_VERSION as NBA_WAREHOUSE_SCHEMA, SeasonPhase, TENNIS_COMPETITION_FROM_METADATA,
    TENNIS_COMPETITION_FROM_TITLE, TENNIS_COMPETITION_UNAVAILABLE, TENNIS_SCHEMA_VERSION,
    TennisCompetition, TennisSides, WarehouseConfig, WarehouseReport, canonicalize_season,
    classify_tennis_phase, classify_tennis_phase_for_event, dollars_to_e4,
    market_tennis_competitor, render_report, season_for_date_tennis, tennis_competition,
    tennis_competition_resolved, tennis_player_sides,
};
