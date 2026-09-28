use std::fs;
use std::path::PathBuf;

use chrono::{DateTime, Utc};
use momento_research_data::checksum::sha256_file;
use momento_research_data::schema::RawMarketEvent;
use momento_research_ingest::types::{
    CommitStatus, CommittedArtifact, GameMarketPair, IdentityMapping, W1CommitHandoff,
};
use momento_research_market::completeness::{ObservationFlags, classify};
use momento_research_market::couple::couple_paths;
use momento_research_market::error::W4Error;
use momento_research_market::firewall::W4_FORBIDDEN_CONCEPTS;
use momento_research_market::gate::verify_checksum;
use momento_research_market::reader::{
    DiscoveryEnvelope, IdentityIndex, committed_envelopes_for_date, parse_envelope_bytes,
};
use momento_research_market::reconstruct::reconstruct_path;
use momento_research_market::runner::{W4RunConfig, run_w4_reconstruction};
use momento_research_market::types::{
    MarketCompleteness, MarketObservationKind, MarketPoint, MissingSide, assert_event_type_legal,
};
use momento_research_market::{
    GateDecision, MarketIdentityStatus, ResearchCapability, research_gate,
};
use serde_json::json;

fn rfc(s: &str) -> DateTime<Utc> {
    DateTime::parse_from_rfc3339(s).unwrap().with_timezone(&Utc)
}

fn env_value(
    ticker: &str,
    event: &str,
    identity: &str,
    payload: serde_json::Value,
) -> serde_json::Value {
    json!({
        "envelope_version": "1",
        "ticker": ticker,
        "event_ticker": event,
        "identity_mapping": identity,
        "observed_game_pk": null,
        "series": "KXMLBGAME",
        "retrieved_at": "2026-08-26T10:00:00Z",
        "payload": payload
    })
}

fn parse_env(v: serde_json::Value) -> DiscoveryEnvelope {
    parse_envelope_bytes(serde_json::to_vec(&v).unwrap().as_slice()).unwrap()
}

fn empty_identity() -> IdentityIndex {
    IdentityIndex::empty()
}

fn trade(id: &str, t: &str, px: &str) -> serde_json::Value {
    json!({
        "trade_id": id,
        "ticker": "KXMLBGAME-26JUN18TEST-AAA",
        "created_time": t,
        "yes_price_dollars": px,
        "count_fp": "1.00"
    })
}

#[test]
fn production_fence() {
    let toml = include_str!("../Cargo.toml");
    assert!(!toml.contains("momento-risk"));
    assert!(!toml.contains("momento-execution"));
    assert!(!toml.contains("momento-strategy-mlb"));
    assert!(!toml.contains("momento-kalshi"));
}

#[test]
fn firewall_forbids_sync_and_theta() {
    let lib = include_str!("../src/lib.rs");
    let runner = include_str!("../src/runner.rs");
    let types = include_str!("../src/types.rs");
    let price_path = include_str!("../src/price_path.rs");
    let price_paths = include_str!("../src/price_paths.rs");
    for bad in W4_FORBIDDEN_CONCEPTS {
        assert!(!lib.contains(bad), "{bad} in lib");
        assert!(!runner.contains(&format!("struct {bad}")), "{bad} struct");
        assert!(!types.contains(&format!("struct {bad}")));
        assert!(!price_path.contains(&format!("struct {bad}")));
        assert!(!price_paths.contains(&format!("struct {bad}")));
    }
    assert!(!types.contains("struct SynchronizedState"));
    assert!(!runner.contains("struct SynchronizedState"));
    let matched_paths = include_str!("../src/matched_paths.rs");
    assert!(!matched_paths.contains("struct SynchronizedState"));
    assert!(!matched_paths.contains("SynchronizedState"));
}

#[test]
fn types_have_no_f64_money() {
    let types = include_str!("../src/types.rs");
    assert!(!types.contains(": f64"));
    assert!(!types.contains("as f64"));
    let cents = include_str!("../src/cents.rs");
    assert!(!cents.contains("as f64"));
    assert!(!cents.contains(": f64"));
}

#[test]
fn candlestick_plus_l2_snapshot_invalid() {
    assert!(assert_event_type_legal("candlestick").is_ok());
    assert!(assert_event_type_legal("l2_snapshot").is_ok());
    assert!(assert_event_type_legal("candlestick+l2_snapshot").is_err());
}

#[test]
fn metadata_only_does_not_invent_bid() {
    let env = parse_env(env_value(
        "KXMLBGAME-26JUN18TEST-AAA",
        "KXMLBGAME-26JUN18TEST",
        "UNMATCHED",
        json!({
            "ticker": "KXMLBGAME-26JUN18TEST-AAA",
            "event_ticker": "KXMLBGAME-26JUN18TEST",
            "completeness": "MARKET_METADATA_ONLY",
            "trades": [],
            "candlesticks": {"unavailable": true}
        }),
    ));
    let (path, _) = reconstruct_path(&env, &empty_identity(), &[]).unwrap();
    assert_eq!(path.completeness, MarketCompleteness::MarketMetadataOnly);
    assert!(path.points.is_empty());
    assert!(path.points.iter().all(|p| p.yes_bid_cents.is_none()));
}

#[test]
fn unmatched_ticker_still_emits_path() {
    let env = parse_env(env_value(
        "KXMLBGAME-26JUN18TEST-AAA",
        "KXMLBGAME-26JUN18TEST",
        "UNMATCHED",
        json!({"trades": [], "candlesticks": {"unavailable": true}}),
    ));
    let (path, _) = reconstruct_path(&env, &empty_identity(), &[]).unwrap();
    assert_eq!(path.identity, IdentityMapping::Unmatched);
    assert!(path.game_pk.is_none());
}

#[test]
fn ambiguous_identity_preserved() {
    let env = parse_env(env_value(
        "KXMLBGAME-26JUN18TEST-AAA",
        "KXMLBGAME-26JUN18TEST",
        "UNMATCHED",
        json!({"trades": [], "candlesticks": {"unavailable": true}}),
    ));
    let mut idx = IdentityIndex::empty();
    idx.by_ticker.insert(
        "KXMLBGAME-26JUN18TEST-AAA".into(),
        GameMarketPair {
            game_pk: None,
            official_date: "2026-06-18".into(),
            event_ticker: Some("KXMLBGAME-26JUN18TEST".into()),
            ticker: "KXMLBGAME-26JUN18TEST-AAA".into(),
            mapping: IdentityMapping::Ambiguous,
            completeness: None,
            notes: "fixture".into(),
        },
    );
    let (path, _) = reconstruct_path(&env, &idx, &[]).unwrap();
    assert_eq!(path.identity, IdentityMapping::Ambiguous);
}

