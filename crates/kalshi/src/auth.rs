//! Kalshi RSA-PSS credentials.
//!
//! Credentials are tagged with [`KalshiEnvironment`]. Demo credentials cannot
//! select production hosts, and production credentials cannot select demo hosts.
//! Presence of credentials does not arm live trading.

use std::fmt;
use std::fs;
use std::path::Path;
use std::time::{SystemTime, UNIX_EPOCH};

use base64::Engine;
use base64::engine::general_purpose::STANDARD as B64;
use momento_core::error::VenueError;
use rand::rngs::OsRng;
use rsa::RsaPrivateKey;
use rsa::pkcs1::DecodeRsaPrivateKey;
use rsa::pkcs8::DecodePrivateKey;
use rsa::pss::BlindedSigningKey;
use rsa::sha2::Sha256;
use rsa::signature::{RandomizedSigner, SignatureEncoding};

use crate::parse::signature_payload;
use crate::secret::{ENV_KALSHI_SECRET_FILE, credentials_from_secret_file};
use crate::types::{
    REST_DEMO, REST_DEMO_ORIGIN, REST_DEMO_SHARED, REST_DEMO_SHARED_ORIGIN, REST_PRODUCTION,
    REST_PRODUCTION_ORIGIN, WS_DEMO, WS_DEMO_SHARED, WS_PRODUCTION,
};

pub const ENV_KALSHI_ENV: &str = "MOMENTO_KALSHI_ENV";
pub const ENV_KALSHI_KEY_ID: &str = "MOMENTO_KALSHI_API_KEY_ID";
pub const ENV_KALSHI_KEY_PATH: &str = "MOMENTO_KALSHI_PRIVATE_KEY_PATH";

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum KalshiEnvironment {
    Demo,
    Production,
}

#[derive(Clone)]
pub struct SignedHeaders {
    pub key_id: String,
    pub timestamp_ms: String,
    pub signature: String,
}

impl fmt::Debug for SignedHeaders {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.debug_struct("SignedHeaders")
            .field("key_id", &"[REDACTED]")
            .field("timestamp_ms", &self.timestamp_ms)
            .field("signature", &"[REDACTED]")
            .finish()
    }
}

#[derive(Clone)]
pub struct KalshiCredentials {
    env: KalshiEnvironment,
    key_id: String,
    private_key: RsaPrivateKey,
}

/// Demo-only credentials. Prefer [`KalshiCredentials`] for new code.
pub type SandboxCredentials = KalshiCredentials;

impl fmt::Debug for KalshiCredentials {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.debug_struct("KalshiCredentials")
            .field("env", &self.env)
            .field("key_id", &"[REDACTED]")
            .finish_non_exhaustive()
    }
}

impl KalshiCredentials {
    pub fn from_pem(
        env: KalshiEnvironment,
        key_id: impl Into<String>,
        pem: &str,
    ) -> Result<Self, VenueError> {
        let key_id = key_id.into();
        if key_id.trim().is_empty() {
            return Err(VenueError::AuthenticationFailed);
        }
        let private_key = RsaPrivateKey::from_pkcs1_pem(pem)
            .or_else(|_| RsaPrivateKey::from_pkcs8_pem(pem))
            .map_err(|e| VenueError::MalformedResponse(format!("invalid RSA private key: {e}")))?;
        Ok(Self {
            env,
            key_id,
            private_key,
        })
    }

    pub fn from_pem_file(
        env: KalshiEnvironment,
        key_id: impl Into<String>,
        path: &Path,
    ) -> Result<Self, VenueError> {
        let pem = fs::read_to_string(path)
            .map_err(|e| VenueError::MalformedResponse(format!("private key path: {e}")))?;
        Self::from_pem(env, key_id, &pem)
    }

    /// Loads **demo** credentials. Production env is refused.
    pub fn from_env() -> Result<Self, VenueError> {
        require_demo_env()?;
        Self::from_env_for(KalshiEnvironment::Demo)
    }

    /// Loads **production** credentials. Demo env is refused.
    pub fn from_production_env() -> Result<Self, VenueError> {
        require_production_env()?;
        Self::from_env_for(KalshiEnvironment::Production)
    }

    fn from_env_for(env: KalshiEnvironment) -> Result<Self, VenueError> {
        if let Ok(path) = std::env::var(ENV_KALSHI_SECRET_FILE) {
            return credentials_from_secret_file(env, Path::new(&path));
        }
        let key_id = std::env::var(ENV_KALSHI_KEY_ID).map_err(|_| {
            VenueError::MalformedResponse(format!("{ENV_KALSHI_KEY_ID} is required"))
        })?;
        let path = std::env::var(ENV_KALSHI_KEY_PATH).map_err(|_| {
            VenueError::MalformedResponse(format!("{ENV_KALSHI_KEY_PATH} is required"))
        })?;
        Self::from_pem_file(env, key_id, Path::new(&path))
    }

    pub fn environment(&self) -> KalshiEnvironment {
        self.env
    }

