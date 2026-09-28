//! TRADES_ONLY readiness / funnel. Observability of 80/81 prints is not FIRST01 replay.

use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};

use crate::capability::MarketIdentityStatus;
use crate::couple::couple_paths;
use crate::price_path::chronological_trades;
use crate::types::{
    LifetimeCoverage, MarketCompleteness, MarketObservationKind, MarketPath, MissingSide,
    ReconstructionAnomaly,
};

/// Frozen FIRST01 baseline, used only as an observability threshold.
/// W4 does not replay FIRST01, retune 80/81/83/89, or submit orders.
pub const FIRST01_ENTRY_TOUCH_CENTS: i32 = 80;
pub const FIRST01_CONFIRM_CENTS: i32 = 81;
/// Observability threshold only. W4 does not replay FIRST01 lock semantics.
pub const FIRST01_LOCK_CENTS: i32 = 89;

/// Gaps longer than this (seconds) are counted; they are missingness, not invented prints.
pub const GAP_THRESHOLD_SECS: i64 = 60;

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct MarketReadiness {
    pub ticker: String,
    pub event_ticker: String,
    pub market_id: String,
    pub identity_status: MarketIdentityStatus,
    pub game_pk: Option<String>,
    pub completeness: MarketCompleteness,
    pub reconstruction_version: String,
    pub trade_count: usize,
    pub candle_count: usize,
    pub quote_count: usize,
    pub l2_snapshot_count: usize,
    pub observed_start: Option<DateTime<Utc>>,
    pub observed_end: Option<DateTime<Utc>>,
    pub span_secs: Option<i64>,
    pub first_trade_ts: Option<DateTime<Utc>>,
    pub last_trade_ts: Option<DateTime<Utc>>,
    pub first_trade_cents: Option<i32>,
    pub last_trade_cents: Option<i32>,
    pub min_trade_cents: Option<i32>,
    pub max_trade_cents: Option<i32>,
    pub max_gap_secs: Option<i64>,
    pub gaps_over_threshold: usize,
    pub duplicate_trade_ids: usize,
    pub conflicting_trades: usize,
    pub malformed: usize,
    pub settlement_observed: bool,
    pub market_open_from_source: bool,
    pub market_close_from_source: bool,
    pub lifetime: LifetimeCoverage,
    pub funnel_has_market_id: bool,
    pub funnel_matched_identity: bool,
    pub funnel_valid_time_coverage: bool,
    pub funnel_trade_observations: bool,
    pub funnel_eighty_observable: bool,
    #[serde(default)]
    pub funnel_eighty_nine_observable: bool,
    pub funnel_first01_trigger_observable: bool,
    pub funnel_post_trigger_path_observable: bool,
    pub funnel_outcome_observable: bool,
    pub first01_replay_sufficient: bool,
    pub price_path_research: String,
    pub orderbook_microstructure: String,
    pub maker_fill_simulation: String,
    pub game_id_linked_research: String,
    pub excluded_from_price_path: bool,
    pub exclusion_reason: Option<String>,
}

