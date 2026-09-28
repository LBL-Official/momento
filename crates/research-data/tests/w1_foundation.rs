//! Waterfall 1 foundation tests. Isolated from live trading.

use chrono::{TimeZone, Utc};
use momento_kalshi::{game_id_for_event_ticker, market_id_for_ticker};
use momento_research_data::foundation::IdentityStubV1;
use momento_research_data::foundation::{
    CoverageRecord, DimensionStatus, LakeWriteGuard, OBSERVABILITY_CONTRACT, ObservabilityKind,
    PartitionCoverage, SourceTimestampKind, W1_STEPS, W1RunConfig, assert_lake_class_honest,
    catalog_demo_manifest_slice, envelope_from_v1, run_w1_foundation,
};
use momento_research_data::{
    CompletenessStatus, DailyManifest, RawMarketEvent, ResearchPaths, ResearchSeason, ResearchSport,
};
use tempfile::tempdir;

#[test]
fn production_fence_research_data_toml() {
    let manifest = include_str!("../Cargo.toml");
    assert!(!manifest.contains("momento-execution"));
    assert!(!manifest.contains("momento-risk"));
    assert!(!manifest.contains("momento-strategy-mlb"));
    assert!(!manifest.contains("trading-engine"));
}

#[test]
fn w1_ledger_ids_are_namespaced_not_plan_ids() {
    assert!(!W1_STEPS.is_empty());
    for spec in W1_STEPS {
        assert!(
            spec.id.starts_with("W1-LEDGER-"),
            "implementation ledger must not collide with PLAN-W1-A*: {}",
            spec.id
        );
        assert!(!spec.id.starts_with("PLAN-"));
    }
}

#[test]
fn observability_never_upgrades_l2_or_pbp() {
    let l2 = OBSERVABILITY_CONTRACT
        .iter()
        .find(|r| r.field == "l2_orderbook")
        .unwrap();
    let pbp = OBSERVABILITY_CONTRACT
        .iter()
        .find(|r| r.field == "pbp")
        .unwrap();
    let start = OBSERVABILITY_CONTRACT
        .iter()
        .find(|r| r.field == "starting_price")
        .unwrap();
    let mid = OBSERVABILITY_CONTRACT
        .iter()
        .find(|r| r.field == "mid")
        .unwrap();
    assert_eq!(l2.kind, ObservabilityKind::L2HistoricalUnavailable);
    assert_eq!(pbp.kind, ObservabilityKind::Unavailable);
    assert_eq!(start.kind, ObservabilityKind::Unavailable);
    assert_eq!(mid.kind, ObservabilityKind::Unavailable);
}

#[test]
fn complete_v1_is_not_lifetime_complete() {
    let rec =
        CoverageRecord::for_kalshi_v1_partition(CompletenessStatus::Complete, 8, 100, 50, 8, 8);
    assert_eq!(rec.partition, PartitionCoverage::PartitionCompleteV1);
    assert_eq!(rec.l2, DimensionStatus::Unavailable);
    assert_eq!(rec.pbp, DimensionStatus::Unavailable);
    assert_eq!(rec.starting_price, DimensionStatus::Unavailable);
    assert_eq!(rec.lifetime_path, DimensionStatus::Unavailable);
    assert_eq!(rec.synchronized_state, DimensionStatus::Unavailable);
    assert_eq!(rec.v1_completeness, CompletenessStatus::Complete);
}

#[test]
fn empty_probe_is_not_fabricated_2025() {
    let rec = CoverageRecord::for_kalshi_v1_partition(CompletenessStatus::Missing, 0, 0, 0, 0, 0);
    assert_eq!(rec.partition, PartitionCoverage::ProbeEmpty);
    assert_eq!(rec.market_discovered, DimensionStatus::Missing);
}

