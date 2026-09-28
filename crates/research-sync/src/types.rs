//! Canonical W5 sync types. Integer cents. No invented L2 or starting price.

use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};

use crate::versions::METHOD_AS_OF_PRIOR_EVENT;

pub const KIND_PBP_OFFICIAL: &str = "PBP_OFFICIAL";
pub const KIND_KALSHI_TRADE_CREATED: &str = "KALSHI_TRADE_CREATED";
pub const KIND_KALSHI_QUOTE: &str = "KALSHI_QUOTE";
pub const KIND_KALSHI_CANDLE: &str = "KALSHI_CANDLE";
pub const KIND_KALSHI_L2: &str = "KALSHI_L2";
pub const KIND_MISSING: &str = "MISSING_TIMESTAMP";

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum ObservationType {
    Trade,
    Quote,
    Candle,
    L2Snapshot,
    L2Delta,
}

impl ObservationType {
    pub fn as_str(self) -> &'static str {
        match self {
            Self::Trade => "TRADE",
            Self::Quote => "QUOTE",
            Self::Candle => "CANDLE",
            Self::L2Snapshot => "L2_SNAPSHOT",
            Self::L2Delta => "L2_DELTA",
        }
    }
}

/// Primary synchronization classification. Failures are retained, never dropped.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum SyncStatus {
    Synchronized,
    AtEvent,
    SynchronizedWithTimestampGap,
    BeforeFirstEvent,
    AfterLastEvent,
    AmbiguousTimestamp,
    MissingTimestamp,
    IdentityUnmatched,
    IdentityAmbiguous,
    SourceDataInvalid,
}

impl SyncStatus {
    pub fn as_str(self) -> &'static str {
        match self {
            Self::Synchronized => "SYNCHRONIZED",
            Self::AtEvent => "AT_EVENT",
            Self::SynchronizedWithTimestampGap => "SYNCHRONIZED_WITH_TIMESTAMP_GAP",
            Self::BeforeFirstEvent => "BEFORE_FIRST_EVENT",
            Self::AfterLastEvent => "AFTER_LAST_EVENT",
            Self::AmbiguousTimestamp => "AMBIGUOUS_TIMESTAMP",
            Self::MissingTimestamp => "MISSING_TIMESTAMP",
            Self::IdentityUnmatched => "IDENTITY_UNMATCHED",
            Self::IdentityAmbiguous => "IDENTITY_AMBIGUOUS",
            Self::SourceDataInvalid => "SOURCE_DATA_INVALID",
        }
    }

    pub fn is_success(self) -> bool {
        matches!(
            self,
            Self::Synchronized | Self::AtEvent | Self::SynchronizedWithTimestampGap
        )
    }
}

/// Collision / placement relative to the matched MLB event timestamp.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum TimestampRelation {
    BeforeEvent,
    AtEvent,
    AfterEvent,
    AmbiguousTimestamp,
    NotApplicable,
}

impl TimestampRelation {
    pub fn as_str(self) -> &'static str {
        match self {
            Self::BeforeEvent => "BEFORE_EVENT",
            Self::AtEvent => "AT_EVENT",
            Self::AfterEvent => "AFTER_EVENT",
            Self::AmbiguousTimestamp => "AMBIGUOUS_TIMESTAMP",
            Self::NotApplicable => "NOT_APPLICABLE",
        }
    }
}

/// ADR-0003 join confidence. Never silently upgraded to EXACT.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum SyncQuality {
    Exact,
    Within1s,
    Within3s,
    Within5s,
    WithinInning,
    Ambiguous,
    Unmatched,
    Unavailable,
}

impl SyncQuality {
    pub fn as_str(self) -> &'static str {
        match self {
            Self::Exact => "EXACT",
            Self::Within1s => "WITHIN_1S",
            Self::Within3s => "WITHIN_3S",
            Self::Within5s => "WITHIN_5S",
            Self::WithinInning => "WITHIN_INNING",
            Self::Ambiguous => "AMBIGUOUS",
            Self::Unmatched => "UNMATCHED",
            Self::Unavailable => "UNAVAILABLE",
        }
    }
}

/// Lag > this (ms) is still as-of matched but classified as a timestamp gap.
pub const GAP_THRESHOLD_MS: i64 = 5_000;

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum IdentityStatus {
    Matched,
    Unmatched,
    Ambiguous,
}

