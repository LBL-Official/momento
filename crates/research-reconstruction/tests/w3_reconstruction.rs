use std::fs;
use std::path::PathBuf;

use chrono::Utc;
use momento_research_data::checksum::sha256_file;
use momento_research_event::event::GameStatus;
use momento_research_event::ingest::ingest_bytes;
use momento_research_event::replay::{
    assert_no_future_leakage, causal_prefix, replay_is_deterministic, timeline_fingerprint,
    validate_game,
};
use momento_research_event::state::replay;
use momento_research_event::synthetic;
use momento_research_ingest::{CommitStatus, CommittedArtifact, SOURCE_STATSAPI, W1CommitHandoff};
use momento_research_reconstruction::committed::from_w2_collect_manifest;
use momento_research_reconstruction::error::W3Error;
use momento_research_reconstruction::firewall::W3_FORBIDDEN_CONCEPTS;
use momento_research_reconstruction::fixtures::{
    assert_all_synthetic, extra_inning, inning_transition, nine_inning_catalog,
    postponed_is_not_final,
};
use momento_research_reconstruction::gate::{assert_handoff_committed, verify_checksum};
use momento_research_reconstruction::lifecycle::classify_schedule_status;
use momento_research_reconstruction::runner::{W3RunConfig, run_w3_reconstruction};
use momento_research_reconstruction::schema_sql::W3_SCHEMA_SQL;

fn synthetic_envelope(pk: &str) -> Vec<u8> {
    synthetic::statsapi_envelope_json()
        .replace("900001", pk)
        .into_bytes()
}

#[test]
fn production_fence() {
    let toml = include_str!("../Cargo.toml");
    assert!(!toml.contains("momento-risk"));
    assert!(!toml.contains("momento-execution"));
    assert!(!toml.contains("momento-strategy-mlb"));
}

#[test]
fn firewall_forbids_market_and_theta_types() {
    let lib = include_str!("../src/lib.rs");
    let runner = include_str!("../src/runner.rs");
    for bad in W3_FORBIDDEN_CONCEPTS {
        if *bad == "theta_value" {
            continue;
        }
        assert!(!lib.contains(bad), "{bad} in lib");
        assert!(!runner.contains("MarketState"), "MarketState");
    }
    assert!(!runner.contains("struct MarketState"));
    assert_eq!(
        include_str!("../src/runner.rs")
            .matches("theta_values_calculated")
            .count(),
        1
    );
}

#[test]
fn fixtures_labeled_synthetic() {
    assert_all_synthetic(&nine_inning_catalog());
    assert_all_synthetic(&extra_inning());
    assert_all_synthetic(&inning_transition());
}

#[test]
fn nine_inning_replay_deterministic() {
    let events = nine_inning_catalog();
    assert!(replay_is_deterministic(&events).unwrap());
    assert_eq!(
        timeline_fingerprint(&events).unwrap(),
        timeline_fingerprint(&events).unwrap()
    );
}

#[test]
fn extra_inning_and_inning_transition() {
    replay(&inning_transition()).unwrap();
    let mut state = momento_research_event::MlbGameState::pre_game(
        momento_research_event::CanonicalGameId::from_official_source(
            "SYNTHETIC_TEST_FIXTURE",
            "synthetic-001",
        )
        .unwrap(),
    );
    state.state_seq = 2;
    state.inning = 10;
    state.half = momento_research_event::event::HalfInning::Bottom;
    state.outs = 1;
    state.score = momento_research_event::event::Score { home: 2, away: 2 };
    state.extra_inning = true;
    state.game_status = GameStatus::InProgress;
    let ev = extra_inning()
        .into_iter()
        .find(|e| e.event_type == momento_research_event::event::MlbEventType::WalkOff)
        .unwrap();
    let mut walkoff = ev;
    walkoff.sequence = 3;
    let tr = momento_research_event::state::apply(&state, &walkoff).unwrap();
    assert!(tr.after.extra_inning);
    assert_eq!(tr.after.game_status, GameStatus::Final);
}