#[test]
fn overwrite_guard_blocks_lake_writes() {
    let dir = tempdir().unwrap();
    let lake = dir.path().join("lake");
    std::fs::create_dir_all(lake.join("MLB")).unwrap();
    let guard = LakeWriteGuard::new(&lake);
    let inside = lake.join("MLB/raw/events.jsonl.gz");
    assert!(guard.assert_not_lake_path(&inside).is_err());
    let outside = dir.path().join("foundation/out.json");
    std::fs::create_dir_all(outside.parent().unwrap()).unwrap();
    std::fs::write(&outside, "{}").unwrap();
    assert!(guard.assert_not_lake_path(&outside).is_ok());
}

#[test]
fn envelope_v2_round_trip_does_not_use_received_at_as_exchange() {
    let v1 = RawMarketEvent {
        received_at: Utc.with_ymd_and_hms(2026, 8, 25, 17, 51, 0).unwrap(),
        source: "rest".into(),
        endpoint: "markets/trades".into(),
        ticker: Some("T".into()),
        payload: serde_json::json!({"created_time":"2026-06-18T01:00:00Z","trade_id":"t1"}),
    };
    let v2 = envelope_from_v1(&v1, "events.jsonl.gz", 9);
    let json = serde_json::to_string(&v2).unwrap();
    let back: momento_research_data::foundation::RawEnvelopeV2 =
        serde_json::from_str(&json).unwrap();
    assert_eq!(
        back.source_timestamp.as_deref(),
        Some("2026-06-18T01:00:00Z")
    );
    assert_eq!(
        back.source_timestamp_kind,
        SourceTimestampKind::TradeCreated
    );
    assert_ne!(
        back.source_timestamp.as_deref(),
        Some(v1.received_at.to_rfc3339().as_str())
    );
}

#[test]
fn w1_job_is_idempotent_on_fixture_lake() {
    let dir = tempdir().unwrap();
    let lake = dir.path().join("Data-Real");
    let out1 = dir.path().join("F1");
    let out2 = dir.path().join("F2");
    seed_empty_probe(&lake);
    let mut cfg = W1RunConfig {
        lake_root: lake.clone(),
        lake_class: "REAL".into(),
        out_dir: out1.clone(),
        season: ResearchSeason::current(),
        generated_at: Utc.with_ymd_and_hms(2026, 8, 26, 8, 0, 0).unwrap(),
        v2_sample_limit: 0,
    };
    let a = run_w1_foundation(&cfg).expect("run a");
    cfg.out_dir = out2.clone();
    cfg.generated_at = Utc.with_ymd_and_hms(2026, 8, 26, 9, 0, 0).unwrap();
    let b = run_w1_foundation(&cfg).expect("run b");
    assert_eq!(a.lake_content_digest, b.lake_content_digest);
    assert_eq!(a.run_id, b.run_id);
    let body_a = std::fs::read_to_string(out1.join("canonical_catalog_body.json")).unwrap();
    let body_b = std::fs::read_to_string(out2.join("canonical_catalog_body.json")).unwrap();
    assert_eq!(body_a, body_b);
    assert!(a.acceptance.no_production_orders_transmitted);
}

#[test]
fn starting_price_is_unverified_not_market_open() {
    let ev = momento_research_data::foundation::StartingPriceEvidence::unverified_from_metadata(
        "T",
        "1",
        "2",
        Some("2026-06-01T00:00:00Z".into()),
    );
    assert_eq!(
        ev.class,
        momento_research_data::foundation::StartingPriceClass::StartingPriceUnverified
    );
    assert!(ev.market_open_price_cents.is_none());
    assert_eq!(ev.observability, ObservabilityKind::Unavailable);
}

#[test]
fn demo_data_path_cannot_be_labeled_real() {
    let dir = tempdir().unwrap();
    let demo = dir.path().join("Backtesting Suite/Data");
    std::fs::create_dir_all(&demo).unwrap();
    assert!(assert_lake_class_honest(&demo, "REAL").is_err());
    assert!(assert_lake_class_honest(&demo, "DEMO").is_ok());
}

#[test]
fn data_real_path_cannot_be_labeled_demo() {
    let dir = tempdir().unwrap();
    let real = dir.path().join("Data-Real");
    std::fs::create_dir_all(&real).unwrap();
    assert!(assert_lake_class_honest(&real, "DEMO").is_err());
    assert!(assert_lake_class_honest(&real, "REAL").is_ok());
}

