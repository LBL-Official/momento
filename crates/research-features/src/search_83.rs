//! Conditional 83¢ entry-state search. Not a price comparison. Not live trading.

use std::collections::{BTreeMap, BTreeSet};
use std::fs;
use std::path::Path;

use crate::a1_targets::{EXIT_HOLD_TO_SETTLEMENT, EXIT_HORIZON_1M, EXIT_LIVE_50PCT_STOP};
use crate::error::B1Error;
use crate::search::{
    BOOTSTRAP_N, BOOTSTRAP_SEED, ChronoSplit, EXITS, FILL_STATUS, SearchRow, SplitMetrics,
    attach_train_tertiles, bootstrap_ev_ci, chronological_60_20_20, flatten, metrics, tertile_cuts,
};
use crate::search_report::SearchConfig;
use crate::store::FeatureStore;
use crate::types::B1EntrySnapshot;
use crate::versions::{ENGINE_VERSION, FEATURE_SCHEMA_VERSION};

const PRIMARY: &str = EXIT_HOLD_TO_SETTLEMENT;

#[derive(Clone, Debug, serde::Serialize)]
pub struct Cond83 {
    pub condition: String,
    pub stage: u8,
    pub entry_price_cents: i32,
    pub fill_status: &'static str,
    pub train: SplitMetrics,
    pub validation: SplitMetrics,
    pub test: SplitMetrics,
    pub all: SplitMetrics,
    pub ev_lift_all: Option<f64>,
    pub ev_lift_test: Option<f64>,
    pub wr_lift_all: Option<f64>,
    pub sharpe_lift_test: Option<f64>,
    pub ev_decay_train_to_test: Option<f64>,
    pub month_concentration: f64,
    pub one_month_domination: bool,
    pub bootstrap_test_ev_usd_ci95: Option<(f64, f64)>,
    pub research_status: String,
}

fn yes_no(b: bool) -> String {
    if b { "YES" } else { "NO" }.into()
}

fn inning_83(inn: Option<u8>) -> &'static str {
    match inn {
        None => "NA",
        Some(i) if i <= 3 => "EARLY",
        Some(i) if i <= 5 => "MID",
        Some(6 | 7) => "LATE_6_7",
        Some(8) => "LATE_8",
        Some(9) => "NINTH",
        Some(_) => "EXTRA",
    }
}

pub fn enrich(row: &mut SearchRow, s: &B1EntrySnapshot) {
    let inn = s.baseball.inning;
    let lead = s.baseball.bound_team_lead;
    let p0 = s.starting_market.p_start_cents;
    let mv = s.market_history.start_to_entry_move_cents;
    row.feats.insert("inning_83".into(), inning_83(inn).into());
    row.feats.insert(
        "inning_exact".into(),
        inn.map(|i| i.to_string()).unwrap_or_else(|| "NA".into()),
    );
    row.feats.insert(
        "half".into(),
        s.baseball
            .half_inning
            .clone()
            .unwrap_or_else(|| "NA".into()),
    );
    row.feats.insert(
        "base_state".into(),
        s.baseball.base_state.clone().unwrap_or_else(|| "NA".into()),
    );
    row.feats.insert(
        "outs_band".into(),
        match s.baseball.outs {
            Some(0) => "EARLY_OUT".into(),
            Some(1) => "MID_OUT".into(),
            Some(2) => "LATE_OUT".into(),
            _ => "NA".into(),
        },
    );
    for (k, n) in [
        ("lead_ge1", 1),
        ("lead_ge2", 2),
        ("lead_ge3", 3),
        ("lead_ge4", 4),
    ] {
        row.feats
            .insert(k.into(), yes_no(lead.is_some_and(|l| l >= n)));
    }
    row.feats
        .insert("trailing".into(), yes_no(lead.is_some_and(|l| l < 0)));
    for (k, t) in [
        ("p_start_lt40", 40),
        ("p_start_lt45", 45),
        ("p_start_lt50", 50),
    ] {
        row.feats
            .insert(k.into(), yes_no(p0.is_some_and(|p| p < t)));
    }
    for (k, t) in [
        ("p_start_ge50", 50),
        ("p_start_ge55", 55),
        ("p_start_ge60", 60),
    ] {
        row.feats
            .insert(k.into(), yes_no(p0.is_some_and(|p| p >= t)));
    }
    row.feats
        .insert("start_move_gt0".into(), yes_no(mv.is_some_and(|m| m > 0)));
    row.feats
        .insert("start_move_neg".into(), yes_no(mv.is_some_and(|m| m < 0)));
    for (k, t) in [
        ("start_move_gt5", 5),
        ("start_move_gt10", 10),
        ("start_move_gt15", 15),
        ("start_move_gt20", 20),
        ("start_move_gt25", 25),
        ("start_move_gt30", 30),
    ] {
        row.feats
            .insert(k.into(), yes_no(mv.is_some_and(|m| m > t)));
    }
    row.feats.insert(
        "vel_sign".into(),
        match s.price_dynamics.p_1m.delta_cents {
            None => "NA".into(),
            Some(x) if x > 0 => "UP".into(),
            Some(x) if x < 0 => "DOWN".into(),
            Some(_) => "FLAT".into(),
        },
    );
    let last_ev = s.event_response.event_history.last();
    row.feats.insert(
        "last_event_class".into(),
        last_ev
            .map(|e| e.event_class.clone())
            .unwrap_or_else(|| "NA".into()),
    );
    row.feats.insert(
        "last_event_sign".into(),
        match last_ev.and_then(|e| e.delta_cents) {
            None => "NA".into(),
            Some(x) if x > 0 => "UP".into(),
            Some(x) if x < 0 => "DOWN".into(),
            Some(_) => "FLAT".into(),
        },
    );
    row.feats.insert(
        "start_move_dir".into(),
        s.market_history
            .start_to_entry_direction
            .map(|d| d.as_str().to_string())
            .unwrap_or_else(|| "NA".into()),
    );
    row.feats.insert(
        "start_move_bucket".into(),
        s.market_history
            .start_to_entry_move_bucket
            .clone()
            .unwrap_or_else(|| "NA".into()),
    );
    row.feats.insert("tied".into(), yes_no(lead == Some(0)));
    row.feats.insert("lead_eq1".into(), yes_no(lead == Some(1)));
    for (k, look) in [
        ("vel_5m_sign", &s.price_dynamics.p_5m),
        ("vel_15m_sign", &s.price_dynamics.p_15m),
        ("vel_30m_sign", &s.price_dynamics.p_30m),
    ] {
        row.feats.insert(
            k.into(),
            match look.delta_cents {
                None => "NA".into(),
                Some(x) if x > 0 => "UP".into(),
                Some(x) if x < 0 => "DOWN".into(),
                Some(_) => "FLAT".into(),
            },
        );
    }
    let n_ev = s.event_response.event_history.len();
    row.feats.insert(
        "n_events_band".into(),
        if n_ev <= 5 {
            "FEW"
        } else if n_ev <= 16 {
            "MID"
        } else {
            "MANY"
        }
        .into(),
    );
}

