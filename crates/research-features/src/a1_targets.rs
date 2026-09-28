//! A1 entry/exit research targets.
//!
//! A1 here is the research-backtest target language (`entry_price_range` +
//! `exit_price_input`), not waterfall W0-A1. Outcomes are TRADE-print modeled
//! exits. They are not fills and do not change live FIRST01.

use chrono::{DateTime, Utc};

use crate::availability::FeatureAvailability;
use crate::price_history::PricedTrade;
use crate::types::{
    A1EntryTarget, A1ExitKind, A1ExitOutcome, A1TargetFeatures, ForwardOutcomes, SettlementOutcome,
};
use crate::versions::A1_DEFAULT_ENTRY_BAND;

pub const EXIT_HOLD_TO_SETTLEMENT: &str = "HOLD_TO_SETTLEMENT";
pub const EXIT_FIRST01: &str = "FIRST01";
pub const EXIT_LIVE_50PCT_STOP: &str = "LIVE_50PCT_STOP";
pub const EXIT_HARD_75: &str = "HARD_STOP_75";
pub const EXIT_HARD_70: &str = "HARD_STOP_70";
pub const EXIT_HARD_65: &str = "HARD_STOP_65";
pub const EXIT_HARD_60: &str = "HARD_STOP_60";
pub const EXIT_HORIZON_1M: &str = "HORIZON_1M";
pub const EXIT_HORIZON_5M: &str = "HORIZON_5M";
pub const EXIT_HORIZON_15M: &str = "HORIZON_15M";
pub const EXIT_HORIZON_30M: &str = "HORIZON_30M";

const TRADE_NOT_FILL: &str = "TRADE print path. Not a demonstrated maker/taker fill.";

fn settlement_return(entry_px: i32, settlement: SettlementOutcome) -> Option<i32> {
    match settlement {
        SettlementOutcome::Win => Some(100 - entry_px),
        SettlementOutcome::Loss => Some(-entry_px),
        _ => None,
    }
}

fn hold_to_settlement(entry_px: i32, outcomes: &ForwardOutcomes) -> A1ExitOutcome {
    let ret = settlement_return(entry_px, outcomes.settlement);
    A1ExitOutcome {
        exit_target: EXIT_HOLD_TO_SETTLEMENT.to_string(),
        kind: A1ExitKind::Settlement,
        availability: if ret.is_some() {
            FeatureAvailability::Available
        } else {
            FeatureAvailability::UnavailableSource
        },
        triggered: false,
        exit_price_cents: ret.map(|r| entry_px + r),
        return_cents: ret,
        exit_timestamp: None,
        source_observation_id: None,
        note: format!("W6 settlement label. {TRADE_NOT_FILL}"),
    }
}

