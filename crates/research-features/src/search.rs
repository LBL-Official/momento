//! Exhaustive A1 bucket search. TRADE-print modeled. Not a trading rule.

use std::collections::{BTreeMap, BTreeSet};

use crate::a1_targets::{
    EXIT_FIRST01, EXIT_HARD_60, EXIT_HARD_65, EXIT_HARD_70, EXIT_HARD_75, EXIT_HOLD_TO_SETTLEMENT,
    EXIT_HORIZON_1M, EXIT_HORIZON_5M, EXIT_HORIZON_15M, EXIT_HORIZON_30M, EXIT_LIVE_50PCT_STOP,
};
use crate::recon::qty_for_entry;
use crate::types::{B1EntrySnapshot, SettlementOutcome};

pub const EXITS: &[&str] = &[
    EXIT_HOLD_TO_SETTLEMENT,
    EXIT_FIRST01,
    EXIT_LIVE_50PCT_STOP,
    EXIT_HARD_75,
    EXIT_HARD_70,
    EXIT_HARD_65,
    EXIT_HARD_60,
    EXIT_HORIZON_1M,
    EXIT_HORIZON_5M,
    EXIT_HORIZON_15M,
    EXIT_HORIZON_30M,
];

pub const ENTRY_KEYS: &[&str] = &[
    "ENTRY_80",
    "ENTRY_81",
    "ENTRY_82",
    "ENTRY_83",
    "ENTRY_BAND_80_83",
];

pub const STAKE_CENTS: i32 = crate::recon::STAKE_CENTS;
pub const BANKROLL_CENTS: i32 = crate::recon::BANKROLL_CENTS;
pub const BOOTSTRAP_N: usize = 1000;
pub const BOOTSTRAP_SEED: u64 = 42;
pub const FILL_STATUS: &str = "TRADE_PRINT_MODELED";

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum ChronoSplit {
    Train,
    Validation,
    Test,
}

impl ChronoSplit {
    pub fn as_str(self) -> &'static str {
        match self {
            Self::Train => "TRAIN",
            Self::Validation => "VALIDATION",
            Self::Test => "TEST",
        }
    }
}

#[derive(Clone, Debug)]
pub struct SearchRow {
    pub game_id: String,
    pub date: String,
    pub month: String,
    pub entry_cents: i32,
    pub qty: i32,
    pub chrono: ChronoSplit,
    pub settlement_win: Option<bool>,
    pub mfe: Option<i32>,
    pub mae: Option<i32>,
    pub exit_ret: BTreeMap<String, i32>,
    pub feats: BTreeMap<String, String>,
}

#[derive(Clone, Debug, Default, serde::Serialize)]
pub struct SplitMetrics {
    pub n_entries: usize,
    pub n_unique_games: usize,
    pub entries_per_game: f64,
    pub median_entries_per_game: f64,
    pub max_entries_per_game: usize,
    pub win_rate: Option<f64>,
    pub exit_positive_rate: Option<f64>,
    pub mean_return_cents: Option<f64>,
    pub median_return_cents: Option<i32>,
    pub ev_cents: Option<f64>,
    pub total_pnl_cents: i32,
    pub total_pnl_usd: f64,
    pub return_pct_of_50: f64,
    pub stdev_pnl_cents: Option<f64>,
    pub sharpe_game_unann: Option<f64>,
    pub sharpe_monthly_ann: Option<f64>,
    pub sortino_game_unann: Option<f64>,
    pub max_dd_cents: i32,
    pub max_dd_usd: f64,
    pub mean_mfe_cents: Option<f64>,
    pub mean_mae_cents: Option<f64>,
    pub best_trade_cents: Option<i32>,
    pub worst_trade_cents: Option<i32>,
    pub profit_factor: Option<f64>,
    pub longest_win_streak: u32,
    pub longest_lose_streak: u32,
}

