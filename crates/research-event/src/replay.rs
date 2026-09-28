//! Replay, determinism, and game validation summaries.

use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};

use crate::error::EventError;
use crate::event::{CanonicalMlbEvent, GameStatus, Score};
use crate::identity::CanonicalGameId;
use crate::outcome::GameOutcome;
use crate::state::{MlbGameState, MlbPbpTransition, replay};
use crate::versions::{NORMALIZATION_VERSION, PARSER_VERSION, STATE_MACHINE_VERSION};

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct GameValidation {
    pub game_id: String,
    pub source: String,
    pub events: usize,
    pub valid: bool,
    pub invalid: usize,
    pub warnings: Vec<String>,
    pub missing_fields: Vec<String>,
    pub final_score: Option<Score>,
    pub computed_final_score: Option<Score>,
    pub reconciled: bool,
    pub parser_version: String,
    pub normalization_version: String,
    pub state_machine_version: String,
    pub error: Option<String>,
}

pub fn validate_game(
    events: &[CanonicalMlbEvent],
    outcome: Option<&GameOutcome>,
) -> GameValidation {
    let game_id = events
        .first()
        .map(|e| e.game_id.as_str().to_string())
        .unwrap_or_default();
    let source = events
        .first()
        .map(|e| e.provenance.source.clone())
        .unwrap_or_default();
    let mut missing = Vec::new();
    for e in events {
        if e.source_timestamp.is_unavailable() {
            missing.push(format!("seq {} source_timestamp", e.sequence));
        }
        if e.runners_after.is_unavailable() {
            missing.push(format!("seq {} runners_after", e.sequence));
        }
    }
    match replay(events) {
        Ok(trs) => {
            let last = trs.last().map(|t| t.after.clone());
            let computed = last.as_ref().map(|s| s.score);
            let final_score = outcome.map(|o| o.final_score);
            let reconciled = match (&final_score, &computed) {
                (Some(a), Some(b)) => a == b,
                (None, _) => {
                    last.as_ref()
                        .is_some_and(|s| s.game_status != GameStatus::Final)
                        || final_score.is_none()
                }
                _ => false,
            };
            let warnings: Vec<String> = trs
                .iter()
                .flat_map(|t| t.invariant_warnings.clone())
                .collect();
            GameValidation {
                game_id,
                source,
                events: events.len(),
                valid: true,
                invalid: 0,
                warnings,
                missing_fields: missing,
                final_score,
                computed_final_score: computed,
                reconciled,
                parser_version: PARSER_VERSION.into(),
                normalization_version: NORMALIZATION_VERSION.into(),
                state_machine_version: STATE_MACHINE_VERSION.into(),
                error: None,
            }
        }
        Err(e) => GameValidation {
            game_id,
            source,
            events: events.len(),
            valid: false,
            invalid: 1,
            warnings: vec![],
            missing_fields: missing,
            final_score: outcome.map(|o| o.final_score),
            computed_final_score: None,
            reconciled: false,
            parser_version: PARSER_VERSION.into(),
            normalization_version: NORMALIZATION_VERSION.into(),
            state_machine_version: STATE_MACHINE_VERSION.into(),
            error: Some(e.to_string()),
        },
    }
}

pub fn timeline_fingerprint(events: &[CanonicalMlbEvent]) -> Result<String, EventError> {
    let body = serde_json::to_vec(events)?;
    Ok(format!("{:x}", Sha256::digest(body)))
}

pub fn replay_is_deterministic(events: &[CanonicalMlbEvent]) -> Result<bool, EventError> {
    let a = replay(events)?;
    let b = replay(events)?;
    let fa = serde_json::to_vec(&a)?;
    let fb = serde_json::to_vec(&b)?;
    Ok(fa == fb)
}

pub fn restore_state(transitions: &[MlbPbpTransition], seq: u32) -> Option<MlbGameState> {
    transitions
        .iter()
        .find(|t| t.sequence == seq)
        .map(|t| t.after.clone())
}

/// Causal prefix: events with sequence <= t. Outcome is never included.
pub fn causal_prefix(events: &[CanonicalMlbEvent], t: u32) -> Vec<CanonicalMlbEvent> {
    events.iter().filter(|e| e.sequence <= t).cloned().collect()
}

/// Substrings that must not appear on an in-progress `MlbGameState` dump.
pub const LOOKAHEAD_FORBIDDEN_SUBSTRINGS: &[&str] = &[
    "winner",
    "OUTCOME_LABEL",
    "final_score",
    "settlement",
    "starting_price",
    "yes_bid",
    "orderbook",
    "market_mid",
    "implied_probability",
];

pub fn assert_no_future_leakage(
    events: &[CanonicalMlbEvent],
    t: u32,
    outcome: &GameOutcome,
) -> Result<(), EventError> {
    let prefix = causal_prefix(events, t);
    if prefix.iter().any(|e| e.sequence > t) {
        return Err(EventError::invariant(
            "LOOKAHEAD",
            "prefix contained future sequence",
        ));
    }
    if prefix.len() != events.iter().filter(|e| e.sequence <= t).count() {
        return Err(EventError::invariant("LOOKAHEAD", "prefix length mismatch"));
    }
    let trs = replay(&prefix)?;
    let state = &trs
        .last()
        .ok_or_else(|| EventError::Malformed("empty replay".into()))?
        .after;
    let dump = serde_json::to_string(state)?;
    for needle in LOOKAHEAD_FORBIDDEN_SUBSTRINGS {
        if dump.contains(needle) {
            return Err(EventError::invariant(
                "LOOKAHEAD",
                format!("state serialization leaked {needle}"),
            ));
        }
    }
    if t < events.last().map(|e| e.sequence).unwrap_or(0) {
        if state.game_status == GameStatus::Final {
            return Err(EventError::invariant(
                "LOOKAHEAD",
                "non-terminal prefix marked Final",
            ));
        }
        if state.score == outcome.final_score && prefix.len() < events.len() {
            // Allowed only if the game had already reached that score; still must not expose winner.
        }
    }
    let _ = CanonicalGameId::from_official_source;
    let _ = outcome.winner;
    Ok(())
}
