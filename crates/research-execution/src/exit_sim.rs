//! Exit liquidation simulation (IOC into displayed YES bid).

use chrono::Utc;

use crate::book_state::MarketBookState;
use crate::fill::SimulatedFill;
use crate::order::{FillEvidence, OrderPurpose, SimulatedOrder};
use crate::params::ExecutionParameters;

pub fn try_liquidation_fill(
    order: &mut SimulatedOrder,
    book: &MarketBookState,
    exchange_ms: i64,
    params: &ExecutionParameters,
    fill_id: u64,
) -> Option<SimulatedFill> {
    if order.remaining_quantity == 0 {
        return None;
    }
    if book.sequence_gap || !book.last_quality.supports_liquidation_simulation() {
        return None;
    }
    let bid = book.best_bid?;
    if bid == 0 {
        return None;
    }

    let available = book.best_bid_liquidity();
    if available == 0 {
        return None;
    }

    let fill_qty = available.min(order.remaining_quantity);
    if !params.allow_partial_fills && fill_qty < order.remaining_quantity {
        return None;
    }
    if fill_qty == 0 {
        return None;
    }

    let is_partial = fill_qty < order.remaining_quantity;
    order.apply_fill(fill_qty);

    Some(SimulatedFill {
        fill_id,
        order_id: order.order_id,
        position_id: order.position_id,
        market_id: order.market_id,
        ticker: order.ticker.clone(),
        side: order.outcome_side,
        purpose: OrderPurpose::Liquidation,
        price_cents: bid,
        quantity_contracts: fill_qty,
        exchange_timestamp_ms: exchange_ms,
        received_timestamp: Utc::now(),
        fill_evidence: match book.last_quality {
            crate::quality::ExecutionDataQuality::FullL2 => FillEvidence::FullL2DisplayedLiquidity,
            crate::quality::ExecutionDataQuality::TopOfBookOnly => {
                FillEvidence::TopOfBookDisplayedLiquidity
            }
            _ => FillEvidence::InsufficientData,
        },
        queue_ahead_at_fill: 0,
        is_partial,
    })
}