#[derive(Clone, Debug, serde::Serialize)]
pub struct Candidate {
    pub id: String,
    pub entry: String,
    pub exit: String,
    pub condition: String,
    pub tier: u8,
    pub fill_status: &'static str,
    pub research_status: String,
    pub train: SplitMetrics,
    pub validation: SplitMetrics,
    pub test: SplitMetrics,
    pub all: SplitMetrics,
    pub train_p_ev_le0: Option<f64>,
    pub bh_q: Option<f64>,
    pub bh_reject_q10: bool,
    pub robust_score: f64,
    pub month_concentration: f64,
    pub one_month_domination: bool,
}

pub fn flatten(s: &B1EntrySnapshot) -> SearchRow {
    let date = s
        .official_date
        .clone()
        .unwrap_or_else(|| s.entry_timestamp.date_naive().to_string());
    let month = date.chars().take(7).collect::<String>();
    let mut exit_ret = BTreeMap::new();
    for e in EXITS {
        if let Some(r) = s.a1_targets.outcome(e).and_then(|x| x.return_cents) {
            exit_ret.insert((*e).to_string(), r);
        }
    }
    let mut feats = BTreeMap::new();
    feats.insert(
        "inning_band".into(),
        inning_band(s.baseball.inning).to_string(),
    );
    feats.insert(
        "lead_regime".into(),
        lead_regime(s.baseball.bound_team_lead).to_string(),
    );
    feats.insert(
        "score_bucket".into(),
        s.baseball.score_bucket.as_str().to_string(),
    );
    feats.insert(
        "outs".into(),
        s.baseball
            .outs
            .map(|o| o.to_string())
            .unwrap_or_else(|| "NA".into()),
    );
    feats.insert(
        "base_class".into(),
        s.baseball.base_class.as_str().to_string(),
    );
    feats.insert("regime".into(), s.baseball.regime.as_str().to_string());
    feats.insert(
        "start_sentiment".into(),
        s.starting_market.start_sentiment.as_str().to_string(),
    );
    feats.insert(
        "start_price_band".into(),
        s.starting_market
            .start_bucket
            .clone()
            .unwrap_or_else(|| "NA".into()),
    );
    feats.insert(
        "personality".into(),
        s.market_history.personality.as_str().to_string(),
    );
    feats.insert(
        "late_6_9_lead2".into(),
        if s.baseball.inning.is_some_and(|i| (6..=9).contains(&i))
            && s.baseball.bound_team_lead.is_some_and(|l| l >= 2)
        {
            "YES"
        } else {
            "NO"
        }
        .into(),
    );
    let run = s
        .event_response
        .responses
        .iter()
        .find(|r| r.event_class == "RUN")
        .and_then(|r| r.last_delta_cents);
    feats.insert("event_run_sign".into(), sign_bucket(run).to_string());
    SearchRow {
        game_id: s.game_id.clone(),
        date,
        month,
        entry_cents: s.entry_trade_price_cents,
        qty: qty_for_entry(s.entry_trade_price_cents),
        chrono: ChronoSplit::Train,
        settlement_win: match s.outcomes.settlement {
            SettlementOutcome::Win => Some(true),
            SettlementOutcome::Loss => Some(false),
            _ => None,
        },
        mfe: s.outcomes.mfe_cents,
        mae: s.outcomes.mae_cents,
        exit_ret,
        feats,
    }
}

fn inning_band(inn: Option<u8>) -> &'static str {
    match inn {
        None => "NA",
        Some(i) if i <= 3 => "EARLY",
        Some(i) if i <= 6 => "MID",
        Some(i) if i <= 8 => "LATE",
        Some(9) => "NINTH",
        Some(_) => "EXTRA",
    }
}

fn lead_regime(lead: Option<i32>) -> &'static str {
    match lead {
        None => "NA",
        Some(l) if l >= 2 => "LEAD",
        Some(l) if l <= -2 => "TRAIL",
        Some(_) => "CLOSE",
    }
}

fn sign_bucket(v: Option<i32>) -> &'static str {
    match v {
        None => "NA",
        Some(x) if x > 0 => "UP",
        Some(x) if x < 0 => "DOWN",
        Some(_) => "FLAT",
    }
}

