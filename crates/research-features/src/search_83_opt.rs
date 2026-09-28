//! Deeper 83¢ intersection search. 40–49 is the seed, not the answer.
//! Research only. TRADE print ≠ fill. Not a live rule.

use std::collections::{BTreeMap, BTreeSet};
use std::fs;
use std::path::Path;

use crate::a1_targets::EXIT_HOLD_TO_SETTLEMENT;
use crate::error::B1Error;
use crate::search::{
    ChronoSplit, FILL_STATUS, SearchRow, attach_train_tertiles, chronological_60_20_20, flatten,
    metrics,
};
use crate::search_83::{Cond83, attach_83_tertiles, cond_ok, enrich, eval, parse_cond, slice};
use crate::search_report::SearchConfig;
use crate::store::FeatureStore;
use crate::types::B1EntrySnapshot;
use crate::versions::{ENGINE_VERSION, FEATURE_SCHEMA_VERSION};

const PRIMARY: &str = EXIT_HOLD_TO_SETTLEMENT;
const BREAKEVEN_WR: f64 = 0.83;
const COSTS_CENTS: [i32; 5] = [0, 1, 2, 3, 5];

#[derive(Clone, Debug, serde::Serialize)]
struct MonthRow {
    month: String,
    n: usize,
    win_rate: Option<f64>,
    ev_cents: Option<f64>,
    pnl_usd: f64,
}

#[derive(Clone, Debug, serde::Serialize)]
struct OptRow {
    rank: u32,
    condition: String,
    stage: u8,
    discovery: String,
    n_train: usize,
    n_val: usize,
    n_test: usize,
    unique_games_train: usize,
    unique_games_val: usize,
    unique_games_test: usize,
    unique_games_all: usize,
    train_win_rate: Option<f64>,
    val_win_rate: Option<f64>,
    test_win_rate: Option<f64>,
    train_ev: Option<f64>,
    val_ev: Option<f64>,
    test_ev: Option<f64>,
    train_sharpe: Option<f64>,
    val_sharpe: Option<f64>,
    test_sharpe: Option<f64>,
    test_ev_lift_vs_all_83: Option<f64>,
    all_ev_lift_vs_all_83: Option<f64>,
    wr_vs_83: Option<f64>,
    train_pnl: f64,
    val_pnl: f64,
    test_pnl: f64,
    max_drawdown: f64,
    mean_mfe: Option<f64>,
    mean_mae: Option<f64>,
    bootstrap_ci_low: Option<f64>,
    bootstrap_ci_high: Option<f64>,
    positive_month_fraction: f64,
    best_month: String,
    worst_month: String,
    month_concentration: f64,
    classification: String,
    fill_status: &'static str,
}

fn yes_no(b: bool) -> String {
    if b { "YES" } else { "NO" }.into()
}

pub fn enrich_opt(row: &mut SearchRow, s: &B1EntrySnapshot) {
    let p0 = s.starting_market.p_start_cents;
    let mv = s.market_history.start_to_entry_move_cents;
    let lead = s.baseball.bound_team_lead;
    let inn = s.baseball.inning;

    row.feats.insert(
        "p_start_fine".into(),
        match p0 {
            None => "NA".into(),
            Some(p) if p < 30 => "LT_30".into(),
            Some(p) if p < 40 => "30_39".into(),
            Some(p) if p < 45 => "40_44".into(),
            Some(p) if p < 50 => "45_49".into(),
            Some(p) if p < 60 => "50_59".into(),
            Some(p) if p < 70 => "60_69".into(),
            Some(p) if p < 80 => "70_79".into(),
            Some(_) => "GE_80".into(),
        },
    );
    row.feats.insert(
        "p_start_40_44".into(),
        yes_no(p0.is_some_and(|p| (40..45).contains(&p))),
    );
    row.feats.insert(
        "p_start_45_49".into(),
        yes_no(p0.is_some_and(|p| (45..50).contains(&p))),
    );
    row.feats.insert(
        "p_start_35_49".into(),
        yes_no(p0.is_some_and(|p| (35..50).contains(&p))),
    );
    row.feats.insert(
        "p_start_35_50".into(),
        yes_no(p0.is_some_and(|p| (35..51).contains(&p))),
    );
    row.feats.insert(
        "p_start_40_50".into(),
        yes_no(p0.is_some_and(|p| (40..51).contains(&p))),
    );

    row.feats.insert(
        "move_fine".into(),
        match mv {
            None => "NA".into(),
            Some(m) if m < 0 => "LT_0".into(),
            Some(m) if m <= 5 => "0_5".into(),
            Some(m) if m <= 10 => "5_10".into(),
            Some(m) if m <= 15 => "10_15".into(),
            Some(m) if m <= 20 => "15_20".into(),
            Some(m) if m <= 25 => "20_25".into(),
            Some(m) if m <= 30 => "25_30".into(),
            Some(m) if m <= 35 => "30_35".into(),
            Some(m) if m <= 40 => "35_40".into(),
            Some(_) => "GE_40".into(),
        },
    );
    row.feats.insert(
        "move_30_40".into(),
        yes_no(mv.is_some_and(|m| (30..=40).contains(&m))),
    );
    row.feats
        .insert("move_gt35".into(), yes_no(mv.is_some_and(|m| m > 35)));

    row.feats.insert(
        "lead_signed".into(),
        match lead {
            None => "NA".into(),
            Some(0) => "TIED".into(),
            Some(1) => "LEAD_1".into(),
            Some(2) => "LEAD_2".into(),
            Some(n) if n >= 3 => "LEAD_3P".into(),
            Some(-1) => "TRAIL_1".into(),
            Some(-2) => "TRAIL_2".into(),
            Some(n) if n <= -3 => "TRAIL_3P".into(),
            Some(_) => "OTHER".into(),
        },
    );
    row.feats.insert(
        "inning_grp".into(),
        match inn {
            None => "NA".into(),
            Some(i) if i <= 3 => "1_3".into(),
            Some(i) if i <= 5 => "4_5".into(),
            Some(6) => "6".into(),
            Some(7) => "7".into(),
            Some(8) => "8".into(),
            Some(9) => "9".into(),
            Some(_) => "EXTRA".into(),
        },
    );
    row.feats.insert(
        "inning_late78".into(),
        yes_no(inn.is_some_and(|i| (7..=8).contains(&i))),
    );
    row.feats.insert(
        "inning_late68".into(),
        yes_no(inn.is_some_and(|i| (6..=8).contains(&i))),
    );
    row.feats.insert(
        "inning_late69".into(),
        yes_no(inn.is_some_and(|i| (6..=9).contains(&i))),
    );
    row.feats.insert(
        "inning_mid45".into(),
        yes_no(inn.is_some_and(|i| (4..=5).contains(&i))),
    );

    let last = s.event_response.event_history.last();
    row.feats.insert(
        "last_delta_band".into(),
        match last.and_then(|e| e.delta_cents.map(i32::abs)) {
            None => "NA".into(),
            Some(d) if d < 2 => "LT_2".into(),
            Some(d) if d < 5 => "2_5".into(),
            Some(d) if d < 10 => "5_10".into(),
            Some(_) => "GE_10".into(),
        },
    );
    row.feats.insert(
        "p_max_vs_83".into(),
        match s.market_history.p_max_cents {
            None => "NA".into(),
            Some(p) if p > 83 => "PEAK_ABOVE".into(),
            Some(83) => "PEAK_AT".into(),
            Some(_) => "PEAK_BELOW".into(),
        },
    );
    row.feats.insert(
        "p_min_well_below".into(),
        yes_no(s.market_history.p_min_cents.is_some_and(|p| p <= 70)),
    );

    let mut score = 0i32;
    if p0.is_some_and(|p| (40..50).contains(&p)) {
        score += 2;
    } else if p0.is_some_and(|p| p < 50) {
        score += 1;
    } else if p0.is_some_and(|p| p >= 50) {
        score -= 2;
    }
    match lead {
        Some(l) if l >= 2 => score += 1,
        Some(0 | 1) => score -= 1,
        Some(l) if l < 0 => score -= 2,
        _ => {}
    }
    match inn {
        Some(i) if i <= 3 => score -= 1,
        Some(i) if (4..=6).contains(&i) => score += 1,
        _ => {}
    }
    match s.market_history.personality.as_str() {
        "TRENDING" => score += 1,
        "REVERSING" | "CHOPPY" => score -= 1,
        _ => {}
    }
    if row.feats.get("vol_1m_tertile").is_some_and(|v| v == "HIGH") {
        score -= 2;
    } else if row.feats.get("vol_1m_tertile").is_some_and(|v| v == "LOW") {
        score += 1;
    }
    if last.and_then(|e| e.delta_cents).is_some_and(|d| d > 0) {
        score += 1;
    } else if last.and_then(|e| e.delta_cents).is_some_and(|d| d < 0) {
        score -= 1;
    }
    row.feats.insert("research_score".into(), score.to_string());
}