#[test]
fn identity_stub_matches_live_hash_helpers_and_stays_unmapped() {
    let event_ticker = "KXMLBGAME-26JUN18NYYBOS";
    let ticker = "KXMLBGAME-26JUN18NYYBOS-NYY";
    let stub = IdentityStubV1::unmapped(
        game_id_for_event_ticker(event_ticker).raw().to_string(),
        market_id_for_ticker(ticker).raw().to_string(),
        ticker,
        event_ticker,
        "KXMLBGAME",
    );
    assert_eq!(
        stub.game_id,
        game_id_for_event_ticker(event_ticker).raw().to_string()
    );
    assert_eq!(
        stub.market_id,
        market_id_for_ticker(ticker).raw().to_string()
    );
    assert!(stub.mlb_game_pk.is_none());
    assert_eq!(
        stub.match_status,
        momento_research_data::foundation::IdentityMatchStatus::Unmapped
    );
}

#[test]
fn lake_catalog_v1_fixture_parses() {
    let body = include_str!("../src/foundation/fixtures/lake_catalog_v1.example.json");
    let catalog: momento_research_data::foundation::LakeCatalogV1 =
        serde_json::from_str(body).expect("fixture");
    assert_eq!(catalog.catalog_version, "1.0.0");
    assert_eq!(catalog.lake_class, "REAL");
    assert_eq!(catalog.entries.len(), 1);
    assert!(catalog.market_evidence[0].mlb_game_pk.is_none());
}

#[test]
fn demo_catalog_slice_is_never_real() {
    let dir = tempdir().unwrap();
    let lake = dir.path().join("Backtesting Suite/Data");
    seed_empty_probe(&lake);
    let slice = catalog_demo_manifest_slice(
        &lake,
        &ResearchSeason::current(),
        Utc.with_ymd_and_hms(2026, 8, 26, 8, 0, 0).unwrap(),
    )
    .expect("demo slice");
    assert_eq!(slice.lake_class, "DEMO");
    assert!(
        slice
            .entries
            .iter()
            .all(|e| e.notes.iter().any(|n| n.contains("DEMO")))
    );
    assert!(slice.entries.iter().all(|e| e.coverage_v2.is_none()));
}

#[test]
fn envelope_v2_fixture_round_trips() {
    let body = include_str!("../src/foundation/fixtures/raw_envelope_v2.example.json");
    let env: momento_research_data::foundation::RawEnvelopeV2 =
        serde_json::from_str(body).expect("envelope fixture");
    assert_eq!(env.source_timestamp_kind, SourceTimestampKind::TradeCreated);
    assert!(env.source_timestamp.is_some());
}

#[test]
#[ignore = "writes Backtesting Suite/Foundation/W1/demo_catalog_slice.json"]
fn write_workspace_demo_catalog_slice() {
    let root = std::path::Path::new(env!("CARGO_MANIFEST_DIR")).join("../..");
    let demo = root.join("Backtesting Suite/Data");
    let out = root.join("Backtesting Suite/Foundation/W1/demo_catalog_slice.json");
    if !demo.exists() || !out.parent().unwrap().exists() {
        return;
    }
    let slice = catalog_demo_manifest_slice(
        &demo,
        &ResearchSeason::current(),
        Utc.with_ymd_and_hms(2026, 8, 26, 8, 0, 0).unwrap(),
    )
    .expect("demo slice");
    assert_eq!(slice.lake_class, "DEMO");
    std::fs::write(&out, serde_json::to_string_pretty(&slice).expect("json"))
        .expect("write demo slice");
}

fn seed_empty_probe(lake: &std::path::Path) {
    let mut paths = ResearchPaths::from_env_or_default();
    paths.root = lake.to_path_buf();
    let sport = ResearchSport::Mlb;
    let date = chrono::NaiveDate::from_ymd_opt(2025, 6, 15).unwrap();
    let mut manifest = DailyManifest::new(sport, &ResearchSeason::current(), date);
    manifest.finalize_status();
    manifest.write_atomic(&paths, sport).unwrap();
}
