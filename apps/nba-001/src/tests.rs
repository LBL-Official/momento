//! Worker unit tests. No network.

use std::path::PathBuf;

use momento_kalshi::MarketCandlestick;
use serde_json::json;

use crate::controls::read_controls;
use crate::engine::client_order_id;
use crate::journal::{Journal, write_json_atomic};
use crate::lease::Lease;
use crate::public::{bar_from_candle, parse_event, parse_live_data};

fn tmp(name: &str) -> PathBuf {
    let dir = std::env::temp_dir().join(format!("nba001-test-{name}-{}", std::process::id()));
    let _ = std::fs::remove_dir_all(&dir);
    std::fs::create_dir_all(&dir).unwrap();
    dir
}

#[test]
fn client_order_id_is_deterministic_and_prefixed() {
    let a = client_order_id("G", "T", 100);
    assert_eq!(a, client_order_id("G", "T", 100));
    assert_ne!(a, client_order_id("G", "T", 160));
    assert_ne!(a, client_order_id("G", "U", 100));
    assert!(a.starts_with(crate::account::CLIENT_ID_PREFIX));
    assert_eq!(a.len(), crate::account::CLIENT_ID_PREFIX.len() + 16);
}

#[test]
fn journal_is_append_only_with_unique_ids() {
    let dir = tmp("journal");
    let mut j = Journal::new(&dir);
    let a = j.record(1, "A", Some("G"), None, json!({"x": 1}));
    let b = j.record(1, "B", None, Some("T"), json!({}));
    assert_ne!(a, b);
    let raw = std::fs::read_to_string(j.path()).unwrap();
    let lines: Vec<serde_json::Value> = raw
        .lines()
        .map(|l| serde_json::from_str(l).unwrap())
        .collect();
    assert_eq!(lines.len(), 2);
    assert_eq!(lines[0]["kind"], "A");
    assert_eq!(lines[0]["bot_id"], "nba-001");
    assert_eq!(lines[1]["market_id"], "T");
    let mut j2 = Journal::new(&dir);
    j2.record(2, "C", None, None, json!({}));
    assert_eq!(
        std::fs::read_to_string(j2.path()).unwrap().lines().count(),
        3
    );
    assert_eq!(j2.write_errors, 0);
}

#[test]
fn atomic_write_leaves_no_temp_file() {
    let dir = tmp("atomic");
    let p = dir.join("status.json");
    write_json_atomic(&p, &json!({"a": 1})).unwrap();
    write_json_atomic(&p, &json!({"a": 2})).unwrap();
    let v: serde_json::Value = serde_json::from_str(&std::fs::read_to_string(&p).unwrap()).unwrap();
    assert_eq!(v["a"], 2);
    assert!(!dir.join("status.tmp").exists());
}

