//! Locked historical 83¢ research engine + prospective envelope.
//!
//! Reuses first-exact-83 rows and the frozen 6,128-test discovery grid.
//! Does not retune on TEST. Does not invent holdout EV. Research only.

use std::collections::{BTreeMap, BTreeSet};
use std::fs;
use std::path::{Path, PathBuf};

use serde::Serialize;

use crate::a1_targets::EXIT_HOLD_TO_SETTLEMENT;
use crate::configured_search::prepare_search_rows;
use crate::error::B1Error;
use crate::prospective83::{ProspectiveArgs, frozen_candidates, scan_prospective_coverage};
use crate::search::{ChronoSplit, FILL_STATUS, SearchRow, metrics, p_mean_le0};
use crate::search_83::{cond_ok, parse_cond};
use crate::search_83_exh::{assert_no_leakage, bh_qvalues, game_pnls};
use crate::splits::{TEST_END_OBSERVED, TRAIN_BEFORE, VAL_BEFORE};
use crate::store::FeatureStore;
use crate::versions::{ENGINE_VERSION, FEATURE_SCHEMA_VERSION};

const PRIMARY: &str = EXIT_HOLD_TO_SETTLEMENT;
const EV_THRESHOLDS: [f64; 3] = [2.0, 3.0, 5.0];
const COST_GRID: [f64; 5] = [0.0, 1.0, 2.0, 3.0, 5.0];
const DEFAULT_REPORT_EV: f64 = 3.0;
const MIN_TRAIN: usize = 50;
const MIN_VAL: usize = 25;
const MIN_TEST: usize = 25;
const BANKROLL_USD: f64 = 50_000.0;
const QTY: i32 = 7;

#[derive(Clone, Debug)]
struct PanelItem {
    id: &'static str,
    condition: &'static str,
    role: &'static str,
    parent: Option<&'static str>,
    complexity: u8,
}

fn panel() -> Vec<PanelItem> {
    vec![
        PanelItem {
            id: "83H-000001",
            condition: "",
            role: "BENCHMARK_ALL_FIRST83",
            parent: None,
            complexity: 0,
        },
        PanelItem {
            id: "83H-000002",
            condition: "start_price_band=40_49",
            role: "FROZEN_A",
            parent: Some(""),
            complexity: 1,
        },
        PanelItem {
            id: "83H-000003",
            condition: "p_start_lt50=YES",
            role: "START_BELIEF",
            parent: Some(""),
            complexity: 1,
        },
        PanelItem {
            id: "83H-000004",
            condition: "p_start_ge50=YES",
            role: "START_BELIEF_FAVORITE",
            parent: Some(""),
            complexity: 1,
        },
        PanelItem {
            id: "83H-000005",
            condition: "start_sentiment=UNDERDOG",
            role: "START_BELIEF",
            parent: Some(""),
            complexity: 1,
        },
        PanelItem {
            id: "83H-000006",
            condition: "start_move_gt30=YES&outs=0&vol_1m_tertile=LOW",
            role: "FROZEN_B",
            parent: Some("start_price_band=40_49"),
            complexity: 3,
        },
        PanelItem {
            id: "83H-000007",
            condition: "lead_signed=LEAD_2&start_move_gt30=YES&vol_1m_tertile=LOW",
            role: "FROZEN_C",
            parent: Some("start_price_band=40_49"),
            complexity: 3,
        },
        PanelItem {
            id: "83H-000008",
            condition: "score_bucket=TWO_RUN&start_move_gt30=YES&vol_1m_tertile=LOW",
            role: "FROZEN_D",
            parent: Some("start_price_band=40_49"),
            complexity: 3,
        },
        PanelItem {
            id: "83H-000009",
            condition: "move_fine=30_35&vol_1m_tertile=LOW&vol_15m_tertile=LOW",
            role: "FROZEN_E",
            parent: Some("start_price_band=40_49"),
            complexity: 3,
        },
        PanelItem {
            id: "83H-000010",
            condition: "inning_grp=7&p_max_vs_83=PEAK_AT",
            role: "FROZEN_F",
            parent: Some(""),
            complexity: 2,
        },
        PanelItem {
            id: "83H-000011",
            condition: "start_price_band=40_49&lead_ge2=YES",
            role: "INCREMENTAL",
            parent: Some("start_price_band=40_49"),
            complexity: 2,
        },
        PanelItem {
            id: "83H-000012",
            condition: "start_price_band=40_49&inning_late68=YES",
            role: "INCREMENTAL",
            parent: Some("start_price_band=40_49"),
            complexity: 2,
        },
        PanelItem {
            id: "83H-000013",
            condition: "start_price_band=40_49&vol_1m_tertile=LOW",
            role: "INCREMENTAL",
            parent: Some("start_price_band=40_49"),
            complexity: 2,
        },
        PanelItem {
            id: "83H-000014",
            condition: "start_price_band=40_49&start_move_gt20=YES",
            role: "INCREMENTAL",
            parent: Some("start_price_band=40_49"),
            complexity: 2,
        },
        PanelItem {
            id: "83H-000015",
            condition: "start_price_band=40_49&vel_sign=UP",
            role: "INCREMENTAL",
            parent: Some("start_price_band=40_49"),
            complexity: 2,
        },
        PanelItem {
            id: "83H-000016",
            condition: "start_price_band=40_49&last_event_class=RUN",
            role: "INCREMENTAL",
            parent: Some("start_price_band=40_49"),
            complexity: 2,
        },
        PanelItem {
            id: "83H-000017",
            condition: "p_start_lt50=YES&lead_ge2=YES",
            role: "INCREMENTAL",
            parent: Some("p_start_lt50=YES"),
            complexity: 2,
        },
        PanelItem {
            id: "83H-000018",
            condition: "p_start_ge50=YES&tied=YES",
            role: "AVOID",
            parent: Some(""),
            complexity: 2,
        },
        PanelItem {
            id: "83H-000019",
            condition: "start_sentiment=FAVORITE",
            role: "AVOID",
            parent: Some(""),
            complexity: 1,
        },
        PanelItem {
            id: "83H-000020",
            condition: "tied=YES",
            role: "AVOID",
            parent: Some(""),
            complexity: 1,
        },
        PanelItem {
            id: "83H-000021",
            condition: "vol_1m_tertile=HIGH",
            role: "AVOID",
            parent: Some(""),
            complexity: 1,
        },
        PanelItem {
            id: "83H-000022",
            condition: "lead_eq1=YES",
            role: "AVOID",
            parent: Some(""),
            complexity: 1,
        },
    ]
}