#[test]
fn trades_path_is_trades_only_even_with_candles() {
    let env = parse_env(env_value(
        "KXMLBGAME-26JUN18TEST-AAA",
        "KXMLBGAME-26JUN18TEST",
        "UNMATCHED",
        json!({
            "trades": [trade("t1", "2026-06-18T20:00:00Z", "0.8000")],
            "candlesticks": {"candlesticks": [{
                "end_period_ts": 1781805600i64,
                "yes_bid": {"open_dollars":"0.7900","high_dollars":"0.7900","low_dollars":"0.7900","close_dollars":"0.7900"},
                "yes_ask": {"open_dollars":"0.8100","high_dollars":"0.8100","low_dollars":"0.8100","close_dollars":"0.8100"},
                "price": {"open_dollars": null, "high_dollars": null, "low_dollars": null, "close_dollars": "0.8000"}
            }]}
        }),
    ));
    let (path, _) = reconstruct_path(&env, &empty_identity(), &[]).unwrap();
    assert_eq!(path.completeness, MarketCompleteness::TradesOnly);
    assert!(
        path.points
            .iter()
            .any(|p| p.kind == MarketObservationKind::Candle1m)
    );
    assert!(
        path.points
            .iter()
            .any(|p| p.kind == MarketObservationKind::Trade)
    );
    let candle = path
        .points
        .iter()
        .find(|p| p.kind == MarketObservationKind::Candle1m)
        .unwrap();
    assert!(candle.candle_ohlc.is_some());
    assert_eq!(candle.candle_ohlc.as_ref().unwrap().yes_bid_close, Some(79));
    assert_eq!(candle.candle_ohlc.as_ref().unwrap().yes_ask_close, Some(81));
    assert!(
        candle.yes_bid_cents.is_none() && candle.yes_ask_cents.is_none(),
        "candle OHLC must not impersonate a quote"
    );
    assert_eq!(
        path.capability.price_path_research,
        momento_research_market::GateDecision::Allowed
    );
    assert_eq!(
        path.capability.orderbook_microstructure,
        momento_research_market::GateDecision::Blocked
    );
}

#[test]
fn candles_only_never_l2() {
    let env = parse_env(env_value(
        "KXMLBGAME-26JUN18TEST-AAA",
        "KXMLBGAME-26JUN18TEST",
        "UNMATCHED",
        json!({
            "trades": [],
            "candlesticks": {"candlesticks": [{
                "end_period_ts": 1781805600i64,
                "yes_bid": {"open_dollars":"0.4600","high_dollars":"0.4600","low_dollars":"0.4600","close_dollars":"0.4600"},
                "yes_ask": {"open_dollars":"0.4700","high_dollars":"0.4700","low_dollars":"0.4700","close_dollars":"0.4700"},
                "price": {"close_dollars": null}
            }]}
        }),
    ));
    let (path, _) = reconstruct_path(&env, &empty_identity(), &[]).unwrap();
    assert_eq!(path.completeness, MarketCompleteness::CandlesOnly);
    assert_ne!(path.completeness, MarketCompleteness::L2Complete);
    assert!(
        path.points
            .iter()
            .all(|p| p.kind == MarketObservationKind::Candle1m)
    );
}

#[test]
fn pit_rest_snapshot_excluded_from_t_game() {
    let env = parse_env(env_value(
        "KXMLBGAME-26JUN18TEST-AAA",
        "KXMLBGAME-26JUN18TEST",
        "UNMATCHED",
        json!({"trades": [], "candlesticks": {"unavailable": true}}),
    ));
    let lake = [RawMarketEvent {
        received_at: rfc("2026-08-25T17:51:20Z"),
        source: "rest".into(),
        endpoint: "markets/orderbook".into(),
        ticker: Some("KXMLBGAME-26JUN18TEST-AAA".into()),
        payload: json!({"orderbook_fp": {"yes_dollars": [["0.50","1.00"]]}}),
    }];
    let (path, _) = reconstruct_path(&env, &empty_identity(), &lake).unwrap();
    assert_eq!(path.ingest_only_pit_count, 1);
    assert!(path.points.is_empty());
    assert!(
        !path
            .points
            .iter()
            .any(|p| p.kind == MarketObservationKind::RestPitSnapshot
                || p.kind == MarketObservationKind::L2Snapshot)
    );
    assert_eq!(path.completeness, MarketCompleteness::MarketMetadataOnly);
}

#[test]
fn one_pit_does_not_classify_l2_complete() {
    let flags = ObservationFlags {
        has_metadata: true,
        has_game_time_l2_snapshot: false,
        ..ObservationFlags::default()
    };
    assert_eq!(classify(&flags), MarketCompleteness::MarketMetadataOnly);
}

#[test]
fn integer_cents_round_trip() {
    let env = parse_env(env_value(
        "KXMLBGAME-26JUN18TEST-AAA",
        "KXMLBGAME-26JUN18TEST",
        "UNMATCHED",
        json!({
            "trades": [trade("t1", "2026-06-18T20:00:00.652611Z", "0.0100")],
            "candlesticks": {"unavailable": true}
        }),
    ));
    let (path, _) = reconstruct_path(&env, &empty_identity(), &[]).unwrap();
    assert_eq!(path.points[0].last_trade_cents, Some(1));
    let bytes = serde_json::to_vec(&path).unwrap();
    let back: momento_research_market::MarketPath = serde_json::from_slice(&bytes).unwrap();
    assert_eq!(back.points[0].last_trade_cents, Some(1));
}

#[test]
fn unsorted_and_duplicate_trades() {
    let env = parse_env(env_value(
        "KXMLBGAME-26JUN18TEST-AAA",
        "KXMLBGAME-26JUN18TEST",
        "UNMATCHED",
        json!({
            "trades": [
                trade("t2", "2026-06-18T21:00:00Z", "0.8200"),
                trade("t1", "2026-06-18T20:00:00Z", "0.8000"),
                trade("t1", "2026-06-18T20:00:00Z", "0.8000")
            ],
            "candlesticks": {"unavailable": true}
        }),
    ));
    let (path, anom) = reconstruct_path(&env, &empty_identity(), &[]).unwrap();
    assert_eq!(path.points.len(), 2);
    assert!(path.points[0].exchange_timestamp <= path.points[1].exchange_timestamp);
    assert!(anom.iter().any(|a| a.code == "UNSORTED_TRADES"));
    assert!(anom.iter().any(|a| a.code == "DUPLICATE_TRADE_ID"));
}

