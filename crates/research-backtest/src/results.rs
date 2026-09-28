//! Local run artifact storage (JSON under Runs/STRATEGY/...).

use std::fs;
use std::path::{Path, PathBuf};

use chrono::Utc;
use serde::{Deserialize, Serialize};

use momento_research_execution::{RunMetrics, write_execution_artifacts};
use momento_research_strategies::{EntrySignal, ExitSignal};

use crate::error::{BacktestError, BacktestErrorCode};
use crate::metadata::RunMetadata;
use crate::paths::BacktestPaths;
use crate::runner::BacktestResult;

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct RunSummary {
    pub run_id: String,
    pub strategy: String,
    pub strategy_version: u32,
    pub execution_model_name: String,
    pub execution_model_version: u32,
    pub quote_observations: u64,
    pub entry_opportunities: u64,
    pub entry_intents: u64,
    /// Legacy alias — equals [`entry_intents`].
    pub entry_signal_count: u64,
    pub exit_signal_count: u64,
    pub entry_orders: u64,
    pub entry_fills: u64,
    pub entry_fill_rate: f64,
    pub exit_orders: u64,
    pub exit_fills: u64,
    pub contracts_requested: u64,
    pub contracts_filled: u64,
    pub average_entry_price_cents: Option<u16>,
    pub average_exit_price_cents: Option<u16>,
    pub positions_opened: u64,
    pub positions_closed: u64,
    pub positions_open_at_end: u64,
    pub gross_pnl_cents: i64,
    pub unrealized_pnl_cents: i64,
    pub net_pnl_cents: i64,
    pub fees_status: String,
    pub max_drawdown_cents: i64,
    pub stop_trigger_count: u64,
    pub failed_exit_attempts: u64,
    pub execution_data_quality: String,
    pub quotes_observed: u64,
    pub events_processed: u64,
    pub sequence_gap_rejects: u64,
    pub metrics: RunMetrics,
    pub note: String,
}

#[derive(Clone, Debug)]
pub struct RunArtifacts {
    pub run_dir: PathBuf,
    pub metadata_path: PathBuf,
    pub summary_path: PathBuf,
    pub entry_signals_path: PathBuf,
    pub exit_signals_path: PathBuf,
    pub events_path: PathBuf,
    pub manifest_path: PathBuf,
    pub execution_orders_path: PathBuf,
    pub execution_fills_path: PathBuf,
    pub execution_positions_path: PathBuf,
    pub pnl_summary_path: PathBuf,
}

