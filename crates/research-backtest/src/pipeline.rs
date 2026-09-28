//! End-to-end process: sheet row → validate → replay → artifacts → results.

use chrono::Utc;

use crate::config::BacktestConfig;
use crate::dataset::{
    data_quality_from_plans, load_datasets, sports_from_series, validate_dataset_coverage,
};
use crate::error::{BacktestError, BacktestErrorCode};
use crate::metadata::{RunMetadata, format_entry_range, format_exit_rule};
use crate::overrides::resolve_experiment;
use crate::results::{RunArtifacts, load_existing_metadata, result_row_from, write_run_artifacts};
use crate::runner::run_backtest;
use crate::sheet_contract::{InputRow, ResultRow, RunStatus};
use crate::sheets_csv::{read_input_csv, read_results_csv, write_input_csv, write_results_csv};
use crate::state::{advance_status, should_process};

#[derive(Clone, Debug, Default)]
pub struct ProcessReport {
    pub processed: usize,
    pub completed: usize,
    pub invalid: usize,
    pub errors: usize,
    pub skipped_idempotent: usize,
    pub result_rows: Vec<ResultRow>,
}

pub fn process_input_workbook(config: &BacktestConfig) -> Result<ProcessReport, BacktestError> {
    let paths = config.paths();
    let input_path = paths.input_csv();
    let results_path = paths.results_csv();
    let mut rows = read_input_csv(&input_path)?;
    let mut existing_results = read_results_csv(&results_path).unwrap_or_default();
    let mut report = ProcessReport::default();

    for i in 0..rows.len() {
        if !should_process(rows[i].status) {
            continue;
        }
        report.processed += 1;
        let row = rows[i].clone();
        match process_queued_row(config, &row, &existing_results) {
            Ok(outcome) => {
                rows[i] = outcome.updated_row;
                if let Some(rr) = outcome.result_row {
                    existing_results.retain(|r| r.run_id != rr.run_id);
                    existing_results.push(rr.clone());
                    report.result_rows.push(rr);
                }
                match rows[i].status {
                    RunStatus::Complete => report.completed += 1,
                    RunStatus::Invalid => report.invalid += 1,
                    RunStatus::Error => report.errors += 1,
                    _ => {}
                }
                if outcome.idempotent {
                    report.skipped_idempotent += 1;
                }
            }
            Err(err) => {
                rows[i].status = RunStatus::Error;
                rows[i].error = format!("{}: {err}", err.code_str());
                rows[i].completed_at = Some(Utc::now());
                report.errors += 1;
            }
        }
        write_input_csv(&input_path, &rows)?;
        write_results_csv(&results_path, &existing_results)?;
    }
    Ok(report)
}

pub struct RowOutcome {
    pub updated_row: InputRow,
    pub result_row: Option<ResultRow>,
    pub artifacts: Option<RunArtifacts>,
    pub idempotent: bool,
}

