//! Starting-price evidence (W1). Never equate first partition candle with market open.

use serde::{Deserialize, Serialize};

use super::observability::ObservabilityKind;

/// What the source actually supports for “where did this contract start?”
#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum StartingPriceClass {
    /// Venue `open_time` plus an observed book/trade at that instant. Not claimed in v1 lake.
    MarketOpenPrice,
    /// Earliest OBSERVED bid/ask or trade in the **lifetime** path (not merely this file).
    FirstObservedPrice,
    /// Timestamp of first observed market state; price may still be unverified.
    FirstObservedTime,
    /// Cannot prove open or lifetime-first. Default for v1 close/settled-day partitions.
    StartingPriceUnverified,
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct StartingPriceEvidence {
    pub ticker: String,
    pub game_id: String,
    pub market_id: String,
    pub class: StartingPriceClass,
    pub market_open_time_metadata: Option<String>,
    pub market_open_time_observability: ObservabilityKind,
    pub market_open_price_cents: Option<u16>,
    pub first_observed_in_partition_note: String,
    pub observability: ObservabilityKind,
}

impl StartingPriceEvidence {
    pub fn unverified_from_metadata(
        ticker: impl Into<String>,
        game_id: impl Into<String>,
        market_id: impl Into<String>,
        open_time: Option<String>,
    ) -> Self {
        let has_open = open_time.as_ref().is_some_and(|s| !s.is_empty());
        Self {
            ticker: ticker.into(),
            game_id: game_id.into(),
            market_id: market_id.into(),
            class: StartingPriceClass::StartingPriceUnverified,
            market_open_time_metadata: open_time,
            market_open_time_observability: if has_open {
                ObservabilityKind::Observed
            } else {
                ObservabilityKind::Unavailable
            },
            market_open_price_cents: None,
            first_observed_in_partition_note:
                "v1 partition is close/settled PT-day. First candle/trade in that file is NOT MARKET_OPEN_PRICE."
                    .into(),
            observability: ObservabilityKind::Unavailable,
        }
    }
}
