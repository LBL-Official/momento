//! Conditional EV helpers. Positive mean is not a prediction.

use crate::a1_targets::{
    EXIT_FIRST01, EXIT_HARD_60, EXIT_HARD_65, EXIT_HARD_70, EXIT_HARD_75, EXIT_HOLD_TO_SETTLEMENT,
    EXIT_HORIZON_1M, EXIT_HORIZON_5M, EXIT_HORIZON_15M, EXIT_HORIZON_30M, EXIT_LIVE_50PCT_STOP,
};
use crate::types::{A1EntryTarget, B1EntrySnapshot, SampleSizeFlag, SettlementOutcome};

#[derive(Clone, Debug, PartialEq, serde::Serialize)]
pub struct ConditionReport {
    pub condition: String,
    pub n_entries: usize,
    pub n_unique_games: usize,
    pub sample_size_flag: SampleSizeFlag,
    pub win_rate: Option<f64>,
    pub baseline_win_rate: Option<f64>,
    pub lift: Option<f64>,
    pub mean_return_cents: Option<f64>,
    pub median_return_cents: Option<i32>,
    pub ev_cents: Option<f64>,
    /// P(win)×(100−entry) − P(loss)×entry using each row's own entry.
    pub settlement_ev_cents: Option<f64>,
    /// P(win)×20 − P(loss)×80. Only comparable for 80¢ entries.
    pub theoretical_ev_80_cents: Option<f64>,
    pub stdev_return_cents: Option<f64>,
    pub mean_mfe_cents: Option<f64>,
    pub mean_mae_cents: Option<f64>,
    pub baseline_mean_return_cents: Option<f64>,
    pub vs_baseline_cents: Option<f64>,
}

fn median(mut xs: Vec<i32>) -> Option<i32> {
    if xs.is_empty() {
        return None;
    }
    xs.sort_unstable();
    Some(xs[xs.len() / 2])
}

fn theoretical_ev_80(win_rate: f64) -> f64 {
    win_rate * 20.0 - (1.0 - win_rate) * 80.0
}

fn settlement_ev_at_entries(rows: &[&B1EntrySnapshot]) -> Option<f64> {
    let decided: Vec<&B1EntrySnapshot> = rows
        .iter()
        .copied()
        .filter(|r| {
            matches!(
                r.outcomes.settlement,
                SettlementOutcome::Win | SettlementOutcome::Loss
            )
        })
        .collect();
    if decided.is_empty() {
        return None;
    }
    let sum: f64 = decided
        .iter()
        .filter_map(|r| settlement_return_cents(r).map(f64::from))
        .sum();
    Some(sum / decided.len() as f64)
}

fn win_stats(rows: &[&B1EntrySnapshot]) -> (Option<f64>, usize, usize) {
    let wins = rows
        .iter()
        .filter(|r| r.outcomes.settlement == SettlementOutcome::Win)
        .count();
    let decided = rows
        .iter()
        .filter(|r| {
            matches!(
                r.outcomes.settlement,
                SettlementOutcome::Win | SettlementOutcome::Loss
            )
        })
        .count();
    let wr = if decided == 0 {
        None
    } else {
        Some(wins as f64 / decided as f64)
    };
    (wr, wins, decided)
}

