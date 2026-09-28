use std::fs;
use std::time::{SystemTime, UNIX_EPOCH};

use momento_core::{GameId, TradingMode};
use momento_strategy_mlb::{MlbGamePhase, MlbGameSnapshot, MlbStrategy, MlbStrategySnapshot};
use momento_trading_engine::runtime::{
    heartbeat_line, load_paper_config, persist_strategy, restore_strategy,
};

fn tmp_dir() -> std::path::PathBuf {
    let nanos = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap()
        .as_nanos();
    let dir = std::env::temp_dir().join(format!("momento-paper-host-{nanos}"));
    fs::create_dir_all(&dir).unwrap();
    dir
}

#[test]
fn paper_config_loads_and_live_gate_is_off() {
    let path = std::path::Path::new(env!("CARGO_MANIFEST_DIR")).join("../../config/paper.toml");
    let cfg = load_paper_config(&path).unwrap();
    assert_eq!(cfg.mode, TradingMode::Paper);
    assert!(!cfg.live.enabled);
    assert!(heartbeat_line(&cfg).contains("live_implemented=false"));
    assert!(heartbeat_line(&cfg).contains("live.enabled=false"));
}

#[test]
fn live_config_cannot_arm_host() {
    let dir = tmp_dir();
    let path = dir.join("live.toml");
    fs::write(
        &path,
        r#"
mode = "live"
timezone = "America/Los_Angeles"
allocation_bps = 1250
max_entry_price_cents = 83
preferred_entry_price_cents = 80
min_entry_price_cents = 80
initial_bankroll_cents = 5000
[live]
enabled = true
confirmation = "ENABLE_LIVE_TRADING"
"#,
    )
    .unwrap();
    let err = load_paper_config(&path).unwrap_err();
    assert!(matches!(
        err,
        momento_trading_engine::runtime::HostError::LiveNotImplemented
    ));
}

#[test]
fn strategy_state_survives_process_restart_via_file() {
    let dir = tmp_dir();
    let mut snap = MlbGameSnapshot::new(GameId::from_raw(10));
    snap.phase = MlbGamePhase::GameLocked;
    let strategy = MlbStrategy::restore(MlbStrategySnapshot { games: vec![snap] });
    persist_strategy(&dir, &strategy).unwrap();

    let restored = restore_strategy(&dir).unwrap();
    assert_eq!(
        restored.phase(GameId::from_raw(10)),
        MlbGamePhase::GameLocked
    );
}
