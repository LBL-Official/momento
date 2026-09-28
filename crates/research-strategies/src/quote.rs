//! Parameterized quote validation mirroring `strategies/mlb/src/quote.rs`.

use chrono::{DateTime, Utc};

use momento_core::{GameId, MarketId, Price, Side};

use crate::params::EntryParameters;

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct StrategyQuote {
    pub game_id: GameId,
    pub market_id: MarketId,
    pub ticker: String,
    pub side: Side,
    pub yes_bid_cents: u16,
    pub yes_ask_cents: u16,
    pub exchange_timestamp_ms: i64,
    pub received_timestamp: DateTime<Utc>,
    pub sequence_gap: bool,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct ValidQuote {
    pub side: Side,
    pub bid: Price,
    pub ask: Price,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum QuoteReject {
    SequenceGap,
    MissingSide,
    MissingBid,
    MissingAsk,
    BidAskInverted,
    ReceiptBeforeExchange,
}

pub fn validate_quote(
    q: &StrategyQuote,
    params: &EntryParameters,
) -> Result<ValidQuote, QuoteReject> {
    if q.sequence_gap {
        return Err(QuoteReject::SequenceGap);
    }
    if q.received_timestamp.timestamp_millis() < q.exchange_timestamp_ms {
        return Err(QuoteReject::ReceiptBeforeExchange);
    }
    let bid = Price::from_cents(q.yes_bid_cents).map_err(|_| QuoteReject::MissingBid)?;
    let ask = Price::from_cents(q.yes_ask_cents).map_err(|_| QuoteReject::MissingAsk)?;
    if params.require_bid_below_ask && bid.cents() > ask.cents() {
        return Err(QuoteReject::BidAskInverted);
    }
    Ok(ValidQuote {
        side: q.side,
        bid,
        ask,
    })
}

pub fn qualifying_price(quote: ValidQuote) -> Price {
    quote.bid
}

pub fn reaches_first_threshold(price: Price, params: &EntryParameters) -> bool {
    price.cents() >= params.first_threshold_cents
}

pub fn reaches_confirmation(price: Price, params: &EntryParameters) -> bool {
    price.cents() >= params.confirmation_threshold_cents
}

pub fn reaches_lock(price: Price, params: &EntryParameters) -> bool {
    price.cents() >= params.lock_threshold_cents
}

pub fn above_max_entry(price: Price, params: &EntryParameters) -> bool {
    price.cents() > params.maximum_entry_price_cents
}

pub fn in_entry_band(price: Price, params: &EntryParameters) -> bool {
    (params.first_threshold_cents..=params.maximum_entry_price_cents).contains(&price.cents())
}

pub fn validate_quote_for_exit(q: &StrategyQuote) -> Result<ValidQuote, QuoteReject> {
    if q.sequence_gap {
        return Err(QuoteReject::SequenceGap);
    }
    if q.received_timestamp.timestamp_millis() < q.exchange_timestamp_ms {
        return Err(QuoteReject::ReceiptBeforeExchange);
    }
    let bid = Price::from_cents(q.yes_bid_cents).map_err(|_| QuoteReject::MissingBid)?;
    let ask = Price::from_cents(q.yes_ask_cents).map_err(|_| QuoteReject::MissingAsk)?;
    if bid.cents() > ask.cents() {
        return Err(QuoteReject::BidAskInverted);
    }
    Ok(ValidQuote {
        side: q.side,
        bid,
        ask,
    })
}
pub fn maker_limit(quote: ValidQuote, params: &EntryParameters) -> Option<Price> {
    if !params.maker_only {
        return Some(qualifying_price(quote));
    }
    let limit = qualifying_price(quote);
    if !in_entry_band(limit, params) {
        return None;
    }
    if limit.cents() < quote.ask.cents() {
        return Some(limit);
    }
    None
}
