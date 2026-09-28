//! Canonical reconstruction: W3 replay + W6 GameState / StateTransition wrapping.

use std::path::Path;

use chrono::{DateTime, Utc};
use momento_research_event::event::{CanonicalMlbEvent, FixtureKind, GameStatus, MlbEventType};
use momento_research_event::field::DataField;
use momento_research_event::identity::{OfficialMlbGameRef, PlayerRef};
use momento_research_event::ingest::ingest_path;
use momento_research_event::state::{MlbGameState, replay};

use crate::error::W6Error;
use crate::fingerprint::{
    event_type_token, fingerprint_state, fingerprint_transition, state_id_for, transition_id_for,
};
use crate::pa::PaTracker;
use crate::types::{
    EventKind, GameState, ReconstructedGame, StateTransition, bases_bitmask, classify_event_kind,
    derived_version, inning_half_id, occupancy_id, pa_version, total_outs_elapsed,
};
use crate::validate::{
    assert_count, assert_event_stream, assert_half_outs, assert_no_inning_after_walkoff,
    assert_runners, assert_walk_off_terminal,
};
use crate::versions::{RECONSTRUCTION_VERSION, SCHEMA_VERSION};

/// Deterministic canonical order: source sequence, then source event id.
/// Never uses retrieval time.
pub fn canonical_order(
    mut events: Vec<CanonicalMlbEvent>,
) -> Result<Vec<CanonicalMlbEvent>, W6Error> {
    events.sort_by(|a, b| {
        a.sequence
            .cmp(&b.sequence)
            .then_with(|| a.canonical_order.cmp(&b.canonical_order))
            .then_with(|| a.source_event_id.cmp(&b.source_event_id))
            .then_with(|| a.event_id.cmp(&b.event_id))
    });
    assert_event_stream(&events)?;
    Ok(events)
}

pub fn reconstruct_envelope(path: &Path) -> Result<ReconstructedGame, W6Error> {
    let (events, report, official) = ingest_path(path)?;
    if report.fixture_kind == FixtureKind::SyntheticTestFixture {
        return Err(W6Error::Timeline(
            "synthetic PBP excluded from historical reconstruction".into(),
        ));
    }
    reconstruct(&events, Some(&official))
}

pub fn reconstruct(
    events: &[CanonicalMlbEvent],
    official: Option<&OfficialMlbGameRef>,
) -> Result<ReconstructedGame, W6Error> {
    let ordered = canonical_order(events.to_vec())?;
    let game_id = ordered[0].game_id.as_str().to_string();
    let game_pk = official
        .map(|o| o.game_pk.clone())
        .unwrap_or_else(|| ordered[0].provenance.source_game_id.clone());

    let pbp = replay(&ordered).map_err(|e| map_replay_err(&game_id, &ordered, e))?;

    let mut pa = PaTracker::new();
    let pre = build_pre_game(&game_id, &game_pk, official, &ordered[0]);
    let mut states = vec![pre.clone()];
    let mut transitions = Vec::with_capacity(ordered.len());
    let mut first_timed: Option<DateTime<Utc>> = None;
    let mut walk_off = false;
    let mut extra_inning = false;
    let mut prev_walkoff = false;

    for (ev, tr) in ordered.iter().zip(pbp.iter()) {
        assert_no_inning_after_walkoff(&game_id, prev_walkoff, ev)?;
        assert_runners(&game_id, ev, &tr.after)?;
        assert_half_outs(&game_id, ev, &tr.after)?;
        assert_walk_off_terminal(&game_id, ev, &tr.after)?;

        pa.apply(&game_id, ev);
        if let Some(ts) = ev.source_timestamp.as_value().copied() {
            if first_timed.is_none() {
                first_timed = Some(ts);
            }
        }

        let prev = states.last().expect("pre-game exists");
        let after = project_state(prev, ev, &tr.after, official, &pa, first_timed, &game_pk)?;
        assert_count(&game_id, ev, &after.balls, &after.strikes)?;

        extra_inning |= after.extra_inning;
        walk_off |= after.walk_off;
        prev_walkoff = ev.event_type == MlbEventType::WalkOff;

        let transition = build_transition(prev, ev, &after, &tr.after.game_status)?;
        states.push(after);
        transitions.push(transition);
    }

    let terminal = states
        .last()
        .is_some_and(|s| s.game_status == GameStatus::Final);
    let timed_events = ordered
        .iter()
        .filter(|e| e.source_timestamp.as_value().is_some())
        .count();

    Ok(ReconstructedGame {
        game_id,
        game_pk,
        official_date: official.map(|o| o.official_date),
        pre_game: pre,
        states,
        transitions,
        events_total: ordered.len(),
        timed_events,
        extra_inning,
        walk_off,
        terminal,
    })
}