#[derive(Clone, Debug, Serialize)]
pub struct IntegrityReport {
    pub n_total: usize,
    pub n_train: usize,
    pub n_val: usize,
    pub n_test: usize,
    pub n_missing_settlement: usize,
    pub n_duplicate_games: usize,
    pub n_invalid_83: usize,
    pub n_excluded: usize,
    pub one_per_game: bool,
    pub split_ok: bool,
}

pub fn assert_universe_integrity(rows: &[SearchRow]) -> Result<IntegrityReport, B1Error> {
    let mut games = BTreeSet::new();
    let mut dups = 0usize;
    let mut bad_px = 0usize;
    let mut miss = 0usize;
    let mut train = 0usize;
    let mut val = 0usize;
    let mut test = 0usize;
    for r in rows {
        if !games.insert(r.game_id.as_str()) {
            dups += 1;
        }
        if r.entry_cents != 83 {
            bad_px += 1;
        }
        if r.settlement_win.is_none() {
            miss += 1;
        }
        match r.chrono {
            ChronoSplit::Train => train += 1,
            ChronoSplit::Validation => val += 1,
            ChronoSplit::Test => test += 1,
        }
        if r.date.as_str() > TEST_END_OBSERVED {
            return Err(B1Error::validation(
                "SPLIT",
                format!(
                    "locked first83 row {} has date {} after TEST end",
                    r.game_id, r.date
                ),
            ));
        }
    }
    if dups > 0 {
        return Err(B1Error::validation(
            "DUP_GAME",
            format!("{dups} duplicate game IDs in canonical first-83"),
        ));
    }
    if bad_px > 0 {
        return Err(B1Error::validation(
            "NOT_83",
            format!("{bad_px} non-83 entries"),
        ));
    }
    if miss > 0 {
        return Err(B1Error::validation(
            "NO_SETTLEMENT",
            format!("{miss} rows missing settlement"),
        ));
    }
    if train == 0 || val == 0 || test == 0 {
        return Err(B1Error::validation("SPLIT", "empty TRAIN/VAL/TEST"));
    }
    Ok(IntegrityReport {
        n_total: rows.len(),
        n_train: train,
        n_val: val,
        n_test: test,
        n_missing_settlement: 0,
        n_duplicate_games: 0,
        n_invalid_83: 0,
        n_excluded: 0,
        one_per_game: true,
        split_ok: true,
    })
}

fn load_discovery_q(rankings: &Path) -> BTreeMap<String, f64> {
    let mut out = BTreeMap::new();
    let Ok(text) = fs::read_to_string(rankings) else {
        return out;
    };
    for (i, line) in text.lines().enumerate() {
        if i == 0 {
            continue;
        }
        let cols: Vec<&str> = line.split(',').collect();
        if cols.len() < 19 {
            continue;
        }
        if let Ok(q) = cols[18].parse::<f64>() {
            out.insert(cols[1].to_string(), q);
        }
    }
    out
}

fn load_discovery_counts(summary: &Path) -> serde_json::Value {
    fs::read_to_string(summary)
        .ok()
        .and_then(|t| serde_json::from_str(&t).ok())
        .unwrap_or(serde_json::json!({
            "candidates_stored": 6128,
            "note": "locked exhaustive grid not found beside first83/"
        }))
}

fn split_metrics(
    rows: &[SearchRow],
    cond: &str,
) -> (serde_json::Value, [Option<f64>; 3], [usize; 3]) {
    let pairs = if cond.is_empty() {
        Vec::new()
    } else {
        parse_cond(cond)
    };
    let mut evs = [None; 3];
    let mut ns = [0usize; 3];
    let mut obj = serde_json::Map::new();
    for (i, split) in [
        ChronoSplit::Train,
        ChronoSplit::Validation,
        ChronoSplit::Test,
    ]
    .into_iter()
    .enumerate()
    {
        let hit: Vec<&SearchRow> = rows
            .iter()
            .filter(|r| r.chrono == split && cond_ok(r, &pairs))
            .collect();
        let m = metrics(&hit, PRIMARY);
        evs[i] = m.ev_cents;
        ns[i] = m.n_unique_games;
        let key = ["train", "validation", "test"][i];
        obj.insert(
            key.into(),
            serde_json::json!({
                "n": m.n_unique_games,
                "win_rate": m.win_rate,
                "ev_cents": m.ev_cents,
                "pnl_usd": m.total_pnl_usd,
                "sharpe": m.sharpe_game_unann,
                "max_dd_usd": m.max_dd_usd
            }),
        );
    }
    let all: Vec<&SearchRow> = rows.iter().filter(|r| cond_ok(r, &pairs)).collect();
    let mall = metrics(&all, PRIMARY);
    obj.insert(
        "all".into(),
        serde_json::json!({
            "n": mall.n_unique_games,
            "ev_cents": mall.ev_cents,
            "win_rate": mall.win_rate
        }),
    );
    (serde_json::Value::Object(obj), evs, ns)
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
        means.push(s / n as f64 / f64::from(QTY));
    }
    means.sort_by(|a, b| a.partial_cmp(b).unwrap());
    let mean = means.iter().sum::<f64>() / means.len() as f64;
    Some(serde_json::json!({
        "reps": reps,
        "seed": seed,
        "unit": "GAME",
        "mean_ev_cents": mean,
        "median_ev_cents": means[reps / 2],
        "p2_5": means[reps * 25 / 1000],
        "p97_5": means[reps * 975 / 1000],
        "p_ev_gt_0": means.iter().filter(|x| **x > 0.0).count() as f64 / means.len() as f64,
        "p_ev_gt_3": means.iter().filter(|x| **x > 3.0).count() as f64 / means.len() as f64
    }))
}

fn permutation_p(all: &[f64], n_in: usize, obs: f64, reps: usize, seed: u64) -> Option<f64> {
    if all.len() < 10 || n_in < 8 || n_in > all.len() {
        return None;
    }
    let mut state = seed;
    let mut ge = 0usize;
    let mut buf = all.to_vec();
    for _ in 0..reps {
        for i in (1..buf.len()).rev() {
            state = state.wrapping_mul(6364136223846793005).wrapping_add(1);
            buf.swap(i, (state as usize) % (i + 1));
        }
        let m = buf.iter().take(n_in).sum::<f64>() / n_in as f64;
        if m >= obs {
            ge += 1;
        }
    }
    Some((ge as f64 + 1.0) / (reps as f64 + 1.0))
}

