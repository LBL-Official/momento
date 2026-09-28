//! Map official Kalshi payloads onto domain types. Unknown values fail closed.

use chrono::{DateTime, Utc};
use momento_core::error::VenueError;
use momento_core::{
    ClientOrderId, Contracts, ExchangeTimestamp, Fee, FeeKind, Fill, FillId, MappedOrderView,
    MomentoError, OrderState, PositionId, Price, ReceivedAt, Side, VenueMarketSnapshot,
    VenueOrderId, VenueSettlementView, contract_premium,
};

use crate::parse::{
    client_order_id_to_kalshi, count_fp_to_contracts, dollars_to_money_cents,
    dollars_to_price_cents, kalshi_to_u128,
};
use crate::types::{GetOrderbookResponse, KalshiFill, KalshiMarket, KalshiOrder};

pub fn encode_client_order_id(id: ClientOrderId) -> String {
    client_order_id_to_kalshi(id.raw())
}

pub fn decode_client_order_id(raw: &str) -> Result<ClientOrderId, VenueError> {
    Ok(ClientOrderId::from_raw(kalshi_to_u128(raw)?))
}

pub fn decode_venue_order_id(raw: &str) -> Result<VenueOrderId, VenueError> {
    Ok(VenueOrderId::from_raw(kalshi_to_u128(raw)?))
}

pub fn encode_venue_order_id(id: VenueOrderId) -> String {
    client_order_id_to_kalshi(id.raw())
}

/// GET/DELETE 404 means the venue no longer has the order. Used by reconcile
/// and occupancy release. Timeouts and 5xx must not use this path.
pub fn is_http_not_found(err: &MomentoError) -> bool {
    matches!(
        err,
        MomentoError::Venue(VenueError::MalformedResponse(s)) if s.contains("HTTP 404")
    )
}

/// Official OrderStatus is resting | canceled | executed.
/// Partial fills are expressed via fill vs remaining counts, not a status value.
pub fn map_order_state(
    status: &str,
    filled: Contracts,
    remaining: Contracts,
) -> Result<OrderState, VenueError> {
    match status {
        "resting" if filled.get() == 0 => Ok(OrderState::Working),
        "resting" if remaining.get() > 0 => Ok(OrderState::PartiallyFilled),
        "canceled" => Ok(OrderState::Cancelled),
        "executed" if remaining.get() == 0 => Ok(OrderState::Filled),
        "executed" => Err(VenueError::UnknownVenueStatus(
            "executed with remaining contracts".into(),
        )),
        "resting" if remaining.get() == 0 => Err(VenueError::UnknownVenueStatus(
            "resting with zero remaining".into(),
        )),
        other => Err(VenueError::UnknownVenueStatus(other.to_string())),
    }
}

pub fn map_order(order: &KalshiOrder) -> Result<MappedOrderView, VenueError> {
    let filled = count_fp_to_contracts(&order.fill_count_fp)?;
    let remaining = count_fp_to_contracts(&order.remaining_count_fp)?;
    let requested = count_fp_to_contracts(&order.initial_count_fp)?;
    let state = map_order_state(&order.status, filled, remaining)?;
    Ok(MappedOrderView {
        client_order_id: decode_client_order_id(&order.client_order_id)?,
        venue_order_id: decode_venue_order_id(&order.order_id)?,
        ticker: order.ticker.clone(),
        state,
        requested,
        filled,
        remaining,
    })
}

pub fn map_market(
    market: &KalshiMarket,
    received_at: ReceivedAt,
    market_id: Option<momento_core::MarketId>,
    game_id: Option<momento_core::GameId>,
) -> Result<VenueMarketSnapshot, VenueError> {
    let bid = optional_price(market.yes_bid_dollars.as_deref())?;
    let ask = optional_price(market.yes_ask_dollars.as_deref())?;
    let last = optional_price(market.last_price_dollars.as_deref())?;
    validate_price_tick_grid(market, bid, ask)?;
    let bid_depth = optional_depth(market.yes_bid_size_fp.as_deref())?;
    let ask_depth = optional_depth(market.yes_ask_size_fp.as_deref())?;
    let exchange_ts = optional_rfc3339(market.updated_time.as_deref())?;
    Ok(VenueMarketSnapshot {
        ticker: market.ticker.clone(),
        event_ticker: market.event_ticker.clone(),
        market_id,
        game_id,
        bid,
        ask,
        last,
        mid: None,
        bid_depth,
        ask_depth,
        exchange_ts,
        received_at,
    })
}

/// Official orderbook is bids-only. Best YES bid is the last `yes_dollars` level.
pub fn best_yes_bid_from_orderbook(
    book: &GetOrderbookResponse,
) -> Result<Option<Price>, VenueError> {
    let Some([price, _count]) = book.orderbook_fp.yes_dollars.last() else {
        return Ok(None);
    };
    Ok(Some(dollars_to_price_cents(price)?))
}