fn map_replay_err(
    game_id: &str,
    events: &[CanonicalMlbEvent],
    e: momento_research_event::EventError,
) -> W6Error {
    let (event_id, seq) = match &e {
        momento_research_event::EventError::SequenceGap { got, .. } => events
            .iter()
            .find(|ev| ev.sequence == *got)
            .map(|ev| (ev.event_id.clone(), ev.sequence))
            .unwrap_or_else(|| (String::new(), *got)),
        _ => events
            .last()
            .map(|ev| (ev.event_id.clone(), ev.sequence))
            .unwrap_or_default(),
    };
    match e {
        momento_research_event::EventError::Invariant { code, message } => {
            W6Error::validation(&code, game_id, event_id, seq, message)
        }
        momento_research_event::EventError::SequenceGap {
            expected,
            got,
            game_id: gid,
        } => W6Error::validation(
            "SEQUENCE_GAP",
            gid,
            event_id,
            got,
            format!("expected {expected} got {got}"),
        ),
        momento_research_event::EventError::DuplicateEvent {
            game_id: gid,
            source_event_id,
        } => W6Error::validation(
            "DUPLICATE_SOURCE_EVENT",
            gid,
            event_id,
            seq,
            source_event_id,
        ),
        other => W6Error::Timeline(other.to_string()),
    }
}

fn player_id(p: &DataField<PlayerRef>) -> DataField<String> {
    match p {
        DataField::Observed { value } => DataField::observed(value.source_player_id.clone()),
        DataField::Derived {
            value,
            transform_version,
        } => DataField::derived(value.source_player_id.clone(), transform_version.clone()),
        DataField::Inferred { value, confidence } => DataField::Inferred {
            value: value.source_player_id.clone(),
            confidence: confidence.clone(),
        },
        DataField::Unavailable { reason } => DataField::unavailable(reason.clone()),
    }
}

fn runner_slot(
    occ: &DataField<momento_research_event::event::BaseOccupancy>,
    which: u8,
) -> DataField<Option<String>> {
    match occ {
        DataField::Unavailable { reason } => DataField::unavailable(reason.clone()),
        other => {
            let Some(o) = other.as_value() else {
                return DataField::unavailable("occupancy missing");
            };
            let slot = match which {
                1 => &o.first,
                2 => &o.second,
                _ => &o.third,
            };
            DataField::observed(slot.as_ref().map(|p| p.source_player_id.clone()))
        }
    }
}

fn team_for_half(
    official: Option<&OfficialMlbGameRef>,
    batting: bool,
    half: momento_research_event::event::HalfInning,
) -> DataField<String> {
    let Some(o) = official else {
        return DataField::unavailable("official identity not supplied");
    };
    let away = if batting {
        match half {
            momento_research_event::event::HalfInning::Top => o.away_team.source_id.clone(),
            momento_research_event::event::HalfInning::Bottom => o.home_team.source_id.clone(),
        }
    } else {
        match half {
            momento_research_event::event::HalfInning::Top => o.home_team.source_id.clone(),
            momento_research_event::event::HalfInning::Bottom => o.away_team.source_id.clone(),
        }
    };
    DataField::observed(away)
}

fn count_after(
    event: &CanonicalMlbEvent,
    machine: &MlbGameState,
) -> (DataField<u8>, DataField<u8>) {
    let pa_end = matches!(
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
            | MlbEventType::InningEnd
            | MlbEventType::CatchersInterference
            | MlbEventType::FieldersChoice
            | MlbEventType::Error
    );
    if pa_end {
        return (
            DataField::derived(0, "W6.COUNT.RESET.1"),
            DataField::derived(0, "W6.COUNT.RESET.1"),
        );
    }
    let balls = event
        .balls
        .as_value()
        .copied()
        .map(DataField::observed)
        .unwrap_or_else(|| {
            if event.balls.is_unavailable() && machine.balls == 0 && machine.strikes == 0 {
                DataField::unavailable("authoritative count not supplied")
            } else {
                DataField::derived(machine.balls, "W6.COUNT.MACHINE.1")
            }
        });
    let strikes = event
        .strikes
        .as_value()
        .copied()
        .map(DataField::observed)
        .unwrap_or_else(|| {
            if event.strikes.is_unavailable() {
                DataField::unavailable("authoritative count not supplied")
            } else {
                DataField::derived(machine.strikes, "W6.COUNT.MACHINE.1")
            }
        });
    (balls, strikes)
}

