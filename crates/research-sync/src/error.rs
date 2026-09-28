//! Fail-closed W5 errors.

use thiserror::Error;

#[derive(Clone, Debug, Error, PartialEq, Eq)]
pub enum W5Error {
    #[error("uncommitted or missing artifact: {0}")]
    Uncommitted(String),
    #[error("refused write inside immutable lake {0}")]
    LakeWriteForbidden(String),
    #[error("invalid timestamp: {0}")]
    InvalidTimestamp(String),
    #[error("timeline: {0}")]
    Timeline(String),
    #[error("identity: {0}")]
    Identity(String),
    #[error("store: {0}")]
    Store(String),
    #[error("io: {0}")]
    Io(String),
}

impl From<std::io::Error> for W5Error {
    fn from(e: std::io::Error) -> Self {
        Self::Io(e.to_string())
    }
}

impl From<serde_json::Error> for W5Error {
    fn from(e: serde_json::Error) -> Self {
        Self::Io(e.to_string())
    }
}

impl From<rusqlite::Error> for W5Error {
    fn from(e: rusqlite::Error) -> Self {
        Self::Store(e.to_string())
    }
}
