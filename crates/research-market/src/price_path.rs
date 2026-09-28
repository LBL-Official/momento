//! Capability-aware price-path research API. Never synthesizes bid/ask from trades.

use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};

use crate::error::W4Error;
use crate::types::{CandleOhlcCents, MarketObservationKind, MarketPath, MarketPoint};

/// Typed trade print. Distinct from quotes and L2.
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct TradeObservation {
    pub exchange_timestamp: DateTime<Utc>,
    pub price_cents: i32,
    pub quantity_hundredths: Option<i64>,
    pub trade_id: Option<String>,
    pub source: Option<String>,
    pub source_record_id: Option<String>,
    pub retrieval_timestamp: Option<DateTime<Utc>>,
}

/// Typed candle. OHLC stays candle; never a quote or L2 snapshot.
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct CandleObservation {
    pub exchange_timestamp: DateTime<Utc>,
    pub ohlc: CandleOhlcCents,
    pub source: Option<String>,
    pub source_record_id: Option<String>,
    pub retrieval_timestamp: Option<DateTime<Utc>>,
}

/// Typed top-of-book quote. Only when the observation kind is actually a quote.
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct QuoteObservation {
    pub exchange_timestamp: DateTime<Utc>,
    pub yes_bid_cents: Option<i32>,
    pub yes_ask_cents: Option<i32>,
    pub source: Option<String>,
    pub source_record_id: Option<String>,
}

/// Typed L2 snapshot. Only when kind is L2_SNAPSHOT.
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct L2SnapshotObservation {
    pub exchange_timestamp: DateTime<Utc>,
    pub yes_bid_cents: Option<i32>,
    pub yes_ask_cents: Option<i32>,
    pub source: Option<String>,
    pub source_record_id: Option<String>,
}

fn blocked(reason: &str) -> W4Error {
    W4Error::CapabilityBlocked(reason.into())
}

/// Observations with `exchange_timestamp <= t`. Retrieval time cannot pull in later prints.
pub fn observations_as_of(path: &MarketPath, t: DateTime<Utc>) -> Vec<&MarketPoint> {
    path.points
        .iter()
        .filter(|p| p.exchange_timestamp <= t)
        .collect()
}

pub fn chronological_trades(path: &MarketPath) -> Result<Vec<TradeObservation>, W4Error> {
    if !path.price_path_available() {
        return Err(blocked(
            "PRICE_PATH_RESEARCH blocked; no legitimate price observations",
        ));
    }
    Ok(path
        .points
        .iter()
        .filter_map(|p| {
            if p.kind != MarketObservationKind::Trade {
                return None;
            }
            Some(TradeObservation {
                exchange_timestamp: p.exchange_timestamp,
                price_cents: p.last_trade_cents?,
                quantity_hundredths: p.quantity_hundredths,
                trade_id: p.trade_id.clone(),
                source: p.source.clone(),
                source_record_id: p.source_record_id.clone(),
                retrieval_timestamp: p.retrieval_timestamp,
            })
        })
        .collect())
}

pub fn chronological_candles(path: &MarketPath) -> Result<Vec<CandleObservation>, W4Error> {
    if path.capability.price_path_research.is_blocked() {
        return Err(blocked("PRICE_PATH_RESEARCH blocked"));
    }
    Ok(path
        .points
        .iter()
        .filter_map(|p| {
            if p.kind != MarketObservationKind::Candle1m {
                return None;
            }
            Some(CandleObservation {
                exchange_timestamp: p.exchange_timestamp,
                ohlc: p.candle_ohlc.clone()?,
                source: p.source.clone(),
                source_record_id: p.source_record_id.clone(),
                retrieval_timestamp: p.retrieval_timestamp,
            })
        })
        .collect())
}

pub fn chronological_quotes(path: &MarketPath) -> Result<Vec<QuoteObservation>, W4Error> {
    if !path
        .points
        .iter()
        .any(|p| p.kind == MarketObservationKind::TopOfBook)
    {
        return Err(blocked(
            "no TOP_OF_BOOK observations; TRADES_ONLY cannot synthesize quotes",
        ));
    }
    Ok(path
        .points
        .iter()
        .filter(|p| p.kind == MarketObservationKind::TopOfBook)
        .map(|p| QuoteObservation {
            exchange_timestamp: p.exchange_timestamp,
            yes_bid_cents: p.yes_bid_cents,
            yes_ask_cents: p.yes_ask_cents,
            source: p.source.clone(),
            source_record_id: p.source_record_id.clone(),
        })
        .collect())
}

pub fn chronological_l2_snapshots(
    path: &MarketPath,
) -> Result<Vec<L2SnapshotObservation>, W4Error> {
    if path.capability.orderbook_microstructure.is_blocked() {
        return Err(blocked(
            "ORDERBOOK_MICROSTRUCTURE blocked; missing L2 is not invented",
        ));
    }
    if !path
        .points
        .iter()
        .any(|p| p.kind == MarketObservationKind::L2Snapshot)
    {
        return Err(blocked("no L2_SNAPSHOT observations on this path"));
    }
    Ok(path
        .points
        .iter()
        .filter(|p| p.kind == MarketObservationKind::L2Snapshot)
        .map(|p| L2SnapshotObservation {
            exchange_timestamp: p.exchange_timestamp,
            yes_bid_cents: p.yes_bid_cents,
            yes_ask_cents: p.yes_ask_cents,
            source: p.source.clone(),
            source_record_id: p.source_record_id.clone(),
        })
        .collect())
}

/// Fail-closed: TRADES_ONLY (and any non-quote path) cannot produce bid/ask.
pub fn synthetic_bid_ask(_path: &MarketPath) -> Result<(i32, i32), W4Error> {
    Err(blocked(
        "synthetic bid/ask from trades or candles is forbidden",
    ))
}

pub fn request_orderbook_microstructure(path: &MarketPath) -> Result<(), W4Error> {
    if path.capability.orderbook_microstructure.is_blocked() {
        return Err(blocked(
            "ORDERBOOK_MICROSTRUCTURE blocked without L2_COMPLETE/PARTIAL evidence",
        ));
    }
    Ok(())
}

pub fn request_maker_fill_simulation(path: &MarketPath) -> Result<(), W4Error> {
    if path.capability.maker_fill_simulation.is_blocked() {
        return Err(blocked("MAKER_FILL_SIMULATION blocked without L2_COMPLETE"));
    }
    Ok(())
}

pub fn first_trade(path: &MarketPath) -> Result<Option<TradeObservation>, W4Error> {
    Ok(chronological_trades(path)?.into_iter().next())
}

pub fn last_trade(path: &MarketPath) -> Result<Option<TradeObservation>, W4Error> {
    Ok(chronological_trades(path)?.into_iter().last())
}

pub fn trade_extrema_cents(path: &MarketPath) -> Result<Option<(i32, i32)>, W4Error> {
    let trades = chronological_trades(path)?;
    let mut iter = trades.iter().map(|t| t.price_cents);
    let Some(first) = iter.next() else {
        return Ok(None);
    };
    let mut min = first;
    let mut max = first;
    for c in iter {
        min = min.min(c);
        max = max.max(c);
    }
    Ok(Some((min, max)))
}

pub fn trades_as_of(path: &MarketPath, t: DateTime<Utc>) -> Result<Vec<TradeObservation>, W4Error> {
    Ok(chronological_trades(path)?
        .into_iter()
        .filter(|tr| tr.exchange_timestamp <= t)
        .collect())
}
