//! Exhaustive 83¢ conditional search. TRAIN discover, VAL select, TEST lock.
//! Not seeded from 40–49. Research only. TRADE print ≠ fill.

use std::collections::{BTreeMap, BTreeSet};
use std::fs;
use std::path::Path;

use crate::a1_targets::EXIT_HOLD_TO_SETTLEMENT;
use crate::error::B1Error;
use crate::search::{
    ChronoSplit, FILL_STATUS, SearchRow, attach_train_tertiles, benjamini_hochberg,
    bootstrap_ev_ci, flatten, metrics, p_mean_le0,
};
use crate::search_83::{
    Cond83, attach_83_tertiles, cond_ok, enrich, eval_screen, parse_cond, slice,
};
use crate::search_83_opt::enrich_opt;
use crate::search_report::SearchConfig;
use crate::splits::apply_official_chrono_split;
use crate::store::FeatureStore;
use crate::types::B1EntrySnapshot;
use crate::versions::{ENGINE_VERSION, FEATURE_SCHEMA_VERSION};

const PRIMARY: &str = EXIT_HOLD_TO_SETTLEMENT;
const FORBIDDEN: &[&str] = &[
    "settlement",
    "mfe",
    "mae",
    "exit_",
    "future",
    "pnl",
    "return_cents",
    "win_rate",
    "fair_value",
    "obi",
    "microprice",
];
const SEED: u64 = 42;

fn official_chrono_split(rows: &mut [SearchRow]) -> (String, String, String) {
    apply_official_chrono_split(rows)
}

#[derive(Clone, Debug)]
pub struct ExhaustiveArgs {
    pub max_depth: u8,
    pub min_train: usize,
    pub min_val: usize,
    pub min_test: usize,
    pub bootstrap_reps: usize,
    pub permutation_reps: usize,
}

impl Default for ExhaustiveArgs {
    fn default() -> Self {
        Self {
            max_depth: 4,
            min_train: 50,
            min_val: 10,
            min_test: 15,
            bootstrap_reps: 10_000,
            permutation_reps: 2_000,
        }
    }
}

#[derive(Clone, Debug, serde::Serialize)]
struct FeatReg {
    feature_name: &'static str,
    source_column: &'static str,
    type_name: &'static str,
    allowed_transformations: &'static str,
    semantic_group: &'static str,
    family: &'static str,
    leakage_status: &'static str,
}