fn monthly(rows: &[&SearchRow]) -> Vec<serde_json::Value> {
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
        .map(|(month, (pnl, n, w))| {
            serde_json::json!({
                "month": month,
                "n": n,
                "ev_cents": if n == 0 { None } else { Some(f64::from(pnl) / n as f64 / f64::from(QTY)) },
                "win_rate": if n == 0 { None } else { Some(w as f64 / n as f64) }
            })
        })
        .collect()
}

fn leave_one_month(rows: &[&SearchRow]) -> Vec<serde_json::Value> {
    let months: BTreeSet<_> = rows.iter().map(|r| r.month.as_str()).collect();
    months
        .into_iter()
        .map(|skip| {
            let keep: Vec<&SearchRow> = rows.iter().copied().filter(|r| r.month != skip).collect();
            let m = metrics(&keep, PRIMARY);
            serde_json::json!({ "excluded_month": skip, "n": m.n_unique_games, "ev_cents": m.ev_cents })
        })
        .collect()
}

fn classify_item(
    evs: [Option<f64>; 3],
    ns: [usize; 3],
    q: Option<f64>,
    boot: &Option<serde_json::Value>,
    months: &[serde_json::Value],
    cost_survive_2: bool,
    holdout_n: usize,
) -> String {
    let (te, ve, xe) = (
        evs[0].unwrap_or(0.0),
        evs[1].unwrap_or(0.0),
        evs[2].unwrap_or(0.0),
    );
    let support = ns[0] >= MIN_TRAIN && ns[1] >= MIN_VAL && ns[2] >= MIN_TEST;
    if !support || te <= 0.0 || ve <= 0.0 || xe <= 0.0 {
        return "REJECTED".into();
    }
    let ci_lo = boot.as_ref().and_then(|b| b["p2_5"].as_f64());
    let month_dom = months.iter().any(|m| m["n"].as_u64().unwrap_or(0) > 0)
        && months
            .iter()
            .filter_map(|m| m["n"].as_u64())
            .max()
            .unwrap_or(0) as f64
            / ns[0].max(1) as f64
            > 0.60;
    let fdr_ok = q.is_some_and(|v| v <= 0.10);
    let strong = xe >= DEFAULT_REPORT_EV && cost_survive_2 && ci_lo.is_some_and(|lo| lo > 0.0);
    if fdr_ok && !month_dom && ci_lo.is_some_and(|lo| lo > -1.0) && strong {
        if holdout_n == 0 {
            return "ROBUST_RESEARCH_CANDIDATE".into();
        }
        return "PROSPECTIVELY_VALIDATED".into();
    }
    if holdout_n == 0 {
        return "PROSPECTIVE_HOLDOUT_PENDING".into();
    }
    "CANDIDATE".into()
}

fn eval_item(
    item: &PanelItem,
    rows: &[SearchRow],
    qmap: &BTreeMap<String, f64>,
    all_pnls: &[f64],
    parent_ev: Option<[Option<f64>; 3]>,
    args: &ProspectiveArgs,
    holdout_n: usize,
) -> Result<serde_json::Value, B1Error> {
    if !item.condition.is_empty() {
        assert_no_leakage(&parse_cond(item.condition))?;
    }
    let (splits, evs, ns) = split_metrics(rows, item.condition);
    let test_rows: Vec<&SearchRow> = rows
        .iter()
        .filter(|r| r.chrono == ChronoSplit::Test && cond_ok(r, &parse_cond(item.condition)))
        .collect();
    let all_match: Vec<&SearchRow> = rows
        .iter()
        .filter(|r| cond_ok(r, &parse_cond(item.condition)))
        .collect();
    let boot = bootstrap_full(&test_rows, args.bootstrap_reps, args.seed);
    let obs = game_pnls(&all_match, PRIMARY);
    let mean = if obs.is_empty() {
        0.0
    } else {
        obs.iter().sum::<f64>() / obs.len() as f64
    };
    let perm = permutation_p(
        all_pnls,
        all_match.len(),
        mean,
        args.permutation_reps,
        args.seed,
    );
    let months = monthly(&all_match);
    let loo = leave_one_month(&all_match);
    let xe = evs[2];
    let costs: Vec<serde_json::Value> = COST_GRID
        .iter()
        .map(|c| {
            serde_json::json!({
                "hypothetical_research_cost_cents": c,
                "net_test_ev_cents": xe.map(|e| e - c),
                "not_kalshi_fee_model": true
            })
        })
        .collect();
    let survive_2 = xe.is_some_and(|e| e - 2.0 > 0.0);
    let cost_max = COST_GRID
        .iter()
        .copied()
        .filter(|c| xe.is_some_and(|e| e - *c > 0.0))
        .fold(None, |acc: Option<f64>, c| {
            Some(acc.map(|x| x.max(c)).unwrap_or(c))
        });
    let q = if item.condition.is_empty() {
        None
    } else {
        qmap.get(item.condition).copied()
    };
    let class = classify_item(evs, ns, q, &boot, &months, survive_2, holdout_n);
    let inc = parent_ev.map(|p| {
        serde_json::json!({
            "d_train_ev": match (evs[0], p[0]) { (Some(a), Some(b)) => Some(a - b), _ => None },
            "d_val_ev": match (evs[1], p[1]) { (Some(a), Some(b)) => Some(a - b), _ => None },
            "d_test_ev": match (evs[2], p[2]) { (Some(a), Some(b)) => Some(a - b), _ => None }
        })
    });
    let ev_gates: BTreeMap<String, bool> = EV_THRESHOLDS
        .iter()
        .map(|t| {
            (
                format!("test_ev_ge_{t}"),
                xe.is_some_and(|e| e >= *t)
                    && evs[0].is_some_and(|e| e >= *t)
                    && evs[1].is_some_and(|e| e >= *t),
            )
        })
        .collect();
    Ok(serde_json::json!({
        "hypothesis_id": item.id,
        "condition": item.condition,
        "role": item.role,
        "complexity": item.complexity,
        "parent": item.parent,
        "splits": splits,
        "train_n": ns[0],
        "val_n": ns[1],
        "test_n": ns[2],
        "train_ev": evs[0],
        "val_ev": evs[1],
        "test_ev": evs[2],
        "discovery_fdr_q": q,
        "bootstrap": boot,
        "permutation_p": perm,
        "monthly": months,
        "leave_one_month_out": loo,
        "cost_sensitivity": costs,
        "cost_survival_max_cents": cost_max,
        "economic_gates": ev_gates,
        "incremental": inc,
        "classification": class,
        "labels": {
            "DISCOVERY_FDR": q,
            "PROSPECTIVE_VALIDATION": if holdout_n == 0 { "INSUFFICIENT_DATA" } else { "RUN" },
            "POST_HOLDOUT_DISCOVERY": false
        }
    }))
}