pub fn map_fill(
    fill: &KalshiFill,
    position_id: PositionId,
    received_at: ReceivedAt,
) -> Result<(Fill, String), VenueError> {
    let venue_fill_id = fill
        .trade_id
        .clone()
        .or_else(|| fill.fill_id.clone())
        .ok_or_else(|| VenueError::MalformedResponse("fill missing trade_id/fill_id".into()))?;
    let qty = count_fp_to_contracts(&fill.count_fp)?;
    let price_raw = fill
        .yes_price_dollars
        .as_deref()
        .ok_or_else(|| VenueError::MalformedResponse("fill missing yes_price_dollars".into()))?;
    let price = dollars_to_price_cents(price_raw)?;
    let premium =
        contract_premium(qty, price).map_err(|e| VenueError::Unrepresentable(e.to_string()))?;
    let exchange_ts = fill
        .ts_ms
        .or(fill.ts)
        .map(ts_ms)
        .or_else(|| {
            optional_rfc3339(fill.created_time.as_deref())
                .ok()
                .flatten()
        })
        .ok_or_else(|| VenueError::MalformedResponse("fill missing timestamp".into()))?;
    if fill.client_order_id.trim().is_empty() {
        return Err(VenueError::MalformedResponse(
            "fill missing client_order_id".into(),
        ));
    }
    let fill_id = FillId::from_raw(kalshi_to_u128(&venue_fill_id)?);
    let mapped = Fill::new(
        fill_id,
        position_id,
        decode_client_order_id(&fill.client_order_id)?,
        Some(decode_venue_order_id(&fill.order_id)?),
        qty,
        price,
        premium,
        Fee::zero(FeeKind::Entry),
        exchange_ts,
        received_at,
    );
    Ok((mapped, venue_fill_id))
}

pub fn mapped_order_to_snapshot(view: &MappedOrderView) -> momento_core::VenueOrderSnapshot {
    momento_core::VenueOrderSnapshot {
        presence: momento_core::OrderPresence::Found,
        venue_order_id: Some(view.venue_order_id),
        venue_status: Some(view.state),
        venue_filled: Some(view.filled),
        venue_remaining: Some(view.remaining),
        venue_fill_prices: Vec::new(),
        venue_fees: None,
        fills: Vec::new(),
        exchange_ts: None,
        contradictory: false,
        insufficient: false,
        authoritative: true,
    }
}

/// Authoritative absence after a complete live order search. Local fills
/// still force [`ReconcileOutcome::Ambiguous`] inside the tracker.
pub fn not_found_snapshot() -> momento_core::VenueOrderSnapshot {
    momento_core::VenueOrderSnapshot {
        presence: momento_core::OrderPresence::NotFound,
        venue_order_id: None,
        venue_status: None,
        venue_filled: None,
        venue_remaining: None,
        venue_fill_prices: Vec::new(),
        venue_fees: None,
        fills: Vec::new(),
        exchange_ts: None,
        contradictory: false,
        insufficient: false,
        authoritative: true,
    }
}

pub fn map_settlement(market: &KalshiMarket) -> Result<VenueSettlementView, VenueError> {
    let result = match market.result.as_deref() {
        Some("yes") => Some(Side::Yes),
        Some("no") => Some(Side::No),
        Some("") | None => None,
        Some("scalar") => {
            return Err(VenueError::Unsupported(
                "scalar settlement is unresolved".into(),
            ));
        }
        Some(other) => {
            return Err(VenueError::UnknownVenueStatus(format!(
                "settlement result {other}"
            )));
        }
    };
    let settlement_value = match market.settlement_value_dollars.as_deref() {
        Some(s) => Some(dollars_to_money_cents(s)?),
        None => None,
    };
    Ok(VenueSettlementView {
        ticker: market.ticker.clone(),
        result,
        settlement_value,
        settlement_ts: optional_rfc3339(market.settlement_ts.as_deref())?,
    })
}

fn optional_price(raw: Option<&str>) -> Result<Option<Price>, VenueError> {
    match raw {
        None | Some("") => Ok(None),
        Some(s) => dollars_to_price_cents(s).map(Some),
    }
}

/// Fail closed when `price_ranges[].step` is sub-cent or a mapped quote is off-grid.
/// Missing `price_ranges` keeps the integer-cent conversion as the domain gate.
fn validate_price_tick_grid(
    market: &KalshiMarket,
    bid: Option<Price>,
    ask: Option<Price>,
) -> Result<(), VenueError> {
    if market.price_ranges.is_empty() {
        return Ok(());
    }
    for range in &market.price_ranges {
        let Some(step_raw) = range.step.as_deref().filter(|s| !s.is_empty()) else {
            continue;
        };
        let step = dollars_to_price_cents(step_raw)?;
        let tick = step.cents();
        if tick == 0 {
            return Err(VenueError::Unrepresentable(format!(
                "price_ranges step {step_raw} is not a positive integer-cent tick"
            )));
        }
        for price in [bid, ask].into_iter().flatten() {
            if price.cents() % tick != 0 {
                return Err(VenueError::Unrepresentable(format!(
                    "price {}¢ is not aligned to tick {tick}¢",
                    price.cents()
                )));
            }
        }
    }
    Ok(())
}

fn optional_depth(raw: Option<&str>) -> Result<Option<u32>, VenueError> {
    match raw {
        None | Some("") => Ok(None),
        Some(s) => match count_fp_to_contracts(s) {
            Ok(c) => Ok(Some(c.get())),
            Err(VenueError::Unrepresentable(_)) => Ok(None),
            Err(e) => Err(e),
        },
    }
}

fn optional_rfc3339(raw: Option<&str>) -> Result<Option<ExchangeTimestamp>, VenueError> {
    match raw {
        None | Some("") => Ok(None),
        Some(s) => {
            let dt = DateTime::parse_from_rfc3339(s)
                .map_err(|e| VenueError::MalformedResponse(e.to_string()))?;
            Ok(Some(ExchangeTimestamp::from_utc(dt.with_timezone(&Utc))))
        }
    }
}

pub fn ts_ms(ms: i64) -> ExchangeTimestamp {
    let secs = ms.div_euclid(1000);
    let nanos = u32::try_from(ms.rem_euclid(1000).saturating_mul(1_000_000)).unwrap_or(0);
    let dt = DateTime::<Utc>::from_timestamp(secs, nanos).unwrap_or(DateTime::<Utc>::UNIX_EPOCH);
    ExchangeTimestamp::from_utc(dt)
}
