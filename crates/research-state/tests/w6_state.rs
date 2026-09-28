//! W6 canonical state engine tests.

use chrono::{TimeZone, Utc};
use momento_research_event::event::{
    BaseOccupancy, CanonicalMlbEvent, GameStatus, HalfInning, MlbEventType, Score,
};
use momento_research_event::field::DataField;
use momento_research_event::identity::DataYear;
use momento_research_event::identity::{
    CanonicalGameId, OfficialMlbGameRef, PlayerRef, SourceRef, event_id,
};
use momento_research_event::synthetic;
use momento_research_state::engine::{canonical_order, reconstruct};
use momento_research_state::firewall::W6_FORBIDDEN_CONCEPTS;
use momento_research_state::lookup::{
    next_event, previous_event, state_at_event, state_at_or_before,
};
use momento_research_state::store::StateStore;
use momento_research_state::types::{PaPhase, TimeLookup};
use momento_research_state::{WATERFALL, join_points};
use std::collections::HashSet;
use std::path::Path;

fn ts(seq: u32) -> chrono::DateTime<Utc> {
    Utc.with_ymd_and_hms(2026, 6, 18, 18, 0, seq.min(59))
        .unwrap()
}

fn player(id: &str) -> PlayerRef {
    PlayerRef {
        source: "SYNTHETIC_TEST_FIXTURE".into(),
        source_player_id: id.into(),
    }
}

fn occ(first: Option<&str>, second: Option<&str>, third: Option<&str>) -> BaseOccupancy {
    BaseOccupancy {
        first: first.map(player),
        second: second.map(player),
        third: third.map(player),
    }
}

fn retarget(mut events: Vec<CanonicalMlbEvent>, source: &str, pk: &str) -> Vec<CanonicalMlbEvent> {
    let gid = CanonicalGameId::from_official_source(source, pk).unwrap();
    for e in &mut events {
        e.game_id = gid.clone();
        e.provenance.source_game_id = pk.to_string();
        e.event_id = event_id(&gid, e.sequence, &e.source_event_id);
    }
    events
}

fn official(pk: &str, n: u8) -> OfficialMlbGameRef {
    OfficialMlbGameRef {
        source: "mlb_statsapi".into(),
        game_pk: pk.into(),
        season: DataYear(2026),
        official_date: chrono::NaiveDate::from_ymd_opt(2026, 6, 18).unwrap(),
        home_team: SourceRef {
            source: "mlb_statsapi".into(),
            source_id: "147".into(),
        },
        away_team: SourceRef {
            source: "mlb_statsapi".into(),
            source_id: "111".into(),
        },
        venue: None,
        game_number: n,
        competition: "MLB".into(),
        home_abbreviation: "NYY".into(),
        away_abbreviation: "BOS".into(),
    }
}

fn set_seq(e: &mut CanonicalMlbEvent, seq: u32) {
    e.sequence = seq;
    e.canonical_order = seq;
    e.source_event_id = format!("syn-{seq}");
    e.event_id = event_id(&e.game_id, seq, &e.source_event_id);
    e.source_timestamp = DataField::observed(ts(seq));
}

fn walkoff_valid(inning: u8, runner_second: Option<&str>) -> Vec<CanonicalMlbEvent> {
    let mut v = synthetic::catalog_play_types_valid();
    v.truncate(1);
    let mut mid = v[0].clone();
    set_seq(&mut mid, 2);
    mid.event_type = MlbEventType::InningStart;
    mid.inning = DataField::observed(inning);
    mid.half = DataField::observed(HalfInning::Bottom);
    mid.outs_before = DataField::observed(0);
    mid.outs_after = DataField::observed(0);
    mid.score_before = DataField::observed(Score { home: 0, away: 0 });
    mid.score_after = DataField::observed(Score { home: 0, away: 0 });
    mid.runs_scored = DataField::observed(0);
    mid.runners_before = DataField::observed(occ(None, None, None));
    mid.runners_after = DataField::observed(occ(None, runner_second, None));
    mid.game_status_after = DataField::observed(GameStatus::InProgress);
    mid.batter = DataField::observed(player("H9"));
    mid.pitcher = DataField::observed(player("P9"));
    mid.event_description = DataField::observed("inning start".into());
    let mut wo = mid.clone();
    set_seq(&mut wo, 3);
    wo.event_type = MlbEventType::WalkOff;
    wo.score_before = DataField::observed(Score { home: 0, away: 0 });
    wo.score_after = DataField::observed(Score { home: 1, away: 0 });
    wo.runs_scored = DataField::observed(1);
    wo.runners_before = DataField::observed(occ(None, runner_second, None));
    wo.runners_after = DataField::observed(occ(None, None, None));
    wo.game_status_after = DataField::observed(GameStatus::Final);
    wo.event_description = DataField::observed("walk-off".into());
    vec![v[0].clone(), mid, wo]
}

