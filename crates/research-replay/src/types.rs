//! W8 replay types. Observational FIRST01 events. Not fills, not P&L.

use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};

use momento_research_path::PathObservation;
use momento_research_strategies::{FIRST01_NAME, FIRST01_VERSION};

use crate::versions::{ENGINE_VERSION, OBSERVABILITY};

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum ReplayPhase {
    Watching,
    First80Triggered,
    WaitingFor81Confirmation,
    EntryEligible,
    PricePaused,
    GameLocked,
}

impl ReplayPhase {
    pub fn as_str(self) -> &'static str {
        match self {
            Self::Watching => "WATCHING",
            Self::First80Triggered => "FIRST_80",
            Self::WaitingFor81Confirmation => "WAITING_FOR_81",
            Self::EntryEligible => "ENTRY_ELIGIBLE",
            Self::PricePaused => "PRICE_PAUSED",
            Self::GameLocked => "GAME_LOCKED",
        }
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum ReplayEventType {
    First80Observed,
    Confirm81Observed,
    EntryEligible,
    EntryIntentProposed,
    PricePaused,
    GameLocked,
    AmbiguousReplayOrder,
    SkippedMissingPrice,
    SkippedMissingTimestamp,
}

impl ReplayEventType {
    pub fn as_str(self) -> &'static str {
        match self {
            Self::First80Observed => "FIRST80_OBSERVED",
            Self::Confirm81Observed => "CONFIRM81_OBSERVED",
            Self::EntryEligible => "ENTRY_ELIGIBLE",
            Self::EntryIntentProposed => "ENTRY_INTENT_PROPOSED",
            Self::PricePaused => "PRICE_PAUSED",
            Self::GameLocked => "GAME_LOCKED",
            Self::AmbiguousReplayOrder => "AMBIGUOUS_REPLAY_ORDER",
            Self::SkippedMissingPrice => "SKIPPED_MISSING_PRICE",
            Self::SkippedMissingTimestamp => "SKIPPED_MISSING_TIMESTAMP",
        }
    }
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct ReplayEvent {
    pub replay_event_id: String,
    pub game_id: String,
    pub market_id: String,
    pub side: String,
    pub observation_id: String,
    pub market_timestamp_utc: Option<DateTime<Utc>>,
    pub strategy_state_before: String,
    pub strategy_state_after: String,
    pub event_type: ReplayEventType,
    pub price_cents: Option<i32>,
    pub state_id: Option<String>,
    pub state_seq: Option<u32>,
    pub state_timestamp_utc: Option<DateTime<Utc>>,
    pub inning: Option<u8>,
    pub half: Option<String>,
    pub outs: Option<u8>,
    pub score_home: Option<u16>,
    pub score_away: Option<u16>,
    pub run_differential: Option<i32>,
    pub bases: Option<String>,
    pub batter_id: Option<String>,
    pub pitcher_id: Option<String>,
    pub balls: Option<u8>,
    pub strikes: Option<u8>,
    pub game_status: Option<String>,
    pub synchronization_class: String,
    pub synchronization_quality: String,
    pub reason: String,
    pub observability: String,
    pub previous_trade_price_cents: Option<i32>,
    pub observed_high_cents_so_far: Option<i32>,
    pub observed_low_cents_so_far: Option<i32>,
    pub cumulative_trade_count: u32,
    pub time_since_previous_trade_ms: Option<i64>,
    pub time_since_state_transition_ms: Option<i64>,
    pub strategy: String,
    pub strategy_version: u32,
    pub w7_dataset_version: String,
    pub w8_engine_version: String,
}

impl ReplayEvent {
    pub fn from_obs(
        obs: &PathObservation,
        before: ReplayPhase,
        after: ReplayPhase,
        event_type: ReplayEventType,
        reason: &str,
        w7_ver: &str,
    ) -> Self {
        Self {
            replay_event_id: crate::ids::replay_event_id(
                w7_ver,
                &obs.game_id,
                &obs.observation_id,
                event_type.as_str(),
            ),
            game_id: obs.game_id.clone(),
            market_id: obs.market_id.clone(),
            side: obs.contract_side.clone(),
            observation_id: obs.observation_id.clone(),
            market_timestamp_utc: obs.market_timestamp_utc,
            strategy_state_before: before.as_str().to_string(),
            strategy_state_after: after.as_str().to_string(),
            event_type,
            price_cents: obs.trade_price_cents,
            state_id: obs.state_id.clone(),
            state_seq: obs.state_seq,
            state_timestamp_utc: obs.matched_state_timestamp_utc,
            inning: obs.inning,
            half: obs.half.clone(),
            outs: obs.outs,
            score_home: obs.score_home,
            score_away: obs.score_away,
            run_differential: obs.run_differential,
            bases: obs
                .bases_bitmask
                .map(momento_research_path::occupancy_label),
            batter_id: obs.batter_id.clone(),
            pitcher_id: obs.pitcher_id.clone(),
            balls: obs.balls,
            strikes: obs.strikes,
            game_status: obs.game_status.clone(),
            synchronization_class: obs.join_status.as_str().to_string(),
            synchronization_quality: obs.synchronization_quality.clone(),
            reason: reason.to_string(),
            observability: OBSERVABILITY.to_string(),
            previous_trade_price_cents: obs.previous_trade_price_cents,
            observed_high_cents_so_far: obs.observed_high_cents_so_far,
            observed_low_cents_so_far: obs.observed_low_cents_so_far,
            cumulative_trade_count: obs.cumulative_trade_count,
            time_since_previous_trade_ms: obs.time_since_previous_trade_ms,
            time_since_state_transition_ms: obs.time_since_state_transition_ms,
            strategy: FIRST01_NAME.to_string(),
            strategy_version: FIRST01_VERSION,
            w7_dataset_version: w7_ver.to_string(),
            w8_engine_version: ENGINE_VERSION.to_string(),
        }
    }