pub fn condition_report<F, R>(
    all: &[B1EntrySnapshot],
    name: &str,
    pred: F,
    return_cents: R,
) -> ConditionReport
where
    F: Fn(&B1EntrySnapshot) -> bool,
    R: Fn(&B1EntrySnapshot) -> Option<i32> + Copy,
{
    let baseline: Vec<i32> = all.iter().filter_map(return_cents).collect();
    let all_refs: Vec<&B1EntrySnapshot> = all.iter().collect();
    let subset: Vec<&B1EntrySnapshot> = all.iter().filter(|r| pred(r)).collect();
    let games: std::collections::BTreeSet<&str> =
        subset.iter().map(|r| r.game_id.as_str()).collect();
    let rets: Vec<i32> = subset.iter().filter_map(|r| return_cents(r)).collect();
    let (win_rate, _, _) = win_stats(&subset);
    let (baseline_win_rate, _, _) = win_stats(&all_refs);
    let mean = if rets.is_empty() {
        None
    } else {
        Some(rets.iter().map(|v| f64::from(*v)).sum::<f64>() / rets.len() as f64)
    };
    let base_mean = if baseline.is_empty() {
        None
    } else {
        Some(baseline.iter().map(|v| f64::from(*v)).sum::<f64>() / baseline.len() as f64)
    };
    let stdev = if rets.len() >= 2 {
        let m = mean.unwrap();
        let var = rets
            .iter()
            .map(|v| {
                let d = f64::from(*v) - m;
                d * d
            })
            .sum::<f64>()
            / rets.len() as f64;
        Some(var.sqrt())
    } else {
        None
    };
    ConditionReport {
        condition: name.to_string(),
        n_entries: subset.len(),
        n_unique_games: games.len(),
        sample_size_flag: SampleSizeFlag::from_unique_games(games.len()),
        win_rate,
        baseline_win_rate,
        lift: match (win_rate, baseline_win_rate) {
            (Some(a), Some(b)) if b > 0.0 => Some(a / b),
            _ => None,
        },
        mean_return_cents: mean,
        median_return_cents: median(rets),
        ev_cents: mean,
        settlement_ev_cents: settlement_ev_at_entries(&subset),
        theoretical_ev_80_cents: win_rate.map(theoretical_ev_80),
        stdev_return_cents: stdev,
        mean_mfe_cents: {
            let xs: Vec<i32> = subset.iter().filter_map(|r| r.outcomes.mfe_cents).collect();
            if xs.is_empty() {
                None
            } else {
                Some(xs.iter().map(|v| f64::from(*v)).sum::<f64>() / xs.len() as f64)
            }
        },
        mean_mae_cents: {
            let xs: Vec<i32> = subset.iter().filter_map(|r| r.outcomes.mae_cents).collect();
            if xs.is_empty() {
                None
            } else {
                Some(xs.iter().map(|v| f64::from(*v)).sum::<f64>() / xs.len() as f64)
            }
        },
        baseline_mean_return_cents: base_mean,
        vs_baseline_cents: match (mean, base_mean) {
            (Some(a), Some(b)) => Some(a - b),
            _ => None,
        },
    }
}

pub fn settlement_return_cents(s: &B1EntrySnapshot) -> Option<i32> {
    match s.outcomes.settlement {
        SettlementOutcome::Win => Some(100 - s.entry_trade_price_cents),
        SettlementOutcome::Loss => Some(-s.entry_trade_price_cents),
        _ => None,
    }
}

pub fn a1_exit_return_cents(s: &B1EntrySnapshot, exit_target: &str) -> Option<i32> {
    s.a1_targets
        .outcome(exit_target)
        .and_then(|e| e.return_cents)
}

pub fn a1_exit_targets() -> &'static [&'static str] {
    &[
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
    ]
}

/// Broad A1 entry × exit × feature-condition matrix.
/// Uses coarse conditions only — no combinatorial explosion.
pub fn a1_bucket_matrix(all: &[B1EntrySnapshot]) -> Vec<ConditionReport> {
    let mut out = Vec::new();
    let entries = [
        ("ALL_80_83", None),
        ("ENTRY_80", Some(A1EntryTarget::Entry80)),
        ("ENTRY_81", Some(A1EntryTarget::Entry81)),
        ("ENTRY_82", Some(A1EntryTarget::Entry82)),
        ("ENTRY_83", Some(A1EntryTarget::Entry83)),
    ];
    type Cond = (&'static str, fn(&B1EntrySnapshot) -> bool);
    let conditions: &[Cond] = &[
        ("ALL", |_| true),
        ("LATE_INN_6_9_LEAD_GE2", |s| {
            s.baseball.inning.is_some_and(|i| (6..=9).contains(&i))
                && s.baseball.bound_team_lead.is_some_and(|l| l >= 2)
        }),
        ("START_UNDERDOG", |s| {
            matches!(
                s.starting_market.start_sentiment,
                crate::types::StartSentiment::Underdog
                    | crate::types::StartSentiment::StrongUnderdog
            )
        }),
        ("START_FAVORITE", |s| {
            matches!(
                s.starting_market.start_sentiment,
                crate::types::StartSentiment::Favorite
                    | crate::types::StartSentiment::StrongFavorite
            )
        }),
        ("REGIME_LATE_OR_NINTH_LEAD", |s| {
            matches!(
                s.baseball.regime,
                crate::types::BaseballRegime::LateLead | crate::types::BaseballRegime::NinthLead
            )
        }),
    ];
    for (entry_name, entry_filter) in entries {
        for exit in a1_exit_targets() {
            for (cond_name, pred) in conditions {
                let name = format!("{entry_name}|{exit}|{cond_name}");
                out.push(condition_report(
                    all,
                    &name,
                    |s| {
                        let entry_ok = match entry_filter {
                            None => s.a1_targets.in_default_band,
                            Some(t) => s.a1_targets.entry_target == t,
                        };
                        entry_ok && pred(s)
                    },
                    |s| a1_exit_return_cents(s, exit),
                ));
            }
        }
    }
    out
}