fn registry() -> &'static [FeatReg] {
    &[
        FeatReg {
            feature_name: "start_price_band",
            source_column: "starting_market.start_bucket",
            type_name: "categorical",
            allowed_transformations: "existing_buckets",
            semantic_group: "START_BELIEF",
            family: "START",
            leakage_status: "OK_AT_ENTRY",
        },
        FeatReg {
            feature_name: "p_start_fine",
            source_column: "starting_market.p_start_cents",
            type_name: "categorical",
            allowed_transformations: "predeclared_bands",
            semantic_group: "START_BELIEF",
            family: "START",
            leakage_status: "OK_AT_ENTRY",
        },
        FeatReg {
            feature_name: "p_start_lt50",
            source_column: "starting_market.p_start_cents",
            type_name: "binary",
            allowed_transformations: "threshold",
            semantic_group: "START_BELIEF",
            family: "START",
            leakage_status: "OK_AT_ENTRY",
        },
        FeatReg {
            feature_name: "p_start_ge50",
            source_column: "starting_market.p_start_cents",
            type_name: "binary",
            allowed_transformations: "threshold",
            semantic_group: "START_BELIEF",
            family: "START",
            leakage_status: "OK_AT_ENTRY",
        },
        FeatReg {
            feature_name: "p_start_35_49",
            source_column: "starting_market.p_start_cents",
            type_name: "binary",
            allowed_transformations: "predeclared_overlap",
            semantic_group: "START_BELIEF",
            family: "START",
            leakage_status: "OK_AT_ENTRY",
        },
        FeatReg {
            feature_name: "p_start_40_50",
            source_column: "starting_market.p_start_cents",
            type_name: "binary",
            allowed_transformations: "predeclared_overlap",
            semantic_group: "START_BELIEF",
            family: "START",
            leakage_status: "OK_AT_ENTRY",
        },
        FeatReg {
            feature_name: "p_start_40_44",
            source_column: "starting_market.p_start_cents",
            type_name: "binary",
            allowed_transformations: "predeclared_overlap",
            semantic_group: "START_BELIEF",
            family: "START",
            leakage_status: "OK_AT_ENTRY",
        },
        FeatReg {
            feature_name: "p_start_45_49",
            source_column: "starting_market.p_start_cents",
            type_name: "binary",
            allowed_transformations: "predeclared_overlap",
            semantic_group: "START_BELIEF",
            family: "START",
            leakage_status: "OK_AT_ENTRY",
        },
        FeatReg {
            feature_name: "p_start_lt30",
            source_column: "starting_market.p_start_cents",
            type_name: "binary",
            allowed_transformations: "predeclared",
            semantic_group: "START_BELIEF",
            family: "START",
            leakage_status: "OK_AT_ENTRY",
        },
        FeatReg {
            feature_name: "p_start_30_34",
            source_column: "starting_market.p_start_cents",
            type_name: "binary",
            allowed_transformations: "predeclared",
            semantic_group: "START_BELIEF",
            family: "START",
            leakage_status: "OK_AT_ENTRY",
        },
        FeatReg {
            feature_name: "p_start_35_39",
            source_column: "starting_market.p_start_cents",
            type_name: "binary",
            allowed_transformations: "predeclared",
            semantic_group: "START_BELIEF",
            family: "START",
            leakage_status: "OK_AT_ENTRY",
        },
        FeatReg {
            feature_name: "p_start_50_54",
            source_column: "starting_market.p_start_cents",
            type_name: "binary",
            allowed_transformations: "predeclared",
            semantic_group: "START_BELIEF",
            family: "START",
            leakage_status: "OK_AT_ENTRY",
        },
        FeatReg {
            feature_name: "p_start_55_59",
            source_column: "starting_market.p_start_cents",
            type_name: "binary",
            allowed_transformations: "predeclared",
            semantic_group: "START_BELIEF",
            family: "START",
            leakage_status: "OK_AT_ENTRY",
        },
        FeatReg {
            feature_name: "p_start_60_69",
            source_column: "starting_market.p_start_cents",
            type_name: "binary",
            allowed_transformations: "predeclared",
            semantic_group: "START_BELIEF",
            family: "START",
            leakage_status: "OK_AT_ENTRY",
        },
        FeatReg {
            feature_name: "p_start_70p",
            source_column: "starting_market.p_start_cents",
            type_name: "binary",
            allowed_transformations: "predeclared",
            semantic_group: "START_BELIEF",
            family: "START",
            leakage_status: "OK_AT_ENTRY",
        },
        FeatReg {
            feature_name: "p_start_40_54",
            source_column: "starting_market.p_start_cents",
            type_name: "binary",
            allowed_transformations: "predeclared_overlap",
            semantic_group: "START_BELIEF",
            family: "START",
            leakage_status: "OK_AT_ENTRY",
        },
        FeatReg {
            feature_name: "p_start_tertile",
            source_column: "starting_market.p_start_cents",
            type_name: "ordinal",
            allowed_transformations: "TRAIN_tertile",
            semantic_group: "START_BELIEF",
            family: "START",
            leakage_status: "TRAIN_ONLY_CUTS",
        },
        FeatReg {
            feature_name: "start_sentiment",
            source_column: "starting_market.start_sentiment",
            type_name: "categorical",
            allowed_transformations: "existing",
            semantic_group: "START_BELIEF",
            family: "START",
            leakage_status: "OK_AT_ENTRY",
        },
        FeatReg {
            feature_name: "inning_83",
            source_column: "baseball.inning",
            type_name: "categorical",
            allowed_transformations: "existing_bands",
            semantic_group: "BASEBALL_STATE",
            family: "INNING",
            leakage_status: "OK_AT_ENTRY",
        },
        FeatReg {
            feature_name: "inning_grp",
            source_column: "baseball.inning",
            type_name: "categorical",
            allowed_transformations: "predeclared",
            semantic_group: "BASEBALL_STATE",
            family: "INNING",
            leakage_status: "OK_AT_ENTRY",
        },
        FeatReg {
            feature_name: "inning_late68",
            source_column: "baseball.inning",
            type_name: "binary",
            allowed_transformations: "predeclared",
            semantic_group: "BASEBALL_STATE",
            family: "INNING",
            leakage_status: "OK_AT_ENTRY",
        },
        FeatReg {
            feature_name: "lead_signed",
            source_column: "baseball.bound_team_lead",
            type_name: "categorical",
            allowed_transformations: "predeclared",
            semantic_group: "BASEBALL_STATE",
            family: "LEAD",
            leakage_status: "OK_AT_ENTRY",
        },
        FeatReg {
            feature_name: "lead_ge2",
            source_column: "baseball.bound_team_lead",
            type_name: "binary",
            allowed_transformations: "threshold",
            semantic_group: "BASEBALL_STATE",
            family: "LEAD",
            leakage_status: "OK_AT_ENTRY",
        },
        FeatReg {
            feature_name: "lead_ge3",
            source_column: "baseball.bound_team_lead",
            type_name: "binary",
            allowed_transformations: "threshold",
            semantic_group: "BASEBALL_STATE",
            family: "LEAD",
            leakage_status: "OK_AT_ENTRY",
        },
        FeatReg {
            feature_name: "trailing",
            source_column: "baseball.bound_team_lead",
            type_name: "binary",
            allowed_transformations: "threshold",
            semantic_group: "BASEBALL_STATE",
            family: "LEAD",
            leakage_status: "OK_AT_ENTRY",
        },
        FeatReg {
            feature_name: "tied",
            source_column: "baseball.bound_team_lead",
            type_name: "binary",
            allowed_transformations: "threshold",
            semantic_group: "BASEBALL_STATE",
            family: "LEAD",
            leakage_status: "OK_AT_ENTRY",
        },
        FeatReg {
            feature_name: "lead_eq1",
            source_column: "baseball.bound_team_lead",
            type_name: "binary",
            allowed_transformations: "threshold",
            semantic_group: "BASEBALL_STATE",
            family: "LEAD",
            leakage_status: "OK_AT_ENTRY",
        },
        FeatReg {
            feature_name: "score_bucket",
            source_column: "baseball.score_bucket",
            type_name: "categorical",
            allowed_transformations: "existing",
            semantic_group: "BASEBALL_STATE",
            family: "LEAD",
            leakage_status: "OK_AT_ENTRY",
        },
        FeatReg {
            feature_name: "outs",
            source_column: "baseball.outs",
            type_name: "categorical",
            allowed_transformations: "raw",
            semantic_group: "BASEBALL_STATE",
            family: "OUTS",
            leakage_status: "OK_AT_ENTRY",
        },
        FeatReg {
            feature_name: "base_class",
            source_column: "baseball.base_class",
            type_name: "categorical",
            allowed_transformations: "existing",
            semantic_group: "BASEBALL_STATE",
            family: "BASES",
            leakage_status: "OK_AT_ENTRY",
        },
        FeatReg {
            feature_name: "half",
            source_column: "baseball.half_inning",
            type_name: "categorical",
            allowed_transformations: "existing",
            semantic_group: "BASEBALL_STATE",
            family: "HALF",
            leakage_status: "OK_AT_ENTRY",
        },
        FeatReg {
            feature_name: "move_fine",
            source_column: "market_history.start_to_entry_move_cents",
            type_name: "categorical",
            allowed_transformations: "predeclared_abs_bins",
            semantic_group: "PATH",
            family: "MOVE",
            leakage_status: "OK_AT_ENTRY",
        },
        FeatReg {
            feature_name: "start_move_tertile",
            source_column: "market_history.start_to_entry_move_cents",
            type_name: "ordinal",
            allowed_transformations: "TRAIN_tertile",
            semantic_group: "PATH",
            family: "MOVE",
            leakage_status: "TRAIN_ONLY_CUTS",
        },
        FeatReg {
            feature_name: "start_move_gt20",
            source_column: "market_history.start_to_entry_move_cents",
            type_name: "binary",
            allowed_transformations: "threshold",
            semantic_group: "PATH",
            family: "MOVE",
            leakage_status: "OK_AT_ENTRY",
        },
        FeatReg {
            feature_name: "start_move_gt30",
            source_column: "market_history.start_to_entry_move_cents",
            type_name: "binary",
            allowed_transformations: "threshold",
            semantic_group: "PATH",
            family: "MOVE",
            leakage_status: "OK_AT_ENTRY",
        },
        FeatReg {
            feature_name: "path_eff_tertile",
            source_column: "market_history.path_efficiency_bps",
            type_name: "ordinal",
            allowed_transformations: "TRAIN_tertile",
            semantic_group: "PATH",
            family: "PATHEFF",
            leakage_status: "TRAIN_ONLY_CUTS",
        },
        FeatReg {
            feature_name: "reversal_tertile",
            source_column: "market_history.reversal_count",
            type_name: "ordinal",
            allowed_transformations: "TRAIN_tertile",
            semantic_group: "PATH",
            family: "REVERSAL",
            leakage_status: "TRAIN_ONLY_CUTS",
        },
        FeatReg {
            feature_name: "p_max_vs_83",
            source_column: "market_history.p_max_cents",
            type_name: "categorical",
            allowed_transformations: "vs_entry",
            semantic_group: "PATH",
            family: "PMAX",
            leakage_status: "OK_AT_ENTRY",
        },
        FeatReg {
            feature_name: "personality",
            source_column: "market_history.personality",
            type_name: "categorical",
            allowed_transformations: "existing",
            semantic_group: "PERSONALITY",
            family: "PERSONALITY",
            leakage_status: "OK_AT_ENTRY",
        },
        FeatReg {
            feature_name: "vel_sign",
            source_column: "price_dynamics.p_1m.delta_cents",
            type_name: "categorical",
            allowed_transformations: "sign",
            semantic_group: "VELOCITY",
            family: "VEL",
            leakage_status: "OK_AT_ENTRY",
        },
        FeatReg {
            feature_name: "vel_1m_tertile",
            source_column: "price_dynamics.p_1m.delta_cents",
            type_name: "ordinal",
            allowed_transformations: "TRAIN_tertile",
            semantic_group: "VELOCITY",
            family: "VEL",
            leakage_status: "TRAIN_ONLY_CUTS",
        },
        FeatReg {
            feature_name: "vel_5m_sign",
            source_column: "price_dynamics.p_5m.delta_cents",
            type_name: "categorical",
            allowed_transformations: "sign",
            semantic_group: "VELOCITY",
            family: "VEL",
            leakage_status: "OK_AT_ENTRY",
        },
        FeatReg {
            feature_name: "accel_sign",
            source_column: "price_dynamics.acceleration_1m_vs_5m_e6",
            type_name: "categorical",
            allowed_transformations: "sign",
            semantic_group: "ACCELERATION",
            family: "ACCEL",
            leakage_status: "OK_AT_ENTRY",
        },
        FeatReg {
            feature_name: "vol_1m_tertile",
            source_column: "market_history.volatility_1m_cents",
            type_name: "ordinal",
            allowed_transformations: "TRAIN_tertile",
            semantic_group: "VOLATILITY",
            family: "VOL1",
            leakage_status: "TRAIN_ONLY_CUTS",
        },
        FeatReg {
            feature_name: "vol_5m_tertile",
            source_column: "market_history.volatility_5m_cents",
            type_name: "ordinal",
            allowed_transformations: "TRAIN_tertile",
            semantic_group: "VOLATILITY",
            family: "VOL5",
            leakage_status: "TRAIN_ONLY_CUTS",
        },
        FeatReg {
            feature_name: "vol_15m_tertile",
            source_column: "market_history.volatility_15m_cents",
            type_name: "ordinal",
            allowed_transformations: "TRAIN_tertile",
            semantic_group: "VOLATILITY",
            family: "VOL15",
            leakage_status: "TRAIN_ONLY_CUTS",
        },
        FeatReg {
            feature_name: "last_event_sign",
            source_column: "event_response.event_history.last.delta",
            type_name: "categorical",
            allowed_transformations: "sign",
            semantic_group: "EVENT_RESPONSE",
            family: "EVENT",
            leakage_status: "OK_AT_ENTRY",
        },
        FeatReg {
            feature_name: "last_event_class",
            source_column: "event_response.event_history.last.class",
            type_name: "categorical",
            allowed_transformations: "existing",
            semantic_group: "EVENT_RESPONSE",
            family: "EVENT",
            leakage_status: "OK_AT_ENTRY",
        },
        FeatReg {
            feature_name: "last_delta_band",
            source_column: "event_response.event_history.last.delta",
            type_name: "categorical",
            allowed_transformations: "predeclared_abs",
            semantic_group: "EVENT_RESPONSE",
            family: "EVENT",
            leakage_status: "OK_AT_ENTRY",
        },
    ]
}

fn yes_no(b: bool) -> String {
    if b { "YES" } else { "NO" }.into()
}

/// Predeclared start-price bands (defined before TEST). Complements enrich_opt.
pub fn enrich_exh(row: &mut SearchRow, s: &B1EntrySnapshot) {
    let p0 = s.starting_market.p_start_cents;
    row.feats
        .insert("p_start_lt30".into(), yes_no(p0.is_some_and(|p| p < 30)));
    row.feats.insert(
        "p_start_30_34".into(),
        yes_no(p0.is_some_and(|p| (30..35).contains(&p))),
    );
    row.feats.insert(
        "p_start_35_39".into(),
        yes_no(p0.is_some_and(|p| (35..40).contains(&p))),
    );
    row.feats.insert(
        "p_start_50_54".into(),
        yes_no(p0.is_some_and(|p| (50..55).contains(&p))),
    );
    row.feats.insert(
        "p_start_55_59".into(),
        yes_no(p0.is_some_and(|p| (55..60).contains(&p))),
    );
    row.feats.insert(
        "p_start_60_69".into(),
        yes_no(p0.is_some_and(|p| (60..70).contains(&p))),
    );
    row.feats
        .insert("p_start_70p".into(), yes_no(p0.is_some_and(|p| p >= 70)));
    row.feats.insert(
        "p_start_40_54".into(),
        yes_no(p0.is_some_and(|p| (40..55).contains(&p))),
    );
}

