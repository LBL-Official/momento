//! Worker configuration. Live arming needs both gates and still cannot
//! submit: this build links no submission adapter.

use std::path::{Path, PathBuf};

use momento_strategy_nba::ConfigMode;
use serde::Deserialize;

pub const LIVE_CONFIRMATION: &str = "ENABLE_LIVE_TRADING";

#[derive(Clone, Debug, Deserialize)]
pub struct Config {
    pub mode: String,
    pub contract_path: PathBuf,
    #[serde(default = "d_tick")]
    pub tick_seconds: u64,
    #[serde(default = "d_discovery")]
    pub discovery_seconds: i64,
    #[serde(default = "d_account")]
    pub account_seconds: i64,
    #[serde(default = "d_backfill")]
    pub backfill_hours_before_start: i64,
    #[serde(default = "d_active")]
    pub active_minutes_before_start: i64,
    #[serde(default = "d_clock_age")]
    pub clock_max_age_seconds: i64,
    #[serde(default = "d_series")]
    pub series: String,
    #[serde(default)]
    pub live: LiveGates,
    #[serde(default)]
    pub collateral: Collateral,
    #[serde(default)]
    pub capital: Capital,
}

#[derive(Clone, Debug, Default, Deserialize)]
pub struct LiveGates {
    #[serde(default)]
    pub enabled: bool,
    #[serde(default)]
    pub confirmation: String,
}

#[derive(Clone, Debug, Default, Deserialize)]
pub struct Collateral {
    /// Evidence of a separate subaccount or shard. Empty = none.
    #[serde(default)]
    pub isolation_evidence: String,
    /// Account-wide reservation ledger every submitter honours. Empty = none.
    #[serde(default)]
    pub reservation_ledger: String,
    /// Other processes that can spend the same collateral.
    #[serde(default)]
    pub shared_credential_submitters: Vec<String>,
}

#[derive(Clone, Debug, Deserialize)]
pub struct Capital {
    pub reference_capital_cents: i64,
    pub funded_target_cents: i64,
    pub external_reserve_cents: i64,
}

impl Default for Capital {
    fn default() -> Self {
        Self {
            reference_capital_cents: 2_000_000,
            funded_target_cents: 500_000,
            external_reserve_cents: 1_500_000,
        }
    }
}

fn d_tick() -> u64 {
    15
}
fn d_discovery() -> i64 {
    300
}
fn d_account() -> i64 {
    60
}
fn d_backfill() -> i64 {
    24
}
fn d_active() -> i64 {
    30
}
fn d_clock_age() -> i64 {
    90
}
fn d_series() -> String {
    "KXNBAGAME".into()
}

impl Config {
    pub fn load(path: &Path) -> Result<Self, String> {
        let raw =
            std::fs::read_to_string(path).map_err(|e| format!("config {}: {e}", path.display()))?;
        let cfg: Config = toml::from_str(&raw).map_err(|e| format!("config parse: {e}"))?;
        cfg.config_mode()?;
        if cfg.tick_seconds < 5 {
            return Err("tick_seconds must be >= 5".into());
        }
        Ok(cfg)
    }

    pub fn config_mode(&self) -> Result<ConfigMode, String> {
        match self.mode.as_str() {
            "live_data_only" => Ok(ConfigMode::LiveDataOnly),
            "shadow" => Ok(ConfigMode::Shadow),
            "first78_live_v1" => Ok(ConfigMode::First78LiveV1),
            "live" => Ok(ConfigMode::Live),
            other => Err(format!("unknown mode {other}")),
        }
    }

    pub fn live_gates_set(&self) -> bool {
        self.live.enabled && self.live.confirmation == LIVE_CONFIRMATION
    }
}
