//! CSV sync contract for Backtesting Input / Results workbooks.
//!
//! Google Drive MCP has no cell-write API. The runner reads/writes local CSV
//! mirrors under `Backtesting Suite/Google Sheets/` which can be imported into
//! the Drive spreadsheets (or replaced via Drive create/export).

use std::fs::File;
use std::io::{BufReader, BufWriter};
use std::path::Path;

use chrono::{DateTime, Utc};
use serde::Deserialize;

use crate::error::{BacktestError, BacktestErrorCode};
use crate::sheet_contract::{InputRow, ResultRow, RunStatus};

#[derive(Debug, Deserialize)]
struct InputCsvRecord {
    #[serde(rename = "Run ID")]
    run_id: String,
    #[serde(rename = "Ticker")]
    ticker: String,
    #[serde(rename = "Season")]
    season: String,
    #[serde(rename = "Time Frame")]
    time_frame: String,
    #[serde(rename = "Entry Condition - Price Range")]
    entry_price_range: String,
    #[serde(rename = "Entry Condition - Model")]
    entry_model: String,
    #[serde(rename = "Exit Condition - Price Range")]
    exit_price_range: String,
    #[serde(rename = "Exit Condition - Model")]
    exit_model: String,
    #[serde(rename = "Status")]
    status: String,
    #[serde(rename = "Submitted At")]
    submitted_at: String,
    #[serde(rename = "Started At")]
    started_at: String,
    #[serde(rename = "Completed At")]
    completed_at: String,
    #[serde(rename = "Result Spreadsheet")]
    result_spreadsheet: String,
    #[serde(rename = "Error")]
    error: String,
}

fn parse_opt_ts(raw: &str) -> Option<DateTime<Utc>> {
    let t = raw.trim();
    if t.is_empty() {
        return None;
    }
    DateTime::parse_from_rfc3339(t)
        .ok()
        .map(|d| d.with_timezone(&Utc))
}

pub fn read_input_csv(path: &Path) -> Result<Vec<InputRow>, BacktestError> {
    let file = File::open(path).map_err(|e| {
        BacktestError::coded(
            BacktestErrorCode::GoogleSheetsError,
            format!("open input csv {}: {e}", path.display()),
        )
    })?;
    let mut rdr = csv::ReaderBuilder::new()
        .flexible(true)
        .trim(csv::Trim::All)
        .from_reader(BufReader::new(file));
    let mut rows = Vec::new();
    for (idx, rec) in rdr.deserialize::<InputCsvRecord>().enumerate() {
        let rec = rec?;
        if rec.ticker.trim().is_empty() && rec.entry_model.trim().is_empty() {
            continue;
        }
        let status = RunStatus::parse(&rec.status).ok_or_else(|| {
            BacktestError::coded(
                BacktestErrorCode::InvalidStatus,
                format!("unknown status '{}'", rec.status),
            )
        })?;
        rows.push(InputRow {
            run_id: rec.run_id,
            ticker: rec.ticker,
            season: rec.season,
            time_frame: rec.time_frame,
            entry_price_range: rec.entry_price_range,
            entry_model: rec.entry_model,
            exit_price_range: rec.exit_price_range,
            exit_model: rec.exit_model,
            status,
            submitted_at: parse_opt_ts(&rec.submitted_at),
            started_at: parse_opt_ts(&rec.started_at),
            completed_at: parse_opt_ts(&rec.completed_at),
            result_spreadsheet: rec.result_spreadsheet,
            error: rec.error,
            row_index: idx,
        });
    }
    Ok(rows)
}

pub fn write_input_csv(path: &Path, rows: &[InputRow]) -> Result<(), BacktestError> {
    if let Some(parent) = path.parent() {
        std::fs::create_dir_all(parent)?;
    }
    let file = File::create(path)?;
    let mut wtr = csv::Writer::from_writer(BufWriter::new(file));
    wtr.write_record([
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
    ])?;
    for row in rows {
        wtr.write_record([
            row.run_id.as_str(),
            row.ticker.as_str(),
            row.season.as_str(),
            row.time_frame.as_str(),
            row.entry_price_range.as_str(),
            row.entry_model.as_str(),
            row.exit_price_range.as_str(),
            row.exit_model.as_str(),
            row.status.as_str(),
            &row.submitted_at.map(|t| t.to_rfc3339()).unwrap_or_default(),
            &row.started_at.map(|t| t.to_rfc3339()).unwrap_or_default(),
            &row.completed_at.map(|t| t.to_rfc3339()).unwrap_or_default(),
            row.result_spreadsheet.as_str(),
            row.error.as_str(),
        ])?;
    }
    wtr.flush()?;
    Ok(())
}

