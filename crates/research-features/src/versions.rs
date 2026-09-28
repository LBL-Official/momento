//! B1 version stamps. Generation time never enters snapshot identity.

pub const WATERFALL: &str = "B1";
pub const ARTIFACT_VERSION: &str = "B1.FEATURES.1.1.0";
pub const SCHEMA_VERSION: &str = "B1.SCHEMA.1.1.0";
pub const ENGINE_VERSION: &str = "B1.ENGINE.1.1.0";
pub const FEATURE_SCHEMA_VERSION: &str = "B1.FEATURE.1.1.0";
pub const DATASET_VERSION: &str = "B1.ENTRY_SNAPSHOT.2";
/// FIRST01 research entry band (A1 default). Not a live-parameter change.
pub const A1_DEFAULT_ENTRY_BAND: &str = "80-83";
/// Event-path history cap (sample-size discipline).
pub const EVENT_HISTORY_CAP: usize = 32;
pub const MIGRATION_001: &str = "001_b1_features_1_1";
pub const OBSERVABILITY: &str = "TRADE_PRINT_NOT_YES_BID";
pub const EXECUTION_STATUS: &str = "OBSERVATIONAL_TRADE_ENTRY";
pub const ORDERING_CONTRACT: &str = "market_timestamp_utc, observation_id";
pub const PRICE_KIND: &str = "TRADE_PRICE";
/// Chronological train/test cut. Entry dates strictly before this are TRAIN.
pub const DEFAULT_SPLIT_CUTOFF_DATE: &str = "2026-01-01";
/// Time-to-profit / time-to-loss threshold: 1¢ beyond entry.
pub const TIME_TO_THRESHOLD_CENTS: i32 = 1;
