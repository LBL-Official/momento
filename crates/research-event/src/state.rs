//! Deterministic MLB game state machine: STATE_before + EVENT = STATE_after.

use serde::{Deserialize, Serialize};

use crate::error::EventError;
use crate::event::{BaseOccupancy, CanonicalMlbEvent, GameStatus, HalfInning, MlbEventType, Score};
use crate::field::DataField;
use crate::identity::{CanonicalGameId, PlayerRef};
use crate::versions::STATE_MACHINE_VERSION;

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum LeadState {
    HomeLeading,
    AwayLeading,
    Tied,
}

/// In-progress MLB situation reconstructed from PBP only.
///
/// Leakage boundary: this type MUST NOT carry eventual winner, settlement,
/// future PBP, future market prices, or actual remaining outs. Those live in
/// isolated [`crate::outcome::GameOutcome`] (labels) or later waterfalls (W3–W5).
/// W5 owns the canonical `StateTransition` / `GameMarketEpisode` types.
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct MlbGameState {
    pub game_id: CanonicalGameId,
    pub state_seq: u32,
    pub last_event_id: Option<String>,
    pub inning: u8,
    pub half: HalfInning,
    pub outs: u8,
    pub game_status: GameStatus,
    pub score: Score,
    pub runners: DataField<BaseOccupancy>,
    pub batter: DataField<PlayerRef>,
    pub pitcher: DataField<PlayerRef>,
    pub balls: u8,
    pub strikes: u8,
    pub batting_team: DataField<String>,
    pub fielding_team: DataField<String>,
    pub runs_on_last_event: u8,
    pub lead: LeadState,
    pub extra_inning: bool,
    pub machine_version: String,
}

impl MlbGameState {
    pub fn pre_game(game_id: CanonicalGameId) -> Self {
        Self {
            game_id,
            state_seq: 0,
            last_event_id: None,
            inning: 1,
            half: HalfInning::Top,
            outs: 0,
            game_status: GameStatus::PreGame,
            score: Score::tied_zero(),
            runners: DataField::observed(BaseOccupancy::empty()),
            batter: DataField::unavailable("pre-game"),
            pitcher: DataField::unavailable("pre-game"),
            balls: 0,
            strikes: 0,
            batting_team: DataField::unavailable("pre-game"),
            fielding_team: DataField::unavailable("pre-game"),
            runs_on_last_event: 0,
            lead: LeadState::Tied,
            extra_inning: false,
            machine_version: STATE_MACHINE_VERSION.to_string(),
        }
    }

    pub fn lead_from_score(score: Score) -> LeadState {
        if score.home > score.away {
            LeadState::HomeLeading
        } else if score.away > score.home {
            LeadState::AwayLeading
        } else {
            LeadState::Tied
        }
    }
}

/// PBP-triggered before/after game states. Not the W5 canonical `StateTransition`.
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct MlbPbpTransition {
    pub game_id: CanonicalGameId,
    pub event_id: String,
    pub sequence: u32,
    pub before: MlbGameState,
    pub after: MlbGameState,
    pub trigger: MlbEventType,
    pub machine_version: String,
    pub invariant_warnings: Vec<String>,
}

