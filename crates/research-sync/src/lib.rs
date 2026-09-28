//! CTO-W5 — Event ↔ Kalshi market time synchronization.
//!
//! AS-OF join: latest canonical MLB event with effective time ≤ market time.
//! Does not invent L2, starting prices, market open/close, or W6 matrices.

#![forbid(unsafe_code)]

pub mod api;
pub mod apply;
pub mod as_of;
pub mod batch;
pub mod error;
pub mod firewall;
pub mod market;
pub mod schema_sql;
pub mod store;
pub mod time;
pub mod timeline;
pub mod types;
pub mod versions;

pub use api::{
    game_state_at, synchronization_report, synchronize_game, synchronize_game_with_clock,
    synchronized_observations_for_event, synchronized_observations_for_game,
    synchronized_observations_for_market,
};
pub use apply::{link_market_path, synchronize_market, synchronize_market_observation};
pub use batch::{SyncReport, W5RunConfig, run_w5_batch};
pub use error::W5Error;
pub use store::SyncStore;
pub use types::{
    GameCoverage, GameStateSnapshot, IdentityStatus, MarketObservation, ObservationType,
    SyncParams, SyncQuality, SyncStatus, SynchronizedMarketObservation, TimedEvent,
    TimestampRelation,
};
pub use versions::{ARTIFACT_VERSION, WATERFALL};