fn count_id(balls: &DataField<u8>, strikes: &DataField<u8>) -> DataField<String> {
    match (balls.as_value(), strikes.as_value()) {
        (Some(b), Some(k)) => DataField::derived(format!("{b}-{k}"), derived_version()),
        _ => DataField::unavailable("count unavailable"),
    }
}

fn build_pre_game(
    game_id: &str,
    game_pk: &str,
    official: Option<&OfficialMlbGameRef>,
    first: &CanonicalMlbEvent,
) -> GameState {
    let runners = DataField::observed(None);
    let mask = 0u8;
    let mut s = GameState {
        state_id: String::new(),
        fingerprint: String::new(),
        fingerprint_version: GameState::fingerprint_version().to_string(),
        schema_version: SCHEMA_VERSION.to_string(),
        game_id: game_id.to_string(),
        game_pk: game_pk.to_string(),
        season: official
            .map(|o| DataField::observed(o.season.0))
            .unwrap_or_else(|| DataField::unavailable("season not in official ref")),
        game_date: official
            .map(|o| DataField::observed(o.official_date))
            .unwrap_or_else(|| DataField::unavailable("game date not in official ref")),
        home_team: official
            .map(|o| DataField::observed(o.home_team.source_id.clone()))
            .unwrap_or_else(|| DataField::unavailable("home team not in official ref")),
        away_team: official
            .map(|o| DataField::observed(o.away_team.source_id.clone()))
            .unwrap_or_else(|| DataField::unavailable("away team not in official ref")),
        home_abbreviation: official
            .map(|o| {
                if o.home_abbreviation.is_empty() {
                    DataField::unavailable("home abbreviation omitted")
                } else {
                    DataField::observed(o.home_abbreviation.clone())
                }
            })
            .unwrap_or_else(|| DataField::unavailable("home abbreviation not in official ref")),
        away_abbreviation: official
            .map(|o| {
                if o.away_abbreviation.is_empty() {
                    DataField::unavailable("away abbreviation omitted")
                } else {
                    DataField::observed(o.away_abbreviation.clone())
                }
            })
            .unwrap_or_else(|| DataField::unavailable("away abbreviation not in official ref")),
        game_number: official.map(|o| o.game_number).unwrap_or(1),
        game_status: GameStatus::PreGame,
        state_seq: 0,
        event_id: None,
        event_sequence: 0,
        source_event_id: DataField::unavailable("pre-game has no source event"),
        source_timestamp: DataField::unavailable("pre-game is not a playable event timestamp"),
        canonical_timestamp: DataField::unavailable("pre-game is not a playable event timestamp"),
        inning: 1,
        half: momento_research_event::event::HalfInning::Top,
        inning_half_id: inning_half_id(1, momento_research_event::event::HalfInning::Top),
        score_home: 0,
        score_away: 0,
        run_differential: 0,
        abs_run_differential: 0,
        outs: 0,
        outs_before_event: DataField::unavailable("pre-game"),
        runner_first: runners.clone(),
        runner_second: runners.clone(),
        runner_third: runners,
        bases_bitmask: mask,
        risp: false,
        base_occupancy_id: occupancy_id(mask),
        batter_id: DataField::unavailable("pre-game"),
        batter_team: DataField::unavailable("pre-game"),
        batter_hand: DataField::unavailable("handedness not in PBP"),
        batting_order_slot: DataField::unavailable("batting order slot not in PBP"),
        pitcher_id: DataField::unavailable("pre-game"),
        pitching_team: DataField::unavailable("pre-game"),
        pitcher_hand: DataField::unavailable("handedness not in PBP"),
        balls: DataField::derived(0, "W6.COUNT.PREGAME.1"),
        strikes: DataField::derived(0, "W6.COUNT.PREGAME.1"),
        count_id: DataField::derived("0-0".into(), derived_version()),
        pitch_of_pa: DataField::unavailable("pre-game"),
        pa_id: DataField::unavailable("pre-game"),
        pa_seq: DataField::unavailable("pre-game"),
        pa_phase: crate::types::PaPhase::None,
        pa_start_ts: DataField::unavailable("pre-game"),
        pa_end_ts: DataField::unavailable("pre-game"),
        pa_result: DataField::unavailable("pre-game"),
        pa_version: pa_version().to_string(),
        event_type: None,
        event_kind: EventKind::GameStart,
        event_description: DataField::unavailable("pre-game"),
        extra_inning: false,
        walk_off: false,
        outs_remaining_half: 3,
        total_outs_elapsed: DataField::derived(0, derived_version()),
        game_elapsed_ms: DataField::unavailable("pre-game"),
        game_remaining_ms: DataField::unavailable(
            "remaining game time not knowable without lookahead",
        ),
        base_out_id: format!("{}|0", occupancy_id(mask)),
        score_state_id: "0-0".into(),
        derived_version: derived_version().to_string(),
        source_dataset: first.provenance.source.clone(),
        source_version: first.provenance.parser_version.clone(),
        reconstruction_version: RECONSTRUCTION_VERSION.to_string(),
    };
    s.fingerprint = fingerprint_state(&s);
    s.state_id = state_id_for(&s);
    s
}