pub fn apply(
    before: &MlbGameState,
    event: &CanonicalMlbEvent,
) -> Result<MlbPbpTransition, EventError> {
    if before.game_id != event.game_id {
        return Err(EventError::GameMismatch {
            state_game: before.game_id.as_str().into(),
            event_game: event.game_id.as_str().into(),
        });
    }
    let expected = before.state_seq + 1;
    if event.sequence != expected {
        return Err(EventError::SequenceGap {
            game_id: before.game_id.as_str().into(),
            expected,
            got: event.sequence,
        });
    }

    check_before_matches(before, event)?;

    let mut after = before.clone();
    after.state_seq = event.sequence;
    after.last_event_id = Some(event.event_id.clone());

    if let Some(st) = event.game_status_after.as_value() {
        after.game_status = *st;
    } else if after.game_status == GameStatus::PreGame {
        after.game_status = GameStatus::InProgress;
    }

    if let Some(i) = event.inning.as_value() {
        after.inning = *i;
    }
    if let Some(h) = event.half.as_value() {
        after.half = *h;
    }
    if let Some(o) = event.outs_after.as_value() {
        after.outs = *o;
    }
    if let Some(s) = event.score_after.as_value() {
        after.score = *s;
    }
    if let Some(r) = event.runners_after.as_value() {
        after.runners = DataField::observed(r.clone());
    } else if event.runners_after.is_unavailable() && event.event_type == MlbEventType::InningEnd {
        after.runners = DataField::observed(BaseOccupancy::empty());
    }
    after.batter = event.batter.clone();
    after.pitcher = event.pitcher.clone();
    if let Some(b) = event.balls.as_value() {
        after.balls = *b;
    }
    if let Some(k) = event.strikes.as_value() {
        after.strikes = *k;
    }
    after.batting_team = event.batting_team.clone();
    after.fielding_team = event.fielding_team.clone();
    after.runs_on_last_event = event.runs_scored.as_value().copied().unwrap_or(0);
    after.lead = MlbGameState::lead_from_score(after.score);
    after.extra_inning = after.inning > 9;
    after.machine_version = STATE_MACHINE_VERSION.to_string();

    if matches!(
        event.event_type,
        MlbEventType::Walk
            | MlbEventType::Strikeout
            | MlbEventType::Single
            | MlbEventType::Double
            | MlbEventType::Triple
            | MlbEventType::HomeRun
            | MlbEventType::Sacrifice
            | MlbEventType::DoublePlay
            | MlbEventType::HitByPitch
            | MlbEventType::WalkOff
            | MlbEventType::FieldOut
            | MlbEventType::ForceOut
    ) {
        after.balls = 0;
        after.strikes = 0;
    }
    if event.event_type == MlbEventType::InningEnd {
        after.outs = 0;
        after.balls = 0;
        after.strikes = 0;
        after.runners = DataField::observed(BaseOccupancy::empty());
    }

    let warnings = check_invariants(before, event, &after)?;
    Ok(MlbPbpTransition {
        game_id: before.game_id.clone(),
        event_id: event.event_id.clone(),
        sequence: event.sequence,
        before: before.clone(),
        after,
        trigger: event.event_type,
        machine_version: STATE_MACHINE_VERSION.to_string(),
        invariant_warnings: warnings,
    })
}

fn check_before_matches(
    before: &MlbGameState,
    event: &CanonicalMlbEvent,
) -> Result<(), EventError> {
    if before.state_seq == 0 {
        return Ok(());
    }
    if let Some(o) = event.outs_before.as_value() {
        if *o != before.outs {
            let half_changed = event.inning.as_value().is_some_and(|i| *i != before.inning)
                || event.half.as_value().is_some_and(|h| *h != before.half);
            if !(half_changed && *o == 0 && before.outs == 3) {
                return Err(EventError::invariant(
                    "OUTS_BEFORE",
                    format!("event outs_before={o} state.outs={}", before.outs),
                ));
            }
        }
    }
    if let Some(s) = event.score_before.as_value() {
        if s != &before.score {
            return Err(EventError::invariant(
                "SCORE_BEFORE",
                format!("event score_before={s:?} state.score={:?}", before.score),
            ));
        }
    }
    if let Some(i) = event.inning.as_value() {
        if event.event_type != MlbEventType::InningEnd
            && event.event_type != MlbEventType::InningStart
            && *i < before.inning
        {
            return Err(EventError::invariant(
                "INNING_BACKWARD",
                format!("event inning={i} state.inning={}", before.inning),
            ));
        }
    }
    Ok(())
}