fn pitch_seq() -> Vec<CanonicalMlbEvent> {
    let mut v = synthetic::catalog_play_types_valid();
    v.truncate(1);
    let mut strike = v[0].clone();
    set_seq(&mut strike, 2);
    strike.event_type = MlbEventType::Strike;
    strike.balls = DataField::observed(0);
    strike.strikes = DataField::observed(1);
    strike.outs_before = DataField::observed(0);
    strike.outs_after = DataField::observed(0);
    strike.batter = DataField::observed(player("B1"));
    strike.pitcher = DataField::observed(player("P1"));
    strike.event_description = DataField::observed("strike".into());
    let mut strike2 = strike.clone();
    set_seq(&mut strike2, 3);
    strike2.event_type = MlbEventType::Strike;
    strike2.strikes = DataField::observed(2);
    let mut foul = strike2.clone();
    set_seq(&mut foul, 4);
    foul.event_type = MlbEventType::Foul;
    foul.strikes = DataField::observed(2);
    foul.event_description = DataField::observed("foul with two strikes".into());
    let mut k = foul.clone();
    set_seq(&mut k, 5);
    k.event_type = MlbEventType::Strikeout;
    k.strikes = DataField::observed(0);
    k.balls = DataField::observed(0);
    k.outs_after = DataField::observed(1);
    k.event_description = DataField::observed("strikeout".into());
    vec![v[0].clone(), strike, strike2, foul, k]
}

#[test]
fn waterfall_is_w6() {
    assert_eq!(WATERFALL, "CTO-W6");
}

#[test]
fn deterministic_replay() {
    let events = synthetic::catalog_play_types_valid();
    let a = reconstruct(&events, None).unwrap();
    let b = reconstruct(&events, None).unwrap();
    assert_eq!(a.states, b.states);
    assert_eq!(a.transitions, b.transitions);
    assert_eq!(
        a.states.last().unwrap().fingerprint,
        b.states.last().unwrap().fingerprint
    );
}

#[test]
fn state_immutability_across_replay() {
    let events = synthetic::catalog_play_types_valid();
    let a = reconstruct(&events, None).unwrap();
    let mut copy = a.states[1].clone();
    copy.score_home = 99;
    let b = reconstruct(&events, None).unwrap();
    assert_eq!(a.states[1].score_home, b.states[1].score_home);
    assert_ne!(copy.score_home, a.states[1].score_home);
}

#[test]
fn fingerprints_deterministic() {
    let events = synthetic::catalog_play_types_valid();
    let a = reconstruct(&events, None).unwrap();
    let b = reconstruct(&events, None).unwrap();
    for (x, y) in a.states.iter().zip(b.states.iter()) {
        assert_eq!(x.fingerprint, y.fingerprint);
        assert_eq!(x.state_id, y.state_id);
    }
    for (x, y) in a.transitions.iter().zip(b.transitions.iter()) {
        assert_eq!(x.fingerprint, y.fingerprint);
        assert_eq!(x.transition_id, y.transition_id);
    }
}

