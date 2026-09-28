//! Fail-closed W6 validation. Impossible states are not repaired.

use std::collections::HashSet;

use momento_research_event::event::{CanonicalMlbEvent, GameStatus, MlbEventType};
use momento_research_event::field::DataField;
use momento_research_event::state::MlbGameState;

use crate::error::W6Error;
use crate::types::{GameState, ValidationFailure};

pub fn fail(
    code: &str,
    game_id: &str,
    event_id: &str,
    sequence: u32,
    message: impl Into<String>,
) -> W6Error {
    W6Error::validation(code, game_id, event_id, sequence, message)
}

pub fn to_failure(
    err: &W6Error,
    before: Option<&GameState>,
    event: Option<&CanonicalMlbEvent>,
) -> ValidationFailure {
    match err {
        W6Error::Validation {
            code,
            game_id,
            event_id,
            sequence,
            message,
        } => ValidationFailure {
            game_id: game_id.clone(),
            event_id: event_id.clone(),
            sequence: *sequence,
            state_before_id: before.map(|s| s.state_id.clone()),
            event_type: event
                .map(|e| crate::fingerprint::event_type_token(e.event_type).to_string())
                .unwrap_or_default(),
            attempted_state_id: None,
            code: code.clone(),
            reason: message.clone(),
        },
        other => ValidationFailure {
            game_id: before.map(|s| s.game_id.clone()).unwrap_or_default(),
            event_id: event.map(|e| e.event_id.clone()).unwrap_or_default(),
            sequence: event.map(|e| e.sequence).unwrap_or(0),
            state_before_id: before.map(|s| s.state_id.clone()),
            event_type: event
                .map(|e| crate::fingerprint::event_type_token(e.event_type).to_string())
                .unwrap_or_default(),
            attempted_state_id: None,
            code: "ENGINE".into(),
            reason: other.to_string(),
        },
    }
}

pub fn assert_event_stream(events: &[CanonicalMlbEvent]) -> Result<(), W6Error> {
    if events.is_empty() {
        return Err(W6Error::validation(
            "EMPTY_EVENTS",
            "",
            "",
            0,
            "no canonical events to replay",
        ));
    }
    let game_id = events[0].game_id.as_str();
    let mut ids = HashSet::new();
    let mut source_ids = HashSet::new();
    let mut seqs = HashSet::new();
    for e in events {
        if e.game_id.as_str() != game_id {
            return Err(fail(
                "GAME_ID_MISMATCH",
                game_id,
                &e.event_id,
                e.sequence,
                format!("event game_id {} != {game_id}", e.game_id.as_str()),
            ));
        }
        if !ids.insert(e.event_id.clone()) {
            return Err(fail(
                "DUPLICATE_EVENT_ID",
                game_id,
                &e.event_id,
                e.sequence,
                "duplicate canonical event id",
            ));
        }
        if !source_ids.insert(e.source_event_id.clone()) {
            return Err(fail(
                "DUPLICATE_SOURCE_EVENT",
                game_id,
                &e.event_id,
                e.sequence,
                format!("duplicate source_event_id {}", e.source_event_id),
            ));
        }
        if !seqs.insert(e.sequence) {
            return Err(fail(
                "DUPLICATE_SEQUENCE",
                game_id,
                &e.event_id,
                e.sequence,
                "duplicate source sequence",
            ));
        }
    }
    Ok(())
}

pub fn assert_runners(
    game_id: &str,
    event: &CanonicalMlbEvent,
    after: &MlbGameState,
) -> Result<(), W6Error> {
    let Some(occ) = after.runners.as_value() else {
        return Ok(());
    };
    let mut seen = HashSet::new();
    for slot in [&occ.first, &occ.second, &occ.third] {
        let Some(p) = slot else {
            continue;
        };
        if p.source_player_id.is_empty() {
            continue;
        }
        if !seen.insert(p.source_player_id.clone()) {
            return Err(fail(
                "DUPLICATE_RUNNER",
                game_id,
                &event.event_id,
                event.sequence,
                format!("player {} occupies multiple bases", p.source_player_id),
            ));
        }
    }
    Ok(())
}

pub fn assert_count(
    game_id: &str,
    event: &CanonicalMlbEvent,
    balls: &DataField<u8>,
    strikes: &DataField<u8>,
) -> Result<(), W6Error> {
    if let Some(b) = balls.as_value() {
        if *b > 4 {
            return Err(fail(
                "COUNT_BALLS",
                game_id,
                &event.event_id,
                event.sequence,
                format!("balls={b}"),
            ));
        }
    }
    if let Some(k) = strikes.as_value() {
        if *k > 3 {
            return Err(fail(
                "COUNT_STRIKES",
                game_id,
                &event.event_id,
                event.sequence,
                format!("strikes={k}"),
            ));
        }
    }
    Ok(())
}

pub fn assert_walk_off_terminal(
    game_id: &str,
    event: &CanonicalMlbEvent,
    after: &MlbGameState,
) -> Result<(), W6Error> {
    if event.event_type != MlbEventType::WalkOff {
        return Ok(());
    }
    if after.game_status != GameStatus::Final {
        return Err(fail(
            "WALKOFF_NOT_TERMINAL",
            game_id,
            &event.event_id,
            event.sequence,
            "walk-off must produce a Final game status",
        ));
    }
    Ok(())
}

pub fn assert_no_inning_after_walkoff(
    game_id: &str,
    prev_walkoff: bool,
    event: &CanonicalMlbEvent,
) -> Result<(), W6Error> {
    if prev_walkoff && event.event_type == MlbEventType::InningStart {
        return Err(fail(
            "WALKOFF_NEXT_INNING",
            game_id,
            &event.event_id,
            event.sequence,
            "walk-off must not create a next-inning state",
        ));
    }
    Ok(())
}

pub fn assert_half_outs(
    game_id: &str,
    event: &CanonicalMlbEvent,
    after: &MlbGameState,
) -> Result<(), W6Error> {
    if after.outs > 3 {
        return Err(fail(
            "OUTS_RANGE",
            game_id,
            &event.event_id,
            event.sequence,
            format!("outs={}", after.outs),
        ));
    }
    Ok(())
}