#[test]
fn missing_side_of_coupled_event_is_explicit() {
    let a = parse_env(env_value(
        "KXMLBGAME-26JUN18TEST-AAA",
        "KXMLBGAME-26JUN18TEST",
        "UNMATCHED",
        json!({"trades": [trade("t1", "2026-06-18T20:00:00Z", "0.8000")], "candlesticks": {"unavailable": true}}),
    ));
    let b = parse_env(env_value(
        "KXMLBGAME-26JUN18TEST-BBB",
        "KXMLBGAME-26JUN18TEST",
        "UNMATCHED",
        json!({"trades": [trade("u1", "2026-06-18T20:00:01Z", "0.2000")], "candlesticks": {"unavailable": true}}),
    ));
    let (pa, _) = reconstruct_path(&a, &empty_identity(), &[]).unwrap();
    let (pb, _) = reconstruct_path(&b, &empty_identity(), &[]).unwrap();
    let (both, _) = couple_paths(&[pa.clone(), pb]);
    assert_eq!(both.len(), 1);
    assert_eq!(both[0].missing_side, MissingSide::None);
    assert!(both[0].team_a_yes.is_some() && both[0].team_b_yes.is_some());

    let (one, _) = couple_paths(&[pa]);
    assert_eq!(one[0].missing_side, MissingSide::SecondYesContract);
    assert!(one[0].team_b_yes.is_none());
}

fn write_committed_run(dir: &std::path::Path, env: &serde_json::Value) -> (PathBuf, PathBuf) {
    let landing = dir.join("landing.json");
    fs::write(&landing, serde_json::to_vec(env).unwrap()).unwrap();
    let sha = sha256_file(&landing).unwrap();
    let handoff = W1CommitHandoff {
        run_id: "test".into(),
        plane: "DATA-INGEST".into(),
        artifact_version: "INGEST.2.1.1".into(),
        committed_at: rfc("2026-08-26T10:00:00Z"),
        artifacts: vec![CommittedArtifact {
            artifact_id: "kalshi_discovery:KXMLBGAME-26JUN18TEST-AAA".into(),
            source: "kalshi_discovery".into(),
            path: landing.display().to_string(),
            sha256: sha,
            partition_id: "KXMLBGAME-26JUN18TEST-AAA".into(),
            date: "2026-06-18".into(),
            commit_status: CommitStatus::Committed,
        }],
    };
    let hp = dir.join("w1_handoff.json");
    fs::write(&hp, serde_json::to_string(&handoff).unwrap()).unwrap();
    (hp, landing)
}

#[test]
fn checksum_mismatch_refuses() {
    let tmp = tempfile::tempdir().unwrap();
    let env = env_value(
        "KXMLBGAME-26JUN18TEST-AAA",
        "KXMLBGAME-26JUN18TEST",
        "UNMATCHED",
        json!({"trades": [], "candlesticks": {"unavailable": true}}),
    );
    let (hp, landing) = write_committed_run(tmp.path(), &env);
    let mut handoff: W1CommitHandoff =
        serde_json::from_str(&fs::read_to_string(&hp).unwrap()).unwrap();
    handoff.artifacts[0].sha256 = "deadbeef".into();
    fs::write(&hp, serde_json::to_string(&handoff).unwrap()).unwrap();
    let loaded: W1CommitHandoff = serde_json::from_str(&fs::read_to_string(&hp).unwrap()).unwrap();
    let err = committed_envelopes_for_date(
        &loaded,
        chrono::NaiveDate::from_ymd_opt(2026, 6, 18).unwrap(),
    )
    .unwrap_err();
    assert!(matches!(err, W4Error::ChecksumMismatch { .. }));
    let _ = landing;
}

#[test]
fn verify_checksum_helper() {
    let tmp = tempfile::tempdir().unwrap();
    let p = tmp.path().join("x.json");
    fs::write(&p, b"{}").unwrap();
    let sha = sha256_file(&p).unwrap();
    verify_checksum(&p, &sha).unwrap();
    let err = verify_checksum(&p, "ffff").unwrap_err();
    assert!(matches!(err, W4Error::ChecksumMismatch { .. }));
}

#[test]
fn no_data_real_writes() {
    let tmp = tempfile::tempdir().unwrap();
    let lake = tmp.path().join("Data-Real");
    fs::create_dir_all(&lake).unwrap();
    let env = env_value(
        "KXMLBGAME-26JUN18TEST-AAA",
        "KXMLBGAME-26JUN18TEST",
        "UNMATCHED",
        json!({"trades": [], "candlesticks": {"unavailable": true}}),
    );
    let (hp, _) = write_committed_run(tmp.path(), &env);
    let mut cfg = W4RunConfig::defaults();
    cfg.lake_root = lake.clone();
    cfg.out_dir = lake.join("nested-out");
    cfg.handoff = Some(hp);
    cfg.include_lake_raw = false;
    cfg.generated_at = rfc("2026-08-26T12:00:00Z");
    let err = run_w4_reconstruction(&cfg).unwrap_err();
    assert!(matches!(err, W4Error::LakeWriteForbidden(_)));
}

#[test]
fn runner_writes_outside_lake() {
    let tmp = tempfile::tempdir().unwrap();
    let lake = tmp.path().join("Data-Real");
    fs::create_dir_all(&lake).unwrap();
    let out = tmp.path().join("Foundation-W4");
    let env = env_value(
        "KXMLBGAME-26JUN18TEST-AAA",
        "KXMLBGAME-26JUN18TEST",
        "UNMATCHED",
        json!({"trades": [trade("t1", "2026-06-18T20:00:00Z", "0.8000")], "candlesticks": {"unavailable": true}}),
    );
    let (hp, _) = write_committed_run(tmp.path(), &env);
    let mut cfg = W4RunConfig::defaults();
    cfg.lake_root = lake;
    cfg.out_dir = out.clone();
    cfg.handoff = Some(hp);
    cfg.include_lake_raw = false;
    cfg.generated_at = rfc("2026-08-26T12:00:00Z");
    let result = run_w4_reconstruction(&cfg).unwrap();
    assert_eq!(result.reconstructed, 1);
    assert!(out.join("reconstruction_summary.json").exists());
    assert!(out.join("w5_handoff.md").exists());
    assert!(
        !out.join("reconstruction_summary.json")
            .to_string_lossy()
            .contains("SynchronizedState")
    );
}