#[test]
fn first_inning_construction() {
    let game = reconstruct(&synthetic::catalog_play_types_valid(), None).unwrap();
    let pre = &game.states[0];
    assert_eq!(pre.inning, 1);
    assert_eq!(pre.half, HalfInning::Top);
    assert_eq!(pre.outs, 0);
    assert_eq!(pre.score_home, 0);
    assert_eq!(pre.score_away, 0);
    assert_eq!(pre.bases_bitmask, 0);
    assert_eq!(pre.game_status, GameStatus::PreGame);
    let start = &game.states[1];
    assert_eq!(start.inning, 1);
    assert_eq!(start.event_type, Some(MlbEventType::GameStart));
}

#[test]
fn score_and_run_differential() {
    let game = reconstruct(&synthetic::catalog_play_types_valid(), None).unwrap();
    let last = game.states.last().unwrap();
    assert_eq!(
        last.run_differential,
        i32::from(last.score_home) - i32::from(last.score_away)
    );
    assert!(last.score_away >= 6);
    let scored = game
        .transitions
        .iter()
        .any(|t| t.score_delta_away > 0 || t.score_delta_home > 0);
    assert!(scored);
}

#[test]
fn runner_placement_and_advancement() {
    let game = reconstruct(&synthetic::catalog_play_types_valid(), None).unwrap();
    let walk = game
        .states
        .iter()
        .rev()
        .find(|s| s.event_type == Some(MlbEventType::Walk))
        .unwrap();
    assert_eq!(
        walk.runner_first.as_value().cloned().flatten().as_deref(),
        Some("B7")
    );
    let sb = game
        .states
        .iter()
        .find(|s| s.event_type == Some(MlbEventType::StolenBase))
        .unwrap();
    assert!(sb.runner_first.as_value().cloned().flatten().is_none());
    assert_eq!(
        sb.runner_second.as_value().cloned().flatten().as_deref(),
        Some("B7")
    );
}

#[test]
fn outs_and_half_inning_transition() {
    let game = reconstruct(&synthetic::catalog_play_types_valid(), None).unwrap();
    let dp = game
        .states
        .iter()
        .find(|s| s.event_type == Some(MlbEventType::DoublePlay))
        .unwrap();
    assert_eq!(dp.outs, 3);
    let iend = game
        .states
        .iter()
        .find(|s| s.event_type == Some(MlbEventType::InningEnd))
        .unwrap();
    assert_eq!(iend.outs, 0);
    assert_eq!(iend.half, HalfInning::Bottom);
    let tr = game
        .transitions
        .iter()
        .find(|t| t.event_type == MlbEventType::InningEnd)
        .unwrap();
    assert!(tr.half_changed);
}

#[test]
fn count_progression_foul_two_strikes_walk_hbp_hr() {
    let game = reconstruct(&pitch_seq(), None).unwrap();
    let s2 = game.states.iter().find(|s| s.event_sequence == 3).unwrap();
    assert_eq!(s2.strikes.as_value().copied(), Some(2));
    let foul = game.states.iter().find(|s| s.event_sequence == 4).unwrap();
    assert_eq!(foul.event_type, Some(MlbEventType::Foul));
    assert_eq!(foul.strikes.as_value().copied(), Some(2));
    let k = game.states.iter().find(|s| s.event_sequence == 5).unwrap();
    assert_eq!(k.event_type, Some(MlbEventType::Strikeout));
    assert_eq!(k.outs, 1);
    assert_eq!(k.balls.as_value().copied(), Some(0));
    assert_eq!(k.strikes.as_value().copied(), Some(0));

    let catalog = reconstruct(&synthetic::catalog_play_types_valid(), None).unwrap();
    assert!(
        catalog
            .states
            .iter()
            .any(|s| s.event_type == Some(MlbEventType::Walk))
    );
    assert!(
        catalog
            .states
            .iter()
            .any(|s| s.event_type == Some(MlbEventType::HitByPitch))
    );
    assert!(
        catalog
            .states
            .iter()
            .any(|s| s.event_type == Some(MlbEventType::HomeRun))
    );
    let hr = catalog
        .states
        .iter()
        .find(|s| s.event_type == Some(MlbEventType::HomeRun))
        .unwrap();
    assert_eq!(hr.bases_bitmask, 0);
}