fn project_state(
    prev: &GameState,
    event: &CanonicalMlbEvent,
    after: &MlbGameState,
    official: Option<&OfficialMlbGameRef>,
    pa: &PaTracker,
    first_timed: Option<DateTime<Utc>>,
    game_pk: &str,
) -> Result<GameState, W6Error> {
    let r1 = runner_slot(&after.runners, 1);
    let r2 = runner_slot(&after.runners, 2);
    let r3 = runner_slot(&after.runners, 3);
    let mask = bases_bitmask(
        r1.as_value().and_then(|x| x.as_deref()),
        r2.as_value().and_then(|x| x.as_deref()),
        r3.as_value().and_then(|x| x.as_deref()),
    );
    let (balls, strikes) = count_after(event, after);
    let cid = count_id(&balls, &strikes);
    let diff = i32::from(after.score.home) - i32::from(after.score.away);
    let walk_off = event.event_type == MlbEventType::WalkOff
        || (after.game_status == GameStatus::Final
            && after.half == momento_research_event::event::HalfInning::Bottom
            && after.inning >= 9
            && after.score.home > after.score.away
            && after.score.home > prev.score_home);
    let elapsed = match (first_timed, event.source_timestamp.as_value()) {
        (Some(start), Some(now)) => {
            DataField::derived((*now - start).num_milliseconds(), derived_version())
        }
        _ => DataField::unavailable("elapsed time requires timed events"),
    };
    let kind = classify_event_kind(event.event_type, after.game_status, prev.game_status);
    let mut s = GameState {
        state_id: String::new(),
        fingerprint: String::new(),
        fingerprint_version: GameState::fingerprint_version().to_string(),
        schema_version: SCHEMA_VERSION.to_string(),
        game_id: prev.game_id.clone(),
        game_pk: game_pk.to_string(),
        season: prev.season.clone(),
        game_date: prev.game_date.clone(),
        home_team: prev.home_team.clone(),
        away_team: prev.away_team.clone(),
        home_abbreviation: prev.home_abbreviation.clone(),
        away_abbreviation: prev.away_abbreviation.clone(),
        game_number: prev.game_number,
        game_status: after.game_status,
        state_seq: after.state_seq,
        event_id: Some(event.event_id.clone()),
        event_sequence: event.sequence,
        source_event_id: DataField::observed(event.source_event_id.clone()),
        source_timestamp: event.source_timestamp.clone(),
        canonical_timestamp: event.source_timestamp.clone(),
        inning: after.inning,
        half: after.half,
        inning_half_id: inning_half_id(after.inning, after.half),
        score_home: after.score.home,
        score_away: after.score.away,
        run_differential: diff,
        abs_run_differential: diff.unsigned_abs() as u16,
        outs: after.outs,
        outs_before_event: event
            .outs_before
            .as_value()
            .copied()
            .map(DataField::observed)
            .unwrap_or_else(|| DataField::derived(prev.outs, derived_version())),
        runner_first: r1,
        runner_second: r2,
        runner_third: r3,
        bases_bitmask: mask,
        risp: mask & 6 != 0,
        base_occupancy_id: occupancy_id(mask),
        batter_id: player_id(&after.batter),
        batter_team: after
            .batting_team
            .clone()
            .or_else_unavailable(|| team_for_half(official, true, after.half)),
        batter_hand: DataField::unavailable("handedness not in PBP"),
        batting_order_slot: DataField::unavailable("batting order slot not in PBP"),
        pitcher_id: player_id(&after.pitcher),
        pitching_team: after
            .fielding_team
            .clone()
            .or_else_unavailable(|| team_for_half(official, false, after.half)),
        pitcher_hand: DataField::unavailable("handedness not in PBP"),
        balls,
        strikes,
        count_id: cid,
        pitch_of_pa: pa.pitch_of_pa.clone(),
        pa_id: pa.id.clone(),
        pa_seq: pa.seq_field(),
        pa_phase: if pa.phase == crate::types::PaPhase::Result {
            crate::types::PaPhase::Result
        } else {
            pa.phase
        },
        pa_start_ts: pa.start_ts.clone(),
        pa_end_ts: pa.end_ts.clone(),
        pa_result: pa.result.clone(),
        pa_version: pa_version().to_string(),
        event_type: Some(event.event_type),
        event_kind: kind,
        event_description: event.event_description.clone(),
        extra_inning: after.inning > 9,
        walk_off,
        outs_remaining_half: 3u8.saturating_sub(after.outs.min(3)),
        total_outs_elapsed: DataField::derived(
            total_outs_elapsed(after.inning, after.half, after.outs),
            derived_version(),
        ),
        game_elapsed_ms: elapsed,
        game_remaining_ms: DataField::unavailable(
            "remaining game time not knowable without lookahead",
        ),
        base_out_id: format!("{}|{}", occupancy_id(mask), after.outs),
        score_state_id: format!("{}-{}", after.score.home, after.score.away),
        derived_version: derived_version().to_string(),
        source_dataset: event.provenance.source.clone(),
        source_version: event.provenance.parser_version.clone(),
        reconstruction_version: RECONSTRUCTION_VERSION.to_string(),
    };
    s.fingerprint = fingerprint_state(&s);
    s.state_id = state_id_for(&s);
    Ok(s)
}