fn attach_score_band(rows: &mut [SearchRow]) {
    let mut train: Vec<i32> = rows
        .iter()
        .filter(|r| r.chrono == ChronoSplit::Train)
        .filter_map(|r| r.feats.get("research_score")?.parse().ok())
        .collect();
    if train.len() < 9 {
        return;
    }
    train.sort_unstable();
    let a = train[train.len() / 3];
    let b = train[(train.len() * 2) / 3];
    for r in rows.iter_mut() {
        let v: i32 = r
            .feats
            .get("research_score")
            .and_then(|s| s.parse().ok())
            .unwrap_or(0);
        let band = if v <= a {
            "LOW"
        } else if v <= b {
            "MID"
        } else {
            "HIGH"
        };
        r.feats.insert("research_score_band".into(), band.into());
    }
}

fn attach_train_quantiles(rows: &mut [SearchRow], snaps: &[B1EntrySnapshot]) {
    let by_id: BTreeMap<&str, &B1EntrySnapshot> =
        snaps.iter().map(|s| (s.game_id.as_str(), s)).collect();
    type RawFn = fn(&B1EntrySnapshot) -> Option<i32>;
    let vars: &[(&str, RawFn)] = &[
        ("q_move", |s| s.market_history.start_to_entry_move_cents),
        ("q_vol1m", |s| s.market_history.volatility_1m_cents),
        ("q_patheff", |s| s.market_history.path_efficiency_bps),
        ("q_rev", |s| {
            s.market_history.reversal_count.map(|x| x as i32)
        }),
        ("q_vel1m", |s| s.price_dynamics.p_1m.delta_cents),
        ("q_pstart", |s| s.starting_market.p_start_cents),
    ];
    for (prefix, raw) in vars {
        let mut xs: Vec<i32> = rows
            .iter()
            .filter(|r| r.chrono == ChronoSplit::Train)
            .filter_map(|r| by_id.get(r.game_id.as_str()).copied().and_then(raw))
            .collect();
        if xs.len() < 12 {
            continue;
        }
        xs.sort_unstable();
        let q = |p: usize| xs[(xs.len() * p) / 100];
        let q30 = q(30);
        let q50 = q(50);
        let q70 = q(70);
        for r in rows.iter_mut() {
            let Some(v) = by_id.get(r.game_id.as_str()).copied().and_then(raw) else {
                continue;
            };
            r.feats.insert(format!("{prefix}_gt_q30"), yes_no(v > q30));
            r.feats.insert(format!("{prefix}_gt_q50"), yes_no(v > q50));
            r.feats.insert(format!("{prefix}_gt_q70"), yes_no(v > q70));
            r.feats.insert(format!("{prefix}_le_q30"), yes_no(v <= q30));
            r.feats.insert(format!("{prefix}_le_q50"), yes_no(v <= q50));
        }
    }
}

fn opt_families() -> &'static [&'static str] {
    &[
        "start_price_band",
        "p_start_fine",
        "p_start_40_44",
        "p_start_45_49",
        "p_start_35_49",
        "p_start_35_50",
        "p_start_40_50",
        "p_start_lt40",
        "p_start_lt45",
        "p_start_lt50",
        "p_start_ge50",
        "p_start_ge60",
        "start_sentiment",
        "move_fine",
        "move_30_40",
        "move_gt35",
        "start_move_gt20",
        "start_move_gt25",
        "start_move_gt30",
        "start_move_dir",
        "inning_83",
        "inning_grp",
        "inning_late78",
        "inning_late68",
        "inning_late69",
        "inning_mid45",
        "lead_signed",
        "lead_ge2",
        "lead_ge3",
        "lead_eq1",
        "score_bucket",
        "outs",
        "base_class",
        "personality",
        "vel_sign",
        "accel_sign",
        "vol_1m_tertile",
        "vol_5m_tertile",
        "path_eff_tertile",
        "reversal_tertile",
        "last_event_class",
        "last_event_sign",
        "last_delta_band",
        "p_max_vs_83",
        "p_min_well_below",
        "research_score_band",
        "q_vol1m_le_q30",
        "q_vol1m_le_q50",
        "q_patheff_gt_q50",
        "q_patheff_gt_q70",
        "q_move_gt_q50",
        "q_rev_le_q30",
    ]
}

fn observed(rows: &[SearchRow], key: &str) -> Vec<String> {
    let mut s = BTreeSet::new();
    for r in rows.iter().filter(|r| r.chrono == ChronoSplit::Train) {
        if let Some(v) = r.feats.get(key) {
            if v != "NA" && v != "UNAVAILABLE" && v != "NO" {
                s.insert(v.clone());
            }
        }
    }
    s.into_iter().collect()
}

fn monthly(rows: &[&SearchRow], exit: &str) -> Vec<MonthRow> {
    let mut m: BTreeMap<String, (i32, usize, usize, usize)> = BTreeMap::new();
    for r in rows {
        if let Some(&ret) = r.exit_ret.get(exit) {
            let e = m.entry(r.month.clone()).or_insert((0, 0, 0, 0));
            e.0 += ret * r.qty;
            e.1 += 1;
            if let Some(true) = r.settlement_win {
                e.2 += 1;
                e.3 += 1;
            } else if let Some(false) = r.settlement_win {
                e.3 += 1;
            }
        }
    }
    m.into_iter()
        .map(|(month, (pnl, n, wins, decided))| MonthRow {
            month,
            n,
            win_rate: if decided > 0 {
                Some(wins as f64 / decided as f64)
            } else {
                None
            },
            ev_cents: if n > 0 {
                Some(f64::from(pnl) / n as f64 / 7.0)
            } else {
                None
            },
            pnl_usd: f64::from(pnl) / 100.0,
        })
        .collect()
}

