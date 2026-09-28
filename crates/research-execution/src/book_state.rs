//! Per-market book state for execution simulation.

use std::collections::BTreeMap;

use momento_research_data::{OrderbookEvent, OrderbookLevel, PublicTrade};

use crate::quality::{ExecutionDataQuality, classify_orderbook_event};

#[derive(Clone, Debug, Default)]
pub struct MarketBookState {
    pub market_id: u128,
    pub ticker: String,
    pub yes_bids: BTreeMap<u16, u32>,
    pub yes_asks: BTreeMap<u16, u32>,
    pub best_bid: Option<u16>,
    pub best_ask: Option<u16>,
    pub last_quality: ExecutionDataQuality,
    pub sequence_gap: bool,
    pub last_exchange_ms: Option<i64>,
}

impl MarketBookState {
    pub fn new(market_id: u128, ticker: impl Into<String>) -> Self {
        Self {
            market_id,
            ticker: ticker.into(),
            ..Self::default()
        }
    }

    pub fn apply_orderbook(&mut self, ob: &OrderbookEvent) {
        self.sequence_gap = ob.sequence_gap;
        self.last_quality = classify_orderbook_event(ob);
        self.last_exchange_ms = ob.exchange_timestamp_ms;
        if ob.sequence_gap {
            self.yes_bids.clear();
            self.yes_asks.clear();
            self.best_bid = None;
            self.best_ask = None;
            return;
        }

        if !ob.levels.is_empty() {
            self.yes_bids.clear();
            self.yes_asks.clear();
            for level in &ob.levels {
                self.apply_level(level);
            }
        } else if let (Some(bid), Some(ask)) = (ob.yes_bid_cents, ob.yes_ask_cents) {
            self.yes_bids.clear();
            self.yes_asks.clear();
            let bid_qty = hundredths_to_contracts(ob.yes_bid_depth_hundredths);
            let ask_qty = hundredths_to_contracts(ob.yes_ask_depth_hundredths);
            if bid_qty > 0 {
                self.yes_bids.insert(bid, bid_qty);
            }
            if ask_qty > 0 {
                self.yes_asks.insert(ask, ask_qty);
            }
        }

        self.recompute_top();
    }

    fn apply_level(&mut self, level: &OrderbookLevel) {
        let qty = hundredths_to_contracts(Some(level.quantity_hundredths));
        if qty == 0 {
            return;
        }
        if level.book_side.eq_ignore_ascii_case("yes") {
            self.yes_bids.insert(level.price_cents, qty);
        } else if level.book_side.eq_ignore_ascii_case("no") {
            // NO bid at P implies YES ask at (100 - P) for binary complementarity.
            let yes_ask = 100u16.saturating_sub(level.price_cents);
            self.yes_asks.insert(yes_ask, qty);
        }
    }

    fn recompute_top(&mut self) {
        self.best_bid = self.yes_bids.keys().next_back().copied();
        self.best_ask = self.yes_asks.keys().next().copied();
    }

    pub fn displayed_bid_at(&self, price: u16) -> u32 {
        self.yes_bids.get(&price).copied().unwrap_or(0)
    }

    pub fn ask_liquidity_at_or_below(&self, limit: u16) -> u32 {
        self.yes_asks
            .iter()
            .filter(|(p, _)| **p <= limit)
            .map(|(_, q)| *q)
            .sum()
    }

    pub fn best_ask_liquidity(&self) -> u32 {
        self.best_ask
            .and_then(|p| self.yes_asks.get(&p).copied())
            .unwrap_or(0)
    }

    pub fn best_bid_liquidity(&self) -> u32 {
        self.best_bid
            .and_then(|p| self.yes_bids.get(&p).copied())
            .unwrap_or(0)
    }

    /// Public trades only reduce queue ahead — they do not directly fill our order.
    pub fn consume_queue_from_trade(&self, trade: &PublicTrade, limit_price: u16) -> u32 {
        if trade.market_id != self.market_id {
            return 0;
        }
        if trade.yes_price_cents != limit_price {
            return 0;
        }
        hundredths_to_contracts(Some(trade.quantity_hundredths))
    }
}

pub fn hundredths_to_contracts(hundredths: Option<i64>) -> u32 {
    let h = hundredths.unwrap_or(0).max(0);
    u32::try_from(h / 100).unwrap_or(u32::MAX)
}