/// Compact W3 game-state reference. Not a W6 tensor.
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct GameStateSnapshot {
    pub game_id: String,
    pub event_id: String,
    pub state_seq: u32,
    pub inning: u8,
    pub half: String,
    pub outs: u8,
    pub score_home: u16,
    pub score_away: u16,
    pub run_differential: i32,
    pub runner_first: Option<String>,
    pub runner_second: Option<String>,
    pub runner_third: Option<String>,
    pub batter: Option<String>,
    pub pitcher: Option<String>,
    pub balls: u8,
    pub strikes: u8,
    pub count: String,
    pub game_status: String,
    pub extra_inning: bool,
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct MarketObservation {
    pub observation_id: String,
    pub market_id: String,
    pub ticker: String,
    pub game_pk: Option<String>,
    pub observation_type: ObservationType,
    pub source_market_time: String,
    pub source_timestamp_kind: String,
    pub normalized_market_time: Option<DateTime<Utc>>,
    pub retrieval_time: Option<DateTime<Utc>>,
    pub last_trade_cents: Option<i32>,
    pub yes_bid_cents: Option<i32>,
    pub yes_ask_cents: Option<i32>,
    pub quantity_hundredths: Option<i64>,
    pub source_id: Option<String>,
    pub source_lineage: String,
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct SynchronizedMarketObservation {
    pub synchronization_id: String,
    pub game_id: String,
    pub game_pk: String,
    pub market_id: String,
    pub ticker: String,
    pub contract_id: String,
    pub contract_side: String,
    pub observation_id: String,
    pub observation_type: ObservationType,
    pub market_timestamp_source: String,
    pub source_timestamp_kind: String,
    pub market_timestamp_utc: Option<DateTime<Utc>>,
    pub retrieval_timestamp: Option<DateTime<Utc>>,
    pub prior_event_id: Option<String>,
    pub prior_event_timestamp_utc: Option<DateTime<Utc>>,
    pub next_event_id: Option<String>,
    pub next_event_timestamp_utc: Option<DateTime<Utc>>,
    pub timestamp_relation: TimestampRelation,
    pub event_to_market_lag_ms: Option<i64>,
    pub market_to_next_event_ms: Option<i64>,
    pub synchronization_status: SyncStatus,
    pub synchronization_method: String,
    pub synchronization_quality: SyncQuality,
    /// Applicable state at t when an as-of match exists.
    /// AT_EVENT uses W3 effective-after, with `timestamp_relation = AT_EVENT`
    /// and `pre_event_state` also populated so the collision is not silent.
    pub game_state: Option<GameStateSnapshot>,
    pub pre_event_state: Option<GameStateSnapshot>,
    pub post_event_state: Option<GameStateSnapshot>,
    pub prior_market_observation_id: Option<String>,
    pub next_market_observation_id: Option<String>,
    pub elapsed_from_prior_obs_ms: Option<i64>,
    pub elapsed_to_next_obs_ms: Option<i64>,
    pub last_trade_cents: Option<i32>,
    pub first_observed_price_cents: Option<i32>,
    pub source_id: Option<String>,
    pub source_lineage: String,
    pub dataset_version: String,
}

impl SynchronizedMarketObservation {
    pub fn method_as_of() -> String {
        METHOD_AS_OF_PRIOR_EVENT.into()
    }

    pub fn matched_event_id(&self) -> Option<&str> {
        self.prior_event_id.as_deref()
    }
}

#[derive(Clone, Copy, Debug)]
pub struct SyncParams<'a> {
    pub game_id: &'a str,
    pub game_pk: &'a str,
    pub identity: IdentityStatus,
    pub events: &'a [TimedEvent],
    pub contract_side: &'a str,
    pub first_observed_price_cents: Option<i32>,
    pub ambiguous_clock: bool,
}

/// Timed PBP point used for AS-OF. States are W3 before/after of this event.
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct TimedEvent {
    pub event_id: String,
    pub sequence: u32,
    pub source_event_time: String,
    pub source_timestamp_kind: String,
    pub normalized_event_time: DateTime<Utc>,
    pub previous_event_id: Option<String>,
    pub next_event_id: Option<String>,
    pub state_before: GameStateSnapshot,
    pub state_after: GameStateSnapshot,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct GameWindow {
    pub start: DateTime<Utc>,
    pub end: DateTime<Utc>,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct AsOfHit {
    pub matched: TimedEvent,
    pub previous: Option<TimedEvent>,
    pub next: Option<TimedEvent>,
    pub lag_ms: i64,
    pub lead_ms: Option<i64>,
    pub relation: TimestampRelation,
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct GameCoverage {
    pub game_id: String,
    pub game_pk: String,
    pub timed_events: usize,
    pub observations: usize,
    pub synchronized: usize,
    pub at_event: usize,
    pub before_first: usize,
    pub after_last: usize,
    pub first_pbp_utc: Option<String>,
    pub last_pbp_utc: Option<String>,
    pub first_market_utc: Option<String>,
    pub last_market_utc: Option<String>,
}