#[test]
fn trades_only_retained_and_gated() {
    let env = parse_env(env_value(
        "KXMLBGAME-26JUN18TEST-AAA",
        "KXMLBGAME-26JUN18TEST",
        "UNMATCHED",
        json!({
            "trades": [trade("t1", "2026-06-18T20:00:00Z", "0.8000")],
            "candlesticks": {"unavailable": true}
        }),
    ));
    let (path, _) = reconstruct_path(&env, &empty_identity(), &[]).unwrap();
    assert_eq!(path.completeness, MarketCompleteness::TradesOnly);
    assert_eq!(path.capability.price_path_research, GateDecision::Allowed);
    assert_eq!(
        path.capability.orderbook_microstructure,
        GateDecision::Blocked
    );
    assert_eq!(path.capability.maker_fill_simulation, GateDecision::Blocked);
    assert!(!path.blocked_on_ingest_observations);
}

#[test]
fn missing_l2_does_not_synthesize_bid_ask_from_trades() {
    let env = parse_env(env_value(
        "KXMLBGAME-26JUN18TEST-AAA",
        "KXMLBGAME-26JUN18TEST",
        "UNMATCHED",
        json!({
            "trades": [trade("t1", "2026-06-18T20:00:00Z", "0.8000")],
            "candlesticks": {"unavailable": true}
        }),
    ));
    let (path, _) = reconstruct_path(&env, &empty_identity(), &[]).unwrap();
    let t = &path.points[0];
    assert_eq!(t.kind, MarketObservationKind::Trade);
    assert_eq!(t.trade_price_cents(), Some(80));
    assert!(t.yes_bid_cents.is_none() && t.yes_ask_cents.is_none());
    assert!(t.derived_spread_cents().is_none());
}

#[test]
fn unmatched_preserved_but_blocks_game_id_research() {
    let env = parse_env(env_value(
        "KXMLBGAME-26JUN18TEST-AAA",
        "KXMLBGAME-26JUN18TEST",
        "UNMATCHED",
        json!({"trades": [trade("t1", "2026-06-18T20:00:00Z", "0.8000")], "candlesticks": {"unavailable": true}}),
    ));
    let (path, _) = reconstruct_path(&env, &empty_identity(), &[]).unwrap();
    assert_eq!(
        path.capability.market_identity_status,
        MarketIdentityStatus::Unmatched
    );
    assert_eq!(
        path.capability.game_id_linked_research,
        GateDecision::Blocked
    );
}

#[test]
fn ambiguous_identity_gated() {
    let env = parse_env(env_value(
        "KXMLBGAME-26JUN18TEST-AAA",
        "KXMLBGAME-26JUN18TEST",
        "UNMATCHED",
        json!({"trades": [], "candlesticks": {"unavailable": true}}),
    ));
    let mut idx = IdentityIndex::empty();
    idx.by_ticker.insert(
        "KXMLBGAME-26JUN18TEST-AAA".into(),
        GameMarketPair {
            game_pk: Some("123".into()),
            official_date: "2026-06-18".into(),
            event_ticker: Some("KXMLBGAME-26JUN18TEST".into()),
            ticker: "KXMLBGAME-26JUN18TEST-AAA".into(),
            mapping: IdentityMapping::Ambiguous,
            completeness: None,
            notes: "fixture".into(),
        },
    );
    let (path, _) = reconstruct_path(&env, &idx, &[]).unwrap();
    assert_eq!(
        path.capability.market_identity_status,
        MarketIdentityStatus::Ambiguous
    );
    assert_eq!(
        path.capability.game_id_linked_research,
        GateDecision::Blocked
    );
}

#[test]
fn matched_identity_permits_game_id_linked_research() {
    let env = parse_env(env_value(
        "KXMLBGAME-26JUN18TEST-AAA",
        "KXMLBGAME-26JUN18TEST",
        "UNMATCHED",
        json!({"trades": [trade("t1", "2026-06-18T20:00:00Z", "0.8000")], "candlesticks": {"unavailable": true}}),
    ));
    let mut idx = IdentityIndex::empty();
    idx.by_ticker.insert(
        "KXMLBGAME-26JUN18TEST-AAA".into(),
        GameMarketPair {
            game_pk: Some("777001".into()),
            official_date: "2026-06-18".into(),
            event_ticker: Some("KXMLBGAME-26JUN18TEST".into()),
            ticker: "KXMLBGAME-26JUN18TEST-AAA".into(),
            mapping: IdentityMapping::Mapped,
            completeness: None,
            notes: "fixture mapped".into(),
        },
    );
    let (path, _) = reconstruct_path(&env, &idx, &[]).unwrap();
    assert_eq!(
        path.capability.market_identity_status,
        MarketIdentityStatus::Matched
    );
    assert_eq!(
        path.capability.game_id_linked_research,
        GateDecision::Allowed
    );
    assert_eq!(path.game_pk.as_deref(), Some("777001"));
}

#[test]
fn capability_metadata_survives_round_trip() {
    let env = parse_env(env_value(
        "KXMLBGAME-26JUN18TEST-AAA",
        "KXMLBGAME-26JUN18TEST",
        "UNMATCHED",
        json!({"trades": [trade("t1", "2026-06-18T20:00:00Z", "0.8000")], "candlesticks": {"unavailable": true}}),
    ));
    let (path, _) = reconstruct_path(&env, &empty_identity(), &[]).unwrap();
    let bytes = serde_json::to_vec(&path).unwrap();
    let back: momento_research_market::MarketPath = serde_json::from_slice(&bytes).unwrap();
    assert_eq!(back.capability, path.capability);
    assert_eq!(back.capability.price_path_research, GateDecision::Allowed);
    assert_eq!(
        back.capability.orderbook_microstructure,
        GateDecision::Blocked
    );
}

#[test]
fn candles_only_never_become_quotes_or_l2() {
    let env = parse_env(env_value(
        "KXMLBGAME-26JUN18TEST-AAA",
        "KXMLBGAME-26JUN18TEST",
        "UNMATCHED",
        json!({
            "trades": [],
            "candlesticks": {"candlesticks": [{
                "end_period_ts": 1781805600i64,
                "yes_bid": {"open_dollars":"0.4600","high_dollars":"0.4600","low_dollars":"0.4600","close_dollars":"0.4600"},
                "yes_ask": {"open_dollars":"0.4700","high_dollars":"0.4700","low_dollars":"0.4700","close_dollars":"0.4700"},
                "price": {"close_dollars": null}
            }]}
        }),
    ));
    let (path, _) = reconstruct_path(&env, &empty_identity(), &[]).unwrap();
    assert_eq!(path.completeness, MarketCompleteness::CandlesOnly);
    assert_eq!(
        research_gate(
            ResearchCapability::OrderbookMicrostructure,
            path.completeness,
            path.capability.market_identity_status
        ),
        GateDecision::Blocked
    );
    let c = &path.points[0];
    assert!(c.yes_bid_cents.is_none());
    assert!(!c.kind.is_game_time_l2());
    assert_eq!(
        path.capability.price_path_research,
        GateDecision::Conditional
    );
}

