//! Characterization tests for the locked first-exact-83 universe.
//! Do not rewrite these numbers to make a strategy look better.

use std::path::Path;

use momento_research_features::configured_search::{
    ConfiguredSearchSpec, ParameterSpec, run_configured_search,
};
use momento_research_features::{TEST_END_OBSERVED, TRAIN_BEFORE, VAL_BEFORE};

#[test]
fn universe_json_matches_locked_counts() {
    let p = Path::new("Backtesting Suite/Foundation/B1/first83/b1_83_universe.json");
    let p = if p.exists() {
        p.to_path_buf()
    } else {
        Path::new("../../Backtesting Suite/Foundation/B1/first83/b1_83_universe.json").to_path_buf()
    };
    if !p.exists() {
        return;
    }
    let v: serde_json::Value = serde_json::from_str(&std::fs::read_to_string(p).unwrap()).unwrap();
    assert_eq!(v["universe"], "FIRST_EXACT_83_TRADE");
    assert_eq!(v["w7_games"], 3384);
    assert_eq!(v["skipped_no_83"], 386);
    assert_eq!(v["skipped_bound_contract_no_83"], 92);
    assert_eq!(v["snapshots_written"], 2906);
    assert_eq!(v["unique_games"], 2906);
    assert_eq!(v["fill_status"], "TRADE_PRINT_MODELED");
}

#[test]
fn official_split_constants_are_locked() {
    assert_eq!(TRAIN_BEFORE, "2025-10-07");
    assert_eq!(VAL_BEFORE, "2026-05-03");
    assert_eq!(TEST_END_OBSERVED, "2026-06-27");
}

#[test]
fn imported_40_49_row_is_candidate() {
    let p = Path::new("Backtesting Suite/Foundation/B1/first83/b1_83_exhaustive_rankings.csv");
    let p = if p.exists() {
        p.to_path_buf()
    } else {
        Path::new("../../Backtesting Suite/Foundation/B1/first83/b1_83_exhaustive_rankings.csv")
            .to_path_buf()
    };
    if !p.exists() {
        return;
    }
    let text = std::fs::read_to_string(p).unwrap();
    let row = text
        .lines()
        .find(|l| l.contains(",start_price_band=40_49,"))
        .expect("40-49 row");
    assert!(row.contains("CANDIDATE"));
    assert!(row.contains("0.1731"));
}

fn first83_sqlite() -> Option<std::path::PathBuf> {
    for p in [
        Path::new("Backtesting Suite/Foundation/B1/first83/features.sqlite"),
        Path::new("../../Backtesting Suite/Foundation/B1/first83/features.sqlite"),
    ] {
        if p.exists() {
            return Some(p.to_path_buf());
        }
    }
    None
}

#[test]
fn unconditional_first83_matches_locked_benchmark() {
    let Some(db) = first83_sqlite() else {
        eprintln!("skip: first83 features.sqlite not present");
        return;
    };
    let spec = ConfiguredSearchSpec {
        features_sqlite: db,
        include_unconditional: true,
        parameters: vec![],
        ..ConfiguredSearchSpec::default()
    };
    let report = run_configured_search(&spec).expect("configured unconditional");
    assert_eq!(report.n_83, 2906);
    assert_eq!(report.unique_games, 2906);
    assert_eq!(report.train_before, TRAIN_BEFORE);
    assert_eq!(report.val_before, VAL_BEFORE);
    let u = &report.unconditional;
    assert_eq!(u.all.n, 2906);
    assert_eq!(u.train.n, 1699);
    assert_eq!(u.validation.n, 494);
    assert_eq!(u.test.n, 713);
    let ev = u.all.ev_cents.unwrap();
    assert!((ev - 0.28).abs() < 0.05, "ALL EV {ev}");
    let wr = u.all.win_rate.unwrap();
    assert!((wr - 0.833).abs() < 0.005, "ALL WR {wr}");
}

#[test]
fn start_band_40_49_matches_locked_benchmark() {
    let Some(db) = first83_sqlite() else {
        eprintln!("skip: first83 features.sqlite not present");
        return;
    };
    let spec = ConfiguredSearchSpec {
        features_sqlite: db,
        include_unconditional: true,
        parameters: vec![ParameterSpec::list(
            "start_price_band",
            vec!["40_49".into()],
        )],
        ..ConfiguredSearchSpec::default()
    };
    let report = run_configured_search(&spec).expect("40-49");
    let h = report
        .hypotheses
        .iter()
        .find(|h| h.condition == "start_price_band=40_49")
        .expect("40-49 hypothesis");
    assert_eq!(h.train.n, 486);
    assert_eq!(h.validation.n, 141);
    assert_eq!(h.test.n, 233);
    assert!((h.train.ev_cents.unwrap() - 3.42).abs() < 0.05);
    assert!((h.validation.ev_cents.unwrap() - 1.40).abs() < 0.05);
    assert!((h.test.ev_cents.unwrap() - 2.41).abs() < 0.05);
    assert!(
        report.number_of_tests >= 1,
        "FDR is over this experiment's tests, not the imported 6128"
    );
}