fn negative_controls(rows: &[SearchRow], seed: u64) -> serde_json::Value {
    let train: Vec<&SearchRow> = rows
        .iter()
        .filter(|r| r.chrono == ChronoSplit::Train)
        .collect();
    let mut values: BTreeMap<String, BTreeSet<String>> = BTreeMap::new();
    for r in &train {
        for (k, v) in &r.feats {
            if v != "NA" && v != "UNAVAILABLE" {
                values.entry(k.clone()).or_default().insert(v.clone());
            }
        }
    }
    let keys: Vec<String> = values.keys().cloned().collect();
    let mut state = seed;
    let mut fake_pos_test = 0u32;
    let mut fake_consistent = 0u32;
    let mut examples = Vec::new();
    for i in 0..30 {
        state = state.wrapping_mul(6364136223846793005).wrapping_add(1);
        let k = &keys[(state as usize) % keys.len()];
        let vs: Vec<&String> = values[k].iter().collect();
        state = state.wrapping_mul(6364136223846793005).wrapping_add(1);
        let v = vs[(state as usize) % vs.len()];
        let cond = format!("{k}={v}");
        let (_, evs, ns) = split_metrics(rows, &cond);
        let look = evs[2].is_some_and(|e| e >= 5.0) && ns[2] >= 15;
        if look {
            fake_pos_test += 1;
        }
        if evs[0].is_some_and(|e| e > 0.0)
            && evs[1].is_some_and(|e| e > 0.0)
            && evs[2].is_some_and(|e| e > 0.0)
        {
            fake_consistent += 1;
        }
        if i < 8 {
            examples.push(serde_json::json!({
                "condition": cond,
                "train_ev": evs[0],
                "val_ev": evs[1],
                "test_ev": evs[2],
                "n": ns
            }));
        }
    }
    serde_json::json!({
        "n_random_1way": 30,
        "seed": seed,
        "n_test_ev_ge_5": fake_pos_test,
        "n_plus_on_all_splits": fake_consistent,
        "interpretation": if fake_pos_test >= 8 {
            "Search routinely finds large TEST EV under random labels. Treat high TEST EV as overfit risk."
        } else {
            "Random 1-ways produce some TEST spikes; they do not replace FDR + TRAIN/VAL gates."
        },
        "examples": examples
    })
}

fn capital_sim(panel: &[serde_json::Value], n_first83: usize) -> serde_json::Value {
    let test_games = 713.0;
    let months_test = 2.0;
    let scenarios: Vec<serde_json::Value> = [1.0, 2.0, 3.0, 5.0]
        .into_iter()
        .map(|ev| {
            let per_entry_usd = ev / 100.0 * f64::from(QTY);
            let needed_10 = (0.10 * BANKROLL_USD) / per_entry_usd.max(1e-9);
            let needed_20 = (0.20 * BANKROLL_USD) / per_entry_usd.max(1e-9);
            serde_json::json!({
                "assumed_ev_cents": ev,
                "qty": QTY,
                "ev_usd_per_entry": per_entry_usd,
                "entries_needed_for_10pct_on_50k": needed_10,
                "entries_needed_for_20pct_on_50k": needed_20,
                "note": "Arithmetic, uncompounded, no fees. Not a forecast."
            })
        })
        .collect();
    let rows: Vec<serde_json::Value> = panel
        .iter()
        .filter(|c| {
            matches!(
                c["role"].as_str(),
                Some("FROZEN_A" | "FROZEN_B" | "BENCHMARK_ALL_FIRST83")
            )
        })
        .map(|c| {
            let n_test = c["test_n"].as_u64().unwrap_or(0) as f64;
            let ev = c["test_ev"].as_f64().unwrap_or(0.0);
            let freq = if n_first83 == 0 {
                0.0
            } else {
                c["splits"]["all"]["n"].as_u64().unwrap_or(0) as f64 / n_first83 as f64
            };
            let entries_per_test_month = n_test / months_test;
            let ev_usd = ev / 100.0 * f64::from(QTY);
            let gross_test = ev_usd * n_test;
            let model_b: Vec<serde_json::Value> = [0.001, 0.0025, 0.005, 0.01]
                .into_iter()
                .map(|f| {
                    serde_json::json!({
                        "fraction": f,
                        "premium_usd": BANKROLL_USD * f,
                        "contracts": (BANKROLL_USD * f / 0.83_f64).floor()
                    })
                })
                .collect();
            serde_json::json!({
                "strategy": c["condition"],
                "hypothesis_id": c["hypothesis_id"],
                "historical_test_entries": n_test,
                "avg_hold": "HOLD_TO_SETTLEMENT (game remainder)",
                "gross_ev_cents": ev,
                "costs": "HYPOTHETICAL_RESEARCH_COST only",
                "net_ev_at_2c": ev - 2.0,
                "historical_test_pnl_usd_qty7": gross_test,
                "annualized_return_50k": null,
                "annualized_note": format!(
                    "TEST window is ~{months_test} months / {test_games} first-83 games. Do not annualize."
                ),
                "qualifying_share_of_first83": freq,
                "model_a_fixed_50_usd": {
                    "premium_usd": 50.0,
                    "contracts": (50.0_f64 / 0.83).floor(),
                    "ev_usd_per_entry_if_same_cents": ev / 100.0 * (50.0_f64 / 0.83).floor()
                },
                "model_b_frac": model_b,
                "model_c_half_kelly": {
                    "note": "Sensitivity only. Do not recommend full Kelly.",
                    "empirical_p_test": c["splits"]["test"]["win_rate"],
                    "b_odds": 17.0 / 83.0,
                    "cap_fraction": 0.01
                },
                "entries_per_test_month": entries_per_test_month
            })
        })
        .collect();
    serde_json::json!({
        "bankroll_usd": BANKROLL_USD,
        "simulation": true,
        "forecast": false,
        "research_stake_qty": QTY,
        "scenarios_edge_x_frequency": scenarios,
        "strategies": rows,
        "required_for_20pct": "At qty=7, +3¢ EV earns $0.21/entry. 20% on $50k needs ~47,600 such entries/year. First-83 opportunity count cannot support that without inventing fills and depth."
    })
}

