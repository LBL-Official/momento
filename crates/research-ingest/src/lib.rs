//! DATA-INGEST plane — acquisition + scheduling + W1 commit + W2/W3 consume gate.
//!
//! Not W4. Does not write Data-Real. Does not reconstruct Kalshi MarketState.

#![forbid(unsafe_code)]

pub mod adapter;
pub mod alerts;
pub mod cloud;
pub mod commit;
pub mod corpus;
pub mod coverage;
pub mod error;
pub mod fence;
pub mod join;
pub mod kalshi;
pub mod kalshi_live;
pub mod land;
pub mod lock;
pub mod matched_trades;
pub mod orchestrator;
pub mod paths;
pub mod planner;
pub mod rejoin;
pub mod schedule;
pub mod source;
pub mod types;
pub mod w2_gate;
pub mod watermarks;

pub use error::IngestError;
pub use orchestrator::{replay_run, run_ingest, run_ingest_with_sources};
pub use planner::{partition_window, required_mlb_partitions};
pub use schedule::{INGEST_HOUR_PACIFIC, next_weekly_ingest, weekly_window};
pub use types::{
    ARTIFACT_VERSION, CommitStatus, CommittedArtifact, DateWindow, IngestPlan, IngestRunReport,
    PLANE, PartitionStatus, RunStatus, SOURCE_KALSHI, SOURCE_KALSHI_DISCOVERY,
    SOURCE_KALSHI_HISTORICAL_CANDLES, SOURCE_KALSHI_MATCHED_TRADES, SOURCE_KALSHI_SETTLEMENT,
    SOURCE_STATSAPI, W1CommitHandoff,
};

pub const WATERFALL: &str = "DATA-INGEST";
