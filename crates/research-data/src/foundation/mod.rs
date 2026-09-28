//! Waterfall 1 — Immutable raw data / canonical data foundation.
//!
//! Additive research-only module. Never writes into the Kalshi lake `raw/`,
//! `orderbook/`, `trades/`, or `manifests/` trees. Never depends on live
//! strategy, risk, or execution.

pub mod availability;
pub mod catalog;
pub mod coverage;
pub mod envelope_v2;
pub mod guard;
pub mod identity_stub;
pub mod integrity;
pub mod ledger;
pub mod observability;
pub mod provenance;
pub mod reporting;
pub mod runner;
pub mod starting_price;
pub mod w2_contract;

pub use availability::KalshiAvailabilityAudit;
pub use catalog::{LakeCatalogV1, LakeFileEntry, LakeLayer, catalog_demo_manifest_slice};
pub use coverage::{CoverageRecord, DIMENSION_VOCABULARY, DimensionStatus, PartitionCoverage};
pub use envelope_v2::{RawEnvelopeV2, envelope_from_v1};
pub use guard::{LakeWriteGuard, assert_lake_class_honest, assert_output_outside_lake};
pub use identity_stub::{IdentityMatchStatus, IdentityStubV1};
pub use integrity::{IntegrityReport, IntegritySeverity};
pub use ledger::{StepStatus, W1_STEPS, WaterfallLedger};
pub use observability::{FieldObservabilityContract, OBSERVABILITY_CONTRACT, ObservabilityKind};
pub use provenance::{
    LakeFileCapture, ProvenanceRecord, SourceTimestampKind, TIMESTAMP_ROLE_NOTES, TimestampRole,
};
pub use runner::{W1RunConfig, W1RunResult, run_w1_foundation};
pub use starting_price::{StartingPriceClass, StartingPriceEvidence};
pub use w2_contract::{RawArtifactRef, RawMarketIdentity, W2_HANDOFF_NOTES};

pub const WATERFALL: &str = "W1";
pub const ARTIFACT_VERSION: &str = "W1.0.0";
pub const CATALOG_VERSION: &str = "1.0.0";
pub const ENVELOPE_V2_SCHEMA: &str = "2.0.0";