#[test]
fn trades_only_price_path_api_and_gates() {
    use momento_research_market::readiness::MarketReadiness;
    use momento_research_market::{
        FIRST01_ENTRY_TOUCH_CENTS, chronological_trades, request_maker_fill_simulation,
        request_orderbook_microstructure, synthetic_bid_ask,
    };

    let env = parse_env(env_value(
        "KXMLBGAME-26JUN18TEST-AAA",
        "KXMLBGAME-26JUN18TEST",
        "UNMATCHED",
        json!({
            "trades": [
                trade("t0", "2026-06-18T19:00:00Z", "0.7900"),
                trade("t1", "2026-06-18T20:00:00Z", "0.8000"),
                trade("t2", "2026-06-18T21:00:00Z", "0.8100")
            ],
            "candlesticks": {"unavailable": true}
        }),
    ));
    let (path, _) = reconstruct_path(&env, &empty_identity(), &[]).unwrap();
    assert!(path.price_path_available());
    assert!(!path.orderbook_available());
    assert!(!path.maker_simulation_available());
    let trades = chronological_trades(&path).unwrap();
    assert_eq!(trades.len(), 3);
    assert_eq!(trades[0].price_cents, 79);
    assert!(synthetic_bid_ask(&path).is_err());
    assert!(request_orderbook_microstructure(&path).is_err());
    assert!(request_maker_fill_simulation(&path).is_err());
    let ready = MarketReadiness::measure(&path, &[]);
    assert!(ready.funnel_eighty_observable);
    assert!(ready.funnel_first01_trigger_observable);
    assert!(ready.funnel_post_trigger_path_observable);
    assert!(!ready.first01_replay_sufficient);
    assert_eq!(FIRST01_ENTRY_TOUCH_CENTS, 80);
}

#[test]
fn observation_kinds_stay_distinct() {
    use momento_research_data::foundation::ObservabilityKind;
    use momento_research_market::completeness::{ObservationFlags, classify};

    let env = parse_env(env_value(
        "KXMLBGAME-26JUN18TEST-AAA",
        "KXMLBGAME-26JUN18TEST",
        "UNMATCHED",
        json!({"trades": [trade("t1", "2026-06-18T20:00:00Z", "0.8000")], "candlesticks": {"unavailable": true}}),
    ));
    let (path, _) = reconstruct_path(&env, &empty_identity(), &[]).unwrap();
    assert_eq!(path.points[0].kind, MarketObservationKind::Trade);
    assert!(path.points[0].trade_price_cents().is_some());
    assert!(path.points[0].yes_bid_cents.is_none());

    let snap = MarketPoint {
        ticker: "T".into(),
        event_ticker: "E".into(),
        market_id: "m".into(),
        exchange_timestamp: rfc("2026-06-18T20:00:00Z"),
        yes_bid_cents: Some(80),
        yes_ask_cents: Some(81),
        last_trade_cents: None,
        quantity_hundredths: None,
        trade_id: None,
        candle_ohlc: None,
        kind: MarketObservationKind::L2Snapshot,
        observability: ObservabilityKind::Observed,
        source: Some("FIXTURE_L2".into()),
        source_record_id: Some("snap1".into()),
        retrieval_timestamp: None,
    };
    let delta = MarketPoint {
        kind: MarketObservationKind::L2Delta,
        source: Some("FIXTURE_L2".into()),
        ..snap.clone()
    };
    let mut flags = ObservationFlags::from_points(&[snap.clone(), delta], true);
    flags.l2_delta_ungapped = true;
    assert_eq!(classify(&flags), MarketCompleteness::L2Complete);
    assert_eq!(
        classify(&ObservationFlags::from_points(&[snap], true)),
        MarketCompleteness::L2Partial
    );
}

#[test]
fn chronology_uses_source_time_not_retrieval() {
    let env = parse_env(env_value(
        "KXMLBGAME-26JUN18TEST-AAA",
        "KXMLBGAME-26JUN18TEST",
        "UNMATCHED",
        json!({
            "trades": [
                trade("late", "2026-06-18T21:00:00Z", "0.8100"),
                trade("early", "2026-06-18T19:00:00Z", "0.7900")
            ],
            "candlesticks": {"unavailable": true}
        }),
    ));
    let (path, anoms) = reconstruct_path(&env, &empty_identity(), &[]).unwrap();
    assert!(anoms.iter().any(|a| a.code == "UNSORTED_TRADES"));
    assert_eq!(path.points[0].trade_id.as_deref(), Some("early"));
    assert_eq!(path.points[1].trade_id.as_deref(), Some("late"));
    assert!(path.points[0].exchange_timestamp < path.points[1].exchange_timestamp);
    assert_eq!(
        path.points[0].retrieval_timestamp,
        path.points[1].retrieval_timestamp
    );
}

#[test]
fn leakage_as_of_excludes_future_trades() {
    use momento_research_market::{observations_as_of, trades_as_of};

    let env = parse_env(env_value(
        "KXMLBGAME-26JUN18TEST-AAA",
        "KXMLBGAME-26JUN18TEST",
        "UNMATCHED",
        json!({
            "trades": [
                trade("t1", "2026-06-18T20:00:00Z", "0.8000"),
                trade("t2", "2026-06-18T21:00:00Z", "0.8100")
            ],
            "settlement_ts": "2026-06-18T23:00:00Z",
            "candlesticks": {"unavailable": true}
        }),
    ));
    let (path, _) = reconstruct_path(&env, &empty_identity(), &[]).unwrap();
    let cut = rfc("2026-06-18T20:30:00Z");
    let as_of = observations_as_of(&path, cut);
    assert_eq!(as_of.len(), 1);
    assert_eq!(as_of[0].trade_id.as_deref(), Some("t1"));
    assert_eq!(trades_as_of(&path, cut).unwrap().len(), 1);
    assert!(cut < rfc("2026-06-18T23:00:00Z"));
    assert!(path.settlement.is_some());
}

