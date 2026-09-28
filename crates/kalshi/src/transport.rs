//! Mockable Kalshi HTTP. No live sockets.

use std::collections::VecDeque;

use momento_core::error::VenueError;

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct KalshiHttpRequest {
    pub method: String,
    pub path: String,
    pub body: Option<String>,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub enum TransportOutcome {
    Http { status: u16, body: String },
    Timeout,
}

pub trait KalshiTransport {
    fn execute(&mut self, request: KalshiHttpRequest) -> TransportOutcome;
}

/// Production/live HTTP is intentionally unavailable in M4.
#[derive(Clone, Debug, Default)]
pub struct DisabledLiveTransport;

impl KalshiTransport for DisabledLiveTransport {
    fn execute(&mut self, _request: KalshiHttpRequest) -> TransportOutcome {
        TransportOutcome::Http {
            status: 0,
            body: String::new(),
        }
    }
}

impl DisabledLiveTransport {
    pub fn refuse(&self) -> VenueError {
        VenueError::LiveDisabled
    }
}

#[derive(Clone, Debug, Default)]
pub struct ScriptedTransport {
    outcomes: VecDeque<TransportOutcome>,
    pub last_request: Option<KalshiHttpRequest>,
}

impl ScriptedTransport {
    pub fn new(outcomes: impl IntoIterator<Item = TransportOutcome>) -> Self {
        Self {
            outcomes: outcomes.into_iter().collect(),
            last_request: None,
        }
    }
}

impl KalshiTransport for ScriptedTransport {
    fn execute(&mut self, request: KalshiHttpRequest) -> TransportOutcome {
        self.last_request = Some(request);
        self.outcomes
            .pop_front()
            .unwrap_or(TransportOutcome::Timeout)
    }
}
