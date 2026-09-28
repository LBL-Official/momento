//! TRADE-price lookbacks, path, velocity, volatility, reversals. Not bid dynamics.

use chrono::{DateTime, Utc};
use momento_research_path::PathObservation;

use crate::availability::FeatureAvailability;
use crate::types::{
    MarketHistoryFeatures, MarketPersonality, MoveDirection, PriceDynamicsFeatures, TradeLookback,
};
use crate::versions::PRICE_KIND;

#[derive(Clone, Copy)]
pub struct PricedTrade<'a> {
    pub ts: DateTime<Utc>,
    pub price: i32,
    pub observation_id: &'a str,
}

pub fn priced_at_or_before<'a>(
    path: &'a [PathObservation],
    game_id: &str,
    market_id: &str,
    side: &str,
    entry: DateTime<Utc>,
) -> Vec<PricedTrade<'a>> {
    let mut out = Vec::new();
    for o in path {
        if o.game_id != game_id || o.market_id != market_id || o.contract_side != side {
            continue;
        }
        let (Some(ts), Some(px)) = (o.market_timestamp_utc, o.trade_price_cents) else {
            continue;
        };
        if ts <= entry {
            out.push(PricedTrade {
                ts,
                price: px,
                observation_id: o.observation_id.as_str(),
            });
        }
    }
    out.sort_by_key(|t| (t.ts, t.observation_id));
    out
}

pub fn priced_after<'a>(
    path: &'a [PathObservation],
    game_id: &str,
    market_id: &str,
    side: &str,
    entry: DateTime<Utc>,
) -> Vec<PricedTrade<'a>> {
    let mut out = Vec::new();
    for o in path {
        if o.game_id != game_id || o.market_id != market_id || o.contract_side != side {
            continue;
        }
        let (Some(ts), Some(px)) = (o.market_timestamp_utc, o.trade_price_cents) else {
            continue;
        };
        if ts > entry {
            out.push(PricedTrade {
                ts,
                price: px,
                observation_id: o.observation_id.as_str(),
            });
        }
    }
    out.sort_by_key(|t| (t.ts, t.observation_id));
    out
}

