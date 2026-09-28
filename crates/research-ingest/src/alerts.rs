//! Structured ingest alerts. Alerts never mutate research state.

use serde::{Deserialize, Serialize};

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum AlertKind {
    SourceUnavailable,
    RepeatedSourceFailure,
    ChecksumConflict,
    VersionConflict,
    UnexpectedCoverageDrop,
    IdentityAmbiguity,
    DuplicateLogicalArtifact,
    ConcurrentRunLock,
    W1CommitFailure,
    DownstreamHandoffRefusal,
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct Alert {
    pub kind: AlertKind,
    pub message: String,
}

impl Alert {
    pub fn new(kind: AlertKind, message: impl Into<String>) -> Self {
        Self {
            kind,
            message: message.into(),
        }
    }
}
