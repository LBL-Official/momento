//! NBA / NCAAB winner-market discovery. Rejects ambiguous complements.

use serde::{Deserialize, Serialize};
use serde_json::Value;

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct DiscoveredPair {
    pub event_ticker: String,
    pub tickers: [String; 2],
    pub exchange_index: Option<i64>,
    pub complement_ok: bool,
    pub reason: Option<String>,
}

pub fn pair_from_event(event: &Value) -> Result<DiscoveredPair, String> {
    let event_ticker = event
        .get("event_ticker")
        .and_then(|v| v.as_str())
        .ok_or("EVENT_TICKER_MISSING")?
        .to_string();
    let markets = event
        .get("markets")
        .and_then(|m| m.as_array())
        .ok_or("MARKETS_MISSING")?;
    if markets.len() != 2 {
        return Ok(DiscoveredPair {
            event_ticker,
            tickers: [String::new(), String::new()],
            exchange_index: None,
            complement_ok: false,
            reason: Some("NOT_EXACTLY_TWO_MARKETS".into()),
        });
    }
    let t0 = markets[0]
        .get("ticker")
        .and_then(|v| v.as_str())
        .unwrap_or("")
        .to_string();
    let t1 = markets[1]
        .get("ticker")
        .and_then(|v| v.as_str())
        .unwrap_or("")
        .to_string();
    if t0.is_empty() || t1.is_empty() || t0 == t1 {
        return Ok(DiscoveredPair {
            event_ticker,
            tickers: [t0, t1],
            exchange_index: None,
            complement_ok: false,
            reason: Some("TICKER_INVALID".into()),
        });
    }
    let i0 = markets[0].get("exchange_index").and_then(|v| v.as_i64());
    let i1 = markets[1].get("exchange_index").and_then(|v| v.as_i64());
    if i0 != i1 {
        return Ok(DiscoveredPair {
            event_ticker,
            tickers: [t0, t1],
            exchange_index: i0,
            complement_ok: false,
            reason: Some("ROUTE_PAIR_MISMATCH".into()),
        });
    }
    let exclusive = event
        .get("mutually_exclusive")
        .and_then(|v| v.as_bool())
        .unwrap_or(false);
    if !exclusive {
        return Ok(DiscoveredPair {
            event_ticker,
            tickers: [t0, t1],
            exchange_index: i0,
            complement_ok: false,
            reason: Some("NOT_MUTUALLY_EXCLUSIVE".into()),
        });
    }
    Ok(DiscoveredPair {
        event_ticker,
        tickers: [t0, t1],
        exchange_index: i0,
        complement_ok: true,
        reason: None,
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn rejects_three_markets_and_route_mismatch() {
        let ev = serde_json::json!({
            "event_ticker": "E",
            "mutually_exclusive": true,
            "markets": [
                {"ticker": "A", "exchange_index": 3},
                {"ticker": "B", "exchange_index": 3},
                {"ticker": "C", "exchange_index": 3}
            ]
        });
        assert_eq!(
            pair_from_event(&ev).unwrap().reason.as_deref(),
            Some("NOT_EXACTLY_TWO_MARKETS")
        );
        let ev = serde_json::json!({
            "event_ticker": "E",
            "mutually_exclusive": true,
            "markets": [
                {"ticker": "A", "exchange_index": 3},
                {"ticker": "B", "exchange_index": 0}
            ]
        });
        assert_eq!(
            pair_from_event(&ev).unwrap().reason.as_deref(),
            Some("ROUTE_PAIR_MISMATCH")
        );
    }
}
