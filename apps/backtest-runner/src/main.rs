//! Research backtest runner CLI. Isolated from live trading.
//!
//! Commands:
//!   process        — run QUEUED rows from local Input CSV → Results CSV + Runs/
//!   init-sheets    — write template Input/Results CSV
//!   seed-demo      — seed COMPLETE demo fixtures for the Input time frame
//!   sheet-ids      — print Drive spreadsheet IDs/URLs
//!
//! Drive sync (agent/Drive MCP): download Input CSV → process → upload Results CSV.

use momento_research_backtest::{
    BacktestConfig, InputRow, ProcessReport, ResultRow, RunStatus, read_input_csv,
    seed_from_sheet_inputs, write_input_csv, write_results_csv,
};
use tracing::info;
use tracing_subscriber::EnvFilter;

fn main() {
    tracing_subscriber::fmt()
        .with_env_filter(EnvFilter::from_default_env().add_directive("info".parse().unwrap()))
        .init();

    let args: Vec<String> = std::env::args().collect();
    let cmd = args.get(1).map(String::as_str).unwrap_or("process");

    match cmd {
        "process" => run_process(),
        "init-sheets" => run_init_sheets(),
        "seed-demo" => run_seed_demo(),
        "sheet-ids" => print_sheet_ids(),
        "validate-mlb" => run_validate_mlb(),
        "reconcile-mlb-frequency" => run_reconcile_mlb_frequency(&args),
        other => {
            eprintln!(
                "unknown command {other}. commands: process, init-sheets, seed-demo, sheet-ids, validate-mlb, reconcile-mlb-frequency"
            );
            std::process::exit(2);
        }
    }
}

fn run_process() {
    let config = BacktestConfig::default();
    info!(
        input = %config.paths().input_csv().display(),
        results = %config.paths().results_csv().display(),
        "processing queued backtests"
    );
    match momento_research_backtest::process_input_workbook(&config) {
        Ok(report) => print_report(&report),
        Err(err) => {
            eprintln!("process failed: {err}");
            std::process::exit(1);
        }
    }
}

fn print_report(report: &ProcessReport) {
    info!(
        processed = report.processed,
        completed = report.completed,
        invalid = report.invalid,
        errors = report.errors,
        idempotent = report.skipped_idempotent,
        "backtest process finished"
    );
    for row in &report.result_rows {
        println!(
            "FIRST01 | Run {} | status={} | entry_signals={} | exit_signals={} | artifacts={}",
            row.run_id, row.run_status, row.entry_signals, row.exit_signals, row.artifacts_location
        );
    }
}

fn run_init_sheets() {
    let config = BacktestConfig::default();
    let paths = config.paths();
    let sample = InputRow {
        run_id: String::new(),
        ticker: "KXMLBGAME, KXWNBAGAME".into(),
        season: "25-26".into(),
        time_frame: "5/1-5/15".into(),
        entry_price_range: "80-83".into(),
        entry_model: "FIRST01".into(),
        exit_price_range: "FIRST01".into(),
        exit_model: "FIRST01".into(),
        status: RunStatus::Queued,
        submitted_at: None,
        started_at: None,
        completed_at: None,
        result_spreadsheet: String::new(),
        error: String::new(),
        row_index: 0,
    };
    write_input_csv(&paths.input_csv(), &[sample]).expect("write input");
    write_results_csv(&paths.results_csv(), &[] as &[ResultRow]).expect("write results");
    println!("wrote {}", paths.input_csv().display());
    println!("wrote {}", paths.results_csv().display());
    let ws = momento_research_backtest::SheetsWorkspace::from_defaults();
    println!("Drive Input:   {}", ws.input_url);
    println!("Drive Results: {}", ws.results_url);
}

fn run_seed_demo() {
    let config = BacktestConfig::default();
    let paths = config.paths();
    let rows = read_input_csv(&paths.input_csv()).unwrap_or_else(|_| {
        eprintln!("no input csv — run init-sheets or pull from Drive first");
        std::process::exit(1);
    });
    let Some(row) = rows.first() else {
        eprintln!("input csv has no data rows");
        std::process::exit(1);
    };
    let mut research = paths.research.clone();
    match seed_from_sheet_inputs(&mut research, &row.season, &row.time_frame) {
        Ok(n) => {
            info!(days_seeded = n, season = %row.season, time_frame = %row.time_frame, "demo fixtures seeded");
            println!(
                "seeded {n} sport-day COMPLETE fixtures for {} {}",
                row.season, row.time_frame
            );
        }
        Err(err) => {
            eprintln!("seed-demo failed: {err}");
            std::process::exit(1);
        }
    }
}

fn print_sheet_ids() {
    let ws = momento_research_backtest::SheetsWorkspace::from_defaults();
    println!("suite_folder_id={}", ws.suite_folder_id);
    println!("input_sheet_id={}", ws.input_spreadsheet_id);
    println!("results_sheet_id={}", ws.results_spreadsheet_id);
    println!("input_url={}", ws.input_url);
    println!("results_url={}", ws.results_url);
}

fn run_validate_mlb() {
    let config = momento_research_backtest::MlbValidationConfig::from_env();
    info!(data_dir = %config.research_data_dir.display(), run_id = %config.run_id, "MLB real-data validation");
    match momento_research_backtest::run_mlb_validation(&config) {
        Ok(result) => {
            println!("CLASSIFICATION: {:?}", result.classification);
            println!("RUN_ID: {}", result.run_id);
            println!("ARTIFACTS: {}", result.run_dir.display());
            println!(
                "OPPORTUNITIES/DAY: {:.2} (total {} over {} eligible days)",
                result.signal_frequency.opportunities_per_eligible_day,
                result.signal_frequency.entry_opportunities,
                result.signal_frequency.eligible_days
            );
            println!(
                "INTENTS: {} ORDERS: {} FILLS: {} FILL_RATE: {:.2}%",
                result.signal_frequency.entry_intents,
                result.entry_orders,
                result.entry_fills,
                result.entry_fill_rate * 100.0
            );
        }
        Err(err) => {
            eprintln!("validate-mlb failed: {err}");
            std::process::exit(1);
        }
    }
}

fn run_reconcile_mlb_frequency(args: &[String]) {
    let source = args.get(2).cloned().unwrap_or_else(|| {
        "Backtesting Suite/Runs/FIRST01/2026/08/2026-08-25_mlb-validation-20260825-185643".into()
    });
    let config = momento_research_backtest::FrequencyReconcileConfig::from_env(source.into());
    info!(
        source = %config.source_run_dir.display(),
        run_id = %config.run_id,
        "MLB frequency reconciliation"
    );
    match momento_research_backtest::run_frequency_reconcile(&config) {
        Ok(r) => {
            println!("RUN_ID: {}", r.run_id);
            println!("ARTIFACTS: {}", r.run_dir.display());
            println!(
                "FIRST01 CANONICAL OPPORTUNITIES / ELIGIBLE DAY = {:.2}",
                r.opportunities_per_day
            );
            println!(
                "LIVE-COMPARABLE FIRST01 INTENTS / ELIGIBLE DAY = {:.2}",
                r.live_comparable_intents_per_day
            );
            println!("ONE-TRADE-PER-GAME = {}", r.one_trade_per_game);
            println!("ROOT CAUSE = {}", r.root_cause);
            println!("PRODUCTION ORDERS TRANSMITTED DURING THIS WORK: 0");
        }
        Err(err) => {
            eprintln!("reconcile-mlb-frequency failed: {err}");
            std::process::exit(1);
        }
    }
}
