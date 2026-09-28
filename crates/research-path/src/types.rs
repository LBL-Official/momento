//! Canonical EventMarketPath types. Trades remain trades. No invented L2.

use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};

use crate::versions::{CAUSAL_VERSION, JOIN_VERSION, OBSERVATION_KIND_TRADE};

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum PathJoinStatus {
    Synchronized,
    AtEvent,
    SynchronizedWithTimestampGap,
    BeforeFirstEvent,
    AfterLastEvent,
    NoGameState,
    Unsynchronizable,
    Unjoinable,
    Rejected,
    ValidationFailure,
}

impl PathJoinStatus {
    pub fn as_str(self) -> &'static str {
        match self {
            Self::Synchronized => "SYNCHRONIZED",
            Self::AtEvent => "AT_EVENT",
            Self::SynchronizedWithTimestampGap => "SYNCHRONIZED_WITH_TIMESTAMP_GAP",
            Self::BeforeFirstEvent => "BEFORE_FIRST_EVENT",
            Self::AfterLastEvent => "AFTER_LAST_EVENT",
            Self::NoGameState => "NO_GAME_STATE",
            Self::Unsynchronizable => "UNSYNCHRONIZABLE",
            Self::Unjoinable => "UNJOINABLE",
            Self::Rejected => "REJECTED_WITH_REASON",
            Self::ValidationFailure => "VALIDATION_FAILURE",
        }
    }

    pub fn has_applicable_state(self) -> bool {
        matches!(
            self,
            Self::Synchronized | Self::AtEvent | Self::SynchronizedWithTimestampGap
        )
    }
}

/// One chronological observation on a GameId × MarketId × side path.
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct PathObservation {
    pub path_observation_id: String,
    pub path_id: String,
    pub game_id: String,
    pub game_pk: String,
    pub market_id: String,
    pub ticker: String,
    pub contract_id: String,
    pub contract_side: String,
    pub observation_id: String,
    pub w5_synchronization_id: String,
    pub observation_kind: String,
    pub market_timestamp_utc: Option<DateTime<Utc>>,
    pub matched_state_timestamp_utc: Option<DateTime<Utc>>,
    pub event_lag_ms: Option<i64>,
    pub synchronization_status: String,
    pub synchronization_quality: String,
    pub join_status: PathJoinStatus,
    pub timestamp_relation: String,
    pub trade_price_cents: Option<i32>,
    pub trade_size_hundredths: Option<i64>,
    pub source_observation_id: Option<String>,
    pub source_lineage: String,
    pub state_id: Option<String>,
    pub state_seq: Option<u32>,
    pub previous_state_id: Option<String>,
    pub previous_state_seq: Option<u32>,
    pub transition_id: Option<String>,
    pub transition_event_type: Option<String>,
    /// Diagnostic only. Never used for assignment or causal features.
    pub next_state_id: Option<String>,
    pub next_state_seq: Option<u32>,
    pub inning: Option<u8>,
    pub half: Option<String>,
    pub outs: Option<u8>,
    pub score_home: Option<u16>,
    pub score_away: Option<u16>,
    pub run_differential: Option<i32>,
    pub bases_bitmask: Option<u8>,
    pub batter_id: Option<String>,
    pub pitcher_id: Option<String>,
    pub balls: Option<u8>,
    pub strikes: Option<u8>,
    pub game_status: Option<String>,
    pub chrono_index: u32,
    pub previous_trade_price_cents: Option<i32>,
    pub price_change_cents: Option<i32>,
    pub cumulative_trade_count: u32,
    pub time_since_previous_trade_ms: Option<i64>,
    pub time_since_state_transition_ms: Option<i64>,
    pub observed_high_cents_so_far: Option<i32>,
    pub observed_low_cents_so_far: Option<i32>,
    pub distance_from_high_cents: Option<i32>,
    pub distance_from_low_cents: Option<i32>,
    pub prior_price_changes: u32,
    pub causal_version: String,
    pub join_version: String,
    pub w5_dataset_version: String,
    pub w6_dataset_version: String,
    pub w7_version: String,
}

impl PathObservation {
    pub fn trade_kind() -> &'static str {
        OBSERVATION_KIND_TRADE
    }

    pub fn versions() -> (&'static str, &'static str) {
        (JOIN_VERSION, CAUSAL_VERSION)
    }
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct EventMarketPath {
    pub path_id: String,
    pub game_id: String,
    pub game_pk: String,
    pub market_id: String,
    pub contract_side: String,
    pub observations: Vec<PathObservation>,
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct StateSegment {
    pub path_id: String,
    pub game_id: String,
    pub market_id: String,
    pub contract_side: String,
    pub state_id: String,
    pub state_seq: u32,
    pub observation_count: u32,
    pub first_market_timestamp_utc: Option<DateTime<Utc>>,
    pub last_market_timestamp_utc: Option<DateTime<Utc>>,
}

pub fn occupancy_label(mask: u8) -> String {
    let f = if mask & 1 != 0 { '1' } else { '_' };
    let s = if mask & 2 != 0 { '2' } else { '_' };
    let t = if mask & 4 != 0 { '3' } else { '_' };
    format!("{f}{s}{t}")
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct GamePathCoverage {
    pub game_id: String,
    pub game_pk: String,
    pub observations: usize,
    pub synchronized: usize,
    pub before_first: usize,
    pub after_last: usize,
    pub at_event: usize,
    pub with_gap: usize,
    pub no_game_state: usize,
    pub coverage: String,
}