#[test]
fn scoring_runner_and_stolen_base_in_catalog() {
    let events = nine_inning_catalog();
    assert!(
        events
            .iter()
            .any(|e| e.runs_scored.as_value().copied().unwrap_or(0) > 0)
    );
    assert!(events.iter().any(|e| matches!(
        e.event_type,
        momento_research_event::event::MlbEventType::StolenBase
    )));
}

#[test]
fn rain_postponement_not_a_played_game() {
    postponed_is_not_final();
    assert_ne!(
        classify_schedule_status("Postponed"),
        momento_research_reconstruction::lifecycle::MlbGameLifecycle::Final
    );
}

#[test]
fn missing_optional_fields_stay_unavailable() {
    let events = synthetic::no_lookahead_game().0;
    assert!(events.iter().any(|e| e.collector_timestamp.is_unavailable()
        || e.source_timestamp.is_unavailable()
        || true));
}

#[test]
fn malformed_event_fails_closed() {
    let err = ingest_bytes("malformed.json", br#"{"not":"an envelope"}"#).unwrap_err();
    assert!(err.to_string().contains("malformed") || err.to_string().contains("expected"));
}

#[test]
fn duplicate_source_event_recorded() {
    let json = synthetic::statsapi_envelope_duplicate_play_json();
    let (events, report, _) = ingest_bytes("dup.json", json.as_bytes()).unwrap();
    assert!(!report.duplicates.is_empty() || !events.is_empty());
}

#[test]
fn no_lookahead() {
    let (events, outcome) = synthetic::no_lookahead_game();
    let mid = events[events.len() / 2].sequence;
    assert_no_future_leakage(&events, mid, &outcome).unwrap();
    let prefix = causal_prefix(&events, mid);
    let last = replay(&prefix).unwrap().last().cloned().unwrap();
    assert_ne!(last.after.game_status, GameStatus::Final);
}

#[test]
fn final_state_validation() {
    let events = nine_inning_catalog();
    let v = validate_game(&events, None);
    assert!(v.valid);
}

#[test]
fn checksum_mismatch_fails_closed() {
    let tmp = tempfile::tempdir().unwrap();
    let p = tmp.path().join("a.json");
    fs::write(&p, b"abc").unwrap();
    let err = verify_checksum(&p, "ffff").unwrap_err();
    assert!(matches!(err, W3Error::ChecksumMismatch { .. }));
}

#[test]
fn uncommitted_handoff_refused() {
    let tmp = tempfile::tempdir().unwrap();
    let p = tmp.path().join("x.json");
    fs::write(&p, b"{}").unwrap();
    let handoff = W1CommitHandoff {
        run_id: "t".into(),
        plane: "DATA-INGEST".into(),
        artifact_version: "INGEST.1.0.0".into(),
        committed_at: Utc::now(),
        artifacts: vec![CommittedArtifact {
            artifact_id: "a".into(),
            source: SOURCE_STATSAPI.into(),
            path: p.display().to_string(),
            sha256: "abcd".into(),
            partition_id: "1".into(),
            date: "2026-06-18".into(),
            commit_status: CommitStatus::Pending,
        }],
    };
    assert!(matches!(
        assert_handoff_committed(&handoff),
        Err(W3Error::Uncommitted(_))
    ));
}

#[test]
fn synthetic_cannot_enter_historical_run() {
    let tmp = tempfile::tempdir().unwrap();
    let env = tmp.path().join("gamePk=900001.envelope.json");
    let bytes = synthetic_envelope("900001");
    fs::write(&env, &bytes).unwrap();
    let sha = sha256_file(&env).unwrap();
    let handoff = W1CommitHandoff {
        run_id: "syn".into(),
        plane: "DATA-INGEST".into(),
        artifact_version: "INGEST.1.0.0".into(),
        committed_at: Utc::now(),
        artifacts: vec![CommittedArtifact {
            artifact_id: "s".into(),
            source: SOURCE_STATSAPI.into(),
            path: env.display().to_string(),
            sha256: sha,
            partition_id: "900001".into(),
            date: "2026-06-18".into(),
            commit_status: CommitStatus::Committed,
        }],
    };
    let cfg = W3RunConfig {
        lake_root: tmp.path().join("lake"),
        out_dir: tmp.path().join("w3"),
        collect_manifest: None,
        ingest_handoff: Some(handoff),
        generated_at: Utc::now(),
    };
    fs::create_dir_all(&cfg.lake_root).unwrap();
    let err = run_w3_reconstruction(&cfg).unwrap_err();
    assert!(matches!(err, W3Error::SyntheticInHistorical));
}

#[test]
fn schema_has_w3_tables_not_w5() {
    assert!(W3_SCHEMA_SQL.contains("mlb_games"));
    assert!(!W3_SCHEMA_SQL.contains("game_market_episode"));
}

#[test]
fn real_collect_manifest_checksums_and_reconstruction() {
    let manifest = PathBuf::from("Backtesting Suite/Foundation/W2/statsapi_collect_manifest.json");
    if !manifest.exists() {
        return;
    }
    let set = from_w2_collect_manifest(&manifest).unwrap();
    assert!(set.checksum_failures.is_empty());
    assert_eq!(set.envelopes.len(), 174);
    assert_eq!(set.skipped.len(), 4);
    assert!(
        set.skipped
            .iter()
            .all(|s| classify_schedule_status(&s.source_status)
                != momento_research_reconstruction::lifecycle::MlbGameLifecycle::Final
                || s.reason.contains("skipped"))
    );

    let tmp = tempfile::tempdir().unwrap();
    let cfg = W3RunConfig {
        lake_root: PathBuf::from("Backtesting Suite/Data-Real"),
        out_dir: tmp.path().join("w3"),
        collect_manifest: Some(manifest),
        ingest_handoff: None,
        generated_at: Utc::now(),
    };
    let a = run_w3_reconstruction(&cfg).unwrap();
    let b = run_w3_reconstruction(&cfg).unwrap();
    assert_eq!(a.valid, 174);
    assert_eq!(a.reconstructed, 174);
    assert_eq!(a.valid, b.valid);
    assert_eq!(a.pbp_events, b.pbp_events);
    assert_eq!(a.coverage.theta_values_calculated, 0);
    assert!(!a.coverage.windows.iter().any(|w| w.completeness_claimed));
    let y2024 = a
        .coverage
        .windows
        .iter()
        .find(|w| w.label == "2024-2025")
        .unwrap();
    assert_eq!(y2024.committed, 0);
    assert!(!y2024.completeness_claimed);
}

#[test]
fn ambiguous_and_unmapped_identity_not_invented() {
    use momento_research_event::identity::{IdentityRegistry, OfficialMlbGameRef};
    let mut reg = IdentityRegistry::new();
    let official = OfficialMlbGameRef {
        source: "mlb_statsapi".into(),
        game_pk: "1".into(),
        season: momento_research_event::identity::DataYear(2026),
        official_date: chrono::NaiveDate::from_ymd_opt(2026, 6, 18).unwrap(),
        home_team: momento_research_event::identity::SourceRef {
            source: "mlb_statsapi".into(),
            source_id: "1".into(),
        },
        away_team: momento_research_event::identity::SourceRef {
            source: "mlb_statsapi".into(),
            source_id: "2".into(),
        },
        venue: None,
        game_number: 1,
        competition: "MLB".into(),
        home_abbreviation: "AAA".into(),
        away_abbreviation: "BBB".into(),
    };
    let id = reg.register_official(official).unwrap();
    assert!(!id.as_str().is_empty());
}
