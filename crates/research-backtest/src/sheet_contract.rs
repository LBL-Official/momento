//! Google Sheet row contracts for input and results.

use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum RunStatus {
    Queued,
    Validating,
    Running,
    Complete,
    Error,
    Invalid,
}

impl RunStatus {
    pub fn as_str(self) -> &'static str {
        match self {
            Self::Queued => "QUEUED",
            Self::Validating => "VALIDATING",
            Self::Running => "RUNNING",
            Self::Complete => "COMPLETE",
            Self::Error => "ERROR",
            Self::Invalid => "INVALID",
        }
    }

    pub fn parse(raw: &str) -> Option<Self> {
        match raw.trim().to_uppercase().as_str() {
            "" | "QUEUED" => Some(Self::Queued),
            "VALIDATING" => Some(Self::Validating),
            "RUNNING" => Some(Self::Running),
            "COMPLETE" => Some(Self::Complete),
            "ERROR" => Some(Self::Error),
            "INVALID" => Some(Self::Invalid),
            _ => None,
        }
    }
}

/// Canonical Backtesting Input row (columns A–N).
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct InputRow {
    pub run_id: String,
    pub ticker: String,
    pub season: String,
    pub time_frame: String,
    pub entry_price_range: String,
    pub entry_model: String,
    pub exit_price_range: String,
    pub exit_model: String,
    pub status: RunStatus,
    pub submitted_at: Option<DateTime<Utc>>,
    pub started_at: Option<DateTime<Utc>>,
    pub completed_at: Option<DateTime<Utc>>,
    pub result_spreadsheet: String,
    pub error: String,
    /// 0-based data row index in the workbook (excludes header).
    pub row_index: usize,
}

impl InputRow {
    pub fn ensure_run_id(&mut self) -> &str {
        if self.run_id.trim().is_empty() {
            self.run_id = uuid::Uuid::new_v4().to_string();
        }
        &self.run_id
    }
}

/// Summary row written to Backtesting Results.
#[derive(Clone, Debug, Default, PartialEq, Serialize, Deserialize)]
pub struct ResultRow {
    pub run_id: String,
    pub strategy: String,
    pub strategy_version: u32,
    pub entry_model: String,
    pub exit_model: String,
    pub ticker_series: String,
    pub season: String,
    pub time_start: String,
    pub time_end: String,
    pub entry_price_override: String,
    pub effective_entry_range: String,
    pub exit_price_override: String,
    pub effective_exit_rule: String,
    pub dataset_coverage: String,
    pub dataset_manifest_checksum: String,
    pub quote_observations: u64,
    pub entry_opportunities: u64,
    pub entry_intents: u64,
    /// Legacy alias — equals [`entry_intents`] (never raw quote count).
    pub entry_signals: u64,
    pub exit_signals: u64,
    pub entry_orders: u64,
    pub entry_fills: u64,
    pub entry_fill_rate: String,
    pub contracts_requested: u64,
    pub contracts_filled: u64,
    pub average_entry: String,
    pub average_exit: String,
    pub stop_triggers: u64,
    pub successful_exits: u64,
    pub failed_exits: u64,
    pub realized_pnl: String,
    pub unrealized_pnl: String,
    pub net_pnl: String,
    pub data_quality: String,
    pub first_entry_timestamp: String,
    pub last_entry_timestamp: String,
    pub run_status: String,
    pub run_duration: String,
    pub artifacts_location: String,
    pub metadata_location: String,
    pub error: String,
    // Future metrics placeholders (signal-only runner leaves these blank).
    pub gross_pnl: String,
    pub pnl_after_fees: String,
    pub w_l: String,
    pub win_rate: String,
    pub rr: String,
    pub trade_frequency_pct: String,
    pub max_drawdown: String,
    pub volatility: String,
    pub downside_deviation: String,
    pub sharpe_ratio: String,
    pub sortino_ratio: String,
    pub calmar_ratio: String,
    pub number_of_trades: String,
    pub opportunities_per_day: String,
    pub trades_per_day: String,
    pub profit_factor: String,
    pub expectancy: String,
    pub median_trade: String,
    pub time_in_market: String,
    pub fees: String,
    pub slippage: String,
    pub drawdown_duration: String,
    pub drawdown_recovery_time: String,
    pub number_of_drawdowns: String,
    pub holding_period: String,
    pub out_of_sample_results: String,
    pub walk_forward_results: String,
    pub parameter_sensitivity: String,
    pub position_sizing: String,
    pub liquidity_constraints: String,
    pub fills: String,
    pub market_impact: String,
    pub look_ahead_bias: String,
    pub survivorship_bias: String,
    pub missing_data_checks: String,
}
