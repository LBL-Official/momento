use std::collections::BTreeMap;
use std::fs;

use chrono::{NaiveDate, Utc};
use momento_research_data::manifest::{CompletenessStatus, DailyManifest};
use momento_research_data::paths::ResearchPaths;
use momento_research_data::sport::{ResearchSeason, ResearchSport};
use momento_research_ingest::commit::commit_artifacts;
use momento_research_ingest::error::IngestError;
use momento_research_ingest::lock::IngestLock;
use momento_research_ingest::paths::{IngestPaths, sha256_bytes};
use momento_research_ingest::source::{DiscoveredPartition, FetchOutcome, FixtureSource};
use momento_research_ingest::types::{
    CommitStatus, CommittedArtifact, DateWindow, IngestPlan, PartitionStatus, RunStatus,
    SOURCE_STATSAPI, W1CommitHandoff,
};
use momento_research_ingest::w2_gate::canonicalize_committed;
use momento_research_ingest::{replay_run, run_ingest};
use serde_json::json;

fn date() -> NaiveDate {
    NaiveDate::from_ymd_opt(2026, 6, 18).unwrap()
}

fn window() -> DateWindow {
    DateWindow {
        label: "test".into(),
        start: date(),
        end: date(),
    }
}

fn part(pk: &str) -> DiscoveredPartition {
    DiscoveredPartition {
        source: SOURCE_STATSAPI.into(),
        date: date(),
        partition_id: pk.into(),
        status_hint: "Final".into(),
        home_abbreviation: "AAA".into(),
        away_abbreviation: "BBB".into(),
        game_number: 1,
    }
}

fn envelope(pk: &str, extra: &str) -> Vec<u8> {
    let pk_n: i64 = pk.parse().unwrap();
    serde_json::to_vec(&json!({
        "envelope_version": "W2.RAW.1.0.0",
        "fixture_kind": "SYNTHETIC_TEST_FIXTURE",
        "source": "mlb_statsapi",
        "source_game_id": pk,
        "payload": {
            "gameData": {
                "game": {"pk": pk_n, "gameNumber": 1},
                "datetime": {"officialDate": "2026-06-18"},
                "teams": {
                    "home": {"id": 1, "abbreviation": "AAA"},
                    "away": {"id": 2, "abbreviation": extra}
                },
                "status": {"detailedState": "Final", "abstractGameState": "Final"}
            },
            "liveData": {"plays": {"allPlays": []}}
        }
    }))
    .unwrap()
}

fn plan(tmp: &tempfile::TempDir) -> IngestPlan {
    let mut p = IngestPlan::test_defaults(tmp.path().join("lake"), tmp.path().join("ingest"));
    p.generated_at = Utc::now();
    p.pbp_windows = vec![window()];
    p.kalshi_catalog = false;
    p
}

fn source_one(pk: &str, bytes: Vec<u8>) -> FixtureSource {
    let mut fetches = BTreeMap::new();
    fetches.insert(pk.to_string(), FetchOutcome::Bytes(bytes));
    FixtureSource {
        partitions: vec![part(pk)],
        fetches,
    }
}

#[test]
fn idempotent_same_bytes_no_overwrite() {
    let tmp = tempfile::tempdir().unwrap();
    let bytes = envelope("1001", "BBB");
    let expected = sha256_bytes(&bytes);
    let src = source_one("1001", bytes.clone());
    let p = plan(&tmp);
    let a = run_ingest(&p, &src).unwrap();
    let b = run_ingest(&p, &src).unwrap();
    let row_a = a
        .coverage
        .iter()
        .find(|r| r.partition_id == "1001")
        .unwrap();
    let row_b = b
        .coverage
        .iter()
        .find(|r| r.partition_id == "1001")
        .unwrap();
    assert_eq!(row_a.sha256.as_deref(), Some(expected.as_str()));
    assert_eq!(row_b.status, PartitionStatus::AlreadyKnown);
    assert_eq!(row_a.sha256, row_b.sha256);
    let dest = IngestPaths::new(tmp.path().join("ingest")).landing_game(date(), "1001");
    assert_eq!(sha256_bytes(&fs::read(&dest).unwrap()), expected);
}

#[test]
fn checksum_preserved_on_disk() {
    let tmp = tempfile::tempdir().unwrap();
    let bytes = envelope("1002", "CCC");
    let expected = sha256_bytes(&bytes);
    let src = source_one("1002", bytes);
    let report = run_ingest(&plan(&tmp), &src).unwrap();
    let dest = IngestPaths::new(tmp.path().join("ingest")).landing_game(date(), "1002");
    assert_eq!(sha256_bytes(&fs::read(dest).unwrap()), expected);
    assert_eq!(report.handoff.artifacts[0].sha256, expected);
}