pub fn chronological_60_20_20(rows: &mut [SearchRow]) -> (String, String, String) {
    let mut dates: Vec<String> = rows.iter().map(|r| r.date.clone()).collect();
    dates.sort();
    dates.dedup();
    let n = dates.len().max(1);
    let i1 = (n * 60) / 100;
    let i2 = (n * 80) / 100;
    let tcut = dates[i1.min(n - 1)].clone();
    let vcut = dates[i2.min(n - 1)].clone();
    for r in rows.iter_mut() {
        r.chrono = if r.date < tcut {
            ChronoSplit::Train
        } else if r.date < vcut {
            ChronoSplit::Validation
        } else {
            ChronoSplit::Test
        };
    }
    (tcut, vcut, dates.last().cloned().unwrap_or_default())
}

pub fn tertile_cuts(mut xs: Vec<i32>) -> Option<(i32, i32)> {
    if xs.len() < 9 {
        return None;
    }
    xs.sort_unstable();
    Some((xs[xs.len() / 3], xs[(xs.len() * 2) / 3]))
}

fn attach_tertile(rows: &mut [SearchRow], key: &str, raw: impl Fn(&SearchRow) -> Option<i32>) {
    let train: Vec<i32> = rows
        .iter()
        .filter(|r| r.chrono == ChronoSplit::Train)
        .filter_map(&raw)
        .collect();
    let Some((a, b)) = tertile_cuts(train) else {
        for r in rows.iter_mut() {
            r.feats
                .insert(key.into(), raw(r).map(|_| "NA").unwrap_or("NA").into());
        }
        return;
    };
    for r in rows.iter_mut() {
        let label = match raw(r) {
            None => "NA".into(),
            Some(v) if v <= a => "LOW".into(),
            Some(v) if v <= b => "MID".into(),
            Some(_) => "HIGH".into(),
        };
        r.feats.insert(key.into(), label);
    }
}

pub fn attach_train_tertiles(rows: &mut [SearchRow], snaps: &[B1EntrySnapshot]) {
    let by_id: BTreeMap<&str, &B1EntrySnapshot> =
        snaps.iter().map(|s| (s.game_id.as_str(), s)).collect();
    attach_tertile(rows, "start_move_tertile", |r| {
        by_id
            .get(r.game_id.as_str())
            .and_then(|s| s.market_history.start_to_entry_move_cents)
    });
    attach_tertile(rows, "p_start_tertile", |r| {
        by_id
            .get(r.game_id.as_str())
            .and_then(|s| s.starting_market.p_start_cents)
    });
    attach_tertile(rows, "vel_1m_tertile", |r| {
        by_id
            .get(r.game_id.as_str())
            .and_then(|s| s.price_dynamics.p_1m.delta_cents)
    });
    attach_tertile(rows, "vol_5m_tertile", |r| {
        by_id
            .get(r.game_id.as_str())
            .and_then(|s| s.market_history.volatility_5m_cents)
    });
    attach_tertile(rows, "reversal_tertile", |r| {
        by_id
            .get(r.game_id.as_str())
            .and_then(|s| s.market_history.reversal_count.map(|x| x as i32))
    });
    attach_tertile(rows, "path_eff_tertile", |r| {
        by_id
            .get(r.game_id.as_str())
            .and_then(|s| s.market_history.path_efficiency_bps)
    });
    for r in rows.iter_mut() {
        let accel = by_id
            .get(r.game_id.as_str())
            .and_then(|s| s.price_dynamics.acceleration_1m_vs_5m_e6);
        r.feats.insert(
            "accel_sign".into(),
            match accel {
                None => "NA".into(),
                Some(x) if x > 0 => "POS".into(),
                Some(x) if x < 0 => "NEG".into(),
                Some(_) => "FLAT".into(),
            },
        );
    }
}

fn entry_ok(row: &SearchRow, entry: &str) -> bool {
    match entry {
        "ENTRY_80" => row.entry_cents == 80,
        "ENTRY_81" => row.entry_cents == 81,
        "ENTRY_82" => row.entry_cents == 82,
        "ENTRY_83" => row.entry_cents == 83,
        "ENTRY_BAND_80_83" => (80..=83).contains(&row.entry_cents),
        _ => false,
    }
}

