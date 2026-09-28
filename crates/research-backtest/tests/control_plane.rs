//! Deterministic control-plane tests for Google Sheet → FIRST01 backtests.

use chrono::{Duration, TimeZone, Utc};
use momento_core::{GameId, MarketId, Side};
use momento_research_backtest::{
    BacktestErrorCode, BacktestPaths, ExitPriceInput, InputRow, RUNNER_VERSION, RunMetadata,
    RunStatus, advance_status, first01_defaults_immutable_after_override, parse_entry_price_range,
    parse_exit_price_input, parse_season, parse_series_list, parse_time_frame, read_input_csv,
    resolve_experiment, resolve_strategy, run_on_quotes, validate_dataset_coverage,
    write_input_csv, write_results_csv,
};
use momento_research_data::{
    CompletenessStatus, DailyManifest, ResearchPaths, ResearchSeason, ResearchSport,
};
use momento_research_strategies::{
    FIRST01_DEFAULT_ENTRY, FIRST01_DEFAULT_EXIT, FIRST01_NAME, FIRST01_VERSION, StrategyQuote,
};
use tempfile::TempDir;

fn sample_row() -> InputRow {
    InputRow {
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
    }
}

#[test]
fn parse_valid_sheet_row() {
    let row = sample_row();
    let exp = resolve_experiment(&row).expect("resolve");
    assert_eq!(exp.entry_model.name, FIRST01_NAME);
    assert_eq!(exp.series.len(), 2);
}

#[test]
fn generate_run_id() {
    let mut row = sample_row();
    assert!(row.run_id.is_empty());
    let id = row.ensure_run_id().to_string();
    assert!(!id.is_empty());
    assert_eq!(row.ensure_run_id(), id);
}

#[test]
fn parse_kxmlbgame() {
    assert_eq!(parse_series_list("KXMLBGAME").unwrap(), vec!["KXMLBGAME"]);
}

#[test]
fn parse_kxwnbagame() {
    assert_eq!(parse_series_list("KXWNBAGAME").unwrap(), vec!["KXWNBAGAME"]);
}

#[test]
fn parse_both_series() {
    let s = parse_series_list("KXMLBGAME, KXWNBAGAME").unwrap();
    assert_eq!(s, vec!["KXMLBGAME", "KXWNBAGAME"]);
}

#[test]
fn parse_80_83() {
    let r = parse_entry_price_range("80-83").unwrap();
    assert_eq!(r.minimum_entry_price_cents, 80);
    assert_eq!(r.maximum_entry_price_cents, 83);
    assert_eq!(r.confirmation_threshold_cents, 81);
}

#[test]
fn parse_60_63() {
    let r = parse_entry_price_range("60-63").unwrap();
    assert_eq!(r.minimum_entry_price_cents, 60);
    assert_eq!(r.maximum_entry_price_cents, 63);
    assert_eq!(r.confirmation_threshold_cents, 61);
}

#[test]
fn reject_malformed_price_range() {
    assert!(parse_entry_price_range("abc").is_err());
    assert!(parse_entry_price_range("80").is_err());
    assert!(parse_entry_price_range("83-80").is_err());
}

#[test]
fn resolve_first01() {
    let m = resolve_strategy("FIRST01").unwrap();
    assert_eq!(m.name, FIRST01_NAME);
    assert_eq!(m.version, FIRST01_VERSION);
}

#[test]
fn reject_unknown_strategy() {
    let err = resolve_strategy("FIRST99").unwrap_err();
    assert_eq!(err.code(), Some(BacktestErrorCode::UnknownStrategy));
}

#[test]
fn resolve_first01_default_parameters() {
    let row = sample_row();
    let exp = resolve_experiment(&row).unwrap();
    assert_eq!(exp.default_parameters.entry, FIRST01_DEFAULT_ENTRY);
    assert_eq!(exp.default_parameters.exit, FIRST01_DEFAULT_EXIT);
}

#[test]
fn apply_entry_override() {
    let mut row = sample_row();
    row.entry_price_range = "60-63".into();
    let exp = resolve_experiment(&row).unwrap();
    assert_eq!(exp.effective_parameters.entry.first_threshold_cents, 60);
    assert_eq!(
        exp.effective_parameters.entry.confirmation_threshold_cents,
        61
    );
    assert_eq!(exp.effective_parameters.entry.maximum_entry_price_cents, 63);
    assert_eq!(exp.entry_model.name, FIRST01_NAME);
}