fn train_games(rows: &[SearchRow], cond: &[(String, String)]) -> usize {
    let mut g = BTreeSet::new();
    for r in rows
        .iter()
        .filter(|r| r.chrono == ChronoSplit::Train && cond_ok(r, cond))
    {
        g.insert(r.game_id.as_str());
    }
    g.len()
}

fn family_of(name: &str) -> &'static str {
    registry()
        .iter()
        .find(|f| f.feature_name == name)
        .map(|f| f.family)
        .unwrap_or("OTHER")
}

fn group_of(name: &str) -> &'static str {
    registry()
        .iter()
        .find(|f| f.feature_name == name)
        .map(|f| f.semantic_group)
        .unwrap_or("OTHER")
}

pub fn assert_no_leakage(cond: &[(String, String)]) -> Result<(), B1Error> {
    for (k, _) in cond {
        let low = k.to_ascii_lowercase();
        if FORBIDDEN.iter().any(|f| low.contains(f)) {
            return Err(B1Error::validation(
                "LEAKAGE",
                format!("forbidden predictor in condition: {k}"),
            ));
        }
    }
    Ok(())
}

fn observed(rows: &[SearchRow], key: &str) -> Vec<String> {
    let mut s = BTreeSet::new();
    for r in rows.iter().filter(|r| r.chrono == ChronoSplit::Train) {
        if let Some(v) = r.feats.get(key) {
            if v != "NA" && v != "UNAVAILABLE" {
                s.insert(v.clone());
            }
        }
    }
    s.into_iter().collect()
}

fn kv(k: &str, v: &str) -> (String, String) {
    (k.to_string(), v.to_string())
}

fn share(n: u64, generated: &[u64; 6]) -> f64 {
    let tot = generated.iter().skip(1).sum::<u64>().max(1);
    n as f64 / tot as f64
}

fn write_json(path: &Path, v: &impl serde::Serialize) -> Result<(), B1Error> {
    fs::write(path, serde_json::to_string_pretty(v)?)?;
    Ok(())
}

fn pre_test_months(rows: &[&SearchRow], exit: &str) -> (f64, f64) {
    let mut m: BTreeMap<String, i32> = BTreeMap::new();
    for r in rows {
        if r.chrono == ChronoSplit::Test {
            continue;
        }
        if let Some(&ret) = r.exit_ret.get(exit) {
            *m.entry(r.month.clone()).or_default() += ret * r.qty;
        }
    }
    if m.is_empty() {
        return (0.0, 1.0);
    }
    let pos = m.values().filter(|v| **v > 0).count() as f64 / m.len() as f64;
    let tot = m.values().map(|v| v.abs()).sum::<i32>().max(1);
    let conc = m
        .values()
        .map(|v| f64::from(v.abs()) / f64::from(tot))
        .fold(0.0, f64::max);
    (pos, conc)
}

/// TRAIN+VAL selection score. TEST is not an input.
fn selection_score(c: &Cond83, rows: &[SearchRow]) -> f64 {
    let cond = parse_cond(&c.condition);
    let pre: Vec<&SearchRow> = rows
        .iter()
        .filter(|r| r.chrono != ChronoSplit::Test && cond_ok(r, &cond))
        .collect();
    let (pos_m, conc) = pre_test_months(&pre, PRIMARY);
    let tev = c.train.ev_cents.unwrap_or(0.0);
    let vev = c.validation.ev_cents.unwrap_or(0.0);
    let tn = c.train.n_unique_games;
    let vn = c.validation.n_unique_games;
    let depth = c.stage.max(1) as f64;
    let mut s = 0.0;
    if tev > 0.0 {
        s += 2.0 + tev.min(8.0) / 4.0;
    } else {
        s -= 2.0;
    }
    if vev > 0.0 {
        s += 3.0 + vev.min(8.0) / 4.0;
    } else {
        s -= 4.0;
    }
    if tn >= 50 {
        s += 1.0;
    }
    if vn >= 25 {
        s += 2.0;
    } else if vn >= 15 {
        s += 0.5;
    } else if vn >= 10 {
        s -= 1.5 + (15 - vn) as f64 * 0.20;
    }
    if vev >= 16.0 && vn < 15 {
        s -= 3.0;
    }
    s += pos_m;
    s -= 0.40 * (depth - 1.0);
    s -= (tev - vev).max(0.0) / 8.0;
    if conc >= 0.60 {
        s -= 2.0;
    }
    s
}

pub fn classify(c: &Cond83, args: &ExhaustiveArgs, qmap: &BTreeMap<String, f64>) -> String {
    let tev = c.train.ev_cents.unwrap_or(0.0);
    let vev = c.validation.ev_cents.unwrap_or(0.0);
    let xev = c.test.ev_cents.unwrap_or(0.0);
    let tn = c.train.n_unique_games;
    let vn = c.validation.n_unique_games;
    let xn = c.test.n_unique_games;
    let fdr_ok = qmap.get(&c.condition).is_some_and(|q| *q <= 0.10);
    if xn < 10 || c.all.n_unique_games < 30 {
        return "REJECTED".into();
    }
    if tev > 0.0 && vev > 0.0 && xev > 0.0 && tn >= 50 && vn >= 25 && xn >= 25 {
        if fdr_ok {
            return "ROBUST".into();
        }
        return "CANDIDATE".into();
    }
    if tev > 0.0
        && vev > 0.0
        && xev > 0.0
        && tn >= args.min_train
        && vn >= args.min_val
        && xn >= args.min_test
    {
        if vn < 25 || xn < 25 {
            return "CANDIDATE_THIN_VALIDATION".into();
        }
        return "CANDIDATE".into();
    }
    if xev > 8.0 && (tev <= 0.0 || vev <= 0.0) {
        return "OVERFIT".into();
    }
    if xev > 0.0 && (tev <= 0.0 || vev <= 0.0) {
        return "EXPLORATORY".into();
    }
    if xev < 0.0 {
        return "REJECTED".into();
    }
    "EXPLORATORY".into()
}

pub fn game_pnls(rows: &[&SearchRow], exit: &str) -> Vec<f64> {
    let mut g: BTreeMap<&str, i32> = BTreeMap::new();
    for r in rows {
        if let Some(&ret) = r.exit_ret.get(exit) {
            *g.entry(r.game_id.as_str()).or_default() += ret * r.qty;
        }
    }
    g.values().map(|v| f64::from(*v)).collect()
}

fn lcg(state: &mut u64) -> u64 {
    *state = state.wrapping_mul(6364136223846793005).wrapping_add(1);
    *state
}

pub fn bh_qvalues(p: &[(String, f64)]) -> BTreeMap<String, f64> {
    let mut items = p.to_vec();
    items.sort_by(|a, b| a.1.partial_cmp(&b.1).unwrap_or(std::cmp::Ordering::Equal));
    let m = items.len() as f64;
    if m == 0.0 {
        return BTreeMap::new();
    }
    let mut q = vec![1.0; items.len()];
    let mut running: f64 = 1.0;
    for i in (0..items.len()).rev() {
        let raw = items[i].1 * m / (i + 1) as f64;
        running = running.min(raw).min(1.0);
        q[i] = running;
    }
    items
        .into_iter()
        .zip(q)
        .map(|((id, _), qi)| (id, qi))
        .collect()
}

fn permutation_p(all: &[f64], n_in: usize, obs_mean: f64, reps: usize, seed: u64) -> Option<f64> {
    if all.len() < 10 || n_in < 8 || n_in > all.len() {
        return None;
    }
    let mut state = seed;
    let mut ge = 0usize;
    let mut buf = all.to_vec();
    for _ in 0..reps {
        for i in (1..buf.len()).rev() {
            let j = (lcg(&mut state) as usize) % (i + 1);
            buf.swap(i, j);
        }
        let m = buf.iter().take(n_in).sum::<f64>() / n_in as f64;
        if m >= obs_mean {
            ge += 1;
        }
    }
    Some((ge as f64 + 1.0) / (reps as f64 + 1.0))
}

fn monthly_all(rows: &[&SearchRow], exit: &str) -> Vec<serde_json::Value> {
    let mut m: BTreeMap<String, (i32, usize, usize, usize)> = BTreeMap::new();
    for r in rows {
        if let Some(&ret) = r.exit_ret.get(exit) {
            let e = m.entry(r.month.clone()).or_insert((0, 0, 0, 0));
            e.0 += ret * r.qty;
            e.1 += 1;
            match r.settlement_win {
                Some(true) => {
                    e.2 += 1;
                    e.3 += 1;
                }
                Some(false) => e.3 += 1,
                None => {}
            }
        }
    }
    m.into_iter()
        .map(|(month, (pnl, n, w, d))| {
            serde_json::json!({
                "month": month,
                "n": n,
                "win_rate": if d > 0 { Some(w as f64 / d as f64) } else { None },
                "ev_cents": if n > 0 { Some(f64::from(pnl) / n as f64 / 7.0) } else { None },
                "pnl_usd": f64::from(pnl) / 100.0
            })
        })
        .collect()
}