#[test]
fn double_play_stolen_base_and_caught_stealing() {
    let game = reconstruct(&synthetic::catalog_play_types_valid(), None).unwrap();
    assert!(
        game.states
            .iter()
            .any(|s| s.event_type == Some(MlbEventType::DoublePlay))
    );
    assert!(
        game.states
            .iter()
            .any(|s| s.event_type == Some(MlbEventType::StolenBase))
    );

    let mut events = synthetic::catalog_play_types_valid();
    events.truncate(
        events
            .iter()
            .position(|e| e.event_type == MlbEventType::StolenBase)
            .unwrap()
            + 1,
    );
    let mut cs = events.last().unwrap().clone();
    let seq = cs.sequence + 1;
    set_seq(&mut cs, seq);
    cs.event_type = MlbEventType::FieldOut;
    cs.outs_before = DataField::observed(0);
    cs.outs_after = DataField::observed(1);
    cs.runners_before = DataField::observed(occ(None, Some("B7"), None));
    cs.runners_after = DataField::observed(occ(None, None, None));
    cs.event_description = DataField::observed("caught stealing".into());
    events.push(cs);
    let game = reconstruct(&events, None).unwrap();
    let last = game.states.last().unwrap();
    assert_eq!(last.outs, 1);
    assert_eq!(last.bases_bitmask, 0);
}

#[test]
fn pitcher_change_and_batter_substitution() {
    let game = reconstruct(&synthetic::catalog_play_types_valid(), None).unwrap();
    let pc = game
        .transitions
        .iter()
        .find(|t| t.event_type == MlbEventType::PitchingChange)
        .unwrap();
    assert!(pc.pitcher_changed);
    assert!(pc.substitution);
    let bc = game
        .transitions
        .iter()
        .find(|t| t.event_type == MlbEventType::BattingChange)
        .unwrap();
    assert!(bc.batter_changed);
}

#[test]
fn pinch_runner() {
    let mut events = synthetic::catalog_play_types_valid();
    events.truncate(
        events
            .iter()
            .position(|e| e.event_type == MlbEventType::Walk)
            .unwrap()
            + 1,
    );
    let mut pr = events.last().unwrap().clone();
    let seq = pr.sequence + 1;
    set_seq(&mut pr, seq);
    pr.event_type = MlbEventType::Substitution;
    pr.runners_before = DataField::observed(occ(Some("B7"), None, None));
    pr.runners_after = DataField::observed(occ(Some("PR1"), None, None));
    pr.substitution = DataField::observed("pinch runner".into());
    pr.event_description = DataField::observed("pinch runner".into());
    events.push(pr);
    let game = reconstruct(&events, None).unwrap();
    let last = game.states.last().unwrap();
    assert_eq!(
        last.runner_first.as_value().cloned().flatten().as_deref(),
        Some("PR1")
    );
    assert!(game.transitions.last().unwrap().substitution);
}

#[test]
fn extra_innings_and_walkoff_no_next_inning() {
    let extra = reconstruct(&walkoff_valid(10, None), None).unwrap();
    assert!(extra.extra_inning);
    assert!(extra.walk_off);
    assert!(extra.terminal);
    assert!(
        !extra
            .states
            .iter()
            .any(|s| s.walk_off && s.inning > extra.states.last().unwrap().inning)
    );
    let last = extra.states.last().unwrap();
    assert_eq!(last.game_status, GameStatus::Final);
    assert_eq!(last.inning, 10);

    let wo = reconstruct(&walkoff_valid(9, None), None).unwrap();
    assert!(wo.walk_off);
    assert_eq!(wo.states.last().unwrap().game_status, GameStatus::Final);
    assert!(
        !wo.states
            .iter()
            .any(|s| s.event_type == Some(MlbEventType::InningStart) && s.inning == 10)
    );
}

#[test]
fn extra_inning_runner_on_second_from_source() {
    let game = reconstruct(&walkoff_valid(10, Some("EI2")), None).unwrap();
    let tenth = game
        .states
        .iter()
        .find(|s| s.event_type == Some(MlbEventType::InningStart))
        .unwrap();
    assert_eq!(
        tenth.runner_second.as_value().cloned().flatten().as_deref(),
        Some("EI2")
    );
}

