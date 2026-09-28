//! Prospective validation of frozen first-exact-83 candidates.
//!
//! Existing TEST through 2026-06-27 is LOCKED / CONSUMED.
//! The holdout may only score already-frozen hypotheses.
//! Does not retune FIRST01, invent L2, or submit orders.

use std::collections::{BTreeMap, BTreeSet};
use std::fs;
use std::path::{Path, PathBuf};

use rusqlite::Connection;
use serde::{Deserialize, Serialize};

use crate::a1_targets::EXIT_HOLD_TO_SETTLEMENT;
use crate::batch::B1RunConfig;
use crate::configured_search::{ConfiguredSearchSpec, ParameterSpec, prepare_search_rows};
use crate::error::B1Error;
use crate::extract_first83::run_first83_extract_subset;
use crate::search::{
    ChronoSplit, FILL_STATUS, SearchRow, bootstrap_ev_ci, flatten, metrics, tertile_cuts,
};
use crate::search_83::{cond_ok, enrich, parse_cond};
use crate::search_83_exh::{assert_no_leakage, enrich_exh, game_pnls};
use crate::search_83_opt::enrich_opt;
use crate::splits::{TEST_END_OBSERVED, TRAIN_BEFORE, VAL_BEFORE, apply_configured_chrono_split};
use crate::store::FeatureStore;
use crate::versions::{ENGINE_VERSION, FEATURE_SCHEMA_VERSION};

