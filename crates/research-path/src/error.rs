//! Fail-closed W7 errors. Never interpolate state or shift timestamps.

use thiserror::Error;

#[derive(Clone, Debug, Error, PartialEq, Eq)]
pub enum W7Error {
    #[error("unjoinable ({code}): {message}")]
    Unjoinable { code: String, message: String },
    #[error("validation ({code}): {message}")]
    Validation { code: String, message: String },
    #[error("uncommitted or missing artifact: {0}")]
    Uncommitted(String),
    #[error("refused write inside immutable lake {0}")]
    LakeWriteForbidden(String),
    #[error("store: {0}")]
    Store(String),
    #[error("io: {0}")]
    Io(String),
}

impl W7Error {
    pub fn unjoinable(code: &str, message: impl Into<String>) -> Self {
        Self::Unjoinable {
            code: code.into(),
            message: message.into(),
        }
    }

    pub fn validation(code: &str, message: impl Into<String>) -> Self {
        Self::Validation {
            code: code.into(),
            message: message.into(),
        }
    }
}

impl From<std::io::Error> for W7Error {
    fn from(e: std::io::Error) -> Self {
        Self::Io(e.to_string())
    }
}

impl From<serde_json::Error> for W7Error {
    fn from(e: serde_json::Error) -> Self {
        Self::Io(e.to_string())
    }
}

impl From<rusqlite::Error> for W7Error {
    fn from(e: rusqlite::Error) -> Self {
        Self::Store(e.to_string())
    }
}

impl From<momento_research_sync::W5Error> for W7Error {
    fn from(e: momento_research_sync::W5Error) -> Self {
        Self::Uncommitted(e.to_string())
    }
}

impl From<momento_research_state::W6Error> for W7Error {
    fn from(e: momento_research_state::W6Error) -> Self {
        Self::Uncommitted(e.to_string())
    }
}