#[test]
fn partial_failure_commits_only_success() {
    let tmp = tempfile::tempdir().unwrap();
    let mut fetches = BTreeMap::new();
    fetches.insert("2001".into(), FetchOutcome::Bytes(envelope("2001", "DDD")));
    fetches.insert("2002".into(), FetchOutcome::Failure("boom".into()));
    let src = FixtureSource {
        partitions: vec![part("2001"), part("2002")],
        fetches,
    };
    let report = run_ingest(&plan(&tmp), &src).unwrap();
    assert_eq!(report.status, RunStatus::CompleteWithGaps);
    assert_eq!(report.handoff.artifacts.len(), 1);
    assert_eq!(report.handoff.artifacts[0].partition_id, "2001");
    let failed = report
        .coverage
        .iter()
        .find(|r| r.partition_id == "2002")
        .unwrap();
    assert_eq!(failed.status, PartitionStatus::Failed);
}

#[test]
fn duplicate_runs_are_idempotent() {
    let tmp = tempfile::tempdir().unwrap();
    let src = source_one("3001", envelope("3001", "EEE"));
    let first = run_ingest(&plan(&tmp), &src).unwrap();
    let second = run_ingest(&plan(&tmp), &src).unwrap();
    assert_eq!(
        first.handoff.artifacts[0].sha256,
        second.handoff.artifacts[0].sha256
    );
    assert_eq!(
        second
            .coverage
            .iter()
            .find(|r| r.partition_id == "3001")
            .unwrap()
            .status,
        PartitionStatus::AlreadyKnown
    );
}

#[test]
fn missing_dates_are_unavailable_not_complete() {
    let tmp = tempfile::tempdir().unwrap();
    let mut p = plan(&tmp);
    p.pbp_windows = vec![DateWindow {
        label: "two-days".into(),
        start: date(),
        end: date().succ_opt().unwrap(),
    }];
    let src = source_one("4001", envelope("4001", "FFF"));
    let report = run_ingest(&p, &src).unwrap();
    let missing = report
        .coverage
        .iter()
        .find(|r| r.partition_id == date().succ_opt().unwrap().to_string())
        .unwrap();
    assert_eq!(missing.status, PartitionStatus::Unavailable);
    assert_ne!(missing.status, PartitionStatus::Complete);
}

#[test]
fn source_failure_does_not_retry_forever() {
    let tmp = tempfile::tempdir().unwrap();
    let mut fetches = BTreeMap::new();
    fetches.insert("5001".into(), FetchOutcome::Failure("down".into()));
    let src = FixtureSource {
        partitions: vec![part("5001")],
        fetches,
    };
    let mut p = plan(&tmp);
    p.max_retries = 0;
    let report = run_ingest(&p, &src).unwrap();
    assert_eq!(report.coverage[0].status, PartitionStatus::Failed);
    assert!(report.handoff.artifacts.is_empty());
    assert_eq!(report.status, RunStatus::Failed);
}

#[test]
fn w2_refuses_uncommitted_w1_artifact() {
    let tmp = tempfile::tempdir().unwrap();
    let path = tmp.path().join("pending.json");
    fs::write(&path, b"{}").unwrap();
    let handoff = W1CommitHandoff {
        run_id: "ingest-test".into(),
        plane: "DATA-INGEST".into(),
        artifact_version: "INGEST.1.0.0".into(),
        committed_at: Utc::now(),
        artifacts: vec![CommittedArtifact {
            artifact_id: "x".into(),
            source: SOURCE_STATSAPI.into(),
            path: path.display().to_string(),
            sha256: "deadbeef".into(),
            partition_id: "1".into(),
            date: date().to_string(),
            commit_status: CommitStatus::Pending,
        }],
    };
    let err = canonicalize_committed(&handoff, tmp.path()).unwrap_err();
    assert!(matches!(err, IngestError::UncommittedW1(_)));
}

#[test]
fn w2_consumes_committed_checksum_verified_artifact() {
    let tmp = tempfile::tempdir().unwrap();
    let src = source_one("6001", envelope("6001", "GGG"));
    let report = run_ingest(&plan(&tmp), &src).unwrap();
    assert_eq!(
        report.handoff.artifacts[0].commit_status,
        CommitStatus::Committed
    );
    assert_eq!(report.w2_games_attempted, 1);
    let replay = replay_run(std::path::Path::new(
        &IngestPaths::new(tmp.path().join("ingest")).run_dir(&report.run_id),
    ))
    .unwrap();
    assert_eq!(replay.run_id, report.run_id);
}

#[test]
fn concurrent_lock_fail_closed() {
    let tmp = tempfile::tempdir().unwrap();
    let paths = IngestPaths::new(tmp.path().join("ingest"));
    let _held = IngestLock::acquire(paths.lock_path()).unwrap();
    let src = source_one("7001", envelope("7001", "HHH"));
    let err = run_ingest(&plan(&tmp), &src).unwrap_err();
    assert!(matches!(err, IngestError::ConcurrentWriter(_)));
}

