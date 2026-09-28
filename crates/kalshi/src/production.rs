//! Production Kalshi HTTP that can authenticate but cannot submit orders.
//!
//! Allowlisted GET requests are sent. Any mutating or order path is refused
//! locally and is never transmitted.

use momento_core::error::VenueError;

use crate::auth::{KalshiCredentials, KalshiEnvironment, refuse_if_demo};
use crate::http::{agent, signed_execute};
use crate::transport::{KalshiHttpRequest, KalshiTransport, TransportOutcome};
use crate::types::{
    BALANCE_PATH, CREATE_ORDER_PATH, EVENTS_PATH, EXCHANGE_STATUS_PATH, FILLS_PATH, MARKETS_PATH,
    ORDERS_PATH, POSITIONS_PATH, REST_PRODUCTION_ORIGIN, SETTLEMENTS_PATH,
};

pub fn production_read_only_allows(method: &str, path: &str) -> bool {
    if !method.eq_ignore_ascii_case("GET") {
        return false;
    }
    let path = path.split('?').next().unwrap_or(path);
    path == EXCHANGE_STATUS_PATH
        || path == BALANCE_PATH
        || path == MARKETS_PATH
        || path == FILLS_PATH
        || path == POSITIONS_PATH
        || path.starts_with("/trade-api/v2/markets/")
}

pub fn is_mutating_kalshi_request(method: &str, path: &str) -> bool {
    let method = method.to_ascii_uppercase();
    if matches!(
        method.as_str(),
        "POST" | "PUT" | "PATCH" | "DELETE" | "CONNECT"
    ) {
        return true;
    }
    let path = path.to_ascii_lowercase();
    path.contains("/orders") || path.contains("/order")
}

pub struct ProductionReadOnlyTransport {
    creds: KalshiCredentials,
    origin: String,
    agent: ureq::Agent,
    sent: Vec<String>,
    refused: Vec<KalshiHttpRequest>,
}

impl ProductionReadOnlyTransport {
    pub fn production(creds: KalshiCredentials) -> Result<Self, VenueError> {
        Self::with_origin(creds, REST_PRODUCTION_ORIGIN)
    }

    pub fn with_origin(creds: KalshiCredentials, origin: &str) -> Result<Self, VenueError> {
        if creds.environment() != KalshiEnvironment::Production {
            return Err(VenueError::EnvironmentMismatch);
        }
        refuse_if_demo(origin)?;
        Ok(Self {
            creds,
            origin: origin.trim_end_matches('/').to_string(),
            agent: agent(),
            sent: Vec::new(),
            refused: Vec::new(),
        })
    }

    pub fn origin(&self) -> &str {
        &self.origin
    }

    pub fn sent_paths(&self) -> &[String] {
        &self.sent
    }

    pub fn refused_requests(&self) -> &[KalshiHttpRequest] {
        &self.refused
    }

    pub fn mutating_request_was_sent(&self) -> bool {
        self.sent.iter().any(|p| {
            let (method, path) = p.split_once(' ').unwrap_or(("GET", p.as_str()));
            is_mutating_kalshi_request(method, path)
        })
    }
}

impl KalshiTransport for ProductionReadOnlyTransport {
    fn execute(&mut self, request: KalshiHttpRequest) -> TransportOutcome {
        if !production_read_only_allows(&request.method, &request.path) {
            self.refused.push(request);
            return TransportOutcome::Http {
                status: 0,
                body: VenueError::ProductionReadOnly.to_string(),
            };
        }
        let url = format!("{}{}", self.origin, request.path);
        if refuse_if_demo(&url).is_err() {
            self.refused.push(request);
            return TransportOutcome::Http {
                status: 0,
                body: VenueError::EnvironmentMismatch.to_string(),
            };
        }
        let path_for_sign = request.path.split('?').next().unwrap_or(&request.path);
        match signed_execute(
            &self.agent,
            &self.creds,
            &request.method,
            &url,
            path_for_sign,
            request.body.as_deref(),
        ) {
            Ok(outcome) => {
                self.sent.push(format!(
                    "{} {path_for_sign}",
                    request.method.to_ascii_uppercase()
                ));
                outcome
            }
            Err(VenueError::Timeout) => TransportOutcome::Timeout,
            Err(other) => TransportOutcome::Http {
                status: 0,
                body: other.to_string(),
            },
        }
    }
}

/// Observe allowlist for the NBA worker: GET only. Adds resting orders,
/// settlements, events, series, milestones, and live data to the read-only
/// set. No method other than GET is ever sent.
pub fn production_observe_allows(method: &str, path: &str) -> bool {
    if !method.eq_ignore_ascii_case("GET") {
        return false;
    }
    let path = path.split('?').next().unwrap_or(path);
    production_read_only_allows("GET", path)
        || path == ORDERS_PATH
        || path == SETTLEMENTS_PATH
        || path == EVENTS_PATH
        || path.starts_with("/trade-api/v2/events/")
        || path.starts_with("/trade-api/v2/series/")
        || path == "/trade-api/v2/milestones"
        || path.starts_with("/trade-api/v2/live_data/")
        || path == "/trade-api/v2/portfolio/subaccounts/balances"
        || path == "/trade-api/v2/portfolio/subaccounts/netting"
        || path == "/trade-api/v2/portfolio/target_balance_allocation"
        || path == "/trade-api/v2/account/limits"
        || path == "/trade-api/v2/historical/cutoff"
}

