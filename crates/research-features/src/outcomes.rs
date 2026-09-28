//! Forward labels. Isolated from features. Settlement is W6 only.

use chrono::{DateTime, Utc};
use momento_research_state::StoredState;

use crate::availability::FeatureAvailability;
use crate::identity::{TeamIdentity, normalize_abbr};
use crate::price_history::PricedTrade;
use crate::types::{ForwardOutcomes, FutureReturn, SettlementOutcome};
use crate::versions::TIME_TO_THRESHOLD_CENTS;

fn last_trade_at_or_before<'a>(
    future: &'a [PricedTrade<'a>],
    deadline: DateTime<Utc>,
) -> Option<&'a PricedTrade<'a>> {
    future.iter().rev().find(|t| t.ts <= deadline)
}

fn future_return(
    future: &[PricedTrade<'_>],
    entry: DateTime<Utc>,
    entry_px: i32,
    secs: i64,
) -> FutureReturn {
    let deadline = entry + chrono::Duration::seconds(secs);
    match last_trade_at_or_before(future, deadline) {
        Some(t) => FutureReturn {
            horizon_secs: secs,
            availability: FeatureAvailability::Available,
            price_cents: Some(t.price),
            return_cents: Some(t.price - entry_px),
            outcome_timestamp: Some(t.ts),
            source_observation_id: Some(t.observation_id.to_string()),
        },
        None => FutureReturn::missing(secs, FeatureAvailability::InsufficientHistory),
    }
}

pub fn settlement_from_w6(
    final_state: Option<&StoredState>,
    game_status: Option<&str>,
    identity: Option<&TeamIdentity>,
    side: &str,
) -> (SettlementOutcome, Option<u16>, Option<u16>) {
    if game_status == Some("FINAL_TIE") {
        return (SettlementOutcome::FinalTie, None, None);
    }
    let Some(st) = final_state else {
        return (SettlementOutcome::SettlementUnavailable, None, None);
    };
    if st.score_home == st.score_away {
        return (
            SettlementOutcome::FinalTie,
            Some(st.score_home),
            Some(st.score_away),
        );
    }
    let Some(id) = identity else {
        return (
            SettlementOutcome::SettlementUnavailable,
            Some(st.score_home),
            Some(st.score_away),
        );
    };
    let winner = if st.score_home > st.score_away {
        id.home.as_str()
    } else {
        id.away.as_str()
    };
    let won = normalize_abbr(side) == normalize_abbr(winner);
    (
        if won {
            SettlementOutcome::Win
        } else {
            SettlementOutcome::Loss
        },
        Some(st.score_home),
        Some(st.score_away),
    )
}

pub fn forward_outcomes(
    future: &[PricedTrade<'_>],
    entry: DateTime<Utc>,
    entry_px: i32,
    final_state: Option<&StoredState>,
    game_status: Option<&str>,
    identity: Option<&TeamIdentity>,
    side: &str,
) -> ForwardOutcomes {
    let (settlement, sh, sa) = settlement_from_w6(final_state, game_status, identity, side);
    let mut max_p = None;
    let mut min_p = None;
    let mut ttp = None;
    let mut ttl = None;
    for t in future {
        max_p = Some(max_p.map_or(t.price, |m: i32| m.max(t.price)));
        min_p = Some(min_p.map_or(t.price, |m: i32| m.min(t.price)));
        let dt = (t.ts - entry).num_seconds();
        if ttp.is_none() && t.price >= entry_px + TIME_TO_THRESHOLD_CENTS {
            ttp = Some(dt.max(0));
        }
        if ttl.is_none() && t.price <= entry_px - TIME_TO_THRESHOLD_CENTS {
            ttl = Some(dt.max(0));
        }
    }
    ForwardOutcomes {
        future_1m: future_return(future, entry, entry_px, 60),
        future_5m: future_return(future, entry, entry_px, 300),
        future_15m: future_return(future, entry, entry_px, 900),
        future_30m: future_return(future, entry, entry_px, 1800),
        future_max_cents: max_p,
        future_min_cents: min_p,
        mfe_cents: max_p.map(|p| p - entry_px),
        mae_cents: min_p.map(|p| p - entry_px),
        time_to_profit_secs: ttp,
        time_to_loss_secs: ttl,
        settlement,
        settlement_home: sh,
        settlement_away: sa,
    }
}