pub fn process_queued_row(
    config: &BacktestConfig,
    row: &InputRow,
    existing_results: &[ResultRow],
) -> Result<RowOutcome, BacktestError> {
    let mut updated = row.clone();
    updated.ensure_run_id();
    if updated.submitted_at.is_none() {
        updated.submitted_at = Some(Utc::now());
    }

    // Idempotency: COMPLETE run_id must not re-run.
    if let Some(existing) = existing_results.iter().find(|r| r.run_id == updated.run_id) {
        if existing.run_status == RunStatus::Complete.as_str() {
            updated.status = RunStatus::Complete;
            updated.result_spreadsheet = config.results_spreadsheet_url.clone();
            updated.error.clear();
            return Ok(RowOutcome {
                updated_row: updated,
                result_row: Some(existing.clone()),
                artifacts: None,
                idempotent: true,
            });
        }
    }
    let paths = config.paths();
    if let Some(meta) = load_existing_metadata(&paths, "FIRST01", &updated.run_id) {
        if meta.status == RunStatus::Complete.as_str() {
            updated.status = RunStatus::Complete;
            updated.result_spreadsheet = config.results_spreadsheet_url.clone();
            return Ok(RowOutcome {
                updated_row: updated,
                result_row: None,
                artifacts: None,
                idempotent: true,
            });
        }
    }

    updated.status = advance_status(RunStatus::Queued, RunStatus::Validating)?;
    let experiment = match resolve_experiment(&updated) {
        Ok(e) => e,
        Err(err) => {
            updated.status = RunStatus::Invalid;
            updated.error = format!("{}: {err}", err.code_str());
            updated.completed_at = Some(Utc::now());
            return Ok(RowOutcome {
                updated_row: updated,
                result_row: None,
                artifacts: None,
                idempotent: false,
            });
        }
    };
    updated.run_id = experiment.run_id.clone();

    let mut paths = config
        .paths()
        .with_season_label(experiment.season.label.clone());
    let sports = sports_from_series(&experiment.series)?;
    let plans = match validate_dataset_coverage(
        &paths.research,
        &sports,
        experiment.time_frame.start,
        experiment.time_frame.end,
        config.allow_incomplete_data,
    ) {
        Ok(p) => p,
        Err(err) => {
            updated.status = match err.code() {
                Some(BacktestErrorCode::DatasetMissing)
                | Some(BacktestErrorCode::DatasetPartial)
                | Some(BacktestErrorCode::DatasetInvalid) => RunStatus::Invalid,
                _ => RunStatus::Error,
            };
            updated.error = format!("{}: {err}", err.code_str());
            updated.completed_at = Some(Utc::now());
            return Ok(RowOutcome {
                updated_row: updated,
                result_row: None,
                artifacts: None,
                idempotent: false,
            });
        }
    };

    updated.status = advance_status(RunStatus::Validating, RunStatus::Running)?;
    updated.started_at = Some(Utc::now());
    let started = updated.started_at.unwrap();

    let mut all_datasets = Vec::new();
    for plan in &plans {
        all_datasets.extend(load_datasets(&paths.research, plan)?);
    }

    let data_quality = data_quality_from_plans(&plans);
    let result = run_backtest(&experiment, &all_datasets, data_quality)?;

    let mut meta = RunMetadata::new_base(
        experiment.run_id.clone(),
        experiment.entry_model.name.clone(),
        experiment.entry_model.version,
        experiment.entry_model.name.clone(),
        experiment.exit_model.name.clone(),
    );
    meta.requested_series = updated.ticker.clone();
    meta.normalized_series = experiment.series.clone();
    meta.requested_season = experiment.season.original.clone();
    meta.normalized_season = experiment.season.label.clone();
    meta.requested_time_frame = experiment.time_frame.original.clone();
    meta.requested_time_start = experiment.time_frame.start.to_string();
    meta.requested_time_end = experiment.time_frame.end.to_string();
    meta.original_entry_price_input = experiment.original_entry_price_input.clone();
    meta.original_exit_price_input = experiment.original_exit_price_input.clone();
    meta.default_parameters = experiment.default_parameters.clone();
    meta.experiment_overrides = experiment.overrides.clone();
    meta.effective_parameters = experiment.effective_parameters.clone();
    meta.default_entry_range = "80-83".into();
    meta.effective_entry_range = format_entry_range(
        experiment.effective_parameters.entry.first_threshold_cents,
        experiment
            .effective_parameters
            .entry
            .maximum_entry_price_cents,
    );
    meta.effective_exit_rule = format_exit_rule(&experiment.effective_parameters.exit);
    meta.dataset_manifest_ids = plans.iter().flat_map(|p| p.manifest_ids.clone()).collect();
    meta.dataset_manifest_checksums = plans.iter().map(|p| p.checksum_digest.clone()).collect();
    meta.dataset_coverage = plans
        .iter()
        .map(|p| format!("{}:{}", p.sport.dir_name(), p.coverage))
        .collect::<Vec<_>>()
        .join("; ");
    meta.status = RunStatus::Complete.as_str().to_string();
    meta.completed_at = Some(Utc::now());
    meta.created_at = started;

    let artifacts = write_run_artifacts(&paths, &meta, &result)?;
    let duration = {
        let end = meta.completed_at.unwrap_or_else(Utc::now);
        format!("{}s", (end - started).num_seconds())
    };
    let rr = result_row_from(&meta, &result, &artifacts, duration);

    updated.status = RunStatus::Complete;
    updated.completed_at = meta.completed_at;
    updated.result_spreadsheet = config.results_spreadsheet_url.clone();
    updated.error.clear();

    // silence unused mut for paths if season already set
    let _ = &mut paths;

    Ok(RowOutcome {
        updated_row: updated,
        result_row: Some(rr),
        artifacts: Some(artifacts),
        idempotent: false,
    })
}