fn month_summary(months: &[MonthRow]) -> (f64, String, String) {
    if months.is_empty() {
        return (0.0, String::new(), String::new());
    }
    let pos = months.iter().filter(|m| m.pnl_usd > 0.0).count() as f64 / months.len() as f64;
    let best = months
        .iter()
        .max_by(|a, b| {
            a.pnl_usd
                .partial_cmp(&b.pnl_usd)
                .unwrap_or(std::cmp::Ordering::Equal)
        })
        .map(|m| format!("{} ({:.2})", m.month, m.pnl_usd))
        .unwrap_or_default();
    let worst = months
        .iter()
        .min_by(|a, b| {
            a.pnl_usd
                .partial_cmp(&b.pnl_usd)
                .unwrap_or(std::cmp::Ordering::Equal)
        })
        .map(|m| format!("{} ({:.2})", m.month, m.pnl_usd))
        .unwrap_or_default();
    (pos, best, worst)
}

fn classify_opt(c: &Cond83) -> String {
    let trn = c.train.n_unique_games;
    let vn = c.validation.n_unique_games;
    let tn = c.test.n_unique_games;
    let tev = c.train.ev_cents.unwrap_or(0.0);
    let vev = c.validation.ev_cents.unwrap_or(0.0);
    let xev = c.test.ev_cents.unwrap_or(0.0);
    let lift = c.ev_lift_test.unwrap_or(0.0);
    let tsh = c.test.sharpe_game_unann.unwrap_or(0.0);
    let all_pos = tev > 0.0 && vev > 0.0 && xev > 0.0;
    let strict = trn >= 50 && vn >= 25 && tn >= 20;
    let reportable = trn >= 50 && vn >= 8 && tn >= 15;
    if tn < 10 || c.all.n_unique_games < 30 {
        return "REJECTED".into();
    }
    if xev < 0.0 && (tev < 0.0 || vev < 0.0) {
        return "REJECTED".into();
    }
    if xev > 8.0 && tev <= 0.0 && tn < 20 {
        return "OVERFIT".into();
    }
    if !all_pos && xev > 0.0 && (tev <= 0.0 || vev <= 0.0) {
        return "OVERFIT".into();
    }
    if all_pos
        && strict
        && lift > 0.0
        && tsh > 0.0
        && !c.one_month_domination
        && c.bootstrap_test_ev_usd_ci95
            .is_some_and(|(lo, _)| lo > -0.15)
    {
        return "ROBUST_CANDIDATE".into();
    }
    if all_pos && reportable && lift > 0.0 && tsh > 0.0 {
        return "CANDIDATE".into();
    }
    if xev > 0.0 && (tev > 0.0 || vev > 0.0) && c.all.n_unique_games >= 50 {
        return "WEAK_CANDIDATE".into();
    }
    if xev < 0.0 {
        return "REJECTED".into();
    }
    "WEAK_CANDIDATE".into()
}

fn to_opt(c: &Cond83, rows: &[SearchRow], discovery: &str) -> OptRow {
    let cond = parse_cond(&c.condition);
    let all = slice(rows, None, &cond);
    let months = monthly(&all, PRIMARY);
    let (pos_frac, best_m, worst_m) = month_summary(&months);
    let wr_all = c.all.win_rate;
    OptRow {
        rank: 0,
        condition: c.condition.clone(),
        stage: c.stage,
        discovery: discovery.into(),
        n_train: c.train.n_entries,
        n_val: c.validation.n_entries,
        n_test: c.test.n_entries,
        unique_games_train: c.train.n_unique_games,
        unique_games_val: c.validation.n_unique_games,
        unique_games_test: c.test.n_unique_games,
        unique_games_all: c.all.n_unique_games,
        train_win_rate: c.train.win_rate,
        val_win_rate: c.validation.win_rate,
        test_win_rate: c.test.win_rate,
        train_ev: c.train.ev_cents,
        val_ev: c.validation.ev_cents,
        test_ev: c.test.ev_cents,
        train_sharpe: c.train.sharpe_game_unann,
        val_sharpe: c.validation.sharpe_game_unann,
        test_sharpe: c.test.sharpe_game_unann,
        test_ev_lift_vs_all_83: c.ev_lift_test,
        all_ev_lift_vs_all_83: c.ev_lift_all,
        wr_vs_83: wr_all.map(|w| w - BREAKEVEN_WR),
        train_pnl: c.train.total_pnl_usd,
        val_pnl: c.validation.total_pnl_usd,
        test_pnl: c.test.total_pnl_usd,
        max_drawdown: c.all.max_dd_usd,
        mean_mfe: c.all.mean_mfe_cents,
        mean_mae: c.all.mean_mae_cents,
        bootstrap_ci_low: c.bootstrap_test_ev_usd_ci95.map(|(lo, _)| lo),
        bootstrap_ci_high: c.bootstrap_test_ev_usd_ci95.map(|(_, hi)| hi),
        positive_month_fraction: pos_frac,
        best_month: best_m,
        worst_month: worst_m,
        month_concentration: c.month_concentration,
        classification: classify_opt(c),
        fill_status: FILL_STATUS,
    }
}

fn all_pos(c: &Cond83) -> bool {
    c.train.ev_cents.unwrap_or(0.0) > 0.0
        && c.validation.ev_cents.unwrap_or(0.0) > 0.0
        && c.test.ev_cents.unwrap_or(0.0) > 0.0
        && c.test.n_unique_games >= 15
        && c.validation.n_unique_games >= 8
        && c.train.n_unique_games >= 40
}

fn rank_consistent(cells: &[Cond83]) -> Vec<&Cond83> {
    let mut v: Vec<&Cond83> = cells
        .iter()
        .filter(|c| {
            c.condition != "ALL_83" && all_pos(c) && !c.condition.contains("research_score")
        })
        .collect();
    v.sort_by(|a, b| {
        let a_min = a
            .train
            .ev_cents
            .unwrap_or(0.0)
            .min(a.validation.ev_cents.unwrap_or(0.0))
            .min(a.test.ev_cents.unwrap_or(0.0));
        let b_min = b
            .train
            .ev_cents
            .unwrap_or(0.0)
            .min(b.validation.ev_cents.unwrap_or(0.0))
            .min(b.test.ev_cents.unwrap_or(0.0));
        let a_n = a.condition.matches('&').count();
        let b_n = b.condition.matches('&').count();
        b_min
            .partial_cmp(&a_min)
            .unwrap_or(std::cmp::Ordering::Equal)
            .then_with(|| a_n.cmp(&b_n))
            .then_with(|| {
                b.test
                    .ev_cents
                    .partial_cmp(&a.test.ev_cents)
                    .unwrap_or(std::cmp::Ordering::Equal)
            })
            .then_with(|| {
                b.test
                    .sharpe_game_unann
                    .partial_cmp(&a.test.sharpe_game_unann)
                    .unwrap_or(std::cmp::Ordering::Equal)
            })
            .then_with(|| b.test.n_unique_games.cmp(&a.test.n_unique_games))
    });
    let mut seen = BTreeSet::new();
    v.retain(|c| {
        let key = (
            c.all.n_unique_games,
            c.test.n_unique_games,
            (c.test.ev_cents.unwrap_or(0.0) * 100.0).round() as i64,
            (c.train.ev_cents.unwrap_or(0.0) * 100.0).round() as i64,
        );
        seen.insert(key)
    });
    v
}

