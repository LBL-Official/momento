//! Reproducibility envelope for a backtest run.

use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};

use momento_research_strategies::{EffectiveParameters, ExperimentOverrides};

use crate::{RUNNER_VERSION, SCHEMA_VERSION};

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct RunMetadata {
    pub run_id: String,
    pub strategy_name: String,
    pub strategy_version: u32,
    pub entry_model: String,
    pub exit_model: String,
    pub requested_series: String,
    pub normalized_series: Vec<String>,
    pub requested_season: String,
    pub normalized_season: String,
    pub requested_time_frame: String,
    pub requested_time_start: String,
    pub requested_time_end: String,
    pub original_entry_price_input: String,
    pub original_exit_price_input: String,
    pub default_parameters: EffectiveParameters,
    pub experiment_overrides: ExperimentOverrides,
    pub effective_parameters: EffectiveParameters,
    pub default_entry_range: String,
    pub effective_entry_range: String,
    pub effective_exit_rule: String,
    pub dataset_manifest_ids: Vec<String>,
    pub dataset_manifest_checksums: Vec<String>,
    pub dataset_coverage: String,
    pub schema_version: String,
    pub runner_version: String,
    pub code_build_identifier: Option<String>,
    pub created_at: DateTime<Utc>,
    pub completed_at: Option<DateTime<Utc>>,
    pub status: String,
    pub error: Option<String>,
    pub execution_model_name: String,
    pub execution_model_version: u32,
}

impl RunMetadata {
    pub fn new_base(
        run_id: String,
        strategy_name: String,
        strategy_version: u32,
        entry_model: String,
        exit_model: String,
    ) -> Self {
        Self {
            run_id,
            strategy_name,
            strategy_version,
            entry_model,
            exit_model,
            requested_series: String::new(),
            normalized_series: Vec::new(),
            requested_season: String::new(),
            normalized_season: String::new(),
            requested_time_frame: String::new(),
            requested_time_start: String::new(),
            requested_time_end: String::new(),
            original_entry_price_input: String::new(),
            original_exit_price_input: String::new(),
            default_parameters: EffectiveParameters {
                entry: momento_research_strategies::FIRST01_DEFAULT_ENTRY,
                exit: momento_research_strategies::FIRST01_DEFAULT_EXIT,
            },
            experiment_overrides: ExperimentOverrides::default(),
            effective_parameters: EffectiveParameters {
                entry: momento_research_strategies::FIRST01_DEFAULT_ENTRY,
                exit: momento_research_strategies::FIRST01_DEFAULT_EXIT,
            },
            default_entry_range: "80-83".into(),
            effective_entry_range: String::new(),
            effective_exit_rule: String::new(),
            dataset_manifest_ids: Vec::new(),
            dataset_manifest_checksums: Vec::new(),
            dataset_coverage: String::new(),
            schema_version: SCHEMA_VERSION.to_string(),
            runner_version: RUNNER_VERSION.to_string(),
            code_build_identifier: option_env!("VERGEN_GIT_SHA").map(str::to_string),
            created_at: Utc::now(),
            completed_at: None,
            status: "QUEUED".into(),
            error: None,
            execution_model_name: momento_research_execution::EXECUTION_MODEL_NAME.to_string(),
            execution_model_version: momento_research_execution::EXECUTION_MODEL_VERSION,
        }
    }
}

pub fn format_entry_range(min: u16, max: u16) -> String {
    format!("{min}-{max}")
}

pub fn format_exit_rule(params: &momento_research_strategies::ExitParameters) -> String {
    if params.loss_numerator == 1 && params.loss_denominator == 2 {
        "FIRST01 50% VWAP loss".into()
    } else {
        format!(
            "{}/{} of entry VWAP",
            params.loss_numerator, params.loss_denominator
        )
    }
}
