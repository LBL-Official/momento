//! 50% stop from actual entry-fill VWAP. Observation is YES bid.
//!
//! Stop identity is the open position: PositionId → MarketId → side.
//! A quote from another market or the opposite side cannot trigger.

use momento_core::{
    BasisPrice, Fill, MarketEvent, Position, PositionLifecycle, Price, half_entry_stop_from_fills,
    yes_bid_reaches_stop,
};

use crate::quote::ValidQuote;

pub fn stop_threshold(entry_fills: &[Fill]) -> Option<BasisPrice> {
    half_entry_stop_from_fills(entry_fills)
}

pub fn yes_bid_triggers_stop(bid: Price, entry_fills: &[Fill]) -> bool {
    match stop_threshold(entry_fills) {
        Some(stop) => yes_bid_reaches_stop(bid, stop),
        None => false,
    }
}

/// Once the 50% stop has fired, reduction continues until actual filled
/// exposure is flat. The original stop price is the trigger, not a resting
/// limit that must return.
pub fn loss_reduction_in_progress(position: &Position) -> bool {
    matches!(
        position.lifecycle(),
        PositionLifecycle::StopTriggered | PositionLifecycle::LiquidationActive
    )
}

/// True only when this quote is the position's own MarketId and side.
/// Missing position identity fails closed (cannot stop).
pub fn quote_is_position_stop_eligible(
    position: &Position,
    event: &MarketEvent,
    quote: ValidQuote,
) -> bool {
    match (position.market_id(), position.side()) {
        (Some(market_id), Some(side)) => {
            event.market_id == market_id && event.side == Some(side) && quote.side == side
        }
        _ => false,
    }
}