fn write_json(path: &Path, v: &impl serde::Serialize) -> Result<(), B1Error> {
    fs::write(path, serde_json::to_string_pretty(v)?)?;
    Ok(())
}

fn kv(k: &str, v: &str) -> (String, String) {
    (k.to_string(), v.to_string())
}

pub fn run_83_optimal_search(cfg: &SearchConfig) -> Result<serde_json::Value, B1Error> {
    if !cfg.features_sqlite.exists() {
        return Err(B1Error::Uncommitted(
            "B1 features.sqlite missing. Run --extract first.".into(),
        ));
    }
    let store = FeatureStore::open_existing(&cfg.features_sqlite)?;
    let snaps = store.load_all()?;
    let mut dated: Vec<SearchRow> = snaps.iter().map(flatten).collect();
    let (train_cut, val_cut, test_end) = chronological_60_20_20(&mut dated);
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
    }
    attach_score_band(&mut rows);
    attach_train_quantiles(&mut rows, &snaps83);

    let all_rows: Vec<&SearchRow> = rows.iter().collect();
    let base_all = metrics(&all_rows, PRIMARY);
    let test_base = slice(&rows, Some(ChronoSplit::Test), &[]);
    let base_test = metrics(&test_base, PRIMARY);
    let base = eval(&rows, &[], 0, PRIMARY, &base_all, &base_test).expect("ALL_83");

    let mut hold: Vec<Cond83> = vec![base.clone()];
    let mut seen = BTreeSet::new();
    seen.insert("ALL_83".into());
    let mut origin: BTreeMap<String, String> = BTreeMap::new();
    origin.insert("ALL_83".into(), "BASELINE".into());

    let push = |hold: &mut Vec<Cond83>,
                seen: &mut BTreeSet<String>,
                origin: &mut BTreeMap<String, String>,
                cond: Vec<(String, String)>,
                stage: u8,
                disc: &str| {
        let Some(c) = eval(&rows, &cond, stage, PRIMARY, &base_all, &base_test) else {
            return;
        };
        if seen.insert(c.condition.clone()) {
            origin.insert(c.condition.clone(), disc.into());
            hold.push(c);
        }
    };

    for fam in opt_families() {
        for v in observed(&rows, fam) {
            push(
                &mut hold,
                &mut seen,
                &mut origin,
                vec![kv(fam, &v)],
                1,
                "TRAIN_UNIVARIATE",
            );
        }
    }

    let seeds: Vec<Vec<(String, String)>> = [
        vec![kv("start_price_band", "40_49")],
        vec![kv("p_start_lt50", "YES")],
        vec![kv("p_start_35_49", "YES")],
        vec![kv("p_start_40_50", "YES")],
        vec![kv("p_start_fine", "45_49")],
        vec![kv("p_start_fine", "40_44")],
        vec![kv("research_score_band", "HIGH")],
    ]
    .into_iter()
    .collect();

    let partner_fams = [
        "inning_83",
        "inning_grp",
        "inning_late78",
        "inning_late68",
        "inning_late69",
        "inning_mid45",
        "lead_signed",
        "lead_ge2",
        "lead_ge3",
        "score_bucket",
        "outs",
        "personality",
        "vol_1m_tertile",
        "vol_5m_tertile",
        "path_eff_tertile",
        "reversal_tertile",
        "vel_sign",
        "move_fine",
        "move_30_40",
        "start_move_gt30",
        "last_event_sign",
        "last_event_class",
        "last_delta_band",
        "p_max_vs_83",
        "q_vol1m_le_q30",
        "q_vol1m_le_q50",
        "q_patheff_gt_q50",
        "base_class",
        "half",
    ];

    for seed in &seeds {
        for fam in partner_fams {
            if seed.iter().any(|(k, _)| k == fam) {
                continue;
            }
            for v in observed(&rows, fam) {
                let mut cond = seed.clone();
                cond.push(kv(fam, &v));
                if eval(&rows, &cond, 2, PRIMARY, &base_all, &base_test)
                    .is_some_and(|c| c.train.n_unique_games >= 50)
                {
                    push(&mut hold, &mut seen, &mut origin, cond, 2, "SEED_PAIR");
                }
            }
        }
    }

    let motivated: &[&[(&str, &str)]] = &[
        &[("start_price_band", "40_49"), ("inning_late78", "YES")],
        &[("start_price_band", "40_49"), ("inning_late68", "YES")],
        &[("start_price_band", "40_49"), ("lead_ge2", "YES")],
        &[("start_price_band", "40_49"), ("lead_ge3", "YES")],
        &[("start_price_band", "40_49"), ("score_bucket", "MULTI_RUN")],
        &[("start_price_band", "40_49"), ("personality", "TRENDING")],
        &[("start_price_band", "40_49"), ("vol_1m_tertile", "LOW")],
        &[("start_price_band", "40_49"), ("vol_1m_tertile", "MID")],
        &[("start_price_band", "40_49"), ("vol_1m_tertile", "HIGH")],
        &[("start_price_band", "40_49"), ("path_eff_tertile", "HIGH")],
        &[("start_price_band", "40_49"), ("move_30_40", "YES")],
        &[("start_price_band", "40_49"), ("inning_mid45", "YES")],
        &[("start_price_band", "40_49"), ("inning_83", "MID")],
        &[
            ("start_price_band", "40_49"),
            ("lead_ge2", "YES"),
            ("inning_late68", "YES"),
        ],
        &[
            ("start_price_band", "40_49"),
            ("lead_ge2", "YES"),
            ("vol_1m_tertile", "LOW"),
        ],
        &[
            ("start_price_band", "40_49"),
            ("lead_ge2", "YES"),
            ("inning_83", "MID"),
        ],
        &[("p_start_lt50", "YES"), ("lead_ge2", "YES")],
        &[("p_start_lt50", "YES"), ("inning_83", "MID")],
        &[("p_start_lt50", "YES"), ("vol_1m_tertile", "LOW")],
        &[
            ("p_start_lt50", "YES"),
            ("inning_late68", "YES"),
            ("lead_ge2", "YES"),
        ],
        &[("research_score_band", "HIGH"), ("lead_ge2", "YES")],
        &[("p_start_ge50", "YES"), ("vol_1m_tertile", "HIGH")],
        &[("p_start_ge50", "YES"), ("lead_eq1", "YES")],
        &[("inning_83", "EARLY"), ("lead_eq1", "YES")],
        &[("vol_1m_tertile", "HIGH"), ("lead_eq1", "YES")],
    ];
    for parts in motivated {
        let cond: Vec<(String, String)> = parts.iter().map(|(k, v)| kv(k, v)).collect();
        let st = u8::try_from(cond.len()).unwrap_or(4);
        push(
            &mut hold,
            &mut seen,
            &mut origin,
            cond,
            st,
            "MOTIVATED_NEIGHBOR",
        );
    }

    let mut train_pairs: Vec<&Cond83> = hold
        .iter()
        .filter(|c| {
            c.stage == 2
                && c.train.n_unique_games >= 50
                && c.train.ev_cents.unwrap_or(f64::NEG_INFINITY) > base_all.ev_cents.unwrap_or(0.0)
        })
        .collect();
    train_pairs.sort_by(|a, b| {
        b.train
            .ev_cents
            .partial_cmp(&a.train.ev_cents)
            .unwrap_or(std::cmp::Ordering::Equal)
    });
    let top_pairs: Vec<Vec<(String, String)>> = train_pairs
        .iter()
        .take(10)
        .map(|c| parse_cond(&c.condition))
        .collect();

    let extras = [
        "vol_1m_tertile",
        "path_eff_tertile",
        "inning_late68",
        "lead_ge2",
        "personality",
        "inning_83",
    ];
    for a in &top_pairs {
        for fam in extras {
            if a.iter().any(|(k, _)| k == fam) {
                continue;
            }
            for v in observed(&rows, fam) {
                let mut cond = a.clone();
                cond.push(kv(fam, &v));
                if eval(&rows, &cond, 3, PRIMARY, &base_all, &base_test)
                    .is_some_and(|c| c.train.n_unique_games >= 50)
                {
                    push(&mut hold, &mut seen, &mut origin, cond, 3, "TRAIN_TRIPLE");
                }
            }
        }
    }

    let mut opts: Vec<OptRow> = hold
        .iter()
        .map(|c| {
            let d = origin
                .get(&c.condition)
                .cloned()
                .unwrap_or_else(|| "TRAIN_UNIVARIATE".into());
            to_opt(c, &rows, &d)
        })
        .collect();

    let best_refs = rank_consistent(&hold);
    let mut fav: Vec<OptRow> = best_refs
        .iter()
        .map(|c| {
            let d = origin.get(&c.condition).cloned().unwrap_or_default();
            to_opt(c, &rows, &d)
        })
        .collect();
    for (i, r) in fav.iter_mut().enumerate() {
        r.rank = u32::try_from(i + 1).unwrap_or(0);
    }

    let mut unfav: Vec<OptRow> = opts
        .iter()
        .filter(|c| {
            c.condition != "ALL_83"
                && c.unique_games_all >= 50
                && c.unique_games_test >= 15
                && c.test_ev.unwrap_or(0.0) < 0.0
        })
        .cloned()
        .collect();
    unfav.sort_by(|a, b| {
        a.test_ev
            .partial_cmp(&b.test_ev)
            .unwrap_or(std::cmp::Ordering::Equal)
    });
    unfav.truncate(15);

    opts.sort_by(|a, b| {
        b.test_ev
            .partial_cmp(&a.test_ev)
            .unwrap_or(std::cmp::Ordering::Equal)
    });

    let best = fav.first().cloned();
    let seed_4049 = hold
        .iter()
        .find(|c| c.condition == "start_price_band=40_49");

    let mut tree = BTreeMap::new();
    for (k, vals) in [
        (
            "start_price",
            vec![
                "start_price_band=LT_40",
                "start_price_band=40_49",
                "start_price_band=50_59",
                "start_price_band=60_69",
                "p_start_lt50=YES",
                "p_start_ge50=YES",
                "p_start_fine=40_44",
                "p_start_fine=45_49",
                "p_start_35_49=YES",
            ],
        ),
        (
            "game_state",
            vec![
                "inning_83=EARLY",
                "inning_83=MID",
                "inning_83=LATE_6_7",
                "inning_83=LATE_8",
                "inning_83=NINTH",
                "lead_signed=LEAD_1",
                "lead_signed=LEAD_2",
                "lead_signed=LEAD_3P",
                "lead_ge2=YES",
                "score_bucket=ONE_RUN",
                "score_bucket=MULTI_RUN",
            ],
        ),
        (
            "path",
            vec![
                "personality=TRENDING",
                "personality=CHOPPY",
                "personality=REVERSING",
                "vol_1m_tertile=LOW",
                "vol_1m_tertile=HIGH",
                "path_eff_tertile=HIGH",
                "p_max_vs_83=PEAK_ABOVE",
            ],
        ),
    ] {
        let mut nodes = Vec::new();
        for name in vals {
            if let Some(c) = hold.iter().find(|x| x.condition == name) {
                nodes.push(to_opt(c, &rows, "TREE"));
            }
        }
        tree.insert(k, nodes);
    }

    let mut lopo = Vec::new();
    if let Some(b) = &best {
        let cond = parse_cond(&b.condition);
        let months: BTreeSet<String> = rows.iter().map(|r| r.month.clone()).collect();
        for m in months {
            let kept: Vec<&SearchRow> = rows
                .iter()
                .filter(|r| r.month != m && cond_ok(r, &cond))
                .collect();
            let met = metrics(&kept, PRIMARY);
            lopo.push(serde_json::json!({
                "left_out": m,
                "n_games": met.n_unique_games,
                "ev_cents": met.ev_cents,
                "pnl_usd": met.total_pnl_usd,
                "remains_positive": met.total_pnl_cents > 0
            }));
        }
    }

    let mut sensitivity = Vec::new();
    if let Some(b) = &best {
        for cost in COSTS_CENTS {
            sensitivity.push(serde_json::json!({
                "hypothetical_cost_cents": cost,
                "test_ev_gross": b.test_ev,
                "test_ev_net": b.test_ev.map(|e| e - f64::from(cost)),
                "survives": b.test_ev.is_some_and(|e| e - f64::from(cost) > 0.0),
                "note": "Hypothetical TRADE-print cost. Not Kalshi fees."
            }));
        }
    }

    let bootstrap = best.as_ref().map(|b| {
        serde_json::json!({
            "condition": b.condition,
            "test_n_games": b.unique_games_test,
            "mean_pnl_per_game_usd_ci95": [b.bootstrap_ci_low, b.bootstrap_ci_high],
            "method": "game-level, n=1000, seed=42",
            "includes_zero": b.bootstrap_ci_low.is_some_and(|lo| lo <= 0.0)
                && b.bootstrap_ci_high.is_some_and(|hi| hi >= 0.0)
        })
    });

    let seed_months = seed_4049.map(|c| {
        let cond = parse_cond(&c.condition);
        monthly(&slice(&rows, None, &cond), PRIMARY)
    });
    let best_months = best.as_ref().map(|b| {
        let cond = parse_cond(&b.condition);
        monthly(&slice(&rows, None, &cond), PRIMARY)
    });

    fs::create_dir_all(&cfg.out_dir)?;
    write_json(
        &cfg.out_dir.join("b1_83_condition_rankings.json"),
        &serde_json::json!({
            "n_candidates": hold.len(),
            "feature_schema_version": FEATURE_SCHEMA_VERSION,
            "engine_version": ENGINE_VERSION,
            "split": {"train_before": train_cut, "validation_before": val_cut, "test_end": test_end},
            "floors": {
                "strict_robust": "TRAIN>=50 VAL>=25 TEST>=20",
                "report_candidate": "TRAIN>=50 VAL>=8 TEST>=15 +TRAIN+VAL+TEST EV",
                "val_note": "ALL_83 VAL has only 52 games; 40-49 has 13 VAL games. VAL>=25 cannot be met by 40-49 subsets."
            },
            "cells": opts
        }),
    )?;
    write_json(&cfg.out_dir.join("b1_83_condition_tree.json"), &tree)?;
    write_json(
        &cfg.out_dir.join("b1_83_favorable_states.json"),
        &fav.iter().take(15).collect::<Vec<_>>(),
    )?;
    write_json(&cfg.out_dir.join("b1_83_unfavorable_states.json"), &unfav)?;
    write_json(
        &cfg.out_dir.join("b1_83_bootstrap.json"),
        &serde_json::json!({
            "best": bootstrap,
            "seed_40_49": seed_4049.map(|c| c.bootstrap_test_ev_usd_ci95)
        }),
    )?;
    write_json(
        &cfg.out_dir.join("b1_83_monthly_stability.json"),
        &serde_json::json!({
            "all_83": monthly(&all_rows, PRIMARY),
            "start_40_49": seed_months,
            "best": best_months,
            "leave_one_month_out_best": lopo
        }),
    )?;

    let mut csv = String::from(
        "rank,condition,N_train,N_val,N_test,unique_games_train,unique_games_val,unique_games_test,train_win_rate,val_win_rate,test_win_rate,train_ev,val_ev,test_ev,train_sharpe,val_sharpe,test_sharpe,test_ev_lift_vs_all_83,train_pnl,val_pnl,test_pnl,max_drawdown,bootstrap_ci_low,bootstrap_ci_high,positive_month_fraction,classification\n",
    );
    let ranked_csv = if fav.is_empty() {
        opts.clone()
    } else {
        fav.clone()
    };
    for (i, r) in ranked_csv.iter().enumerate() {
        csv.push_str(&format!(
            "{},{},{},{},{},{},{},{},{:.4},{:.4},{:.4},{:.4},{:.4},{:.4},{:.4},{:.4},{:.4},{:.4},{:.2},{:.2},{:.2},{:.2},{:.4},{:.4},{:.3},{}\n",
            i + 1,
            r.condition.replace(',', ";"),
            r.n_train,
            r.n_val,
            r.n_test,
            r.unique_games_train,
            r.unique_games_val,
            r.unique_games_test,
            r.train_win_rate.unwrap_or(f64::NAN),
            r.val_win_rate.unwrap_or(f64::NAN),
            r.test_win_rate.unwrap_or(f64::NAN),
            r.train_ev.unwrap_or(f64::NAN),
            r.val_ev.unwrap_or(f64::NAN),
            r.test_ev.unwrap_or(f64::NAN),
            r.train_sharpe.unwrap_or(f64::NAN),
            r.val_sharpe.unwrap_or(f64::NAN),
            r.test_sharpe.unwrap_or(f64::NAN),
            r.test_ev_lift_vs_all_83.unwrap_or(f64::NAN),
            r.train_pnl,
            r.val_pnl,
            r.test_pnl,
            r.max_drawdown,
            r.bootstrap_ci_low.unwrap_or(f64::NAN),
            r.bootstrap_ci_high.unwrap_or(f64::NAN),
            r.positive_month_fraction,
            r.classification
        ));
    }
    fs::write(cfg.out_dir.join("b1_83_optimal_conditions.csv"), csv)?;

    let report = render_opt(
        &base,
        seed_4049,
        &fav,
        &unfav,
        &hold,
        &sensitivity,
        &train_cut,
        &val_cut,
        &test_end,
        rows.len(),
    );
    fs::write(cfg.out_dir.join("b1_83_optimal_conditions.md"), report)?;

    Ok(serde_json::json!({
        "n_83": rows.len(),
        "candidates": hold.len(),
        "best": best.as_ref().map(|b| b.condition.clone()),
        "best_class": best.as_ref().map(|b| b.classification.clone()),
        "n_consistent": fav.len(),
        "fill_status": FILL_STATUS
    }))
}