    pub fn is_state_linked(&self) -> bool {
        self.state_id.is_some()
    }
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct First01Opportunity {
    pub opportunity_id: String,
    pub game_id: String,
    pub market_id: String,
    pub side: String,
    pub first80_timestamp_utc: Option<DateTime<Utc>>,
    pub first80_observation_id: Option<String>,
    pub first80_price_cents: Option<i32>,
    pub first80_state_id: Option<String>,
    pub first80_state_seq: Option<u32>,
    pub first80_sync_quality: Option<String>,
    pub confirmation_timestamp_utc: Option<DateTime<Utc>>,
    pub confirmation_observation_id: Option<String>,
    pub confirmation_price_cents: Option<i32>,
    pub confirmation_state_id: Option<String>,
    pub confirmation_state_seq: Option<u32>,
    pub confirmation_sync_quality: Option<String>,
    pub entry_eligible_timestamp_utc: Option<DateTime<Utc>>,
    pub entry_observation_id: Option<String>,
    pub entry_price_cents: Option<i32>,
    pub intent_proposed: bool,
    pub game_lock_timestamp_utc: Option<DateTime<Utc>>,
    pub game_lock_observation_id: Option<String>,
    pub game_lock_price_cents: Option<i32>,
    pub replay_terminal_state: String,
    pub first80_sync_class: Option<String>,
    pub confirmation_sync_class: Option<String>,
    pub entry_sync_class: Option<String>,
    pub lock_sync_class: Option<String>,
    pub observability: String,
    pub strategy: String,
    pub strategy_version: u32,
    pub w7_dataset_version: String,
    pub w8_engine_version: String,
}

#[derive(Clone, Debug, Default, PartialEq, Eq)]
pub struct ReplayOutcome {
    pub events: Vec<ReplayEvent>,
    pub opportunities: Vec<First01Opportunity>,
    pub prints_80: usize,
    pub first80: usize,
    pub confirm81: usize,
    pub entry_eligible: usize,
    pub intents_proposed: usize,
    pub game_locks: usize,
    pub price_pauses: usize,
    pub ambiguous: usize,
    pub skipped: usize,
    pub observations: usize,
    pub sides: usize,
}
