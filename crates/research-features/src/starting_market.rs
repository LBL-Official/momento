//! Layer 2 — earliest TRADE on the bound contract. Not a pregame mid.

use chrono::{DateTime, Utc};
use momento_research_path::PathObservation;

use crate::availability::FeatureAvailability;
use crate::types::{StartSentiment, StartingMarketFeatures};

pub fn start_bucket(cents: i32) -> &'static str {
    if cents < 40 {
        "LT_40"
    } else if cents < 50 {
        "40_49"
    } else if cents < 60 {
        "50_59"
    } else if cents < 70 {
        "60_69"
    } else if cents < 80 {
        "70_79"
    } else {
        "GE_80"
    }
}

/// First TRADE on the same game/market/side with timestamp ≤ entry.
pub fn starting_market(
    path: &[PathObservation],
    game_id: &str,
    market_id: &str,
    side: &str,
    entry: DateTime<Utc>,
) -> StartingMarketFeatures {
    let start = path.iter().find(|o| {
        o.game_id == game_id
            && o.market_id == market_id
            && o.contract_side == side
            && o.trade_price_cents.is_some()
            && o.market_timestamp_utc.is_some_and(|t| t <= entry)
    });
    match start {
        Some(o) => {
            let px = o.trade_price_cents.unwrap();
            StartingMarketFeatures {
                availability: FeatureAvailability::Available,
                p_start_cents: Some(px),
                starting_price_source: "TRADE".to_string(),
                start_observation_id: Some(o.observation_id.clone()),
                start_timestamp: o.market_timestamp_utc,
                start_bias_cents: Some(px - 50),
                start_bucket: Some(start_bucket(px).to_string()),
                start_sentiment: StartSentiment::from_p_start_cents(Some(px)),
                starting_bid: FeatureAvailability::UnavailableSource,
                starting_ask: FeatureAvailability::UnavailableSource,
                starting_mid: FeatureAvailability::UnavailableSource,
                starting_spread: FeatureAvailability::UnavailableSource,
            }
        }
        None => StartingMarketFeatures {
            availability: FeatureAvailability::InsufficientHistory,
            p_start_cents: None,
            starting_price_source: "TRADE".to_string(),
            start_observation_id: None,
            start_timestamp: None,
            start_bias_cents: None,
            start_bucket: None,
            start_sentiment: StartSentiment::Unavailable,
            starting_bid: FeatureAvailability::UnavailableSource,
            starting_ask: FeatureAvailability::UnavailableSource,
            starting_mid: FeatureAvailability::UnavailableSource,
            starting_spread: FeatureAvailability::UnavailableSource,
        },
    }
}
