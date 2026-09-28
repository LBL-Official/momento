//! Fail-closed W3 errors.

use thiserror::Error;

#[derive(Clone, Debug, Error, PartialEq, Eq)]
pub enum W3Error {
    #[error("uncommitted or unverified artifact: {0}")]
    Uncommitted(String),
    #[error("checksum mismatch for {path}: expected {expected}, got {actual}")]
    ChecksumMismatch {
        path: String,
        expected: String,
        actual: String,
    },
    #[error("refused write inside immutable lake {0}")]
    LakeWriteForbidden(String),
    #[error("synthetic fixture mixed into historical coverage")]
    SyntheticInHistorical,
    #[error("io: {0}")]
    Io(String),
    #[error("reconstruction: {0}")]
    Reconstruction(String),
}

impl From<std::io::Error> for W3Error {
    fn from(e: std::io::Error) -> Self {
        Self::Io(e.to_string())
    }
}

impl From<serde_json::Error> for W3Error {
    fn from(e: serde_json::Error) -> Self {
        Self::Io(e.to_string())
    }
}
