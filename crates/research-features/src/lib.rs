//! B1 — observational price-dissection feature engine.
//!
//! Consumes W6/W7/W8. Does not modify live FIRST01, invent L2, or start W9.

#![forbid(unsafe_code)]

pub mod a1_targets;
pub mod analysis;
pub mod availability;
pub mod batch;
pub mod configured_search;
pub mod dataset;
pub mod dictionary;
pub mod error;
pub mod event_response;
pub mod extract_first83;
pub mod firewall;
pub mod game_state;
pub mod identity;
pub mod ids;
pub mod interactions;
pub mod market_history;
pub mod microstructure;
pub mod normalization;
pub mod outcomes;
pub mod price_history;
pub mod prospective83;
pub mod prospective83_engine;
pub mod recon;
pub mod schema_sql;
pub mod search;
pub mod search_83;
pub mod search_83_exh;
pub mod search_83_opt;
pub mod search_report;
pub mod sixth_lead2_first80;
pub mod splits;
pub mod starting_market;
pub mod store;
pub mod types;
pub mod validation;
pub mod versions;

pub use batch::{B1RunConfig, FeatureReport, run_b1_batch};
pub use configured_search::{
    ConfiguredSearchReport, ConfiguredSearchSpec, ParameterSpec, estimate_hypothesis_count,
    run_configured_search, run_configured_search_with_progress,
};
pub use dataset::{W8EntryInput, extract_snapshot};
pub use error::B1Error;
pub use extract_first83::{First83ExtractReport, run_first83_extract, run_first83_extract_subset};
pub use prospective83::{
    ProspectiveArgs, ProspectiveReport, frozen_candidates, load_prospective_summary,
    run_prospective_validation,
};
pub use prospective83_engine::{
    prospective83_api_envelope, run_capital_sim_only, run_prospective83_engine,
};
pub use search_83::run_83_condition_search;
pub use search_83_exh::{ExhaustiveArgs, run_83_exhaustive_search};
pub use search_83_opt::run_83_optimal_search;
pub use search_report::{SearchConfig, run_bucket_search};
pub use sixth_lead2_first80::{SixthLead2Report, run_sixth_lead2_first80};
pub use splits::{TEST_END_OBSERVED, TRAIN_BEFORE, VAL_BEFORE, apply_official_chrono_split};
pub use store::FeatureStore;
pub use types::B1EntrySnapshot;
pub use versions::{ARTIFACT_VERSION, WATERFALL};
