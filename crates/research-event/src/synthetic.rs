//! SYNTHETIC_TEST_FIXTURE builders. These are **not** historical MLB games.

use chrono::{TimeZone, Utc};

use crate::event::{
    BaseOccupancy, CanonicalMlbEvent, EventProvenance, FixtureKind, GameStatus, HalfInning,
    MlbEventType, ReviewInfo, Score,
};
use crate::field::DataField;
use crate::identity::{CanonicalGameId, PlayerRef, event_id};
use crate::w1_bridge::MlbTimestampKind;

const SOURCE: &str = "SYNTHETIC_TEST_FIXTURE";

fn gid() -> CanonicalGameId {
    CanonicalGameId::from_official_source(SOURCE, "synthetic-001").expect("id")
}

fn player(id: &str) -> PlayerRef {
    PlayerRef {
        source: SOURCE.into(),
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

struct Spec {
    seq: u32,
    ty: MlbEventType,
    inning: u8,
    half: HalfInning,
    outs_b: u8,
    outs_a: u8,
    score_b: Score,
    score_a: Score,
    run_b: BaseOccupancy,
    run_a: BaseOccupancy,
    desc: &'static str,
    balls: u8,
    strikes: u8,
    status: GameStatus,
    amends: Option<&'static str>,
    batter: &'static str,
    pitcher: &'static str,
}

fn score(h: u16, a: u16) -> Score {
    Score { home: h, away: a }
}

fn ev(s: Spec) -> CanonicalMlbEvent {
    let game_id = gid();
    let source_event_id = format!("syn-{}", s.seq);
    let ts = Utc
        .with_ymd_and_hms(2026, 6, 18, 18, 0, s.seq.min(59))
        .unwrap();
    let runs = s.score_a.total().saturating_sub(s.score_b.total()) as u8;
    let (bat, field) = if s.half == HalfInning::Top {
        ("111", "147")
    } else {
        ("147", "111")
    };
    CanonicalMlbEvent {
        event_id: event_id(&game_id, s.seq, &source_event_id),
        game_id,
        sequence: s.seq,
        source_event_id: source_event_id.clone(),
        source_timestamp: DataField::observed(ts),
        source_timestamp_kind: MlbTimestampKind::PbpOfficial,
        collector_timestamp: DataField::unavailable("synthetic has no collector"),
        canonical_order: s.seq,
        inning: DataField::observed(s.inning),
        half: DataField::observed(s.half),
        outs_before: DataField::observed(s.outs_b),
        outs_after: DataField::observed(s.outs_a),
        score_before: DataField::observed(s.score_b),
        score_after: DataField::observed(s.score_a),
        batting_team: DataField::observed(bat.into()),
        fielding_team: DataField::observed(field.into()),
        batter: DataField::observed(player(s.batter)),
        pitcher: DataField::observed(player(s.pitcher)),
        runners_before: DataField::observed(s.run_b),
        runners_after: DataField::observed(s.run_a),
        event_type: s.ty,
        event_description: DataField::observed(s.desc.into()),
        runs_scored: DataField::observed(runs),
        balls: DataField::observed(s.balls),
        strikes: DataField::observed(s.strikes),
        pitch: None,
        review: if s.ty == MlbEventType::Review {
            Some(ReviewInfo {
                in_review: true,
                overturned: DataField::observed(true),
                challenge_team: DataField::observed("111".into()),
            })
        } else {
            None
        },
        substitution: if matches!(
            s.ty,
            MlbEventType::PitchingChange | MlbEventType::BattingChange | MlbEventType::Substitution
        ) {
            DataField::observed(s.desc.into())
        } else {
            DataField::unavailable("none")
        },
        amends_event_id: s.amends.map(|x| x.to_string()),
        game_status_after: DataField::observed(s.status),
        provenance: EventProvenance {
            source: SOURCE.into(),
            source_game_id: "synthetic-001".into(),
            source_event_id,
            raw_file: DataField::unavailable("in-memory SYNTHETIC_TEST_FIXTURE"),
            raw_line: DataField::unavailable("in-memory"),
            payload_sha256: DataField::unavailable("in-memory"),
            parser_version: crate::versions::PARSER_VERSION.into(),
            normalization_version: crate::versions::NORMALIZATION_VERSION.into(),
            schema_version: crate::versions::SCHEMA_VERSION.into(),
            retrieval_timestamp: DataField::unavailable("synthetic"),
            fixture_kind: FixtureKind::SyntheticTestFixture,
        },
    }
}

fn start() -> CanonicalMlbEvent {
    ev(Spec {
        seq: 1,
        ty: MlbEventType::GameStart,
        inning: 1,
        half: HalfInning::Top,
        outs_b: 0,
        outs_a: 0,
        score_b: score(0, 0),
        score_a: score(0, 0),
        run_b: occ(None, None, None),
        run_a: occ(None, None, None),
        desc: "SYNTHETIC_TEST_FIXTURE game_start",
        balls: 0,
        strikes: 0,
        status: GameStatus::InProgress,
        amends: None,
        batter: "B1",
        pitcher: "P1",
    })
}

/// Top 1st ends (3 outs) then bottom 1st first out. Real StatsAPI omits InningEnd records.
pub fn inning_change_after_three_outs() -> Vec<CanonicalMlbEvent> {
    vec![
        start(),
        ev(Spec {
            seq: 2,
            ty: MlbEventType::Strikeout,
            inning: 1,
            half: HalfInning::Top,
            outs_b: 0,
            outs_a: 3,
            score_b: score(0, 0),
            score_a: score(0, 0),
            run_b: occ(None, None, None),
            run_a: occ(None, None, None),
            desc: "third out of top 1st",
            balls: 0,
            strikes: 0,
            status: GameStatus::InProgress,
            amends: None,
            batter: "B1",
            pitcher: "P1",
        }),
        ev(Spec {
            seq: 3,
            ty: MlbEventType::FieldOut,
            inning: 1,
            half: HalfInning::Bottom,
            outs_b: 0,
            outs_a: 1,
            score_b: score(0, 0),
            score_a: score(0, 0),
            run_b: occ(None, None, None),
            run_a: occ(None, None, None),
            desc: "first out of bottom 1st after inning change",
            balls: 0,
            strikes: 0,
            status: GameStatus::InProgress,
            amends: None,
            batter: "B2",
            pitcher: "P2",
        }),
    ]
}

/// Normal inning fragment covering required play types (not a real game).
pub fn catalog_play_types() -> Vec<CanonicalMlbEvent> {
    let mut v = vec![start()];
    let mut seq = 2u32;
    let push = |v: &mut Vec<_>, seq: &mut u32, mut s: Spec| {
        s.seq = *seq;
        v.push(ev(s));
        *seq += 1;
    };
    push(
        &mut v,
        &mut seq,
        Spec {
            seq: 0,
            ty: MlbEventType::Strike,
            inning: 1,
            half: HalfInning::Top,
            outs_b: 0,
            outs_a: 0,
            score_b: score(0, 0),
            score_a: score(0, 0),
            run_b: occ(None, None, None),
            run_a: occ(None, None, None),
            desc: "strike",
            balls: 0,
            strikes: 1,
            status: GameStatus::InProgress,
            amends: None,
            batter: "B1",
            pitcher: "P1",
        },
    );
    push(
        &mut v,
        &mut seq,
        Spec {
            seq: 0,
            ty: MlbEventType::Ball,
            inning: 1,
            half: HalfInning::Top,
            outs_b: 0,
            outs_a: 0,
            score_b: score(0, 0),
            score_a: score(0, 0),
            run_b: occ(None, None, None),
            run_a: occ(None, None, None),
            desc: "ball",
            balls: 1,
            strikes: 1,
            status: GameStatus::InProgress,
            amends: None,
            batter: "B1",
            pitcher: "P1",
        },
    );
    push(
        &mut v,
        &mut seq,
        Spec {
            seq: 0,
            ty: MlbEventType::Walk,
            inning: 1,
            half: HalfInning::Top,
            outs_b: 0,
            outs_a: 0,
            score_b: score(0, 0),
            score_a: score(0, 0),
            run_b: occ(None, None, None),
            run_a: occ(Some("B1"), None, None),
            desc: "walk — runner on first",
            balls: 0,
            strikes: 0,
            status: GameStatus::InProgress,
            amends: None,
            batter: "B1",
            pitcher: "P1",
        },
    );
    push(
        &mut v,
        &mut seq,
        Spec {
            seq: 0,
            ty: MlbEventType::Single,
            inning: 1,
            half: HalfInning::Top,
            outs_b: 0,
            outs_a: 0,
            score_b: score(0, 0),
            score_a: score(0, 0),
            run_b: occ(Some("B1"), None, None),
            run_a: occ(Some("B2"), Some("B1"), None),
            desc: "single — first/second",
            balls: 0,
            strikes: 0,
            status: GameStatus::InProgress,
            amends: None,
            batter: "B2",
            pitcher: "P1",
        },
    );
    push(
        &mut v,
        &mut seq,
        Spec {
            seq: 0,
            ty: MlbEventType::HitByPitch,
            inning: 1,
            half: HalfInning::Top,
            outs_b: 0,
            outs_a: 0,
            score_b: score(0, 0),
            score_a: score(0, 0),
            run_b: occ(Some("B2"), Some("B1"), None),
            run_a: occ(Some("B3"), Some("B2"), Some("B1")),
            desc: "HBP — bases loaded",
            balls: 0,
            strikes: 0,
            status: GameStatus::InProgress,
            amends: None,
            batter: "B3",
            pitcher: "P1",
        },
    );
    push(
        &mut v,
        &mut seq,
        Spec {
            seq: 0,
            ty: MlbEventType::Double,
            inning: 1,
            half: HalfInning::Top,
            outs_b: 0,
            outs_a: 0,
            score_b: score(0, 0),
            score_a: score(0, 2),
            run_b: occ(Some("B3"), Some("B2"), Some("B1")),
            run_a: occ(None, Some("B4"), Some("B3")),
            desc: "double scoring",
            balls: 0,
            strikes: 0,
            status: GameStatus::InProgress,
            amends: None,
            batter: "B4",
            pitcher: "P1",
        },
    );
    push(
        &mut v,
        &mut seq,
        Spec {
            seq: 0,
            ty: MlbEventType::Triple,
            inning: 1,
            half: HalfInning::Top,
            outs_b: 0,
            outs_a: 0,
            score_b: score(0, 2),
            score_a: score(0, 4),
            run_b: occ(None, Some("B4"), Some("B3")),
            run_a: occ(None, None, Some("B5")),
            desc: "triple",
            balls: 0,
            strikes: 0,
            status: GameStatus::InProgress,
            amends: None,
            batter: "B5",
            pitcher: "P1",
        },
    );
    push(
        &mut v,
        &mut seq,
        Spec {
            seq: 0,
            ty: MlbEventType::HomeRun,
            inning: 1,
            half: HalfInning::Top,
            outs_b: 0,
            outs_a: 0,
            score_b: score(0, 4),
            score_a: score(0, 6),
            run_b: occ(None, None, Some("B5")),
            run_a: occ(None, None, None),
            desc: "home run",
            balls: 0,
            strikes: 0,
            status: GameStatus::InProgress,
            amends: None,
            batter: "B6",
            pitcher: "P1",
        },
    );
    push(
        &mut v,
        &mut seq,
        Spec {
            seq: 0,
            ty: MlbEventType::StolenBase,
            inning: 1,
            half: HalfInning::Top,
            outs_b: 0,
            outs_a: 0,
            score_b: score(0, 6),
            score_a: score(0, 6),
            run_b: occ(Some("B7"), None, None),
            run_a: occ(None, Some("B7"), None),
            desc: "stolen_base",
            balls: 1,
            strikes: 0,
            status: GameStatus::InProgress,
            amends: None,
            batter: "B8",
            pitcher: "P1",
        },
    );
    // stolen_base assumes B7 on first — insert a walk first? Current state has empty bases after HR.
    // Fix: the stolen base event has runners_before first occupied — state machine will fail
    // OUTS_BEFORE/score but runners aren't checked for continuity strictly.
    // Runners_before won't be validated against state. That's OK for catalog if we insert a walk.
    v
}

/// Repair catalog: after HR bases empty, walk then SB.
pub fn catalog_play_types_valid() -> Vec<CanonicalMlbEvent> {
    let mut v = catalog_play_types();
    // Replace stolen-base (last) with walk then SB
    v.pop();
    let seq = v.len() as u32 + 1;
    let walk = ev(Spec {
        seq,
        ty: MlbEventType::Walk,
        inning: 1,
        half: HalfInning::Top,
        outs_b: 0,
        outs_a: 0,
        score_b: score(0, 6),
        score_a: score(0, 6),
        run_b: occ(None, None, None),
        run_a: occ(Some("B7"), None, None),
        desc: "walk before SB",
        balls: 0,
        strikes: 0,
        status: GameStatus::InProgress,
        amends: None,
        batter: "B7",
        pitcher: "P1",
    });
    let sb = ev(Spec {
        seq: seq + 1,
        ty: MlbEventType::StolenBase,
        inning: 1,
        half: HalfInning::Top,
        outs_b: 0,
        outs_a: 0,
        score_b: score(0, 6),
        score_a: score(0, 6),
        run_b: occ(Some("B7"), None, None),
        run_a: occ(None, Some("B7"), None),
        desc: "stolen_base",
        balls: 1,
        strikes: 0,
        status: GameStatus::InProgress,
        amends: None,
        batter: "B8",
        pitcher: "P1",
    });
    let sac = ev(Spec {
        seq: seq + 2,
        ty: MlbEventType::Sacrifice,
        inning: 1,
        half: HalfInning::Top,
        outs_b: 0,
        outs_a: 1,
        score_b: score(0, 6),
        score_a: score(0, 7),
        run_b: occ(None, Some("B7"), None),
        run_a: occ(None, None, None),
        desc: "sacrifice",
        balls: 0,
        strikes: 0,
        status: GameStatus::InProgress,
        amends: None,
        batter: "B8",
        pitcher: "P1",
    });
    let k = ev(Spec {
        seq: seq + 3,
        ty: MlbEventType::Strikeout,
        inning: 1,
        half: HalfInning::Top,
        outs_b: 1,
        outs_a: 2,
        score_b: score(0, 7),
        score_a: score(0, 7),
        run_b: occ(None, None, None),
        run_a: occ(None, None, None),
        desc: "strikeout",
        balls: 0,
        strikes: 0,
        status: GameStatus::InProgress,
        amends: None,
        batter: "B9",
        pitcher: "P1",
    });
    let err = ev(Spec {
        seq: seq + 4,
        ty: MlbEventType::Error,
        inning: 1,
        half: HalfInning::Top,
        outs_b: 2,
        outs_a: 2,
        score_b: score(0, 7),
        score_a: score(0, 7),
        run_b: occ(None, None, None),
        run_a: occ(Some("B10"), None, None),
        desc: "error",
        balls: 0,
        strikes: 0,
        status: GameStatus::InProgress,
        amends: None,
        batter: "B10",
        pitcher: "P1",
    });
    let dp = ev(Spec {
        seq: seq + 5,
        ty: MlbEventType::DoublePlay,
        inning: 1,
        half: HalfInning::Top,
        outs_b: 2,
        outs_a: 3,
        score_b: score(0, 7),
        score_a: score(0, 7),
        run_b: occ(Some("B10"), None, None),
        run_a: occ(None, None, None),
        desc: "double play (third out)",
        balls: 0,
        strikes: 0,
        status: GameStatus::InProgress,
        amends: None,
        batter: "B11",
        pitcher: "P1",
    });
    let iend = ev(Spec {
        seq: seq + 6,
        ty: MlbEventType::InningEnd,
        inning: 1,
        half: HalfInning::Bottom,
        outs_b: 3,
        outs_a: 0,
        score_b: score(0, 7),
        score_a: score(0, 7),
        run_b: occ(None, None, None),
        run_a: occ(None, None, None),
        desc: "inning transition to bottom 1",
        balls: 0,
        strikes: 0,
        status: GameStatus::InProgress,
        amends: None,
        batter: "H1",
        pitcher: "P2",
    });
    let pc = ev(Spec {
        seq: seq + 7,
        ty: MlbEventType::PitchingChange,
        inning: 1,
        half: HalfInning::Bottom,
        outs_b: 0,
        outs_a: 0,
        score_b: score(0, 7),
        score_a: score(0, 7),
        run_b: occ(None, None, None),
        run_a: occ(None, None, None),
        desc: "pitching_change",
        balls: 0,
        strikes: 0,
        status: GameStatus::InProgress,
        amends: None,
        batter: "H1",
        pitcher: "P3",
    });
    let bc = ev(Spec {
        seq: seq + 8,
        ty: MlbEventType::BattingChange,
        inning: 1,
        half: HalfInning::Bottom,
        outs_b: 0,
        outs_a: 0,
        score_b: score(0, 7),
        score_a: score(0, 7),
        run_b: occ(None, None, None),
        run_a: occ(None, None, None),
        desc: "batting_change",
        balls: 0,
        strikes: 0,
        status: GameStatus::InProgress,
        amends: None,
        batter: "H1b",
        pitcher: "P3",
    });
    let rev = ev(Spec {
        seq: seq + 9,
        ty: MlbEventType::Review,
        inning: 1,
        half: HalfInning::Bottom,
        outs_b: 0,
        outs_a: 0,
        score_b: score(0, 7),
        score_a: score(0, 7),
        run_b: occ(None, None, None),
        run_a: occ(None, None, None),
        desc: "review",
        balls: 0,
        strikes: 0,
        status: GameStatus::InProgress,
        amends: None,
        batter: "H1b",
        pitcher: "P3",
    });
    v.extend([walk, sb, sac, k, err, dp, iend, pc, bc, rev]);
    v
}

pub fn walkoff_bottom_ninth() -> Vec<CanonicalMlbEvent> {
    vec![
        start(),
        ev(Spec {
            seq: 2,
            ty: MlbEventType::InningStart,
            inning: 9,
            half: HalfInning::Bottom,
            outs_b: 0,
            outs_a: 0,
            score_b: score(3, 3),
            score_a: score(3, 3),
            run_b: occ(None, None, None),
            run_a: occ(None, None, None),
            desc: "SYNTHETIC jump to bottom 9 tied (fixture, not a full game)",
            balls: 0,
            strikes: 0,
            status: GameStatus::InProgress,
            amends: None,
            batter: "H9",
            pitcher: "P9",
        }),
        ev(Spec {
            seq: 3,
            ty: MlbEventType::WalkOff,
            inning: 9,
            half: HalfInning::Bottom,
            outs_b: 0,
            outs_a: 0,
            score_b: score(3, 3),
            score_a: score(4, 3),
            run_b: occ(None, None, None),
            run_a: occ(None, None, None),
            desc: "walk-off single",
            balls: 0,
            strikes: 0,
            status: GameStatus::Final,
            amends: None,
            batter: "H9",
            pitcher: "P9",
        }),
    ]
}

/// Walk-off fixture that is illegal for sequential replay from pre-game (inning jump).
/// Used as a labeled fragment after seeding state via a dedicated helper.
pub fn extra_inning_walkoff() -> Vec<CanonicalMlbEvent> {
    vec![
        start(),
        ev(Spec {
            seq: 2,
            ty: MlbEventType::InningStart,
            inning: 10,
            half: HalfInning::Bottom,
            outs_b: 0,
            outs_a: 0,
            score_b: score(2, 2),
            score_a: score(2, 2),
            run_b: occ(None, None, None),
            run_a: occ(None, None, None),
            desc: "SYNTHETIC extra innings bottom 10",
            balls: 0,
            strikes: 0,
            status: GameStatus::InProgress,
            amends: None,
            batter: "H10",
            pitcher: "P10",
        }),
        ev(Spec {
            seq: 3,
            ty: MlbEventType::WalkOff,
            inning: 10,
            half: HalfInning::Bottom,
            outs_b: 1,
            outs_a: 1,
            score_b: score(2, 2),
            score_a: score(3, 2),
            run_b: occ(None, None, Some("R3")),
            run_a: occ(None, None, None),
            desc: "extra-inning walk-off",
            balls: 0,
            strikes: 0,
            status: GameStatus::Final,
            amends: None,
            batter: "H10",
            pitcher: "P10",
        }),
    ]
}

pub fn amendment_review_outs() -> Vec<CanonicalMlbEvent> {
    vec![
        start(),
        ev(Spec {
            seq: 2,
            ty: MlbEventType::Strikeout,
            inning: 1,
            half: HalfInning::Top,
            outs_b: 0,
            outs_a: 1,
            score_b: score(0, 0),
            score_a: score(0, 0),
            run_b: occ(None, None, None),
            run_a: occ(None, None, None),
            desc: "called strikeout",
            balls: 0,
            strikes: 0,
            status: GameStatus::InProgress,
            amends: None,
            batter: "B1",
            pitcher: "P1",
        }),
        ev(Spec {
            seq: 3,
            ty: MlbEventType::Amendment,
            inning: 1,
            half: HalfInning::Top,
            outs_b: 1,
            outs_a: 0,
            score_b: score(0, 0),
            score_a: score(0, 0),
            run_b: occ(None, None, None),
            run_a: occ(Some("B1"), None, None),
            desc: "review overturn: batter safe",
            balls: 0,
            strikes: 0,
            status: GameStatus::InProgress,
            amends: Some("syn-2"),
            batter: "B1",
            pitcher: "P1",
        }),
    ]
}

pub fn strikeout_then_illegal_outs_drop() -> Vec<CanonicalMlbEvent> {
    vec![
        start(),
        ev(Spec {
            seq: 2,
            ty: MlbEventType::Strikeout,
            inning: 1,
            half: HalfInning::Top,
            outs_b: 0,
            outs_a: 1,
            score_b: score(0, 0),
            score_a: score(0, 0),
            run_b: occ(None, None, None),
            run_a: occ(None, None, None),
            desc: "k",
            balls: 0,
            strikes: 0,
            status: GameStatus::InProgress,
            amends: None,
            batter: "B1",
            pitcher: "P1",
        }),
        ev(Spec {
            seq: 3,
            ty: MlbEventType::Single,
            inning: 1,
            half: HalfInning::Top,
            outs_b: 1,
            outs_a: 0,
            score_b: score(0, 0),
            score_a: score(0, 0),
            run_b: occ(None, None, None),
            run_a: occ(Some("B2"), None, None),
            desc: "illegal outs drop",
            balls: 0,
            strikes: 0,
            status: GameStatus::InProgress,
            amends: None,
            batter: "B2",
            pitcher: "P1",
        }),
    ]
}

pub fn illegal_score_drop() -> Vec<CanonicalMlbEvent> {
    vec![
        start(),
        ev(Spec {
            seq: 2,
            ty: MlbEventType::HomeRun,
            inning: 1,
            half: HalfInning::Top,
            outs_b: 0,
            outs_a: 0,
            score_b: score(0, 0),
            score_a: score(0, 1),
            run_b: occ(None, None, None),
            run_a: occ(None, None, None),
            desc: "hr",
            balls: 0,
            strikes: 0,
            status: GameStatus::InProgress,
            amends: None,
            batter: "B1",
            pitcher: "P1",
        }),
        ev(Spec {
            seq: 3,
            ty: MlbEventType::Single,
            inning: 1,
            half: HalfInning::Top,
            outs_b: 0,
            outs_a: 0,
            score_b: score(0, 1),
            score_a: score(0, 0),
            run_b: occ(None, None, None),
            run_a: occ(Some("B2"), None, None),
            desc: "illegal score drop",
            balls: 0,
            strikes: 0,
            status: GameStatus::InProgress,
            amends: None,
            batter: "B2",
            pitcher: "P1",
        }),
    ]
}

pub fn no_lookahead_game() -> (Vec<CanonicalMlbEvent>, crate::outcome::GameOutcome) {
    let events = vec![
        start(),
        ev(Spec {
            seq: 2,
            ty: MlbEventType::Single,
            inning: 1,
            half: HalfInning::Top,
            outs_b: 0,
            outs_a: 0,
            score_b: score(0, 0),
            score_a: score(0, 0),
            run_b: occ(None, None, None),
            run_a: occ(Some("B1"), None, None),
            desc: "single",
            balls: 0,
            strikes: 0,
            status: GameStatus::InProgress,
            amends: None,
            batter: "B1",
            pitcher: "P1",
        }),
        ev(Spec {
            seq: 3,
            ty: MlbEventType::HomeRun,
            inning: 1,
            half: HalfInning::Top,
            outs_b: 0,
            outs_a: 0,
            score_b: score(0, 0),
            score_a: score(0, 2),
            run_b: occ(Some("B1"), None, None),
            run_a: occ(None, None, None),
            desc: "hr",
            balls: 0,
            strikes: 0,
            status: GameStatus::InProgress,
            amends: None,
            batter: "B2",
            pitcher: "P1",
        }),
    ];
    let outcome = crate::outcome::GameOutcome::from_final_score(
        events[0].game_id.clone(),
        score(3, 2),
        SOURCE,
    );
    (events, outcome)
}

pub fn statsapi_envelope_json() -> String {
    serde_json::json!({
        "envelope_version": "W2.RAW.1.0.0",
        "fixture_kind": "SYNTHETIC_TEST_FIXTURE",
        "source": "mlb_statsapi_live_feed_v1",
        "source_game_id": "900001",
        "retrieved_at": "2026-08-26T00:00:00Z",
        "payload": {
            "gameData": {
                "game": { "pk": 900001 },
                "datetime": { "officialDate": "2026-06-18" },
                "teams": {
                    "home": { "id": 147, "abbreviation": "NYY" },
                    "away": { "id": 111, "abbreviation": "BOS" }
                },
                "venue": { "id": 1, "name": "SYNTHETIC_TEST_FIXTURE" }
            },
            "liveData": {
                "plays": {
                    "allPlays": [{
                        "playId": "syn-play-1",
                        "result": {
                            "eventType": "strikeout",
                            "event": "Strikeout",
                            "description": "SYNTHETIC_TEST_FIXTURE strikeout",
                            "homeScore": 0,
                            "awayScore": 0
                        },
                        "about": {
                            "inning": 1,
                            "halfInning": "top",
                            "hasReview": false,
                            "startTime": "2026-06-18T18:05:00Z"
                        },
                        "count": { "balls": 2, "strikes": 3, "outs": 1 },
                        "matchup": {
                            "batter": { "id": 101 },
                            "pitcher": { "id": 201 }
                        },
                        "runners": []
                    }]
                }
            }
        }
    })
    .to_string()
}

/// Same synthetic StatsAPI envelope with a duplicated `playId` (duplicate-handling fixture).
pub fn statsapi_envelope_duplicate_play_json() -> String {
    let mut v: serde_json::Value =
        serde_json::from_str(&statsapi_envelope_json()).expect("synthetic envelope json");
    let plays = v
        .pointer_mut("/payload/liveData/plays/allPlays")
        .and_then(|p| p.as_array_mut())
        .expect("allPlays array");
    let first = plays.first().cloned().expect("at least one play");
    plays.push(first);
    v.to_string()
}
