//! W2 engine tests: schema, state, replay, determinism, no-lookahead, fixtures.

use momento_research_event::adapter::{EventStateAdapter, MlbEventAdapter};
use momento_research_event::event::{FixtureKind, GameStatus, HalfInning, MlbEventType};
use momento_research_event::identity::{CanonicalGameId, IdentityRegistry, OfficialMlbGameRef};
use momento_research_event::ingest::{ingest_bytes, map_event_type};
use momento_research_event::outcome::Winner;
use momento_research_event::replay::{
    assert_no_future_leakage, causal_prefix, replay_is_deterministic, restore_state,
    timeline_fingerprint, validate_game,
};
use momento_research_event::sequence::PbpSequence;
use momento_research_event::source::{discover_local_pbp, source_contract};
use momento_research_event::state::{MlbGameState, apply, replay};
use momento_research_event::synthetic;
use momento_research_event::w1_bridge::w1_stub_is_unmapped;
use momento_research_event::{ObservabilityKind, SCHEMA_VERSION};

use chrono::NaiveDate;
use momento_research_data::foundation::IdentityStubV1;

#[test]
fn production_fence_no_live_deps() {
    let toml = include_str!("../Cargo.toml");
    assert!(!toml.contains("momento-risk"));
    assert!(!toml.contains("momento-execution"));
    assert!(!toml.contains("momento-strategy-mlb"));
}

#[test]
fn source_contract_no_auto_sub() {
    assert!(!source_contract().automatic_substitution);
}

#[test]
fn fixtures_are_labeled_synthetic() {
    for e in synthetic::catalog_play_types_valid() {
        assert_eq!(e.provenance.fixture_kind, FixtureKind::SyntheticTestFixture);
        assert!(e.event_description.as_value().is_some());
    }
}

#[test]
fn catalog_replays() {
    let events = synthetic::catalog_play_types_valid();
    let trs = replay(&events).expect("catalog replay");
    assert_eq!(trs.len(), events.len());
    assert!(trs.iter().any(|t| t.trigger == MlbEventType::Walk));
    assert!(trs.iter().any(|t| t.trigger == MlbEventType::Strikeout));
    assert!(trs.iter().any(|t| t.trigger == MlbEventType::Single));
    assert!(trs.iter().any(|t| t.trigger == MlbEventType::Double));
    assert!(trs.iter().any(|t| t.trigger == MlbEventType::Triple));
    assert!(trs.iter().any(|t| t.trigger == MlbEventType::HomeRun));
    assert!(trs.iter().any(|t| t.trigger == MlbEventType::Sacrifice));
    assert!(trs.iter().any(|t| t.trigger == MlbEventType::DoublePlay));
    assert!(trs.iter().any(|t| t.trigger == MlbEventType::Error));
    assert!(
        trs.iter()
            .any(|t| t.trigger == MlbEventType::PitchingChange)
    );
    assert!(trs.iter().any(|t| t.trigger == MlbEventType::BattingChange));
    assert!(trs.iter().any(|t| t.trigger == MlbEventType::Review));
    assert!(trs.iter().any(|t| t.trigger == MlbEventType::InningEnd));
    assert!(trs.iter().any(|t| t.trigger == MlbEventType::StolenBase));
}

#[test]
fn determinism() {
    let events = synthetic::catalog_play_types_valid();
    assert!(replay_is_deterministic(&events).unwrap());
    let a = timeline_fingerprint(&events).unwrap();
    let b = timeline_fingerprint(&events).unwrap();
    assert_eq!(a, b);
}

#[test]
fn serialize_round_trip() {
    let events = synthetic::catalog_play_types_valid();
    let json = serde_json::to_string(&events).unwrap();
    let back: Vec<momento_research_event::CanonicalMlbEvent> = serde_json::from_str(&json).unwrap();
    assert_eq!(events, back);
}

#[test]
fn state_restore() {
    let events = synthetic::catalog_play_types_valid();
    let trs = replay(&events).unwrap();
    let mid = restore_state(&trs, 3).unwrap();
    assert_eq!(mid.state_seq, 3);
}

#[test]
fn amendment_allows_outs_decrease() {
    let trs = replay(&synthetic::amendment_review_outs()).unwrap();
    assert_eq!(trs.last().unwrap().after.outs, 0);
}