const PRIMARY: &str = EXIT_HOLD_TO_SETTLEMENT;
const DEFAULT_SEED: u64 = 42;
const DEFAULT_BOOTSTRAP: usize = 10_000;
const DEFAULT_PERM: usize = 2_000;

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct FrozenCandidate {
    pub id: &'static str,
    pub name: &'static str,
    pub condition: &'static str,
    pub why_frozen: &'static str,
    pub discovery_fdr_q: Option<f64>,
    pub historical: HistoricalLock,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct HistoricalLock {
    pub train_n: u32,
    pub val_n: u32,
    pub test_n: u32,
    pub train_ev: f64,
    pub val_ev: f64,
    pub test_ev: f64,
}

/// Predeclared set. Definitions must not be edited to improve a score.
pub fn frozen_candidates() -> Vec<FrozenCandidate> {
    vec![
        FrozenCandidate {
            id: "CAND_A_40_49",
            name: "Candidate A",
            condition: "start_price_band=40_49",
            why_frozen: "Simplest +EV-on-all-splits 1-way. Discovery BH q=0.173 from 6,128 tests.",
            discovery_fdr_q: Some(0.1731),
            historical: HistoricalLock {
                train_n: 486,
                val_n: 141,
                test_n: 233,
                train_ev: 3.42,
                val_ev: 1.40,
                test_ev: 2.41,
            },
        },
        FrozenCandidate {
            id: "CAND_B_MOVE30_OUTS0_VOL1M_LOW",
            name: "Candidate B",
            condition: "start_move_gt30=YES&outs=0&vol_1m_tertile=LOW",
            why_frozen: "Highest-priority 3-way from locked exhaustive ROBUST leaders. Predeclared before this holdout.",
            discovery_fdr_q: None,
            historical: HistoricalLock {
                train_n: 62,
                val_n: 28,
                test_n: 41,
                train_ev: 10.55,
                val_ev: 9.86,
                test_ev: 12.12,
            },
        },
        FrozenCandidate {
            id: "CAND_C_LEAD2_MOVE30_VOL1M_LOW",
            name: "Candidate C",
            condition: "lead_signed=LEAD_2&start_move_gt30=YES&vol_1m_tertile=LOW",
            why_frozen: "Locked exhaustive ROBUST 3-way. Predeclared.",
            discovery_fdr_q: None,
            historical: HistoricalLock {
                train_n: 121,
                val_n: 50,
                test_n: 92,
                train_ev: 8.74,
                val_ev: 13.00,
                test_ev: 3.96,
            },
        },
        FrozenCandidate {
            id: "CAND_D_TWORUN_MOVE30_VOL1M_LOW",
            name: "Candidate D",
            condition: "score_bucket=TWO_RUN&start_move_gt30=YES&vol_1m_tertile=LOW",
            why_frozen: "Locked exhaustive ROBUST 3-way (near-duplicate of C). Predeclared.",
            discovery_fdr_q: None,
            historical: HistoricalLock {
                train_n: 121,
                val_n: 50,
                test_n: 92,
                train_ev: 8.74,
                val_ev: 13.00,
                test_ev: 3.96,
            },
        },
        FrozenCandidate {
            id: "CAND_E_MOVEFINE_VOL_LOW",
            name: "Candidate E",
            condition: "move_fine=30_35&vol_1m_tertile=LOW&vol_15m_tertile=LOW",
            why_frozen: "Locked exhaustive ROBUST 3-way. Predeclared.",
            discovery_fdr_q: None,
            historical: HistoricalLock {
                train_n: 125,
                val_n: 61,
                test_n: 102,
                train_ev: 9.00,
                val_ev: 8.80,
                test_ev: 4.25,
            },
        },
        FrozenCandidate {
            id: "CAND_F_INNING7_PEAK_AT",
            name: "Candidate F",
            condition: "inning_grp=7&p_max_vs_83=PEAK_AT",
            why_frozen: "VAL-selected primary. Less evidentiary weight than independently predeclared cells.",
            discovery_fdr_q: Some(0.1837),
            historical: HistoricalLock {
                train_n: 65,
                val_n: 25,
                test_n: 48,
                train_ev: 7.77,
                val_ev: 13.00,
                test_ev: 2.42,
            },
        },
    ]
}

#[derive(Clone, Debug, Serialize)]
pub struct ProspectiveCoverage {
    pub existing_cutoff: String,
    pub prospective_start: String,
    pub prospective_end: Option<String>,
    pub w6_eligible_games: usize,
    pub w7_path_games: usize,
    pub w7_post_cutoff_games: usize,
    pub first83_eligible: usize,
    pub excluded_no_w7_path: usize,
    pub excluded_reason: String,
    pub w6_date_min: Option<String>,
    pub w6_date_max: Option<String>,
    pub status: String,
}

#[derive(Clone, Debug)]
pub struct ProspectiveArgs {
    pub cutoff: String,
    pub prospective_start: String,
    pub prospective_end: Option<String>,
    pub w6_sqlite: PathBuf,
    pub w7_sqlite: PathBuf,
    pub w8_sqlite: PathBuf,
    pub identity_landing: PathBuf,
    pub first83_sqlite: PathBuf,
    pub out_dir: PathBuf,
    pub bootstrap_reps: usize,
    pub permutation_reps: usize,
    pub seed: u64,
    pub candidate_set: Option<Vec<String>>,
    pub cost_grid_cents: Vec<f64>,
}

impl ProspectiveArgs {
    pub fn defaults(root: impl AsRef<Path>) -> Self {
        let root = root.as_ref();
        let b1 = root.join("Backtesting Suite/Foundation/B1");
        Self {
            cutoff: TEST_END_OBSERVED.into(),
            prospective_start: "2026-06-28".into(),
            prospective_end: None,
            w6_sqlite: root.join("Backtesting Suite/Foundation/W6/state.sqlite"),
            w7_sqlite: root.join("Backtesting Suite/Foundation/W7/path.sqlite"),
            w8_sqlite: root.join("Backtesting Suite/Foundation/W8/replay.sqlite"),
            identity_landing: root.join("Backtesting Suite/Foundation/Ingest/landing/mlb_statsapi"),
            first83_sqlite: b1.join("first83/features.sqlite"),
            out_dir: b1.join("prospective83"),
            bootstrap_reps: DEFAULT_BOOTSTRAP,
            permutation_reps: DEFAULT_PERM,
            seed: DEFAULT_SEED,
            candidate_set: None,
            cost_grid_cents: vec![0.5, 1.0, 2.0, 3.0, 5.0],
        }
    }
}

#[derive(Clone, Debug, Serialize)]
pub struct ProspectiveReport {
    pub answer: String,
    pub headline: String,
    pub production_count: u32,
    pub fill_status: &'static str,
    pub l2_status: &'static str,
    pub feature_schema_version: &'static str,
    pub engine_version: &'static str,
    pub discovery_tests: u32,
    pub frozen_candidates: usize,
    pub coverage: ProspectiveCoverage,
    pub candidates: Vec<serde_json::Value>,
    pub locked_train_tertiles: serde_json::Value,
    pub abort_reason: Option<String>,
}

pub fn assert_no_holdout_overlap(start: &str, cutoff: &str) -> Result<(), B1Error> {
    if start <= cutoff {
        return Err(B1Error::validation(
            "HOLDOUT_OVERLAP",
            format!("prospective start {start} must be strictly after cutoff {cutoff}"),
        ));
    }
    Ok(())
}

pub fn scan_prospective_coverage(args: &ProspectiveArgs) -> Result<ProspectiveCoverage, B1Error> {
    assert_no_holdout_overlap(&args.prospective_start, &args.cutoff)?;
    if !args.w6_sqlite.exists() {
        return Ok(ProspectiveCoverage {
            existing_cutoff: args.cutoff.clone(),
            prospective_start: args.prospective_start.clone(),
            prospective_end: args.prospective_end.clone(),
            w6_eligible_games: 0,
            w7_path_games: 0,
            w7_post_cutoff_games: 0,
            first83_eligible: 0,
            excluded_no_w7_path: 0,
            excluded_reason: "W6 state.sqlite missing".into(),
            w6_date_min: None,
            w6_date_max: None,
            status: "PROSPECTIVE_DATA_NOT_YET_AVAILABLE".into(),
        });
    }
    let w6 = Connection::open(&args.w6_sqlite)?;
    let mut w6_rows: Vec<(String, String)> = w6
        .prepare(
            "SELECT game_id, official_date FROM games
             WHERE official_date > ?1 AND official_date >= ?2
               AND (?3 IS NULL OR official_date <= ?3)
               AND status = 'OK'",
        )?
        .query_map(
            rusqlite::params![
                args.cutoff,
                args.prospective_start,
                args.prospective_end.as_deref()
            ],
            |r| Ok((r.get::<_, String>(0)?, r.get::<_, String>(1)?)),
        )?
        .filter_map(|x| x.ok())
        .collect();
    if w6_rows
        .iter()
        .any(|(_, d)| d.as_str() <= args.cutoff.as_str())
    {
        return Err(B1Error::validation(
            "LEAK_CUTOFF",
            "W6 scan returned a game on or before the locked TEST cutoff",
        ));
    }
    w6_rows.sort_by(|a, b| a.1.cmp(&b.1).then(a.0.cmp(&b.0)));
    let w6_ids: BTreeSet<String> = w6_rows.iter().map(|(g, _)| g.clone()).collect();
    let date_min = w6_rows.first().map(|r| r.1.clone());
    let date_max = w6_rows.last().map(|r| r.1.clone());

    let mut w7_all = BTreeSet::new();
    if args.w7_sqlite.exists() {
        let w7 = Connection::open(&args.w7_sqlite)?;
        let mut stmt = w7.prepare("SELECT DISTINCT game_id FROM game_path_coverage")?;
        let rows = stmt.query_map([], |r| r.get::<_, String>(0))?;
        for g in rows.flatten() {
            w7_all.insert(g);
        }
    }
    let overlap: BTreeSet<_> = w6_ids.intersection(&w7_all).cloned().collect();
    let excluded = w6_ids.len().saturating_sub(overlap.len());
    let status = if overlap.is_empty() {
        "PROSPECTIVE_DATA_NOT_YET_AVAILABLE"
    } else {
        "PROSPECTIVE_PATHS_PRESENT"
    };
    Ok(ProspectiveCoverage {
        existing_cutoff: args.cutoff.clone(),
        prospective_start: args.prospective_start.clone(),
        prospective_end: date_max.clone().or_else(|| args.prospective_end.clone()),
        w6_eligible_games: w6_ids.len(),
        w7_path_games: w7_all.len(),
        w7_post_cutoff_games: overlap.len(),
        first83_eligible: 0,
        excluded_no_w7_path: excluded,
        excluded_reason: if overlap.is_empty() {
            "W6 games exist after cutoff but W7 EventMarketPath / TRADE prints were not reconstructed for those games. First-exact-83 requires a W7 TRADE at 83¢. Do not invent prints from W6 state alone.".into()
        } else {
            "W7 paths present; first-83 extract not run in this invocation.".into()
        },
        w6_date_min: date_min,
        w6_date_max: date_max,
        status: status.into(),
    })
}

fn selected_candidates(args: &ProspectiveArgs) -> Result<Vec<FrozenCandidate>, B1Error> {
    let all = frozen_candidates();
    let Some(want) = args.candidate_set.as_ref() else {
        return Ok(all);
    };
    let mut out = Vec::new();
    for key in want {
        let k = key.trim();
        let hit = all.iter().find(|c| {
            c.id == k
                || c.id.ends_with(k)
                || c.name.eq_ignore_ascii_case(k)
                || c.name.ends_with(k)
                || format!("Candidate {k}") == c.name
                || c.id.contains(k)
        });
        match hit {
            Some(c) => {
                if !out.iter().any(|x: &FrozenCandidate| x.id == c.id) {
                    out.push(c.clone());
                }
            }
            None => {
                return Err(B1Error::validation(
                    "UNKNOWN_CANDIDATE",
                    format!("candidate-set member {k} is not a frozen ID"),
                ));
            }
        }
    }
    if out.is_empty() {
        return Err(B1Error::validation(
            "EMPTY_CANDIDATE_SET",
            "candidate-set selected nothing",
        ));
    }
    Ok(out)
}

fn empty_eval(c: &FrozenCandidate, coverage_n: usize) -> serde_json::Value {
    let _ = coverage_n;
    serde_json::json!({
        "hypothesis_id": c.id,
        "name": c.name,
        "condition": c.condition,
        "why_frozen": c.why_frozen,
        "search_stage": "FROZEN_PREDECLARED",
        "discovery_fdr_q": c.discovery_fdr_q,
        "historical": c.historical,
        "layer": "PROSPECTIVE_VALIDATION",
        "prospective": {
            "n_games": 0,
            "n_unique_games": 0,
            "coverage_pct": 0.0,
            "win_rate": null,
            "ev_cents": null,
            "pnl_usd": null,
            "sharpe": null,
            "max_dd_usd": null,
            "status": "PROSPECTIVE_DATA_NOT_YET_AVAILABLE"
        },
        "incremental_ev_vs_all83": null,
        "bootstrap": null,
        "permutation_p": null,
        "cost_sensitivity": [],
        "cost_survival_max_cents": null,
        "monthly": [],
        "concentration": null,
        "threshold_sensitivity": "SECONDARY_NOT_RUN_NO_HOLDOUT",
        "classification": "INSUFFICIENT_DATA",
        "labels": {
            "DISCOVERY_FDR": c.discovery_fdr_q,
            "PROSPECTIVE_VALIDATION": "NOT_RUN",
            "POST_HOLDOUT_DISCOVERY": false
        }
    })
}

fn locked_train_tertiles(first83: &Path) -> Result<serde_json::Value, B1Error> {
    if !first83.exists() {
        return Ok(serde_json::json!({ "status": "LOCKED_FIRST83_MISSING" }));
    }
    let store = FeatureStore::open_existing(first83)?;
    let snaps = store.load_all()?;
    let mut rows: Vec<SearchRow> = snaps.iter().map(flatten).collect();
    apply_configured_chrono_split(&mut rows, TRAIN_BEFORE, VAL_BEFORE);
    let by_id: BTreeMap<_, _> = snaps.iter().map(|s| (s.game_id.as_str(), s)).collect();
    let cut = |raw: &dyn Fn(&crate::types::B1EntrySnapshot) -> Option<i32>| -> serde_json::Value {
        let train: Vec<i32> = rows
            .iter()
            .filter(|r| r.chrono == ChronoSplit::Train)
            .filter_map(|r| by_id.get(r.game_id.as_str()).copied().and_then(raw))
            .collect();
        match tertile_cuts(train) {
            Some((a, b)) => {
                serde_json::json!({ "low_max": a, "mid_max": b, "source": "LOCKED_TRAIN" })
            }
            None => serde_json::json!({ "status": "NO_TRAIN_CUTS" }),
        }
    };
    Ok(serde_json::json!({
        "vol_1m": cut(&|s| s.market_history.volatility_1m_cents),
        "vol_15m": cut(&|s| s.market_history.volatility_15m_cents),
        "vol_30m": cut(&|s| s.market_history.volatility_30m_cents),
        "vol_z": cut(&|s| s.market_history.volatility_5m_z_e3),
        "path_dist": cut(&|s| s.market_history.path_distance_cents),
        "note": "Prospective rows must reuse these TRAIN cuts. Never refit on the holdout."
    }))
}

fn locked_game_ids(first83: &Path) -> Result<BTreeSet<String>, B1Error> {
    if !first83.exists() {
        return Ok(BTreeSet::new());
    }
    let store = FeatureStore::open_existing(first83)?;
    Ok(store.load_all()?.into_iter().map(|s| s.game_id).collect())
}

fn apply_locked_tertiles(
    rows: &mut [SearchRow],
    snaps: &[crate::types::B1EntrySnapshot],
    cuts: &serde_json::Value,
) {
    let by_id: BTreeMap<_, _> = snaps.iter().map(|s| (s.game_id.as_str(), s)).collect();
    let apply = |rows: &mut [SearchRow],
                 key: &str,
                 json_key: &str,
                 raw: &dyn Fn(&crate::types::B1EntrySnapshot) -> Option<i32>| {
        let a = cuts[json_key]["low_max"].as_i64().map(|x| x as i32);
        let b = cuts[json_key]["mid_max"].as_i64().map(|x| x as i32);
        for r in rows.iter_mut() {
            let v = by_id.get(r.game_id.as_str()).copied().and_then(raw);
            let label = match (v, a, b) {
                (None, _, _) | (Some(_), None, _) | (Some(_), _, None) => "NA".into(),
                (Some(x), Some(lo), Some(_)) if x <= lo => "LOW".into(),
                (Some(x), Some(_), Some(mid)) if x <= mid => "MID".into(),
                (Some(_), Some(_), Some(_)) => "HIGH".into(),
            };
            r.feats.insert(key.into(), label);
        }
    };
    apply(rows, "vol_1m_tertile", "vol_1m", &|s| {
        s.market_history.volatility_1m_cents
    });
    apply(rows, "vol_15m_tertile", "vol_15m", &|s| {
        s.market_history.volatility_15m_cents
    });
    apply(rows, "vol_30m_tertile", "vol_30m", &|s| {
        s.market_history.volatility_30m_cents
    });
    apply(rows, "vol_z_tertile", "vol_z", &|s| {
        s.market_history.volatility_5m_z_e3
    });
    apply(rows, "path_dist_tertile", "path_dist", &|s| {
        s.market_history.path_distance_cents
    });
}

fn bootstrap_full(rows: &[&SearchRow], reps: usize, seed: u64) -> Option<serde_json::Value> {
    let pnls = game_pnls(rows, PRIMARY);
    if pnls.len() < 8 {
        return None;
    }
    let mut state = seed;
    let mut means = Vec::with_capacity(reps);
    let n = pnls.len();
    for _ in 0..reps {
        let mut s = 0.0;
        for _ in 0..n {
            state = state.wrapping_mul(6364136223846793005).wrapping_add(1);
            s += pnls[(state as usize) % n];
        }
        means.push(s / n as f64 / 100.0);
    }
    means.sort_by(|a, b| a.partial_cmp(b).unwrap());
    let mean = means.iter().sum::<f64>() / means.len() as f64;
    let lo = means[reps * 25 / 1000];
    let hi = means[reps * 975 / 1000];
    let med = means[reps / 2];
    let p_pos = means.iter().filter(|x| **x > 0.0).count() as f64 / means.len() as f64;
    Some(serde_json::json!({
        "reps": reps,
        "seed": seed,
        "unit": "GAME",
        "mean_ev_cents": mean,
        "median_ev_cents": med,
        "ci95": [lo, hi],
        "p_ev_gt_0": p_pos
    }))
}

fn permutation_membership_p(
    all: &[f64],
    n_in: usize,
    obs_mean: f64,
    reps: usize,
    seed: u64,
) -> Option<f64> {
    if all.len() < 10 || n_in < 8 || n_in > all.len() {
        return None;
    }
    let mut state = seed;
    let mut ge = 0usize;
    let mut buf = all.to_vec();
    for _ in 0..reps {
        for i in (1..buf.len()).rev() {
            state = state.wrapping_mul(6364136223846793005).wrapping_add(1);
            let j = (state as usize) % (i + 1);
            buf.swap(i, j);
        }
        let m = buf.iter().take(n_in).sum::<f64>() / n_in as f64;
        if m >= obs_mean {
            ge += 1;
        }
    }
    Some((ge as f64 + 1.0) / (reps as f64 + 1.0))
}

fn monthly_rows(rows: &[&SearchRow]) -> Vec<serde_json::Value> {
    let mut m: BTreeMap<String, (i32, usize, usize)> = BTreeMap::new();
    for r in rows {
        if let Some(&ret) = r.exit_ret.get(PRIMARY) {
            let e = m.entry(r.month.clone()).or_insert((0, 0, 0));
            e.0 += ret * r.qty;
            e.1 += 1;
            if r.settlement_win == Some(true) {
                e.2 += 1;
            }
        }
    }
    m.into_iter()
        .map(|(month, (pnl, n, wins))| {
            serde_json::json!({
                "month": month,
                "n": n,
                "ev_cents": if n == 0 { None } else { Some(f64::from(pnl) / n as f64 / 7.0) },
                "pnl_usd": f64::from(pnl) / 100.0,
                "win_rate": if n == 0 { None } else { Some(wins as f64 / n as f64) }
            })
        })
        .collect()
}

fn rolling_ev(rows: &[&SearchRow], window: usize) -> Vec<f64> {
    let mut dated: Vec<(&str, i32)> = rows
        .iter()
        .filter_map(|r| {
            r.exit_ret
                .get(PRIMARY)
                .map(|&ret| (r.date.as_str(), ret * r.qty))
        })
        .collect();
    dated.sort_by(|a, b| a.0.cmp(b.0));
    if dated.len() < window {
        return Vec::new();
    }
    dated
        .windows(window)
        .map(|w| w.iter().map(|(_, p)| f64::from(*p)).sum::<f64>() / window as f64 / 7.0)
        .collect()
}

fn concentration(rows: &[&SearchRow]) -> serde_json::Value {
    let mut games: Vec<(String, i32, String)> = Vec::new();
    let mut by_game: BTreeMap<&str, (i32, &str)> = BTreeMap::new();
    for r in rows {
        if let Some(&ret) = r.exit_ret.get(PRIMARY) {
            let e = by_game
                .entry(r.game_id.as_str())
                .or_insert((0, r.date.as_str()));
            e.0 += ret * r.qty;
        }
    }
    for (g, (pnl, date)) in by_game {
        games.push((g.to_string(), pnl, date.to_string()));
    }
    let total: i32 = games.iter().map(|g| g.1).sum();
    let mut by_abs = games.clone();
    by_abs.sort_by_key(|g| -g.1.abs());
    let top10_n = (games.len() as f64 * 0.10).ceil() as usize;
    let top10_pnl: i32 = by_abs.iter().take(top10_n.max(1)).map(|g| g.1).sum();
    let mut months: BTreeMap<String, i32> = BTreeMap::new();
    for g in &games {
        *months.entry(g.2.chars().take(7).collect()).or_default() += g.1;
    }
    let top_month = months.iter().max_by_key(|(_, v)| **v);
    serde_json::json!({
        "n_games": games.len(),
        "total_pnl_usd": f64::from(total) / 100.0,
        "top_month": top_month.map(|(k, v)| serde_json::json!({"month": k, "pnl_usd": f64::from(*v) / 100.0})),
        "top_10_games_pnl_usd": f64::from(by_abs.iter().take(10).map(|g| g.1).sum::<i32>()) / 100.0,
        "top_10pct_share": if total == 0 { 0.0 } else { f64::from(top10_pnl) / f64::from(total.abs()) },
        "flag_tiny_n": games.len() < 25
    })
}

fn cost_grid(ev: Option<f64>, grid: &[f64]) -> (Vec<serde_json::Value>, Option<f64>) {
    let Some(gross) = ev else {
        return (Vec::new(), None);
    };
    let rows: Vec<serde_json::Value> = grid
        .iter()
        .map(|c| {
            serde_json::json!({
                "hypothetical_research_cost_cents": c,
                "net_ev_cents": gross - c,
                "fee_model": "HYPOTHETICAL_RESEARCH_COST",
                "not_kalshi_fee_model": true
            })
        })
        .collect();
    let max_pos = grid
        .iter()
        .copied()
        .filter(|c| gross - *c > 0.0)
        .fold(None, |acc: Option<f64>, c| {
            Some(acc.map(|x| x.max(c)).unwrap_or(c))
        });
    (rows, max_pos)
}

fn classify_holdout(
    c: &FrozenCandidate,
    n: usize,
    ev: Option<f64>,
    boot: &Option<serde_json::Value>,
    cost_max: Option<f64>,
    conc: &serde_json::Value,
) -> String {
    let Some(ev) = ev else {
        return "INSUFFICIENT_DATA".into();
    };
    if n == 0 {
        return "INSUFFICIENT_DATA".into();
    }
    if ev <= 0.0 {
        return "FAIL".into();
    }
    if conc["flag_tiny_n"].as_bool() == Some(true) && n < 15 {
        return "INTERESTING".into();
    }
    let ci_lo = boot.as_ref().and_then(|b| b["ci95"][0].as_f64());
    if ci_lo.is_some_and(|lo| lo < -2.0) {
        return "INTERESTING".into();
    }
    if cost_max.is_some_and(|c| c < 1.0) {
        return "INTERESTING".into();
    }
    let hist_ok =
        c.historical.train_ev > 0.0 && c.historical.val_ev > 0.0 && c.historical.test_ev > 0.0;
    if hist_ok && n >= 25 && cost_max.unwrap_or(0.0) >= 1.0 {
        return "CANDIDATE".into();
    }
    "INTERESTING".into()
}

fn eval_on_holdout(
    c: &FrozenCandidate,
    holdout: &[SearchRow],
    all_pnls: &[f64],
    all_ev: Option<f64>,
    args: &ProspectiveArgs,
) -> serde_json::Value {
    let cond = parse_cond(c.condition);
    let rows: Vec<&SearchRow> = holdout.iter().filter(|r| cond_ok(r, &cond)).collect();
    let m = metrics(&rows, PRIMARY);
    let ev = m.ev_cents;
    let boot = bootstrap_full(&rows, args.bootstrap_reps, args.seed);
    let obs_mean = game_pnls(&rows, PRIMARY).iter().sum::<f64>() / rows.len().max(1) as f64;
    let perm = permutation_membership_p(
        all_pnls,
        rows.len(),
        obs_mean,
        args.permutation_reps,
        args.seed,
    );
    let (costs, cost_max) = cost_grid(ev, &args.cost_grid_cents);
    let conc = concentration(&rows);
    let monthly = monthly_rows(&rows);
    let class = classify_holdout(c, m.n_unique_games, ev, &boot, cost_max, &conc);
    serde_json::json!({
        "hypothesis_id": c.id,
        "name": c.name,
        "condition": c.condition,
        "why_frozen": c.why_frozen,
        "search_stage": "FROZEN_PREDECLARED",
        "discovery_fdr_q": c.discovery_fdr_q,
        "historical": c.historical,
        "layer": "PROSPECTIVE_VALIDATION",
        "prospective": {
            "n_games": m.n_entries,
            "n_unique_games": m.n_unique_games,
            "coverage_pct": if holdout.is_empty() { 0.0 } else { m.n_unique_games as f64 / holdout.len() as f64 * 100.0 },
            "win_rate": m.win_rate,
            "loss_rate": m.win_rate.map(|w| 1.0 - w),
            "ev_cents": ev,
            "pnl_usd": m.total_pnl_usd,
            "game_level_mean": m.mean_return_cents,
            "game_level_std": m.stdev_pnl_cents,
            "sharpe": m.sharpe_game_unann,
            "max_dd_usd": m.max_dd_usd,
            "worst_game": m.worst_trade_cents,
            "best_game": m.best_trade_cents,
            "rolling_25_ev": rolling_ev(&rows, 25),
            "rolling_50_ev": rolling_ev(&rows, 50)
        },
        "incremental_ev_vs_all83": match (ev, all_ev) {
            (Some(a), Some(b)) => Some(a - b),
            _ => None
        },
        "bootstrap": boot,
        "permutation_p": perm,
        "cost_sensitivity": costs,
        "cost_survival_max_cents": cost_max,
        "monthly": monthly,
        "concentration": conc,
        "threshold_sensitivity": "SECONDARY_NOT_RUN_PRIMARY_LOCKED",
        "classification": class,
        "labels": {
            "DISCOVERY_FDR": c.discovery_fdr_q,
            "PROSPECTIVE_VALIDATION": "RUN",
            "POST_HOLDOUT_DISCOVERY": false
        }
    })
}

fn write_artifacts(dir: &Path, report: &ProspectiveReport) -> Result<(), B1Error> {
    fs::create_dir_all(dir)?;
    let coverage = &report.coverage;
    fs::write(
        dir.join("prospective83_manifest.json"),
        serde_json::to_string_pretty(&serde_json::json!({
            "dataset_id": "B1_FIRST83_PROSPECTIVE",
            "dataset_version": "v1",
            "universe": "FIRST_EXACT_83_TRADE",
            "fill_status": FILL_STATUS,
            "l2_status": "UNAVAILABLE_SOURCE",
            "exit": PRIMARY,
            "stake": "qty = 625 // 83 = 7",
            "cutoff_locked_test_end": coverage.existing_cutoff,
            "prospective_start": coverage.prospective_start,
            "prospective_end": coverage.prospective_end,
            "feature_schema_version": FEATURE_SCHEMA_VERSION,
            "engine_version": ENGINE_VERSION,
            "frozen_candidate_ids": frozen_candidates().iter().map(|c| c.id).collect::<Vec<_>>(),
            "locked_train_tertiles": report.locked_train_tertiles,
            "status": coverage.status,
            "answer": report.answer,
            "production_count": 0,
            "do_not_retune_on_holdout": true,
            "research_mode": "B1_FIRST83_PROSPECTIVE/v1"
        }))?,
    )?;
    fs::write(
        dir.join("prospective83_candidates.json"),
        serde_json::to_string_pretty(&frozen_candidates())?,
    )?;
    let mut csv = String::from(
        "hypothesis_id,condition,historical_test_ev,prospective_n,prospective_ev,classification\n",
    );
    for c in &report.candidates {
        csv.push_str(&format!(
            "{},{},{},{},{},{}\n",
            c["hypothesis_id"].as_str().unwrap_or(""),
            c["condition"].as_str().unwrap_or(""),
            c["historical"]["test_ev"].as_f64().unwrap_or(0.0),
            c["prospective"]["n_unique_games"].as_u64().unwrap_or(0),
            c["prospective"]["ev_cents"]
                .as_f64()
                .map(|x| format!("{x:.4}"))
                .unwrap_or_default(),
            c["classification"].as_str().unwrap_or(""),
        ));
    }
    fs::write(dir.join("prospective83_results.csv"), csv)?;
    let mut monthly_csv = String::from("hypothesis_id,month,n,ev_cents,win_rate\n");
    let mut boots = serde_json::Map::new();
    let mut perms = serde_json::Map::new();
    let mut costs = serde_json::Map::new();
    let mut concs = serde_json::Map::new();
    for c in &report.candidates {
        let id = c["hypothesis_id"].as_str().unwrap_or("");
        if let Some(arr) = c["monthly"].as_array() {
            for row in arr {
                monthly_csv.push_str(&format!(
                    "{},{},{},{},{}\n",
                    id,
                    row["month"].as_str().unwrap_or(""),
                    row["n"].as_u64().unwrap_or(0),
                    row["ev_cents"]
                        .as_f64()
                        .map(|x| format!("{x:.4}"))
                        .unwrap_or_default(),
                    row["win_rate"]
                        .as_f64()
                        .map(|x| format!("{x:.4}"))
                        .unwrap_or_default(),
                ));
            }
        }
        boots.insert(id.to_string(), c["bootstrap"].clone());
        perms.insert(id.to_string(), c["permutation_p"].clone());
        costs.insert(id.to_string(), c["cost_sensitivity"].clone());
        concs.insert(id.to_string(), c["concentration"].clone());
    }
    if monthly_csv.lines().count() <= 1 {
        monthly_csv.push_str("# no prospective observations\n");
    }
    fs::write(dir.join("prospective83_monthly.csv"), monthly_csv)?;
    let empty_note = coverage.status == "PROSPECTIVE_DATA_NOT_YET_AVAILABLE";
    fs::write(
        dir.join("prospective83_bootstrap.json"),
        serde_json::to_string_pretty(&serde_json::json!({
            "status": coverage.status,
            "unit": "GAME",
            "by_hypothesis": boots,
            "note": if empty_note { "Primary holdout result recorded as insufficient data." } else { "Game-level bootstrap of frozen candidates only." }
        }))?,
    )?;
    fs::write(
        dir.join("prospective83_permutation.json"),
        serde_json::to_string_pretty(&serde_json::json!({
            "status": coverage.status,
            "h0": "candidate membership has no relationship with settlement outcome",
            "by_hypothesis": perms
        }))?,
    )?;
    fs::write(
        dir.join("prospective83_cost_sensitivity.json"),
        serde_json::to_string_pretty(&serde_json::json!({
            "status": coverage.status,
            "fee_model": "HYPOTHETICAL_RESEARCH_COST",
            "not_kalshi_fee_model": true,
            "by_hypothesis": costs
        }))?,
    )?;
    fs::write(
        dir.join("prospective83_threshold_sensitivity.json"),
        serde_json::to_string_pretty(&serde_json::json!({
            "status": if empty_note { "SECONDARY_NOT_RUN_NO_HOLDOUT" } else { "SECONDARY_NOT_RUN_PRIMARY_LOCKED" },
            "note": "Secondary threshold exploration must not replace the frozen primary result."
        }))?,
    )?;
    fs::write(
        dir.join("prospective83_concentration.json"),
        serde_json::to_string_pretty(&serde_json::json!({
            "status": coverage.status,
            "by_hypothesis": concs
        }))?,
    )?;
    fs::write(
        dir.join("prospective83_data_quality.json"),
        serde_json::to_string_pretty(&coverage)?,
    )?;
    fs::write(
        dir.join("prospective83_search_registry.json"),
        serde_json::to_string_pretty(&serde_json::json!({
            "total_hypotheses_tested": report.candidates.len(),
            "frozen_predeclared": frozen_candidates().len(),
            "benchmarks": 2,
            "1_way": 1,
            "2_way": 1,
            "3_way": 4,
            "4_way": 0,
            "threshold_variants": 0,
            "new_discovery_this_run": 0,
            "effective_tests_this_run": report.candidates.len(),
            "fdr_procedure": "Discovery BH q lives on the 6,128-test historical search (DISCOVERY_FDR). This run is PROSPECTIVE_VALIDATION of frozen IDs only. No new FDR.",
            "post_holdout_discovery": 0
        }))?,
    )?;
    fs::write(dir.join("prospective83_report.md"), render_report(report))?;
    fs::write(
        dir.join("prospective83_summary.json"),
        serde_json::to_string_pretty(report)?,
    )?;
    Ok(())
}

fn executive_table(report: &ProspectiveReport) -> String {
    report
        .candidates
        .iter()
        .map(|c| {
            let ci = c["bootstrap"]["ci95"]
                .as_array()
                .map(|a| {
                    format!(
                        "[{:.2}, {:.2}]",
                        a.first().and_then(|x| x.as_f64()).unwrap_or(0.0),
                        a.get(1).and_then(|x| x.as_f64()).unwrap_or(0.0)
                    )
                })
                .unwrap_or_else(|| "—".into());
            format!(
                "| {} | {:+.2}¢ | {} | {} | {} | {} | {} |",
                c["name"].as_str().unwrap_or(""),
                c["historical"]["test_ev"].as_f64().unwrap_or(0.0),
                c["prospective"]["n_unique_games"].as_u64().unwrap_or(0),
                c["prospective"]["ev_cents"]
                    .as_f64()
                    .map(|x| format!("{x:+.2}¢"))
                    .unwrap_or_else(|| "—".into()),
                ci,
                c["cost_survival_max_cents"]
                    .as_f64()
                    .map(|x| format!("{x:.1}¢"))
                    .unwrap_or_else(|| "—".into()),
                c["classification"].as_str().unwrap_or(""),
            )
        })
        .collect::<Vec<_>>()
        .join("\n")
}

fn render_report(report: &ProspectiveReport) -> String {
    let cov = &report.coverage;
    format!(
        "# Prospective validation of frozen 83¢ entry states\n\n\
## DOES ANY FROZEN 83¢ STATE SURVIVE PROSPECTIVE VALIDATION?\n\n\
**{}**\n\n\
{}\n\n\
PRODUCTION_COUNT = {}\n\n\
Fill = `{}`. L2 = `{}`.\n\n\
## Coverage\n\n\
| Field | Value |\n|---|---:|\n\
| existing locked TEST cutoff | {} |\n\
| prospective start | {} |\n\
| prospective end (W6 observed) | {} |\n\
| W6 eligible games after cutoff | {} |\n\
| W7 reconstructed games (all time) | {} |\n\
| W7 ∩ post-cutoff W6 | {} |\n\
| first-exact-83 in holdout | {} |\n\
| excluded (no W7 path) | {} |\n\n\
{}\n\n\
## Executive table\n\n\
| Candidate | Historical TEST EV | Prospective N | Prospective EV | 95% CI | Cost survival | Classification |\n\
|---|---:|---:|---:|---|---|---|\n\
{}\n\n\
## Distinctions\n\n\
| Layer | Status |\n|---|---|\n\
| historical backtest (TRAIN/VAL) | frozen; not re-selected |\n\
| locked TEST through {} | CONSUMED; not used to pick winners |\n\
| prospective evidence | **not yet available** |\n\
| production evidence | none; PRODUCTION_COUNT=0 |\n\n\
## Why the holdout is empty\n\n\
W6 canonical state includes games {} through {}. W7 EventMarketPath and W8 replay stop at {}. \
A first-exact-83 snapshot requires a W7 TRADE print at 83¢. Using W6 scores/innings without a \
TRADE print would invent the research unit. That is forbidden.\n\n\
## Frozen definitions (do not edit to improve a score)\n\n\
See `prospective83_candidates.json`. Historical TEST is locked/consumed.\n\n\
| ID | Condition | Why frozen | Hist TEST |\n|---|---|---|---:|\n\
| CAND_A_40_49 | `start_price_band=40_49` | simplest +EV 1-way; discovery q=0.173 | +2.41¢ |\n\
| CAND_B_MOVE30_OUTS0_VOL1M_LOW | `start_move_gt30=YES&outs=0&vol_1m_tertile=LOW` | predeclared priority 3-way | +12.12¢ |\n\
| CAND_C_LEAD2_MOVE30_VOL1M_LOW | `lead_signed=LEAD_2&start_move_gt30=YES&vol_1m_tertile=LOW` | predeclared | +3.96¢ |\n\
| CAND_D_TWORUN_MOVE30_VOL1M_LOW | `score_bucket=TWO_RUN&start_move_gt30=YES&vol_1m_tertile=LOW` | predeclared (near-dup C) | +3.96¢ |\n\
| CAND_E_MOVEFINE_VOL_LOW | `move_fine=30_35&vol_1m_tertile=LOW&vol_15m_tertile=LOW` | predeclared | +4.25¢ |\n\
| CAND_F_INNING7_PEAK_AT | `inning_grp=7&p_max_vs_83=PEAK_AT` | VAL-selected; less weight | +2.42¢ |\n\n\
No prospective EV, CI, cost, or threshold result exists for any of these.\n\n\
## Secondary analyses\n\n\
Bootstrap, permutation, cost grid, threshold sensitivity, and new discovery were **not run**. \
They must not replace a missing primary holdout.\n\n\
## Reproducibility\n\n\
```text\n\
./target/release/momento-research-b1 --validate-83-prospective\n\
```\n\n\
Research only. No live FIRST01 / 80/81/83/89 / stop / risk / W9 / L2 / orders.\n",
        report.answer,
        report.headline,
        report.production_count,
        report.fill_status,
        report.l2_status,
        cov.existing_cutoff,
        cov.prospective_start,
        cov.prospective_end.as_deref().unwrap_or("—"),
        cov.w6_eligible_games,
        cov.w7_path_games,
        cov.w7_post_cutoff_games,
        cov.first83_eligible,
        cov.excluded_no_w7_path,
        cov.excluded_reason,
        executive_table(report),
        cov.existing_cutoff,
        cov.w6_date_min.as_deref().unwrap_or("—"),
        cov.w6_date_max.as_deref().unwrap_or("—"),
        cov.existing_cutoff,
    )
}

/// Verify a frozen condition still reconstructs on the locked first83 extract.
pub fn verify_frozen_on_locked(
    first83_sqlite: &Path,
    condition: &str,
) -> Result<Option<(usize, usize, usize)>, B1Error> {
    if !first83_sqlite.exists() {
        return Ok(None);
    }
    let spec = ConfiguredSearchSpec {
        features_sqlite: first83_sqlite.to_path_buf(),
        include_unconditional: false,
        parameters: condition_to_params(condition)?,
        ..ConfiguredSearchSpec::default()
    };
    let (rows, _, _, _, _) =
        prepare_search_rows(&spec.features_sqlite, &spec.train_before, &spec.val_before)?;
    let cond = parse_cond(condition);
    let mut tn = BTreeSet::new();
    let mut vn = BTreeSet::new();
    let mut xn = BTreeSet::new();
    for r in &rows {
        if !cond_ok(r, &cond) {
            continue;
        }
        match r.chrono {
            crate::search::ChronoSplit::Train => {
                tn.insert(r.game_id.as_str());
            }
            crate::search::ChronoSplit::Validation => {
                vn.insert(r.game_id.as_str());
            }
            crate::search::ChronoSplit::Test => {
                xn.insert(r.game_id.as_str());
            }
        }
    }
    Ok(Some((tn.len(), vn.len(), xn.len())))
}

fn condition_to_params(condition: &str) -> Result<Vec<ParameterSpec>, B1Error> {
    let pairs = parse_cond(condition);
    if pairs.is_empty() {
        return Err(B1Error::validation("EMPTY", "empty frozen condition"));
    }
    Ok(pairs
        .into_iter()
        .map(|(n, v)| ParameterSpec::list(n, vec![v]))
        .collect())
}

fn overlap_game_ids(args: &ProspectiveArgs) -> Result<Vec<String>, B1Error> {
    let cov = scan_prospective_coverage(args)?;
    if cov.w7_post_cutoff_games == 0 {
        return Ok(Vec::new());
    }
    let w6 = Connection::open(&args.w6_sqlite)?;
    let w6_ids: BTreeSet<String> = w6
        .prepare(
            "SELECT game_id FROM games
             WHERE official_date > ?1 AND official_date >= ?2
               AND (?3 IS NULL OR official_date <= ?3)
               AND status = 'OK'",
        )?
        .query_map(
            rusqlite::params![
                args.cutoff,
                args.prospective_start,
                args.prospective_end.as_deref()
            ],
            |r| r.get::<_, String>(0),
        )?
        .flatten()
        .collect();
    let w7 = Connection::open(&args.w7_sqlite)?;
    let w7_ids: BTreeSet<String> = w7
        .prepare("SELECT DISTINCT game_id FROM game_path_coverage")?
        .query_map([], |r| r.get::<_, String>(0))?
        .flatten()
        .collect();
    Ok(w6_ids.intersection(&w7_ids).cloned().collect())
}

fn prepare_holdout_rows(
    snaps: &[crate::types::B1EntrySnapshot],
    cuts: &serde_json::Value,
    cutoff: &str,
    locked_ids: &BTreeSet<String>,
) -> Result<Vec<SearchRow>, B1Error> {
    let mut seen = BTreeSet::new();
    for s in snaps {
        if s.official_date.as_deref().unwrap_or("") <= cutoff {
            return Err(B1Error::validation(
                "LEAK_CUTOFF",
                format!("holdout snapshot {} predates cutoff", s.game_id),
            ));
        }
        if locked_ids.contains(&s.game_id) {
            return Err(B1Error::validation(
                "TEST_LEAK",
                format!(
                    "holdout game {} is already in the locked first83 extract",
                    s.game_id
                ),
            ));
        }
        if !seen.insert(s.game_id.as_str()) {
            return Err(B1Error::validation(
                "DUP_GAME",
                format!("duplicate holdout game {}", s.game_id),
            ));
        }
        if !matches!(
            s.outcomes.settlement,
            crate::types::SettlementOutcome::Win | crate::types::SettlementOutcome::Loss
        ) {
            return Err(B1Error::validation(
                "NO_SETTLEMENT",
                format!("holdout game {} has no settlement outcome", s.game_id),
            ));
        }
    }
    let mut rows: Vec<SearchRow> = snaps.iter().map(flatten).collect();
    for r in &mut rows {
        r.chrono = ChronoSplit::Test;
    }
    apply_locked_tertiles(&mut rows, snaps, cuts);
    for (r, s) in rows.iter_mut().zip(snaps.iter()) {
        enrich(r, s);
        enrich_opt(r, s);
        enrich_exh(r, s);
        apply_locked_tertiles(std::slice::from_mut(r), std::slice::from_ref(s), cuts);
        assert_no_leakage(
            &r.feats
                .keys()
                .map(|k| (k.clone(), String::new()))
                .collect::<Vec<_>>(),
        )?;
        if r.date.as_str() <= cutoff {
            return Err(B1Error::validation(
                "LEAK_CUTOFF",
                format!("row {} date {} ≤ cutoff", r.game_id, r.date),
            ));
        }
    }
    Ok(rows)
}

pub fn run_prospective_validation(args: &ProspectiveArgs) -> Result<ProspectiveReport, B1Error> {
    assert_no_holdout_overlap(&args.prospective_start, &args.cutoff)?;
    let mut coverage = scan_prospective_coverage(args)?;
    let frozen = selected_candidates(args)?;
    let tertiles = locked_train_tertiles(&args.first83_sqlite)?;
    let holdout_rows = if coverage.w7_post_cutoff_games == 0 {
        Vec::new()
    } else {
        let ids = overlap_game_ids(args)?;
        let locked = locked_game_ids(&args.first83_sqlite)?;
        for gid in &ids {
            if locked.contains(gid) {
                return Err(B1Error::validation(
                    "TEST_LEAK",
                    format!("W7 holdout game {gid} is already in locked first83"),
                ));
            }
        }
        let mut cfg = B1RunConfig::defaults();
        cfg.w6_sqlite = args.w6_sqlite.clone();
        cfg.w7_sqlite = args.w7_sqlite.clone();
        cfg.w8_sqlite = args.w8_sqlite.clone();
        cfg.identity_landing = args.identity_landing.clone();
        let extract_db = args.out_dir.join("features.sqlite");
        let extract = run_first83_extract_subset(&cfg, &ids, &extract_db, &args.cutoff)?;
        coverage.first83_eligible = extract.unique_games;
        coverage.excluded_reason = format!(
            "W7 overlap {}; first-83 snapshots {}; never 83 {}; bound never 83 {}",
            ids.len(),
            extract.unique_games,
            extract.skipped_no_83,
            extract.skipped_bound_contract_no_83
        );
        if extract.unique_games == 0 {
            Vec::new()
        } else {
            let store = FeatureStore::open_existing(&extract_db)?;
            let snaps = store.load_all()?;
            prepare_holdout_rows(&snaps, &tertiles, &args.cutoff, &locked)?
        }
    };
    if coverage.w7_post_cutoff_games == 0 || holdout_rows.is_empty() {
        coverage.status = "PROSPECTIVE_DATA_NOT_YET_AVAILABLE".into();
        if coverage.w7_post_cutoff_games == 0 {
            coverage.first83_eligible = 0;
        }
    } else {
        coverage.status = "PROSPECTIVE_EVALUATED".into();
        coverage.first83_eligible = holdout_rows.len();
    }
    let all_pnls = game_pnls(&holdout_rows.iter().collect::<Vec<_>>(), PRIMARY);
    let all_m = metrics(&holdout_rows.iter().collect::<Vec<_>>(), PRIMARY);
    let mut candidates: Vec<serde_json::Value> = if holdout_rows.is_empty() {
        frozen
            .iter()
            .map(|c| empty_eval(c, coverage.w6_eligible_games))
            .collect()
    } else {
        frozen
            .iter()
            .map(|c| eval_on_holdout(c, &holdout_rows, &all_pnls, all_m.ev_cents, args))
            .collect()
    };
    candidates.push(serde_json::json!({
        "hypothesis_id": "BENCH_ALL_FIRST83",
        "name": "ALL_FIRST83",
        "condition": "",
        "why_frozen": "Unconditional first-exact-83 benchmark.",
        "search_stage": "BENCHMARK",
        "historical": { "train_ev": 0.11, "val_ev": -0.81, "test_ev": 1.43, "train_n": 1699, "val_n": 494, "test_n": 713 },
        "layer": "PROSPECTIVE_VALIDATION",
        "prospective": if holdout_rows.is_empty() {
            serde_json::json!({"n_games": 0, "n_unique_games": 0, "ev_cents": null, "status": "PROSPECTIVE_DATA_NOT_YET_AVAILABLE"})
        } else {
            serde_json::json!({
                "n_games": all_m.n_entries,
                "n_unique_games": all_m.n_unique_games,
                "ev_cents": all_m.ev_cents,
                "win_rate": all_m.win_rate,
                "pnl_usd": all_m.total_pnl_usd,
                "status": "EVALUATED"
            })
        },
        "classification": if holdout_rows.is_empty() { "INSUFFICIENT_DATA" } else { "BENCHMARK" },
        "labels": { "DISCOVERY_FDR": null, "PROSPECTIVE_VALIDATION": if holdout_rows.is_empty() { "NOT_RUN" } else { "RUN" } }
    }));
    candidates.push(serde_json::json!({
        "hypothesis_id": "BENCH_NO_ENTRY",
        "name": "do nothing",
        "condition": "NO_ENTRY",
        "why_frozen": "No-entry baseline.",
        "search_stage": "BENCHMARK",
        "historical": { "train_ev": 0.0, "val_ev": 0.0, "test_ev": 0.0, "train_n": 0, "val_n": 0, "test_n": 0 },
        "layer": "PROSPECTIVE_VALIDATION",
        "prospective": { "n_games": 0, "n_unique_games": 0, "ev_cents": 0.0, "pnl_usd": 0.0 },
        "classification": if holdout_rows.is_empty() { "INSUFFICIENT_DATA" } else { "BENCHMARK" },
        "labels": { "DISCOVERY_FDR": null, "PROSPECTIVE_VALIDATION": "BASELINE" }
    }));
    let any_pos = candidates.iter().any(|c| {
        c["search_stage"] == "FROZEN_PREDECLARED"
            && c["classification"] != "INSUFFICIENT_DATA"
            && c["classification"] != "FAIL"
            && c["prospective"]["ev_cents"]
                .as_f64()
                .is_some_and(|x| x > 0.0)
    });
    let robust = candidates
        .iter()
        .any(|c| c["classification"] == "ROBUST_RESEARCH_FINDING");
    let (answer, headline) = if holdout_rows.is_empty() {
        (
            "INSUFFICIENT DATA".into(),
            "W6 has post-cutoff games, but W7 TRADE paths do not (or none printed 83¢). \
No first-exact-83 prospective observation exists. \
NO ROBUST 83¢ ENTRY EDGE FOUND — holdout not yet evaluable."
                .into(),
        )
    } else if robust {
        (
            "YES".into(),
            "A frozen candidate met the ROBUST_RESEARCH_FINDING bar on the holdout. Not production."
                .into(),
        )
    } else if any_pos {
        (
            "NO".into(),
            "At least one frozen cell was positive on the holdout, but none cleared ROBUST_RESEARCH_FINDING. PRODUCTION_COUNT=0."
                .into(),
        )
    } else {
        (
            "NO".into(),
            "NO ROBUST 83¢ ENTRY EDGE FOUND. Frozen candidates did not survive the untouched holdout."
                .into(),
        )
    };
    let report = ProspectiveReport {
        answer,
        headline,
        production_count: 0,
        fill_status: FILL_STATUS,
        l2_status: "UNAVAILABLE_SOURCE",
        feature_schema_version: FEATURE_SCHEMA_VERSION,
        engine_version: ENGINE_VERSION,
        discovery_tests: 6128,
        frozen_candidates: frozen.len(),
        coverage,
        candidates,
        locked_train_tertiles: tertiles,
        abort_reason: None,
    };
    write_artifacts(&args.out_dir, &report)?;
    let _ = bootstrap_ev_ci(&[], PRIMARY, 10, args.seed);
    Ok(report)
}

pub fn load_prospective_summary(dir: &Path) -> Result<Option<serde_json::Value>, B1Error> {
    let p = dir.join("prospective83_summary.json");
    if !p.exists() {
        return Ok(None);
    }
    Ok(Some(serde_json::from_str(&fs::read_to_string(p)?)?))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn frozen_ids_and_keys_are_stable() {
        let cs = frozen_candidates();
        assert_eq!(cs.len(), 6);
        assert_eq!(cs[0].condition, "start_price_band=40_49");
        assert_eq!(
            cs[1].condition,
            "start_move_gt30=YES&outs=0&vol_1m_tertile=LOW"
        );
        assert!(cs[5].why_frozen.contains("VAL-selected"));
        assert_eq!(cs[0].historical.test_n, 233);
        assert_eq!(cs[1].historical.test_n, 41);
    }

    #[test]
    fn holdout_cannot_start_on_or_before_cutoff() {
        assert!(assert_no_holdout_overlap("2026-06-27", "2026-06-27").is_err());
        assert!(assert_no_holdout_overlap("2026-05-03", "2026-06-27").is_err());
        assert!(assert_no_holdout_overlap("2026-06-28", "2026-06-27").is_ok());
    }

    #[test]
    fn locked_candidate_b_still_matches_published_n() {
        let p = Path::new("Backtesting Suite/Foundation/B1/first83/features.sqlite");
        let p = if p.exists() {
            p.to_path_buf()
        } else {
            Path::new("../../Backtesting Suite/Foundation/B1/first83/features.sqlite").to_path_buf()
        };
        let Some((t, v, x)) =
            verify_frozen_on_locked(&p, "start_move_gt30=YES&outs=0&vol_1m_tertile=LOW")
                .expect("verify")
        else {
            return;
        };
        assert_eq!((t, v, x), (62, 28, 41));
    }

    #[test]
    fn empty_holdout_does_not_invent_ev() {
        let tmp = tempfile::tempdir().unwrap();
        let mut args = ProspectiveArgs::defaults(tmp.path());
        args.out_dir = tmp.path().join("out");
        args.w6_sqlite = tmp.path().join("missing-w6.sqlite");
        let report = run_prospective_validation(&args).unwrap();
        assert_eq!(report.answer, "INSUFFICIENT DATA");
        assert_eq!(report.production_count, 0);
        for c in &report.candidates {
            assert_eq!(c["classification"], "INSUFFICIENT_DATA");
            if c["search_stage"] == "FROZEN_PREDECLARED" {
                assert!(c["prospective"]["ev_cents"].is_null());
            }
        }
        assert!(args.out_dir.join("prospective83_report.md").exists());
    }

    #[test]
    fn unknown_candidate_set_is_rejected() {
        let tmp = tempfile::tempdir().unwrap();
        let mut args = ProspectiveArgs::defaults(tmp.path());
        args.out_dir = tmp.path().join("out");
        args.w6_sqlite = tmp.path().join("missing-w6.sqlite");
        args.candidate_set = Some(vec!["NOT_A_FROZEN_ID".into()]);
        let err = run_prospective_validation(&args).unwrap_err();
        assert!(err.to_string().contains("UNKNOWN_CANDIDATE"));
    }
}