#[test]
fn controls_missing_is_off_and_malformed_is_paused() {
    let dir = tmp("controls");
    let c = read_controls(&dir);
    assert!(!c.pause_entries && !c.full_stop && c.read_error.is_none());
    std::fs::write(dir.join("control.json"), "{not json").unwrap();
    let c = read_controls(&dir);
    assert!(c.pause_entries);
    assert!(c.read_error.is_some());
    std::fs::write(dir.join("control.json"), r#"{"full_stop": true}"#).unwrap();
    let c = read_controls(&dir);
    assert!(c.full_stop && !c.pause_entries);
}

#[test]
fn lease_is_single_writer() {
    let dir = tmp("lease");
    let first = Lease::acquire(&dir).unwrap();
    let second = Lease::acquire(&dir);
    assert!(second.is_err_and(|e| e.starts_with("ALREADY_RUNNING")));
    drop(first);
    assert!(Lease::acquire(&dir).is_ok());
}

#[test]
fn candle_parses_to_integer_cents() {
    let c: MarketCandlestick = serde_json::from_value(json!({
        "end_period_ts": 1_790_000_060,
        "yes_bid": {"open_dollars": "0.7500", "low_dollars": "0.6700", "high_dollars": "0.7900", "close_dollars": "0.7800"},
        "yes_ask": {"open_dollars": "0.7700", "low_dollars": "0.7000", "high_dollars": "0.8100", "close_dollars": "0.8000"},
        "volume_fp": "0.50",
    }))
    .unwrap();
    let b = bar_from_candle(&c);
    assert_eq!(b.end_ts, 1_790_000_060);
    assert_eq!(b.yes_bid_close, Some(78));
    assert_eq!(b.yes_ask_close, Some(80));
    assert_eq!(b.yes_bid_low, Some(67));
    assert_eq!(b.volume, Some(50));
    assert!(b.is_quality(false));
}

#[test]
fn malformed_candle_is_an_error_not_zero() {
    let parsed = serde_json::from_value::<MarketCandlestick>(json!({
        "end_period_ts": 1,
        "yes_bid": {},
        "yes_ask": {},
    }));
    assert!(parsed.is_err());
    let c: MarketCandlestick = serde_json::from_value(json!({
        "end_period_ts": 1,
        "yes_bid": {"open_dollars": "x", "low_dollars": "x", "high_dollars": "x", "close_dollars": "x"},
        "yes_ask": {"open_dollars": "0.10", "low_dollars": "0.10", "high_dollars": "0.10", "close_dollars": "0.10"},
        "volume_fp": "3.00",
    }))
    .unwrap();
    let b = bar_from_candle(&c);
    assert_eq!(b.yes_bid_close, None);
    assert!(!b.is_quality(true));
}

/// Network: `cargo test -p momento-nba-001 -- --ignored real_candles`.
#[test]
#[ignore]
fn real_candles_replay_through_cross_tracker() {
    let mut public = crate::public::Public::production();
    let ticker = "KXWNBAGAME-26SEP24LVPHX-PHX";
    let bars = public
        .candles("KXWNBAGAME", ticker, 1_790_295_000, 1_790_311_000, 0)
        .unwrap();
    assert!(bars.len() > 100);
    let mut t = momento_strategy_nba::CrossTracker::new();
    for b in &bars {
        t.push(b);
    }
    assert!(t.quality_bars() > 0);
    assert_ne!(
        t.outcome(),
        momento_strategy_nba::CrossOutcome::ChronologyUnresolved
    );
    eprintln!(
        "bars={} quality={} outcome={:?}",
        bars.len(),
        t.quality_bars(),
        t.outcome()
    );
}

#[test]
fn event_and_live_data_parse() {
    let ev = parse_event(&json!({
        "event_ticker": "KXNBAGAME-26OCT20BOSDET",
        "series_ticker": "KXNBAGAME",
        "mutually_exclusive": true,
        "exchange_index": 0,
        "markets": [
            {"ticker": "KXNBAGAME-26OCT20BOSDET-BOS", "event_ticker": "KXNBAGAME-26OCT20BOSDET", "exchange_index": 0,
             "status": "active", "yes_sub_title": "Boston", "yes_bid_dollars": "0.5500", "yes_ask_dollars": "0.5600"},
            {"event_ticker": "missing ticker is dropped"}
        ]
    }))
    .unwrap();
    assert_eq!(ev.desc.mutually_exclusive, Some(true));
    assert_eq!(ev.markets.len(), 1);
    assert_eq!(ev.markets[0].desc.exchange_index, Some(0));
    assert_eq!(ev.markets[0].yes_bid_cents, Some(55));

    let obs = parse_live_data(
        &json!({"live_data": {"details": {"status": "inprogress", "period": 2, "period_type": "quarter",
            "period_remaining_time": "06:12", "last_updated_ts": 995}}}),
        1000,
    )
    .unwrap();
    assert_eq!(obs.period, Some(2));
    assert_eq!(obs.source_updated_at, Some(995));
    assert!(momento_strategy_nba::slice::classify(&obs).eligible());
    assert!(parse_live_data(&json!({}), 0).is_none());
}

#[test]
fn shipped_config_is_shadow_with_live_gates_unset() {
    let path = concat!(env!("CARGO_MANIFEST_DIR"), "/../../config/nba-001.toml");
    let cfg = crate::config::Config::load(std::path::Path::new(path)).unwrap();
    assert_eq!(
        cfg.config_mode().unwrap(),
        momento_strategy_nba::ConfigMode::Shadow
    );
    assert!(!cfg.live_gates_set());
    assert!(cfg.collateral.isolation_evidence.is_empty());
    assert!(cfg.collateral.reservation_ledger.is_empty());
}

#[test]
fn state_absent_starts_empty() {
    let dir = tmp("state-absent");
    let (s, v) = crate::load_state(&dir, 1).unwrap();
    assert!(s.games.is_empty());
    assert_eq!(v["state"], "ABSENT");
}

#[test]
fn state_v1_with_batch_key_loads_and_ignores_it() {
    let dir = tmp("state-v1");
    std::fs::write(
        dir.join("state.json"),
        json!({"markets": {}, "games": {}, "batch": {"batches": [{"number": 1}]}}).to_string(),
    )
    .unwrap();
    let (s, v) = crate::load_state(&dir, 1).unwrap();
    assert_eq!(v["state"], "LOADED");
    assert_eq!(s.equity.current().number, 1);
    assert_eq!(s.equity.reference_equity().cents(), 2_000_000);
}

#[test]
fn state_unreadable_is_kept_aside_not_overwritten() {
    let dir = tmp("state-bad");
    std::fs::write(dir.join("state.json"), "{\"games\": 7}").unwrap();
    let (s, v) = crate::load_state(&dir, 42).unwrap();
    assert!(s.games.is_empty());
    assert_eq!(v["state"], "UNREADABLE_KEPT_ASIDE");
    assert!(!dir.join("state.json").exists());
    assert_eq!(
        std::fs::read_to_string(dir.join("state.json.unreadable-42")).unwrap(),
        "{\"games\": 7}"
    );
}

#[test]
fn fees_verified_only_for_the_evidenced_configuration() {
    use crate::engine::fees_verified_for;
    use momento_strategy_nba::{BalancePrecision, FeeModel, FeeType};
    let m = |t, milli| Some(FeeModel::new(t, milli, BalancePrecision::Cent));
    assert!(fees_verified_for(
        true,
        m(FeeType::QuadraticWithMakerFees, 1000)
    ));
    assert!(!fees_verified_for(
        false,
        m(FeeType::QuadraticWithMakerFees, 1000)
    ));
    // KXMLBGAME publishes 0.5 but was charged at 1: not verified.
    assert!(!fees_verified_for(
        true,
        m(FeeType::QuadraticWithMakerFees, 500)
    ));
    assert!(!fees_verified_for(true, m(FeeType::Quadratic, 1000)));
    assert!(!fees_verified_for(true, None));
}
