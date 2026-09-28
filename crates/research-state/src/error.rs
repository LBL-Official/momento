//! Fail-closed W6 errors. Impossible states are not repaired.

use thiserror::Error;

#[derive(Clone, Debug, Error, PartialEq, Eq)]
pub enum W6Error {
    #[error("validation ({code}): {message}")]
    Validation {
        code: String,
        game_id: String,
        event_id: String,
        sequence: u32,
        message: String,
    },
    #[error("no canonical state at or before timestamp")]
    NoState,
    #[error("uncommitted or missing artifact: {0}")]
    Uncommitted(String),
    #[error("refused write inside immutable lake {0}")]
    LakeWriteForbidden(String),
    #[error("timeline: {0}")]
    Timeline(String),
    #[error("identity: {0}")]
    Identity(String),
    #[error("store: {0}")]
    Store(String),
    #[error("io: {0}")]
    Io(String),
}

impl W6Error {
    pub fn validation(
        code: &str,
        game_id: impl Into<String>,
        event_id: impl Into<String>,
        sequence: u32,
        message: impl Into<String>,
    ) -> Self {
        Self::Validation {
            code: code.into(),
            game_id: game_id.into(),
            event_id: event_id.into(),
            sequence,
            message: message.into(),
        }
    }
}

impl From<std::io::Error> for W6Error {
    fn from(e: std::io::Error) -> Self {
        Self::Io(e.to_string())
    }
}

impl From<serde_json::Error> for W6Error {
    fn from(e: serde_json::Error) -> Self {
        Self::Io(e.to_string())
    }
}

impl From<rusqlite::Error> for W6Error {
    fn from(e: rusqlite::Error) -> Self {
        Self::Store(e.to_string())
    }
}

impl From<momento_research_event::EventError> for W6Error {
    fn from(e: momento_research_event::EventError) -> Self {
        Self::Timeline(e.to_string())
    }
}
