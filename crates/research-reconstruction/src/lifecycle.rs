//! Schedule/game lifecycle. Not a W2 GameStatus fork — maps source status text.

use serde::{Deserialize, Serialize};

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum MlbGameLifecycle {
    Scheduled,
    Postponed,
    Cancelled,
    Suspended,
    Final,
    Live,
    Unknown,
}

pub fn classify_schedule_status(status: &str) -> MlbGameLifecycle {
    let s = status.trim().to_ascii_lowercase();
    if s.contains("postpon") {
        MlbGameLifecycle::Postponed
    } else if s.contains("cancel") {
        MlbGameLifecycle::Cancelled
    } else if s.contains("suspend") {
        MlbGameLifecycle::Suspended
    } else if s == "final" {
        MlbGameLifecycle::Final
    } else if s.contains("progress") || s == "live" || s.contains("in progress") {
        MlbGameLifecycle::Live
    } else if s.contains("schedul") || s.contains("preview") || s.contains("pre-game") {
        MlbGameLifecycle::Scheduled
    } else {
        MlbGameLifecycle::Unknown
    }
}

pub fn is_played_final(status: MlbGameLifecycle) -> bool {
    status == MlbGameLifecycle::Final
}
