//! Deterministic fingerprints. Retrieval and generation timestamps never participate.

use chrono::{DateTime, Utc};
use momento_research_event::event::{GameStatus, HalfInning, MlbEventType};
use momento_research_event::field::DataField;
use sha2::{Digest, Sha256};

use crate::types::{EventKind, GameState, PaPhase, StateTransition};
use crate::versions::{FINGERPRINT_VERSION, RECONSTRUCTION_VERSION};

pub fn sha256_hex(kind: &str, parts: &[&str]) -> String {
    let mut h = Sha256::new();
    h.update(kind.as_bytes());
    h.update(FINGERPRINT_VERSION.as_bytes());
    for p in parts {
        h.update([0u8]);
        h.update(p.as_bytes());
    }
    format!("{:x}", h.finalize())
}

pub fn field_token<T: ToString>(f: &DataField<T>) -> String {
    match f {
        DataField::Observed { value }
        | DataField::Derived { value, .. }
        | DataField::Inferred { value, .. } => {
            format!("V:{}", value.to_string())
        }
        DataField::Unavailable { .. } => "U".into(),
    }
}

pub fn opt_field_token(f: &DataField<Option<String>>) -> String {
    match f {
        DataField::Observed { value }
        | DataField::Derived { value, .. }
        | DataField::Inferred { value, .. } => match value {
            Some(id) => format!("V:{id}"),
            None => "EMPTY".into(),
        },
        DataField::Unavailable { .. } => "U".into(),
    }
}

pub fn ts_token(f: &DataField<DateTime<Utc>>) -> String {
    match f.as_value() {
        Some(t) => format!("V:{}", t.to_rfc3339()),
        None => "U".into(),
    }
}

pub fn half_token(h: HalfInning) -> &'static str {
    match h {
        HalfInning::Top => "TOP",
        HalfInning::Bottom => "BOTTOM",
    }
}

pub fn status_token(s: GameStatus) -> &'static str {
    match s {
        GameStatus::PreGame => "PRE_GAME",
        GameStatus::InProgress => "IN_PROGRESS",
        GameStatus::Suspended => "SUSPENDED",
        GameStatus::Delayed => "DELAYED",
        GameStatus::Final => "FINAL",
        GameStatus::Unknown => "UNKNOWN",
    }
}

pub fn event_type_token(t: MlbEventType) -> &'static str {
    match t {
        MlbEventType::GameStart => "GAME_START",
        MlbEventType::Pitch => "PITCH",
        MlbEventType::Ball => "BALL",
        MlbEventType::Strike => "STRIKE",
        MlbEventType::Foul => "FOUL",
        MlbEventType::Walk => "WALK",
        MlbEventType::HitByPitch => "HIT_BY_PITCH",
        MlbEventType::Strikeout => "STRIKEOUT",
        MlbEventType::Single => "SINGLE",
        MlbEventType::Double => "DOUBLE",
        MlbEventType::Triple => "TRIPLE",
        MlbEventType::HomeRun => "HOME_RUN",
        MlbEventType::Sacrifice => "SACRIFICE",
        MlbEventType::DoublePlay => "DOUBLE_PLAY",
        MlbEventType::Error => "ERROR",
        MlbEventType::StolenBase => "STOLEN_BASE",
        MlbEventType::WildPitch => "WILD_PITCH",
        MlbEventType::PassedBall => "PASSED_BALL",
        MlbEventType::Balk => "BALK",
        MlbEventType::FieldersChoice => "FIELDERS_CHOICE",
        MlbEventType::CatchersInterference => "CATCHERS_INTERFERENCE",
        MlbEventType::PitchingChange => "PITCHING_CHANGE",
        MlbEventType::BattingChange => "BATTING_CHANGE",
        MlbEventType::Substitution => "SUBSTITUTION",
        MlbEventType::Review => "REVIEW",
        MlbEventType::Amendment => "AMENDMENT",
        MlbEventType::InningStart => "INNING_START",
        MlbEventType::InningEnd => "INNING_END",
        MlbEventType::WalkOff => "WALK_OFF",
        MlbEventType::GameEnd => "GAME_END",
        MlbEventType::FieldOut => "FIELD_OUT",
        MlbEventType::ForceOut => "FORCE_OUT",
        MlbEventType::Other => "OTHER",
    }
}

pub fn event_kind_token(k: EventKind) -> &'static str {
    k.as_str()
}

pub fn pa_phase_token(p: PaPhase) -> &'static str {
    p.as_str()
}

/// Baseball-situation fingerprint. No retrieval/generation timestamps.
pub fn state_fingerprint_parts(s: &GameState) -> Vec<String> {
    vec![
        s.game_id.clone(),
        s.state_seq.to_string(),
        s.event_id.clone().unwrap_or_else(|| "NONE".into()),
        s.inning.to_string(),
        half_token(s.half).to_string(),
        s.outs.to_string(),
        s.score_home.to_string(),
        s.score_away.to_string(),
        status_token(s.game_status).to_string(),
        opt_field_token(&s.runner_first),
        opt_field_token(&s.runner_second),
        opt_field_token(&s.runner_third),
        field_token(&s.batter_id),
        field_token(&s.pitcher_id),
        field_token(&s.balls),
        field_token(&s.strikes),
        pa_phase_token(s.pa_phase).to_string(),
        field_token(&s.pa_seq),
        s.walk_off.to_string(),
        s.extra_inning.to_string(),
        ts_token(&s.canonical_timestamp),
    ]
}

pub fn fingerprint_state(s: &GameState) -> String {
    let parts = state_fingerprint_parts(s);
    let refs: Vec<&str> = parts.iter().map(String::as_str).collect();
    sha256_hex("w6.state.fp", &refs)
}

pub fn state_id_for(s: &GameState) -> String {
    sha256_hex(
        "w6.state.id",
        &[
            s.game_id.as_str(),
            &s.state_seq.to_string(),
            s.fingerprint.as_str(),
        ],
    )
}

pub fn fingerprint_transition(t: &StateTransition) -> String {
    sha256_hex(
        "w6.transition.fp",
        &[
            t.game_id.as_str(),
            &t.sequence.to_string(),
            t.event_id.as_str(),
            t.previous_state_id.as_str(),
            t.resulting_state_id.as_str(),
            event_type_token(t.event_type),
            &t.score_delta_home.to_string(),
            &t.score_delta_away.to_string(),
            &t.out_delta.to_string(),
            &t.bases_before.to_string(),
            &t.bases_after.to_string(),
        ],
    )
}

pub fn transition_id_for(t: &StateTransition) -> String {
    sha256_hex(
        "w6.transition.id",
        &[
            t.game_id.as_str(),
            t.previous_state_id.as_str(),
            t.source_event_id.as_str(),
            t.resulting_state_id.as_str(),
        ],
    )
}

pub fn reconstruction_version() -> &'static str {
    RECONSTRUCTION_VERSION
}
