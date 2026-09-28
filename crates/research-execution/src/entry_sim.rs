//! Entry maker-fill simulation.

use chrono::Utc;

use momento_research_strategies::EntrySignal;

use crate::book_state::MarketBookState;
use crate::fill::SimulatedFill;
use crate::order::{FillEvidence, OrderPurpose, SimulatedOrder};
use crate::params::ExecutionParameters;
use crate::quality::ExecutionDataQuality;

pub fn queue_ahead_at_submit(book: &MarketBookState, limit: u16) -> u32 {
    book.displayed_bid_at(limit)
}

pub fn try_entry_fill(
    order: &mut SimulatedOrder,
    book: &MarketBookState,
    exchange_ms: i64,
    params: &ExecutionParameters,
    fill_id: u64,
) -> Option<SimulatedFill> {
    if order.remaining_quantity == 0 {
        return None;
    }
    if book.sequence_gap || !book.last_quality.supports_maker_simulation() {
        return None;
    }
    let ask = book.best_ask?;
    if ask > order.limit_price_cents {
        return None;
    }

    let sellable = if book.last_quality == ExecutionDataQuality::FullL2 {
        book.ask_liquidity_at_or_below(order.limit_price_cents)
    } else {
        book.best_ask_liquidity()
    };
    if sellable == 0 {
        return None;
    }

    let mut queue = order.queue_ahead_contracts;
    let mut available = sellable;
    if queue > 0 {
        if available <= queue {
            order.queue_ahead_contracts = queue - available;
            return None;
        }
        available -= queue;
        order.queue_ahead_contracts = 0;
        queue = 0;
    }

    let fill_qty = available.min(order.remaining_quantity);
    if !params.allow_partial_fills && fill_qty < order.remaining_quantity {
        return None;
    }
    if fill_qty == 0 {
        return None;
    }

    let price = ask;
    let is_partial = fill_qty < order.remaining_quantity;
    order.apply_fill(fill_qty);

    Some(SimulatedFill {
        fill_id,
        order_id: order.order_id,
        position_id: order.position_id,
        market_id: order.market_id,
        ticker: order.ticker.clone(),
        side: order.outcome_side,
        purpose: OrderPurpose::Entry,
        price_cents: price,
        quantity_contracts: fill_qty,
        exchange_timestamp_ms: exchange_ms,
        received_timestamp: Utc::now(),
        fill_evidence: match book.last_quality {
            ExecutionDataQuality::FullL2 => FillEvidence::FullL2DisplayedLiquidity,
            ExecutionDataQuality::TopOfBookOnly => FillEvidence::TopOfBookDisplayedLiquidity,
            _ => FillEvidence::InsufficientData,
        },
        queue_ahead_at_fill: queue,
        is_partial,
    })
}

pub fn should_create_entry_order(working: &[(u128, u128)], signal: &EntrySignal) -> bool {
    !working
        .iter()
        .any(|(market_id, game_id)| *market_id == signal.market_id && *game_id == signal.game_id)
}
