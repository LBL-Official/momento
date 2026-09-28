//! Game period from Kalshi `live_data` (basketball_game). Q2 and Q3 only.

use std::collections::VecDeque;

use serde::{Deserialize, Serialize};

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct ClockObservation {
    /// When this worker received the payload (unix seconds).
    pub received_at: i64,
    /// Source `last_updated_ts` (unix seconds), if sent.
    pub source_updated_at: Option<i64>,
    pub status: String,
    pub period: Option<u8>,
    pub period_type: Option<String>,
    pub period_remaining: Option<String>,
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(
    tag = "bucket",
    content = "reason",
    rename_all = "SCREAMING_SNAKE_CASE"
)]
pub enum Bucket {
    Pregame,
    Q1,
    Q2,
    Q3,
    Q4,
    Overtime,
    PeriodBreak,
    Final,
    Unavailable(String),
}

impl Bucket {
    pub fn eligible(&self) -> bool {
        matches!(self, Bucket::Q2 | Bucket::Q3)
    }

    pub fn label(&self) -> String {
        match self {
            Bucket::Unavailable(reason) => format!("CLOCK_UNAVAILABLE:{reason}"),
            other => serde_json::to_value(other)
                .ok()
                .and_then(|v| v.get("bucket").and_then(|b| b.as_str()).map(str::to_string))
                .unwrap_or_else(|| "UNKNOWN".into()),
        }
    }
}

/// Seconds the source may lag the receive time before the clock is stale.
pub const SOURCE_MAX_LAG_S: i64 = 300;

/// Period at `signal_ts` from the observation nearest that time.
pub fn bucket_for(history: &ClockHistory, signal_ts: i64, max_age_s: i64) -> Bucket {
    let Some(obs) = history.nearest(signal_ts) else {
        return Bucket::Unavailable("NO_OBSERVATION".into());
    };
    if (obs.received_at - signal_ts).abs() > max_age_s {
        return Bucket::Unavailable("OBSERVATION_TOO_FAR_FROM_SIGNAL".into());
    }
    classify(obs)
}

pub fn classify(obs: &ClockObservation) -> Bucket {
    match obs.status.as_str() {
        "scheduled" | "created" | "not_started" => return Bucket::Pregame,
        "closed" | "complete" | "completed" => return Bucket::Final,
        "halftime" => return Bucket::PeriodBreak,
        "inprogress" => {}
        other => return Bucket::Unavailable(format!("STATUS_{other}")),
    }
    if let Some(updated) = obs.source_updated_at
        && obs.received_at - updated > SOURCE_MAX_LAG_S
    {
        return Bucket::Unavailable("SOURCE_STALE".into());
    }
    if obs.period_type.as_deref() != Some("quarter") {
        return Bucket::Unavailable("NOT_QUARTERS".into());
    }
    let Some(period) = obs.period else {
        return Bucket::Unavailable("PERIOD_MISSING".into());
    };
    if obs.period_remaining.as_deref() == Some("00:00") {
        return Bucket::PeriodBreak;
    }
    match period {
        1 => Bucket::Q1,
        2 => Bucket::Q2,
        3 => Bucket::Q3,
        4 => Bucket::Q4,
        p if p > 4 => Bucket::Overtime,
        _ => Bucket::Unavailable("PERIOD_ZERO".into()),
    }
}

/// Bounded recent observations for one game.
#[derive(Clone, Debug, Default, Serialize, Deserialize)]
pub struct ClockHistory {
    items: VecDeque<ClockObservation>,
}

impl ClockHistory {
    pub const CAPACITY: usize = 64;

    pub fn push(&mut self, obs: ClockObservation) {
        if self.items.len() == Self::CAPACITY {
            self.items.pop_front();
        }
        self.items.push_back(obs);
    }

    pub fn latest(&self) -> Option<&ClockObservation> {
        self.items.back()
    }

    pub fn nearest(&self, ts: i64) -> Option<&ClockObservation> {
        self.items
            .iter()
            .min_by_key(|o| ((o.received_at - ts).abs(), -o.received_at))
    }
}