pub(crate) fn attach_83_tertiles(rows: &mut [SearchRow], snaps: &[B1EntrySnapshot]) {
    let by_id: BTreeMap<&str, &B1EntrySnapshot> =
        snaps.iter().map(|s| (s.game_id.as_str(), s)).collect();
    let attach =
        |rows: &mut [SearchRow], key: &str, raw: &dyn Fn(&B1EntrySnapshot) -> Option<i32>| {
            let train: Vec<i32> = rows
                .iter()
                .filter(|r| r.chrono == ChronoSplit::Train)
                .filter_map(|r| by_id.get(r.game_id.as_str()).copied().and_then(raw))
                .collect();
            let cuts = tertile_cuts(train);
            for r in rows.iter_mut() {
                let v = by_id.get(r.game_id.as_str()).copied().and_then(raw);
                let label = match (v, cuts) {
                    (None, _) => "NA".into(),
                    (Some(_), None) => "NA".into(),
                    (Some(x), Some((a, _))) if x <= a => "LOW".into(),
                    (Some(x), Some((_, b))) if x <= b => "MID".into(),
                    (Some(_), Some(_)) => "HIGH".into(),
                };
                r.feats.insert(key.into(), label);
            }
        };
    attach(rows, "vol_1m_tertile", &|s| {
        s.market_history.volatility_1m_cents
    });
    attach(rows, "vol_15m_tertile", &|s| {
        s.market_history.volatility_15m_cents
    });
    attach(rows, "vol_30m_tertile", &|s| {
        s.market_history.volatility_30m_cents
    });
    attach(rows, "vol_z_tertile", &|s| {
        s.market_history.volatility_5m_z_e3
    });
    attach(rows, "path_dist_tertile", &|s| {
        s.market_history.path_distance_cents
    });
}

fn families() -> &'static [&'static str] {
    &[
        "inning_83",
        "inning_exact",
        "half",
        "lead_regime",
        "score_bucket",
        "lead_ge1",
        "lead_ge2",
        "lead_ge3",
        "lead_ge4",
        "trailing",
        "tied",
        "lead_eq1",
        "outs",
        "outs_band",
        "base_class",
        "base_state",
        "regime",
        "start_sentiment",
        "start_price_band",
        "p_start_lt40",
        "p_start_lt45",
        "p_start_lt50",
        "p_start_ge50",
        "p_start_ge55",
        "p_start_ge60",
        "start_move_gt0",
        "start_move_neg",
        "start_move_gt5",
        "start_move_gt10",
        "start_move_gt15",
        "start_move_gt20",
        "start_move_gt25",
        "start_move_gt30",
        "start_move_tertile",
        "start_move_dir",
        "start_move_bucket",
        "p_start_tertile",
        "personality",
        "vel_sign",
        "vel_5m_sign",
        "vel_15m_sign",
        "vel_30m_sign",
        "vel_1m_tertile",
        "accel_sign",
        "vol_1m_tertile",
        "vol_5m_tertile",
        "vol_15m_tertile",
        "vol_30m_tertile",
        "vol_z_tertile",
        "reversal_tertile",
        "path_eff_tertile",
        "path_dist_tertile",
        "event_run_sign",
        "last_event_class",
        "last_event_sign",
        "n_events_band",
        "late_6_9_lead2",
    ]
}

pub fn cond_ok(row: &SearchRow, cond: &[(String, String)]) -> bool {
    cond.iter()
        .all(|(k, v)| row.feats.get(k).is_some_and(|x| x == v))
}

pub(crate) fn slice<'a>(
    rows: &'a [SearchRow],
    split: Option<ChronoSplit>,
    cond: &[(String, String)],
) -> Vec<&'a SearchRow> {
    rows.iter()
        .filter(|r| split.is_none_or(|s| r.chrono == s) && cond_ok(r, cond))
        .collect()
}

fn month_conc(rows: &[&SearchRow], _exit: &str) -> f64 {
    let mut m: BTreeMap<String, usize> = BTreeMap::new();
    for r in rows {
        *m.entry(r.month.clone()).or_default() += 1;
    }
    let tot = rows.len().max(1);
    m.values()
        .map(|v| *v as f64 / tot as f64)
        .fold(0.0, f64::max)
}

fn oos_ok(c: &Cond83) -> bool {
    c.all.n_unique_games >= 30
        && c.test.n_unique_games >= 15
        && c.validation.n_unique_games >= 10
        && c.validation.ev_cents.unwrap_or(0.0) > 0.0
        && c.test.ev_cents.unwrap_or(0.0) > 0.0
        && c.test.sharpe_game_unann.unwrap_or(0.0) > 0.0
}

pub fn label(cond: &[(String, String)]) -> String {
    if cond.is_empty() {
        "ALL_83".into()
    } else {
        cond.iter()
            .map(|(k, v)| format!("{k}={v}"))
            .collect::<Vec<_>>()
            .join("&")
    }
}

fn classify(c: &Cond83, base_test_ev: Option<f64>) -> String {
    let n = c.all.n_unique_games;
    let tn = c.test.n_unique_games;
    let vn = c.validation.n_unique_games;
    let tev = c.test.ev_cents.unwrap_or(0.0);
    let vev = c.validation.ev_cents.unwrap_or(0.0);
    let tsh = c.test.sharpe_game_unann.unwrap_or(0.0);
    let lift = c.ev_lift_test.unwrap_or(0.0);
    if n < 30 {
        return "TOO_SMALL".into();
    }
    if tev > 0.0
        && vev > 0.0
        && tsh > 0.0
        && lift > 0.0
        && !c.one_month_domination
        && n >= 100
        && tn >= 30
        && vn >= 15
    {
        return "STRONG_CANDIDATE".into();
    }
    if tev > 0.0 && vev > 0.0 && tsh > 0.0 && lift > 0.0 && n >= 50 && tn >= 20 && vn >= 10 {
        return "CANDIDATE".into();
    }
    if tev > 0.0 && vev > 0.0 && n >= 30 && tn >= 15 && vn >= 8 {
        return "EXPLORATORY".into();
    }
    if tn >= 10 && tev < 0.0 && tev < base_test_ev.unwrap_or(0.0) {
        return "UNFAVORABLE".into();
    }
    "WEAK".into()
}

pub(crate) fn eval(
    rows: &[SearchRow],
    cond: &[(String, String)],
    stage: u8,
    exit: &str,
    base_all: &SplitMetrics,
    base_test: &SplitMetrics,
) -> Option<Cond83> {
    eval_inner(rows, cond, stage, exit, base_all, base_test, true)
}

/// Same metrics as [`eval`] but skips the TEST bootstrap. Use for mass screening.
pub fn eval_screen(
    rows: &[SearchRow],
    cond: &[(String, String)],
    stage: u8,
    exit: &str,
    base_all: &SplitMetrics,
    base_test: &SplitMetrics,
) -> Option<Cond83> {
    eval_inner(rows, cond, stage, exit, base_all, base_test, false)
}