impl MarketReadiness {
    pub fn measure(path: &MarketPath, anomalies: &[ReconstructionAnomaly]) -> Self {
        let trades = chronological_trades(path).unwrap_or_default();
        let trade_count = trades.len();
        let candle_count = path
            .points
            .iter()
            .filter(|p| p.kind == MarketObservationKind::Candle1m)
            .count();
        let quote_count = path
            .points
            .iter()
            .filter(|p| p.kind == MarketObservationKind::TopOfBook)
            .count();
        let l2_snapshot_count = path
            .points
            .iter()
            .filter(|p| p.kind == MarketObservationKind::L2Snapshot)
            .count();

        let mut max_gap = None;
        let mut gaps_over = 0usize;
        for w in trades.windows(2) {
            let g = (w[1].exchange_timestamp - w[0].exchange_timestamp).num_seconds();
            max_gap = Some(max_gap.map_or(g, |m: i64| m.max(g)));
            if g > GAP_THRESHOLD_SECS {
                gaps_over += 1;
            }
        }

        let min_cents = trades.iter().map(|t| t.price_cents).min();
        let max_cents = trades.iter().map(|t| t.price_cents).max();
        let first = trades.first();
        let last = trades.last();
        let span = match (path.observed_start, path.observed_end) {
            (Some(a), Some(b)) => Some((b - a).num_seconds()),
            _ => None,
        };

        let eighty_idx = trades
            .iter()
            .position(|t| t.price_cents >= FIRST01_ENTRY_TOUCH_CENTS);
        let eighty_observable = eighty_idx.is_some();
        let first01_trigger = eighty_idx.is_some_and(|i| {
            trades[i..]
                .iter()
                .any(|t| t.price_cents >= FIRST01_CONFIRM_CENTS)
        });
        let post_trigger = eighty_idx.is_some_and(|i| trades.len() > i + 1);
        let eighty_nine_observable = trades.iter().any(|t| t.price_cents == FIRST01_LOCK_CENTS);

        let ticker_anoms: Vec<_> = anomalies
            .iter()
            .filter(|a| a.ticker == path.ticker)
            .collect();
        let duplicate_trade_ids = ticker_anoms
            .iter()
            .filter(|a| a.code == "DUPLICATE_TRADE_ID")
            .count();
        let conflicting_trades = ticker_anoms
            .iter()
            .filter(|a| a.code == "CONFLICTING_TRADE")
            .count();
        let malformed = ticker_anoms
            .iter()
            .filter(|a| {
                a.code == "UNPARSEABLE_PRICE"
                    || a.code == "MISSING_TRADE_TIME"
                    || a.code == "IMPOSSIBLE_TIMESTAMP"
                    || a.code == "MISSING_CANDLE_TIME"
            })
            .count();

        let matched = path.capability.market_identity_status == MarketIdentityStatus::Matched;
        let time_ok = path.observed_start.is_some() && path.observed_end.is_some();
        let trades_ok = trade_count > 0;
        let outcome = path.settlement.is_some();
        let first01_sufficient = matched && time_ok && trades_ok && first01_trigger && post_trigger;

        let excluded = !path.price_path_available();
        let exclusion_reason = if excluded {
            Some("PRICE_PATH_RESEARCH_BLOCKED".into())
        } else {
            None
        };

        Self {
            ticker: path.ticker.clone(),
            event_ticker: path.event_ticker.clone(),
            market_id: path.market_id.clone(),
            identity_status: path.capability.market_identity_status,
            game_pk: path.game_pk.clone(),
            completeness: path.completeness,
            reconstruction_version: path.reconstruction_version.clone(),
            trade_count,
            candle_count,
            quote_count,
            l2_snapshot_count,
            observed_start: path.observed_start,
            observed_end: path.observed_end,
            span_secs: span,
            first_trade_ts: first.map(|t| t.exchange_timestamp),
            last_trade_ts: last.map(|t| t.exchange_timestamp),
            first_trade_cents: first.map(|t| t.price_cents),
            last_trade_cents: last.map(|t| t.price_cents),
            min_trade_cents: min_cents,
            max_trade_cents: max_cents,
            max_gap_secs: max_gap,
            gaps_over_threshold: gaps_over,
            duplicate_trade_ids,
            conflicting_trades,
            malformed,
            settlement_observed: outcome,
            market_open_from_source: path.open_time.is_some(),
            market_close_from_source: path.close_time.is_some(),
            lifetime: path.lifetime_coverage,
            funnel_has_market_id: !path.market_id.is_empty(),
            funnel_matched_identity: matched,
            funnel_valid_time_coverage: time_ok,
            funnel_trade_observations: trades_ok,
            funnel_eighty_observable: eighty_observable,
            funnel_eighty_nine_observable: eighty_nine_observable,
            funnel_first01_trigger_observable: first01_trigger,
            funnel_post_trigger_path_observable: post_trigger,
            funnel_outcome_observable: outcome,
            first01_replay_sufficient: first01_sufficient,
            price_path_research: path.capability.price_path_research.as_str().into(),
            orderbook_microstructure: path.capability.orderbook_microstructure.as_str().into(),
            maker_fill_simulation: path.capability.maker_fill_simulation.as_str().into(),
            game_id_linked_research: path.capability.game_id_linked_research.as_str().into(),
            excluded_from_price_path: excluded,
            exclusion_reason,
        }
    }
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct FunnelCounts {
    pub markets: usize,
    pub has_market_id: usize,
    pub matched_identity: usize,
    pub valid_time_coverage: usize,
    pub trade_observations: usize,
    pub eighty_observable: usize,
    #[serde(default)]
    pub eighty_nine_observable: usize,
    pub first01_trigger_observable: usize,
    pub post_trigger_path_observable: usize,
    pub outcome_observable: usize,
    pub first01_replay_sufficient: usize,
}

impl FunnelCounts {
    pub fn from_rows(rows: &[MarketReadiness]) -> Self {
        Self {
            markets: rows.len(),
            has_market_id: rows.iter().filter(|r| r.funnel_has_market_id).count(),
            matched_identity: rows.iter().filter(|r| r.funnel_matched_identity).count(),
            valid_time_coverage: rows.iter().filter(|r| r.funnel_valid_time_coverage).count(),
            trade_observations: rows.iter().filter(|r| r.funnel_trade_observations).count(),
            eighty_observable: rows.iter().filter(|r| r.funnel_eighty_observable).count(),
            eighty_nine_observable: rows
                .iter()
                .filter(|r| r.funnel_eighty_nine_observable)
                .count(),
            first01_trigger_observable: rows
                .iter()
                .filter(|r| r.funnel_first01_trigger_observable)
                .count(),
            post_trigger_path_observable: rows
                .iter()
                .filter(|r| r.funnel_post_trigger_path_observable)
                .count(),
            outcome_observable: rows.iter().filter(|r| r.funnel_outcome_observable).count(),
            first01_replay_sufficient: rows.iter().filter(|r| r.first01_replay_sufficient).count(),
        }
    }
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct CoupledReadiness {
    pub event_ticker: String,
    pub both_yes: bool,
    pub missing_side: MissingSide,
    pub either_eighty_observable: bool,
}

pub fn coupled_readiness(paths: &[MarketPath], rows: &[MarketReadiness]) -> Vec<CoupledReadiness> {
    let (episodes, _) = couple_paths(paths);
    let by_ticker: std::collections::BTreeMap<&str, &MarketReadiness> =
        rows.iter().map(|r| (r.ticker.as_str(), r)).collect();
    episodes
        .into_iter()
        .map(|e| {
            let a = e
                .team_a_yes
                .as_ref()
                .and_then(|p| by_ticker.get(p.ticker.as_str()).copied());
            let b = e
                .team_b_yes
                .as_ref()
                .and_then(|p| by_ticker.get(p.ticker.as_str()).copied());
            let either = a.is_some_and(|r| r.funnel_eighty_observable)
                || b.is_some_and(|r| r.funnel_eighty_observable);
            CoupledReadiness {
                event_ticker: e.event_ticker,
                both_yes: e.missing_side == MissingSide::None,
                missing_side: e.missing_side,
                either_eighty_observable: either,
            }
        })
        .collect()
}