/// Signed production GET-only transport. Refuses every non-GET locally.
pub struct ProductionObserveTransport {
    creds: KalshiCredentials,
    origin: String,
    agent: ureq::Agent,
    sent: Vec<String>,
    sent_total: usize,
    refused: usize,
}

impl ProductionObserveTransport {
    pub fn production(creds: KalshiCredentials) -> Result<Self, VenueError> {
        if creds.environment() != KalshiEnvironment::Production {
            return Err(VenueError::EnvironmentMismatch);
        }
        refuse_if_demo(REST_PRODUCTION_ORIGIN)?;
        Ok(Self {
            creds,
            origin: REST_PRODUCTION_ORIGIN.to_string(),
            agent: agent(),
            sent: Vec::new(),
            sent_total: 0,
            refused: 0,
        })
    }

    pub fn sent_count(&self) -> usize {
        self.sent_total
    }

    pub fn refused_count(&self) -> usize {
        self.refused
    }

    /// True if any non-GET was transmitted. Must always be false.
    pub fn non_get_was_sent(&self) -> bool {
        self.sent.iter().any(|p| !p.starts_with("GET "))
    }
}

impl KalshiTransport for ProductionObserveTransport {
    fn execute(&mut self, request: KalshiHttpRequest) -> TransportOutcome {
        if !production_observe_allows(&request.method, &request.path) || request.body.is_some() {
            self.refused += 1;
            return TransportOutcome::Http {
                status: 0,
                body: VenueError::ProductionReadOnly.to_string(),
            };
        }
        let url = format!("{}{}", self.origin, request.path);
        if refuse_if_demo(&url).is_err() {
            self.refused += 1;
            return TransportOutcome::Http {
                status: 0,
                body: VenueError::EnvironmentMismatch.to_string(),
            };
        }
        let path_for_sign = request.path.split('?').next().unwrap_or(&request.path);
        match signed_execute(&self.agent, &self.creds, "GET", &url, path_for_sign, None) {
            Ok(outcome) => {
                if self.sent.len() >= 64 {
                    self.sent.remove(0);
                }
                self.sent.push(format!("GET {path_for_sign}"));
                self.sent_total += 1;
                outcome
            }
            Err(VenueError::Timeout) => TransportOutcome::Timeout,
            Err(other) => TransportOutcome::Http {
                status: 0,
                body: other.to_string(),
            },
        }
    }
}

/// Local proof that a create-order POST is not on the allowlist.
pub fn create_order_is_blocked() -> bool {
    !production_read_only_allows("POST", CREATE_ORDER_PATH)
        && is_mutating_kalshi_request("POST", CREATE_ORDER_PATH)
}

/// Production HTTP that may submit post-only entries, reduce-only
/// liquidations, and cancels. Amend is not sent.
pub fn production_trading_allows(method: &str, path: &str) -> bool {
    let method_u = method.to_ascii_uppercase();
    let path = path.split('?').next().unwrap_or(path);
    match method_u.as_str() {
        "GET" => path.starts_with("/trade-api/v2/"),
        "POST" => path == CREATE_ORDER_PATH,
        "DELETE" => path.starts_with("/trade-api/v2/portfolio/events/orders/"),
        _ => false,
    }
}

pub struct ProductionTradingTransport {
    creds: KalshiCredentials,
    origin: String,
    agent: ureq::Agent,
}

impl ProductionTradingTransport {
    pub fn production(creds: KalshiCredentials) -> Result<Self, VenueError> {
        if creds.environment() != KalshiEnvironment::Production {
            return Err(VenueError::EnvironmentMismatch);
        }
        refuse_if_demo(REST_PRODUCTION_ORIGIN)?;
        Ok(Self {
            creds,
            origin: REST_PRODUCTION_ORIGIN.to_string(),
            agent: agent(),
        })
    }

    pub fn origin(&self) -> &str {
        &self.origin
    }
}

impl KalshiTransport for ProductionTradingTransport {
    fn execute(&mut self, request: KalshiHttpRequest) -> TransportOutcome {
        if !production_trading_allows(&request.method, &request.path) {
            return TransportOutcome::Http {
                status: 0,
                body: VenueError::Unsupported(
                    "production trading transport refused this method/path".into(),
                )
                .to_string(),
            };
        }
        let url = format!("{}{}", self.origin, request.path);
        if refuse_if_demo(&url).is_err() {
            return TransportOutcome::Http {
                status: 0,
                body: VenueError::EnvironmentMismatch.to_string(),
            };
        }
        let path_for_sign = request.path.split('?').next().unwrap_or(&request.path);
        match signed_execute(
            &self.agent,
            &self.creds,
            &request.method,
            &url,
            path_for_sign,
            request.body.as_deref(),
        ) {
            Ok(outcome) => outcome,
            Err(VenueError::Timeout) => TransportOutcome::Timeout,
            Err(other) => TransportOutcome::Http {
                status: 0,
                body: other.to_string(),
            },
        }
    }
}