#[test]
fn walkoff_apply() {
    let mut state = MlbGameState::pre_game(
        CanonicalGameId::from_official_source("SYNTHETIC_TEST_FIXTURE", "synthetic-001").unwrap(),
    );
    state.state_seq = 2;
    state.inning = 9;
    state.half = HalfInning::Bottom;
    state.outs = 0;
    state.score = momento_research_event::event::Score { home: 3, away: 3 };
    state.game_status = GameStatus::InProgress;
    let ev = synthetic::walkoff_bottom_ninth()
        .into_iter()
        .find(|e| e.event_type == MlbEventType::WalkOff)
        .unwrap();
    let mut walkoff = ev;
    walkoff.sequence = 3;
    walkoff.canonical_order = 3;
    let tr = apply(&state, &walkoff).expect("walkoff");
    assert_eq!(tr.after.game_status, GameStatus::Final);
    assert_eq!(tr.after.score.home, 4);
}

#[test]
fn extra_inning_walkoff_apply() {
    let mut state = MlbGameState::pre_game(
        CanonicalGameId::from_official_source("SYNTHETIC_TEST_FIXTURE", "synthetic-001").unwrap(),
    );
    state.state_seq = 2;
    state.inning = 10;
    state.half = HalfInning::Bottom;
    state.outs = 1;
    state.score = momento_research_event::event::Score { home: 2, away: 2 };
    state.extra_inning = true;
    state.game_status = GameStatus::InProgress;
    let ev = synthetic::extra_inning_walkoff()
        .into_iter()
        .find(|e| e.event_type == MlbEventType::WalkOff)
        .unwrap();
    let mut walkoff = ev;
    walkoff.sequence = 3;
    let tr = apply(&state, &walkoff).unwrap();
    assert!(tr.after.extra_inning);
    assert_eq!(tr.after.game_status, GameStatus::Final);
}

#[test]
fn invalid_transitions_fail_loud() {
    assert!(replay(&synthetic::strikeout_then_illegal_outs_drop()).is_err());
    assert!(replay(&synthetic::illegal_score_drop()).is_err());
}

#[test]
fn no_future_leakage() {
    let (events, outcome) = synthetic::no_lookahead_game();
    assert_eq!(outcome.winner, Winner::Home);
    assert_ne!(
        replay(&events).unwrap().last().unwrap().after.score,
        outcome.final_score
    );
    assert_no_future_leakage(&events, 2, &outcome).unwrap();
    let prefix = causal_prefix(&events, 2);
    let state = replay(&prefix).unwrap().last().unwrap().after.clone();
    let dump = serde_json::to_string(&state).unwrap();
    assert!(!dump.contains("winner"));
    assert!(!dump.contains(&format!("{:?}", outcome.final_score)));
    assert_eq!(state.game_status, GameStatus::InProgress);
    assert_eq!(state.score.away, 0);
}

#[test]
fn event_time_no_theta_formula() {
    let events = synthetic::catalog_play_types_valid();
    let trs = replay(&events).unwrap();
    let adapter = MlbEventAdapter;
    let rem = adapter.remaining_opportunities(&trs.last().unwrap().after);
    assert_eq!(rem.unit, "outs");
    assert_eq!(rem.regulation_budget, 54);
    let et = adapter.event_time(&trs[1].after, &events[1]);
    assert_eq!(et.event_theta.status, "ESTIMATOR_DEFERRED_W9");
    assert!(et.event_theta.inputs.theta_value.is_unavailable());
    assert!(
        et.actual_outs_remaining.is_unavailable() || trs[1].after.game_status == GameStatus::Final
    );
}

#[test]
fn sequence_views() {
    let seq = PbpSequence::new(
        synthetic::catalog_play_types_valid()[0].game_id.clone(),
        synthetic::catalog_play_types_valid(),
    );
    assert!(!seq.last_n_events(3).is_empty());
    assert!(!seq.last_n_plate_appearances(3).is_empty());
    assert!(!seq.last_n_scoring(2).is_empty());
    assert_eq!(
        seq.last_n_pitching_changes(1)[0].event_type,
        MlbEventType::PitchingChange
    );
    assert_eq!(seq.last_n_reviews(1)[0].event_type, MlbEventType::Review);
    assert!(!seq.event_type_transitions().is_empty());
    assert!(!seq.scoring_bursts().is_empty());
}

