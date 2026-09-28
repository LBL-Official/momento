//! JSON artifact writers for execution results.

use std::fs;
use std::path::{Path, PathBuf};

use serde::Serialize;

use crate::engine::ExecutionBacktestResult;
use crate::params::FeesModel;
use crate::pnl::{PositionPnl, compute_position_pnl};

#[derive(Clone, Debug)]
pub struct ExecutionArtifacts {
    pub signals_dir: PathBuf,
    pub execution_dir: PathBuf,
    pub pnl_dir: PathBuf,
    pub entry_signals_path: PathBuf,
    pub exit_signals_path: PathBuf,
    pub orders_path: PathBuf,
    pub fills_path: PathBuf,
    pub positions_path: PathBuf,
    pub realized_path: PathBuf,
    pub pnl_summary_path: PathBuf,
}

pub fn write_execution_artifacts(
    run_dir: &Path,
    result: &ExecutionBacktestResult,
    marks: &[(u128, u16)],
) -> std::io::Result<ExecutionArtifacts> {
    let signals_dir = run_dir.join("signals");
    let execution_dir = run_dir.join("execution");
    let pnl_dir = run_dir.join("pnl");
    fs::create_dir_all(&signals_dir)?;
    fs::create_dir_all(&execution_dir)?;
    fs::create_dir_all(&pnl_dir)?;

    let entry_signals_path = signals_dir.join("entry_signals.json");
    let exit_signals_path = signals_dir.join("exit_signals.json");
    let orders_path = execution_dir.join("orders.json");
    let fills_path = execution_dir.join("fills.json");
    let positions_path = execution_dir.join("positions.json");
    let realized_path = pnl_dir.join("realized.json");
    let pnl_summary_path = pnl_dir.join("summary.json");

    write_json(&entry_signals_path, &result.entry_signals)?;
    write_json(&exit_signals_path, &result.exit_signals)?;
    write_json(&orders_path, &result.orders)?;
    write_json(&fills_path, &result.fills)?;
    write_json(&positions_path, &result.positions)?;

    let realized: Vec<PositionPnl> = result
        .positions
        .iter()
        .map(|p| {
            let mark = marks
                .iter()
                .find(|(m, _)| *m == p.market_id)
                .map(|(_, px)| *px);
            compute_position_pnl(p, mark, FeesModel::NotModeled)
        })
        .collect();
    write_json(&realized_path, &realized)?;
    write_json(&pnl_summary_path, &result.portfolio_pnl)?;

    crate::trade_ledger::write_trade_ledger(run_dir, result)?;

    Ok(ExecutionArtifacts {
        signals_dir,
        execution_dir,
        pnl_dir,
        entry_signals_path,
        exit_signals_path,
        orders_path,
        fills_path,
        positions_path,
        realized_path,
        pnl_summary_path,
    })
}

fn write_json<T: Serialize>(path: &Path, value: &T) -> std::io::Result<()> {
    let body = serde_json::to_string_pretty(value)?;
    let tmp = path.with_extension("tmp");
    fs::write(&tmp, body)?;
    fs::rename(tmp, path)?;
    Ok(())
}