fn cond_ok(row: &SearchRow, cond: &[(String, String)]) -> bool {
    cond.iter()
        .all(|(k, v)| row.feats.get(k).is_some_and(|x| x == v))
}

pub fn metrics(rows: &[&SearchRow], exit: &str) -> SplitMetrics {
    let rows: Vec<&SearchRow> = rows
        .iter()
        .copied()
        .filter(|r| r.exit_ret.contains_key(exit))
        .collect();
    let mut by_game: BTreeMap<&str, i32> = BTreeMap::new();
    let mut pnls = Vec::new();
    let mut rets = Vec::new();
    let mut dates = Vec::new();
    let mut wins = 0usize;
    let mut decided = 0usize;
    let mut pos = 0usize;
    let mut mfe = Vec::new();
    let mut mae = Vec::new();
    for r in &rows {
        let Some(&ret) = r.exit_ret.get(exit) else {
            continue;
        };
        let pnl = ret * r.qty;
        by_game
            .entry(r.game_id.as_str())
            .and_modify(|x| *x += pnl)
            .or_insert(pnl);
        pnls.push((r.date.clone(), pnl));
        rets.push(ret);
        dates.push(r.date.clone());
        if let Some(w) = r.settlement_win {
            decided += 1;
            if w {
                wins += 1;
            }
        }
        if ret > 0 {
            pos += 1;
        }
        if let Some(v) = r.mfe {
            mfe.push(v);
        }
        if let Some(v) = r.mae {
            mae.push(v);
        }
    }
    pnls.sort_by(|a, b| a.0.cmp(&b.0));
    let game_pnls: Vec<i32> = by_game.values().copied().collect();
    let n_g = game_pnls.len();
    let counts: Vec<usize> = {
        let mut c: BTreeMap<&str, usize> = BTreeMap::new();
        for r in &rows {
            *c.entry(r.game_id.as_str()).or_default() += 1;
        }
        c.into_values().collect()
    };
    let max_epg = counts.iter().copied().max().unwrap_or(0);
    let med_epg = {
        let mut c = counts.clone();
        c.sort_unstable();
        if c.is_empty() {
            0.0
        } else {
            c[c.len() / 2] as f64
        }
    };
    let total: i32 = game_pnls.iter().sum();
    let mean_ret = if rets.is_empty() {
        None
    } else {
        Some(rets.iter().map(|v| f64::from(*v)).sum::<f64>() / rets.len() as f64)
    };
    let mut med = rets.clone();
    med.sort_unstable();
    let stdev = sample_stdev(&game_pnls.iter().map(|v| f64::from(*v)).collect::<Vec<_>>());
    let mean_pnl = if game_pnls.is_empty() {
        None
    } else {
        Some(game_pnls.iter().map(|v| f64::from(*v)).sum::<f64>() / n_g as f64)
    };
    let sharpe = match (mean_pnl, stdev) {
        (Some(m), Some(s)) if s > 0.0 => Some(m / s),
        _ => None,
    };
    let down: Vec<f64> = game_pnls.iter().map(|v| f64::from(*v).min(0.0)).collect();
    let ddev = sample_stdev(&down);
    let sortino = match (mean_pnl, ddev) {
        (Some(m), Some(s)) if s > 0.0 => Some(m / s),
        _ => None,
    };
    let mut eq = BANKROLL_CENTS;
    let mut peak = eq;
    let mut max_dd = 0;
    for (_, p) in &pnls {
        eq += p;
        peak = peak.max(eq);
        max_dd = max_dd.max(peak - eq);
    }
    let mut month: BTreeMap<String, i32> = BTreeMap::new();
    for (d, p) in &pnls {
        *month.entry(d.chars().take(7).collect()).or_default() += *p;
    }
    let month_rets: Vec<f64> = month
        .values()
        .map(|v| f64::from(*v) / f64::from(BANKROLL_CENTS))
        .collect();
    let sharpe_m = if month_rets.len() >= 3 {
        let m = month_rets.iter().sum::<f64>() / month_rets.len() as f64;
        sample_stdev(&month_rets).and_then(|s| {
            if s > 0.0 {
                Some((m / s) * (12.0_f64).sqrt())
            } else {
                None
            }
        })
    } else {
        None
    };
    let (mut ws, mut ls, mut cws, mut cls) = (0u32, 0u32, 0u32, 0u32);
    for p in game_pnls.iter() {
        if *p > 0 {
            cws += 1;
            cls = 0;
            ws = ws.max(cws);
        } else if *p < 0 {
            cls += 1;
            cws = 0;
            ls = ls.max(cls);
        }
    }
    let gains: i32 = game_pnls.iter().filter(|p| **p > 0).sum();
    let losses: i32 = game_pnls.iter().filter(|p| **p < 0).map(|p| p.abs()).sum();
    SplitMetrics {
        n_entries: rows.len(),
        n_unique_games: n_g,
        entries_per_game: if n_g == 0 {
            0.0
        } else {
            rows.len() as f64 / n_g as f64
        },
        median_entries_per_game: med_epg,
        max_entries_per_game: max_epg,
        win_rate: if decided == 0 {
            None
        } else {
            Some(wins as f64 / decided as f64)
        },
        exit_positive_rate: if rows.is_empty() {
            None
        } else {
            Some(pos as f64 / rows.len() as f64)
        },
        mean_return_cents: mean_ret,
        median_return_cents: if med.is_empty() {
            None
        } else {
            Some(med[med.len() / 2])
        },
        ev_cents: mean_ret,
        total_pnl_cents: total,
        total_pnl_usd: f64::from(total) / 100.0,
        return_pct_of_50: f64::from(total) / f64::from(BANKROLL_CENTS),
        stdev_pnl_cents: stdev,
        sharpe_game_unann: sharpe,
        sharpe_monthly_ann: sharpe_m,
        sortino_game_unann: sortino,
        max_dd_cents: max_dd,
        max_dd_usd: f64::from(max_dd) / 100.0,
        mean_mfe_cents: mean_opt(&mfe),
        mean_mae_cents: mean_opt(&mae),
        best_trade_cents: game_pnls.iter().copied().max(),
        worst_trade_cents: game_pnls.iter().copied().min(),
        profit_factor: if losses == 0 {
            None
        } else {
            Some(f64::from(gains) / f64::from(losses))
        },
        longest_win_streak: ws,
        longest_lose_streak: ls,
    }
}

