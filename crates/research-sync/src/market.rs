//! Load MATCHED historical trades. Trades are not quotes or L2.

use chrono::NaiveDate;
use momento_research_ingest::paths::IngestPaths;
use momento_research_market::cents::{dollars_to_cents, fp_to_hundredths};
use momento_research_market::reconstruct::market_id_hex;
use serde_json::Value;
use sha2::{Digest, Sha256};
use std::fs;
use std::path::Path;

use crate::error::W5Error;
use crate::time::normalize_source_timestamp;
use crate::types::{KIND_KALSHI_TRADE_CREATED, KIND_MISSING, MarketObservation, ObservationType};

#[derive(Clone, Debug)]
pub struct MarketTradeTape {
    pub ticker: String,
    pub market_id: String,
    pub game_pk: String,
    pub observations: Vec<MarketObservation>,
    pub malformed: usize,
    pub duplicates_dropped: usize,
    pub missing_timestamps: usize,
    pub first_observed_price_cents: Option<i32>,
}

pub fn load_matched_trade_sidecar(
    ingest_root: &Path,
    official_date: &str,
    ticker: &str,
    game_pk: &str,
) -> Result<Option<MarketTradeTape>, W5Error> {
    let date = NaiveDate::parse_from_str(official_date, "%Y-%m-%d")
        .map_err(|e| W5Error::Uncommitted(format!("official_date {official_date}: {e}")))?;
    let path = IngestPaths::new(ingest_root).landing_kalshi_matched_trades(date, ticker);
    if !path.exists() {
        return Ok(None);
    }
    let v: Value = serde_json::from_slice(&fs::read(&path)?)?;
    parse_sidecar(&v, ticker, game_pk, &path)
}

pub fn parse_sidecar(
    sidecar: &Value,
    expected_ticker: &str,
    game_pk: &str,
    path: &Path,
) -> Result<Option<MarketTradeTape>, W5Error> {
    let ticker = sidecar
        .get("ticker")
        .and_then(|x| x.as_str())
        .unwrap_or(expected_ticker);
    if ticker != expected_ticker {
        return Err(W5Error::Identity(format!(
            "sidecar ticker {ticker} != MATCHED {expected_ticker}"
        )));
    }
    let retrieved = sidecar
        .get("retrieved_at")
        .and_then(|x| x.as_str())
        .and_then(|s| normalize_source_timestamp(s).ok())
        .map(|n| n.utc);
    let trades = sidecar
        .get("trades")
        .and_then(|x| x.as_array())
        .cloned()
        .unwrap_or_default();
    let market_id = market_id_hex(expected_ticker);
    let mut seen = std::collections::HashSet::new();
    let mut observations = Vec::new();
    let mut malformed = 0usize;
    let mut duplicates_dropped = 0usize;
    let mut missing_timestamps = 0usize;
    for t in trades {
        let trade_id = t
            .get("trade_id")
            .and_then(|x| x.as_str())
            .unwrap_or("")
            .to_string();
        if !trade_id.is_empty() && !seen.insert(trade_id.clone()) {
            duplicates_dropped += 1;
            continue;
        }
        let raw_ts = t
            .get("created_time")
            .and_then(|x| x.as_str())
            .unwrap_or("")
            .to_string();
        let normalized = if raw_ts.is_empty() {
            missing_timestamps += 1;
            None
        } else {
            match normalize_source_timestamp(&raw_ts) {
                Ok(n) => Some(n.utc),
                Err(_) => {
                    missing_timestamps += 1;
                    None
                }
            }
        };
        if t.get("yes_price_dollars").is_none() && t.get("count_fp").is_none() && raw_ts.is_empty()
        {
            malformed += 1;
        }
        let cents = t
            .get("yes_price_dollars")
            .and_then(|x| x.as_str())
            .and_then(|s| dollars_to_cents(s).ok());
        let qty = t
            .get("count_fp")
            .and_then(|x| x.as_str())
            .and_then(|s| fp_to_hundredths(s).ok());
        let observation_id = observation_id(expected_ticker, &trade_id, &raw_ts);
        observations.push(MarketObservation {
            observation_id,
            market_id: market_id.clone(),
            ticker: expected_ticker.to_string(),
            game_pk: Some(game_pk.to_string()),
            observation_type: ObservationType::Trade,
            source_market_time: raw_ts,
            source_timestamp_kind: if normalized.is_some() {
                KIND_KALSHI_TRADE_CREATED.into()
            } else {
                KIND_MISSING.into()
            },
            normalized_market_time: normalized,
            retrieval_time: retrieved,
            last_trade_cents: cents,
            yes_bid_cents: None,
            yes_ask_cents: None,
            quantity_hundredths: qty,
            source_id: if trade_id.is_empty() {
                None
            } else {
                Some(trade_id)
            },
            source_lineage: path.display().to_string(),
        });
    }
    observations.sort_by(|a, b| {
        a.normalized_market_time
            .cmp(&b.normalized_market_time)
            .then(a.observation_id.cmp(&b.observation_id))
    });
    let first_observed_price_cents = observations
        .iter()
        .find_map(|o| o.normalized_market_time.and(o.last_trade_cents));
    Ok(Some(MarketTradeTape {
        ticker: expected_ticker.to_string(),
        market_id,
        game_pk: game_pk.to_string(),
        observations,
        malformed,
        duplicates_dropped,
        missing_timestamps,
        first_observed_price_cents,
    }))
}

fn observation_id(ticker: &str, trade_id: &str, ts: &str) -> String {
    format!(
        "{:x}",
        Sha256::digest(format!("obs\0{ticker}\0{trade_id}\0{ts}").as_bytes())
    )
}
