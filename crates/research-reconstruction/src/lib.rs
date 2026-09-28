//! CTO-W3 — MLB game / PBP reconstruction over committed source artifacts.
//!
//! Reuses the W2 parser and fail-closed state machine. Does not reconstruct
//! Kalshi markets (W4), synchronize clocks (W5), or estimate theta (W10).

#![forbid(unsafe_code)]

pub mod committed;
pub mod coverage;
pub mod error;
pub mod firewall;
pub mod fixtures;
pub mod gate;
pub mod ledger;
pub mod lifecycle;
pub mod runner;
pub mod schema_sql;
pub mod versions;

pub use error::W3Error;
pub use runner::{W3RunConfig, W3RunResult, run_w3_reconstruction};
pub use versions::{ARTIFACT_VERSION, WATERFALL};