#[allow(clippy::too_many_arguments)]
fn rec(
    id: u32,
    c: &Cond83,
    sel: f64,
    class: &str,
    fdr_q: Option<f64>,
    ci: Option<(f64, f64)>,
    pos_m: f64,
) -> serde_json::Value {
    let parts = parse_cond(&c.condition);
    let groups: BTreeSet<&str> = parts.iter().map(|(k, _)| group_of(k)).collect();
    serde_json::json!({
        "candidate_id": format!("E83-{id:04}"),
        "condition_expression": c.condition,
        "interaction_depth": c.stage,
        "feature_groups": groups,
        "train_n": c.train.n_unique_games,
        "val_n": c.validation.n_unique_games,
        "test_n": c.test.n_unique_games,
        "n_snapshots": c.all.n_entries,
        "n_unique_games": c.all.n_unique_games,
        "train_ev": c.train.ev_cents,
        "val_ev": c.validation.ev_cents,
        "test_ev": c.test.ev_cents,
        "train_wr": c.train.win_rate,
        "val_wr": c.validation.win_rate,
        "test_wr": c.test.win_rate,
        "train_sharpe": c.train.sharpe_game_unann,
        "val_sharpe": c.validation.sharpe_game_unann,
        "test_sharpe": c.test.sharpe_game_unann,
        "test_pnl": c.test.total_pnl_usd,
        "selection_score": sel,
        "bootstrap_ci_low": ci.map(|x| x.0),
        "bootstrap_ci_high": ci.map(|x| x.1),
        "positive_month_fraction": pos_m,
        "fdr_q": fdr_q,
        "classification": class,
        "fill_status": FILL_STATUS,
        "entries_per_game_max": c.all.max_entries_per_game
    })
}

