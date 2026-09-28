//! Trading engine composition root. Paper and live hosts.

use std::env;
use std::path::PathBuf;

use momento_core::TradingMode;
use momento_kalshi::redact_secrets;
use momento_trading_engine::demo::run_demo;
use momento_trading_engine::iti_live::run_iti_live;
use momento_trading_engine::live::run_live;
use momento_trading_engine::runtime::{
    HostError, heartbeat_line, heartbeat_period, load_paper_config, peek_config, persist_strategy,
    restore_strategy, state_file,
};

fn main() {
    if let Err(err) = run() {
        eprintln!(
            "momento-trading-engine fatal: {}",
            redact_secrets(&err.to_string())
        );
        std::process::exit(err.process_exit_code());
    }
}

fn run() -> Result<(), HostError> {
    let config_path = env::var("MOMENTO_CONFIG")
        .map(PathBuf::from)
        .unwrap_or_else(|_| PathBuf::from("config/paper.toml"));
    let state_dir = env::var("MOMENTO_STATE_DIR")
        .map(PathBuf::from)
        .unwrap_or_else(|_| PathBuf::from("data"));

    let peeked = peek_config(&config_path)?;
    if peeked.mode == TradingMode::Live {
        if peeked.is_research_iti() {
            return run_iti_live(&config_path, &state_dir);
        }
        return run_live(&config_path, &state_dir);
    }
    if peeked.mode == TradingMode::Demo {
        return run_demo(&config_path, &state_dir);
    }

    let cfg = load_paper_config(&config_path)?;
    eprintln!(
        "momento-trading-engine start config={} state_dir={} mode={:?} live.enabled={} live_implemented=false",
        config_path.display(),
        state_dir.display(),
        cfg.mode,
        cfg.live.enabled
    );

    let strategy = restore_strategy(&state_dir)?;
    persist_strategy(&state_dir, &strategy)?;
    eprintln!(
        "momento-trading-engine restored games={} persistence={}",
        strategy.snapshot().games.len(),
        state_file(&state_dir).display()
    );

    loop {
        persist_strategy(&state_dir, &strategy)?;
        eprintln!("{}", heartbeat_line(&cfg));
        std::thread::sleep(heartbeat_period());
    }
}
