//! Parse Kalshi credential JSON retrieved from AWS Secrets Manager.
//! This module does not call AWS. The secret string must never be logged.

use serde::Deserialize;

use momento_core::error::VenueError;

use crate::auth::{KalshiCredentials, KalshiEnvironment};
use crate::redact::redact_secrets;

pub const ENV_KALSHI_SECRET_FILE: &str = "MOMENTO_KALSHI_SECRET_FILE";
pub const ENV_KALSHI_SECRET_ARN: &str = "MOMENTO_KALSHI_SECRET_ARN";

#[derive(Deserialize)]
struct SecretPayload {
    environment: String,
    api_key_id: String,
    private_key_pem: String,
}

/// Load credentials from a Secrets Manager JSON document.
///
/// Expected shape (values never logged):
/// `{ "environment": "production", "api_key_id": "...", "private_key_pem": "..." }`
pub fn credentials_from_secret_json(
    expected: KalshiEnvironment,
    json: &str,
) -> Result<KalshiCredentials, VenueError> {
    let parsed: SecretPayload = serde_json::from_str(json).map_err(|e| {
        VenueError::MalformedResponse(format!(
            "kalshi secret json: {}",
            redact_secrets(&e.to_string())
        ))
    })?;
    let tagged = match parsed.environment.trim().to_ascii_lowercase().as_str() {
        "demo" | "sandbox" => KalshiEnvironment::Demo,
        "production" | "prod" => KalshiEnvironment::Production,
        _ => return Err(VenueError::EnvironmentMismatch),
    };
    if tagged != expected {
        return Err(VenueError::EnvironmentMismatch);
    }
    KalshiCredentials::from_pem(expected, parsed.api_key_id, &parsed.private_key_pem)
}

pub fn credentials_from_secret_file(
    expected: KalshiEnvironment,
    path: &std::path::Path,
) -> Result<KalshiCredentials, VenueError> {
    let json = std::fs::read_to_string(path)
        .map_err(|e| VenueError::MalformedResponse(format!("kalshi secret file: {e}")))?;
    credentials_from_secret_json(expected, &json)
}
