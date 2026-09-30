//! Operating mode is derived from state, never set directly.

use serde::{Deserialize, Serialize};

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum ConfigMode {
    LiveDataOnly,
    Shadow,
    Live,
    /// Supervised FIRST78 Live V1 collector. Production submission stays compiled out.
    First78LiveV1,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum Mode {
    LiveDataOnly,
    Shadow,
    ArmedWaitingDate,
    ArmedWaitingFunds,
    LiveExecuting,
    ReconciliationHold,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct ModeInputs {
    pub config: ConfigMode,
    pub live_gates_set: bool,
    pub reconciliation_healthy: bool,
    /// Blocker codes other than funds and date (contract, fees, route,
    /// collateral, adapter). Any entry keeps the worker out of ARMED.
    pub hard_blockers: Vec<String>,
    pub funds_sufficient: bool,
    pub eligible_market_listed: bool,
}

pub fn derive_mode(i: &ModeInputs) -> Mode {
    if !i.reconciliation_healthy {
        return Mode::ReconciliationHold;
    }
    match i.config {
        ConfigMode::LiveDataOnly => Mode::LiveDataOnly,
        ConfigMode::Shadow | ConfigMode::First78LiveV1 => Mode::Shadow,
        ConfigMode::Live => {
            if !i.live_gates_set || !i.hard_blockers.is_empty() {
                Mode::Shadow
            } else if !i.funds_sufficient {
                Mode::ArmedWaitingFunds
            } else if !i.eligible_market_listed {
                Mode::ArmedWaitingDate
            } else {
                Mode::LiveExecuting
            }
        }
    }
}