fn lookback(
    prior: &[PricedTrade<'_>],
    entry: DateTime<Utc>,
    entry_px: i32,
    secs: i64,
) -> TradeLookback {
    let target = entry - chrono::Duration::seconds(secs);
    let Some(hit) = prior.iter().rev().find(|t| t.ts <= target) else {
        return TradeLookback::missing(secs, FeatureAvailability::InsufficientHistory);
    };
    let actual = (entry - hit.ts).num_seconds();
    let delta = entry_px - hit.price;
    let vel = if actual > 0 {
        Some((i64::from(delta) * 1_000_000) / actual)
    } else {
        None
    };
    TradeLookback {
        requested_horizon_secs: secs,
        availability: FeatureAvailability::Available,
        price_cents: Some(hit.price),
        feature_timestamp: Some(hit.ts),
        source_observation_id: Some(hit.observation_id.to_string()),
        lookback_actual_seconds: Some(actual),
        delta_cents: Some(delta),
        velocity_cents_per_sec_e6: vel,
    }
}

/// Realized TRADE-price volatility: population stdev of trade-to-trade ΔP, rounded cents.
pub fn realized_vol_cents(
    prior: &[PricedTrade<'_>],
    entry: DateTime<Utc>,
    window_secs: i64,
) -> Option<i32> {
    let start = entry - chrono::Duration::seconds(window_secs);
    let slice: Vec<i32> = prior
        .iter()
        .filter(|t| t.ts >= start && t.ts <= entry)
        .map(|t| t.price)
        .collect();
    if slice.len() < 2 {
        return None;
    }
    let mut diffs = Vec::new();
    for w in slice.windows(2) {
        diffs.push(i64::from(w[1] - w[0]));
    }
    if diffs.is_empty() {
        return None;
    }
    let n = diffs.len() as i64;
    let mean = diffs.iter().sum::<i64>() / n;
    let var = diffs.iter().map(|d| (d - mean) * (d - mean)).sum::<i64>() / n;
    Some((var as f64).sqrt().round() as i32)
}

pub fn path_stats(prior: &[PricedTrade<'_>]) -> MarketHistoryFeatures {
    if prior.is_empty() {
        return MarketHistoryFeatures::default();
    }
    let start = prior[0].price;
    let entry = prior[prior.len() - 1].price;
    let mut dist = 0i32;
    let mut reversals = 0u32;
    let mut prev_dir = MoveDirection::Flat;
    let mut max_p = start;
    let mut min_p = start;
    let mut peak = start;
    let mut trough = start;
    let mut max_run = 0i32;
    let mut max_dd = 0i32;
    for w in prior.windows(2) {
        let a = w[0].price;
        let b = w[1].price;
        let step = (b - a).abs();
        dist += step;
        let dir = MoveDirection::from_delta(b - a);
        if dir != MoveDirection::Flat && prev_dir != MoveDirection::Flat && dir != prev_dir {
            reversals += 1;
        }
        if dir != MoveDirection::Flat {
            prev_dir = dir;
        }
        max_p = max_p.max(b);
        min_p = min_p.min(b);
        peak = peak.max(b);
        trough = trough.min(b);
        max_run = max_run.max(peak - start);
        max_dd = max_dd.max(start - trough);
    }
    let move_cents = entry - start;
    let efficiency = if dist == 0 {
        None
    } else {
        Some((move_cents.abs() * 10_000) / dist)
    };
    let last_5_dir = if prior.len() >= 2 {
        MoveDirection::from_delta(
            prior[prior.len() - 1].price - prior[prior.len().saturating_sub(6)].price,
        )
    } else {
        MoveDirection::Flat
    };
    let personality = classify_personality(
        dist, efficiency, reversals, move_cents, last_5_dir, start, min_p, max_p,
    );
    MarketHistoryFeatures {
        start_to_entry_move_cents: Some(move_cents),
        start_to_entry_magnitude_cents: Some(move_cents.abs()),
        start_to_entry_direction: Some(MoveDirection::from_delta(move_cents)),
        start_to_entry_move_bucket: Some(move_bucket(move_cents).to_string()),
        p_max_cents: Some(max_p),
        p_min_cents: Some(min_p),
        path_distance_cents: Some(dist),
        path_efficiency_bps: efficiency,
        reversal_count: Some(reversals),
        max_run_up_cents: Some(max_run),
        max_drawdown_cents: Some(max_dd),
        volatility_1m_cents: None,
        volatility_5m_cents: None,
        volatility_15m_cents: None,
        volatility_30m_cents: None,
        volatility_5m_z_e3: None,
        volatility_z_availability: FeatureAvailability::InsufficientHistory,
        start_to_entry_move_z_e3: None,
        start_to_entry_move_z_availability: FeatureAvailability::InsufficientHistory,
        personality,
        price_kind: PRICE_KIND.to_string(),
    }
}

/// Promote a trending/unclassified path to ACCELERATING or DECELERATING
/// when 1m vs 5m TRADE velocity is available.
pub fn refine_personality(hist: &mut MarketHistoryFeatures, dyns: &PriceDynamicsFeatures) {
    let Some(accel) = dyns.acceleration_1m_vs_5m_e6 else {
        return;
    };
    let recent_up = dyns.p_1m.delta_cents.is_some_and(|d| d > 0);
    match hist.personality {
        MarketPersonality::Trending | MarketPersonality::Unclassified if recent_up => {
            if accel > 0 {
                hist.personality = MarketPersonality::Accelerating;
            } else if accel < 0 {
                hist.personality = MarketPersonality::Decelerating;
            }
        }
        _ => {}
    }
}

pub fn move_bucket(cents: i32) -> &'static str {
    if cents < 0 {
        "LT_0"
    } else if cents <= 10 {
        "0_10"
    } else if cents <= 20 {
        "10_20"
    } else if cents <= 30 {
        "20_30"
    } else {
        "GT_30"
    }
}

#[allow(clippy::too_many_arguments)]
fn classify_personality(
    dist: i32,
    efficiency: Option<i32>,
    reversals: u32,
    net: i32,
    last_dir: MoveDirection,
    start: i32,
    min_p: i32,
    max_p: i32,
) -> MarketPersonality {
    if dist <= 2 {
        return MarketPersonality::Stable;
    }
    let start_dir = MoveDirection::from_delta(net);
    if start_dir != MoveDirection::Flat && last_dir != MoveDirection::Flat && last_dir != start_dir
    {
        return MarketPersonality::Reversing;
    }
    if reversals >= 5 && efficiency.is_some_and(|e| e < 4000) {
        return MarketPersonality::Choppy;
    }
    if min_p < start && max_p > start && net.abs() <= 5 {
        return MarketPersonality::MeanReverting;
    }
    if efficiency.is_some_and(|e| e >= 7000) && reversals <= 2 {
        return MarketPersonality::Trending;
    }
    MarketPersonality::Unclassified
}

pub fn price_dynamics(
    prior: &[PricedTrade<'_>],
    entry: DateTime<Utc>,
    entry_px: i32,
) -> PriceDynamicsFeatures {
    let p1 = lookback(prior, entry, entry_px, 60);
    let p5 = lookback(prior, entry, entry_px, 300);
    let p15 = lookback(prior, entry, entry_px, 900);
    let p30 = lookback(prior, entry, entry_px, 1800);
    let (accel, accel_av) = match (p1.velocity_cents_per_sec_e6, p5.velocity_cents_per_sec_e6) {
        (Some(v1), Some(v5)) => (Some(v1 - v5), FeatureAvailability::Available),
        _ => (None, FeatureAvailability::InsufficientHistory),
    };
    PriceDynamicsFeatures {
        p_1m: p1,
        p_5m: p5,
        p_15m: p15,
        p_30m: p30,
        acceleration_1m_vs_5m_e6: accel,
        acceleration_availability: accel_av,
        price_kind: PRICE_KIND.to_string(),
    }
}

pub fn attach_volatility(
    hist: &mut MarketHistoryFeatures,
    prior: &[PricedTrade<'_>],
    entry: DateTime<Utc>,
) {
    hist.volatility_1m_cents = realized_vol_cents(prior, entry, 60);
    hist.volatility_5m_cents = realized_vol_cents(prior, entry, 300);
    hist.volatility_15m_cents = realized_vol_cents(prior, entry, 900);
    hist.volatility_30m_cents = realized_vol_cents(prior, entry, 1800);
}
