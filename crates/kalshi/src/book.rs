//! In-memory Kalshi order book from official `orderbook_snapshot` / `orderbook_delta`.
//!
//! Best YES bid is the highest remaining YES bid. Best YES ask is implied from
//! the highest remaining NO bid (`YES ask = $1 − NO bid`), which is official
//! binary-book complementarity, not a synthetic mid.

use std::collections::{BTreeMap, HashMap};

use momento_core::Price;
use momento_core::error::VenueError;

use crate::parse::{count_fp_to_hundredths, dollars_to_price_cents};
use crate::types::{OrderbookDeltaMsg, OrderbookSnapshotMsg};

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum SeqOutcome {
    Apply,
    Duplicate,
    Gap,
}

#[derive(Clone, Debug, Default)]
pub struct SeqTracker {
    last: HashMap<u64, u64>,
}

impl SeqTracker {
    pub fn new() -> Self {
        Self::default()
    }

    pub fn check(&mut self, sid: u64, seq: u64) -> SeqOutcome {
        match self.last.get(&sid).copied() {
            Some(prev) if seq <= prev => SeqOutcome::Duplicate,
            Some(prev) if seq == prev.saturating_add(1) => {
                self.last.insert(sid, seq);
                SeqOutcome::Apply
            }
            Some(_) => SeqOutcome::Gap,
            None => {
                self.last.insert(sid, seq);
                SeqOutcome::Apply
            }
        }
    }