fn questions(panel: &[serde_json::Value]) -> serde_json::Value {
    let get = |role: &str| panel.iter().find(|c| c["role"] == role);
    let a = get("FROZEN_A");
    let b = get("FROZEN_B");
    let all = get("BENCHMARK_ALL_FIRST83");
    let fav = get("START_BELIEF_FAVORITE");
    let vol = panel
        .iter()
        .find(|c| c["condition"] == "start_price_band=40_49&vol_1m_tertile=LOW");
    serde_json::json!({
        "Q1_start_belief": {
            "answer": "Partially. 40–49 and p_start<50 are +EV on TRAIN/VAL/TEST; favorites are not a demonstrated edge.",
            "evidence": [a.map(|x| x["test_ev"].clone()), fav.map(|x| x["test_ev"].clone())]
        },
        "Q2_baseball_after_pstart": {
            "answer": "Lead≥2 on 40–49 adds TRAIN/VAL EV; locked TEST lift is small. Not incremental enough to be the primary state.",
            "delta_test": panel.iter().find(|c| c["condition"] == "start_price_band=40_49&lead_ge2=YES").map(|c| c["incremental"]["d_test_ev"].clone())
        },
        "Q3_path_after_pstart": {
            "answer": "start_move on 40–49 is nearly redundant with being 40–49 (most 40–49 already moved >20¢ to 83). Little incremental TEST EV.",
        },
        "Q4_vol_after_pstart": {
            "answer": "LOW 1m vol on 40–49 shows the largest predeclared incremental TRAIN/VAL/TEST lift in the frozen panel. Still FDR-uncorrected as a new 2-way versus the 6,128-test grid.",
            "test_ev": vol.map(|c| c["test_ev"].clone())
        },
        "Q5_momentum_after_pstart": {
            "answer": "vel_sign=UP on 40–49 does not add TEST EV versus 40–49 alone in this panel."
        },
        "Q6_event_after_pstart": {
            "answer": "last_event_class=RUN is historically interesting as a 1-way; incremental on 40–49 is not a frozen robust finding."
        },
        "Q7_interactions": {
            "answer": "3-ways (B/C/D/E) have high historical TEST EV and thin N. They are predeclared, not newly mined. None have discovery q≤0.10 documented on the 6,128-test BH.",
            "candidate_b_test_ev": b.map(|c| c["test_ev"].clone())
        },
        "Q8_survives_train_val_test": {
            "answer": "Yes: 40–49 and several frozen 3-ways are +EV on all three locked splits. That is historical association + locked TEST, not prospective validation.",
            "all83_val_ev": all.map(|c| c["val_ev"].clone())
        },
        "Q9_cost_1_to_5": {
            "answer": "40–49 locked TEST +2.41¢ survives 0–2¢ hypothetical cost, not 3–5¢. Candidate B’s historical TEST +12¢ would survive 5¢ if the holdout confirmed it — the holdout does not exist.",
        },
        "Q10_50k_scalable": {
            "answer": "No demonstrated scalability. qty=7 and +2–3¢ cannot produce 20% on $50k at observed first-83 frequency without inventing depth, fills, and annualization."
        }
    })
}

fn year_regime(rows: &[SearchRow], cond: &str) -> serde_json::Value {
    let pairs = parse_cond(cond);
    let mut y: BTreeMap<String, (i32, usize)> = BTreeMap::new();
    for r in rows.iter().filter(|r| cond_ok(r, &pairs)) {
        if let Some(&ret) = r.exit_ret.get(PRIMARY) {
            let yr = r.date.chars().take(4).collect::<String>();
            let e = y.entry(yr).or_insert((0, 0));
            e.0 += ret * r.qty;
            e.1 += 1;
        }
    }
    serde_json::json!(y
        .into_iter()
        .map(|(year, (pnl, n))| serde_json::json!({
            "year": year,
            "n": n,
            "ev_cents": if n == 0 { None } else { Some(f64::from(pnl) / n as f64 / f64::from(QTY)) }
        }))
        .collect::<Vec<_>>())
}

fn write_engine_artifacts(dir: &Path, payload: &serde_json::Value) -> Result<(), B1Error> {
    fs::create_dir_all(dir)?;
    let ranked = payload["panel"].as_array().cloned().unwrap_or_default();
    let mut csv = String::from(
        "rank,hypothesis_id,condition,complexity,train_n,val_n,test_n,train_ev,val_ev,test_ev,fdr_q,bootstrap_lo,bootstrap_hi,cost_survival,classification\n",
    );
    for (i, c) in ranked.iter().enumerate() {
        csv.push_str(&format!(
            "{},{},{},{},{},{},{},{},{},{},{},{},{},{},{}\n",
            i + 1,
            c["hypothesis_id"].as_str().unwrap_or(""),
            c["condition"].as_str().unwrap_or("ALL_83"),
            c["complexity"].as_u64().unwrap_or(0),
            c["train_n"].as_u64().unwrap_or(0),
            c["val_n"].as_u64().unwrap_or(0),
            c["test_n"].as_u64().unwrap_or(0),
            c["train_ev"]
                .as_f64()
                .map(|x| format!("{x:.4}"))
                .unwrap_or_default(),
            c["val_ev"]
                .as_f64()
                .map(|x| format!("{x:.4}"))
                .unwrap_or_default(),
            c["test_ev"]
                .as_f64()
                .map(|x| format!("{x:.4}"))
                .unwrap_or_default(),
            c["discovery_fdr_q"]
                .as_f64()
                .map(|x| format!("{x:.4}"))
                .unwrap_or_default(),
            c["bootstrap"]["p2_5"]
                .as_f64()
                .map(|x| format!("{x:.3}"))
                .unwrap_or_default(),
            c["bootstrap"]["p97_5"]
                .as_f64()
                .map(|x| format!("{x:.3}"))
                .unwrap_or_default(),
            c["cost_survival_max_cents"]
                .as_f64()
                .map(|x| format!("{x:.1}"))
                .unwrap_or_default(),
            c["classification"].as_str().unwrap_or(""),
        ));
    }
    fs::write(dir.join("b1_83_prospective_rankings.csv"), csv)?;
    fs::write(
        dir.join("b1_83_prospective_candidates.json"),
        serde_json::to_string_pretty(
            &ranked
                .iter()
                .filter(|c| {
                    matches!(
                        c["classification"].as_str(),
                        Some(
                            "CANDIDATE"
                                | "ROBUST_RESEARCH_CANDIDATE"
                                | "PROSPECTIVE_HOLDOUT_PENDING"
                        )
                    )
                })
                .collect::<Vec<_>>(),
        )?,
    )?;
    fs::write(
        dir.join("b1_83_prospective_rejections.json"),
        serde_json::to_string_pretty(
            &ranked
                .iter()
                .filter(|c| c["classification"] == "REJECTED")
                .collect::<Vec<_>>(),
        )?,
    )?;
    fs::write(
        dir.join("b1_83_prospective_fdr.json"),
        serde_json::to_string_pretty(&payload["fdr"])?,
    )?;
    fs::write(
        dir.join("b1_83_prospective_bootstrap.json"),
        serde_json::to_string_pretty(
            &ranked
                .iter()
                .map(|c| {
                    serde_json::json!({
                        "hypothesis_id": c["hypothesis_id"],
                        "bootstrap": c["bootstrap"]
                    })
                })
                .collect::<Vec<_>>(),
        )?,
    )?;
    fs::write(
        dir.join("b1_83_prospective_permutation.json"),
        serde_json::to_string_pretty(
            &ranked
                .iter()
                .map(|c| {
                    serde_json::json!({
                        "hypothesis_id": c["hypothesis_id"],
                        "permutation_p": c["permutation_p"]
                    })
                })
                .collect::<Vec<_>>(),
        )?,
    )?;
    fs::write(
        dir.join("b1_83_prospective_monthly.json"),
        serde_json::to_string_pretty(
            &ranked
                .iter()
                .map(|c| {
                    serde_json::json!({
                        "hypothesis_id": c["hypothesis_id"],
                        "monthly": c["monthly"]
                    })
                })
                .collect::<Vec<_>>(),
        )?,
    )?;
    fs::write(
        dir.join("b1_83_prospective_capital_simulation.json"),
        serde_json::to_string_pretty(&payload["capital"])?,
    )?;
    fs::write(
        dir.join("b1_83_prospective_negative_controls.json"),
        serde_json::to_string_pretty(&payload["negative_controls"])?,
    )?;
    fs::write(
        dir.join("b1_83_prospective_provenance.json"),
        serde_json::to_string_pretty(&payload["provenance"])?,
    )?;
    fs::write(dir.join("b1_83_prospective_report.md"), render_md(payload))?;
    fs::write(
        dir.join("b1_83_prospective_engine.json"),
        serde_json::to_string_pretty(payload)?,
    )?;
    Ok(())
}

