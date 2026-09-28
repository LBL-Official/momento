//! CTO-W8 — FIRST01 strategy replay over W7 EventMarketPath.
//!
//! Observational only. Does not submit orders, simulate fills, or compute P&L.

#![forbid(unsafe_code)]

pub mod api;
pub mod batch;
pub mod error;
pub mod firewall;
pub mod ids;
pub mod machine;
pub mod schema_sql;
pub mod store;
pub mod types;
pub mod versions;

pub use batch::{ReplayReport, W8RunConfig, run_w8_batch};
pub use error::W8Error;
pub use machine::replay_path;
pub use store::ReplayStore;
pub use types::{First01Opportunity, ReplayEvent, ReplayEventType, ReplayOutcome, ReplayPhase};
pub use versions::{ARTIFACT_VERSION, WATERFALL};