pub fn write_run_artifacts(
    paths: &BacktestPaths,
    meta: &RunMetadata,
    result: &BacktestResult,
) -> Result<RunArtifacts, BacktestError> {
    let run_dir = paths.run_dir(&meta.strategy_name, &meta.run_id, meta.created_at);
    fs::create_dir_all(&run_dir).map_err(|e| {
        BacktestError::coded(
            BacktestErrorCode::ResultWriteError,
            format!("mkdir {}: {e}", run_dir.display()),
        )
    })?;

    let metadata_path = run_dir.join("metadata.json");
    let summary_path = run_dir.join("summary.json");
    let entry_signals_path = run_dir.join("entry_signals.json");
    let exit_signals_path = run_dir.join("exit_signals.json");
    let events_path = run_dir.join("events.json");
    let manifest_path = run_dir.join("manifest.json");

    write_json(&metadata_path, meta)?;

    let m = &result.execution.metrics;
    let summary = RunSummary {
        run_id: meta.run_id.clone(),
        strategy: meta.strategy_name.clone(),
        strategy_version: meta.strategy_version,
        execution_model_name: meta.execution_model_name.clone(),
        execution_model_version: meta.execution_model_version,
        entry_signal_count: m.entry_intents,
        quote_observations: m.quote_observations,
        entry_opportunities: m.entry_opportunities,
        entry_intents: m.entry_intents,
        exit_signal_count: m.exit_signals,
        entry_orders: m.entry_orders,
        entry_fills: m.entry_fills,
        entry_fill_rate: m.entry_fill_rate,
        exit_orders: m.exit_orders,
        exit_fills: m.exit_fills,
        contracts_requested: m.contracts_requested,
        contracts_filled: m.contracts_filled,
        average_entry_price_cents: m.average_entry_price_cents,
        average_exit_price_cents: m.average_exit_price_cents,
        positions_opened: m.positions_opened,
        positions_closed: m.positions_closed,
        positions_open_at_end: m.positions_open_at_end,
        gross_pnl_cents: m.gross_pnl_cents,
        unrealized_pnl_cents: m.unrealized_pnl_cents,
        net_pnl_cents: m.net_pnl_cents,
        fees_status: m.fees_status.clone(),
        max_drawdown_cents: m.max_drawdown_cents,
        stop_trigger_count: m.stop_trigger_count,
        failed_exit_attempts: m.failed_exit_attempts,
        execution_data_quality: m.data_quality.execution_data_quality.clone(),
        quotes_observed: result.execution.quotes_observed,
        events_processed: result.execution.events_processed,
        sequence_gap_rejects: result.execution.sequence_gap_rejects,
        metrics: m.clone(),
        note: "Execution simulator: signals distinct from fills.".into(),
    };
    write_json(&summary_path, &summary)?;
    fs::create_dir_all(run_dir.join("signals")).map_err(|e| {
        BacktestError::coded(
            BacktestErrorCode::ResultWriteError,
            format!("mkdir signals: {e}"),
        )
    })?;
    write_json(
        &run_dir.join("signals/quote_observations.json"),
        &result.execution.quote_observations,
    )?;
    write_json(
        &run_dir.join("signals/opportunities.json"),
        &result.execution.entry_opportunities,
    )?;
    write_json(
        &run_dir.join("signals/entry_intents.json"),
        &result.execution.entry_intents,
    )?;
    write_json(&entry_signals_path, &result.execution.entry_intents)?;
    write_json(
        &run_dir.join("signals/entry_signals.json"),
        &result.execution.entry_signals,
    )?;
    write_json(&exit_signals_path, &result.execution.exit_signals)?;

    let exec_artifacts =
        write_execution_artifacts(&run_dir, &result.execution, &result.execution.final_marks)
            .map_err(|e| {
                BacktestError::coded(
                    BacktestErrorCode::ResultWriteError,
                    format!("execution artifacts: {e}"),
                )
            })?;

    let events = EventsFile {
        schema: "execution_events_v1",
        entry_signals: result.execution.entry_signals.clone(),
        exit_signals: result.execution.exit_signals.clone(),
        written_at: Utc::now(),
    };
    write_json(&events_path, &events)?;

    let run_manifest = serde_json::json!({
        "run_id": meta.run_id,
        "strategy": meta.strategy_name,
        "strategy_version": meta.strategy_version,
        "execution_model_name": meta.execution_model_name,
        "execution_model_version": meta.execution_model_version,
        "files": [
            "metadata.json",
            "summary.json",
            "entry_signals.json",
            "exit_signals.json",
            "events.json",
            "manifest.json",
            "signals/quote_observations.json",
            "signals/opportunities.json",
            "signals/entry_intents.json",
            "signals/entry_signals.json",
            "signals/exit_signals.json",
            "execution/orders.json",
            "execution/fills.json",
            "execution/positions.json",
            "pnl/realized.json",
            "pnl/summary.json"
        ],
        "dataset_manifest_ids": meta.dataset_manifest_ids,
        "dataset_manifest_checksums": meta.dataset_manifest_checksums,
        "runner_version": meta.runner_version,
        "schema_version": meta.schema_version,
    });
    write_json(&manifest_path, &run_manifest)?;

    Ok(RunArtifacts {
        run_dir,
        metadata_path,
        summary_path,
        entry_signals_path,
        exit_signals_path,
        events_path,
        manifest_path,
        execution_orders_path: exec_artifacts.orders_path,
        execution_fills_path: exec_artifacts.fills_path,
        execution_positions_path: exec_artifacts.positions_path,
        pnl_summary_path: exec_artifacts.pnl_summary_path,
    })
}

#[derive(Serialize, Deserialize)]
struct EventsFile {
    schema: &'static str,
    entry_signals: Vec<EntrySignal>,
    exit_signals: Vec<ExitSignal>,
    written_at: chrono::DateTime<Utc>,
}

fn write_json<T: Serialize>(path: &Path, value: &T) -> Result<(), BacktestError> {
    let body = serde_json::to_string_pretty(value).map_err(|e| {
        BacktestError::coded(
            BacktestErrorCode::ResultWriteError,
            format!("json encode {}: {e}", path.display()),
        )
    })?;
    let tmp = path.with_extension("json.tmp");
    fs::write(&tmp, body)?;
    fs::rename(&tmp, path)?;
    Ok(())
}

pub fn load_existing_metadata(
    paths: &BacktestPaths,
    strategy: &str,
    run_id: &str,
) -> Option<RunMetadata> {
    let root = paths.runs_root().join(strategy);
    if !root.exists() {
        return None;
    }
    find_metadata_by_run_id(&root, run_id)
}