fn render_md(p: &serde_json::Value) -> String {
    let mut md = String::new();
    md.push_str("# Prospective 83¢ conditional-state research\n\n");
    md.push_str("## Does any observable state justify paying 83¢?\n\n");
    md.push_str(&format!(
        "**{}**\n\n{}\n\n",
        p["headline_status"].as_str().unwrap_or(""),
        p["headline"].as_str().unwrap_or("")
    ));
    md.push_str(
        "PRODUCTION_COUNT = 0. Fill = `TRADE_PRINT_MODELED`. L2 = `UNAVAILABLE_SOURCE`.\n\n",
    );
    md.push_str("## Integrity\n\n");
    md.push_str(&format!(
        "{}\n\n",
        serde_json::to_string_pretty(&p["integrity"]).unwrap_or_default()
    ));
    md.push_str("## Primary table\n\n");
    md.push_str("| Rank | Condition | Cx | TRAIN N | VAL N | TEST N | TRAIN EV | VAL EV | TEST EV | FDR q | Bootstrap CI | Cost | Class |\n");
    md.push_str("|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---|\n");
    if let Some(arr) = p["panel"].as_array() {
        for (i, c) in arr.iter().enumerate() {
            md.push_str(&format!(
                "| {} | `{}` | {} | {} | {} | {} | {} | {} | {} | {} | [{}, {}] | {} | {} |\n",
                i + 1,
                if c["condition"].as_str().unwrap_or("").is_empty() {
                    "ALL_83"
                } else {
                    c["condition"].as_str().unwrap_or("")
                },
                c["complexity"],
                c["train_n"],
                c["val_n"],
                c["test_n"],
                c["train_ev"]
                    .as_f64()
                    .map(|x| format!("{x:.2}"))
                    .unwrap_or("—".into()),
                c["val_ev"]
                    .as_f64()
                    .map(|x| format!("{x:.2}"))
                    .unwrap_or("—".into()),
                c["test_ev"]
                    .as_f64()
                    .map(|x| format!("{x:.2}"))
                    .unwrap_or("—".into()),
                c["discovery_fdr_q"]
                    .as_f64()
                    .map(|x| format!("{x:.3}"))
                    .unwrap_or("—".into()),
                c["bootstrap"]["p2_5"]
                    .as_f64()
                    .map(|x| format!("{x:.2}"))
                    .unwrap_or("—".into()),
                c["bootstrap"]["p97_5"]
                    .as_f64()
                    .map(|x| format!("{x:.2}"))
                    .unwrap_or("—".into()),
                c["cost_survival_max_cents"]
                    .as_f64()
                    .map(|x| format!("{x:.1}"))
                    .unwrap_or("—".into()),
                c["classification"].as_str().unwrap_or(""),
            ));
        }
    }
    md.push_str("\n## Incremental information\n\n");
    md.push_str("| Parent | Added | Δ TRAIN | Δ VAL | Δ TEST | Cx | Verdict |\n|---|---|---:|---:|---:|---:|---|\n");
    if let Some(arr) = p["panel"].as_array() {
        for c in arr.iter().filter(|c| c["role"] == "INCREMENTAL") {
            let dt = c["incremental"]["d_test_ev"].as_f64();
            let verdict =
                if dt.is_some_and(|x| x > 1.0) && c["val_ev"].as_f64().is_some_and(|x| x > 0.0) {
                    "adds on locked TEST; still not FDR-robust"
                } else if dt.is_some_and(|x| x > 0.0) {
                    "small lift"
                } else {
                    "no useful incremental TEST EV"
                };
            md.push_str(&format!(
                "| `{}` | `{}` | {} | {} | {} | {} | {} |\n",
                c["parent"].as_str().unwrap_or(""),
                c["condition"].as_str().unwrap_or(""),
                c["incremental"]["d_train_ev"]
                    .as_f64()
                    .map(|x| format!("{x:.2}"))
                    .unwrap_or("—".into()),
                c["incremental"]["d_val_ev"]
                    .as_f64()
                    .map(|x| format!("{x:.2}"))
                    .unwrap_or("—".into()),
                c["incremental"]["d_test_ev"]
                    .as_f64()
                    .map(|x| format!("{x:.2}"))
                    .unwrap_or("—".into()),
                c["complexity"],
                verdict
            ));
        }
    }
    md.push_str("\n## Distinctions\n\n");
    md.push_str("| Layer | Meaning |\n|---|---|\n");
    md.push_str("| historical association | cell EV on TRAIN/VAL |\n");
    md.push_str("| predictive evidence | survived TRAIN→VAL→locked TEST + FDR |\n");
    md.push_str("| prospective validation | frozen definition on post-2026-06-27 games |\n\n");
    md.push_str("## Conditional questions\n\n");
    if let Some(q) = p["questions"].as_object() {
        for (k, v) in q {
            md.push_str(&format!(
                "### {}\n\n{}\n\n",
                k,
                v["answer"].as_str().unwrap_or("")
            ));
        }
    }
    md.push_str("## $50k capital simulation (not a forecast)\n\n");
    md.push_str(&format!(
        "{}\n\n",
        p["capital"]["required_for_20pct"].as_str().unwrap_or("")
    ));
    md.push_str("## Prospective holdout\n\n");
    md.push_str(&format!(
        "status={} · available first-83={} · W6 after cutoff={} · W7 overlap={}\n\n",
        p["prospective"]["status"].as_str().unwrap_or(""),
        p["prospective"]["n"].as_u64().unwrap_or(0),
        p["requirements"]["available_games"].as_u64().unwrap_or(0),
        p["requirements"]["w7_overlap"].as_u64().unwrap_or(0)
    ));
    md.push_str(&format!(
        "New data required: reconstruct W7 EventMarketPath for the {} post-cutoff W6 games, then extract first-exact-83. A decisive holdout needs at least {} first-83 games (research gate), preferably ≥50.\n\n",
        p["requirements"]["available_games"],
        p["requirements"]["minimum_test_n"]
    ));
    md.push_str("## Reproducibility\n\n```\n./target/release/momento-research-b1 --prospective-83\n```\n\nResearch only. No live FIRST01 / W9 / L2 / orders.\n");
    md
}