pub fn write_results_csv(path: &Path, rows: &[ResultRow]) -> Result<(), BacktestError> {
    if let Some(parent) = path.parent() {
        std::fs::create_dir_all(parent)?;
    }
    let file = File::create(path)?;
    let mut wtr = csv::Writer::from_writer(BufWriter::new(file));
    wtr.write_record([
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
        "Quote Observations",
        "Entry Opportunities",
        "Entry Intents",
        "Entry Signals (legacy=intents)",
        "Exit Signals",
        "Entry Orders",
        "Entry Fills",
        "Entry Fill Rate",
        "Contracts Requested",
        "Contracts Filled",
        "Average Entry",
        "Average Exit",
        "Stop Triggers",
        "Successful Exits",
        "Failed Exits",
        "Realized P&L",
        "Unrealized P&L",
        "Net P&L",
        "Max Drawdown",
        "Data Quality",
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
    ])?;
    for r in rows {
        wtr.write_record([
            r.run_id.as_str(),
            r.strategy.as_str(),
            &r.strategy_version.to_string(),
            r.entry_model.as_str(),
            r.exit_model.as_str(),
            r.ticker_series.as_str(),
            r.season.as_str(),
            r.time_start.as_str(),
            r.time_end.as_str(),
            r.entry_price_override.as_str(),
            r.effective_entry_range.as_str(),
            r.exit_price_override.as_str(),
            r.effective_exit_rule.as_str(),
            r.dataset_coverage.as_str(),
            r.dataset_manifest_checksum.as_str(),
            &r.quote_observations.to_string(),
            &r.entry_opportunities.to_string(),
            &r.entry_intents.to_string(),
            &r.entry_signals.to_string(),
            &r.exit_signals.to_string(),
            &r.entry_orders.to_string(),
            &r.entry_fills.to_string(),
            r.entry_fill_rate.as_str(),
            &r.contracts_requested.to_string(),
            &r.contracts_filled.to_string(),
            r.average_entry.as_str(),
            r.average_exit.as_str(),
            &r.stop_triggers.to_string(),
            &r.successful_exits.to_string(),
            &r.failed_exits.to_string(),
            r.realized_pnl.as_str(),
            r.unrealized_pnl.as_str(),
            r.net_pnl.as_str(),
            r.max_drawdown.as_str(),
            r.data_quality.as_str(),
            r.first_entry_timestamp.as_str(),
            r.last_entry_timestamp.as_str(),
            r.run_status.as_str(),
            r.run_duration.as_str(),
            r.artifacts_location.as_str(),
            r.metadata_location.as_str(),
            r.error.as_str(),
            r.gross_pnl.as_str(),
            r.pnl_after_fees.as_str(),
            r.w_l.as_str(),
            r.win_rate.as_str(),
            r.rr.as_str(),
            r.trade_frequency_pct.as_str(),
            r.max_drawdown.as_str(),
            r.volatility.as_str(),
            r.downside_deviation.as_str(),
            r.sharpe_ratio.as_str(),
            r.sortino_ratio.as_str(),
            r.calmar_ratio.as_str(),
            r.number_of_trades.as_str(),
            r.profit_factor.as_str(),
            r.expectancy.as_str(),
            r.median_trade.as_str(),
            r.time_in_market.as_str(),
            r.fees.as_str(),
            r.slippage.as_str(),
            r.drawdown_duration.as_str(),
            r.drawdown_recovery_time.as_str(),
            r.number_of_drawdowns.as_str(),
            r.holding_period.as_str(),
            r.out_of_sample_results.as_str(),
            r.walk_forward_results.as_str(),
            r.parameter_sensitivity.as_str(),
            r.position_sizing.as_str(),
            r.liquidity_constraints.as_str(),
            r.fills.as_str(),
            r.market_impact.as_str(),
            r.look_ahead_bias.as_str(),
            r.survivorship_bias.as_str(),
            r.missing_data_checks.as_str(),
        ])?;
    }
    wtr.flush()?;
    Ok(())
}

pub fn read_results_csv(path: &Path) -> Result<Vec<ResultRow>, BacktestError> {
    if !path.exists() {
        return Ok(Vec::new());
    }
    let file = File::open(path)?;
    let mut rdr = csv::ReaderBuilder::new()
        .flexible(true)
        .from_reader(BufReader::new(file));
    let mut out = Vec::new();
    for result in rdr.records() {
        let rec = result?;
        if rec.is_empty() || rec.get(0).unwrap_or("").eq_ignore_ascii_case("Run ID") {
            continue;
        }
        let get = |i: usize| rec.get(i).unwrap_or("").to_string();
        out.push(ResultRow {
            run_id: get(0),
            strategy: get(1),
            strategy_version: get(2).parse().unwrap_or(0),
            entry_model: get(3),
            exit_model: get(4),
            ticker_series: get(5),
            season: get(6),
            time_start: get(7),
            time_end: get(8),
            entry_price_override: get(9),
            effective_entry_range: get(10),
            exit_price_override: get(11),
            effective_exit_rule: get(12),
            dataset_coverage: get(13),
            dataset_manifest_checksum: get(14),
            quote_observations: get(15).parse().unwrap_or(0),
            entry_opportunities: get(16).parse().unwrap_or(0),
            entry_intents: get(17).parse().unwrap_or(0),
            entry_signals: get(18).parse().unwrap_or(0),
            exit_signals: get(19).parse().unwrap_or(0),
            entry_orders: get(20).parse().unwrap_or(0),
            entry_fills: get(21).parse().unwrap_or(0),
            entry_fill_rate: get(22),
            contracts_requested: get(23).parse().unwrap_or(0),
            contracts_filled: get(24).parse().unwrap_or(0),
            average_entry: get(25),
            average_exit: get(26),
            stop_triggers: get(27).parse().unwrap_or(0),
            successful_exits: get(28).parse().unwrap_or(0),
            failed_exits: get(29).parse().unwrap_or(0),
            realized_pnl: get(30),
            unrealized_pnl: get(31),
            net_pnl: get(32),
            max_drawdown: get(33),
            data_quality: get(34),
            first_entry_timestamp: get(35),
            last_entry_timestamp: get(36),
            run_status: get(37),
            run_duration: get(38),
            artifacts_location: get(39),
            metadata_location: get(40),
            error: get(41),
            ..ResultRow::default()
        });
    }
    Ok(out)
}
