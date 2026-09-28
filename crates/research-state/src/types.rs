//! Canonical W6 GameState and StateTransition. No market prices.

use chrono::{DateTime, NaiveDate, Utc};
use momento_research_event::event::{GameStatus, HalfInning, MlbEventType};
use momento_research_event::field::DataField;
use serde::{Deserialize, Serialize};

use crate::versions::{DERIVED_VERSION, FINGERPRINT_VERSION, PA_VERSION, SCHEMA_VERSION};

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum PaPhase {
    None,
    Start,
    Pitch,
    Result,
    End,
}

impl PaPhase {
    pub fn as_str(self) -> &'static str {
        match self {
            Self::None => "NONE",
            Self::Start => "PA_START",
            Self::Pitch => "PITCH",
            Self::Result => "PA_RESULT",
            Self::End => "PA_END",
        }
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum EventKind {
    Ordinary,
    Review,
    Amendment,
    Delay,
    Resumption,
    Substitution,
    GameStatusTransition,
    GameStart,
    GameEnd,
}

impl EventKind {
    pub fn as_str(self) -> &'static str {
        match self {
            Self::Ordinary => "ORDINARY",
            Self::Review => "REVIEW",
            Self::Amendment => "AMENDMENT",
            Self::Delay => "DELAY",
            Self::Resumption => "RESUMPTION",
            Self::Substitution => "SUBSTITUTION",
            Self::GameStatusTransition => "GAME_STATUS_TRANSITION",
            Self::GameStart => "GAME_START",
            Self::GameEnd => "GAME_END",
        }
    }
}

/// Canonical MLB game state immediately after an event (or pre-game at seq 0).
/// Immutable after construction. Retrieval time is never a field.
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct GameState {
    pub state_id: String,
    pub fingerprint: String,
    pub fingerprint_version: String,
    pub schema_version: String,
    pub game_id: String,
    pub game_pk: String,
    pub season: DataField<i32>,
    pub game_date: DataField<NaiveDate>,
    pub home_team: DataField<String>,
    pub away_team: DataField<String>,
    pub home_abbreviation: DataField<String>,
    pub away_abbreviation: DataField<String>,
    pub game_number: u8,
    pub game_status: GameStatus,
    pub state_seq: u32,
    pub event_id: Option<String>,
    pub event_sequence: u32,
    pub source_event_id: DataField<String>,
    pub source_timestamp: DataField<DateTime<Utc>>,
    pub canonical_timestamp: DataField<DateTime<Utc>>,
    pub inning: u8,
    pub half: HalfInning,
    pub inning_half_id: String,
    pub score_home: u16,
    pub score_away: u16,
    pub run_differential: i32,
    pub abs_run_differential: u16,
    pub outs: u8,
    pub outs_before_event: DataField<u8>,
    pub runner_first: DataField<Option<String>>,
    pub runner_second: DataField<Option<String>>,
    pub runner_third: DataField<Option<String>>,
    pub bases_bitmask: u8,
    pub risp: bool,
    pub base_occupancy_id: String,
    pub batter_id: DataField<String>,
    pub batter_team: DataField<String>,
    pub batter_hand: DataField<String>,
    pub batting_order_slot: DataField<u8>,
    pub pitcher_id: DataField<String>,
    pub pitching_team: DataField<String>,
    pub pitcher_hand: DataField<String>,
    pub balls: DataField<u8>,
    pub strikes: DataField<u8>,
    pub count_id: DataField<String>,
    pub pitch_of_pa: DataField<u8>,
    pub pa_id: DataField<String>,
    pub pa_seq: DataField<u32>,
    pub pa_phase: PaPhase,
    pub pa_start_ts: DataField<DateTime<Utc>>,
    pub pa_end_ts: DataField<DateTime<Utc>>,
    pub pa_result: DataField<String>,
    pub pa_version: String,
    pub event_type: Option<MlbEventType>,
    pub event_kind: EventKind,
    pub event_description: DataField<String>,
    pub extra_inning: bool,
    pub walk_off: bool,
    pub outs_remaining_half: u8,
    pub total_outs_elapsed: DataField<u32>,
    pub game_elapsed_ms: DataField<i64>,
    pub game_remaining_ms: DataField<i64>,
    pub base_out_id: String,
    pub score_state_id: String,
    pub derived_version: String,
    pub source_dataset: String,
    pub source_version: String,
    pub reconstruction_version: String,
}

impl GameState {
    pub fn fingerprint_version() -> &'static str {
        FINGERPRINT_VERSION
    }

    pub fn schema_version() -> &'static str {
        SCHEMA_VERSION
    }
}