#[test]
fn apply_exit_percent_override() {
    let mut row = sample_row();
    row.exit_price_range = "40%".into();
    let exp = resolve_experiment(&row).unwrap();
    assert_eq!(exp.effective_parameters.exit.loss_numerator, 40);
    assert_eq!(exp.effective_parameters.exit.loss_denominator, 100);
    assert!(!matches!(exp.exit_input, ExitPriceInput::ModelNative));
}

#[test]
fn first01_definition_remains_immutable() {
    let mut row = sample_row();
    row.entry_price_range = "60-63".into();
    let exp = resolve_experiment(&row).unwrap();
    assert!(first01_defaults_immutable_after_override(
        exp.effective_parameters.entry
    ));
    assert_eq!(FIRST01_DEFAULT_ENTRY.first_threshold_cents, 80);
    assert_eq!(FIRST01_DEFAULT_ENTRY.confirmation_threshold_cents, 81);
    assert_eq!(FIRST01_DEFAULT_ENTRY.maximum_entry_price_cents, 83);
    assert_eq!(FIRST01_DEFAULT_ENTRY.lock_threshold_cents, 89);
    assert_eq!(FIRST01_DEFAULT_EXIT.loss_numerator, 1);
    assert_eq!(FIRST01_DEFAULT_EXIT.loss_denominator, 2);
}

#[test]
fn season_and_timeframe_normalize() {
    let season = parse_season("25-26").unwrap();
    assert_eq!(season.label, "2025-2026");
    let tf = parse_time_frame("5/1-5/15", &season).unwrap();
    assert_eq!(tf.start.to_string(), "2026-05-01");
    assert_eq!(tf.end.to_string(), "2026-05-15");
}

#[test]
fn dataset_missing_rejection() {
    let tmp = TempDir::new().unwrap();
    let research = ResearchPaths {
        root: tmp.path().join("Data"),
        season: ResearchSeason {
            label: "2025-2026".into(),
        },
    };
    let start = chrono::NaiveDate::from_ymd_opt(2026, 5, 1).unwrap();
    let end = chrono::NaiveDate::from_ymd_opt(2026, 5, 2).unwrap();
    let err =
        validate_dataset_coverage(&research, &[ResearchSport::Mlb], start, end, false).unwrap_err();
    assert_eq!(err.code(), Some(BacktestErrorCode::DatasetMissing));
}

#[test]
fn dataset_partial_rejection() {
    let tmp = TempDir::new().unwrap();
    let research = ResearchPaths {
        root: tmp.path().join("Data"),
        season: ResearchSeason {
            label: "2025-2026".into(),
        },
    };
    let date = chrono::NaiveDate::from_ymd_opt(2026, 5, 1).unwrap();
    let mut m = DailyManifest::new(ResearchSport::Mlb, &research.season, date);
    m.markets_discovered = 2;
    m.markets_collected = 1;
    m.missing_markets = vec!["X".into()];
    m.finalize_status();
    assert_eq!(m.completeness_status, CompletenessStatus::Partial);
    m.write_atomic(&research, ResearchSport::Mlb).unwrap();
    let err =
        validate_dataset_coverage(&research, &[ResearchSport::Mlb], date, date, false).unwrap_err();
    assert_eq!(err.code(), Some(BacktestErrorCode::DatasetPartial));
}

#[test]
fn run_metadata_generation() {
    let row = sample_row();
    let exp = resolve_experiment(&row).unwrap();
    let mut meta = RunMetadata::new_base(
        exp.run_id.clone(),
        FIRST01_NAME.into(),
        FIRST01_VERSION,
        FIRST01_NAME.into(),
        FIRST01_NAME.into(),
    );
    meta.effective_parameters = exp.effective_parameters.clone();
    meta.experiment_overrides = exp.overrides.clone();
    assert_eq!(meta.strategy_name, FIRST01_NAME);
    assert_eq!(meta.runner_version, RUNNER_VERSION);
}

#[test]
fn status_machine_queued_running_complete() {
    let s = advance_status(RunStatus::Queued, RunStatus::Validating).unwrap();
    let s = advance_status(s, RunStatus::Running).unwrap();
    let s = advance_status(s, RunStatus::Complete).unwrap();
    assert_eq!(s, RunStatus::Complete);
}

#[test]
fn error_state_handling() {
    let s = advance_status(RunStatus::Queued, RunStatus::Running).unwrap();
    let s = advance_status(s, RunStatus::Error).unwrap();
    assert_eq!(s, RunStatus::Error);
}