fn check_invariants(
    before: &MlbGameState,
    event: &CanonicalMlbEvent,
    after: &MlbGameState,
) -> Result<Vec<String>, EventError> {
    let mut warnings = Vec::new();
    if after.score.home < before.score.home || after.score.away < before.score.away {
        return Err(EventError::invariant(
            "SCORE_DECREASE",
            format!("{:?} -> {:?}", before.score, after.score),
        ));
    }
    if after.inning < before.inning {
        return Err(EventError::invariant(
            "INNING_BACKWARD",
            format!("{} -> {}", before.inning, after.inning),
        ));
    }
    let same_half = after.inning == before.inning && after.half == before.half;
    if same_half && after.outs < before.outs && !event.is_amendment() {
        return Err(EventError::invariant(
            "OUTS_DECREASE",
            format!("outs {} -> {} without amendment", before.outs, after.outs),
        ));
    }
    if after.outs > 3 {
        return Err(EventError::invariant(
            "OUTS_EXCEED_THREE",
            format!("outs_after={}", after.outs),
        ));
    }
    if let (Some(b), Some(a)) = (event.score_before.as_value(), event.score_after.as_value()) {
        let delta = a.total().saturating_sub(b.total());
        if let Some(r) = event.runs_scored.as_value() {
            if u32::from(*r) != delta {
                return Err(EventError::invariant(
                    "RUNS_RECONCILE",
                    format!("runs_scored={r} score_delta={delta}"),
                ));
            }
        }
    }
    if let Some(half) = event.half.as_value() {
        if let (Some(bat), Some(field)) = (
            event.batting_team.as_value(),
            event.fielding_team.as_value(),
        ) {
            if bat == field {
                return Err(EventError::invariant(
                    "BATTING_FIELDING",
                    "batting team equals fielding team",
                ));
            }
            let _ = half;
        }
    }
    if event.event_type == MlbEventType::WalkOff {
        if after.half != HalfInning::Bottom || after.inning < 9 {
            return Err(EventError::invariant(
                "WALKOFF_CONTEXT",
                "walk-off requires bottom of 9th or later",
            ));
        }
        if after.score.home <= after.score.away {
            return Err(EventError::invariant(
                "WALKOFF_SCORE",
                "walk-off must leave home ahead",
            ));
        }
        if after.game_status != GameStatus::Final {
            warnings.push("walk-off event did not set game_status=Final".into());
        }
    }
    if after.game_status == GameStatus::Final && after.score.home == after.score.away {
        return Err(EventError::invariant(
            "FINAL_TIE",
            "MLB regulation/extra completion cannot be tied in reconstructed final state",
        ));
    }
    if after.balls > 4 {
        return Err(EventError::invariant(
            "BALLS",
            format!("balls={}", after.balls),
        ));
    }
    if after.strikes > 3 {
        return Err(EventError::invariant(
            "STRIKES",
            format!("strikes={}", after.strikes),
        ));
    }
    Ok(warnings)
}

pub fn replay(events: &[CanonicalMlbEvent]) -> Result<Vec<MlbPbpTransition>, EventError> {
    if events.is_empty() {
        return Err(EventError::Malformed("no events to replay".into()));
    }
    let mut state = MlbGameState::pre_game(events[0].game_id.clone());
    let mut out = Vec::with_capacity(events.len());
    for ev in events {
        let tr = apply(&state, ev)?;
        state = tr.after.clone();
        out.push(tr);
    }
    Ok(out)
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::synthetic;

    #[test]
    fn outs_cannot_decrease_without_amendment() {
        let events = synthetic::strikeout_then_illegal_outs_drop();
        let err = replay(&events).unwrap_err();
        assert!(matches!(err, EventError::Invariant { code, .. } if code == "OUTS_DECREASE"));
    }

    #[test]
    fn score_cannot_decrease() {
        let events = synthetic::illegal_score_drop();
        let err = replay(&events).unwrap_err();
        assert!(matches!(err, EventError::Invariant { code, .. } if code == "SCORE_DECREASE"));
    }
}