fn mean_opt(xs: &[i32]) -> Option<f64> {
    if xs.is_empty() {
        None
    } else {
        Some(xs.iter().map(|v| f64::from(*v)).sum::<f64>() / xs.len() as f64)
    }
}

fn sample_stdev(xs: &[f64]) -> Option<f64> {
    if xs.len() < 2 {
        return None;
    }
    let m = xs.iter().sum::<f64>() / xs.len() as f64;
    let v = xs.iter().map(|x| (x - m) * (x - m)).sum::<f64>() / (xs.len() - 1) as f64;
    Some(v.sqrt())
}

fn erf_approx(x: f64) -> f64 {
    let ax = x.abs();
    let t = 1.0 / (1.0 + 0.3275911 * ax);
    let y = 1.0
        - (((((1.061405429 * t - 1.453152027) * t) + 1.421413741) * t - 0.284496736) * t
            + 0.254829592)
            * t
            * (-x * x).exp();
    y.copysign(x)
}

pub fn p_mean_le0(pnls: &[f64]) -> Option<f64> {
    if pnls.len() < 3 {
        return None;
    }
    let m = pnls.iter().sum::<f64>() / pnls.len() as f64;
    let s = sample_stdev(pnls)?;
    if s == 0.0 {
        return Some(if m > 0.0 { 0.0 } else { 1.0 });
    }
    let z = m / (s / (pnls.len() as f64).sqrt());
    Some(0.5 * (1.0 - erf_approx(z / std::f64::consts::SQRT_2)))
}