#[test]
fn provenance_traces_to_raw_trade() {
    let env = parse_env(env_value(
        "KXMLBGAME-26JUN18TEST-AAA",
        "KXMLBGAME-26JUN18TEST",
        "UNMATCHED",
        json!({"trades": [trade("t1", "2026-06-18T20:00:00Z", "0.8000")], "candlesticks": {"unavailable": true}}),
    ));
    let (path, _) = reconstruct_path(&env, &empty_identity(), &[]).unwrap();
    let p = &path.points[0];
    assert_eq!(p.source.as_deref(), Some("KALSHI_PUBLIC_TRADE"));
    assert_eq!(p.source_record_id.as_deref(), Some("t1"));
    assert!(p.retrieval_timestamp.is_some());
    assert!(!path.reconstruction_version.is_empty());
}

#[test]
fn reconstruct_is_deterministic() {
    let env = parse_env(env_value(
        "KXMLBGAME-26JUN18TEST-AAA",
        "KXMLBGAME-26JUN18TEST",
        "UNMATCHED",
        json!({"trades": [trade("t1", "2026-06-18T20:00:00Z", "0.8000")], "candlesticks": {"unavailable": true}}),
    ));
    let (a, _) = reconstruct_path(&env, &empty_identity(), &[]).unwrap();
    let (b, _) = reconstruct_path(&env, &empty_identity(), &[]).unwrap();
    assert_eq!(a, b);
    assert_eq!(
        serde_json::to_vec(&a).unwrap(),
        serde_json::to_vec(&b).unwrap()
    );
}

#[test]
fn first_trade_is_not_market_open() {
    let env = parse_env(env_value(
        "KXMLBGAME-26JUN18TEST-AAA",
        "KXMLBGAME-26JUN18TEST",
        "UNMATCHED",
        json!({
            "open_time": "2026-06-18T16:00:00Z",
            "close_time": "2026-06-18T23:00:00Z",
            "trades": [trade("t1", "2026-06-18T20:00:00Z", "0.8000")],
            "candlesticks": {"unavailable": true}
        }),
    ));
    let (path, _) = reconstruct_path(&env, &empty_identity(), &[]).unwrap();
    assert_eq!(path.open_time.as_deref(), Some("2026-06-18T16:00:00Z"));
    assert_eq!(path.observed_start.unwrap(), rfc("2026-06-18T20:00:00Z"));
    assert_ne!(
        path.open_time.as_deref().unwrap(),
        path.observed_start.unwrap().to_rfc3339()
    );
}

#[test]
fn conflicting_trade_keeps_first() {
    let env = parse_env(env_value(
        "KXMLBGAME-26JUN18TEST-AAA",
        "KXMLBGAME-26JUN18TEST",
        "UNMATCHED",
        json!({
            "trades": [
                trade("t1", "2026-06-18T20:00:00Z", "0.8000"),
                trade("t1", "2026-06-18T20:00:01Z", "0.8100")
            ],
            "candlesticks": {"unavailable": true}
        }),
    ));
    let (path, anoms) = reconstruct_path(&env, &empty_identity(), &[]).unwrap();
    assert_eq!(path.points.len(), 1);
    assert_eq!(path.points[0].last_trade_cents, Some(80));
    assert!(anoms.iter().any(|a| a.code == "CONFLICTING_TRADE"));
}

#[test]
fn price_path_reconstruct_skips_metadata_only() {
    use momento_research_data::checksum::sha256_file;
    use momento_research_market::run_price_path_reconstruction;

    let tmp = tempfile::tempdir().unwrap();
    let ingest = tmp.path().join("ingest");
    fs::create_dir_all(ingest.join("runs")).unwrap();
    let trades = env_value(
        "KXMLBGAME-26JUN18TEST-AAA",
        "KXMLBGAME-26JUN18TEST",
        "UNMATCHED",
        json!({
            "completeness": "TRADES_ONLY",
            "trades": [trade("t1", "2026-06-18T20:00:00Z", "0.8000")],
            "candlesticks": {"unavailable": true}
        }),
    );
    let meta = env_value(
        "KXMLBGAME-26JUN18TEST-BBB",
        "KXMLBGAME-26JUN18TEST",
        "UNMATCHED",
        json!({
            "completeness": "MARKET_METADATA_ONLY",
            "trades": [],
            "candlesticks": {"unavailable": true}
        }),
    );
    let land_a = tmp.path().join("a.json");
    let land_b = tmp.path().join("b.json");
    fs::write(&land_a, serde_json::to_vec(&trades).unwrap()).unwrap();
    fs::write(&land_b, serde_json::to_vec(&meta).unwrap()).unwrap();
    let handoff = W1CommitHandoff {
        run_id: "test-pp".into(),
        plane: "DATA-INGEST".into(),
        artifact_version: "INGEST.2.1.1".into(),
        committed_at: rfc("2026-08-26T10:00:00Z"),
        artifacts: vec![
            CommittedArtifact {
                artifact_id: "kalshi_discovery:A".into(),
                source: "kalshi_discovery".into(),
                path: land_a.display().to_string(),
                sha256: sha256_file(&land_a).unwrap(),
                partition_id: "KXMLBGAME-26JUN18TEST-AAA".into(),
                date: "2026-06-18".into(),
                commit_status: CommitStatus::Committed,
            },
            CommittedArtifact {
                artifact_id: "kalshi_discovery:B".into(),
                source: "kalshi_discovery".into(),
                path: land_b.display().to_string(),
                sha256: sha256_file(&land_b).unwrap(),
                partition_id: "KXMLBGAME-26JUN18TEST-BBB".into(),
                date: "2026-06-18".into(),
                commit_status: CommitStatus::Committed,
            },
        ],
    };
    let hp = tmp.path().join("w1_handoff.json");
    let pairs = tmp.path().join("game_market_pairs.json");
    fs::write(&hp, serde_json::to_string(&handoff).unwrap()).unwrap();
    fs::write(&pairs, "[]").unwrap();
    let out = tmp.path().join("out");
    let lake = tmp.path().join("lake");
    fs::create_dir_all(&lake).unwrap();
    let report =
        run_price_path_reconstruction(&ingest, &lake, &out, Some(&hp), Some(&pairs)).unwrap();
    assert_eq!(report.reconstructed, 1);
    assert_eq!(report.reconstructable_trades_only, 1);
    assert_eq!(report.skipped_metadata_only, 1);
    assert_eq!(report.l2_paths, 0);
    assert!(out.join("price_path_compact.jsonl").exists());
}

