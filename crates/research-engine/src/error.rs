use thiserror::Error;

#[derive(Debug, Error)]
pub enum EngineError {
    #[error("io: {0}")]
    Io(String),
    #[error("store: {0}")]
    Store(String),
    #[error("validation ({code}): {message}")]
    Validation { code: String, message: String },
    #[error("not found: {0}")]
    NotFound(String),
    #[error("forbidden promotion {from} → {to}")]
    ForbiddenPromotion { from: String, to: String },
    #[error("research: {0}")]
    Research(String),
}

impl EngineError {
    pub fn validation(code: &str, message: impl Into<String>) -> Self {
        Self::Validation {
            code: code.into(),
            message: message.into(),
        }
    }
}

impl From<std::io::Error> for EngineError {
    fn from(e: std::io::Error) -> Self {
        Self::Io(e.to_string())
    }
}

impl From<rusqlite::Error> for EngineError {
    fn from(e: rusqlite::Error) -> Self {
        Self::Store(e.to_string())
    }
}

impl From<serde_json::Error> for EngineError {
    fn from(e: serde_json::Error) -> Self {
        Self::Io(e.to_string())
    }
}

impl From<momento_research_features::B1Error> for EngineError {
    fn from(e: momento_research_features::B1Error) -> Self {
        Self::Research(e.to_string())
    }
}