fn find_metadata_by_run_id(dir: &Path, run_id: &str) -> Option<RunMetadata> {
    let entries = fs::read_dir(dir).ok()?;
    for entry in entries.flatten() {
        let path = entry.path();
        if path.is_dir() {
            if let Some(m) = find_metadata_by_run_id(&path, run_id) {
                return Some(m);
            }
            continue;
        }
        if path.file_name()?.to_string_lossy() == "metadata.json" {
            if let Ok(body) = fs::read_to_string(&path) {
                if let Ok(meta) = serde_json::from_str::<RunMetadata>(&body) {
                    if meta.run_id == run_id {
                        return Some(meta);
                    }
                }
            }
        }
    }
    None
}

fn format_cents(cents: i64) -> String {
    let dollars = cents / 100;
    let rem = (cents % 100).unsigned_abs();
    format!("${dollars}.{rem:02}")
}

pub fn result_row_from(
    meta: &RunMetadata,
    result: &BacktestResult,
    artifacts: &RunArtifacts,
    duration: String,
) -> crate::sheet_contract::ResultRow {
    let m = &result.execution.metrics;
    crate::sheet_contract::ResultRow {
        run_id: meta.run_id.clone(),
        strategy: meta.strategy_name.clone(),
        strategy_version: meta.strategy_version,
        entry_model: meta.entry_model.clone(),
        exit_model: meta.exit_model.clone(),
        ticker_series: meta.normalized_series.join(", "),
        season: meta.normalized_season.clone(),
        time_start: meta.requested_time_start.clone(),
        time_end: meta.requested_time_end.clone(),
        entry_price_override: meta.original_entry_price_input.clone(),
        effective_entry_range: meta.effective_entry_range.clone(),
        exit_price_override: meta.original_exit_price_input.clone(),
        effective_exit_rule: meta.effective_exit_rule.clone(),
        dataset_coverage: meta.dataset_coverage.clone(),
        dataset_manifest_checksum: meta.dataset_manifest_checksums.join(";"),
        quote_observations: m.quote_observations,
        entry_opportunities: m.entry_opportunities,
        entry_intents: m.entry_intents,
        entry_signals: m.entry_intents,
        exit_signals: m.exit_signals,
        entry_orders: m.entry_orders,
        entry_fills: m.entry_fills,
        entry_fill_rate: format!("{:.2}%", m.entry_fill_rate * 100.0),
        contracts_requested: m.contracts_requested,
        contracts_filled: m.contracts_filled,
        average_entry: m
            .average_entry_price_cents
            .map(|c| format!("{c}¢"))
            .unwrap_or_default(),
        average_exit: m
            .average_exit_price_cents
            .map(|c| format!("{c}¢"))
            .unwrap_or_default(),
        stop_triggers: m.stop_trigger_count,
        successful_exits: m.exit_fills,
        failed_exits: m.failed_exit_attempts,
        realized_pnl: format_cents(m.gross_pnl_cents),
        unrealized_pnl: format_cents(m.unrealized_pnl_cents),
        net_pnl: format_cents(m.net_pnl_cents),
        max_drawdown: format_cents(m.max_drawdown_cents),
        data_quality: m.data_quality.execution_data_quality.clone(),
        first_entry_timestamp: result
            .execution
            .first_entry_exchange_ms
            .map(crate::runner::ms_to_rfc3339)
            .unwrap_or_default(),
        last_entry_timestamp: result
            .execution
            .last_entry_exchange_ms
            .map(crate::runner::ms_to_rfc3339)
            .unwrap_or_default(),
        run_status: meta.status.clone(),
        run_duration: duration,
        artifacts_location: artifacts.run_dir.display().to_string(),
        metadata_location: artifacts.metadata_path.display().to_string(),
        error: meta.error.clone().unwrap_or_default(),
        gross_pnl: format_cents(m.gross_pnl_cents),
        pnl_after_fees: format_cents(m.net_pnl_cents),
        number_of_trades: m.positions_closed.to_string(),
        opportunities_per_day: String::new(),
        trades_per_day: String::new(),
        fees: m.fees_status.clone(),
        fills: format!(
            "entry_orders={} entry_fills={} exit_fills={}",
            m.entry_orders, m.entry_fills, m.exit_fills
        ),
        look_ahead_bias: "exchange_timestamp chronological; no future quotes".into(),
        missing_data_checks: meta.dataset_coverage.clone(),
        ..crate::sheet_contract::ResultRow::default()
    }
}
