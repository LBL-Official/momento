//! Warehouse errors. Never silently recover from inconsistent catalog state.

use thiserror::Error;

#[derive(Debug, Error)]
pub enum WarehouseError {
    #[error("kalshi public API: {0}")]
    Api(String),
    #[error("io: {0}")]
    Io(#[from] std::io::Error),
    #[error("json: {0}")]
    Json(#[from] serde_json::Error),
    #[error("schema: {0}")]
    Schema(String),
    #[error("validation failed: {0}")]
    Validation(String),
    #[error("pagination refused silent truncate: {0}")]
    Pagination(String),
}

impl WarehouseError {
    pub fn api(err: impl std::fmt::Display) -> Self {
        Self::Api(err.to_string())
    }
}
