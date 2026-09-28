//! CTO-W7 — Canonical EventMarketPath join of W5 observations onto W6 game truth.
//!
//! W5 owns AS-OF synchronization. W6 owns canonical MLB state.
//! This crate does not reconstruct PBP, invent L2, or implement strategy replay.

#![forbid(unsafe_code)]

pub mod api;
pub mod batch;
pub mod causal;
pub mod error;
pub mod firewall;
pub mod join;
pub mod schema_sql;
pub mod store;
pub mod types;
pub mod versions;

pub use api::{
    market_observations_after, market_observations_before, observations_at_or_before,
    observations_at_state, observations_in_state_seq_range, observations_where_price_equals,
    path_for_contract, path_for_game, path_for_market, state_at_market_observation,
};
pub use batch::{PathReport, W7RunConfig, run_w7_batch};
pub use error::W7Error;
pub use join::{W6Index, join_observation, path_id, sort_path_observations};
pub use store::{PathRunMeta, PathStore};
pub use types::{EventMarketPath, PathJoinStatus, PathObservation, StateSegment, occupancy_label};
pub use versions::{ARTIFACT_VERSION, WATERFALL};