#[test]
fn delayed_and_review_events() {
    let mut events = synthetic::amendment_review_outs();
    let mut delay = events[1].clone();
    set_seq(&mut delay, events.len() as u32 + 1);
    delay.event_type = MlbEventType::Other;
    delay.game_status_after = DataField::observed(GameStatus::Delayed);
    delay.event_description = DataField::observed("rain delay".into());
    delay.outs_before = events
        .last()
        .unwrap()
        .outs_after
        .as_value()
        .copied()
        .map(DataField::observed)
        .unwrap();
    delay.outs_after = delay.outs_before.clone();
    delay.score_before = events.last().unwrap().score_after.clone();
    delay.score_after = delay.score_before.clone();
    events.push(delay);
    let game = reconstruct(&events, None).unwrap();
    assert!(game.transitions.iter().any(|t| t.review || t.amendment));
    assert!(
        game.states
            .iter()
            .any(|s| s.game_status == GameStatus::Delayed)
    );
}

#[test]
fn malformed_impossible_state_fails_closed() {
    assert!(reconstruct(&synthetic::illegal_score_drop(), None).is_err());
    assert!(reconstruct(&synthetic::strikeout_then_illegal_outs_drop(), None).is_err());
}

#[test]
fn duplicate_event_fails_closed() {
    let mut events = synthetic::catalog_play_types_valid();
    let dup = events[1].clone();
    events.push(dup);
    let err = reconstruct(&events, None).unwrap_err();
    assert!(
        err.to_string().contains("duplicate")
            || matches!(err, momento_research_state::W6Error::Validation { .. })
    );
}

#[test]
fn deterministic_same_timestamp_ordering() {
    let mut events = pitch_seq();
    let t = ts(2);
    events[1].source_timestamp = DataField::observed(t);
    events[2].source_timestamp = DataField::observed(t);
    let shuffled = vec![
        events[0].clone(),
        events[2].clone(),
        events[1].clone(),
        events[3].clone(),
        events[4].clone(),
    ];
    let ordered = canonical_order(shuffled).unwrap();
    assert_eq!(ordered[1].sequence, 2);
    assert_eq!(ordered[2].sequence, 3);
    let game = reconstruct(&ordered, None).unwrap();
    let hit = state_at_or_before(&game, t);
    match hit {
        TimeLookup::Hit { state, .. } => {
            assert_eq!(
                state.event_sequence, 3,
                "same timestamp uses later source sequence"
            );
        }
        TimeLookup::NoState { .. } => panic!("expected hit"),
    }
}

#[test]
fn state_at_or_before_no_future_and_no_state() {
    let game = reconstruct(&pitch_seq(), None).unwrap();
    let e3 = game.states.iter().find(|s| s.event_sequence == 3).unwrap();
    let t3 = *e3.canonical_timestamp.as_value().unwrap();
    let before = t3 - chrono::Duration::milliseconds(1);
    match state_at_or_before(&game, before) {
        TimeLookup::Hit { state, .. } => {
            assert!(state.event_sequence < 3);
            assert_ne!(state.fingerprint, e3.fingerprint);
        }
        TimeLookup::NoState { .. } => {
            assert!(
                game.states
                    .iter()
                    .filter(|s| s.event_sequence > 0 && s.event_sequence < 3)
                    .all(|s| s.canonical_timestamp.as_value().is_none_or(|t| *t > before))
            );
        }
    }
    let very_early = Utc.with_ymd_and_hms(2020, 1, 1, 0, 0, 0).unwrap();
    match state_at_or_before(&game, very_early) {
        TimeLookup::NoState {
            next_event_time, ..
        } => {
            assert!(next_event_time.is_some());
        }
        TimeLookup::Hit { .. } => panic!("must not return a future state"),
    }
    let at = state_at_or_before(&game, t3);
    match at {
        TimeLookup::Hit { state, .. } => assert_eq!(state.event_sequence, 3),
        TimeLookup::NoState { .. } => panic!("exact timestamp should hit"),
    }
    let at_event = state_at_event(&game, 3).unwrap();
    assert_eq!(at_event.event_sequence, 3);
    assert!(previous_event(&game, 3).is_some());
    assert!(next_event(&game, 3).is_some());
}