fn matched_pair_doc(ticker: &str, pk: &str) -> GameMarketPair {
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

fn write_matched_sidecar(
    ingest: &std::path::Path,
    ticker: &str,
    trades: Vec<serde_json::Value>,
    retrieved_at: &str,
) {
    use momento_research_ingest::paths::IngestPaths;
    let dest = IngestPaths::new(ingest).landing_kalshi_matched_trades(
        chrono::NaiveDate::from_ymd_opt(2025, 7, 15).unwrap(),
        ticker,
    );
    fs::create_dir_all(dest.parent().unwrap()).unwrap();
    let env = json!({
        "envelope_version": "INGEST.KALSHI.MATCHED_TRADES.1.0.0",
        "ticker": ticker,
        "game_pk": "718001",
        "identity_mapping": "MAPPED",
        "official_date": "2025-07-15",
        "retrieved_at": retrieved_at,
        "canonical_trade_count": trades.len(),
        "trades": trades
    });
    fs::write(dest, serde_json::to_vec(&env).unwrap()).unwrap();
}

#[test]
fn matched_trade_reconstruction_quality_gates() {
    use momento_research_market::reconstruct::market_id_hex;
    use momento_research_market::{
        chronological_trades, request_maker_fill_simulation, request_orderbook_microstructure,
        run_matched_trade_reconstruction, synthetic_bid_ask,
    };

    let tmp = tempfile::tempdir().unwrap();
    let ingest = tmp.path().join("ingest");
    let lake = tmp.path().join("lake");
    let out = tmp.path().join("out");
    fs::create_dir_all(ingest.join("runs")).unwrap();
    fs::create_dir_all(&lake).unwrap();
    fs::create_dir_all(&out).unwrap();

    let ticker = "KXMLBGAME-25JUL15AAABBB-AAA";
    let meta_ticker = "KXMLBGAME-25JUL15AAABBB-BBB";
    let unmatched_ticker = "KXMLBGAME-25JUL15AAABBB-ZZZ";
    let sentinel = b"UNMATCHED_COMPACT_MUST_NOT_CHANGE\n";
    fs::write(out.join("price_path_compact.jsonl"), sentinel).unwrap();
    fs::write(
        out.join("price_path_readiness.json"),
        serde_json::to_vec(&json!({"reconstructable_trades_only": 238})).unwrap(),
    )
    .unwrap();
    fs::write(
        out.join("price_path_market_rows.json"),
        serde_json::to_vec(&json!([{"trade_count": 10}])).unwrap(),
    )
    .unwrap();

    write_matched_sidecar(
        &ingest,
        ticker,
        vec![
            json!({
                "trade_id": "late",
                "ticker": ticker,
                "created_time": "2025-07-15T21:00:00Z",
                "yes_price_dollars": "0.8100",
                "count_fp": "1.00"
            }),
            json!({
                "trade_id": "early",
                "ticker": ticker,
                "created_time": "2025-07-15T19:00:00Z",
                "yes_price_dollars": "0.8000",
                "count_fp": "1.00"
            }),
            json!({
                "trade_id": "lock",
                "ticker": ticker,
                "created_time": "2025-07-15T22:00:00Z",
                "yes_price_dollars": "0.8900",
                "count_fp": "1.00"
            }),
            json!({
                "trade_id": "dup",
                "ticker": ticker,
                "created_time": "2025-07-15T19:00:00Z",
                "yes_price_dollars": "0.8000",
                "count_fp": "1.00"
            }),
        ],
        "2026-08-26T19:00:00Z",
    );
    let meta_dest = momento_research_ingest::paths::IngestPaths::new(&ingest)
        .landing_kalshi_matched_trades(
            chrono::NaiveDate::from_ymd_opt(2025, 7, 15).unwrap(),
            meta_ticker,
        );
    fs::create_dir_all(meta_dest.parent().unwrap()).unwrap();
    fs::write(
        meta_dest,
        serde_json::to_vec(&json!({
            "envelope_version": "INGEST.KALSHI.MATCHED_TRADES.1.0.0",
            "ticker": "OTHER-TICKER",
            "game_pk": "718001",
            "identity_mapping": "MAPPED",
            "official_date": "2025-07-15",
            "retrieved_at": "2026-08-26T19:00:00Z",
            "canonical_trade_count": 1,
            "trades": [{
                "trade_id": "x",
                "ticker": "OTHER-TICKER",
                "created_time": "2025-07-15T19:00:00Z",
                "yes_price_dollars": "0.8000",
                "count_fp": "1.00"
            }]
        }))
        .unwrap(),
    )
    .unwrap();

    let pairs = vec![
        matched_pair_doc(ticker, "718001"),
        matched_pair_doc(meta_ticker, "718001"),
        GameMarketPair {
            game_pk: None,
            official_date: "2025-07-15".into(),
            event_ticker: Some("KXMLBGAME-25JUL15AAABBB".into()),
            ticker: unmatched_ticker.into(),
            mapping: IdentityMapping::Unmatched,
            completeness: None,
            notes: "UNMATCHED".into(),
        },
    ];
    let pairs_path = tmp.path().join("game_market_pairs.json");
    let handoff_path = tmp.path().join("w1_handoff.json");
    fs::write(&pairs_path, serde_json::to_string(&pairs).unwrap()).unwrap();
    fs::write(
        &handoff_path,
        serde_json::to_string(&W1CommitHandoff {
            run_id: "test-w4d".into(),
            plane: "DATA-INGEST".into(),
            artifact_version: "INGEST.2.1.1".into(),
            committed_at: rfc("2026-08-26T10:00:00Z"),
            artifacts: vec![],
        })
        .unwrap(),
    )
    .unwrap();

    let a = run_matched_trade_reconstruction(
        &ingest,
        &lake,
        &out,
        Some(&handoff_path),
        Some(&pairs_path),
    )
    .unwrap();
    let b = run_matched_trade_reconstruction(
        &ingest,
        &lake,
        &out,
        Some(&handoff_path),
        Some(&pairs_path),
    )
    .unwrap();
    assert_eq!(a.total_matched_markets, 2);
    assert_eq!(a.matched_with_trades, 1);
    assert_eq!(a.matched_without_trades, 1);
    assert_eq!(a.matched_trades_only, 1);
    assert_eq!(a.matched_metadata_only, 1);
    assert_eq!(a.matched_l2_complete, 0);
    assert_eq!(a.matched_l2_partial, 0);
    assert_eq!(a.matched_with_exact_80_print, 1);
    assert_eq!(a.matched_with_exact_81_print, 1);
    assert_eq!(a.matched_with_exact_89_print, 1);
    assert_eq!(a.matched_with_post_80_path, 1);
    assert_eq!(a.unmappable_sidecars, 1);
    assert_eq!(a.total_matched_trade_observations, 4);
    assert_eq!(a.min_trades_per_matched_with_trades, Some(4));
    assert_eq!(a.existing_unmatched_trades_only_paths, Some(238));
    assert_eq!(a.combined_trade_observations, Some(14));
    assert_eq!(
        serde_json::to_vec(&a).unwrap(),
        serde_json::to_vec(&b).unwrap()
    );
    assert_eq!(
        fs::read(out.join("price_path_compact.jsonl")).unwrap(),
        sentinel
    );
    let compact = fs::read_to_string(out.join("matched_price_path_compact.jsonl")).unwrap();
    assert!(compact.contains(ticker));
    assert!(!compact.contains(unmatched_ticker));
    assert!(!compact.contains("WRONG-SIDECAR"));

    let rows: Vec<serde_json::Value> =
        serde_json::from_slice(&fs::read(out.join("matched_price_path_market_rows.json")).unwrap())
            .unwrap();
    let traded = rows.iter().find(|r| r["ticker"] == ticker).unwrap();
    assert_eq!(traded["game_pk"], "718001");
    assert_eq!(traded["identity_status"], "MATCHED");
    assert_eq!(traded["market_id"], market_id_hex(ticker));
    assert_eq!(traded["completeness"], "TRADES_ONLY");
    assert_eq!(traded["quote_count"], 0);
    assert_eq!(traded["l2_snapshot_count"], 0);
    let meta = rows.iter().find(|r| r["ticker"] == meta_ticker).unwrap();
    assert_eq!(meta["completeness"], "MARKET_METADATA_ONLY");
    assert_eq!(meta["trade_count"], 0);
    assert_eq!(meta["funnel_eighty_observable"], false);

    let env = parse_env(env_value(
        ticker,
        "KXMLBGAME-25JUL15AAABBB",
        "MAPPED",
        json!({"trades": [], "candlesticks": {"unavailable": true}}),
    ));
    let mut idx = IdentityIndex::empty();
    idx.by_ticker
        .insert(ticker.into(), matched_pair_doc(ticker, "718001"));
    let raw = vec![
        RawMarketEvent {
            received_at: rfc("2026-08-26T20:00:00Z"),
            source: "historical_rest".into(),
            endpoint: "matched_historical_trades".into(),
            ticker: Some(ticker.into()),
            payload: json!({
                "trade_id": "early",
                "ticker": ticker,
                "created_time": "2025-07-15T19:00:00Z",
                "yes_price_dollars": "0.8000",
                "count_fp": "1.00"
            }),
        },
        RawMarketEvent {
            received_at: rfc("2026-08-26T10:00:00Z"),
            source: "historical_rest".into(),
            endpoint: "matched_historical_trades".into(),
            ticker: Some(ticker.into()),
            payload: json!({
                "trade_id": "late",
                "ticker": ticker,
                "created_time": "2025-07-15T21:00:00Z",
                "yes_price_dollars": "0.8100",
                "count_fp": "1.00"
            }),
        },
    ];
    let (path, _) = reconstruct_path(&env, &idx, &raw).unwrap();
    assert_eq!(path.game_pk.as_deref(), Some("718001"));
    assert_eq!(path.market_id, market_id_hex(ticker));
    assert_eq!(path.completeness, MarketCompleteness::TradesOnly);
    assert_eq!(
        path.capability.market_identity_status,
        MarketIdentityStatus::Matched
    );
    let trades = chronological_trades(&path).unwrap();
    assert_eq!(trades[0].trade_id.as_deref(), Some("early"));
    assert_eq!(trades[1].trade_id.as_deref(), Some("late"));
    assert!(trades[0].exchange_timestamp < trades[1].exchange_timestamp);
    assert!(
        trades[0].retrieval_timestamp.unwrap() > trades[1].retrieval_timestamp.unwrap(),
        "retrieval must not reorder"
    );
    assert!(
        path.points
            .iter()
            .all(|p| p.yes_bid_cents.is_none() && p.yes_ask_cents.is_none())
    );
    assert!(synthetic_bid_ask(&path).is_err());
    assert!(request_orderbook_microstructure(&path).is_err());
    assert!(request_maker_fill_simulation(&path).is_err());
    assert_eq!(
        path.points[0].source.as_deref(),
        Some("KALSHI_HISTORICAL_TRADE")
    );
}

#[test]
fn matched_eighty_observability_is_trade_prints_not_candles() {
    use momento_research_market::run_matched_trade_reconstruction;

    let tmp = tempfile::tempdir().unwrap();
    let ingest = tmp.path().join("ingest");
    let lake = tmp.path().join("lake");
    let out = tmp.path().join("out");
    fs::create_dir_all(ingest.join("runs")).unwrap();
    fs::create_dir_all(&lake).unwrap();
    let ticker = "KXMLBGAME-25JUL15AAABBB-CCC";
    let disc = momento_research_ingest::paths::IngestPaths::new(&ingest).landing_kalshi_discovery(
        chrono::NaiveDate::from_ymd_opt(2025, 7, 15).unwrap(),
        ticker,
    );
    fs::create_dir_all(disc.parent().unwrap()).unwrap();
    fs::write(
        &disc,
        serde_json::to_vec(&env_value(
            ticker,
            "KXMLBGAME-25JUL15AAABBB",
            "MAPPED",
            json!({
                "completeness": "CANDLES_ONLY",
                "trades": [],
                "candlesticks": {"candlesticks": [{
                    "end_period_ts": 1752534000i64,
                    "price": {"close_dollars": "0.8000"},
                    "yes_bid": {"close_dollars": "0.8000"},
                    "yes_ask": {"close_dollars": "0.8100"}
                }]}
            }),
        ))
        .unwrap(),
    )
    .unwrap();
    let pairs = vec![matched_pair_doc(ticker, "718002")];
    let pairs_path = tmp.path().join("game_market_pairs.json");
    let handoff_path = tmp.path().join("w1_handoff.json");
    fs::write(&pairs_path, serde_json::to_string(&pairs).unwrap()).unwrap();
    fs::write(
        &handoff_path,
        serde_json::to_string(&W1CommitHandoff {
            run_id: "test-w4d-candle".into(),
            plane: "DATA-INGEST".into(),
            artifact_version: "INGEST.2.1.1".into(),
            committed_at: rfc("2026-08-26T10:00:00Z"),
            artifacts: vec![],
        })
        .unwrap(),
    )
    .unwrap();
    let cov = run_matched_trade_reconstruction(
        &ingest,
        &lake,
        &out,
        Some(&handoff_path),
        Some(&pairs_path),
    )
    .unwrap();
    assert_eq!(cov.matched_with_exact_80_print, 0);
    assert_eq!(cov.matched_with_trades, 0);
    assert_eq!(cov.matched_l2_complete, 0);
}
