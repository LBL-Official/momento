//! Input sheet status state machine.

use crate::error::{BacktestError, BacktestErrorCode};
use crate::sheet_contract::RunStatus;

/// Advance status along the allowed transitions.
pub fn advance_status(from: RunStatus, to: RunStatus) -> Result<RunStatus, BacktestError> {
    let ok = matches!(
        (from, to),
        (RunStatus::Queued, RunStatus::Validating)
            | (RunStatus::Validating, RunStatus::Running)
            | (RunStatus::Validating, RunStatus::Invalid)
            | (RunStatus::Running, RunStatus::Complete)
            | (RunStatus::Running, RunStatus::Error)
            | (RunStatus::Queued, RunStatus::Invalid)
            | (RunStatus::Queued, RunStatus::Running) // allow skip validating in simple runner
    );
    if ok {
        Ok(to)
    } else {
        Err(BacktestError::coded(
            BacktestErrorCode::InvalidStatus,
            format!(
                "illegal status transition {} → {}",
                from.as_str(),
                to.as_str()
            ),
        ))
    }
}

pub fn is_terminal(status: RunStatus) -> bool {
    matches!(
        status,
        RunStatus::Complete | RunStatus::Error | RunStatus::Invalid
    )
}

pub fn should_process(status: RunStatus) -> bool {
    status == RunStatus::Queued
}
