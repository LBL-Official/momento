//! Paper host runtime. Does not connect to Kalshi. Does not arm live trading.
//!
//! Persistence uses the existing [`MlbStrategySnapshot`] type. This is a file
//! adapter, not a second strategy state machine.

use std::fs;
use std::path::{Path, PathBuf};
use std::time::Duration;

use momento_core::{TradingConfig, TradingMode};
use momento_strategy_mlb::{MlbStrategy, MlbStrategySnapshot};
use momento_strategy_wnba::{WnbaStrategy, WnbaStrategySnapshot};

pub const HEARTBEAT_SECS: u64 = 5;
pub const STATE_FILE_NAME: &str = "mlb-strategy.json";
pub const WNBA_STATE_FILE_NAME: &str = "wnba-strategy.json";
pub const PREFLIGHT_EXIT_CODE: i32 = 78;

#[derive(Debug)]
pub enum HostError {
    Io(String),
    Config(String),
    LiveNotImplemented,
    LiveDisarmed,
    Preflight(String),
    Venue(String),
}

impl std::fmt::Display for HostError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            Self::Io(s) | Self::Config(s) | Self::Preflight(s) | Self::Venue(s) => write!(f, "{s}"),
            Self::LiveNotImplemented => write!(f, "live trading is not implemented"),
            Self::LiveDisarmed => write!(
                f,
                "live trading is disarmed; require mode=live, live.enabled=true, confirmation=ENABLE_LIVE_TRADING"
            ),
        }
    }
}

impl std::error::Error for HostError {}

impl HostError {
    pub fn process_exit_code(&self) -> i32 {
        match self {
            Self::Preflight(_) | Self::LiveDisarmed => PREFLIGHT_EXIT_CODE,
            _ => 1,
        }
    }
}

pub fn load_paper_config(path: &Path) -> Result<TradingConfig, HostError> {
    let raw = fs::read_to_string(path).map_err(|e| HostError::Io(e.to_string()))?;
    let cfg = TradingConfig::from_toml_str(&raw).map_err(|e| HostError::Config(e.to_string()))?;
    cfg.validate().map_err(|e| {
        if matches!(
            e,
            momento_core::ConfigError::LiveNotImplemented
                | momento_core::ConfigError::LiveGateIncomplete
        ) {
            HostError::LiveNotImplemented
        } else {
            HostError::Config(e.to_string())
        }
    })?;
    if !matches!(cfg.mode, TradingMode::Paper | TradingMode::Replay) {
        return Err(HostError::LiveNotImplemented);
    }
    if cfg.live.enabled {
        return Err(HostError::LiveNotImplemented);
    }
    Ok(cfg)
}

pub fn load_demo_config(path: &Path) -> Result<TradingConfig, HostError> {
    let cfg = peek_config(path)?;
    cfg.validate()
        .map_err(|e| HostError::Config(e.to_string()))?;
    if cfg.mode != TradingMode::Demo {
        return Err(HostError::Preflight("config mode is not demo".into()));
    }
    if cfg.live.enabled || cfg.live.confirmation == momento_core::LIVE_CONFIRMATION {
        return Err(HostError::Preflight(
            "demo mode forbids ENABLE_LIVE_TRADING".into(),
        ));
    }
    if !cfg.is_research_iti() {
        return Err(HostError::Preflight(
            "demo mode requires strategy_profile = research_iti".into(),
        ));
    }
    Ok(cfg)
}

pub fn load_live_config(path: &Path) -> Result<TradingConfig, HostError> {
    let raw = fs::read_to_string(path).map_err(|e| HostError::Io(e.to_string()))?;
    let cfg = TradingConfig::from_toml_str(&raw).map_err(|e| HostError::Config(e.to_string()))?;
    cfg.validate()
        .map_err(|e| HostError::Config(e.to_string()))?;
    if cfg.is_research_iti() {
        return Err(HostError::Preflight(
            "momento-live factory path cannot load research_iti".into(),
        ));
    }
    if !cfg.is_live_armed() {
        return Err(HostError::LiveDisarmed);
    }
    Ok(cfg)
}

