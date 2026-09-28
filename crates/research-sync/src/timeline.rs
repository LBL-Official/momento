//! W3 PBP timeline: ingest + replay. No second game-state reconstruction.

use chrono::{DateTime, Utc};
use momento_research_event::CanonicalGameId;
use momento_research_event::event::{CanonicalMlbEvent, FixtureKind};
use momento_research_event::ingest::ingest_path;
use momento_research_event::state::{MlbGameState, replay};
use std::collections::HashSet;
use std::path::Path;

use crate::error::W5Error;
use crate::types::{GameStateSnapshot, KIND_PBP_OFFICIAL, TimedEvent};

#[derive(Clone, Debug)]
pub struct PbpTimeline {
    pub game_id: String,
    pub game_pk: String,
    pub events_total: usize,
    pub timed: Vec<TimedEvent>,
    pub backward_time: bool,
    pub duplicate_event_id: bool,
    pub duplicate_sequence: bool,
    pub wrong_game_id: bool,
    pub synthetic: bool,
}

impl PbpTimeline {
    pub fn ambiguous_clock(&self) -> bool {
        self.duplicate_event_id || self.duplicate_sequence || self.wrong_game_id
    }
}

pub fn load_pbp_timeline(envelope: &Path) -> Result<PbpTimeline, W5Error> {
    let (events, report, official) = ingest_path(envelope)
        .map_err(|e| W5Error::Timeline(format!("{}: {e}", envelope.display())))?;
    if report.fixture_kind == FixtureKind::SyntheticTestFixture {
        return Err(W5Error::Timeline(
            "synthetic PBP excluded from historical sync".into(),
        ));
    }
    if events.is_empty() {
        return Ok(PbpTimeline {
            game_id: CanonicalGameId::from_official_source("mlb_statsapi", &official.game_pk)
                .map(|g| g.0)
                .unwrap_or_default(),
            game_pk: official.game_pk,
            events_total: 0,
            timed: Vec::new(),
            backward_time: false,
            duplicate_event_id: false,
            duplicate_sequence: false,
            wrong_game_id: false,
            synthetic: false,
        });
    }
    build_timeline(&events, &official.game_pk)
}

pub fn build_timeline(events: &[CanonicalMlbEvent], game_pk: &str) -> Result<PbpTimeline, W5Error> {
    let mut ids = HashSet::new();
    let mut seqs = HashSet::new();
    let mut duplicate_event_id = false;
    let mut duplicate_sequence = false;
    let mut wrong_game_id = false;
    let expected = CanonicalGameId::from_official_source("mlb_statsapi", game_pk)
        .map_err(|e| W5Error::Identity(e.to_string()))?;

    let mut ordered = events.to_vec();
    ordered.sort_by_key(|e| (e.canonical_order, e.sequence));

    for e in &ordered {
        if e.game_id != expected {
            wrong_game_id = true;
        }
        if !ids.insert(e.event_id.clone()) {
            duplicate_event_id = true;
        }
        if !seqs.insert(e.sequence) {
            duplicate_sequence = true;
        }
    }

    let transitions = replay(&ordered).map_err(|e| W5Error::Timeline(e.to_string()))?;
    let mut timed = Vec::new();
    let mut prev_t: Option<DateTime<Utc>> = None;
    let mut backward_time = false;
    for (ev, tr) in ordered.iter().zip(transitions.iter()) {
        let Some(ts) = ev.source_timestamp.as_value().copied() else {
            continue;
        };
        let raw = ts.to_rfc3339();
        if let Some(p) = prev_t {
            if ts < p {
                backward_time = true;
            }
        }
        prev_t = Some(ts);
        timed.push(TimedEvent {
            event_id: ev.event_id.clone(),
            sequence: ev.sequence,
            source_event_time: raw,
            source_timestamp_kind: KIND_PBP_OFFICIAL.into(),
            normalized_event_time: ts,
            previous_event_id: None,
            next_event_id: None,
            state_before: snapshot(&tr.before, &ev.event_id),
            state_after: snapshot(&tr.after, &ev.event_id),
        });
    }
    timed.sort_by(|a, b| {
        a.normalized_event_time
            .cmp(&b.normalized_event_time)
            .then(a.sequence.cmp(&b.sequence))
    });
    link_event_neighbors(&mut timed);
    Ok(PbpTimeline {
        game_id: expected.0,
        game_pk: game_pk.to_string(),
        events_total: events.len(),
        timed,
        backward_time,
        duplicate_event_id,
        duplicate_sequence,
        wrong_game_id,
        synthetic: false,
    })
}

pub fn link_event_neighbors(timed: &mut [TimedEvent]) {
    let n = timed.len();
    for i in 0..n {
        if i > 0 {
            timed[i].previous_event_id = Some(timed[i - 1].event_id.clone());
        }
        if i + 1 < n {
            timed[i].next_event_id = Some(timed[i + 1].event_id.clone());
        }
    }
}

pub fn snapshot(state: &MlbGameState, event_id: &str) -> GameStateSnapshot {
    let runners = state.runners.as_value();
    GameStateSnapshot {
        game_id: state.game_id.as_str().to_string(),
        event_id: event_id.to_string(),
        state_seq: state.state_seq,
        inning: state.inning,
        half: format!("{:?}", state.half).to_uppercase(),
        outs: state.outs,
        score_home: state.score.home,
        score_away: state.score.away,
        run_differential: state.score.differential(),
        runner_first: runners.and_then(|r| r.first.as_ref().map(|p| p.source_player_id.clone())),
        runner_second: runners.and_then(|r| r.second.as_ref().map(|p| p.source_player_id.clone())),
        runner_third: runners.and_then(|r| r.third.as_ref().map(|p| p.source_player_id.clone())),
        batter: state.batter.as_value().map(|p| p.source_player_id.clone()),
        pitcher: state.pitcher.as_value().map(|p| p.source_player_id.clone()),
        balls: state.balls,
        strikes: state.strikes,
        count: format!("{}-{}", state.balls, state.strikes),
        game_status: format!("{:?}", state.game_status).to_uppercase(),
        extra_inning: state.extra_inning,
    }
}