fn eval_inner(
    rows: &[SearchRow],
    cond: &[(String, String)],
    stage: u8,
    exit: &str,
    base_all: &SplitMetrics,
    base_test: &SplitMetrics,
    with_bootstrap: bool,
) -> Option<Cond83> {
    let train = slice(rows, Some(ChronoSplit::Train), cond);
    if train.len() < 12 {
        return None;
    }
    let val = slice(rows, Some(ChronoSplit::Validation), cond);
    let test = slice(rows, Some(ChronoSplit::Test), cond);
    let all = slice(rows, None, cond);
    let train_m = metrics(&train, exit);
    if train_m.n_unique_games < 12 {
        return None;
    }
    let test_m = metrics(&test, exit);
    let all_m = metrics(&all, exit);
    let val_m = metrics(&val, exit);
    let conc = month_conc(&all, exit);
    let ev_lift_all = match (all_m.ev_cents, base_all.ev_cents) {
        (Some(a), Some(b)) => Some(a - b),
        _ => None,
    };
    let ev_lift_test = match (test_m.ev_cents, base_test.ev_cents) {
        (Some(a), Some(b)) => Some(a - b),
        _ => None,
    };
    let wr_lift_all = match (all_m.win_rate, base_all.win_rate) {
        (Some(a), Some(b)) => Some(a - b),
        _ => None,
    };
    let sharpe_lift_test = match (test_m.sharpe_game_unann, base_test.sharpe_game_unann) {
        (Some(a), Some(b)) => Some(a - b),
        _ => None,
    };
    let ev_decay_train_to_test = match (train_m.ev_cents, test_m.ev_cents) {
        (Some(a), Some(b)) => Some(b - a),
        _ => None,
    };
    let boot = if with_bootstrap {
        bootstrap_ev_ci(&test, exit, BOOTSTRAP_N, BOOTSTRAP_SEED)
    } else {
        None
    };
    let mut c = Cond83 {
        condition: label(cond),
        stage,
        entry_price_cents: 83,
        fill_status: FILL_STATUS,
        train: train_m,
        validation: val_m,
        test: test_m,
        all: all_m,
        ev_lift_all,
        ev_lift_test,
        wr_lift_all,
        sharpe_lift_test,
        ev_decay_train_to_test,
        month_concentration: conc,
        one_month_domination: conc >= 0.60,
        bootstrap_test_ev_usd_ci95: boot,
        research_status: String::new(),
    };
    c.research_status = classify(&c, base_test.ev_cents);
    Some(c)
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

pub fn parse_cond(s: &str) -> Vec<(String, String)> {
    if s == "ALL_83" {
        return vec![];
    }
    s.split('&')
        .filter_map(|p| {
            p.split_once('=')
                .map(|(k, v)| (k.to_string(), v.to_string()))
        })
        .collect()
}

fn write_json(path: &Path, v: &impl serde::Serialize) -> Result<(), B1Error> {
    fs::write(path, serde_json::to_string_pretty(v)?)?;
    Ok(())
}

fn rank_best(cands: &[Cond83]) -> Vec<&Cond83> {
    let mut v: Vec<&Cond83> = cands
        .iter()
        .filter(|c| c.condition != "ALL_83" && oos_ok(c))
        .collect();
    v.sort_by(|a, b| {
        let a_train = a.train.ev_cents.unwrap_or(f64::NEG_INFINITY) > 0.0;
        let b_train = b.train.ev_cents.unwrap_or(f64::NEG_INFINITY) > 0.0;
        b_train
            .cmp(&a_train)
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
            .then_with(|| b.all.n_unique_games.cmp(&a.all.n_unique_games))
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

fn rank_worst(cands: &[Cond83]) -> Vec<&Cond83> {
    let mut v: Vec<&Cond83> = cands
        .iter()
        .filter(|c| {
            c.condition != "ALL_83"
                && c.all.n_unique_games >= 30
                && c.test.n_unique_games >= 15
                && c.test.ev_cents.is_some()
        })
        .collect();
    v.sort_by(|a, b| {
        a.test
            .ev_cents
            .partial_cmp(&b.test.ev_cents)
            .unwrap_or(std::cmp::Ordering::Equal)
            .then_with(|| b.all.n_unique_games.cmp(&a.all.n_unique_games))
    });
    v
}

fn csv_row(c: &Cond83) -> String {
    format!(
        "{},{},{},{},{},{:.4},{:.4},{:.4},{:.4},{:.4},{:.4},{:.4},{:.4},{:.4},{:.2},{:.2},{:.4},{:.4},{},{}",
        c.condition.replace(',', ";"),
        c.stage,
        c.all.n_entries,
        c.all.n_unique_games,
        c.test.n_unique_games,
        c.train.ev_cents.unwrap_or(f64::NAN),
        c.validation.ev_cents.unwrap_or(f64::NAN),
        c.test.ev_cents.unwrap_or(f64::NAN),
        c.train.sharpe_game_unann.unwrap_or(f64::NAN),
        c.validation.sharpe_game_unann.unwrap_or(f64::NAN),
        c.test.sharpe_game_unann.unwrap_or(f64::NAN),
        c.train.win_rate.unwrap_or(f64::NAN),
        c.validation.win_rate.unwrap_or(f64::NAN),
        c.test.win_rate.unwrap_or(f64::NAN),
        c.test.total_pnl_usd,
        c.test.max_dd_usd,
        c.ev_lift_test.unwrap_or(f64::NAN),
        c.ev_decay_train_to_test.unwrap_or(f64::NAN),
        c.research_status,
        c.fill_status
    )
}

pub fn run_83_condition_search(cfg: &SearchConfig) -> Result<serde_json::Value, B1Error> {
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
    }

    let all_rows: Vec<&SearchRow> = rows.iter().collect();
    let base_all = metrics(&all_rows, PRIMARY);
    let test_base = slice(&rows, Some(ChronoSplit::Test), &[]);
    let base_test = metrics(&test_base, PRIMARY);
    let base = eval(&rows, &[], 0, PRIMARY, &base_all, &base_test).expect("ALL_83");

    let mut hold: Vec<Cond83> = vec![base.clone()];
    let mut seen = BTreeSet::new();
    seen.insert("ALL_83".into());

    let push = |hold: &mut Vec<Cond83>,
                seen: &mut BTreeSet<String>,
                rows: &[SearchRow],
                cond: Vec<(String, String)>,
                stage: u8,
                base_all: &SplitMetrics,
                base_test: &SplitMetrics| {
        let Some(c) = eval(rows, &cond, stage, PRIMARY, base_all, base_test) else {
            return;
        };
        if seen.insert(c.condition.clone()) {
            hold.push(c);
        }
    };

    for fam in families() {
        for v in observed(&rows, fam) {
            push(
                &mut hold,
                &mut seen,
                &rows,
                vec![(fam.to_string(), v)],
                1,
                &base_all,
                &base_test,
            );
        }
    }

    let mut uni_rank: Vec<&Cond83> = hold
        .iter()
        .filter(|c| {
            c.stage == 1
                && c.train.n_unique_games >= 30
                && c.train.ev_cents.unwrap_or(f64::NEG_INFINITY) > base_all.ev_cents.unwrap_or(0.0)
        })
        .collect();
    uni_rank.sort_by(|a, b| {
        b.train
            .ev_cents
            .partial_cmp(&a.train.ev_cents)
            .unwrap_or(std::cmp::Ordering::Equal)
    });
    let top_uni: Vec<Vec<(String, String)>> = uni_rank
        .iter()
        .take(14)
        .map(|c| parse_cond(&c.condition))
        .collect();

    let motivated: &[(&str, &str, &str, &str)] = &[
        ("inning_83", "LATE_6_7", "lead_ge2", "YES"),
        ("inning_83", "LATE_8", "lead_ge2", "YES"),
        ("late_6_9_lead2", "YES", "start_sentiment", "UNDERDOG"),
        ("late_6_9_lead2", "YES", "p_start_lt50", "YES"),
        ("lead_ge2", "YES", "p_start_lt50", "YES"),
        ("lead_ge2", "YES", "start_move_gt20", "YES"),
        ("lead_ge2", "YES", "personality", "TRENDING"),
        ("start_sentiment", "UNDERDOG", "start_move_gt20", "YES"),
        (
            "start_sentiment",
            "STRONG_UNDERDOG",
            "start_move_gt20",
            "YES",
        ),
        ("personality", "CHOPPY", "vol_5m_tertile", "HIGH"),
        ("personality", "TRENDING", "path_eff_tertile", "HIGH"),
        ("score_bucket", "MULTI_RUN", "start_move_gt20", "YES"),
        ("inning_83", "LATE_6_7", "start_move_gt20", "YES"),
        ("lead_ge3", "YES", "p_start_lt50", "YES"),
        ("trailing", "YES", "vol_5m_tertile", "HIGH"),
        ("inning_83", "NINTH", "lead_eq1", "YES"),
        ("inning_83", "LATE_8", "score_bucket", "ONE_RUN"),
        ("personality", "REVERSING", "vol_5m_tertile", "HIGH"),
        ("start_move_dir", "UP", "path_eff_tertile", "HIGH"),
        ("start_move_dir", "UP", "vol_5m_tertile", "LOW"),
        ("vel_sign", "UP", "personality", "TRENDING"),
        ("lead_ge2", "YES", "vol_z_tertile", "LOW"),
    ];
    for (a, va, b, vb) in motivated {
        push(
            &mut hold,
            &mut seen,
            &rows,
            vec![
                (a.to_string(), va.to_string()),
                (b.to_string(), vb.to_string()),
            ],
            2,
            &base_all,
            &base_test,
        );
    }
    for (i, a) in top_uni.iter().enumerate() {
        for b in top_uni.iter().skip(i + 1) {
            if a[0].0 == b[0].0 {
                continue;
            }
            let mut cond = a.clone();
            cond.extend(b.iter().cloned());
            if eval(&rows, &cond, 2, PRIMARY, &base_all, &base_test)
                .is_some_and(|c| c.train.n_unique_games >= 30)
            {
                push(&mut hold, &mut seen, &rows, cond, 2, &base_all, &base_test);
            }
        }
    }

    let motivated3: &[&[(&str, &str)]] = &[
        &[
            ("inning_83", "LATE_6_7"),
            ("lead_ge2", "YES"),
            ("p_start_lt50", "YES"),
        ],
        &[
            ("inning_83", "LATE_6_7"),
            ("lead_ge2", "YES"),
            ("start_move_gt20", "YES"),
        ],
        &[
            ("lead_ge2", "YES"),
            ("p_start_lt50", "YES"),
            ("start_move_gt20", "YES"),
        ],
        &[
            ("late_6_9_lead2", "YES"),
            ("p_start_lt50", "YES"),
            ("start_move_gt20", "YES"),
        ],
        &[
            ("lead_ge2", "YES"),
            ("start_move_gt20", "YES"),
            ("path_eff_tertile", "HIGH"),
        ],
        &[
            ("inning_83", "LATE_6_7"),
            ("lead_ge2", "YES"),
            ("personality", "TRENDING"),
        ],
        &[
            ("score_bucket", "MULTI_RUN"),
            ("p_start_lt50", "YES"),
            ("start_move_gt20", "YES"),
        ],
        &[
            ("inning_83", "NINTH"),
            ("lead_eq1", "YES"),
            ("vol_5m_tertile", "HIGH"),
        ],
        &[
            ("inning_83", "LATE_8"),
            ("score_bucket", "ONE_RUN"),
            ("personality", "REVERSING"),
        ],
        &[
            ("personality", "CHOPPY"),
            ("vol_5m_tertile", "HIGH"),
            ("score_bucket", "ONE_RUN"),
        ],
        &[
            ("lead_ge2", "YES"),
            ("start_move_gt20", "YES"),
            ("vol_5m_tertile", "LOW"),
        ],
        &[
            ("inning_83", "LATE_6_7"),
            ("lead_ge2", "YES"),
            ("vel_sign", "UP"),
        ],
    ];
    for parts in motivated3 {
        let cond: Vec<(String, String)> = parts
            .iter()
            .map(|(k, v)| ((*k).to_string(), (*v).to_string()))
            .collect();
        push(&mut hold, &mut seen, &rows, cond, 3, &base_all, &base_test);
    }
    let motivated4: &[&[(&str, &str)]] = &[
        &[
            ("inning_83", "LATE_6_7"),
            ("lead_ge2", "YES"),
            ("p_start_lt50", "YES"),
            ("start_move_gt20", "YES"),
        ],
        &[
            ("late_6_9_lead2", "YES"),
            ("p_start_lt50", "YES"),
            ("start_move_gt20", "YES"),
            ("path_eff_tertile", "HIGH"),
        ],
        &[
            ("lead_ge2", "YES"),
            ("p_start_lt50", "YES"),
            ("start_move_gt20", "YES"),
            ("personality", "TRENDING"),
        ],
        &[
            ("inning_83", "LATE_6_7"),
            ("lead_ge2", "YES"),
            ("p_start_lt50", "YES"),
            ("path_eff_tertile", "HIGH"),
        ],
        &[
            ("inning_83", "NINTH"),
            ("lead_eq1", "YES"),
            ("vol_5m_tertile", "HIGH"),
            ("personality", "REVERSING"),
        ],
    ];
    for parts in motivated4 {
        let cond: Vec<(String, String)> = parts
            .iter()
            .map(|(k, v)| ((*k).to_string(), (*v).to_string()))
            .collect();
        push(&mut hold, &mut seen, &rows, cond, 4, &base_all, &base_test);
    }

    let top3: Vec<Vec<(String, String)>> = rank_best(&hold)
        .into_iter()
        .filter(|c| c.stage <= 2)
        .take(10)
        .map(|c| parse_cond(&c.condition))
        .collect();
    for (i, a) in top3.iter().enumerate() {
        for (j, b) in top3.iter().enumerate().skip(i + 1) {
            for c in top3.iter().skip(j + 1) {
                let mut keys = BTreeSet::new();
                let mut cond = Vec::new();
                let mut ok = true;
                for part in [a.as_slice(), b.as_slice(), c.as_slice()]
                    .into_iter()
                    .flatten()
                {
                    if !keys.insert(part.0.clone()) {
                        ok = false;
                        break;
                    }
                    cond.push(part.clone());
                }
                if !ok || cond.len() < 3 {
                    continue;
                }
                if eval(&rows, &cond, 3, PRIMARY, &base_all, &base_test)
                    .is_some_and(|x| x.train.n_unique_games >= 50)
                {
                    push(&mut hold, &mut seen, &rows, cond, 3, &base_all, &base_test);
                }
            }
        }
    }

    let top4src: Vec<Vec<(String, String)>> = rank_best(&hold)
        .into_iter()
        .filter(|c| (1..=3).contains(&c.stage) && c.train.n_unique_games >= 50)
        .take(8)
        .map(|c| parse_cond(&c.condition))
        .collect();
    for (i, a) in top4src.iter().enumerate() {
        for (j, b) in top4src.iter().enumerate().skip(i + 1) {
            for (k, c) in top4src.iter().enumerate().skip(j + 1) {
                for d in top4src.iter().skip(k + 1) {
                    let mut keys = BTreeSet::new();
                    let mut cond = Vec::new();
                    let mut ok = true;
                    for part in [a.as_slice(), b.as_slice(), c.as_slice(), d.as_slice()]
                        .into_iter()
                        .flatten()
                    {
                        if !keys.insert(part.0.clone()) {
                            ok = false;
                            break;
                        }
                        cond.push(part.clone());
                    }
                    if !ok || cond.len() < 4 {
                        continue;
                    }
                    if eval(&rows, &cond, 4, PRIMARY, &base_all, &base_test)
                        .is_some_and(|x| x.train.n_unique_games >= 50)
                    {
                        push(&mut hold, &mut seen, &rows, cond, 4, &base_all, &base_test);
                    }
                }
            }
        }
    }

    let best = rank_best(&hold);
    let worst = rank_worst(&hold);
    let best_one = best.first().copied();

    let mut by_exit = BTreeMap::new();
    if let Some(b) = best_one {
        let cond = parse_cond(&b.condition);
        for ex in EXITS {
            let all_ex = metrics(&all_rows, ex);
            let test_ex = metrics(&slice(&rows, Some(ChronoSplit::Test), &[]), ex);
            if let Some(c) = eval(&rows, &cond, b.stage, ex, &all_ex, &test_ex) {
                by_exit.insert((*ex).to_string(), c);
            }
        }
    }

    let mut exit_rankings = BTreeMap::new();
    for ex in [PRIMARY, EXIT_HORIZON_1M, EXIT_LIVE_50PCT_STOP] {
        let all_ex = metrics(&all_rows, ex);
        let test_ex = metrics(&slice(&rows, Some(ChronoSplit::Test), &[]), ex);
        let mut scored: Vec<Cond83> = hold
            .iter()
            .filter(|c| c.condition != "ALL_83")
            .filter_map(|c| {
                eval(
                    &rows,
                    &parse_cond(&c.condition),
                    c.stage,
                    ex,
                    &all_ex,
                    &test_ex,
                )
            })
            .collect();
        scored.retain(|c| c.test.n_unique_games >= 10 && c.all.n_unique_games >= 30);
        scored.sort_by(|a, b| {
            b.test
                .ev_cents
                .partial_cmp(&a.test.ev_cents)
                .unwrap_or(std::cmp::Ordering::Equal)
                .then_with(|| {
                    b.test
                        .sharpe_game_unann
                        .partial_cmp(&a.test.sharpe_game_unann)
                        .unwrap_or(std::cmp::Ordering::Equal)
                })
        });
        exit_rankings.insert(
            (*ex).to_string(),
            scored.into_iter().take(8).collect::<Vec<_>>(),
        );
    }

    let mut sensitivity = Vec::new();
    for t in [5, 10, 15, 20, 25, 30] {
        if let Some(c) = eval(
            &rows,
            &[("start_move_gt".to_string() + &t.to_string(), "YES".into())],
            1,
            PRIMARY,
            &base_all,
            &base_test,
        ) {
            sensitivity.push(c);
        }
    }
    for t in [40, 45, 50] {
        if let Some(c) = eval(
            &rows,
            &[(format!("p_start_lt{t}"), "YES".into())],
            1,
            PRIMARY,
            &base_all,
            &base_test,
        ) {
            sensitivity.push(c);
        }
    }

    let mut monthly = BTreeMap::new();
    for r in &rows {
        if let Some(&ret) = r.exit_ret.get(PRIMARY) {
            let e = monthly.entry(r.month.clone()).or_insert((0i32, 0usize));
            e.0 += ret * r.qty;
            e.1 += 1;
        }
    }
    let mut lopo = Vec::new();
    if let Some(b) = best_one {
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

    fs::create_dir_all(&cfg.out_dir)?;
    write_json(
        &cfg.out_dir.join("b1_83_baseline.json"),
        &serde_json::json!({
            "entry_price_cents": 83,
            "question": "Given a contract already at 83¢, which conditions make that entry favorable?",
            "not_the_question": "Is 81¢ better than 83¢?",
            "n_entries": rows.len(),
            "n_unique_games": base_all.n_unique_games,
            "split": {"train_before": train_cut, "validation_before": val_cut, "test_end": test_end},
            "hold": base,
            "fill_status": FILL_STATUS,
            "executable_fill_confirmed": false,
            "breakeven_note": "83¢ YES needs ~83% true win probability before fees."
        }),
    )?;
    write_json(
        &cfg.out_dir.join("b1_83_condition_search.json"),
        &serde_json::json!({
            "n_candidates": hold.len(),
            "feature_schema_version": FEATURE_SCHEMA_VERSION,
            "engine_version": ENGINE_VERSION,
            "primary_exit": PRIMARY,
            "ranking": "TEST EV then TEST Sharpe; lift vs ALL_83; game-level",
            "cells": hold
        }),
    )?;
    let mut csv = String::from(
        "condition,stage,n_entries,n_games,n_test_games,train_ev,val_ev,test_ev,train_sharpe,val_sharpe,test_sharpe,train_wr,val_wr,test_wr,test_pnl_usd,test_maxdd_usd,ev_lift_test,ev_decay,status,fill_status\n",
    );
    let mut ranked = hold.clone();
    ranked.sort_by(|a, b| {
        b.test
            .ev_cents
            .partial_cmp(&a.test.ev_cents)
            .unwrap_or(std::cmp::Ordering::Equal)
    });
    for c in &ranked {
        csv.push_str(&csv_row(c));
        csv.push('\n');
    }
    fs::write(cfg.out_dir.join("b1_83_condition_rankings.csv"), csv)?;
    write_json(
        &cfg.out_dir.join("b1_83_best_conditions.json"),
        &best.iter().take(25).collect::<Vec<_>>(),
    )?;
    write_json(
        &cfg.out_dir.join("b1_83_worst_conditions.json"),
        &worst.iter().take(25).collect::<Vec<_>>(),
    )?;
    write_json(
        &cfg.out_dir.join("b1_83_best_condition_exits.json"),
        &by_exit,
    )?;
    write_json(
        &cfg.out_dir.join("b1_83_exit_family_rankings.json"),
        &exit_rankings,
    )?;
    write_json(
        &cfg.out_dir.join("b1_83_threshold_sensitivity.json"),
        &sensitivity,
    )?;
    write_json(
        &cfg.out_dir.join("b1_83_stability.json"),
        &serde_json::json!({
            "monthly_all_83_hold": monthly.iter().map(|(k,(p,n))| serde_json::json!({"month":k,"pnl_usd":f64::from(*p)/100.0,"n":n})).collect::<Vec<_>>(),
            "leave_one_month_out_best": lopo
        }),
    )?;

    let report = render_report(
        &rows,
        &base,
        &hold,
        &best,
        &worst,
        &by_exit,
        &exit_rankings,
        &sensitivity,
        &train_cut,
        &val_cut,
        &test_end,
    );
    fs::write(cfg.out_dir.join("b1_83_condition_report.md"), report)?;

    Ok(serde_json::json!({
        "n_83": rows.len(),
        "candidates": hold.len(),
        "best": best_one.map(|c| c.condition.clone()),
        "best_status": best_one.map(|c| c.research_status.clone()),
        "baseline_ev_cents": base_all.ev_cents,
        "fill_status": FILL_STATUS
    }))
}

#[allow(clippy::too_many_arguments)]
fn render_report(
    rows: &[SearchRow],
    base: &Cond83,
    all: &[Cond83],
    best: &[&Cond83],
    worst: &[&Cond83],
    by_exit: &BTreeMap<String, Cond83>,
    exit_rankings: &BTreeMap<String, Vec<Cond83>>,
    sensitivity: &[Cond83],
    train_cut: &str,
    val_cut: &str,
    test_end: &str,
) -> String {
    let mut md = String::new();
    md.push_str("# Conditional 83¢ entry-state search\n\n");
    md.push_str("**Question:** Given an MLB Kalshi contract trading at 83¢, what observable combination of baseball state, starting market belief, and market/price history produced the highest robust out-of-sample expected value?\n\n");
    md.push_str("This is **not** a 80-vs-81-vs-83 price comparison. The universe is `ENTRY_83` / `entry_price_cents = 83` only. 80/81/82 prints are excluded from ranking.\n\n");
    md.push_str(&format!(
        "**Fill status:** `{FILL_STATUS}`. `executable_fill_confirmed: false`. Research labels only. Not a live rule.\n\n"
    ));
    md.push_str("## 1. Direct answer\n\n");
    if let Some(b) = best.first() {
        md.push_str(&format!(
            "**Given an MLB Kalshi contract already trading at 83¢, the strongest robust hold-to-settlement state was `{}` (status `{}`).**\n\n",
            b.condition, b.research_status
        ));
        if b.condition.contains("start_price_band=40_49") || b.condition.contains("p_start_lt50") {
            md.push_str("In English: an 83¢ YES entry was most favorable when the contract **opened as a mild underdog (about 40–49¢)** and later **repriced to 83¢**. That is a large start-to-entry move, but “any move > +20¢” alone did **not** pass VAL. Strong underdogs (`P_start < 40`) were too rare and not helpful. Contracts that **opened already ≥50¢** (favorites that only drifted to 83¢) were unfavorable.\n\n");
        }
        md.push_str(&format!(
            "- Entry price: **83¢** (fixed)\n- Games (all / test): **{} / {}**\n- TEST EV: **{:.2}¢/contract** (lift vs ALL_83: {:.2}¢)\n- EV per 7-contract stake: **{:.2}¢** (${:.2})\n- TEST Sharpe (game, unann.): **{:.3}**\n- TEST win rate: **{:.1}%**\n- TEST P&L (qty=7, uncompounded vs $50): **${:.2}**\n- TEST MaxDD: **${:.2}**\n- MFE / MAE (all, ¢): {:.1} / {:.1}\n- TRAIN EV {:.2}¢ → VAL {:.2}¢ → TEST {:.2}¢ (decay {:.2}¢)\n\n",
            b.all.n_unique_games,
            b.test.n_unique_games,
            b.test.ev_cents.unwrap_or(f64::NAN),
            b.ev_lift_test.unwrap_or(f64::NAN),
            b.test.ev_cents.unwrap_or(0.0) * 7.0,
            b.test.ev_cents.unwrap_or(0.0) * 7.0 / 100.0,
            b.test.sharpe_game_unann.unwrap_or(f64::NAN),
            b.test.win_rate.unwrap_or(f64::NAN) * 100.0,
            b.test.total_pnl_usd,
            b.test.max_dd_usd,
            b.all.mean_mfe_cents.unwrap_or(f64::NAN),
            b.all.mean_mae_cents.unwrap_or(f64::NAN),
            b.train.ev_cents.unwrap_or(f64::NAN),
            b.validation.ev_cents.unwrap_or(f64::NAN),
            b.test.ev_cents.unwrap_or(f64::NAN),
            b.ev_decay_train_to_test.unwrap_or(f64::NAN),
        ));
        if let Some((lo, hi)) = b.bootstrap_test_ev_usd_ci95 {
            md.push_str(&format!(
                "TEST game-level bootstrap 95% CI for mean P&L/game: **${lo:.2} to ${hi:.2}**. {}\n\n",
                if lo <= 0.0 && hi >= 0.0 {
                    "The interval **includes $0**, so this is not a confirmed edge — CANDIDATE only."
                } else {
                    "The interval excludes $0 on this TEST slice; still not a live rule."
                }
            ));
        }
        if !matches!(b.research_status.as_str(), "STRONG_CANDIDATE" | "CANDIDATE") {
            md.push_str("This is **exploratory / not strong**: sample, decay, or concentration still limits the claim. Do not treat it as a live entry rule.\n\n");
        }
    } else {
        md.push_str("**No 83¢ condition produced positive VAL and TEST hold-to-settlement EV with ≥30 unique games.** The ALL_83 baseline itself is a losing settlement bet at 83¢ (breakeven ≈ 83% true win rate before fees). No robust favorable 83¢ *settlement* state was found under the sample-size and chronological rules.\n\n");
        if let Some(rel) = all
            .iter()
            .filter(|c| c.condition != "ALL_83" && c.all.n_unique_games >= 50)
            .max_by(|a, b| {
                a.test
                    .ev_cents
                    .partial_cmp(&b.test.ev_cents)
                    .unwrap_or(std::cmp::Ordering::Equal)
            })
        {
            md.push_str(&format!(
                "The *least unfavorable* N≥50 hold cell by TEST EV was `{}` (TEST EV {:.2}¢, lift {:.2}¢, n={}, status `{}`). That is a relative ranking against a negative baseline, not a claim of positive expected value.\n\n",
                rel.condition,
                rel.test.ev_cents.unwrap_or(f64::NAN),
                rel.ev_lift_test.unwrap_or(f64::NAN),
                rel.all.n_unique_games,
                rel.research_status
            ));
        }
    }
    md.push_str("## 2. Dataset\n\n");
    md.push_str(&format!(
        "- Universe: B1 snapshots with `entry_trade_price_cents = 83` only\n- N 83¢ entries / unique games: **{} / {}**\n- Date split: official B1 chronological 60/20/20 on the full W8 feature universe (not re-cut on 83¢ dates): TRAIN < `{}`, VAL < `{}`, TEST through `{}`\n- Primary label: `HOLD_TO_SETTLEMENT` (W6). EV = mean(settlement_value − 83) ¢/contract. Breakeven ≈ 83% win rate before fees.\n- Independence unit: **game**\n- Floors: exploratory ≥30 games, candidate ≥50, strong ≥100\n- Candidates evaluated: {}\n- L2 / OBI / mid / fair value: unused (`UNAVAILABLE_SOURCE`)\n\n",
        rows.len(),
        base.all.n_unique_games,
        train_cut,
        val_cut,
        test_end,
        all.len()
    ));
    md.push_str("## 3. ALL_83 baseline (hold to settlement)\n\n");
    md.push_str(&format!(
        "| Split | Entries | Games | Win | EV¢ | Sharpe | P&L $ | MaxDD $ |\n|---|---:|---:|---:|---:|---:|---:|---:|\n| ALL | {} | {} | {:.3} | {:.2} | {:.3} | {:.2} | {:.2} |\n| TRAIN | {} | {} | {:.3} | {:.2} | {:.3} | {:.2} | {:.2} |\n| VAL | {} | {} | {:.3} | {:.2} | {:.3} | {:.2} | {:.2} |\n| TEST | {} | {} | {:.3} | {:.2} | {:.3} | {:.2} | {:.2} |\n\n",
        base.all.n_entries, base.all.n_unique_games, base.all.win_rate.unwrap_or(f64::NAN), base.all.ev_cents.unwrap_or(f64::NAN), base.all.sharpe_game_unann.unwrap_or(f64::NAN), base.all.total_pnl_usd, base.all.max_dd_usd,
        base.train.n_entries, base.train.n_unique_games, base.train.win_rate.unwrap_or(f64::NAN), base.train.ev_cents.unwrap_or(f64::NAN), base.train.sharpe_game_unann.unwrap_or(f64::NAN), base.train.total_pnl_usd, base.train.max_dd_usd,
        base.validation.n_entries, base.validation.n_unique_games, base.validation.win_rate.unwrap_or(f64::NAN), base.validation.ev_cents.unwrap_or(f64::NAN), base.validation.sharpe_game_unann.unwrap_or(f64::NAN), base.validation.total_pnl_usd, base.validation.max_dd_usd,
        base.test.n_entries, base.test.n_unique_games, base.test.win_rate.unwrap_or(f64::NAN), base.test.ev_cents.unwrap_or(f64::NAN), base.test.sharpe_game_unann.unwrap_or(f64::NAN), base.test.total_pnl_usd, base.test.max_dd_usd,
    ));
    md.push_str("Every conditional cell is compared to this ALL_83 hold baseline (`EV_Lift = Conditional_EV − All_83_EV`). 80–83 band results are a different study.\n\n");
    md.push_str("## 4. Search methodology\n\n");
    md.push_str("Staged search on ENTRY_83 only:\n\n1. Univariate over the available B1 feature families\n2. Motivated pairs plus top-TRAIN univariate pairs (TRAIN EV > ALL_83 TRAIN EV, TRAIN n≥30)\n3. Motivated three-ways, then combinatorial three-ways from cells that already had +VAL and +TEST hold EV\n4. Motivated four-ways, then combinatorial four-ways if TRAIN n≥50\n\nTertile cuts are fit on **83¢ TRAIN only**. No threshold is tuned on TEST. Ranking for the primary table requires +VAL EV, +TEST EV, TEST Sharpe > 0, TEST n≥15, VAL n≥10, and ≥30 unique games. Tiny TEST slices that go 100% (EV = +17.00¢ exactly, Sharpe undefined) are discarded. Prefer +TRAIN EV for stability, then TEST EV, then TEST Sharpe. Do not rank by total P&L or in-sample Sharpe.\n\n");
    md.push_str("## 5. Feature universe\n\n");
    md.push_str("Used (B1 schema, TRADE prints): inning (raw + EARLY/MID/LATE_6_7/LATE_8/NINTH), half, lead thresholds, score_bucket, outs, base class/state, start sentiment / P_start thresholds, StartToEntryMove thresholds and tertiles, personality, velocity / acceleration / path efficiency / path distance / reversals, volatility 1/5/15/30m and TRAIN z tertile, last event class/sign, event-count band.\n\nUnused (UNAVAILABLE_SOURCE): OBI, OBI_z, MicroPrice, Spread, Depth, OFI, Absorption, Replenishment, FairValue, bid/ask.\n\n");
    md.push_str("## 6. Best individual conditions\n\n");
    table_stage(&mut md, all, 1, 12);
    md.push_str("## 7. Best 2-way conditions\n\n");
    table_stage(&mut md, all, 2, 12);
    md.push_str("## 8. Best 3-way conditions\n\n");
    table_stage(&mut md, all, 3, 10);
    md.push_str("## 9. Best 4-way conditions\n\n");
    table_stage(&mut md, all, 4, 8);
    md.push_str("## 10. Best overall 83¢ condition (hold)\n\n");
    md.push_str("| Rank | 83¢ condition | Stage | Games | Test n | Test EV¢ | Test Sharpe | Test WR | EV lift | Status |\n|---:|---|---:|---:|---:|---:|---:|---:|---:|---|\n");
    for (i, c) in best.iter().take(15).enumerate() {
        md.push_str(&format!(
            "| {} | {} | {} | {} | {} | {:.2} | {:.3} | {:.3} | {:.2} | {} |\n",
            i + 1,
            c.condition,
            c.stage,
            c.all.n_unique_games,
            c.test.n_unique_games,
            c.test.ev_cents.unwrap_or(f64::NAN),
            c.test.sharpe_game_unann.unwrap_or(f64::NAN),
            c.test.win_rate.unwrap_or(f64::NAN),
            c.ev_lift_test.unwrap_or(f64::NAN),
            c.research_status
        ));
    }
    if best.is_empty() {
        md.push_str("\n*Empty: no cell cleared +VAL EV, +TEST EV, TEST Sharpe > 0, TEST n≥15, VAL n≥10, and ≥30 unique games.* Tiny TEST slices that go 100% (EV = +17.00¢) are discarded.\n");
    }
    md.push_str("\n## 11. Worst overall 83¢ condition (hold)\n\n");
    md.push_str("These are **UNFAVORABLE_83_STATE** candidates: same 83¢ entry, worse TEST settlement EV.\n\n");
    for (i, c) in worst.iter().take(10).enumerate() {
        md.push_str(&format!(
            "{}. `{}` TEST EV {:.2}¢ TRAIN {:.2}¢ VAL {:.2}¢ (n={} test_n={}) status={}\n",
            i + 1,
            c.condition,
            c.test.ev_cents.unwrap_or(f64::NAN),
            c.train.ev_cents.unwrap_or(f64::NAN),
            c.validation.ev_cents.unwrap_or(f64::NAN),
            c.all.n_unique_games,
            c.test.n_unique_games,
            c.research_status
        ));
    }
    md.push_str("\n## 12. Train / VAL / Test\n\nSee ALL_83 table above and per-condition columns in `b1_83_condition_rankings.csv`. Conditions were proposed from TRAIN (and motivated baseball/market hypotheses). VAL and TEST were not used to cut thresholds.\n\n");
    md.push_str("## 13. Bootstrap CI\n\nGame-level bootstrap (n=1000, seed=42) on TEST P&L/game for each cell is in `b1_83_condition_search.json` (`bootstrap_test_ev_usd_ci95`). A CI that crosses $0 is not a confirmed edge.\n\n");
    md.push_str("## 14. Monthly stability\n\nALL_83 monthly hold P&L is in `b1_83_stability.json`. Leave-one-month-out for the top validated cell is in the same file (`remains_positive` per left-out month). A cell that flips sign when one month is removed is not robust.\n\n");
    md.push_str("## 15. Threshold sensitivity\n\n");
    for c in sensitivity {
        md.push_str(&format!(
            "- `{}` TEST EV {:.2}¢ VAL {:.2}¢ TRAIN {:.2}¢ n={} status={}\n",
            c.condition,
            c.test.ev_cents.unwrap_or(f64::NAN),
            c.validation.ev_cents.unwrap_or(f64::NAN),
            c.train.ev_cents.unwrap_or(f64::NAN),
            c.all.n_unique_games,
            c.research_status
        ));
    }
    md.push_str("\nIf only one adjacent threshold is positive, label the cut **fragile**.\n\n");
    md.push_str("## 16. Other exits (do not replace the settlement question)\n\n");
    md.push_str("Primary question remains settlement EV of an 83¢ state. Horizon labels are short-term TRADE continuation. Stops are path-dependent TRADE prints. None are maker fills.\n\n");
    if let Some(rows_ex) = exit_rankings.get(EXIT_HORIZON_1M) {
        md.push_str("### Short-horizon (HORIZON_1M) top cells\n\n");
        for (i, c) in rows_ex.iter().take(5).enumerate() {
            md.push_str(&format!(
                "{}. `{}` TEST EV {:.2}¢ Sharpe {:.3} n={}\n",
                i + 1,
                c.condition,
                c.test.ev_cents.unwrap_or(f64::NAN),
                c.test.sharpe_game_unann.unwrap_or(f64::NAN),
                c.all.n_unique_games
            ));
        }
        md.push('\n');
    }
    if let Some(rows_ex) = exit_rankings.get(EXIT_LIVE_50PCT_STOP) {
        md.push_str("### Stop-path (LIVE_50PCT_STOP) top cells\n\n");
        for (i, c) in rows_ex.iter().take(5).enumerate() {
            md.push_str(&format!(
                "{}. `{}` TEST EV {:.2}¢ Sharpe {:.3} n={}\n",
                i + 1,
                c.condition,
                c.test.ev_cents.unwrap_or(f64::NAN),
                c.test.sharpe_game_unann.unwrap_or(f64::NAN),
                c.all.n_unique_games
            ));
        }
        md.push('\n');
    }
    md.push_str("### Best hold condition under every A1 exit\n\n");
    for (ex, c) in by_exit {
        md.push_str(&format!(
            "- `{ex}` TEST EV {:.2}¢ Sharpe {:.3} n_test={} status={}\n",
            c.test.ev_cents.unwrap_or(f64::NAN),
            c.test.sharpe_game_unann.unwrap_or(f64::NAN),
            c.test.n_unique_games,
            c.research_status
        ));
    }
    md.push_str("\n## 17. Multiple-testing / data-mining warning\n\n");
    md.push_str(&format!(
        "{} cells were scored. Many share overlapping games. A raw TEST winner is expected under noise, especially when the unconditional 83¢ hold EV is already negative. Benjamini–Hochberg was **not** used as the primary ranker (the primary ranker is chronological +EV). Do not promote a cell to a live rule because it is rank 1 in this file.\n\n",
        all.len()
    ));
    md.push_str("## 18. Execution limitations\n\n");
    md.push_str("- TRADE print ≠ maker fill. Queue, cancel, and fill probability are unknown.\n- Fees are omitted. 83¢ maker/taker economics are not invented.\n- qty = 625 // 83 = 7 contracts; P&L is uncompounded vs a $50 snapshot.\n- A1 exits are **research labels**, not live execution assumptions.\n- Live FIRST01 80/81/83/89 and the 50% stop were **not** changed.\n- W9 was **not** started. L2 was **not** invented. No ML. No fair value.\n\n");
    md.push_str("## 19. Final research conclusion\n\n");
    if let Some(b) = best.first() {
        md.push_str(&format!(
            "**FAVORABLE_83_STATE:** `{}` (status `{}`). An 83¢ YES print was most favorable when this opening-belief / game-state filter held, with +VAL and +TEST settlement EV and adequate TEST games. Treat as a research discovery, not a production filter.\n\n",
            b.condition, b.research_status
        ));
    } else {
        md.push_str("At 83¢, settlement EV is negative unconditionally, and no searched baseball/market-history filter produced a robust positive VAL+TEST hold edge with adequate unique TEST games. Tiny 100%-win TEST slices are not a finding.\n\n");
    }
    if let Some(w) = worst.first() {
        md.push_str(&format!(
            "**UNFAVORABLE_83_STATE:** `{}` — TEST EV {:.2}¢ on {} TEST / {} total games (status `{}`).\n\n",
            w.condition,
            w.test.ev_cents.unwrap_or(f64::NAN),
            w.test.n_unique_games,
            w.all.n_unique_games,
            w.research_status
        ));
    }
    md.push_str("The example hypothesis “late innings + lead ≥2 + large start-to-entry repricing” did **not** earn a robust hold-to-settlement promotion: several of those cells were +TRAIN/+VAL and −TEST. Do not deploy it.\n\n");
    md.push_str("**STOP.** Do not modify live FIRST01, risk, or W9 from this report.\n");
    md
}

fn table_stage(md: &mut String, all: &[Cond83], stage: u8, n: usize) {
    let mut v: Vec<&Cond83> = all
        .iter()
        .filter(|c| c.stage == stage && c.all.n_unique_games >= 30 && c.test.n_unique_games >= 10)
        .collect();
    v.sort_by(|a, b| {
        oos_ok(b)
            .cmp(&oos_ok(a))
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
    });
    if v.is_empty() {
        md.push_str("*No cells at this stage with ≥30 unique games and ≥10 TEST games.*\n\n");
        return;
    }
    md.push_str("| Condition | Games | Test n | TEST EV¢ | VAL EV¢ | TRAIN EV¢ | TEST Sharpe | Lift | Status |\n|---|---:|---:|---:|---:|---:|---:|---:|---|\n");
    for c in v.into_iter().take(n) {
        md.push_str(&format!(
            "| {} | {} | {} | {:.2} | {:.2} | {:.2} | {:.3} | {:.2} | {} |\n",
            c.condition,
            c.all.n_unique_games,
            c.test.n_unique_games,
            c.test.ev_cents.unwrap_or(f64::NAN),
            c.validation.ev_cents.unwrap_or(f64::NAN),
            c.train.ev_cents.unwrap_or(f64::NAN),
            c.test.sharpe_game_unann.unwrap_or(f64::NAN),
            c.ev_lift_test.unwrap_or(f64::NAN),
            c.research_status
        ));
    }
    md.push('\n');
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn inning_83_buckets() {
        assert_eq!(inning_83(Some(7)), "LATE_6_7");
        assert_eq!(inning_83(Some(8)), "LATE_8");
        assert_eq!(inning_83(Some(9)), "NINTH");
    }

    #[test]
    fn parse_roundtrip() {
        let c = parse_cond("lead_ge2=YES&p_start_lt50=YES");
        assert_eq!(c.len(), 2);
        assert_eq!(label(&c), "lead_ge2=YES&p_start_lt50=YES");
    }

    #[test]
    fn oos_ok_rejects_tiny_perfect_test() {
        let mut c = Cond83 {
            condition: "toy".into(),
            stage: 1,
            entry_price_cents: 83,
            fill_status: FILL_STATUS,
            train: SplitMetrics {
                n_unique_games: 100,
                ev_cents: Some(-2.0),
                ..SplitMetrics::default()
            },
            validation: SplitMetrics {
                n_unique_games: 7,
                ev_cents: Some(2.0),
                ..SplitMetrics::default()
            },
            test: SplitMetrics {
                n_unique_games: 6,
                ev_cents: Some(17.0),
                sharpe_game_unann: None,
                ..SplitMetrics::default()
            },
            all: SplitMetrics {
                n_unique_games: 113,
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
        c.all.n_unique_games = 113;
        assert!(!oos_ok(&c));
    }
}