#[test]
fn different_bytes_new_version_no_overwrite() {
    let tmp = tempfile::tempdir().unwrap();
    let p = plan(&tmp);
    let first = source_one("8001", envelope("8001", "III"));
    run_ingest(&p, &first).unwrap();
    let second = source_one("8001", envelope("8001", "JJJ"));
    let report = run_ingest(&p, &second).unwrap();
    assert_eq!(report.coverage[0].status, PartitionStatus::VersionConflict);
    let orig = IngestPaths::new(tmp.path().join("ingest")).landing_game(date(), "8001");
    assert_eq!(
        sha256_bytes(&fs::read(&orig).unwrap()),
        sha256_bytes(&envelope("8001", "III"))
    );
}

#[test]
fn kalshi_missing_manifest_is_not_complete() {
    let tmp = tempfile::tempdir().unwrap();
    let lake = tmp.path().join("lake");
    let paths = ResearchPaths {
        root: lake.clone(),
        season: ResearchSeason {
            label: "2025-2026".into(),
        },
    };
    let mut missing = DailyManifest::new(ResearchSport::Mlb, &paths.season, date());
    missing.completeness_status = CompletenessStatus::Missing;
    missing.write_atomic(&paths, ResearchSport::Mlb).unwrap();
    let mut complete = DailyManifest::new(
        ResearchSport::Mlb,
        &paths.season,
        date().succ_opt().unwrap(),
    );
    complete.completeness_status = CompletenessStatus::Complete;
    complete.markets_discovered = 2;
    complete.markets_collected = 2;
    complete.write_atomic(&paths, ResearchSport::Mlb).unwrap();

    let mut p = IngestPlan::test_defaults(lake, tmp.path().join("ingest"));
    p.kalshi_catalog = true;
    p.pbp_windows.clear();
    let src = FixtureSource::default();
    let report = run_ingest(&p, &src).unwrap();
    let miss = report
        .coverage
        .iter()
        .find(|r| r.date == date().to_string())
        .unwrap();
    assert_eq!(miss.status, PartitionStatus::Unavailable);
    let ok = report
        .coverage
        .iter()
        .find(|r| r.date == date().succ_opt().unwrap().to_string())
        .unwrap();
    assert_eq!(ok.status, PartitionStatus::Complete);
}

#[test]
fn refuse_ingest_root_inside_lake() {
    let tmp = tempfile::tempdir().unwrap();
    let lake = tmp.path().join("lake");
    fs::create_dir_all(&lake).unwrap();
    let mut p = plan(&tmp);
    p.lake_root = lake.clone();
    p.ingest_root = lake.join("nested");
    let err = run_ingest(&p, &FixtureSource::default()).unwrap_err();
    assert!(matches!(err, IngestError::LakeWriteForbidden(_)));
}

#[test]
fn commit_rejects_checksum_mismatch() {
    let tmp = tempfile::tempdir().unwrap();
    let path = tmp.path().join("a.json");
    fs::write(&path, b"abc").unwrap();
    let err = commit_artifacts(
        "run",
        Utc::now(),
        vec![CommittedArtifact {
            artifact_id: "a".into(),
            source: SOURCE_STATSAPI.into(),
            path: path.display().to_string(),
            sha256: "ffff".into(),
            partition_id: "1".into(),
            date: date().to_string(),
            commit_status: CommitStatus::Pending,
        }],
    )
    .unwrap_err();
    assert!(matches!(err, IngestError::ChecksumMismatch { .. }));
}

#[test]
fn historical_windows_partition_and_execute_unavailable_without_network() {
    let tmp = tempfile::tempdir().unwrap();
    let as_of = NaiveDate::from_ymd_opt(2026, 8, 26).unwrap();
    let mut p = IngestPlan::test_defaults(tmp.path().join("lake"), tmp.path().join("ingest"));
    p.generated_at = Utc::now();
    p.pbp_windows = DateWindow::required_mlb_windows(as_of);
    p.fill_unlisted_dates = false;
    p.invoke_w2 = false;
    p.kalshi_catalog = false;
    p.execution_mode = momento_research_ingest::types::ExecutionMode::HistoricalBackfill;
    let report = run_ingest(&p, &FixtureSource::default()).unwrap();
    assert!(!report.backfill_complete);
    assert!(!report.network_ready);
    assert!(report.code_ready);
    assert_eq!(report.window_coverage.len(), 3);
    for w in &report.window_coverage {
        assert_eq!(
            w.status,
            momento_research_ingest::types::WindowStatus::Unavailable
        );
        assert!(!w.completeness_claimed);
    }
}