#[test]
fn strategy_scoped_artifact_path() {
    let tmp = TempDir::new().unwrap();
    let paths = BacktestPaths::with_roots(tmp.path().to_path_buf(), tmp.path().join("Data"));
    let created = Utc.with_ymd_and_hms(2026, 5, 3, 12, 0, 0).unwrap();
    let dir = paths.run_dir("FIRST01", "abc-123", created);
    let s = dir.to_string_lossy();
    assert!(s.contains("Runs/FIRST01/"));
    assert!(s.contains("2026/05/"));
    assert!(s.contains("2026-05-03_abc-123"));
}

#[test]
fn chronological_no_lookahead_runner() {
    let row = sample_row();
    let exp = resolve_experiment(&row).unwrap();
    let t0 = Utc.with_ymd_and_hms(2026, 5, 1, 18, 0, 0).unwrap();
    let quotes = vec![
        quote(1, 101, 79, 80, t0),
        quote(1, 101, 80, 81, t0 + Duration::seconds(1)),
        quote(1, 101, 81, 82, t0 + Duration::seconds(2)),
    ];
    let result = run_on_quotes(&exp, &quotes);
    assert_eq!(result.entry_signals.len(), 1);
    assert_eq!(result.entry_signals[0].signal_price_cents, 81);
    assert_eq!(result.entry_signals[0].market_id, 101);
    assert_eq!(result.simulated_entry_fills, 0);
}

#[test]
fn market_id_side_identity_preserved() {
    let row = sample_row();
    let exp = resolve_experiment(&row).unwrap();
    let t0 = Utc.with_ymd_and_hms(2026, 5, 1, 18, 0, 0).unwrap();
    let quotes = vec![
        quote(1, 101, 80, 81, t0),
        quote(1, 102, 81, 82, t0 + Duration::seconds(1)),
        quote(1, 101, 81, 82, t0 + Duration::seconds(2)),
    ];
    let result = run_on_quotes(&exp, &quotes);
    assert_eq!(result.entry_signals.len(), 1);
    assert_eq!(result.entry_signals[0].market_id, 101);
}

#[test]
fn override_60_63_changes_thresholds_not_identity() {
    let mut row = sample_row();
    row.entry_price_range = "60-63".into();
    let exp = resolve_experiment(&row).unwrap();
    let t0 = Utc.with_ymd_and_hms(2026, 5, 1, 18, 0, 0).unwrap();
    let quotes = vec![
        quote(1, 201, 60, 61, t0),
        quote(1, 201, 61, 62, t0 + Duration::seconds(1)),
    ];
    let result = run_on_quotes(&exp, &quotes);
    assert_eq!(result.entry_signals.len(), 1);
    assert_eq!(result.entry_signals[0].strategy, FIRST01_NAME);
    assert_eq!(result.entry_signals[0].first_threshold_cents, 60);
}

#[test]
fn csv_roundtrip_and_result_summary() {
    let tmp = TempDir::new().unwrap();
    let input = tmp.path().join("input.csv");
    let results = tmp.path().join("results.csv");
    let mut row = sample_row();
    row.ensure_run_id();
    write_input_csv(&input, &[row]).unwrap();
    let loaded = read_input_csv(&input).unwrap();
    assert_eq!(loaded.len(), 1);
    assert_eq!(loaded[0].entry_model, "FIRST01");
    write_results_csv(&results, &[]).unwrap();
}

#[test]
fn no_production_trading_imports() {
    let manifest = include_str!("../Cargo.toml");
    assert!(!manifest.contains("momento-execution"));
    assert!(!manifest.contains("momento-risk"));
    assert!(!manifest.contains("momento-strategy-mlb"));
    assert!(!manifest.contains("trading-engine"));
}

#[test]
fn exit_first01_native() {
    assert!(matches!(
        parse_exit_price_input("FIRST01").unwrap(),
        ExitPriceInput::ModelNative
    ));
}

#[test]
fn unsupported_exit_rejected() {
    let err = parse_exit_price_input("40-45").unwrap_err();
    assert_eq!(err.code(), Some(BacktestErrorCode::UnsupportedExitOverride));
}

fn quote(game: u128, market: u128, bid: u16, ask: u16, ts: chrono::DateTime<Utc>) -> StrategyQuote {
    StrategyQuote {
        game_id: GameId::from_raw(game),
        market_id: MarketId::from_raw(market),
        ticker: format!("TEST-{market}"),
        side: Side::Yes,
        yes_bid_cents: bid,
        yes_ask_cents: ask,
        exchange_timestamp_ms: ts.timestamp_millis(),
        received_timestamp: ts + Duration::milliseconds(5),
        sequence_gap: false,
    }
}