pub fn benjamini_hochberg(p: &mut [(String, f64)], q: f64) -> BTreeSet<String> {
    p.sort_by(|a, b| a.1.partial_cmp(&b.1).unwrap_or(std::cmp::Ordering::Equal));
    let m = p.len() as f64;
    let mut keep = BTreeSet::new();
    let mut max_k = None;
    for (i, (id, pv)) in p.iter().enumerate() {
        let thresh = q * ((i + 1) as f64) / m;
        if *pv <= thresh {
            max_k = Some(i);
        }
        let _ = id;
    }
    if let Some(k) = max_k {
        for (id, _) in p.iter().take(k + 1) {
            keep.insert(id.clone());
        }
    }
    keep
}

fn month_concentration(rows: &[&SearchRow], exit: &str) -> f64 {
    let mut m: BTreeMap<String, i32> = BTreeMap::new();
    let mut tot = 0i32;
    for r in rows {
        if let Some(&ret) = r.exit_ret.get(exit) {
            let p = ret * r.qty;
            tot += p;
            *m.entry(r.month.clone()).or_default() += p;
        }
    }
    if tot <= 0 {
        return 1.0;
    }
    m.values()
        .map(|v| f64::from(*v.max(&0)) / f64::from(tot))
        .fold(0.0, f64::max)
}

fn robust_score(c: &Candidate) -> f64 {
    let ts = c.test.sharpe_game_unann.unwrap_or(0.0).clamp(-2.0, 3.0);
    let vs = c
        .validation
        .sharpe_game_unann
        .unwrap_or(0.0)
        .clamp(-2.0, 3.0);
    let ev_sign = if c.test.total_pnl_cents > 0 {
        1.0
    } else {
        -1.0
    };
    let ev_mag = (c.test.total_pnl_usd.abs() + 1.0).ln();
    let games = ((c.test.n_unique_games as f64 + 1.0).ln()) / (401.0_f64).ln();
    let conc = 1.0 - c.month_concentration.min(1.0);
    let dd = 1.0 - (c.test.max_dd_usd / 50.0).min(1.0);
    0.35 * ts + 0.25 * ev_sign * ev_mag + 0.15 * vs + 0.10 * games + 0.10 * conc + 0.05 * dd
}

fn classify(c: &Candidate) -> String {
    if c.train.n_unique_games < 20 || c.train.ev_cents.unwrap_or(0.0) <= 0.0 {
        return "REJECTED".into();
    }
    if c.validation.ev_cents.unwrap_or(0.0) <= 0.0 {
        return "WEAK_AFTER_VALIDATION".into();
    }
    if c.test.ev_cents.unwrap_or(0.0) <= 0.0 {
        return "IN_SAMPLE_ONLY".into();
    }
    if c.test.n_unique_games >= 50
        && c.test.sharpe_game_unann.unwrap_or(0.0) > 0.0
        && !c.one_month_domination
        && c.bh_reject_q10
    {
        return "ROBUST_CANDIDATE".into();
    }
    if c.test.ev_cents.unwrap_or(0.0) > 0.0 {
        return "PROMISING_BUT_UNCONFIRMED".into();
    }
    "REJECTED".into()
}

fn slice<'a>(
    rows: &'a [SearchRow],
    split: Option<ChronoSplit>,
    entry: &str,
    cond: &[(String, String)],
) -> Vec<&'a SearchRow> {
    rows.iter()
        .filter(|r| split.is_none_or(|s| r.chrono == s) && entry_ok(r, entry) && cond_ok(r, cond))
        .collect()
}

