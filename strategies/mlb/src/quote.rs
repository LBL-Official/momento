//! Qualifying quote rules for MLB 80/81/89.
//!
//! Authoritative observation (strategy spec, 2026-08-24):
//! `qualifying_price = yes_bid_dollars` → [`momento_core::MarketEvent::bid`].
//!
//! Kalshi does not provide an official mid. This crate does **not** invent
//! `(bid+ask)/2`, does **not** use last trade, and does **not** use YES ask
//! as the 80/81/89 observation. Ask is used only to refuse crossing.

use momento_core::{MarketEvent, Price, Side};

pub const FIRST_80_CENTS: u16 = 80;
pub const CONFIRM_81_CENTS: u16 = 81;
pub const MAX_ENTRY_CENTS: u16 = 83;
pub const LOCK_89_CENTS: u16 = 89;

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct ValidQuote {
    pub side: Side,
    /// Kalshi YES bid. This is the qualifying MLB observation price.
    pub bid: Price,
    /// Kalshi YES ask. Maker-only constraint only; never the 80/81/89 input.
    pub ask: Price,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum QuoteReject {
    Stale,
    MissingSide,
    MissingBid,
    MissingAsk,
    BidAskInverted,
    ReceiptBeforeExchange,
}

pub fn validate_quote(event: &MarketEvent, data_stale: bool) -> Result<ValidQuote, QuoteReject> {
    if data_stale {
        return Err(QuoteReject::Stale);
    }
    if event.received_at.utc() < event.exchange_ts.utc() {
        return Err(QuoteReject::ReceiptBeforeExchange);
    }
    let side = event.side.ok_or(QuoteReject::MissingSide)?;
    let bid = event.bid.ok_or(QuoteReject::MissingBid)?;
    let ask = event.ask.ok_or(QuoteReject::MissingAsk)?;
    if bid.cents() > ask.cents() {
        return Err(QuoteReject::BidAskInverted);
    }
    Ok(ValidQuote { side, bid, ask })
}

/// Authoritative MLB observation: current best YES bid.
pub fn qualifying_price(quote: ValidQuote) -> Price {
    quote.bid
}

pub fn reaches_first_80(price: Price) -> bool {
    price.cents() >= FIRST_80_CENTS
}

pub fn reaches_81(price: Price) -> bool {
    price.cents() >= CONFIRM_81_CENTS
}

pub fn reaches_89(price: Price) -> bool {
    price.cents() >= LOCK_89_CENTS
}

pub fn above_max_entry(price: Price) -> bool {
    price.cents() > MAX_ENTRY_CENTS
}

pub fn in_entry_band(price: Price) -> bool {
    (FIRST_80_CENTS..=MAX_ENTRY_CENTS).contains(&price.cents())
}

/// Maker-only limit: join the YES bid in 80–83, never above 83, never at or through the ask.
pub fn maker_limit(quote: ValidQuote) -> Option<Price> {
    let limit = qualifying_price(quote);
    if !in_entry_band(limit) {
        return None;
    }
    if limit.cents() < quote.ask.cents() {
        return Some(limit);
    }
    None
}
