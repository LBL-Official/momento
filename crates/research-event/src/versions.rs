//! Version stamps for every W2 transform that can change.

pub const WATERFALL: &str = "W2";
pub const ARTIFACT_VERSION: &str = "W2.2.0";
pub const PARSER_VERSION: &str = "W2.PBP.1.1.0";
pub const NORMALIZATION_VERSION: &str = "W2.NORM.1.0.0";
pub const SCHEMA_VERSION: &str = "W2.EVENT.1.1.0";
pub const STATE_MACHINE_VERSION: &str = "W2.STATE.1.1.0";
/// 1.2.0: observed Kalshi trailing game digit (doubleheader) is part of the
/// suffix crosswalk. Still does not invent `gamePk` from ticker text.
pub const IDENTITY_VERSION: &str = "W2.IDENTITY.1.2.0";
pub const SEQUENCE_VERSION: &str = "W2.SEQ.1.0.0";
pub const EVENT_TIME_DEFINITION_VERSION: &str = "W2.EVENT_TIME.1.0.0";
/// ADR-0005 definition v1: 54 regulation outs; extra innings and walk-offs explicit.
pub const REMAINING_OUTS_DEFINITION_VERSION: &str = "v1-regulation-54";
pub const SOURCE_CONTRACT_VERSION: &str = "W2.SOURCE.1.0.0";
pub const COVERAGE_VERSION: &str = "W2.COVERAGE.1.0.0";