#[test]
fn provenance_preserved() {
    let game = reconstruct(&synthetic::catalog_play_types_valid(), None).unwrap();
    for s in game.states.iter().skip(1) {
        assert!(!s.source_dataset.is_empty());
        assert!(s.source_event_id.as_value().is_some());
        assert!(!s.reconstruction_version.is_empty());
    }
    for t in &game.transitions {
        assert!(!t.provenance_source.is_empty());
        assert!(!t.source_event_id.is_empty());
        assert!(!t.previous_state_id.is_empty());
    }
}

#[test]
fn game_id_uniqueness_and_doubleheader_separation() {
    let a = retarget(walkoff_valid(9, None), "mlb_statsapi", "1001");
    let b = retarget(walkoff_valid(9, None), "mlb_statsapi", "1002");
    let ga = reconstruct(&a, Some(&official("1001", 1))).unwrap();
    let gb = reconstruct(&b, Some(&official("1002", 2))).unwrap();
    assert_ne!(ga.game_id, gb.game_id);
    assert_ne!(ga.pre_game.state_id, gb.pre_game.state_id);
    assert_eq!(ga.pre_game.game_number, 1);
    assert_eq!(gb.pre_game.game_number, 2);
}

#[test]
fn pa_lifecycle_play_and_pitch_level() {
    let pitch = reconstruct(&pitch_seq(), None).unwrap();
    assert!(pitch.states.iter().any(|s| s.pa_phase == PaPhase::Pitch));
    assert!(pitch.states.iter().any(|s| s.pa_phase == PaPhase::Result));
    let play = reconstruct(&synthetic::catalog_play_types_valid(), None).unwrap();
    assert!(play.states.iter().any(|s| s.pa_phase == PaPhase::Result));
}

#[test]
fn join_points_have_no_prices() {
    let game = reconstruct(&walkoff_valid(9, None), None).unwrap();
    let keys = join_points(&game);
    assert!(!keys.is_empty());
    let encoded = serde_json::to_string(&keys).unwrap();
    assert!(!encoded.contains("cents"));
    assert!(!encoded.contains("bid"));
}

#[test]
fn sqlite_state_at_or_before_no_lookahead() {
    let game = reconstruct(&pitch_seq(), None).unwrap();
    let mut store = StateStore::open_memory("test", Utc::now()).unwrap();
    store.insert_game(&game, "OK", None).unwrap();
    let e3 = game.states.iter().find(|s| s.event_sequence == 3).unwrap();
    let t3 = *e3.canonical_timestamp.as_value().unwrap();
    let id = store
        .state_id_at_or_before(&game.game_id, t3)
        .unwrap()
        .unwrap();
    assert_eq!(id, e3.state_id);
    let early = store
        .state_id_at_or_before(
            &game.game_id,
            Utc.with_ymd_and_hms(2020, 1, 1, 0, 0, 0).unwrap(),
        )
        .unwrap();
    assert!(early.is_none());
}