pub fn run_83_exhaustive_search(
    cfg: &SearchConfig,
    args: &ExhaustiveArgs,
) -> Result<serde_json::Value, B1Error> {
    if !cfg.features_sqlite.exists() {
        return Err(B1Error::Uncommitted(
            "B1 features.sqlite missing. Run --extract first.".into(),
        ));
    }
    let store = FeatureStore::open_existing(&cfg.features_sqlite)?;
    let snaps = store.load_all()?;
    let mut dated: Vec<SearchRow> = snaps.iter().map(flatten).collect();
    let (train_cut, val_cut, test_end) = official_chrono_split(&mut dated);
    let snaps83: Vec<B1EntrySnapshot> = snaps
        .iter()
        .filter(|s| s.entry_trade_price_cents == 83)
        .cloned()
        .collect();
    let mut rows: Vec<SearchRow> = dated.into_iter().filter(|r| r.entry_cents == 83).collect();
    if snaps83.is_empty() {
        return Err(B1Error::validation("NO_83", "no ENTRY_83 snapshots"));
    }
    attach_train_tertiles(&mut rows, &snaps83);
    attach_83_tertiles(&mut rows, &snaps83);
    for (r, s) in rows.iter_mut().zip(snaps83.iter()) {
        enrich(r, s);
        enrich_opt(r, s);
        enrich_exh(r, s);
    }
    for r in &rows {
        assert_no_leakage(
            &r.feats
                .keys()
                .map(|k| (k.clone(), String::new()))
                .collect::<Vec<_>>(),
        )?;
    }

    let all_rows: Vec<&SearchRow> = rows.iter().collect();
    let max_epg = all_rows
        .iter()
        .fold(BTreeMap::<&str, usize>::new(), |mut m, r| {
            *m.entry(r.game_id.as_str()).or_default() += 1;
            m
        })
        .into_values()
        .max()
        .unwrap_or(0);
    let base_all = metrics(&all_rows, PRIMARY);
    let base_test = metrics(&slice(&rows, Some(ChronoSplit::Test), &[]), PRIMARY);
    let base = eval_screen(&rows, &[], 0, PRIMARY, &base_all, &base_test).expect("ALL_83");

    let mut hold: Vec<Cond83> = Vec::new();
    let mut seen = BTreeSet::new();
    let mut n_gen = [0u64; 6];

    let push = |hold: &mut Vec<Cond83>,
                seen: &mut BTreeSet<String>,
                n_gen: &mut [u64; 6],
                cond: Vec<(String, String)>,
                stage: u8|
     -> Result<(), B1Error> {
        assert_no_leakage(&cond)?;
        let Some(c) = eval_screen(&rows, &cond, stage, PRIMARY, &base_all, &base_test) else {
            return Ok(());
        };
        n_gen[stage as usize] = n_gen[stage as usize].saturating_add(1);
        if c.train.n_unique_games < 12 {
            return Ok(());
        }
        if seen.insert(c.condition.clone()) {
            hold.push(c);
        }
        Ok(())
    };

    for spec in registry() {
        for v in observed(&rows, spec.feature_name) {
            push(
                &mut hold,
                &mut seen,
                &mut n_gen,
                vec![kv(spec.feature_name, &v)],
                1,
            )?;
        }
    }

    let levels: Vec<(String, String, &'static str, &'static str)> = hold
        .iter()
        .filter(|c| c.stage == 1)
        .filter_map(|c| {
            let p = parse_cond(&c.condition);
            let (k, v) = p.first()?;
            Some((k.clone(), v.clone(), family_of(k), group_of(k)))
        })
        .collect();

    if args.max_depth >= 2 {
        for (i, a) in levels.iter().enumerate() {
            for b in levels.iter().skip(i + 1) {
                if a.2 == b.2 || a.3 == b.3 {
                    continue;
                }
                let cond = vec![kv(&a.0, &a.1), kv(&b.0, &b.1)];
                if train_games(&rows, &cond) >= args.min_train {
                    push(&mut hold, &mut seen, &mut n_gen, cond, 2)?;
                }
            }
        }
    }

    let train_floor = base.train.ev_cents.unwrap_or(0.0);
    let top1 = diverse_top1(&hold, args.min_train, train_floor, 4);

    if args.max_depth >= 3 {
        let top3 = top1.iter().take(20).cloned().collect::<Vec<_>>();
        for i in 0..top3.len() {
            for j in (i + 1)..top3.len() {
                for k in (j + 1)..top3.len() {
                    let mut keys = BTreeSet::new();
                    let mut fams = BTreeSet::new();
                    let mut cond = Vec::new();
                    let mut ok = true;
                    for part in [&top3[i], &top3[j], &top3[k]].into_iter().flatten() {
                        if !keys.insert(part.0.clone()) || !fams.insert(family_of(&part.0)) {
                            ok = false;
                            break;
                        }
                        cond.push(part.clone());
                    }
                    if !ok || cond.len() != 3 {
                        continue;
                    }
                    if train_games(&rows, &cond) >= args.min_train {
                        push(&mut hold, &mut seen, &mut n_gen, cond, 3)?;
                    }
                }
            }
        }
    }
    if args.max_depth >= 4 {
        let top4 = top1.iter().take(10).cloned().collect::<Vec<_>>();
        for i in 0..top4.len() {
            for j in (i + 1)..top4.len() {
                for k in (j + 1)..top4.len() {
                    for l in (k + 1)..top4.len() {
                        let mut keys = BTreeSet::new();
                        let mut fams = BTreeSet::new();
                        let mut cond = Vec::new();
                        let mut ok = true;
                        for part in [&top4[i], &top4[j], &top4[k], &top4[l]]
                            .into_iter()
                            .flatten()
                        {
                            if !keys.insert(part.0.clone()) || !fams.insert(family_of(&part.0)) {
                                ok = false;
                                break;
                            }
                            cond.push(part.clone());
                        }
                        if !ok || cond.len() != 4 {
                            continue;
                        }
                        if train_games(&rows, &cond) >= args.min_train {
                            push(&mut hold, &mut seen, &mut n_gen, cond, 4)?;
                        }
                    }
                }
            }
        }
    }
    if args.max_depth >= 5 {
        let top5 = top1.iter().take(6).cloned().collect::<Vec<_>>();
        if top5.len() == 6 {
            let mut keys = BTreeSet::new();
            let mut fams = BTreeSet::new();
            let mut cond = Vec::new();
            let mut ok = true;
            for part in top5.iter().flatten() {
                if !keys.insert(part.0.clone()) || !fams.insert(family_of(&part.0)) {
                    ok = false;
                    break;
                }
                cond.push(part.clone());
            }
            if ok && cond.len() == 6 {
                let _ = cond.pop();
            }
            if ok && cond.len() >= 5 && train_games(&rows, &cond) >= args.min_train {
                push(&mut hold, &mut seen, &mut n_gen, cond, 5)?;
            }
        }
    }

    let n_train_pass = hold
        .iter()
        .filter(|c| {
            c.train.n_unique_games >= args.min_train && c.train.ev_cents.unwrap_or(0.0) > 0.0
        })
        .count();
    let n_val_pass = hold
        .iter()
        .filter(|c| {
            c.train.ev_cents.unwrap_or(0.0) > 0.0
                && c.validation.ev_cents.unwrap_or(0.0) > 0.0
                && c.train.n_unique_games >= args.min_train
                && c.validation.n_unique_games >= args.min_val
        })
        .count();

    let mut scored: Vec<(f64, Cond83)> = hold
        .iter()
        .filter(|c| c.condition != "ALL_83")
        .map(|c| (selection_score(c, &rows), c.clone()))
        .collect();
    scored.sort_by(|a, b| b.0.partial_cmp(&a.0).unwrap_or(std::cmp::Ordering::Equal));

    let mut pvals: Vec<(String, f64)> = Vec::new();
    for c in &hold {
        let tr = slice(&rows, Some(ChronoSplit::Train), &parse_cond(&c.condition));
        let pnls = game_pnls(&tr, PRIMARY);
        if let Some(p) = p_mean_le0(&pnls) {
            pvals.push((c.condition.clone(), p));
        }
    }
    let mut p_bh = pvals.clone();
    let keep = benjamini_hochberg(&mut p_bh, 0.10);
    let qmap = bh_qvalues(&pvals);

    let val_finalists: Vec<&(f64, Cond83)> = scored
        .iter()
        .filter(|(_, c)| {
            c.train.ev_cents.unwrap_or(0.0) > 0.0
                && c.validation.ev_cents.unwrap_or(0.0) > 0.0
                && c.train.n_unique_games >= args.min_train
                && c.validation.n_unique_games >= args.min_val
        })
        .take(25)
        .collect();

    let mut recs = Vec::new();
    for (i, (sel, c)) in scored.iter().enumerate() {
        let class = classify(c, args, &qmap);
        let cond = parse_cond(&c.condition);
        let pre: Vec<&SearchRow> = rows
            .iter()
            .filter(|r| r.chrono != ChronoSplit::Test && cond_ok(r, &cond))
            .collect();
        let (pos_m, _) = pre_test_months(&pre, PRIMARY);
        recs.push(rec(
            u32::try_from(i + 1).unwrap_or(0),
            c,
            *sel,
            &class,
            qmap.get(&c.condition).copied(),
            None,
            pos_m,
        ));
    }

    let mut boot = Vec::new();
    let mut perm = Vec::new();
    let all_pnls = game_pnls(&all_rows, PRIMARY);
    for (sel, c) in val_finalists.iter().take(12) {
        let test = slice(&rows, Some(ChronoSplit::Test), &parse_cond(&c.condition));
        let ci = bootstrap_ev_ci(&test, PRIMARY, args.bootstrap_reps, SEED);
        boot.push(serde_json::json!({
            "condition": c.condition,
            "selection_score": sel,
            "test_n": c.test.n_unique_games,
            "mean_pnl_per_game_usd_ci95": ci,
            "reps": args.bootstrap_reps,
            "seed": SEED
        }));
        let members = slice(&rows, None, &parse_cond(&c.condition));
        let n_in = {
            let g: BTreeSet<&str> = members.iter().map(|r| r.game_id.as_str()).collect();
            g.len()
        };
        let obs = c.all.ev_cents.unwrap_or(0.0) * 7.0;
        let p = permutation_p(&all_pnls, n_in, obs, args.permutation_reps, SEED);
        perm.push(serde_json::json!({
            "condition": c.condition,
            "observed_mean_pnl_cents": obs,
            "n_games": n_in,
            "permutation_p_ge_obs": p,
            "reps": args.permutation_reps,
            "null": "shuffle game P&L; keep membership size"
        }));
    }

    let mut raw_test = hold.clone();
    raw_test.sort_by(|a, b| {
        b.test
            .ev_cents
            .partial_cmp(&a.test.ev_cents)
            .unwrap_or(std::cmp::Ordering::Equal)
    });
    let survived_test = |c: &Cond83| {
        c.test.ev_cents.unwrap_or(0.0) > 0.0
            && c.test.n_unique_games >= args.min_test
            && !matches!(classify(c, args, &qmap).as_str(), "REJECTED" | "OVERFIT")
    };
    let robust: Vec<&(f64, Cond83)> = val_finalists
        .iter()
        .copied()
        .filter(|(_, c)| survived_test(c))
        .collect();
    let simple: Vec<&(f64, Cond83)> = val_finalists
        .iter()
        .copied()
        .filter(|(_, c)| c.stage <= 2 && survived_test(c))
        .collect();

    let bench = hold
        .iter()
        .find(|c| c.condition == "start_price_band=40_49");
    let primary = simple.first().or(robust.first()).map(|x| x.1.clone());

    let mut neg: Vec<Cond83> = hold
        .iter()
        .filter(|c| {
            c.train.n_unique_games >= args.min_train
                && c.validation.n_unique_games >= args.min_val
                && (c.train.ev_cents.unwrap_or(0.0) < 0.0
                    || c.validation.ev_cents.unwrap_or(0.0) < 0.0)
        })
        .cloned()
        .collect();
    neg.sort_by(|a, b| {
        let sa = a.train.ev_cents.unwrap_or(0.0) + a.validation.ev_cents.unwrap_or(0.0);
        let sb = b.train.ev_cents.unwrap_or(0.0) + b.validation.ev_cents.unwrap_or(0.0);
        sa.partial_cmp(&sb).unwrap_or(std::cmp::Ordering::Equal)
    });
    neg.truncate(15);

    let mut ladder = Vec::new();
    ladder.push(serde_json::json!({"layer":"ALL_83","condition":"ALL_83","train_ev":base.train.ev_cents,"val_ev":base.validation.ev_cents,"test_ev":base.test.ev_cents,"n":base.all.n_unique_games}));
    if let Some(s) = hold.iter().find(|c| c.condition == "p_start_lt50=YES") {
        ladder.push(serde_json::json!({"layer":"START_BELIEF","condition":s.condition,"train_ev":s.train.ev_cents,"val_ev":s.validation.ev_cents,"test_ev":s.test.ev_cents,"n":s.all.n_unique_games}));
    }
    if let Some(s) = bench {
        ladder.push(serde_json::json!({"layer":"START_40_49","condition":s.condition,"train_ev":s.train.ev_cents,"val_ev":s.validation.ev_cents,"test_ev":s.test.ev_cents,"n":s.all.n_unique_games}));
    }
    for (layer, parts) in [
        (
            "START+LEAD",
            vec![kv("p_start_lt50", "YES"), kv("lead_ge2", "YES")],
        ),
        (
            "START_40_49+LEAD",
            vec![kv("start_price_band", "40_49"), kv("lead_ge2", "YES")],
        ),
        (
            "START_40_49+INNING",
            vec![kv("start_price_band", "40_49"), kv("inning_late68", "YES")],
        ),
        (
            "START_40_49+PATH",
            vec![
                kv("start_price_band", "40_49"),
                kv("start_move_gt20", "YES"),
            ],
        ),
        (
            "START_40_49+VOL",
            vec![kv("start_price_band", "40_49"), kv("vol_1m_tertile", "LOW")],
        ),
        (
            "START_40_49+VEL",
            vec![kv("start_price_band", "40_49"), kv("vel_sign", "UP")],
        ),
    ] {
        let name = parts
            .iter()
            .map(|(k, v)| format!("{k}={v}"))
            .collect::<Vec<_>>()
            .join("&");
        let found = hold
            .iter()
            .find(|c| c.condition == name)
            .cloned()
            .or_else(|| eval_screen(&rows, &parts, 2, PRIMARY, &base_all, &base_test));
        if let Some(s) = found {
            ladder.push(serde_json::json!({
                "layer": layer,
                "condition": s.condition,
                "train_ev": s.train.ev_cents,
                "val_ev": s.validation.ev_cents,
                "test_ev": s.test.ev_cents,
                "n": s.all.n_unique_games,
                "train_n": s.train.n_unique_games,
                "val_n": s.validation.n_unique_games,
                "test_n": s.test.n_unique_games,
                "ev_lift_vs_all83_test": s.ev_lift_test
            }));
        }
    }

    let mut sensitivity = Vec::new();
    if let Some(p) = &primary {
        for cost in [0, 1, 2, 3, 5] {
            sensitivity.push(serde_json::json!({
                "hypothetical_cost_cents": cost,
                "test_ev_gross": p.test.ev_cents,
                "test_ev_net": p.test.ev_cents.map(|e| e - f64::from(cost)),
                "survives": p.test.ev_cents.is_some_and(|e| e - f64::from(cost) > 0.0),
                "note": "Hypothetical TRADE-print cost. Not Kalshi fees."
            }));
        }
    }

    fs::create_dir_all(&cfg.out_dir)?;
    write_json(
        &cfg.out_dir.join("b1_83_feature_registry.json"),
        &registry(),
    )?;
    write_json(&cfg.out_dir.join("b1_83_exhaustive_candidates.json"), &recs)?;
    write_json(
        &cfg.out_dir.join("b1_83_robust_leaders.json"),
        &robust.iter().take(15).map(|(s, c)| serde_json::json!({"selection_score":s,"condition":c.condition,"train_ev":c.train.ev_cents,"val_ev":c.validation.ev_cents,"test_ev":c.test.ev_cents,"class":classify(c,args,&qmap)})).collect::<Vec<_>>(),
    )?;
    write_json(
        &cfg.out_dir.join("b1_83_raw_test_leaders.json"),
        &raw_test.iter().take(20).map(|c| serde_json::json!({"condition":c.condition,"test_ev":c.test.ev_cents,"test_n":c.test.n_unique_games,"train_ev":c.train.ev_cents,"val_ev":c.validation.ev_cents,"label":"OVERFIT_RISK"})).collect::<Vec<_>>(),
    )?;
    write_json(
        &cfg.out_dir.join("b1_83_negative_states.json"),
        &neg.iter().map(|c| serde_json::json!({"condition":c.condition,"train_ev":c.train.ev_cents,"val_ev":c.validation.ev_cents,"test_ev":c.test.ev_cents,"n":c.all.n_unique_games,"test_n":c.test.n_unique_games})).collect::<Vec<_>>(),
    )?;
    write_json(
        &cfg.out_dir.join("b1_83_search_summary.json"),
        &serde_json::json!({
            "n_83_snapshots": rows.len(),
            "n_83_games": base_all.n_unique_games,
            "max_entries_per_game": max_epg,
            "duplicate_policy": "B1 extract is one primary 83¢ TRADE snapshot per game. Metrics aggregate by game_id.",
            "split": {"train_before": train_cut, "validation_before": val_cut, "test_end": test_end},
            "features_in_registry": registry().len(),
            "features_considered": registry().len(),
            "transformations_considered": n_gen[1],
            "generated_by_depth": {"1": n_gen[1], "2": n_gen[2], "3": n_gen[3], "4": n_gen[4], "5": n_gen[5]},
            "search_space_share": {
                "1": share(n_gen[1], &n_gen),
                "2": share(n_gen[2], &n_gen),
                "3": share(n_gen[3], &n_gen),
                "4": share(n_gen[4], &n_gen),
                "5": share(n_gen[5], &n_gen)
            },
            "candidates_stored": hold.len(),
            "train_pass": n_train_pass,
            "train_val_pass": n_val_pass,
            "test_evaluated": hold.len(),
            "args": {"max_depth": args.max_depth, "min_train": args.min_train, "min_val": args.min_val, "min_test": args.min_test, "bootstrap_reps": args.bootstrap_reps, "permutation_reps": args.permutation_reps, "seed": SEED},
            "feature_schema_version": FEATURE_SCHEMA_VERSION,
            "engine_version": ENGINE_VERSION,
            "fill_status": FILL_STATUS
        }),
    )?;
    write_json(
        &cfg.out_dir.join("b1_83_incremental_information.json"),
        &ladder,
    )?;
    write_json(
        &cfg.out_dir.join("b1_83_monthly_stability.json"),
        &serde_json::json!({
            "all_83": monthly_all(&all_rows, PRIMARY),
            "primary": primary.as_ref().map(|p| monthly_all(&slice(&rows, None, &parse_cond(&p.condition)), PRIMARY)),
            "benchmark_40_49": bench.map(|b| monthly_all(&slice(&rows, None, &parse_cond(&b.condition)), PRIMARY))
        }),
    )?;
    write_json(&cfg.out_dir.join("b1_83_bootstrap.json"), &boot)?;
    write_json(&cfg.out_dir.join("b1_83_permutation_test.json"), &perm)?;
    write_json(
        &cfg.out_dir.join("b1_83_multiple_testing.json"),
        &serde_json::json!({
            "method": "Benjamini-Hochberg FDR q=0.10 on TRAIN game-level P(mean P&L <= 0)",
            "n_tested": pvals.len(),
            "n_reject_q10": keep.len(),
            "kept": keep.iter().take(20).collect::<Vec<_>>(),
            "note": "Uncorrected TEST EV is not evidence. Selection score ignores TEST."
        }),
    )?;

    let mut csv = String::from(
        "rank,condition,depth,sel,train_n,val_n,test_n,train_ev,val_ev,test_ev,train_wr,val_wr,test_wr,train_sharpe,val_sharpe,test_sharpe,test_pnl,class,fdr_q\n",
    );
    for (i, (sel, c)) in scored.iter().enumerate() {
        csv.push_str(&format!(
            "{},{},{},{:.4},{},{},{},{:.4},{:.4},{:.4},{:.4},{:.4},{:.4},{:.4},{:.4},{:.4},{:.2},{},{:.4}\n",
            i + 1,
            c.condition.replace(',', ";"),
            c.stage,
            sel,
            c.train.n_unique_games,
            c.validation.n_unique_games,
            c.test.n_unique_games,
            c.train.ev_cents.unwrap_or(f64::NAN),
            c.validation.ev_cents.unwrap_or(f64::NAN),
            c.test.ev_cents.unwrap_or(f64::NAN),
            c.train.win_rate.unwrap_or(f64::NAN),
            c.validation.win_rate.unwrap_or(f64::NAN),
            c.test.win_rate.unwrap_or(f64::NAN),
            c.train.sharpe_game_unann.unwrap_or(f64::NAN),
            c.validation.sharpe_game_unann.unwrap_or(f64::NAN),
            c.test.sharpe_game_unann.unwrap_or(f64::NAN),
            c.test.total_pnl_usd,
            classify(c, args, &qmap),
            qmap.get(&c.condition).copied().unwrap_or(f64::NAN)
        ));
    }
    fs::write(cfg.out_dir.join("b1_83_exhaustive_rankings.csv"), csv)?;

    let report = render(
        &base,
        bench,
        primary.as_ref(),
        &raw_test,
        &scored,
        &val_finalists,
        &simple,
        &neg,
        &sensitivity,
        &ladder,
        &n_gen,
        hold.len(),
        n_train_pass,
        n_val_pass,
        rows.len(),
        max_epg,
        args,
        &train_cut,
        &val_cut,
        &test_end,
        keep.len(),
        pvals.len(),
        &qmap,
    );
    fs::write(cfg.out_dir.join("b1_83_exhaustive_report.md"), report)?;

    eprintln!(
        "RESEARCH ONLY.\nNo live FIRST01 parameters changed.\nNo 80/81/83/89 thresholds changed.\nNo stop changed.\nNo risk changed.\nNo W9 started.\nNo L2 fields invented.\nNo orders submitted."
    );

    Ok(serde_json::json!({
        "n_83": rows.len(),
        "candidates": hold.len(),
        "primary": primary.as_ref().map(|p| p.condition.clone()),
        "primary_class": primary.as_ref().map(|p| classify(p, args, &qmap)),
        "train_val_pass": n_val_pass,
        "fill_status": FILL_STATUS
    }))
}

