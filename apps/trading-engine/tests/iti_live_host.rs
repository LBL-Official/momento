use std::fs;
use std::time::{SystemTime, UNIX_EPOCH};

use momento_core::TradingMode;
use momento_trading_engine::iti_live::{factory_live_unit_refused, iti_live_preflight_config};
use momento_trading_engine::runtime::{HostError, load_iti_live_config, load_live_config};

fn tmp_dir() -> std::path::PathBuf {
    let nanos = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap()
        .as_nanos();
    let dir = std::env::temp_dir().join(format!("momento-iti-live-host-{nanos}"));
    fs::create_dir_all(&dir).unwrap();
    dir
}

fn live_iti_toml() -> &'static str {
    r#"
mode = "live"
timezone = "America/Los_Angeles"
allocation_bps = 1250
max_entry_price_cents = 59
preferred_entry_price_cents = 20
min_entry_price_cents = 20
initial_bankroll_cents = 5000
sizing_mode = "FIXED_CENTS"
max_position_budget_cents = 625
strategy_profile = "research_iti"
iti_entry_cents = 20
iti_win_cents = 60
iti_loss_cents = 10
sport = "mlb"
[live]
enabled = true
confirmation = "ENABLE_LIVE_TRADING"
"#
}

#[test]
fn live_iti_config_is_accepted() {
    let dir = tmp_dir();
    let path = dir.join("live.toml");
    fs::write(&path, live_iti_toml()).unwrap();
    let cfg = load_iti_live_config(&path).unwrap();
    assert_eq!(cfg.mode, TradingMode::Live);
    assert!(cfg.is_research_iti());
    assert!(cfg.is_live_armed());
    assert_eq!(cfg.iti_entry_cents, Some(20));
    assert_eq!(cfg.iti_win_cents, Some(60));
    assert_eq!(cfg.iti_loss_cents, Some(10));
    iti_live_preflight_config(&cfg).unwrap();
}

#[test]
fn factory_load_live_config_rejects_research_iti() {
    let dir = tmp_dir();
    let path = dir.join("live.toml");
    fs::write(&path, live_iti_toml()).unwrap();
    match load_live_config(&path) {
        Err(HostError::Preflight(msg)) => {
            assert!(msg.contains("research_iti"));
        }
        other => panic!("factory path must refuse research_iti: {other:?}"),
    }
}

#[test]
fn factory_live_toml_still_80_83() {
    let live = std::path::Path::new(env!("CARGO_MANIFEST_DIR")).join("../../config/live.toml");
    let cfg = load_live_config(&live).unwrap();
    assert_eq!(cfg.min_entry_price_cents, 80);
    assert_eq!(cfg.max_entry_price_cents, 83);
    assert!(!cfg.is_research_iti());
}

#[test]
fn factory_paths_are_refused() {
    let config = std::path::Path::new("/var/lib/momento/config/live.toml");
    let state = std::path::Path::new("/var/lib/momento/state");
    assert!(factory_live_unit_refused(config, state).is_err());
    let isolated_cfg = std::path::Path::new("/var/lib/momento/live/mlb-002/live.toml");
    let isolated_state = std::path::Path::new("/var/lib/momento/live/mlb-002/state");
    assert!(factory_live_unit_refused(isolated_cfg, isolated_state).is_ok());
}