#[test]
fn wild_pitch_passed_ball_balk_force_fc() {
    let mut events = synthetic::catalog_play_types_valid();
    events.truncate(
        events
            .iter()
            .position(|e| e.event_type == MlbEventType::Walk)
            .unwrap()
            + 1,
    );
    let template = events.last().unwrap().clone();
    let mut seq = template.sequence;
    for (ty, desc, after, outs_a) in [
        (
            MlbEventType::WildPitch,
            "wild pitch",
            occ(None, Some("B7"), None),
            0u8,
        ),
        (
            MlbEventType::PassedBall,
            "passed ball",
            occ(None, None, Some("B7")),
            0,
        ),
        (MlbEventType::Balk, "balk", occ(None, None, Some("B7")), 0),
    ] {
        seq += 1;
        let mut e = template.clone();
        set_seq(&mut e, seq);
        e.event_type = ty;
        e.outs_before = DataField::observed(0);
        e.outs_after = DataField::observed(outs_a);
        e.runners_after = DataField::observed(after);
        e.event_description = DataField::observed(desc.into());
        e.score_before = template.score_after.clone();
        e.score_after = template.score_after.clone();
        events.push(e);
    }
    seq += 1;
    let mut fc = template.clone();
    set_seq(&mut fc, seq);
    fc.event_type = MlbEventType::FieldersChoice;
    fc.outs_before = DataField::observed(0);
    fc.outs_after = DataField::observed(1);
    fc.runners_after = DataField::observed(occ(Some("B8"), None, None));
    fc.batter = DataField::observed(player("B8"));
    events.push(fc);
    seq += 1;
    let mut fo = template.clone();
    set_seq(&mut fo, seq);
    fo.event_type = MlbEventType::ForceOut;
    fo.outs_before = DataField::observed(1);
    fo.outs_after = DataField::observed(2);
    fo.runners_before = DataField::observed(occ(Some("B8"), None, None));
    fo.runners_after = DataField::observed(occ(None, None, None));
    events.push(fo);
    let game = reconstruct(&events, None).unwrap();
    assert!(
        game.states
            .iter()
            .any(|s| s.event_type == Some(MlbEventType::WildPitch))
    );
    assert!(
        game.states
            .iter()
            .any(|s| s.event_type == Some(MlbEventType::PassedBall))
    );
    assert!(
        game.states
            .iter()
            .any(|s| s.event_type == Some(MlbEventType::Balk))
    );
    assert!(
        game.states
            .iter()
            .any(|s| s.event_type == Some(MlbEventType::FieldersChoice))
    );
    assert!(
        game.states
            .iter()
            .any(|s| s.event_type == Some(MlbEventType::ForceOut))
    );
}

#[test]
fn remaining_time_never_uses_future() {
    let game = reconstruct(&walkoff_valid(9, None), None).unwrap();
    for s in &game.states {
        assert!(s.game_remaining_ms.is_unavailable());
    }
}

#[test]
fn firewall_forbids_greeks_and_strategy_types() {
    let lib = include_str!("../src/lib.rs");
    let engine = include_str!("../src/engine.rs");
    for bad in W6_FORBIDDEN_CONCEPTS {
        assert!(!lib.contains(bad), "{bad} in lib");
        assert!(!engine.contains(bad), "{bad} in engine");
    }
}

#[test]
fn reconstruction_smoke_real_pbp_if_present() {
    let root = Path::new("Backtesting Suite/Foundation/Ingest/landing/mlb_statsapi");
    if !root.exists() {
        return;
    }
    let mut n = 0usize;
    let mut ok = 0usize;
    fn walk(dir: &Path, n: &mut usize, ok: &mut usize) {
        let Ok(rd) = std::fs::read_dir(dir) else {
            return;
        };
        for ent in rd.flatten() {
            let p = ent.path();
            if p.is_dir() {
                walk(&p, n, ok);
            } else if p
                .file_name()
                .and_then(|s| s.to_str())
                .is_some_and(|s| s.ends_with(".envelope.json"))
            {
                if *n >= 3 {
                    return;
                }
                *n += 1;
                if momento_research_state::reconstruct_envelope(&p).is_ok() {
                    *ok += 1;
                }
            }
        }
    }
    walk(root, &mut n, &mut ok);
    assert!(n == 0 || ok > 0, "present PBP envelopes should reconstruct");
}

#[test]
fn state_ids_unique_within_game() {
    let game = reconstruct(&synthetic::catalog_play_types_valid(), None).unwrap();
    let mut ids = HashSet::new();
    for s in &game.states {
        assert!(ids.insert(s.state_id.clone()));
    }
    let mut tids = HashSet::new();
    for t in &game.transitions {
        assert!(tids.insert(t.transition_id.clone()));
    }
    assert_eq!(game.states.len(), game.transitions.len() + 1);
}

#[test]
fn score_never_decreases() {
    let game = reconstruct(&synthetic::catalog_play_types_valid(), None).unwrap();
    for w in game.states.windows(2) {
        assert!(w[1].score_home >= w[0].score_home);
        assert!(w[1].score_away >= w[0].score_away);
    }
}