#[test]
fn forward_window_idempotent_and_overlap_finds_late_data() {
    let tmp = tempfile::tempdir().unwrap();
    let mut p = plan(&tmp);
    p.persist_watermarks = true;
    p.overlap_days = 3;
    p.kalshi_catalog = false;
    let src = source_one("9001", envelope("9001", "KKK"));
    let first = run_ingest(&p, &src).unwrap();
    assert_eq!(
        first.watermark_state.mlb_pbp_acquisition.as_deref(),
        Some("2026-06-18")
    );
    let mut fetches = BTreeMap::new();
    fetches.insert("9001".into(), FetchOutcome::Bytes(envelope("9001", "KKK")));
    fetches.insert("9002".into(), FetchOutcome::Bytes(envelope("9002", "LLL")));
    let late = FixtureSource {
        partitions: vec![part("9001"), part("9002")],
        fetches,
    };
    p.generated_at = Utc::now();
    let second = run_ingest(&p, &late).unwrap();
    let late_row = second
        .coverage
        .iter()
        .find(|r| r.partition_id == "9002")
        .unwrap();
    assert_eq!(late_row.status, PartitionStatus::Complete);
    assert_eq!(
        second
            .coverage
            .iter()
            .find(|r| r.partition_id == "9001")
            .unwrap()
            .status,
        PartitionStatus::AlreadyKnown
    );
}

#[test]
fn watermark_does_not_advance_after_failure() {
    let tmp = tempfile::tempdir().unwrap();
    let mut fetches = BTreeMap::new();
    fetches.insert("9101".into(), FetchOutcome::Bytes(envelope("9101", "MMM")));
    fetches.insert("9102".into(), FetchOutcome::Failure("down".into()));
    let src = FixtureSource {
        partitions: vec![part("9101"), part("9102")],
        fetches,
    };
    let mut p = plan(&tmp);
    p.max_retries = 0;
    let report = run_ingest(&p, &src).unwrap();
    assert_eq!(report.status, RunStatus::CompleteWithGaps);
    assert_eq!(report.watermark_state.mlb_pbp_acquisition.as_deref(), None);
}

#[test]
fn watermark_contiguous_success_then_failure() {
    let tmp = tempfile::tempdir().unwrap();
    let d2 = date().succ_opt().unwrap();
    let mut fetches = BTreeMap::new();
    fetches.insert("9201".into(), FetchOutcome::Bytes(envelope("9201", "NNN")));
    fetches.insert("9202".into(), FetchOutcome::Failure("down".into()));
    let mut p2 = part("9202");
    p2.date = d2;
    let src = FixtureSource {
        partitions: vec![part("9201"), p2],
        fetches,
    };
    let mut p = plan(&tmp);
    p.pbp_windows = vec![DateWindow {
        label: "two".into(),
        start: date(),
        end: d2,
    }];
    p.fill_unlisted_dates = false;
    p.max_retries = 0;
    let report = run_ingest(&p, &src).unwrap();
    assert_eq!(
        report.watermark_state.mlb_pbp_acquisition.as_deref(),
        Some("2026-06-18")
    );
}

#[test]
fn bounded_retry_exhaustion_is_failed() {
    let tmp = tempfile::tempdir().unwrap();
    let mut fetches = BTreeMap::new();
    fetches.insert("9301".into(), FetchOutcome::Failure("down".into()));
    let src = FixtureSource {
        partitions: vec![part("9301")],
        fetches,
    };
    let mut p = plan(&tmp);
    p.max_retries = 2;
    let report = run_ingest(&p, &src).unwrap();
    assert_eq!(report.coverage[0].status, PartitionStatus::Failed);
    assert!(
        report.coverage[0].notes.contains("retries exhausted")
            || report.coverage[0].notes.contains("down")
    );
}

