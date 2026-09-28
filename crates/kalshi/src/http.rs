//! Shared signed HTTP. Callers must already have refused the wrong environment.

use std::time::Duration;

use momento_core::error::VenueError;

use crate::auth::KalshiCredentials;
use crate::redact::redact_secrets;
use crate::transport::TransportOutcome;

pub(crate) const HTTP_TIMEOUT: Duration = Duration::from_secs(15);

pub(crate) fn agent() -> ureq::Agent {
    ureq::AgentBuilder::new().timeout(HTTP_TIMEOUT).build()
}

pub(crate) fn signed_execute(
    agent: &ureq::Agent,
    creds: &KalshiCredentials,
    method: &str,
    url: &str,
    path_for_sign: &str,
    body: Option<&str>,
) -> Result<TransportOutcome, VenueError> {
    let signed = creds.sign(method, path_for_sign)?;
    let mut req = agent.request(method, url);
    req = req
        .set("KALSHI-ACCESS-KEY", &signed.key_id)
        .set("KALSHI-ACCESS-TIMESTAMP", &signed.timestamp_ms)
        .set("KALSHI-ACCESS-SIGNATURE", &signed.signature)
        .set("Accept", "application/json");
    let result = if let Some(body) = body {
        req.set("Content-Type", "application/json")
            .send_string(body)
    } else {
        req.call()
    };
    match result {
        Ok(resp) => {
            let status = resp.status();
            let body = resp.into_string().unwrap_or_default();
            Ok(TransportOutcome::Http { status, body })
        }
        Err(ureq::Error::Status(status, resp)) => {
            let body = resp.into_string().unwrap_or_default();
            Ok(TransportOutcome::Http { status, body })
        }
        Err(ureq::Error::Transport(t)) => {
            let msg = t.to_string().to_ascii_lowercase();
            if msg.contains("timed out") || msg.contains("timeout") {
                Err(VenueError::Timeout)
            } else {
                Err(VenueError::MalformedResponse(redact_secrets(
                    &t.to_string(),
                )))
            }
        }
    }
}
