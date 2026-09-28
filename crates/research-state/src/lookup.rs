//! Time-addressable lookup. Never returns a future state.

use chrono::{DateTime, Utc};

use crate::error::W6Error;
use crate::types::{GameState, ReconstructedGame, StateTransition, TimeLookup};

pub fn replay_game_from(reconstructed: &ReconstructedGame) -> &ReconstructedGame {
    reconstructed
}

pub fn state_at_event(
    game: &ReconstructedGame,
    event_sequence: u32,
) -> Result<&GameState, W6Error> {
    game.states
        .iter()
        .find(|s| {
            s.event_sequence == event_sequence && (event_sequence == 0 || s.event_id.is_some())
        })
        .or_else(|| game.states.iter().find(|s| s.state_seq == event_sequence))
        .ok_or(W6Error::NoState)
}

pub fn transition_at_event(
    game: &ReconstructedGame,
    event_sequence: u32,
) -> Result<&StateTransition, W6Error> {
    game.transitions
        .iter()
        .find(|t| t.sequence == event_sequence)
        .ok_or(W6Error::NoState)
}

/// Latest canonical state whose authoritative event timestamp is <= T.
/// Pre-game and untimed events do not participate.
/// If none exist, `TimeLookup::NoState` — never the first later event.
/// Same timestamps break ties with source sequence (later sequence wins).
pub fn state_at_or_before<'a>(game: &'a ReconstructedGame, t: DateTime<Utc>) -> TimeLookup<'a> {
    let mut timed: Vec<(usize, DateTime<Utc>, u32)> = game
        .states
        .iter()
        .enumerate()
        .filter_map(|(i, s)| {
            if s.state_seq == 0 {
                return None;
            }
            s.canonical_timestamp
                .as_value()
                .copied()
                .map(|ts| (i, ts, s.event_sequence))
        })
        .collect();
    timed.sort_by(|a, b| a.1.cmp(&b.1).then(a.2.cmp(&b.2)));

    let mut lo = 0usize;
    let mut hi = timed.len();
    while lo < hi {
        let mid = (lo + hi) / 2;
        if timed[mid].1 <= t {
            lo = mid + 1;
        } else {
            hi = mid;
        }
    }
    if lo == 0 {
        let next = timed.first().map(|(i, ts, _)| (*i, *ts));
        return TimeLookup::NoState {
            next_event_id: next.and_then(|(i, _)| game.states[i].event_id.as_deref()),
            next_event_time: next.map(|(_, ts)| ts),
        };
    }
    let idx = timed[lo - 1].0;
    let prev_t = if lo >= 2 { Some(timed[lo - 2].1) } else { None };
    let next_t = timed.get(lo).map(|x| x.1);
    TimeLookup::Hit {
        state: &game.states[idx],
        previous_event_id: if lo >= 2 {
            game.states[timed[lo - 2].0].event_id.as_deref()
        } else {
            None
        },
        next_event_id: timed
            .get(lo)
            .and_then(|(i, _, _)| game.states[*i].event_id.as_deref()),
        previous_event_time: prev_t,
        next_event_time: next_t,
    }
}

pub fn previous_event(game: &ReconstructedGame, event_sequence: u32) -> Option<&GameState> {
    let pos = game
        .states
        .iter()
        .position(|s| s.event_sequence == event_sequence)?;
    if pos == 0 {
        None
    } else {
        Some(&game.states[pos - 1])
    }
}

pub fn next_event(game: &ReconstructedGame, event_sequence: u32) -> Option<&GameState> {
    let pos = game
        .states
        .iter()
        .position(|s| s.event_sequence == event_sequence)?;
    game.states.get(pos + 1)
}