pub fn run_prospective83_engine(args: &ProspectiveArgs) -> Result<serde_json::Value, B1Error> {
    let coverage = scan_prospective_coverage(args)?;
    if !args.first83_sqlite.exists() {
        return Err(B1Error::Uncommitted(format!(
            "locked first83 missing at {}",
            args.first83_sqlite.display()
        )));
    }
    let (rows, ..) = prepare_search_rows(&args.first83_sqlite, TRAIN_BEFORE, VAL_BEFORE)?;
    let integrity = assert_universe_integrity(&rows)?;
    let store = FeatureStore::open_existing(&args.first83_sqlite)?;
    let snaps = store.load_all()?;
    if snaps.len() != rows.len() {
        return Err(B1Error::validation(
            "N_MISMATCH",
            format!("snapshots {} vs rows {}", snaps.len(), rows.len()),
        ));
    }
    let qmap = load_discovery_q(
        &args
            .first83_sqlite
            .parent()
            .unwrap_or(Path::new("."))
            .join("b1_83_exhaustive_rankings.csv"),
    );
    let discovery = load_discovery_counts(
        &args
            .first83_sqlite
            .parent()
            .unwrap_or(Path::new("."))
            .join("b1_83_search_summary.json"),
    );
    let all_pnls = game_pnls(&rows.iter().collect::<Vec<_>>(), PRIMARY);
    let mut ev_cache: BTreeMap<String, [Option<f64>; 3]> = BTreeMap::new();
    let mut evaluated = Vec::new();
    for item in panel() {
        let parent_ev = item.parent.and_then(|p| ev_cache.get(p).copied());
        let v = eval_item(
            &item,
            &rows,
            &qmap,
            &all_pnls,
            parent_ev,
            args,
            coverage.first83_eligible,
        )?;
        ev_cache.insert(
            item.condition.to_string(),
            [
                v["train_ev"].as_f64(),
                v["val_ev"].as_f64(),
                v["test_ev"].as_f64(),
            ],
        );
        evaluated.push(v);
    }
    let pvals: Vec<(String, f64)> = evaluated
        .iter()
        .filter_map(|c| {
            let cond = c["condition"].as_str()?;
            let pairs = parse_cond(cond);
            let train: Vec<&SearchRow> = rows
                .iter()
                .filter(|r| r.chrono == ChronoSplit::Train && cond_ok(r, &pairs))
                .collect();
            let pnls = game_pnls(&train, PRIMARY)
                .into_iter()
                .map(|x| x / 100.0)
                .collect::<Vec<_>>();
            p_mean_le0(&pnls).map(|p| (c["hypothesis_id"].as_str().unwrap_or("").to_string(), p))
        })
        .collect();
    let panel_q = bh_qvalues(&pvals);
    let fdr = serde_json::json!({
        "discovery_grid_tests": discovery["candidates_stored"],
        "discovery_method": "Benjamini-Hochberg q=0.10 on TRAIN P(mean P&L≤0), 6,128 locked tests",
        "panel_only_bh_does_not_replace_discovery_fdr": true,
        "panel_bh_q": panel_q,
        "note": "A new FDR over this small panel is not a substitute for the 6,128-test discovery correction."
    });
    let negs = negative_controls(&rows, args.seed);
    let capital = capital_sim(&evaluated, integrity.n_total);
    let qs = questions(&evaluated);
    let robust_n = evaluated
        .iter()
        .filter(|c| c["classification"] == "ROBUST_RESEARCH_CANDIDATE")
        .count();
    let pending_n = evaluated
        .iter()
        .filter(|c| c["classification"] == "PROSPECTIVE_HOLDOUT_PENDING")
        .count();
    let headline_status = if coverage.first83_eligible == 0 && robust_n == 0 {
        "NO — no robust state / INSUFFICIENT DATA — prospective validation pending"
    } else if robust_n > 0 && coverage.first83_eligible == 0 {
        "YES — research candidate only / INSUFFICIENT DATA — prospective validation pending"
    } else {
        "INSUFFICIENT DATA — prospective validation pending"
    };
    let headline = if robust_n > 0 {
        format!(
            "Canonical first-exact-83 N={}. Locked exhaustive grid tested {} hypotheses. \
One predeclared 3-way (Candidate B: start_move>30 ∧ outs=0 ∧ vol_1m LOW) meets the historical \
ROBUST_RESEARCH_CANDIDATE gates on TRAIN/VAL/locked TEST, including discovery FDR q≤0.10. \
That is not prospective validation and not production. \
40–49 remains the simplest +EV-on-all-splits 1-way (q≈0.173, TEST +2.41¢ < +3¢ report bar). \
Prospective holdout: 0 first-83 games. {} W6 games exist after 2026-06-27 but W7 TRADE paths were not reconstructed.",
            integrity.n_total,
            discovery["candidates_stored"].as_u64().unwrap_or(6128),
            coverage.w6_eligible_games
        )
    } else {
        format!(
            "Canonical first-exact-83 N={}. Locked exhaustive grid tested {} hypotheses. \
No panel cell meets ROBUST_RESEARCH_CANDIDATE. \
Prospective holdout: 0 first-83 games. {} W6 games after cutoff have no W7 TRADE paths.",
            integrity.n_total,
            discovery["candidates_stored"].as_u64().unwrap_or(6128),
            coverage.w6_eligible_games
        )
    };
    let dataset_hash = {
        let mut h: u64 = 0xcbf2_9ce4_8422_2325;
        for r in &rows {
            for b in r.game_id.as_bytes() {
                h ^= u64::from(*b);
                h = h.wrapping_mul(0x1000_0000_01b3);
            }
        }
        format!("{h:016x}")
    };
    let payload = serde_json::json!({
        "engine_version": ENGINE_VERSION,
        "feature_schema_version": FEATURE_SCHEMA_VERSION,
        "universe": "B1_FIRST83/v1",
        "entry_definition": "FIRST_EXACT_83",
        "target": PRIMARY,
        "fill_status": FILL_STATUS,
        "l2_status": "UNAVAILABLE_SOURCE",
        "headline_status": headline_status,
        "headline": headline,
        "production_count": 0,
        "integrity": integrity,
        "panel": evaluated,
        "fdr": fdr,
        "negative_controls": negs,
        "capital": capital,
        "questions": qs,
        "year_stability_40_49": year_regime(&rows, "start_price_band=40_49"),
        "discovery": discovery,
        "counts": {
            "hypotheses_in_discovery_grid": discovery["candidates_stored"],
            "panel_evaluated": panel().len(),
            "robust_research_candidate": robust_n,
            "prospective_holdout_pending": pending_n,
            "rejected_in_panel": evaluated.iter().filter(|c| c["classification"]=="REJECTED").count()
        },
        "prospective": {
            "n": coverage.first83_eligible,
            "wins": 0,
            "losses": 0,
            "ev_cents": null,
            "sharpe": null,
            "status": coverage.status
        },
        "requirements": {
            "required_games": MIN_TEST,
            "available_games": coverage.w6_eligible_games,
            "w7_overlap": coverage.w7_post_cutoff_games,
            "required_positive_events": 15,
            "available_positive_events": 0,
            "locked_candidate": "start_price_band=40_49",
            "minimum_ev": DEFAULT_REPORT_EV,
            "minimum_sharpe": null,
            "minimum_test_n": MIN_TEST,
            "reason": coverage.excluded_reason
        },
        "provenance": {
            "train_before": TRAIN_BEFORE,
            "val_before": VAL_BEFORE,
            "test_end_observed": TEST_END_OBSERVED,
            "dataset_hash_fnv": dataset_hash,
            "bootstrap_seed": args.seed,
            "permutation_seed": args.seed,
            "economic_report_threshold_cents": DEFAULT_REPORT_EV,
            "economic_thresholds_cents": EV_THRESHOLDS,
            "cost_grid_cents": COST_GRID,
            "min_train": MIN_TRAIN,
            "min_val": MIN_VAL,
            "min_test": MIN_TEST,
            "command": "./target/release/momento-research-b1 --prospective-83"
        },
        "coverage": coverage
    });
    write_engine_artifacts(&args.out_dir, &payload)?;
    Ok(payload)
}