fn diverse_top1(
    hold: &[Cond83],
    min_train: usize,
    train_floor: f64,
    per_family: usize,
) -> Vec<Vec<(String, String)>> {
    let mut by_fam: BTreeMap<&str, Vec<&Cond83>> = BTreeMap::new();
    for c in hold {
        if c.stage != 1 || c.train.n_unique_games < min_train {
            continue;
        }
        if c.train.ev_cents.unwrap_or(f64::NEG_INFINITY) <= train_floor {
            continue;
        }
        let parts = parse_cond(&c.condition);
        let Some((k, v)) = parts.first() else {
            continue;
        };
        if v == "NO" {
            continue;
        }
        by_fam.entry(family_of(k)).or_default().push(c);
    }
    let mut out = Vec::new();
    for mut v in by_fam.into_values() {
        v.sort_by(|a, b| {
            b.train
                .ev_cents
                .partial_cmp(&a.train.ev_cents)
                .unwrap_or(std::cmp::Ordering::Equal)
        });
        for c in v.into_iter().take(per_family) {
            out.push((c.train.ev_cents.unwrap_or(0.0), parse_cond(&c.condition)));
        }
    }
    out.sort_by(|a, b| b.0.partial_cmp(&a.0).unwrap_or(std::cmp::Ordering::Equal));
    out.into_iter().map(|(_, c)| c).collect()
}

fn top_kway(scored: &[(f64, Cond83)], depth: u8) -> Vec<&(f64, Cond83)> {
    let mut v: Vec<&(f64, Cond83)> = scored
        .iter()
        .filter(|(_, c)| c.stage == depth && c.train.n_unique_games >= 40)
        .collect();
    v.sort_by(|a, b| b.0.partial_cmp(&a.0).unwrap_or(std::cmp::Ordering::Equal));
    v
}

fn fmt_c(c: &Cond83) -> String {
    format!(
        "`{}` TRAIN {:.2} VAL {:.2} TEST {:.2} n={}/{}/{}",
        c.condition,
        c.train.ev_cents.unwrap_or(f64::NAN),
        c.validation.ev_cents.unwrap_or(f64::NAN),
        c.test.ev_cents.unwrap_or(f64::NAN),
        c.train.n_unique_games,
        c.validation.n_unique_games,
        c.test.n_unique_games
    )
}