/// Deterministic transition: previous_state + event → resulting_state.
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct StateTransition {
    pub transition_id: String,
    pub fingerprint: String,
    pub game_id: String,
    pub sequence: u32,
    pub event_id: String,
    pub source_event_id: String,
    pub previous_state_id: String,
    pub resulting_state_id: String,
    pub event_timestamp: DataField<DateTime<Utc>>,
    pub event_type: MlbEventType,
    pub event_kind: EventKind,
    pub source_event_type: DataField<String>,
    pub score_delta_home: i32,
    pub score_delta_away: i32,
    pub out_delta: i32,
    pub bases_before: u8,
    pub bases_after: u8,
    pub batter_changed: bool,
    pub pitcher_changed: bool,
    pub inning_changed: bool,
    pub half_changed: bool,
    pub count_changed: bool,
    pub runner_first_changed: bool,
    pub runner_second_changed: bool,
    pub runner_third_changed: bool,
    pub substitution: bool,
    pub review: bool,
    pub amendment: bool,
    pub delay: bool,
    pub walk_off: bool,
    pub extra_inning: bool,
    pub pa_phase: PaPhase,
    pub amends_event_id: Option<String>,
    pub provenance_source: String,
    pub provenance_raw_file: DataField<String>,
    pub reconstruction_version: String,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct ReconstructedGame {
    pub game_id: String,
    pub game_pk: String,
    pub official_date: Option<NaiveDate>,
    pub pre_game: GameState,
    pub states: Vec<GameState>,
    pub transitions: Vec<StateTransition>,
    pub events_total: usize,
    pub timed_events: usize,
    pub extra_inning: bool,
    pub walk_off: bool,
    pub terminal: bool,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub enum TimeLookup<'a> {
    Hit {
        state: &'a GameState,
        previous_event_id: Option<&'a str>,
        next_event_id: Option<&'a str>,
        previous_event_time: Option<DateTime<Utc>>,
        next_event_time: Option<DateTime<Utc>>,
    },
    NoState {
        next_event_id: Option<&'a str>,
        next_event_time: Option<DateTime<Utc>>,
    },
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct ValidationFailure {
    pub game_id: String,
    pub event_id: String,
    pub sequence: u32,
    pub state_before_id: Option<String>,
    pub event_type: String,
    pub attempted_state_id: Option<String>,
    pub code: String,
    pub reason: String,
}

pub fn half_code(h: HalfInning) -> &'static str {
    match h {
        HalfInning::Top => "T",
        HalfInning::Bottom => "B",
    }
}

pub fn inning_half_id(inning: u8, half: HalfInning) -> String {
    format!("{inning}{}", half_code(half))
}

pub fn bases_bitmask(first: Option<&str>, second: Option<&str>, third: Option<&str>) -> u8 {
    let mut m = 0u8;
    if first.is_some() {
        m |= 1;
    }
    if second.is_some() {
        m |= 2;
    }
    if third.is_some() {
        m |= 4;
    }
    m
}

pub fn occupancy_id(mask: u8) -> String {
    let f = if mask & 1 != 0 { '1' } else { '_' };
    let s = if mask & 2 != 0 { '2' } else { '_' };
    let t = if mask & 4 != 0 { '3' } else { '_' };
    format!("{f}{s}{t}")
}

pub fn classify_event_kind(
    ty: MlbEventType,
    status: GameStatus,
    prev_status: GameStatus,
) -> EventKind {
    match ty {
        MlbEventType::GameStart => EventKind::GameStart,
        MlbEventType::GameEnd | MlbEventType::WalkOff => EventKind::GameEnd,
        MlbEventType::Review => EventKind::Review,
        MlbEventType::Amendment => EventKind::Amendment,
        MlbEventType::PitchingChange | MlbEventType::BattingChange | MlbEventType::Substitution => {
            EventKind::Substitution
        }
        _ if status == GameStatus::Delayed && prev_status != GameStatus::Delayed => {
            EventKind::Delay
        }
        _ if prev_status == GameStatus::Delayed && status != GameStatus::Delayed => {
            EventKind::Resumption
        }
        _ if status != prev_status => EventKind::GameStatusTransition,
        _ => EventKind::Ordinary,
    }
}

pub fn is_pa_result(ty: MlbEventType) -> bool {
    matches!(
        ty,
        MlbEventType::Walk
            | MlbEventType::Strikeout
            | MlbEventType::Single
            | MlbEventType::Double
            | MlbEventType::Triple
            | MlbEventType::HomeRun
            | MlbEventType::Sacrifice
            | MlbEventType::DoublePlay
            | MlbEventType::HitByPitch
            | MlbEventType::Error
            | MlbEventType::FieldersChoice
            | MlbEventType::WalkOff
            | MlbEventType::FieldOut
            | MlbEventType::ForceOut
            | MlbEventType::CatchersInterference
    )
}

pub fn is_pitch(ty: MlbEventType) -> bool {
    matches!(
        ty,
        MlbEventType::Pitch | MlbEventType::Ball | MlbEventType::Strike | MlbEventType::Foul
    )
}

pub const PA_UNAVAILABLE: &str = "pitch-level PA not in play-granularity PBP";

pub fn pa_version() -> &'static str {
    PA_VERSION
}

pub fn derived_version() -> &'static str {
    DERIVED_VERSION
}

pub fn total_outs_elapsed(inning: u8, half: HalfInning, outs: u8) -> u32 {
    let completed_innings = u32::from(inning.saturating_sub(1));
    let half_outs = match half {
        HalfInning::Top => 0,
        HalfInning::Bottom => 3,
    };
    completed_innings * 6 + half_outs + u32::from(outs.min(3))
}