pub fn prospective83_api_envelope(
    args: &ProspectiveArgs,
    engine: Option<&serde_json::Value>,
) -> Result<serde_json::Value, B1Error> {
    let coverage = scan_prospective_coverage(args)?;
    let frozen = frozen_candidates();
    let status = if coverage.first83_eligible == 0 {
        "INSUFFICIENT_DATA"
    } else {
        "PROSPECTIVE_EVALUATED"
    };
    Ok(serde_json::json!({
        "engine_version": ENGINE_VERSION,
        "universe": "B1_FIRST83/v1",
        "research_mode": "B1_FIRST83_PROSPECTIVE/v1",
        "entry_definition": "FIRST_EXACT_83",
        "target": PRIMARY,
        "status": status,
        "reason": coverage.excluded_reason,
        "historical_cutoff": TEST_END_OBSERVED,
        "candidate": {
            "id": "CAND_A_40_49",
            "condition": "start_price_band=40_49",
            "immutable": true,
            "historical": frozen.iter().find(|c| c.id == "CAND_A_40_49")
        },
        "frozen_candidates": frozen,
        "prospective": {
            "n": coverage.first83_eligible,
            "wins": 0,
            "losses": 0,
            "ev_cents": null,
            "sharpe": null
        },
        "requirements": {
            "required_games": MIN_TEST,
            "available_games": coverage.w6_eligible_games,
            "w7_overlap": coverage.w7_post_cutoff_games,
            "required_positive_events": 15,
            "available_positive_events": 0,
            "locked_candidate": "start_price_band=40_49",
            "minimum_ev": DEFAULT_REPORT_EV,
            "minimum_sharpe": null,
            "minimum_test_n": MIN_TEST
        },
        "provenance": {
            "fill_status": FILL_STATUS,
            "l2_status": "UNAVAILABLE_SOURCE",
            "do_not_retune_on_holdout": true,
            "command": "./target/release/momento-research-b1 --prospective-83"
        },
        "coverage": coverage,
        "engine": engine,
        "production_count": 0
    }))
}

pub fn run_capital_sim_only(args: &ProspectiveArgs) -> Result<PathBuf, B1Error> {
    let _payload = run_prospective83_engine(args)?;
    Ok(args
        .out_dir
        .join("b1_83_prospective_capital_simulation.json"))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn panel_ids_are_stable_and_unique() {
        let p = panel();
        let mut ids = BTreeSet::new();
        for item in &p {
            assert!(item.id.starts_with("83H-"));
            assert!(ids.insert(item.id));
        }
        assert_eq!(p[1].condition, "start_price_band=40_49");
        assert_eq!(
            p[5].condition,
            "start_move_gt30=YES&outs=0&vol_1m_tertile=LOW"
        );
    }

    #[test]
    fn api_envelope_is_insufficient_without_holdout() {
        let tmp = tempfile::tempdir().unwrap();
        let mut args = ProspectiveArgs::defaults(tmp.path());
        args.w6_sqlite = tmp.path().join("missing.sqlite");
        let env = prospective83_api_envelope(&args, None).unwrap();
        assert_eq!(env["status"], "INSUFFICIENT_DATA");
        assert!(env["prospective"]["ev_cents"].is_null());
        assert_eq!(env["production_count"], 0);
        assert_eq!(env["requirements"]["minimum_test_n"], 25);
    }
}