    pub fn reset(&mut self) {
        self.last.clear();
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct BookQuote {
    pub yes_bid: Price,
    pub yes_ask: Price,
    pub yes_bid_depth: Option<u32>,
    pub yes_ask_depth: Option<u32>,
    pub ts_ms: Option<i64>,
}

#[derive(Clone, Debug, Default)]
struct MarketBook {
    yes: BTreeMap<u16, i64>,
    no: BTreeMap<u16, i64>,
    snapshot_applied: bool,
    stale: bool,
    ts_ms: Option<i64>,
}

impl MarketBook {
    fn apply_levels(
        &mut self,
        yes: Option<&Vec<[String; 2]>>,
        no: Option<&Vec<[String; 2]>>,
    ) -> Result<(), VenueError> {
        self.yes.clear();
        self.no.clear();
        if let Some(levels) = yes {
            load_side(&mut self.yes, levels)?;
        }
        if let Some(levels) = no {
            load_side(&mut self.no, levels)?;
        }
        self.snapshot_applied = true;
        self.stale = false;
        Ok(())
    }

    fn apply_delta(&mut self, side: &str, price: Price, delta: i64) -> Result<(), VenueError> {
        let book = match side {
            "yes" => &mut self.yes,
            "no" => &mut self.no,
            other => {
                return Err(VenueError::MalformedResponse(format!(
                    "orderbook_delta side {other}"
                )));
            }
        };
        let cents = price.cents();
        let next = book.get(&cents).copied().unwrap_or(0).checked_add(delta);
        let Some(qty) = next else {
            return Err(VenueError::Unrepresentable(
                "orderbook quantity overflow".into(),
            ));
        };
        if qty < 0 {
            return Err(VenueError::MalformedResponse(
                "orderbook quantity went negative".into(),
            ));
        }
        if qty == 0 {
            book.remove(&cents);
        } else {
            book.insert(cents, qty);
        }
        Ok(())
    }

    fn quote(&self) -> Option<BookQuote> {
        if !self.snapshot_applied || self.stale {
            return None;
        }
        let (yes_bid, yes_bid_depth) = best_level(&self.yes)?;
        let (no_bid, yes_ask_depth) = best_level(&self.no)?;
        let yes_ask_cents = 100u16.checked_sub(no_bid.cents())?;
        let yes_ask = Price::from_cents(yes_ask_cents).ok()?;
        if yes_bid.cents() > yes_ask.cents() {
            return None;
        }
        Some(BookQuote {
            yes_bid,
            yes_ask,
            yes_bid_depth,
            yes_ask_depth,
            ts_ms: self.ts_ms,
        })
    }
}

fn load_side(book: &mut BTreeMap<u16, i64>, levels: &[[String; 2]]) -> Result<(), VenueError> {
    for level in levels {
        let price = dollars_to_price_cents(&level[0])?;
        let qty = count_fp_to_hundredths(&level[1])?;
        if qty < 0 {
            return Err(VenueError::MalformedResponse(
                "orderbook snapshot quantity is negative".into(),
            ));
        }
        if qty == 0 {
            continue;
        }
        book.insert(price.cents(), qty);
    }
    Ok(())
}

fn best_level(book: &BTreeMap<u16, i64>) -> Option<(Price, Option<u32>)> {
    let (cents, qty) = book.iter().next_back()?;
    if *qty <= 0 {
        return None;
    }
    let price = Price::from_cents(*cents).ok()?;
    let depth = if *qty % 100 == 0 {
        u32::try_from(*qty / 100).ok()
    } else {
        None
    };
    Some((price, depth))
}

#[derive(Clone, Debug, Default)]
pub struct LocalOrderBook {
    markets: HashMap<String, MarketBook>,
    seq: SeqTracker,
    gap: bool,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct BookLevel {
    pub price_cents: u16,
    pub quantity_hundredths: i64,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct BookDepth {
    pub yes_bids: Vec<BookLevel>,
    pub no_bids: Vec<BookLevel>,
    pub snapshot_applied: bool,
    pub stale: bool,
    pub ts_ms: Option<i64>,
}

impl LocalOrderBook {
    pub fn new() -> Self {
        Self::default()
    }

    pub fn clear(&mut self) {
        self.markets.clear();
        self.seq.reset();
        self.gap = false;
    }

    pub fn has_gap(&self) -> bool {
        self.gap
    }

    pub fn market_count(&self) -> usize {
        self.markets
            .values()
            .filter(|m| m.snapshot_applied && !m.stale)
            .count()
    }

    pub fn remove(&mut self, ticker: &str) {
        self.markets.remove(ticker);
    }

    pub fn quote(&self, ticker: &str) -> Option<BookQuote> {
        if self.gap {
            return None;
        }
        self.markets.get(ticker).and_then(MarketBook::quote)
    }

    /// Apply an official snapshot. Sequence is checked per subscription `sid`.
    pub fn apply_snapshot(
        &mut self,
        sid: u64,
        seq: u64,
        msg: &OrderbookSnapshotMsg,
    ) -> Result<ApplyResult, VenueError> {
        match self.seq.check(sid, seq) {
            SeqOutcome::Duplicate => return Ok(ApplyResult::Ignored),
            SeqOutcome::Gap => {
                self.gap = true;
                return Ok(ApplyResult::Gap);
            }
            SeqOutcome::Apply => {}
        }
        let mut next = MarketBook::default();
        next.apply_levels(msg.yes_dollars_fp.as_ref(), msg.no_dollars_fp.as_ref())?;
        self.markets.insert(msg.market_ticker.clone(), next);
        Ok(ApplyResult::Updated {
            ticker: msg.market_ticker.clone(),
            quote: self
                .markets
                .get(&msg.market_ticker)
                .and_then(MarketBook::quote),
        })
    }

    pub fn apply_delta(
        &mut self,
        sid: u64,
        seq: u64,
        msg: &OrderbookDeltaMsg,
    ) -> Result<ApplyResult, VenueError> {
        match self.seq.check(sid, seq) {
            SeqOutcome::Duplicate => return Ok(ApplyResult::Ignored),
            SeqOutcome::Gap => {
                self.gap = true;
                return Ok(ApplyResult::Gap);
            }
            SeqOutcome::Apply => {}
        }
        if self.gap {
            return Ok(ApplyResult::Gap);
        }
        let Some(price_raw) = msg.price_dollars.as_deref() else {
            return Err(VenueError::MalformedResponse(
                "orderbook_delta missing price_dollars".into(),
            ));
        };
        let Some(delta_raw) = msg.delta_fp.as_deref() else {
            return Err(VenueError::MalformedResponse(
                "orderbook_delta missing delta_fp".into(),
            ));
        };
        let Some(side) = msg.side.as_deref() else {
            return Err(VenueError::MalformedResponse(
                "orderbook_delta missing side".into(),
            ));
        };
        let price = dollars_to_price_cents(price_raw)?;
        let delta = count_fp_to_hundredths(delta_raw)?;
        let Some(current) = self.markets.get(&msg.market_ticker).cloned() else {
            return Ok(ApplyResult::Unready {
                ticker: msg.market_ticker.clone(),
            });
        };
        if !current.snapshot_applied {
            return Ok(ApplyResult::Unready {
                ticker: msg.market_ticker.clone(),
            });
        }
        let mut next = current;
        next.apply_delta(side, price, delta)?;
        if let Some(ts) = msg.ts_ms {
            next.ts_ms = Some(ts);
        }
        self.markets.insert(msg.market_ticker.clone(), next);
        Ok(ApplyResult::Updated {
            ticker: msg.market_ticker.clone(),
            quote: self
                .markets
                .get(&msg.market_ticker)
                .and_then(MarketBook::quote),
        })
    }

    pub fn depth(&self, ticker: &str) -> Option<BookDepth> {
        if self.gap {
            return None;
        }
        let market = self.markets.get(ticker)?;
        if !market.snapshot_applied || market.stale {
            return None;
        }
        Some(BookDepth {
            yes_bids: levels_from_book(&market.yes),
            no_bids: levels_from_book(&market.no),
            snapshot_applied: market.snapshot_applied,
            stale: market.stale,
            ts_ms: market.ts_ms,
        })
    }

    pub fn mark_stale(&mut self, ticker: &str) {
        if let Some(market) = self.markets.get_mut(ticker) {
            market.stale = true;
        }
    }

    pub fn resync_snapshot(
        &mut self,
        sid: u64,
        seq: u64,
        msg: &OrderbookSnapshotMsg,
    ) -> Result<ApplyResult, VenueError> {
        self.seq.reset();
        self.gap = false;
        self.apply_snapshot(sid, seq, msg)
    }
}

fn levels_from_book(book: &BTreeMap<u16, i64>) -> Vec<BookLevel> {
    book.iter()
        .rev()
        .filter(|(_, qty)| **qty > 0)
        .map(|(cents, qty)| BookLevel {
            price_cents: *cents,
            quantity_hundredths: *qty,
        })
        .collect()
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub enum ApplyResult {
    Ignored,
    Gap,
    Unready {
        ticker: String,
    },
    Updated {
        ticker: String,
        quote: Option<BookQuote>,
    },
}
