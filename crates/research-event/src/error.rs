//! Typed reconstruction errors. Never silently repaired.

use thiserror::Error;

#[derive(Clone, Debug, Error, PartialEq, Eq)]
pub enum EventError {
    #[error("missing source identifier: {0}")]
    MissingSourceId(String),
    #[error("duplicate source event {source_event_id} for game {game_id}")]
    DuplicateEvent {
        game_id: String,
        source_event_id: String,
    },
    #[error("identity collision: {0}")]
    IdentityCollision(String),
    #[error("malformed PBP: {0}")]
    Malformed(String),
    #[error("invariant violated ({code}): {message}")]
    Invariant { code: String, message: String },
    #[error("sequence gap: expected {expected}, got {got} for game {game_id}")]
    SequenceGap {
        game_id: String,
        expected: u32,
        got: u32,
    },
    #[error("game mismatch: state={state_game} event={event_game}")]
    GameMismatch {
        state_game: String,
        event_game: String,
    },
    #[error("source conflict: {0}")]
    SourceConflict(String),
    #[error("io: {0}")]
    Io(String),
    #[error("serialization: {0}")]
    Serde(String),
}

impl EventError {
    pub fn invariant(code: &str, message: impl Into<String>) -> Self {
        Self::Invariant {
            code: code.to_string(),
            message: message.into(),
        }
    }
}

impl From<std::io::Error> for EventError {
    fn from(e: std::io::Error) -> Self {
        Self::Io(e.to_string())
    }
}

impl From<serde_json::Error> for EventError {
    fn from(e: serde_json::Error) -> Self {
        Self::Serde(e.to_string())
    }
}
