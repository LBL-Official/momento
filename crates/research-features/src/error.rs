//! Fail-closed B1 errors. Never invent L2, fills, or settlement.

use thiserror::Error;

#[derive(Clone, Debug, Error, PartialEq, Eq)]
pub enum B1Error {
    #[error("uncommitted or missing artifact: {0}")]
    Uncommitted(String),
    #[error("refused write inside immutable lake {0}")]
    LakeWriteForbidden(String),
    #[error("validation ({code}): {message}")]
    Validation { code: String, message: String },
    #[error("store: {0}")]
    Store(String),
    #[error("io: {0}")]
    Io(String),
}

impl B1Error {
    pub fn validation(code: &str, message: impl Into<String>) -> Self {
        Self::Validation {
            code: code.into(),
            message: message.into(),
        }
    }
}

impl From<std::io::Error> for B1Error {
    fn from(e: std::io::Error) -> Self {
        Self::Io(e.to_string())
    }
}

impl From<serde_json::Error> for B1Error {
    fn from(e: serde_json::Error) -> Self {
        Self::Io(e.to_string())
    }
}

impl From<rusqlite::Error> for B1Error {
    fn from(e: rusqlite::Error) -> Self {
        Self::Store(e.to_string())
    }
}

impl From<momento_research_path::W7Error> for B1Error {
    fn from(e: momento_research_path::W7Error) -> Self {
        Self::Uncommitted(e.to_string())
    }
}

impl From<momento_research_state::W6Error> for B1Error {
    fn from(e: momento_research_state::W6Error) -> Self {
        Self::Uncommitted(e.to_string())
    }
}