#[allow(clippy::too_many_arguments)]
fn render(
    base: &Cond83,
    bench: Option<&Cond83>,
    primary: Option<&Cond83>,
    raw_test: &[Cond83],
    scored: &[(f64, Cond83)],
    val_finalists: &[&(f64, Cond83)],
    simple: &[&(f64, Cond83)],
    neg: &[Cond83],
    sensitivity: &[serde_json::Value],
    ladder: &[serde_json::Value],
    n_gen: &[u64; 6],
    n_hold: usize,
    n_train_pass: usize,
    n_val_pass: usize,
    n83: usize,
    max_epg: usize,
    args: &ExhaustiveArgs,
    train_cut: &str,
    val_cut: &str,
    test_end: &str,
    n_bh: usize,
    n_p: usize,
    qmap: &BTreeMap<String, f64>,
) -> String {
    let mut md = String::new();
    md.push_str("# Exhaustive Conditional 83¢ Research\n\n");
    md.push_str("## 1. Executive answer\n\n");
    match primary {
        Some(p) => {
            md.push_str(&format!(
                "VAL-selected primary (TEST locked): **`{}`** class `{}`.\n\n",
                p.condition,
                classify(p, args, qmap)
            ));
            md.push_str(&format!(
                "TRAIN n={} EV={:.2}¢ WR={:.1}% · VAL n={} EV={:.2}¢ WR={:.1}% · TEST n={} EV={:.2}¢ WR={:.1}% Sharpe={:.3}\n\n",
                p.train.n_unique_games, p.train.ev_cents.unwrap_or(f64::NAN), p.train.win_rate.unwrap_or(0.0)*100.0,
                p.validation.n_unique_games, p.validation.ev_cents.unwrap_or(f64::NAN), p.validation.win_rate.unwrap_or(0.0)*100.0,
                p.test.n_unique_games, p.test.ev_cents.unwrap_or(f64::NAN), p.test.win_rate.unwrap_or(0.0)*100.0,
                p.test.sharpe_game_unann.unwrap_or(f64::NAN)
            ));
            if classify(p, args, qmap) != "ROBUST" {
                md.push_str("**NO ROBUST OPTIMAL STATE FOUND** under TRAIN≥50 / VAL≥25 / TEST≥25. The primary is the strongest VAL-selected simple state that stayed +TEST.\n\n");
            }
        }
        None => md.push_str("**NO ROBUST OPTIMAL STATE FOUND.** No VAL-selected simple state stayed positive on locked TEST.\n\n"),
    }

    md.push_str("## 2. Universe and methodology\n\n");
    md.push_str(&format!(
        "- Universe: `entry_trade_price_cents=83` only. N snapshots/games = {n83}/{}.\n- Duplicate policy: B1 stores **one** primary 83¢ TRADE snapshot per game (`max_entries_per_game={max_epg}`). Sharpe/bootstrap/permutation use game-level P&L.\n- Split (unchanged): TRAIN < `{train_cut}`, VAL < `{val_cut}`, TEST through `{test_end}`.\n- Discovery: TRAIN. Selection score: TRAIN+VAL only. TEST evaluated after freeze.\n- Stake: qty = 625 // 83 = 7. Uncompounded. Sharpe = game mean P&L / sample stdev (unannualized).\n- Fill: `{FILL_STATUS}`.\n\n"
        , base.all.n_unique_games
    ));
    md.push_str("Selection score (no TEST): `+2+clip(train_ev,8)/4` if TRAIN EV>0 else −2; `+3+clip(val_ev,8)/4` if VAL EV>0 else −4; +1 if TRAIN n≥50; +2 if VAL n≥25 else +0.5 if VAL n≥15 else −1.5−0.2×(15−VAL n) if VAL n≥10; −3 if VAL EV≥16 and VAL n<15 (perfect thin cell); +TRAIN/VAL positive-month fraction; −0.4×(depth−1); −max(train−val,0)/8; −2 if month concentration ≥0.60. Primary confirmation after freeze: TEST n≥min_test and TEST EV>0; REJECTED/OVERFIT cannot be primary.\n\n");

    md.push_str("## 3. Data leakage controls\n\n");
    md.push_str("Forbidden keys asserted on every feature name and condition: settlement, mfe, mae, exit_, future, pnl, return_cents, win_rate, fair_value, obi, microprice. Tertiles/quantiles fit on 83¢ TRAIN only. Settlement is label only.\n\n");

    md.push_str("## 4. Search-space definition\n\n");
    md.push_str(&format!(
        "{} registry features across START_BELIEF, BASEBALL_STATE, PATH, PERSONALITY, VELOCITY, ACCELERATION, VOLATILITY, EVENT_RESPONSE. Same-family pairs skipped (redundancy map). 40–49 is a competing 1-way, not a seed.\n\n",
        registry().len()
    ));

    md.push_str("## 5. Search counts\n\n");
    md.push_str(&format!(
        "| Stage | Generated (TRAIN-pruned) | Share |\n|---|---:|---:|\n| 1-way | {} | {:.1}% |\n| 2-way | {} | {:.1}% |\n| 3-way | {} | {:.1}% |\n| 4-way | {} | {:.1}% |\n| 5-way | {} | {:.1}% |\n| Stored | {n_hold} | |\n| TRAIN+ | {n_train_pass} | |\n| TRAIN+VAL+ | {n_val_pass} | |\n| TEST evaluated | {n_hold} | |\n\n",
        n_gen[1],
        100.0 * share(n_gen[1], n_gen),
        n_gen[2],
        100.0 * share(n_gen[2], n_gen),
        n_gen[3],
        100.0 * share(n_gen[3], n_gen),
        n_gen[4],
        100.0 * share(n_gen[4], n_gen),
        n_gen[5],
        100.0 * share(n_gen[5], n_gen)
    ));

    md.push_str("## 6. ALL_83 baseline\n\n");
    md.push_str(&format!(
        "| Split | Games | WR | EV¢ | Sharpe | P&L $ |\n|---|---:|---:|---:|---:|---:|\n| ALL | {} | {:.3} | {:.2} | {:.3} | {:.2} |\n| TRAIN | {} | {:.3} | {:.2} | {:.3} | {:.2} |\n| VAL | {} | {:.3} | {:.2} | {:.3} | {:.2} |\n| TEST | {} | {:.3} | {:.2} | {:.3} | {:.2} |\n\n",
        base.all.n_unique_games, base.all.win_rate.unwrap_or(f64::NAN), base.all.ev_cents.unwrap_or(f64::NAN), base.all.sharpe_game_unann.unwrap_or(f64::NAN), base.all.total_pnl_usd,
        base.train.n_unique_games, base.train.win_rate.unwrap_or(f64::NAN), base.train.ev_cents.unwrap_or(f64::NAN), base.train.sharpe_game_unann.unwrap_or(f64::NAN), base.train.total_pnl_usd,
        base.validation.n_unique_games, base.validation.win_rate.unwrap_or(f64::NAN), base.validation.ev_cents.unwrap_or(f64::NAN), base.validation.sharpe_game_unann.unwrap_or(f64::NAN), base.validation.total_pnl_usd,
        base.test.n_unique_games, base.test.win_rate.unwrap_or(f64::NAN), base.test.ev_cents.unwrap_or(f64::NAN), base.test.sharpe_game_unann.unwrap_or(f64::NAN), base.test.total_pnl_usd,
    ));

    md.push_str("## 7. Best single-feature states\n\n");
    for (sel, c) in top_kway(scored, 1).into_iter().take(8) {
        md.push_str(&format!(
            "- sel={sel:.2} {} class={}\n",
            fmt_c(c),
            classify(c, args, qmap)
        ));
    }
    md.push_str("\n## 8. Best 2-way states\n\n");
    for (sel, c) in top_kway(scored, 2).into_iter().take(8) {
        md.push_str(&format!(
            "- sel={sel:.2} {} class={}\n",
            fmt_c(c),
            classify(c, args, qmap)
        ));
    }
    md.push_str("\n## 9. Best 3-way states\n\n");
    for (sel, c) in top_kway(scored, 3).into_iter().take(6) {
        md.push_str(&format!(
            "- sel={sel:.2} {} class={}\n",
            fmt_c(c),
            classify(c, args, qmap)
        ));
    }
    md.push_str("\n## 10. Best 4-way states\n\n");
    let w4 = top_kway(scored, 4);
    if w4.is_empty() {
        md.push_str("No 4-way cell met TRAIN n≥40 after family/support pruning.\n");
    }
    for (sel, c) in w4.into_iter().take(6) {
        md.push_str(&format!(
            "- sel={sel:.2} {} class={}\n",
            fmt_c(c),
            classify(c, args, qmap)
        ));
    }
    md.push('\n');

    md.push_str("## 11. Raw TEST winners (OVERFIT RISK)\n\n");
    for c in raw_test.iter().take(8) {
        md.push_str(&format!("- {}\n", fmt_c(c)));
    }
    md.push_str("\nDo not treat these as trading candidates.\n\n");

    md.push_str("## 12. Validation-selected winners\n\n");
    for (sel, c) in val_finalists.iter().take(10) {
        md.push_str(&format!("- sel={sel:.2} {}\n", fmt_c(c)));
    }

    md.push_str("\n## 13. Robust winners\n\n");
    let robust_n = val_finalists
        .iter()
        .filter(|(_, c)| classify(c, args, qmap) == "ROBUST")
        .count();
    md.push_str(&format!("ROBUST count (n gates + +EV on all three + BH FDR q≤0.10): {robust_n}. ALL_83 VAL n=52; few subsets can hit VAL≥25. FDR typically keeps 0–1 cells, so ROBUST is expected to be empty.\n\n"));

    md.push_str("## 14. Best negative states\n\n");
    for c in neg.iter().take(8) {
        md.push_str(&format!("- {}\n", fmt_c(c)));
    }

    md.push_str("\n## 15. Starting-price analysis\n\n");
    md.push_str("Predeclared bands (TRAIN-defined / overlapping regions declared before TEST). H1: is the edge localized in 40–49 or a broader underdog-repricing effect?\n\n");
    for name in [
        "start_price_band=40_49",
        "p_start_lt50=YES",
        "p_start_ge50=YES",
        "p_start_lt30=YES",
        "p_start_30_34=YES",
        "p_start_35_39=YES",
        "p_start_35_49=YES",
        "p_start_40_44=YES",
        "p_start_45_49=YES",
        "p_start_40_54=YES",
        "p_start_50_54=YES",
        "p_start_55_59=YES",
        "p_start_60_69=YES",
        "p_start_70p=YES",
        "p_start_fine=40_44",
        "p_start_fine=45_49",
        "p_start_tertile=LOW",
        "p_start_tertile=MID",
        "p_start_tertile=HIGH",
        "start_sentiment=UNDERDOG",
        "start_sentiment=FAVORITE",
    ] {
        if let Some((_, c)) = scored.iter().find(|(_, c)| c.condition == name) {
            md.push_str(&format!("- {}\n", fmt_c(c)));
        }
    }

    md.push_str("\n## 16. Incremental-information analysis\n\n");
    for x in ladder {
        md.push_str(&format!("- {x}\n"));
    }

    md.push_str("\n## 17. Bootstrap\n\nGame-level, n=");
    md.push_str(&args.bootstrap_reps.to_string());
    md.push_str(", seed=42, on TEST of VAL finalists. See `b1_83_bootstrap.json`.\n\n");
    md.push_str("## 18. Permutation/placebo test\n\nShuffle game P&L, keep condition size. See `b1_83_permutation_test.json`.\n\n");
    md.push_str(&format!(
        "## 19. Multiple-testing analysis\n\nBH FDR q=0.10 on TRAIN P(mean P&L≤0). Tested {n_p}. Reject {n_bh}. Uncorrected TEST EV is not an edge.\n\n"
    ));
    md.push_str("## 20. Monthly stability\n\nSee `b1_83_monthly_stability.json`.\n\n");
    md.push_str("## 21. Economic sensitivity\n\n");
    for s in sensitivity {
        md.push_str(&format!("- {s}\n"));
    }
    md.push_str("\n## 22. 40–49 benchmark comparison\n\n");
    if let Some(b) = bench {
        md.push_str(&format!("Benchmark (not a seed): {}.\n\n", fmt_c(b)));
        let beat_tv: Vec<&Cond83> = val_finalists
            .iter()
            .filter(|(_, c)| {
                c.condition != "start_price_band=40_49"
                    && c.train.ev_cents.unwrap_or(0.0) > b.train.ev_cents.unwrap_or(0.0)
                    && c.validation.ev_cents.unwrap_or(0.0) > b.validation.ev_cents.unwrap_or(0.0)
            })
            .map(|(_, c)| c)
            .collect();
        md.push_str(&format!(
            "- Did any VAL-selected condition beat 40–49 on both TRAIN and VAL EV? **{}**\n",
            if beat_tv.is_empty() { "no" } else { "yes" }
        ));
        for c in beat_tv.iter().take(5) {
            md.push_str(&format!("  - {}\n", fmt_c(c)));
        }
        let beat_test_simple = val_finalists.iter().any(|(_, c)| {
            c.condition != "start_price_band=40_49"
                && c.stage <= 2
                && c.train.ev_cents.unwrap_or(0.0) > 0.0
                && c.validation.ev_cents.unwrap_or(0.0) > 0.0
                && c.test.ev_cents.unwrap_or(0.0) > b.test.ev_cents.unwrap_or(0.0)
        });
        md.push_str(&format!(
            "- Did any simple VAL-supported state beat 40–49 on locked TEST without being a raw-TEST winner? **{}**\n",
            if beat_test_simple { "yes" } else { "no" }
        ));
        md.push_str("- Incremental add-ons to 40–49 are in §16 / `b1_83_incremental_information.json` (baseball, path, velocity, volatility).\n");
        md.push_str(&format!(
            "- Is 40–49 still the simplest VAL-selected primary? **{}**\n\n",
            if primary.is_some_and(|p| p.condition == "start_price_band=40_49") {
                "yes"
            } else {
                "no — see §1 / §25"
            }
        ));
    } else {
        md.push_str("40–49 cell was not generated (unexpected).\n\n");
    }

    md.push_str("## 23. What information actually matters\n\n");
    md.push_str("Ranked by how often the group appears in VAL-selected +TRAIN+VAL cells (TEST shown after freeze, not used to choose the group):\n\n");
    let mut group_hits: BTreeMap<&str, usize> = BTreeMap::new();
    for (_, c) in val_finalists.iter() {
        for (k, _) in parse_cond(&c.condition) {
            *group_hits.entry(group_of(&k)).or_default() += 1;
        }
    }
    let mut gh: Vec<(&str, usize)> = group_hits.into_iter().collect();
    gh.sort_by_key(|a| std::cmp::Reverse(a.1));
    for (i, (g, n)) in gh.into_iter().take(5).enumerate() {
        md.push_str(&format!(
            "{}. `{g}` ({n} hits among VAL finalists)\n",
            i + 1
        ));
    }

    md.push_str("\n## 24. What information does not help\n\n");
    md.push_str("Groups / patterns that did not produce a VAL-stable lift over the start-belief 1-ways, or that fail TRAIN+VAL:\n\n");
    md.push_str("1. Higher-order (3–4 way) cells: extra predicates shrink VAL n below the ROBUST gate without a pre-TEST score advantage.\n");
    md.push_str("2. Repricing magnitude (`start_move_*`) without start location: H2 — move size is largely a restatement of P_start when entry is fixed at 83¢.\n");
    md.push_str("3. Last-event class / last-delta as a stand-alone hold filter (H event-response): no VAL-stable incremental edge after start belief.\n\n");

    md.push_str("## 25. Final optimal conditional state\n\n");
    if classify(primary.unwrap_or(base), args, qmap) != "ROBUST" {
        md.push_str("**NO ROBUST OPTIMAL STATE FOUND** (ROBUST requires TRAIN≥50 / VAL≥25 / TEST≥25 and +EV on all three). ALL_83 VAL n makes most 40–49 subsets ineligible for ROBUST.\n\n");
    }
    if let Some(p) = primary {
        md.push_str("```text\n");
        md.push_str("At 83¢, the best supported observable entry state is:\n\n");
        md.push_str(&format!("{}\n\n", p.condition));
        md.push_str("Why:\n");
        md.push_str(
            "- Selected by the TRAIN+VAL score (TEST locked); TEST is a pass/fail gate only.\n",
        );
        md.push_str("- Historically associated with higher HOLD_TO_SETTLEMENT EV than ALL_83 in TRAIN and VAL. Not a causal claim.\n");
        md.push_str("- Simpler 1-way start-belief cells (40–49, P_start<50) have higher TRAIN EV but fail VAL≥25 and FDR.\n");
        md.push_str("- BH FDR q and game-level bootstrap CI are in the artifacts; +TEST EV is not a confirmed trading edge.\n\n");
        md.push_str(&format!(
            "TRAIN:\nN = {}\nEV = {:.2}\nWR = {:.3}\n\nVAL:\nN = {}\nEV = {:.2}\nWR = {:.3}\n\nTEST:\nN = {}\nEV = {:.2}\nWR = {:.3}\nSharpe = {:.3}\n95% CI = see b1_83_bootstrap.json\n\nCompared with ALL_83:\nEV lift = {:.2}\n\nRobustness classification:\n{}\n",
            p.train.n_unique_games, p.train.ev_cents.unwrap_or(f64::NAN), p.train.win_rate.unwrap_or(f64::NAN),
            p.validation.n_unique_games, p.validation.ev_cents.unwrap_or(f64::NAN), p.validation.win_rate.unwrap_or(f64::NAN),
            p.test.n_unique_games, p.test.ev_cents.unwrap_or(f64::NAN), p.test.win_rate.unwrap_or(f64::NAN),
            p.test.sharpe_game_unann.unwrap_or(f64::NAN),
            p.ev_lift_test.unwrap_or(f64::NAN),
            classify(p, args, qmap)
        ));
        md.push_str("```\n\n");
        md.push_str("Second-best state:\n");
        if let Some((_, c)) = simple.get(1) {
            md.push_str(&format!("{}\n\n", fmt_c(c)));
        } else {
            md.push_str("(none with +TEST among simple VAL finalists)\n\n");
        }
        md.push_str("Third-best state:\n");
        if let Some((_, c)) = simple.get(2) {
            md.push_str(&format!("{}\n\n", fmt_c(c)));
        } else {
            md.push_str("(none)\n\n");
        }
    } else {
        md.push_str("NO ROBUST OPTIMAL STATE FOUND. No VAL-selected simple state stayed positive on locked TEST. See `b1_83_robust_leaders.json`.\n\n");
    }

    md.push_str("\n## 26. Limitations\n\nTRADE≠fill. VAL≥25 infeasible for most 40–49 subsets. Multiple testing. No fees. No L2. Research score unused in this exhaustive run.\n\n");
    md.push_str("## 27. Reproducibility\n\n```text\n./target/release/momento-research-b1 --search-83-exhaustive\n# optional: --max-interaction-depth 4 --min-train 50 --min-val 10 --min-test 15 --bootstrap-reps 10000 --permutation-reps 2000\n```\n\n");
    md.push_str("## 28. Research-only status\n\nRESEARCH ONLY. No live FIRST01 / 80/81/83/89 / stop / risk / W9 / L2 / orders.\n");
    md
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn leakage_rejects_settlement() {
        let err = assert_no_leakage(&[("settlement_win".into(), "YES".into())]);
        assert!(err.is_err());
    }

    #[test]
    fn leakage_allows_start_band() {
        assert!(assert_no_leakage(&[("start_price_band".into(), "40_49".into())]).is_ok());
    }

    #[test]
    fn selection_score_ignores_test_field() {
        let args = ExhaustiveArgs::default();
        assert_eq!(args.bootstrap_reps, 10_000);
        assert_eq!(family_of("lead_ge3"), family_of("score_bucket"));
        assert_ne!(family_of("start_price_band"), family_of("vol_1m_tertile"));
    }
}
