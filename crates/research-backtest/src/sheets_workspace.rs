//! Google Sheets identity + sync notes for the control plane.
//!
//! Live cell I/O is performed by Cursor's Google Sheets MCP when authenticated.
//! The Rust runner uses local CSV mirrors under `Backtesting Suite/Google Sheets/`
//! so backtests remain deterministic without network/OAuth at runtime.

use serde::{Deserialize, Serialize};

use crate::config::{
    DEFAULT_DRIVE_SUITE_FOLDER_ID, DEFAULT_INPUT_SHEET_ID, DEFAULT_RESULTS_SHEET_ID,
};

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct SheetsWorkspace {
    pub suite_folder_id: String,
    pub input_spreadsheet_id: String,
    pub results_spreadsheet_id: String,
    pub input_url: String,
    pub results_url: String,
}

impl Default for SheetsWorkspace {
    fn default() -> Self {
        Self::from_defaults()
    }
}

impl SheetsWorkspace {
    pub fn from_defaults() -> Self {
        let input = std::env::var("MOMENTO_BACKTEST_INPUT_SHEET_ID")
            .unwrap_or_else(|_| DEFAULT_INPUT_SHEET_ID.to_string());
        let results = std::env::var("MOMENTO_BACKTEST_RESULTS_SHEET_ID")
            .unwrap_or_else(|_| DEFAULT_RESULTS_SHEET_ID.to_string());
        Self {
            suite_folder_id: std::env::var("MOMENTO_BACKTEST_DRIVE_FOLDER_ID")
                .unwrap_or_else(|_| DEFAULT_DRIVE_SUITE_FOLDER_ID.to_string()),
            input_url: format!("https://docs.google.com/spreadsheets/d/{input}/edit"),
            results_url: format!("https://docs.google.com/spreadsheets/d/{results}/edit"),
            input_spreadsheet_id: input,
            results_spreadsheet_id: results,
        }
    }
}

/// Canonical Input header row (columns A–N).
pub const INPUT_HEADERS: [&str; 14] = [
    "Run ID",
    "Ticker",
    "Season",
    "Time Frame",
    "Entry Condition - Price Range",
    "Entry Condition - Model",
    "Exit Condition - Price Range",
    "Exit Condition - Model",
    "Status",
    "Submitted At",
    "Started At",
    "Completed At",
    "Result Spreadsheet",
    "Error",
];

/// Results headers including future metrics placeholders (signal-only blanks today).
pub fn results_headers() -> Vec<&'static str> {
    vec![
        "Run ID",
        "Strategy",
        "Strategy Version",
        "Entry Model",
        "Exit Model",
        "Ticker/Series",
        "Season",
        "Time Start",
        "Time End",
        "Entry Price Override",
        "Effective Entry Range",
        "Exit Price Override",
        "Effective Exit Rule",
        "Dataset Coverage",
        "Dataset Manifest Checksum",
        "Entry Signals",
        "Exit Signals",
        "First Entry Timestamp",
        "Last Entry Timestamp",
        "Run Status",
        "Run Duration",
        "Artifacts Location",
        "Metadata Location",
        "Error",
        "Gross PNL",
        "PNL After Fees",
        "W-L",
        "Win Rate",
        "RR",
        "Trade Frequency %",
        "Max Drawdown",
        "Volatility",
        "Downside Deviation",
        "Sharpe Ratio",
        "Sortino Ratio",
        "Calmar Ratio",
        "Number of Trades",
        "Profit Factor",
        "Expectancy",
        "Median Trade",
        "Time in Market",
        "Fees",
        "Slippage",
        "Drawdown Duration",
        "Drawdown Recovery Time",
        "Number of Drawdowns",
        "Holding Period",
        "out-of-sample results",
        "walk-forward results",
        "parameter sensitivity",
        "position sizing",
        "liquidity constraints",
        "fills",
        "market impact",
        "look-ahead bias",
        "survivorship bias",
        "missing-data checks",
    ]
}