fn changed_player(a: &DataField<String>, b: &DataField<String>) -> bool {
    a.as_value() != b.as_value()
}

fn build_transition(
    prev: &GameState,
    event: &CanonicalMlbEvent,
    after: &GameState,
    _status: &GameStatus,
) -> Result<StateTransition, W6Error> {
    let bases_before = prev.bases_bitmask;
    let mut t = StateTransition {
        transition_id: String::new(),
        fingerprint: String::new(),
        game_id: after.game_id.clone(),
        sequence: after.event_sequence,
        event_id: event.event_id.clone(),
        source_event_id: event.source_event_id.clone(),
        previous_state_id: prev.state_id.clone(),
        resulting_state_id: after.state_id.clone(),
        event_timestamp: event.source_timestamp.clone(),
        event_type: event.event_type,
        event_kind: after.event_kind,
        source_event_type: event
            .event_description
            .as_value()
            .cloned()
            .map(DataField::observed)
            .unwrap_or_else(|| DataField::observed(event_type_token(event.event_type).to_string())),
        score_delta_home: i32::from(after.score_home) - i32::from(prev.score_home),
        score_delta_away: i32::from(after.score_away) - i32::from(prev.score_away),
        out_delta: i32::from(after.outs) - i32::from(prev.outs),
        bases_before,
        bases_after: after.bases_bitmask,
        batter_changed: changed_player(&prev.batter_id, &after.batter_id),
        pitcher_changed: changed_player(&prev.pitcher_id, &after.pitcher_id),
        inning_changed: prev.inning != after.inning,
        half_changed: prev.half != after.half,
        count_changed: prev.balls.as_value() != after.balls.as_value()
            || prev.strikes.as_value() != after.strikes.as_value(),
        runner_first_changed: prev.runner_first.as_value() != after.runner_first.as_value(),
        runner_second_changed: prev.runner_second.as_value() != after.runner_second.as_value(),
        runner_third_changed: prev.runner_third.as_value() != after.runner_third.as_value(),
        substitution: matches!(
            event.event_type,
            MlbEventType::PitchingChange | MlbEventType::BattingChange | MlbEventType::Substitution
        ),
        review: event.event_type == MlbEventType::Review
            || event.review.as_ref().is_some_and(|r| r.in_review),
        amendment: event.is_amendment(),
        delay: after.event_kind == EventKind::Delay,
        walk_off: after.walk_off,
        extra_inning: after.extra_inning && !prev.extra_inning,
        pa_phase: after.pa_phase,
        amends_event_id: event.amends_event_id.clone(),
        provenance_source: event.provenance.source.clone(),
        provenance_raw_file: event.provenance.raw_file.clone(),
        reconstruction_version: RECONSTRUCTION_VERSION.to_string(),
    };
    t.fingerprint = fingerprint_transition(&t);
    t.transition_id = transition_id_for(&t);
    Ok(t)
}

trait OrElseUnavail<T> {
    fn or_else_unavailable(self, f: impl FnOnce() -> DataField<T>) -> DataField<T>;
}

impl<T> OrElseUnavail<T> for DataField<T> {
    fn or_else_unavailable(self, f: impl FnOnce() -> DataField<T>) -> DataField<T> {
        if self.is_unavailable() { f() } else { self }
    }
}
