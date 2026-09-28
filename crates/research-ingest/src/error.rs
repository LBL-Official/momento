//! Fail-closed ingest errors. No silent infinite retry.

use thiserror::Error;

#[derive(Clone, Debug, Error, PartialEq, Eq)]
pub enum IngestError {
    #[error("concurrent ingest writer holds {0}")]
    ConcurrentWriter(String),
    #[error("W2 refused uncommitted or unverified W1 artifact: {0}")]
    UncommittedW1(String),
    #[error("checksum mismatch for {path}: expected {expected}, got {actual}")]
    ChecksumMismatch {
        path: String,
        expected: String,
        actual: String,
    },
    #[error("refused write inside immutable lake {0}")]
    LakeWriteForbidden(String),
    #[error("refused write {path}: {reason}")]
    PathForbidden { path: String, reason: String },
    #[error("sport adapter not implemented: {0}")]
    SportNotImplemented(String),
    #[error("network ingest not authorized: {0}")]
    NetworkUnauthorized(String),
    #[error("source failure: {0}")]
    SourceFailure(String),
    #[error("bounded retries exhausted for {0}")]
    RetryExhausted(String),
    #[error("io: {0}")]
    Io(String),
    #[error("serialization: {0}")]
    Serde(String),
}

impl From<std::io::Error> for IngestError {
    fn from(e: std::io::Error) -> Self {
        Self::Io(e.to_string())
    }
}

impl From<serde_json::Error> for IngestError {
    fn from(e: serde_json::Error) -> Self {
        Self::Serde(e.to_string())
    }
}