    pub fn sign(&self, method: &str, path: &str) -> Result<SignedHeaders, VenueError> {
        let timestamp_ms = unix_ms()?.to_string();
        let payload = signature_payload(&timestamp_ms, method, path);
        let signing_key = BlindedSigningKey::<Sha256>::new(self.private_key.clone());
        let sig = signing_key.sign_with_rng(&mut OsRng, payload.as_bytes());
        Ok(SignedHeaders {
            key_id: self.key_id.clone(),
            timestamp_ms,
            signature: B64.encode(sig.to_bytes()),
        })
    }
}

pub fn require_demo_env() -> Result<(), VenueError> {
    match env_label()?.as_str() {
        "demo" | "sandbox" => Ok(()),
        "production" | "prod" | "live" => Err(VenueError::ProductionForbidden),
        _ => Err(VenueError::SandboxEnvRequired),
    }
}

pub fn require_production_env() -> Result<(), VenueError> {
    match env_label()?.as_str() {
        "production" | "prod" => Ok(()),
        "demo" | "sandbox" => Err(VenueError::EnvironmentMismatch),
        "live" => Err(VenueError::ProductionForbidden),
        _ => Err(VenueError::ProductionEnvRequired),
    }
}

fn env_label() -> Result<String, VenueError> {
    Ok(std::env::var(ENV_KALSHI_ENV)
        .unwrap_or_default()
        .trim()
        .to_ascii_lowercase())
}

pub fn unix_ms() -> Result<u128, VenueError> {
    Ok(SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map_err(|e| VenueError::MalformedResponse(e.to_string()))?
        .as_millis())
}

pub fn is_production_url(url: &str) -> bool {
    let lower = url.to_ascii_lowercase();
    let host = host_of(&lower);
    (host.contains("kalshi.com") && !host.contains("demo"))
        || lower.starts_with(REST_PRODUCTION)
        || lower.starts_with(REST_PRODUCTION_ORIGIN)
        || lower.starts_with(WS_PRODUCTION)
}

pub fn is_demo_url(url: &str) -> bool {
    let lower = url.to_ascii_lowercase();
    let host = host_of(&lower);
    host.contains("demo.kalshi.co")
        || host == "demo-api.kalshi.co"
        || lower.starts_with(REST_DEMO)
        || lower.starts_with(REST_DEMO_SHARED)
        || lower.starts_with(WS_DEMO)
        || lower.starts_with(WS_DEMO_SHARED)
        || lower.starts_with(REST_DEMO_ORIGIN)
        || lower.starts_with(REST_DEMO_SHARED_ORIGIN)
}

pub fn refuse_if_production(url: &str) -> Result<(), VenueError> {
    if is_production_url(url) || !is_demo_url(url) {
        Err(VenueError::ProductionForbidden)
    } else {
        Ok(())
    }
}

pub fn refuse_if_demo(url: &str) -> Result<(), VenueError> {
    if is_demo_url(url) || !is_production_url(url) {
        Err(VenueError::EnvironmentMismatch)
    } else {
        Ok(())
    }
}

pub fn require_host_matches_credentials(
    env: KalshiEnvironment,
    url: &str,
) -> Result<(), VenueError> {
    match env {
        KalshiEnvironment::Demo => refuse_if_production(url),
        KalshiEnvironment::Production => refuse_if_demo(url),
    }
}

fn host_of(url: &str) -> String {
    let rest = url.split_once("://").map(|(_, rest)| rest).unwrap_or(url);
    rest.split('/').next().unwrap_or(rest).to_string()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn production_hosts_are_forbidden_for_sandbox() {
        assert!(refuse_if_production(REST_PRODUCTION).is_err());
        assert!(refuse_if_production(WS_PRODUCTION).is_err());
        assert!(refuse_if_production("https://api.elections.kalshi.com/trade-api/v2").is_err());
        assert!(refuse_if_production(REST_DEMO).is_ok());
        assert!(refuse_if_production(REST_DEMO_SHARED).is_ok());
        assert!(refuse_if_production(WS_DEMO_SHARED).is_ok());
    }

    #[test]
    fn demo_hosts_are_forbidden_for_production() {
        assert!(refuse_if_demo(REST_DEMO).is_err());
        assert!(refuse_if_demo(REST_DEMO_SHARED).is_err());
        assert!(refuse_if_demo(REST_PRODUCTION).is_ok());
        assert!(
            require_host_matches_credentials(KalshiEnvironment::Demo, REST_PRODUCTION).is_err()
        );
        assert!(
            require_host_matches_credentials(KalshiEnvironment::Production, REST_DEMO_SHARED)
                .is_err()
        );
        assert!(
            require_host_matches_credentials(KalshiEnvironment::Production, REST_PRODUCTION)
                .is_ok()
        );
    }

    #[test]
    fn production_env_is_forbidden() {
        assert!(is_production_url(
            "https://external-api.kalshi.com/trade-api/v2"
        ));
        assert!(!is_production_url(
            "https://demo-api.kalshi.co/trade-api/v2"
        ));
    }
}
