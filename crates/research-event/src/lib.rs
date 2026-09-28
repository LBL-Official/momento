//! Waterfall 2 — MLB event / play-by-play reconstruction (research only).
//!
//! Independent of live strategy, risk, and execution. Does not synchronize
//! Kalshi markets (W3/W4). Does not fabricate historical PBP.

#![forbid(unsafe_code)]

pub mod adapter;
pub mod collect;
pub mod coverage;
pub mod error;
pub mod event;
pub mod event_time;
pub mod field;
pub mod historical;
pub mod identity;
pub mod ingest;
pub mod ledger;
pub mod market_ref;
pub mod outcome;
pub mod replay;
pub mod reporting;
pub mod runner;
pub mod schema_sql;
pub mod sequence;
pub mod source;
pub mod state;
pub mod synthetic;
pub mod versions;
pub mod w1_bridge;

pub use adapter::{EventStateAdapter, MlbEventAdapter, RemainingOpportunities};
pub use collect::{CollectReport, CollectedGame};
pub use error::EventError;
pub use event::CanonicalMlbEvent;
pub use historical::{HistoricalReconstructionReport, reconstruct_envelopes, reconstruct_paths};
pub use identity::{CanonicalGameId, IdentityRegistry};
pub use ingest::{ingest_bytes, ingest_path, official_ref_from_envelope_bytes, sha256_bytes};
pub use market_ref::MlbMarketReference;
pub use outcome::GameOutcome;
pub use runner::{W2RunConfig, W2RunResult, run_w2_event_reconstruction};
pub use state::{MlbGameState, MlbPbpTransition};
pub use versions::{
    ARTIFACT_VERSION, EVENT_TIME_DEFINITION_VERSION, NORMALIZATION_VERSION, PARSER_VERSION,
    REMAINING_OUTS_DEFINITION_VERSION, SCHEMA_VERSION, STATE_MACHINE_VERSION, WATERFALL,
};

/// Re-export W1 observability. W2 does not fork this vocabulary.
pub use momento_research_data::foundation::ObservabilityKind;