fn first_stop(
    future: &[PricedTrade<'_>],
    entry_px: i32,
    threshold: i32,
    name: &str,
    outcomes: &ForwardOutcomes,
) -> A1ExitOutcome {
    if let Some(hit) = future.iter().find(|t| t.price <= threshold) {
        return A1ExitOutcome {
            exit_target: name.to_string(),
            kind: A1ExitKind::ModeledStop,
            availability: FeatureAvailability::Available,
            triggered: true,
            exit_price_cents: Some(hit.price),
            return_cents: Some(hit.price - entry_px),
            exit_timestamp: Some(hit.ts),
            source_observation_id: Some(hit.observation_id.to_string()),
            note: format!("First TRADE <= {threshold} after entry. {TRADE_NOT_FILL}"),
        };
    }
    let hold = hold_to_settlement(entry_px, outcomes);
    A1ExitOutcome {
        exit_target: name.to_string(),
        kind: A1ExitKind::ModeledStop,
        availability: hold.availability,
        triggered: false,
        exit_price_cents: hold.exit_price_cents,
        return_cents: hold.return_cents,
        exit_timestamp: None,
        source_observation_id: None,
        note: format!(
            "Stop {threshold} never printed; fallback is W6 settlement. {TRADE_NOT_FILL}"
        ),
    }
}

fn horizon(
    future: &[PricedTrade<'_>],
    entry: DateTime<Utc>,
    entry_px: i32,
    secs: i64,
    name: &str,
) -> A1ExitOutcome {
    let deadline = entry + chrono::Duration::seconds(secs);
    match future.iter().rev().find(|t| t.ts <= deadline) {
        Some(t) => A1ExitOutcome {
            exit_target: name.to_string(),
            kind: A1ExitKind::ModeledHorizon,
            availability: FeatureAvailability::Available,
            triggered: true,
            exit_price_cents: Some(t.price),
            return_cents: Some(t.price - entry_px),
            exit_timestamp: Some(t.ts),
            source_observation_id: Some(t.observation_id.to_string()),
            note: format!("Last TRADE in (entry, entry+{secs}s]. {TRADE_NOT_FILL}"),
        },
        None => A1ExitOutcome {
            exit_target: name.to_string(),
            kind: A1ExitKind::ModeledHorizon,
            availability: FeatureAvailability::InsufficientHistory,
            triggered: false,
            exit_price_cents: None,
            return_cents: None,
            exit_timestamp: None,
            source_observation_id: None,
            note: format!("No TRADE in (entry, entry+{secs}s]. {TRADE_NOT_FILL}"),
        },
    }
}

pub fn a1_targets(
    future: &[PricedTrade<'_>],
    entry: DateTime<Utc>,
    entry_px: i32,
    outcomes: &ForwardOutcomes,
) -> A1TargetFeatures {
    let entry_target = A1EntryTarget::from_entry_cents(entry_px);
    let half = entry_px / 2;
    let first01 = first_stop(future, entry_px, half, EXIT_FIRST01, outcomes);
    let mut live50 = first01.clone();
    live50.exit_target = EXIT_LIVE_50PCT_STOP.to_string();
    A1TargetFeatures {
        entry_target,
        entry_band: A1_DEFAULT_ENTRY_BAND.to_string(),
        in_default_band: entry_target.in_default_band(),
        exits: vec![
            hold_to_settlement(entry_px, outcomes),
            first01,
            live50,
            first_stop(future, entry_px, 75, EXIT_HARD_75, outcomes),
            first_stop(future, entry_px, 70, EXIT_HARD_70, outcomes),
            first_stop(future, entry_px, 65, EXIT_HARD_65, outcomes),
            first_stop(future, entry_px, 60, EXIT_HARD_60, outcomes),
            horizon(future, entry, entry_px, 60, EXIT_HORIZON_1M),
            horizon(future, entry, entry_px, 300, EXIT_HORIZON_5M),
            horizon(future, entry, entry_px, 900, EXIT_HORIZON_15M),
            horizon(future, entry, entry_px, 1800, EXIT_HORIZON_30M),
        ],
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use chrono::TimeZone;

    fn t(h: u32, m: u32, price: i32, id: &'static str) -> PricedTrade<'static> {
        PricedTrade {
            ts: Utc.with_ymd_and_hms(2025, 6, 1, h, m, 0).unwrap(),
            price,
            observation_id: id,
        }
    }

    fn win_outcomes() -> ForwardOutcomes {
        use crate::types::{FutureReturn, SettlementOutcome};
        ForwardOutcomes {
            future_1m: FutureReturn::missing(60, FeatureAvailability::InsufficientHistory),
            future_5m: FutureReturn::missing(300, FeatureAvailability::InsufficientHistory),
            future_15m: FutureReturn::missing(900, FeatureAvailability::InsufficientHistory),
            future_30m: FutureReturn::missing(1800, FeatureAvailability::InsufficientHistory),
            future_max_cents: None,
            future_min_cents: None,
            mfe_cents: None,
            mae_cents: None,
            time_to_profit_secs: None,
            time_to_loss_secs: None,
            settlement: SettlementOutcome::Win,
            settlement_home: Some(5),
            settlement_away: Some(2),
        }
    }

    #[test]
    fn fifty_pct_stop_hits_first_print_at_or_below_half() {
        let entry = Utc.with_ymd_and_hms(2025, 6, 1, 19, 0, 0).unwrap();
        let future = vec![t(19, 2, 70, "a"), t(19, 4, 40, "b"), t(19, 6, 30, "c")];
        let a1 = a1_targets(&future, entry, 81, &win_outcomes());
        let stop = a1.outcome(EXIT_LIVE_50PCT_STOP).unwrap();
        assert!(stop.triggered);
        assert_eq!(stop.exit_price_cents, Some(40));
        assert_eq!(stop.return_cents, Some(40 - 81));
        assert_eq!(stop.source_observation_id.as_deref(), Some("b"));
    }
}