pub fn load_iti_live_config(path: &Path) -> Result<TradingConfig, HostError> {
    let cfg = peek_config(path)?;
    cfg.validate()
        .map_err(|e| HostError::Config(e.to_string()))?;
    if cfg.mode != TradingMode::Live {
        return Err(HostError::Preflight(
            "ITI live config mode is not live".into(),
        ));
    }
    if !cfg.is_research_iti() {
        return Err(HostError::Preflight(
            "ITI live requires strategy_profile = research_iti".into(),
        ));
    }
    if !cfg.is_live_armed() {
        return Err(HostError::LiveDisarmed);
    }
    Ok(cfg)
}

pub fn peek_config(path: &Path) -> Result<TradingConfig, HostError> {
    let raw = fs::read_to_string(path).map_err(|e| HostError::Io(e.to_string()))?;
    TradingConfig::from_toml_str(&raw).map_err(|e| HostError::Config(e.to_string()))
}

pub fn state_file(state_dir: &Path) -> PathBuf {
    state_dir.join(STATE_FILE_NAME)
}

pub fn restore_strategy(state_dir: &Path) -> Result<MlbStrategy, HostError> {
    let path = state_file(state_dir);
    if !path.exists() {
        return Ok(MlbStrategy::new());
    }
    let raw = fs::read_to_string(&path).map_err(|e| HostError::Io(e.to_string()))?;
    let snap: MlbStrategySnapshot =
        serde_json::from_str(&raw).map_err(|e| HostError::Io(e.to_string()))?;
    Ok(MlbStrategy::restore(snap))
}

pub fn persist_strategy(state_dir: &Path, strategy: &MlbStrategy) -> Result<(), HostError> {
    fs::create_dir_all(state_dir).map_err(|e| HostError::Io(e.to_string()))?;
    let path = state_file(state_dir);
    let tmp = state_dir.join(format!("{STATE_FILE_NAME}.tmp"));
    let json = serde_json::to_string_pretty(&strategy.snapshot())
        .map_err(|e| HostError::Io(e.to_string()))?;
    fs::write(&tmp, json).map_err(|e| HostError::Io(e.to_string()))?;
    fs::rename(&tmp, path).map_err(|e| HostError::Io(e.to_string()))?;
    Ok(())
}

pub fn wnba_state_file(state_dir: &Path) -> PathBuf {
    state_dir.join(WNBA_STATE_FILE_NAME)
}

pub fn restore_wnba_strategy(state_dir: &Path) -> Result<WnbaStrategy, HostError> {
    let path = wnba_state_file(state_dir);
    if !path.exists() {
        return Ok(WnbaStrategy::new());
    }
    let raw = fs::read_to_string(&path).map_err(|e| HostError::Io(e.to_string()))?;
    let snap: WnbaStrategySnapshot =
        serde_json::from_str(&raw).map_err(|e| HostError::Io(e.to_string()))?;
    Ok(WnbaStrategy::restore(snap))
}

pub fn persist_wnba_strategy(state_dir: &Path, strategy: &WnbaStrategy) -> Result<(), HostError> {
    fs::create_dir_all(state_dir).map_err(|e| HostError::Io(e.to_string()))?;
    let path = wnba_state_file(state_dir);
    let tmp = state_dir.join(format!("{WNBA_STATE_FILE_NAME}.tmp"));
    let json = serde_json::to_string_pretty(&strategy.snapshot())
        .map_err(|e| HostError::Io(e.to_string()))?;
    fs::write(&tmp, json).map_err(|e| HostError::Io(e.to_string()))?;
    fs::rename(&tmp, path).map_err(|e| HostError::Io(e.to_string()))?;
    Ok(())
}

pub fn heartbeat_line(cfg: &TradingConfig) -> String {
    format!(
        "momento heartbeat mode={:?} live.enabled={} live_implemented=false timezone={} snapshot_tz=America/Los_Angeles interval_secs={}",
        cfg.mode, cfg.live.enabled, cfg.timezone, HEARTBEAT_SECS
    )
}

pub fn heartbeat_period() -> Duration {
    Duration::from_secs(HEARTBEAT_SECS)
}