#[test]
fn statsapi_parser() {
    let json = synthetic::statsapi_envelope_json();
    let (events, report, official) =
        ingest_bytes("memory://synthetic.json", json.as_bytes()).unwrap();
    assert_eq!(report.fixture_kind, FixtureKind::SyntheticTestFixture);
    assert_eq!(official.game_pk, "900001");
    assert!(
        events
            .iter()
            .any(|e| e.event_type == MlbEventType::Strikeout)
    );
    replay(&events).expect("parsed synthetic statsapi");
}

#[test]
fn malformed_pbp() {
    let err = ingest_bytes("memory://bad.json", b"{not json").unwrap_err();
    assert!(matches!(
        err,
        momento_research_event::EventError::Malformed(_)
            | momento_research_event::EventError::Serde(_)
    ));
}

#[test]
fn w1_identity_unmapped() {
    let s = IdentityStubV1::unmapped("g", "m", "t", "e", "KXMLBGAME");
    assert!(w1_stub_is_unmapped(&s));
}

#[test]
fn identity_no_invented_map() {
    let mut reg = IdentityRegistry::new();
    let official = OfficialMlbGameRef {
        source: "mlb_statsapi".into(),
        game_pk: "1".into(),
        season: momento_research_event::identity::DataYear(2026),
        official_date: NaiveDate::from_ymd_opt(2026, 6, 18).unwrap(),
        home_team: momento_research_event::identity::SourceRef {
            source: "mlb_statsapi".into(),
            source_id: "147".into(),
        },
        away_team: momento_research_event::identity::SourceRef {
            source: "mlb_statsapi".into(),
            source_id: "111".into(),
        },
        venue: None,
        game_number: 1,
        competition: "MLB".into(),
        home_abbreviation: "NYY".into(),
        away_abbreviation: "BOS".into(),
    };
    let id = reg.register_official(official).unwrap();
    assert!(reg.get(&id).unwrap().kalshi.is_none());
}

#[test]
fn observability_kind_is_w1() {
    let _ = ObservabilityKind::Unavailable;
    assert_eq!(SCHEMA_VERSION, "W2.EVENT.1.1.0");
}

#[test]
fn ingest_duplicate_source_event_is_recorded_not_replayed_twice() {
    let json = synthetic::statsapi_envelope_duplicate_play_json();
    let (events, report, _) = ingest_bytes("memory://dup.json", json.as_bytes()).unwrap();
    assert!(
        report.duplicates.iter().any(|d| d == "syn-play-1"),
        "duplicate playId must be reported"
    );
    let n = events
        .iter()
        .filter(|e| e.source_event_id == "syn-play-1")
        .count();
    assert_eq!(n, 1);
}

#[test]
fn statsapi_play_timestamp_is_pbp_official_not_trade_created() {
    let json = synthetic::statsapi_envelope_json();
    let (events, _, _) = ingest_bytes("memory://ts.json", json.as_bytes()).unwrap();
    let play = events
        .iter()
        .find(|e| e.source_event_id == "syn-play-1")
        .expect("play");
    assert_eq!(
        play.source_timestamp_kind,
        momento_research_event::w1_bridge::MlbTimestampKind::PbpOfficial
    );
    assert_eq!(
        momento_research_event::w1_bridge::w1_kind_for_mlb(play.source_timestamp_kind),
        momento_research_data::foundation::SourceTimestampKind::Unknown
    );
}

#[test]
fn kalshi_unmapped_id_is_never_rewritten_to_fake_mlb_pk() {
    let ident = IdentityRegistry::kalshi_only_unmapped(
        "KXMLBGAME-26JUN18NYYBOS",
        "KXMLBGAME-26JUN18NYYBOS-NYY",
    );
    assert!(ident.canonical_game_id.as_str().starts_with("kalshi:"));
    let k = ident.kalshi.expect("alias");
    assert!(k.mlb_game_pk.is_none());
    assert_eq!(
        k.starting_price_class,
        momento_research_data::foundation::StartingPriceClass::StartingPriceUnverified
    );
}

#[test]
fn in_progress_state_does_not_know_actual_remaining_outs_or_settlement() {
    let (events, outcome) = synthetic::no_lookahead_game();
    let prefix = causal_prefix(&events, 2);
    let state = replay(&prefix).unwrap().last().unwrap().after.clone();
    let adapter = MlbEventAdapter;
    let et = adapter.event_time(&state, &prefix[1]);
    assert!(et.actual_outs_remaining.is_unavailable());
    let dump = serde_json::to_string(&state).unwrap();
    assert!(!dump.contains("settlement"));
    assert!(!dump.contains("winner"));
    assert_ne!(state.score, outcome.final_score);
    assert_eq!(state.game_status, GameStatus::InProgress);
}

