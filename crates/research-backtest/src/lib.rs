//! Research-only backtest control plane.
//!
//! Separates STRATEGY (FIRST01) from EXPERIMENT PARAMETERS from DATASET from
//! REPORTING. Does not submit orders and does not depend on live trading crates.

#![forbid(unsafe_code)]

pub mod config;
pub mod dataset;
pub mod error;
pub mod fixture;
pub mod metadata;
pub mod overrides;
pub mod parse;
pub mod paths;
pub mod pipeline;
pub mod registry;
pub mod results;
pub mod runner;
pub mod sheet_contract;
pub mod sheets_csv;
pub mod sheets_workspace;
pub mod state;
pub mod validation;

pub use config::BacktestConfig;
pub use dataset::validate_dataset_coverage;
pub use error::{BacktestError, BacktestErrorCode};
pub use fixture::{seed_complete_range, seed_from_sheet_inputs};
pub use metadata::RunMetadata;
pub use overrides::{
    ResolvedExperiment, first01_defaults_immutable_after_override, resolve_experiment,
};
pub use parse::{
    EntryPriceRange, ExitPriceInput, NormalizedSeason, NormalizedTimeFrame,
    parse_entry_price_range, parse_exit_price_input, parse_season, parse_series_list,
    parse_time_frame,
};
pub use paths::BacktestPaths;
pub use pipeline::{ProcessReport, process_input_workbook, process_queued_row};
pub use registry::{StrategyRegistry, resolve_strategy};
pub use results::{RunArtifacts, RunSummary, write_run_artifacts};
pub use runner::{
    BacktestResult, SignalBacktestResult, run_backtest, run_on_quotes, run_signal_backtest,
};
pub use sheet_contract::{InputRow, ResultRow, RunStatus};
pub use sheets_csv::{read_input_csv, write_input_csv, write_results_csv};
pub use sheets_workspace::{INPUT_HEADERS, SheetsWorkspace, results_headers};
pub use state::advance_status;
pub use validation::{
    FrequencyReconcileConfig, FrequencyReconcileResult, MlbValidationConfig, MlbValidationResult,
    ValidationClassification, run_frequency_reconcile, run_mlb_validation,
};

pub const RUNNER_VERSION: &str = env!("CARGO_PKG_VERSION");
pub const SCHEMA_VERSION: &str = "1.0.0";
