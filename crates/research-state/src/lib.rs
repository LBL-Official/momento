//! CTO-W6 — Canonical MLB GameState / StateTransition engine.
//!
//! Does not attach price paths. Does not implement strategy replay.

#![forbid(unsafe_code)]

pub mod api;
pub mod batch;
pub mod engine;
pub mod error;
pub mod fingerprint;
pub mod firewall;
pub mod lookup;
pub mod pa;
pub mod schema_sql;
pub mod store;
pub mod types;
pub mod validate;
pub mod versions;

pub use api::{StateJoinKey, join_points};
pub use batch::{ReconstructionReport, W6RunConfig, run_w6_batch};
pub use engine::{canonical_order, reconstruct, reconstruct_envelope};
pub use error::W6Error;
pub use lookup::{
    next_event, previous_event, replay_game_from, state_at_event, state_at_or_before,
    transition_at_event,
};
pub use store::{StateStore, StoredState, StoredTransition};
pub use types::{GameState, ReconstructedGame, StateTransition, TimeLookup};
pub use versions::{ARTIFACT_VERSION, SCHEMA_VERSION, WATERFALL};