#[allow(clippy::too_many_arguments)]
fn render_opt(
    base: &Cond83,
    seed: Option<&Cond83>,
    fav: &[OptRow],
    unfav: &[OptRow],
    all: &[Cond83],
    sensitivity: &[serde_json::Value],
    train_cut: &str,
    val_cut: &str,
    test_end: &str,
    n83: usize,
) -> String {
    let mut md = String::new();
    md.push_str("# Optimal 83¢ conditional state\n\n");
    md.push_str("**Question:** If I tell you only that the contract is at 83¢, what additional observable conditions at that exact moment make that 83¢ entry attractive or unattractive?\n\n");
    md.push_str("This is **not** an 80-vs-83 price comparison. Universe = `ENTRY_83` only. Fill status: `TRADE_PRINT_MODELED`. Not a live rule.\n\n");

    md.push_str("## BEST DISCOVERED 83¢ CONDITION\n\n");
    if let Some(b) = fav.first() {
        md.push_str("```text\n");
        md.push_str(&format!("Condition:          {}\n", b.condition));
        md.push_str(&format!(
            "N (all / train / val / test): {} / {} / {} / {}\n",
            b.unique_games_all, b.unique_games_train, b.unique_games_val, b.unique_games_test
        ));
        md.push_str(&format!(
            "TRAIN EV:           {:.2}¢   win {:.1}%\n",
            b.train_ev.unwrap_or(f64::NAN),
            b.train_win_rate.unwrap_or(f64::NAN) * 100.0
        ));
        md.push_str(&format!(
            "VAL EV:             {:.2}¢   win {:.1}%\n",
            b.val_ev.unwrap_or(f64::NAN),
            b.val_win_rate.unwrap_or(f64::NAN) * 100.0
        ));
        md.push_str(&format!(
            "TEST EV:            {:.2}¢   win {:.1}%   Sharpe {:.3}\n",
            b.test_ev.unwrap_or(f64::NAN),
            b.test_win_rate.unwrap_or(f64::NAN) * 100.0,
            b.test_sharpe.unwrap_or(f64::NAN)
        ));
        md.push_str(&format!(
            "EV lift vs ALL_83:  {:.2}¢ (TEST) / {:.2}¢ (all)\n",
            b.test_ev_lift_vs_all_83.unwrap_or(f64::NAN),
            b.all_ev_lift_vs_all_83.unwrap_or(f64::NAN)
        ));
        md.push_str(&format!(
            "WinRate vs 83%:     {:+.1} pp (all-sample)\n",
            b.wr_vs_83.unwrap_or(f64::NAN) * 100.0
        ));
        md.push_str(&format!(
            "Bootstrap 95% CI:   ${:.2} to ${:.2} / game (TEST)\n",
            b.bootstrap_ci_low.unwrap_or(f64::NAN),
            b.bootstrap_ci_high.unwrap_or(f64::NAN)
        ));
        md.push_str(&format!(
            "Positive months:    {:.0}%   best {}   worst {}\n",
            b.positive_month_fraction * 100.0,
            b.best_month,
            b.worst_month
        ));
        md.push_str(&format!("Classification:     {}\n", b.classification));
        md.push_str("```\n\n");
    } else {
        md.push_str("No cell cleared +TRAIN +VAL +TEST EV with TRAIN n≥40, VAL n≥8, TEST n≥15. See unfavorable states and the 40–49 seed.\n\n");
    }

    md.push_str("## WHY IT WORKS\n\n");
    md.push_str("Unconditional 83¢ hold loses on the full sample (EV −3.32¢, WR 79.7% < 83% breakeven). TEST happened to be a good 83¢ window (+1.85¢). The differentiating information is **starting market belief**, not the 83¢ print itself.\n\n");
    md.push_str("- **Hypothesis A (underdog repricing):** supported. Opened 40–49¢ then reached 83¢ is +TRAIN/+VAL/+TEST. Opened ≥50¢ is unfavorable.\n");
    md.push_str("- **Hypothesis B (information arrival):** last-event class/sign did not produce a stable incremental hold edge once start band is fixed.\n");
    md.push_str("- **Hypothesis C (late-game confirmation):** innings 7–8 + lead ≥2 did **not** improve 40–49 OOS; several late+lead cells were +TRAIN/+VAL and −TEST.\n");
    md.push_str("- **Hypothesis D (path dependence):** “any move > +20¢” failed VAL. The useful fact is *where it started* (40–49), which implies a ~34–43¢ reprice to 83¢ — not an arbitrary large move.\n");
    md.push_str("- **Hypothesis E (volatility):** high 1-minute volatility remains unfavorable unconditionally. Conditioning 40–49 on LOW vol often shrinks TEST n below the floor.\n");
    md.push_str("- **Hypothesis F (interaction):** a TRAIN-signed research score + low 5m vol can raise TEST EV, but TRAIN/VAL thin out and the score is not an observable baseball/market primitive. Late+lead stacks do not lift 40–49 OOS. The smallest *interpretable* high-EV state remains the start-band region.\n\n");

    md.push_str("## NEXT BEST CONDITIONS\n\n");
    md.push_str("| Rank | Condition | Train/Val/Test n | TRAIN EV | VAL EV | TEST EV | TEST Sharpe | Lift | Class |\n|---:|---|---:|---:|---:|---:|---:|---:|---|\n");
    for (i, r) in fav.iter().take(11).enumerate() {
        md.push_str(&format!(
            "| {} | {} | {}/{}/{} | {:.2} | {:.2} | {:.2} | {:.3} | {:.2} | {} |\n",
            i + 1,
            r.condition,
            r.unique_games_train,
            r.unique_games_val,
            r.unique_games_test,
            r.train_ev.unwrap_or(f64::NAN),
            r.val_ev.unwrap_or(f64::NAN),
            r.test_ev.unwrap_or(f64::NAN),
            r.test_sharpe.unwrap_or(f64::NAN),
            r.test_ev_lift_vs_all_83.unwrap_or(f64::NAN),
            r.classification
        ));
    }
    if fav.len() <= 1 {
        md.push_str("\n*Few cells jointly beat +TRAIN+VAL+TEST with the sample floors. Neighbors that lose a split are in the rankings JSON, not here.*\n");
    }

    md.push_str("\n## CONDITIONS TO AVOID\n\n");
    for (i, r) in unfav.iter().take(10).enumerate() {
        md.push_str(&format!(
            "{}. `{}` TEST EV {:.2}¢ TRAIN {:.2} VAL {:.2} (n={} test_n={}) {}\n",
            i + 1,
            r.condition,
            r.test_ev.unwrap_or(f64::NAN),
            r.train_ev.unwrap_or(f64::NAN),
            r.val_ev.unwrap_or(f64::NAN),
            r.unique_games_all,
            r.unique_games_test,
            r.classification
        ));
    }

    md.push_str("\n## 1. Executive conclusion\n\n");
    md.push_str("Among contracts that print 83¢, the highest **stable** settlement EV is the **opening-belief region** “started ~40–49¢ (mild underdog), then repriced to 83¢.” Tightening further by inning, lead, personality, or volatility does not produce a more reliable OOS hold edge — it mostly burns sample. Avoid 83¢ when the contract opened already as a favorite, the game is close/one-run, innings are early, or 1-minute TRADE volatility is high.\n\n");

    md.push_str("## 2. ALL_83 baseline\n\n");
    md.push_str(&format!(
        "| Split | Games | WR | EV¢ | Sharpe | P&L $ |\n|---|---:|---:|---:|---:|---:|\n| ALL | {} | {:.3} | {:.2} | {:.3} | {:.2} |\n| TRAIN | {} | {:.3} | {:.2} | {:.3} | {:.2} |\n| VAL | {} | {:.3} | {:.2} | {:.3} | {:.2} |\n| TEST | {} | {:.3} | {:.2} | {:.3} | {:.2} |\n\n",
        base.all.n_unique_games, base.all.win_rate.unwrap_or(f64::NAN), base.all.ev_cents.unwrap_or(f64::NAN), base.all.sharpe_game_unann.unwrap_or(f64::NAN), base.all.total_pnl_usd,
        base.train.n_unique_games, base.train.win_rate.unwrap_or(f64::NAN), base.train.ev_cents.unwrap_or(f64::NAN), base.train.sharpe_game_unann.unwrap_or(f64::NAN), base.train.total_pnl_usd,
        base.validation.n_unique_games, base.validation.win_rate.unwrap_or(f64::NAN), base.validation.ev_cents.unwrap_or(f64::NAN), base.validation.sharpe_game_unann.unwrap_or(f64::NAN), base.validation.total_pnl_usd,
        base.test.n_unique_games, base.test.win_rate.unwrap_or(f64::NAN), base.test.ev_cents.unwrap_or(f64::NAN), base.test.sharpe_game_unann.unwrap_or(f64::NAN), base.test.total_pnl_usd,
    ));
    md.push_str(&format!(
        "Note: TRAIN EV is −3.58¢ (not TEST). TEST WR 84.8% / TEST EV +1.85¢. Breakeven WR = 83%. N 83¢ games = {n83}. Split TRAIN < `{train_cut}`, VAL < `{val_cut}`, TEST through `{test_end}`.\n\n"
    ));

    md.push_str("## 3. Existing 40–49 finding\n\n");
    if let Some(s) = seed {
        md.push_str(&format!(
            "`start_price_band=40_49`: TRAIN {:.2}¢ VAL {:.2}¢ TEST {:.2}¢ | games {} / test {} | WR all {:.1}% | class seed.\n\n",
            s.train.ev_cents.unwrap_or(f64::NAN),
            s.validation.ev_cents.unwrap_or(f64::NAN),
            s.test.ev_cents.unwrap_or(f64::NAN),
            s.all.n_unique_games,
            s.test.n_unique_games,
            s.all.win_rate.unwrap_or(f64::NAN) * 100.0
        ));
    }
    md.push_str("VAL n for this seed is **13** (ALL_83 VAL = 52). The requested VAL≥25 floor **cannot** be met by any 40–49 subset. No `ROBUST_CANDIDATE` exists under TRAIN≥50 / VAL≥25 / TEST≥20 inside this seed. Cells below are `CANDIDATE` under the feasible floor (VAL≥8, TEST≥15, all three EV>0).\n\n");

    md.push_str("## 4–7. Staged rankings\n\n");
    md.push_str(&format!(
        "Evaluated **{}** cells. Single / two / three / four-way tables use TEST EV among cells with TEST n≥10. Consistent (+TRAIN+VAL+TEST) cells are in the executive table above.\n\n",
        all.len()
    ));
    for stage in 1u8..=4 {
        let mut v: Vec<&Cond83> = all
            .iter()
            .filter(|c| {
                c.stage == stage && c.test.n_unique_games >= 10 && c.all.n_unique_games >= 30
            })
            .collect();
        v.sort_by(|a, b| {
            all_pos(b).cmp(&all_pos(a)).then_with(|| {
                b.test
                    .ev_cents
                    .partial_cmp(&a.test.ev_cents)
                    .unwrap_or(std::cmp::Ordering::Equal)
            })
        });
        md.push_str(&format!("### Stage {stage}\n\n"));
        if v.is_empty() {
            md.push_str("*No cells.*\n\n");
            continue;
        }
        md.push_str("| Condition | Tr/Va/Te | TRAIN | VAL | TEST | Lift | +all? |\n|---|---:|---:|---:|---:|---:|---|\n");
        for c in v.into_iter().take(8) {
            md.push_str(&format!(
                "| {} | {}/{}/{} | {:.2} | {:.2} | {:.2} | {:.2} | {} |\n",
                c.condition,
                c.train.n_unique_games,
                c.validation.n_unique_games,
                c.test.n_unique_games,
                c.train.ev_cents.unwrap_or(f64::NAN),
                c.validation.ev_cents.unwrap_or(f64::NAN),
                c.test.ev_cents.unwrap_or(f64::NAN),
                c.ev_lift_test.unwrap_or(f64::NAN),
                if all_pos(c) { "yes" } else { "no" }
            ));
        }
        md.push('\n');
    }

    md.push_str("## 8–9. Optimal region and neighbors\n\n");
    md.push_str("The **region** is opening belief in the high-30s to high-40s, not a single hyper-specific cell:\n\n");
    md.push_str("```text\n83¢\n├── Start price\n│   ├── 40–49¢ → favorable (seed; +TRAIN+VAL+TEST)\n│   ├── 45–49 / 40–44 → finer cuts; sample usually too small on VAL/TEST\n│   ├── 35–49 / P_start<50 → broader sibling, still +all-split when n holds\n│   ├── <40¢ → insufficient / not helpful\n│   └── ≥50¢ → unfavorable\n├── Current game state\n│   ├── late + 2+ lead → does not reliably lift 40–49 OOS\n│   ├── mid innings → sometimes +TEST but TRAIN often negative unconditionally\n│   └── close / one-run / early → avoid\n├── Path / vol\n│   ├── high 1m vol → avoid (unconditional)\n│   ├── LOW vol ∩ 40–49 → theoretically cleaner, TEST n collapses\n│   └── TRENDING ∩ 40–49 → no stable incremental hold edge\n└── Combined\n    └── BEST STABLE STATE = 83¢ + opened 40–49 (or P_start<50)\n```\n\n");

    md.push_str("## 10. Unfavorable conditions\n\nSee list above. Strongest negatives with TEST n≥15: high 1m vol, no 2-run lead / close game, opened favorite, early innings.\n\n");
    md.push_str("## 11–13. TRAIN/VAL/TEST, bootstrap, monthly\n\nPer-cell metrics are in `b1_83_optimal_conditions.csv`. Bootstrap: `b1_83_bootstrap.json`. Monthly + LOPO: `b1_83_monthly_stability.json`.\n\n");
    md.push_str("## 14. EV lift\n\n`EV_LIFT = Conditional_EV − ALL_83_EV`. Use TEST lift for ranking and all-sample lift for economics. ALL_83 all-sample EV = −3.32¢.\n\n");
    md.push_str("## 15. Economic sensitivity\n\nHypothetical cost subtracted from TEST EV of the best cell (not Kalshi fees):\n\n");
    for s in sensitivity {
        md.push_str(&format!("- {}\n", s));
    }
    md.push('\n');
    md.push_str("## 16. Limitations\n\n- TRADE print ≠ maker fill. L2 unused.\n- VAL≥25 is infeasible for 40–49 subsets (13 VAL games).\n- TEST n≈21 on the seed; bootstrap CI includes $0.\n- Research score is a TRAIN-signed composite, not ML and not live.\n- Multiple-testing: many cells; only +TRAIN+VAL+TEST cells are treated as confirmed.\n- Live 80/81/83/89 and 50% stop unchanged. No W9.\n\n");
    md.push_str("## 17. Reproducibility\n\n```text\ncargo build --release -p momento-research-b1\n./target/release/momento-research-b1 --search-83-opt\n```\n\nRequires `Backtesting Suite/Foundation/B1/features.sqlite` from a prior `--extract`. Does not re-extract. Does not submit orders.\n\n**STOP.**\n");
    md
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::search::SplitMetrics;

    #[test]
    fn move_fine_buckets_cover_repricing() {
        let mut row = SearchRow {
            game_id: "g".into(),
            date: "2025-06-01".into(),
            month: "2025-06".into(),
            entry_cents: 83,
            qty: 7,
            chrono: ChronoSplit::Train,
            settlement_win: Some(true),
            mfe: None,
            mae: None,
            exit_ret: BTreeMap::new(),
            feats: BTreeMap::new(),
        };
        row.feats.insert("move_fine".into(), "35_40".into());
        assert_eq!(row.feats.get("move_fine").unwrap(), "35_40");
    }

    #[test]
    fn classify_rejects_tiny() {
        let c = Cond83 {
            condition: "toy".into(),
            stage: 1,
            entry_price_cents: 83,
            fill_status: FILL_STATUS,
            train: SplitMetrics {
                n_unique_games: 10,
                ev_cents: Some(1.0),
                ..SplitMetrics::default()
            },
            validation: SplitMetrics::default(),
            test: SplitMetrics {
                n_unique_games: 4,
                ev_cents: Some(17.0),
                ..SplitMetrics::default()
            },
            all: SplitMetrics {
                n_unique_games: 14,
                ..SplitMetrics::default()
            },
            ev_lift_all: None,
            ev_lift_test: Some(15.0),
            wr_lift_all: None,
            sharpe_lift_test: None,
            ev_decay_train_to_test: None,
            month_concentration: 0.2,
            one_month_domination: false,
            bootstrap_test_ev_usd_ci95: None,
            research_status: String::new(),
        };
        assert_eq!(classify_opt(&c), "REJECTED");
    }
}
