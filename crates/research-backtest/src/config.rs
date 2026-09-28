//! Runner configuration (research-only).

use serde::{Deserialize, Serialize};

use crate::paths::BacktestPaths;

pub const DEFAULT_INPUT_SHEET_ID: &str = "1l9t6SCUlg-ns_GvuOvRpci-AwymIalMKQoP-zP4i5Iw";
pub const DEFAULT_RESULTS_SHEET_ID: &str = "1ld4GqSgtjhYm9w5ejoOAutZKzDAjKL2wfzx--bGDo5A";
pub const DEFAULT_DRIVE_SUITE_FOLDER_ID: &str = "1WKopI1xCPIHQ7yuPs3X10M5EFVhvvZlL";

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct BacktestConfig {
    pub paths: BacktestPathsConfig,
    pub input_sheet_id: String,
    pub results_sheet_id: String,
    pub drive_suite_folder_id: String,
    pub results_spreadsheet_url: String,
    /// Reject PARTIAL/MISSING/INVALID manifests by default.
    pub allow_incomplete_data: bool,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct BacktestPathsConfig {
    pub suite_root: String,
    pub data_root: String,
}

impl Default for BacktestConfig {
    fn default() -> Self {
        let paths = BacktestPaths::from_env_or_default();
        Self {
            paths: BacktestPathsConfig {
                suite_root: paths.suite_root.display().to_string(),
                data_root: paths.research.root.display().to_string(),
            },
            input_sheet_id: std::env::var("MOMENTO_BACKTEST_INPUT_SHEET_ID")
                .unwrap_or_else(|_| DEFAULT_INPUT_SHEET_ID.to_string()),
            results_sheet_id: std::env::var("MOMENTO_BACKTEST_RESULTS_SHEET_ID")
                .unwrap_or_else(|_| DEFAULT_RESULTS_SHEET_ID.to_string()),
            drive_suite_folder_id: std::env::var("MOMENTO_BACKTEST_DRIVE_FOLDER_ID")
                .unwrap_or_else(|_| DEFAULT_DRIVE_SUITE_FOLDER_ID.to_string()),
            results_spreadsheet_url: format!(
                "https://docs.google.com/spreadsheets/d/{}/edit",
                std::env::var("MOMENTO_BACKTEST_RESULTS_SHEET_ID")
                    .unwrap_or_else(|_| DEFAULT_RESULTS_SHEET_ID.to_string())
            ),
            allow_incomplete_data: false,
        }
    }
}

impl BacktestConfig {
    pub fn paths(&self) -> BacktestPaths {
        BacktestPaths::with_roots(
            self.paths.suite_root.clone().into(),
            self.paths.data_root.clone().into(),
        )
    }
}
