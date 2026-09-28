//! Canonical MLB event model (W2-D). Optional fields are DataField, never sentinels.

use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};

use crate::field::DataField;
use crate::identity::{CanonicalGameId, PlayerRef};
use crate::w1_bridge::MlbTimestampKind;

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum HalfInning {
    Top,
    Bottom,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum GameStatus {
    PreGame,
    InProgress,
    Suspended,
    Delayed,
    Final,
    Unknown,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum MlbEventType {
    GameStart,
    Pitch,
    Ball,
    Strike,
    Foul,
    Walk,
    HitByPitch,
    Strikeout,
    Single,
    Double,
    Triple,
    HomeRun,
    Sacrifice,
    DoublePlay,
    Error,
    StolenBase,
    WildPitch,
    PassedBall,
    Balk,
    FieldersChoice,
    CatchersInterference,
    PitchingChange,
    BattingChange,
    Substitution,
    Review,
    Amendment,
    InningStart,
    InningEnd,
    WalkOff,
    GameEnd,
    FieldOut,
    ForceOut,
    Other,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum FixtureKind {
    HistoricalSource,
    SyntheticTestFixture,
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct BaseOccupancy {
    pub first: Option<PlayerRef>,
    pub second: Option<PlayerRef>,
    pub third: Option<PlayerRef>,
}

impl BaseOccupancy {
    pub fn empty() -> Self {
        Self {
            first: None,
            second: None,
            third: None,
        }
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct Score {
    pub home: u16,
    pub away: u16,
}

impl Score {
    pub fn tied_zero() -> Self {
        Self { home: 0, away: 0 }
    }

    pub fn differential(self) -> i32 {
        i32::from(self.home) - i32::from(self.away)
    }

    pub fn total(self) -> u32 {
        u32::from(self.home) + u32::from(self.away)
    }
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct PitchInfo {
    pub pitch_of_pa: DataField<u8>,
    pub pitch_type: DataField<String>,
    pub description: DataField<String>,
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct ReviewInfo {
    pub in_review: bool,
    pub overturned: DataField<bool>,
    pub challenge_team: DataField<String>,
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct EventProvenance {
    pub source: String,
    pub source_game_id: String,
    pub source_event_id: String,
    pub raw_file: DataField<String>,
    pub raw_line: DataField<u64>,
    pub payload_sha256: DataField<String>,
    pub parser_version: String,
    pub normalization_version: String,
    pub schema_version: String,
    pub retrieval_timestamp: DataField<DateTime<Utc>>,
    pub fixture_kind: FixtureKind,
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct CanonicalMlbEvent {
    pub event_id: String,
    pub game_id: CanonicalGameId,
    pub sequence: u32,
    pub source_event_id: String,
    pub source_timestamp: DataField<DateTime<Utc>>,
    pub source_timestamp_kind: MlbTimestampKind,
    pub collector_timestamp: DataField<DateTime<Utc>>,
    pub canonical_order: u32,
    pub inning: DataField<u8>,
    pub half: DataField<HalfInning>,
    pub outs_before: DataField<u8>,
    pub outs_after: DataField<u8>,
    pub score_before: DataField<Score>,
    pub score_after: DataField<Score>,
    pub batting_team: DataField<String>,
    pub fielding_team: DataField<String>,
    pub batter: DataField<PlayerRef>,
    pub pitcher: DataField<PlayerRef>,
    pub runners_before: DataField<BaseOccupancy>,
    pub runners_after: DataField<BaseOccupancy>,
    pub event_type: MlbEventType,
    pub event_description: DataField<String>,
    pub runs_scored: DataField<u8>,
    pub balls: DataField<u8>,
    pub strikes: DataField<u8>,
    pub pitch: Option<PitchInfo>,
    pub review: Option<ReviewInfo>,
    pub substitution: DataField<String>,
    pub amends_event_id: Option<String>,
    pub game_status_after: DataField<GameStatus>,
    pub provenance: EventProvenance,
}

impl CanonicalMlbEvent {
    pub fn is_synthetic(&self) -> bool {
        self.provenance.fixture_kind == FixtureKind::SyntheticTestFixture
    }

    pub fn is_amendment(&self) -> bool {
        self.event_type == MlbEventType::Amendment || self.amends_event_id.is_some()
    }
}