#[test]
fn w2_does_not_define_w5_state_transition_or_fork_w1_identity() {
    let state_src = include_str!("../src/state.rs");
    assert!(!state_src.contains("pub struct StateTransition"));
    assert!(state_src.contains("pub struct MlbPbpTransition"));
    let bridge = include_str!("../src/w1_bridge.rs");
    assert!(!bridge.contains("pub struct RawMarketIdentity {"));
    assert!(!bridge.contains("pub struct RawArtifactRef {"));
    assert!(bridge.contains("pub use momento_research_data::foundation"));
}

#[test]
fn schema_has_pbp_transitions_not_w5_canonical_table() {
    let sql = momento_research_event::schema_sql::SCHEMA_SQL;
    assert!(sql.contains("mlb_pbp_transitions"));
    assert!(sql.contains("mlb_market_refs"));
    assert!(!sql.contains("CREATE TABLE mlb_state_transitions"));
    assert!(!sql.contains("CREATE TABLE mlb_game_market_episodes"));
}

#[test]
fn coverage_does_not_claim_2025_pbp() {
    let root = std::path::Path::new("Backtesting Suite/Data-Real");
    if !root.exists() {
        return;
    }
    let report = momento_research_event::coverage::report_from_lake(root);
    assert!(report.mlb_2025.contains("MISSING_HISTORICAL_SOURCE"));
    assert!(report.rows.iter().filter(|r| r.season == "2025").all(|r| {
        !matches!(
            r.pbp_available,
            momento_research_event::coverage::CoverageStatus::Available
        )
    }));
}

#[test]
fn schema_sql_has_keys() {
    assert!(momento_research_event::schema_sql::SCHEMA_SQL.contains("PRIMARY KEY"));
    assert!(momento_research_event::schema_sql::SCHEMA_SQL.contains("mlb_canonical_events"));
    assert!(
        momento_research_event::schema_sql::INTENDED_QUERIES.contains("regulation_outs_remaining")
    );
}

#[test]
fn map_event_types() {
    assert_eq!(map_event_type("home_run"), MlbEventType::HomeRun);
    assert_eq!(map_event_type("walk_off"), MlbEventType::WalkOff);
    assert_eq!(map_event_type("field_out"), MlbEventType::FieldOut);
}

#[test]
fn inning_change_after_three_outs_replays() {
    let trs = replay(&synthetic::inning_change_after_three_outs()).expect("inning change");
    assert_eq!(trs.last().unwrap().after.half, HalfInning::Bottom);
    assert_eq!(trs.last().unwrap().after.outs, 1);
}

#[test]
fn validation_summary() {
    let v = validate_game(&synthetic::catalog_play_types_valid(), None);
    assert!(v.valid);
    assert_eq!(v.parser_version, momento_research_event::PARSER_VERSION);
}

#[test]
fn runner_writes_outside_lake() {
    let tmp = tempfile::tempdir().unwrap();
    let cfg = momento_research_event::W2RunConfig {
        lake_root: std::path::PathBuf::from("Backtesting Suite/Data-Real"),
        out_dir: tmp.path().join("w2-out"),
        generated_at: chrono::Utc.with_ymd_and_hms(2026, 8, 26, 7, 0, 0).unwrap(),
    };
    let result = momento_research_event::run_w2_event_reconstruction(&cfg).expect("run");
    assert_eq!(result.google_status, "GOOGLE_PUBLISH_PENDING");
    assert!(!result.historical_pbp_available);
    assert!(cfg.out_dir.join("w2_coverage.csv").exists());
    assert!(cfg.out_dir.join("sheets_w2_index.csv").exists());
    assert!(result.synthetic_validations_ok);
    assert_eq!(result.ledger_blocked_steps, 0);
    assert!(result.ledger_complete_steps >= 90);
}

#[test]
fn local_pbp_discovery_empty() {
    let d = discover_local_pbp(&[std::path::PathBuf::from("crates/research-event/src")]);
    assert!(!d.historical_pbp_available);
}

use chrono::TimeZone;