fn families() -> &'static [&'static str] {
    &[
        "inning_band",
        "lead_regime",
        "score_bucket",
        "outs",
        "base_class",
        "regime",
        "start_sentiment",
        "start_price_band",
        "start_move_tertile",
        "p_start_tertile",
        "vel_1m_tertile",
        "accel_sign",
        "personality",
        "reversal_tertile",
        "vol_5m_tertile",
        "event_run_sign",
        "late_6_9_lead2",
        "path_eff_tertile",
    ]
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

fn eval_candidate(
    rows: &[SearchRow],
    entry: &str,
    exit: &str,
    cond: &[(String, String)],
    tier: u8,
) -> Option<Candidate> {
    let train = slice(rows, Some(ChronoSplit::Train), entry, cond);
    if train.len() < 8 {
        return None;
    }
    let condition = if cond.is_empty() {
        "ALL".into()
    } else {
        cond.iter()
            .map(|(k, v)| format!("{k}={v}"))
            .collect::<Vec<_>>()
            .join("&")
    };
    let id = format!("{entry}|{exit}|{condition}");
    let val = slice(rows, Some(ChronoSplit::Validation), entry, cond);
    let test = slice(rows, Some(ChronoSplit::Test), entry, cond);
    let all = slice(rows, None, entry, cond);
    let train_m = metrics(&train, exit);
    if train_m.n_unique_games < 8 {
        return None;
    }
    let all_m = metrics(&all, exit);
    let conc = month_concentration(&all, exit);
    let train_pnls: Vec<f64> = {
        let mut g: BTreeMap<&str, i32> = BTreeMap::new();
        for r in &train {
            if let Some(&ret) = r.exit_ret.get(exit) {
                *g.entry(r.game_id.as_str()).or_default() += ret * r.qty;
            }
        }
        g.values().map(|v| f64::from(*v)).collect()
    };
    let mut c = Candidate {
        id,
        entry: entry.into(),
        exit: exit.into(),
        condition,
        tier,
        fill_status: FILL_STATUS,
        research_status: String::new(),
        train: train_m,
        validation: metrics(&val, exit),
        test: metrics(&test, exit),
        all: all_m,
        train_p_ev_le0: p_mean_le0(&train_pnls),
        bh_q: None,
        bh_reject_q10: false,
        robust_score: 0.0,
        month_concentration: conc,
        one_month_domination: conc >= 0.60,
    };
    c.robust_score = robust_score(&c);
    Some(c)
}

pub fn generate_candidates(rows: &[SearchRow]) -> Vec<Candidate> {
    let mut out = Vec::new();
    let pairs: &[(&str, &str)] = &[
        ("inning_band", "start_sentiment"),
        ("inning_band", "start_move_tertile"),
        ("lead_regime", "start_move_tertile"),
        ("start_sentiment", "start_move_tertile"),
        ("vel_1m_tertile", "accel_sign"),
        ("personality", "vol_5m_tertile"),
        ("event_run_sign", "vel_1m_tertile"),
        ("regime", "start_sentiment"),
        ("late_6_9_lead2", "start_sentiment"),
        ("late_6_9_lead2", "start_move_tertile"),
        ("score_bucket", "start_move_tertile"),
        ("personality", "start_sentiment"),
    ];
    let triples: &[(&str, &str, &str)] = &[
        ("regime", "start_sentiment", "start_move_tertile"),
        ("late_6_9_lead2", "start_sentiment", "start_move_tertile"),
        ("inning_band", "vel_1m_tertile", "vol_5m_tertile"),
        ("start_sentiment", "start_move_tertile", "vel_1m_tertile"),
        ("start_sentiment", "start_move_tertile", "personality"),
        ("lead_regime", "start_sentiment", "personality"),
    ];
    for entry in ENTRY_KEYS {
        for exit in EXITS {
            if let Some(c) = eval_candidate(rows, entry, exit, &[], 0) {
                out.push(c);
            }
            for fam in families() {
                for v in observed(rows, fam) {
                    if let Some(c) = eval_candidate(rows, entry, exit, &[(fam.to_string(), v)], 1) {
                        out.push(c);
                    }
                }
            }
            for (a, b) in pairs {
                for va in observed(rows, a) {
                    for vb in observed(rows, b) {
                        if let Some(c) = eval_candidate(
                            rows,
                            entry,
                            exit,
                            &[(a.to_string(), va.clone()), (b.to_string(), vb)],
                            2,
                        ) {
                            if c.train.n_unique_games >= 20 {
                                out.push(c);
                            }
                        }
                    }
                }
            }
            for (a, b, d) in triples {
                for va in observed(rows, a) {
                    for vb in observed(rows, b) {
                        for vd in observed(rows, d) {
                            if let Some(c) = eval_candidate(
                                rows,
                                entry,
                                exit,
                                &[
                                    (a.to_string(), va.clone()),
                                    (b.to_string(), vb.clone()),
                                    (d.to_string(), vd),
                                ],
                                3,
                            ) {
                                if c.train.n_unique_games >= 50 {
                                    out.push(c);
                                }
                            }
                        }
                    }
                }
            }
        }
    }
    let mut pvals: Vec<(String, f64)> = out
        .iter()
        .filter_map(|c| c.train_p_ev_le0.map(|p| (c.id.clone(), p)))
        .collect();
    let keep = benjamini_hochberg(&mut pvals, 0.10);
    let pmap: BTreeMap<_, _> = pvals.into_iter().collect();
    for c in &mut out {
        c.bh_q = pmap.get(&c.id).copied();
        c.bh_reject_q10 = keep.contains(&c.id);
        c.research_status = classify(c);
    }
    out
}

pub fn bootstrap_ev_ci(rows: &[&SearchRow], exit: &str, n: usize, seed: u64) -> Option<(f64, f64)> {
    let mut by_game: BTreeMap<&str, i32> = BTreeMap::new();
    for r in rows {
        if let Some(&ret) = r.exit_ret.get(exit) {
            *by_game.entry(r.game_id.as_str()).or_default() += ret * r.qty;
        }
    }
    let games: Vec<i32> = by_game.values().copied().collect();
    if games.len() < 10 {
        return None;
    }
    let mut state = seed;
    let mut means = Vec::with_capacity(n);
    for _ in 0..n {
        let mut s = 0i64;
        for _ in 0..games.len() {
            state = state.wrapping_mul(6364136223846793005).wrapping_add(1);
            let idx = (state as usize) % games.len();
            s += i64::from(games[idx]);
        }
        means.push(s as f64 / games.len() as f64);
    }
    means.sort_by(|a, b| a.partial_cmp(b).unwrap());
    Some((means[n * 25 / 1000] / 100.0, means[n * 975 / 1000] / 100.0))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn tertiles_are_order_stats() {
        let xs: Vec<i32> = (0..30).collect();
        let (a, b) = tertile_cuts(xs).unwrap();
        assert!(a < b);
    }

    #[test]
    fn qty_matches_published_convention() {
        assert_eq!(qty_for_entry(80), 7);
        assert_eq!(qty_for_entry(81), 7);
        assert_eq!(qty_for_entry(83), 7);
    }

    #[test]
    fn chrono_split_has_no_date_overlap() {
        let mut rows: Vec<SearchRow> = (0..10)
            .map(|i| SearchRow {
                game_id: format!("g{i}"),
                date: format!("2025-0{}-01", i + 1),
                month: format!("2025-0{}", i + 1),
                entry_cents: 81,
                qty: 7,
                chrono: ChronoSplit::Train,
                settlement_win: Some(true),
                mfe: None,
                mae: None,
                exit_ret: BTreeMap::new(),
                feats: BTreeMap::new(),
            })
            .collect();
        // dates 2025-01 .. 2025-10 — fix padding
        for (i, r) in rows.iter_mut().enumerate() {
            r.date = format!("2025-{:02}-01", i + 1);
            r.month = format!("2025-{:02}", i + 1);
        }
        chronological_60_20_20(&mut rows);
        let trains: BTreeSet<_> = rows
            .iter()
            .filter(|r| r.chrono == ChronoSplit::Train)
            .map(|r| r.date.as_str())
            .collect();
        let tests: BTreeSet<_> = rows
            .iter()
            .filter(|r| r.chrono == ChronoSplit::Test)
            .map(|r| r.date.as_str())
            .collect();
        assert!(trains.is_disjoint(&tests));
    }

    #[test]
    fn bh_keeps_small_p() {
        let mut p = vec![("a".into(), 0.001), ("b".into(), 0.80), ("c".into(), 0.90)];
        let keep = benjamini_hochberg(&mut p, 0.10);
        assert!(keep.contains("a"));
        assert!(!keep.contains("b"));
    }
}