#[test]
fn kalshi_discovery_never_invents_ticker_and_keeps_unmatched() {
    use momento_research_ingest::kalshi::{DiscoveredMarket, FixtureKalshiSource};
    use momento_research_ingest::orchestrator::run_ingest_with_sources;
    use momento_research_ingest::types::IdentityMapping;
    let tmp = tempfile::tempdir().unwrap();
    let mut p = plan(&tmp);
    p.kalshi_catalog = false;
    p.kalshi_discover = true;
    p.invoke_w2 = false;
    let mut artifacts = BTreeMap::new();
    artifacts.insert(
        "KXMLBGAME-26JUN18NYYBOS-NYY".into(),
        FetchOutcome::Bytes(br#"{"ticker":"KXMLBGAME-26JUN18NYYBOS-NYY"}"#.to_vec()),
    );
    let kalshi = FixtureKalshiSource {
        markets: vec![DiscoveredMarket {
            date: date(),
            ticker: "KXMLBGAME-26JUN18NYYBOS-NYY".into(),
            event_ticker: Some("KXMLBGAME-26JUN18NYYBOS".into()),
            series: Some("KXMLBGAME".into()),
            mapping: IdentityMapping::Unmatched,
            observed_game_pk: None,
            completeness: None,
            notes: String::new(),
            open_time: None,
            close_time: None,
            result: None,
            settlement_ts: None,
            settlement_value_dollars: None,
            status: None,
        }],
        artifacts,
    };
    let report = run_ingest_with_sources(&p, &FixtureSource::default(), &kalshi).unwrap();
    let id = report
        .identity_report
        .iter()
        .find(|r| r.ticker.contains("NYY"))
        .unwrap();
    assert_eq!(id.mapping, IdentityMapping::Unmatched);
    assert!(id.observed_game_pk.is_none());
    assert_eq!(
        report
            .coverage
            .iter()
            .find(|r| r.partition_id.contains("NYY"))
            .unwrap()
            .status,
        PartitionStatus::Unmatched
    );
}

#[test]
fn kalshi_ambiguous_stays_ambiguous() {
    use momento_research_ingest::kalshi::{DiscoveredMarket, FixtureKalshiSource};
    use momento_research_ingest::orchestrator::run_ingest_with_sources;
    use momento_research_ingest::types::IdentityMapping;
    let tmp = tempfile::tempdir().unwrap();
    let mut p = plan(&tmp);
    p.kalshi_catalog = false;
    p.kalshi_discover = true;
    p.invoke_w2 = false;
    let mut artifacts = BTreeMap::new();
    artifacts.insert(
        "KXMLBGAME-DH".into(),
        FetchOutcome::Bytes(br#"{"ticker":"KXMLBGAME-DH"}"#.to_vec()),
    );
    let kalshi = FixtureKalshiSource {
        markets: vec![DiscoveredMarket {
            date: date(),
            ticker: "KXMLBGAME-DH".into(),
            event_ticker: None,
            series: Some("KXMLBGAME".into()),
            mapping: IdentityMapping::Ambiguous,
            observed_game_pk: None,
            completeness: None,
            notes: "doubleheader".into(),
            open_time: None,
            close_time: None,
            result: None,
            settlement_ts: None,
            settlement_value_dollars: None,
            status: None,
        }],
        artifacts,
    };
    let report = run_ingest_with_sources(&p, &FixtureSource::default(), &kalshi).unwrap();
    assert_eq!(
        report.identity_report[0].mapping,
        IdentityMapping::Ambiguous
    );
    assert_eq!(
        report
            .coverage
            .iter()
            .find(|r| r.partition_id == "KXMLBGAME-DH")
            .unwrap()
            .status,
        PartitionStatus::Ambiguous
    );
}

#[test]
fn kalshi_same_bytes_already_known_different_version_conflict() {
    use momento_research_ingest::kalshi::{DiscoveredMarket, FixtureKalshiSource};
    use momento_research_ingest::orchestrator::run_ingest_with_sources;
    use momento_research_ingest::types::IdentityMapping;
    let tmp = tempfile::tempdir().unwrap();
    let mut p = plan(&tmp);
    p.kalshi_catalog = false;
    p.kalshi_discover = true;
    p.fetch_kalshi_artifacts = true;
    p.invoke_w2 = false;
    let market = DiscoveredMarket {
        date: date(),
        ticker: "KXMLBGAME-X-NYY".into(),
        event_ticker: None,
        series: Some("KXMLBGAME".into()),
        mapping: IdentityMapping::Unmatched,
        observed_game_pk: None,
        completeness: None,
        notes: String::new(),
        open_time: None,
        close_time: None,
        result: None,
        settlement_ts: None,
        settlement_value_dollars: None,
        status: None,
    };
    let mut artifacts = BTreeMap::new();
    artifacts.insert(
        "KXMLBGAME-X-NYY".into(),
        FetchOutcome::Bytes(br#"{"ticker":"KXMLBGAME-X-NYY","v":1}"#.to_vec()),
    );
    let kalshi = FixtureKalshiSource {
        markets: vec![market.clone()],
        artifacts: artifacts.clone(),
    };
    run_ingest_with_sources(&p, &FixtureSource::default(), &kalshi).unwrap();
    let again = run_ingest_with_sources(&p, &FixtureSource::default(), &kalshi).unwrap();
    assert_eq!(
        again
            .coverage
            .iter()
            .find(|r| r.partition_id == "KXMLBGAME-X-NYY")
            .unwrap()
            .status,
        PartitionStatus::AlreadyKnown
    );
    artifacts.insert(
        "KXMLBGAME-X-NYY".into(),
        FetchOutcome::Bytes(br#"{"ticker":"KXMLBGAME-X-NYY","v":2}"#.to_vec()),
    );
    let changed = FixtureKalshiSource {
        markets: vec![market],
        artifacts,
    };
    let conflict = run_ingest_with_sources(&p, &FixtureSource::default(), &changed).unwrap();
    assert_eq!(
        conflict
            .coverage
            .iter()
            .find(|r| r.partition_id == "KXMLBGAME-X-NYY")
            .unwrap()
            .status,
        PartitionStatus::VersionConflict
    );
}

#[test]
fn skip_existing_lands_candle_sidecar_without_rewriting_envelope() {
    use momento_research_ingest::kalshi::{
        DiscoveredMarket, KalshiDiscoverySource, landed_candles_observed,
    };
    use momento_research_ingest::orchestrator::run_ingest_with_sources;
    use momento_research_ingest::types::IdentityMapping;

    struct CandleOnlySource {
        market: DiscoveredMarket,
        candles: FetchOutcome,
    }
    impl KalshiDiscoverySource for CandleOnlySource {
        fn discover(&self, window: &DateWindow) -> Result<Vec<DiscoveredMarket>, IngestError> {
            Ok(if window.contains(self.market.date) {
                vec![self.market.clone()]
            } else {
                vec![]
            })
        }
        fn fetch_artifact(&self, _market: &DiscoveredMarket) -> Result<FetchOutcome, IngestError> {
            Err(IngestError::SourceFailure(
                "fetch_artifact must not run when trades sidecar exists".into(),
            ))
        }
        fn fetch_candlesticks(
            &self,
            _market: &DiscoveredMarket,
        ) -> Result<Option<FetchOutcome>, IngestError> {
            Ok(Some(self.candles.clone()))
        }
    }

    let tmp = tempfile::tempdir().unwrap();
    let mut p = plan(&tmp);
    p.kalshi_catalog = false;
    p.kalshi_discover = true;
    p.fetch_kalshi_artifacts = true;
    p.skip_existing = true;
    p.invoke_w2 = false;
    let market = DiscoveredMarket {
        date: date(),
        ticker: "KXMLBGAME-X-NYY".into(),
        event_ticker: None,
        series: Some("KXMLBGAME".into()),
        mapping: IdentityMapping::Unmatched,
        observed_game_pk: None,
        completeness: None,
        notes: String::new(),
        open_time: None,
        close_time: None,
        result: None,
        settlement_ts: None,
        settlement_value_dollars: None,
        status: None,
    };
    let paths = IngestPaths::new(&p.ingest_root);
    let dest = paths.landing_kalshi_discovery(market.date, &market.ticker);
    fs::create_dir_all(dest.parent().unwrap()).unwrap();
    fs::write(
        &dest,
        br#"{"envelope_version":"INGEST.KALSHI.DISCOVERY.1.0.0","payload":{"completeness":"TRADES_ONLY","trades_status":"OBSERVED_HISTORICAL","candles_status":"UNAVAILABLE"},"ticker":"KXMLBGAME-X-NYY"}"#,
    )
    .unwrap();
    let original = fs::read(&dest).unwrap();
    let trades = paths.landing_kalshi_matched_trades(market.date, &market.ticker);
    fs::create_dir_all(trades.parent().unwrap()).unwrap();
    fs::write(
        &trades,
        br#"{"trades_status":"OBSERVED_HISTORICAL","canonical_trade_count":1,"trades":[{"ticker":"KXMLBGAME-X-NYY"}]}"#,
    )
    .unwrap();
    let kalshi = CandleOnlySource {
        market: market.clone(),
        candles: FetchOutcome::Bytes(
            br#"{"candles_status":"OBSERVED_HISTORICAL","candlesticks":[{"end_period_ts":1,"yes_bid":{"open":"0.5300","high":"0.5300","low":"0.5300","close":"0.5300"},"volume":"1.00"}]}"#.to_vec(),
        ),
    };
    let report = run_ingest_with_sources(&p, &FixtureSource::default(), &kalshi).unwrap();
    assert_eq!(fs::read(&dest).unwrap(), original);
    assert!(landed_candles_observed(&paths, &market));
    let settled = paths.landing_kalshi_settlement(market.date, &market.ticker);
    assert!(
        settled.is_file(),
        "skip_existing still lands catalog settlement"
    );
    assert_eq!(
        report
            .coverage
            .iter()
            .find(|r| r.partition_id == "KXMLBGAME-X-NYY")
            .unwrap()
            .status,
        PartitionStatus::Complete
    );
}

#[test]
fn w1_w2_raw_and_production_roots_rejected() {
    use momento_research_ingest::error::IngestError;
    let tmp = tempfile::tempdir().unwrap();
    let lake = tmp.path().join("lake");
    fs::create_dir_all(&lake).unwrap();
    let w1 = tmp.path().join("Foundation").join("W1");
    fs::create_dir_all(&w1).unwrap();
    let mut p = plan(&tmp);
    p.lake_root = lake;
    p.ingest_root = w1.clone();
    p.forbidden_write_roots = vec![w1];
    let err = run_ingest(&p, &FixtureSource::default()).unwrap_err();
    assert!(matches!(
        err,
        IngestError::PathForbidden { .. } | IngestError::LakeWriteForbidden(_)
    ));
}

#[test]
fn unimplemented_sports_do_not_fabricate_partitions() {
    use momento_research_ingest::adapter::nba_stub;
    use momento_research_ingest::source::PartitionSource;
    let listed = nba_stub().list_partitions(&window()).unwrap();
    assert!(listed.is_empty());
}

#[test]
fn committed_handoff_is_w2_w3_consumable() {
    let tmp = tempfile::tempdir().unwrap();
    let src = source_one("9401", envelope("9401", "OOO"));
    let report = run_ingest(&plan(&tmp), &src).unwrap();
    momento_research_ingest::w2_gate::assert_w2_may_consume(&report.handoff).unwrap();
    assert!(report.handoff.statsapi_committed().count() >= 1);
}

#[test]
fn observed_gamepk_comes_from_source_partition_id() {
    let tmp = tempfile::tempdir().unwrap();
    let src = source_one("747123", envelope("747123", "PPP"));
    let report = run_ingest(&plan(&tmp), &src).unwrap();
    assert_eq!(report.handoff.artifacts[0].partition_id, "747123");
}

#[test]
fn completeness_is_read_from_payload_not_inferred_as_l2() {
    use momento_research_ingest::kalshi::completeness_from_payload;
    use momento_research_ingest::types::MarketCompleteness;
    let payload = serde_json::json!({
        "completeness": "TRADES_ONLY",
        "l2": "HISTORICAL_L2_UNAVAILABLE",
        "candle_count": 12
    });
    assert_eq!(
        completeness_from_payload(&payload),
        Some(MarketCompleteness::TradesOnly)
    );
    assert_ne!(
        completeness_from_payload(&payload),
        Some(MarketCompleteness::L2Complete)
    );
}

fn matched_pair(ticker: &str, pk: &str) -> momento_research_ingest::types::GameMarketPair {
    use momento_research_ingest::types::{GameMarketPair, IdentityMapping};
    GameMarketPair {
        game_pk: Some(pk.into()),
        official_date: "2025-07-15".into(),
        event_ticker: Some("KXMLBGAME-25JUL15AAABBB".into()),
        ticker: ticker.into(),
        mapping: IdentityMapping::Mapped,
        completeness: None,
        notes: "MAPPED via unique observed abbr suffix; gamePk OBSERVED from StatsAPI".into(),
    }
}

fn unmatched_pair(ticker: &str) -> momento_research_ingest::types::GameMarketPair {
    use momento_research_ingest::types::{GameMarketPair, IdentityMapping};
    GameMarketPair {
        game_pk: None,
        official_date: "2025-07-15".into(),
        event_ticker: Some("KXMLBGAME-25JUL15AAABBB".into()),
        ticker: ticker.into(),
        mapping: IdentityMapping::Unmatched,
        completeness: None,
        notes: "UNMATCHED".into(),
    }
}

fn fixture_trade(id: &str, ticker: &str, ts: &str, px: &str) -> serde_json::Value {
    json!({
        "trade_id": id,
        "ticker": ticker,
        "created_time": ts,
        "yes_price_dollars": px,
        "count_fp": "1.00"
    })
}

#[test]
fn matched_trade_backfill_preserves_identity_and_is_idempotent() {
    use std::path::PathBuf;

    use chrono::{TimeZone, Utc};
    use momento_research_ingest::matched_trades::{
        FixtureMatchedTradeSource, MatchedTradeFetch, dollar_string_is_exact_cents,
        run_matched_trade_backfill,
    };
    use momento_research_ingest::paths::{IngestPaths, sha256_file};

    assert!(dollar_string_is_exact_cents("0.8000").is_ok());
    assert_eq!(
        dollar_string_is_exact_cents("0.8010"),
        Err("finer_than_cents")
    );

    let tmp = tempfile::tempdir().unwrap();
    let lake = tmp.path().join("lake");
    let ingest = tmp.path().join("ingest");
    fs::create_dir_all(&lake).unwrap();
    let ticker = "KXMLBGAME-25JUL15AAABBB-AAA";
    let unmatched_ticker = "KXMLBGAME-25JUL15AAABBB-ZZZ";
    let mut by_ticker = BTreeMap::new();
    by_ticker.insert(
        ticker.to_string(),
        MatchedTradeFetch {
            status: "OBSERVED_HISTORICAL".into(),
            trades: vec![
                fixture_trade("t1", ticker, "2025-07-15T19:00:00Z", "0.8000"),
                fixture_trade("t1", ticker, "2025-07-15T19:00:00Z", "0.8000"),
                fixture_trade("t2", ticker, "2025-07-15T20:00:00Z", "0.8100"),
                fixture_trade(
                    "bad-ticker",
                    "OTHER-TICKER",
                    "2025-07-15T21:00:00Z",
                    "0.8900",
                ),
                json!({
                    "trade_id": "no-time",
                    "ticker": ticker,
                    "yes_price_dollars": "0.8000",
                    "count_fp": "1.00"
                }),
                fixture_trade("fine", ticker, "2025-07-15T21:30:00Z", "0.8010"),
            ],
            notes: String::new(),
        },
    );
    by_ticker.insert(
        unmatched_ticker.to_string(),
        MatchedTradeFetch {
            status: "OBSERVED_HISTORICAL".into(),
            trades: vec![fixture_trade(
                "u1",
                unmatched_ticker,
                "2025-07-15T19:00:00Z",
                "0.8000",
            )],
            notes: String::new(),
        },
    );
    let source = FixtureMatchedTradeSource { by_ticker };
    let pairs = vec![
        matched_pair(ticker, "718001"),
        unmatched_pair(unmatched_ticker),
    ];
    let generated = Utc.with_ymd_and_hms(2026, 8, 26, 19, 0, 0).unwrap();
    let forbidden: Vec<PathBuf> = vec![];
    let report = run_matched_trade_backfill(
        &ingest, &lake, &forbidden, &pairs, &source, generated, false, None,
    )
    .unwrap();
    assert_eq!(report.matched_attempted, 1);
    assert_eq!(report.landed_with_trades, 1);
    assert_eq!(report.canonical_trade_observations, 2);
    assert_eq!(report.duplicate_source_events_dropped, 1);
    assert_eq!(report.unmappable, 1);
    assert!(report.malformed >= 2);
    assert!(
        report
            .quarantine
            .iter()
            .any(|q| q.code == "UNMAPPABLE_TICKER")
    );
    assert!(
        report
            .quarantine
            .iter()
            .any(|q| q.code == "PRECISION_FINER_THAN_CENTS")
    );
    assert!(
        report
            .quarantine
            .iter()
            .any(|q| q.code == "MALFORMED_MISSING_TIME")
    );

    let dest = IngestPaths::new(&ingest).landing_kalshi_matched_trades(
        chrono::NaiveDate::from_ymd_opt(2025, 7, 15).unwrap(),
        ticker,
    );
    assert!(dest.exists());
    let landed: serde_json::Value = serde_json::from_slice(&fs::read(&dest).unwrap()).unwrap();
    assert_eq!(landed["game_pk"], "718001");
    assert_eq!(landed["ticker"], ticker);
    assert_eq!(landed["identity_mapping"], "MAPPED");
    assert_eq!(landed["canonical_trade_count"], 2);
    let sha1 = sha256_file(&dest).unwrap();

    let report2 = run_matched_trade_backfill(
        &ingest, &lake, &forbidden, &pairs, &source, generated, true, None,
    )
    .unwrap();
    assert_eq!(report2.skipped_existing, 1);
    assert_eq!(report2.landed_with_trades, 1);
    assert_eq!(report2.canonical_trade_observations, 2);
    assert_eq!(sha256_file(&dest).unwrap(), sha1);

    let unmatched_dest = IngestPaths::new(&ingest).landing_kalshi_matched_trades(
        chrono::NaiveDate::from_ymd_opt(2025, 7, 15).unwrap(),
        unmatched_ticker,
    );
    assert!(!unmatched_dest.exists());
}

#[test]
fn matched_trade_backfill_refuses_lake_write() {
    use momento_research_ingest::matched_trades::{
        FixtureMatchedTradeSource, run_matched_trade_backfill,
    };

    let tmp = tempfile::tempdir().unwrap();
    let lake = tmp.path().join("lake");
    fs::create_dir_all(&lake).unwrap();
    let err = run_matched_trade_backfill(
        &lake,
        &lake,
        &[],
        &[matched_pair("KXMLBGAME-25JUL15AAABBB-AAA", "1")],
        &FixtureMatchedTradeSource::default(),
        Utc::now(),
        false,
        None,
    )
    .unwrap_err();
    assert!(matches!(err, IngestError::LakeWriteForbidden(_)));
}

#[test]
fn matched_empty_fetch_is_metadata_only_sidecar() {
    use momento_research_ingest::matched_trades::{
        FixtureMatchedTradeSource, MatchedTradeFetch, run_matched_trade_backfill,
    };
    use momento_research_ingest::paths::IngestPaths;

    let tmp = tempfile::tempdir().unwrap();
    let lake = tmp.path().join("lake");
    let ingest = tmp.path().join("ingest");
    fs::create_dir_all(&lake).unwrap();
    let ticker = "KXMLBGAME-25JUL15AAABBB-AAA";
    let mut by_ticker = BTreeMap::new();
    by_ticker.insert(
        ticker.to_string(),
        MatchedTradeFetch {
            status: "OBSERVED_HISTORICAL".into(),
            trades: vec![],
            notes: String::new(),
        },
    );
    let report = run_matched_trade_backfill(
        &ingest,
        &lake,
        &[],
        &[matched_pair(ticker, "718001")],
        &FixtureMatchedTradeSource { by_ticker },
        Utc::now(),
        false,
        None,
    )
    .unwrap();
    assert_eq!(report.landed_with_trades, 0);
    assert_eq!(report.landed_empty, 1);
    assert_eq!(report.canonical_trade_observations, 0);
    let dest = IngestPaths::new(&ingest).landing_kalshi_matched_trades(
        chrono::NaiveDate::from_ymd_opt(2025, 7, 15).unwrap(),
        ticker,
    );
    let landed: serde_json::Value = serde_json::from_slice(&fs::read(dest).unwrap()).unwrap();
    assert_eq!(landed["canonical_trade_count"], 0);
}
