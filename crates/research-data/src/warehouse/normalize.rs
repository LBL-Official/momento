//! Raw JSON → normalized warehouse rows. Never invent L2.

use std::collections::BTreeSet;
use std::fs;
use std::path::Path;

use chrono::{TimeZone, Utc};
use serde_json::Value;

use super::error::WarehouseError;
use super::identity::hex_u128;
use super::paths::WarehousePaths;
use super::types::{
    MARKET_DATA_TYPE_CANDLE_TOB, NbaCandleRow, NbaMarketRow, NbaTradeRow, count_fp_to_hundredths,
    dollars_to_e4, json_str, parse_rfc3339,
};
use momento_kalshi::{game_id_for_event_ticker, market_id_for_ticker};

use crate::raw::read_raw_events;

#[allow(clippy::too_many_arguments)]
pub fn parse_candle_row(
    ticker: &str,
    event_id: &str,
    candle: &Value,
    open_ts: Option<i64>,
    close_ts: Option<i64>,
    now: chrono::DateTime<Utc>,
    seen: &mut BTreeSet<(String, i64)>,
    schema_version: &str,
) -> Option<NbaCandleRow> {
    let end_ts = candle.get("end_period_ts")?.as_i64()?;
    let end_time = Utc.timestamp_opt(end_ts, 0).single()?;
    let start_time = Utc.timestamp_opt(end_ts - 60, 0).single()?;
    let is_duplicate = !seen.insert((ticker.to_string(), end_ts));
    let bid = candle.get("yes_bid");
    let ask = candle.get("yes_ask");
    let price = candle.get("price");
    let bid_close = dist_e4(bid, "close");
    let ask_close = dist_e4(ask, "close");
    let is_valid = bid_close.is_some() && ask_close.is_some();
    Some(NbaCandleRow {
        ticker: ticker.to_string(),
        event_id: event_id.to_string(),
        market_id: hex_u128(market_id_for_ticker(ticker).raw()),
        game_id: hex_u128(game_id_for_event_ticker(event_id).raw()),
        end_period_ts: end_ts,
        start_time,
        end_time,
        yes_bid_open_e4: dist_e4(bid, "open"),
        yes_bid_high_e4: dist_e4(bid, "high"),
        yes_bid_low_e4: dist_e4(bid, "low"),
        yes_bid_close_e4: bid_close,
        yes_ask_open_e4: dist_e4(ask, "open"),
        yes_ask_high_e4: dist_e4(ask, "high"),
        yes_ask_low_e4: dist_e4(ask, "low"),
        yes_ask_close_e4: ask_close,
        price_open_e4: dist_e4(price, "open"),
        price_high_e4: dist_e4(price, "high"),
        price_low_e4: dist_e4(price, "low"),
        price_close_e4: dist_e4(price, "close"),
        price_mean_e4: dist_e4(price, "mean"),
        price_previous_e4: dist_e4(price, "previous"),
        volume_hundredths: json_str(candle, "volume")
            .or_else(|| json_str(candle, "volume_fp"))
            .as_deref()
            .and_then(count_fp_to_hundredths),
        open_interest_hundredths: json_str(candle, "open_interest")
            .or_else(|| json_str(candle, "open_interest_fp"))
            .as_deref()
            .and_then(count_fp_to_hundredths),
        market_data_type: MARKET_DATA_TYPE_CANDLE_TOB.into(),
        orderbook_depth_available: false,
        is_valid,
        is_duplicate,
        is_pre_market: open_ts.is_some_and(|o| end_ts < o),
        is_post_market: close_ts.is_some_and(|c| end_ts > c),
        source: "historical_rest".into(),
        ingested_at: now,
        schema_version: schema_version.into(),
    })
}

fn dist_e4(obj: Option<&Value>, field: &str) -> Option<i64> {
    let o = obj?;
    let raw = o
        .get(field)
        .or_else(|| o.get(format!("{field}_dollars")))
        .and_then(|v| v.as_str())?;
    dollars_to_e4(raw)
}

pub fn parse_trade_row(
    ticker: &str,
    event_id: &str,
    trade: &Value,
    now: chrono::DateTime<Utc>,
    seen: &mut BTreeSet<String>,
    schema_version: &str,
) -> Option<NbaTradeRow> {
    let trade_id = json_str(trade, "trade_id")?;
    let created = json_str(trade, "created_time")?;
    let ts = parse_rfc3339(&created)?;
    let is_duplicate = !seen.insert(trade_id.clone());
    let taker_outcome = json_str(trade, "taker_outcome_side");
    let side = match taker_outcome.as_deref() {
        Some("yes") => "buy_yes".to_string(),
        Some("no") => "sell_yes".to_string(),
        Some(other) => other.to_string(),
        None => "unknown".to_string(),
    };
    Some(NbaTradeRow {
        trade_id,
        ticker: ticker.to_string(),
        event_id: event_id.to_string(),
        market_id: hex_u128(market_id_for_ticker(ticker).raw()),
        game_id: hex_u128(game_id_for_event_ticker(event_id).raw()),
        timestamp: ts,
        yes_price_e4: json_str(trade, "yes_price_dollars")
            .as_deref()
            .and_then(dollars_to_e4),
        no_price_e4: json_str(trade, "no_price_dollars")
            .as_deref()
            .and_then(dollars_to_e4),
        quantity_hundredths: json_str(trade, "count_fp")
            .as_deref()
            .and_then(count_fp_to_hundredths),
        taker_outcome_side: taker_outcome,
        taker_book_side: json_str(trade, "taker_book_side"),
        taker_side: json_str(trade, "taker_side"),
        side_classification: side,
        is_block_trade: trade
            .get("is_block_trade")
            .and_then(|v| v.as_bool())
            .unwrap_or(false),
        is_duplicate,
        source: "historical_rest".into(),
        ingested_at: now,
        schema_version: schema_version.into(),
    })
}

pub fn load_raw_candles_for_ticker(
    paths: &WarehousePaths,
    market: &NbaMarketRow,
) -> Result<Vec<NbaCandleRow>, WarehouseError> {
    let file = paths.raw_candles(&market.ticker).join("candles.jsonl.gz");
    if !file.exists() {
        return Ok(Vec::new());
    }
    let events = read_raw_events(&file)?;
    let mut seen = BTreeSet::new();
    let mut rows = Vec::new();
    let now = Utc::now();
    let open_ts = market
        .open_time
        .as_deref()
        .and_then(parse_rfc3339)
        .map(|t| t.timestamp());
    let close_ts = market
        .close_time
        .as_deref()
        .and_then(parse_rfc3339)
        .map(|t| t.timestamp());
    for ev in events {
        let candles = ev
            .payload
            .get("candlesticks")
            .and_then(|c| c.as_array())
            .cloned()
            .unwrap_or_default();
        for c in candles {
            if let Some(row) = parse_candle_row(
                &market.ticker,
                &market.event_id,
                &c,
                open_ts,
                close_ts,
                now,
                &mut seen,
                &market.schema_version,
            ) {
                rows.push(row);
            }
        }
    }
    Ok(rows)
}

pub fn load_raw_trades_for_ticker(
    paths: &WarehousePaths,
    market: &NbaMarketRow,
) -> Result<Vec<NbaTradeRow>, WarehouseError> {
    let dir = paths.raw_trades(&market.ticker);
    if !dir.exists() {
        return Ok(Vec::new());
    }
    let mut files: Vec<_> = fs::read_dir(&dir)?
        .filter_map(|e| e.ok())
        .map(|e| e.path())
        .filter(|p| {
            p.file_name()
                .and_then(|n| n.to_str())
                .is_some_and(|n| n.starts_with("page-") && n.ends_with(".jsonl.gz"))
        })
        .collect();
    files.sort();
    let mut seen = BTreeSet::new();
    let mut rows = Vec::new();
    let now = Utc::now();
    for file in files {
        for trade in super::ingest::load_raw_array(&file)? {
            if let Some(row) = parse_trade_row(
                &market.ticker,
                &market.event_id,
                &trade,
                now,
                &mut seen,
                &market.schema_version,
            ) {
                rows.push(row);
            }
        }
    }
    Ok(rows)
}

pub fn month_from_rfc_date(date: Option<&str>) -> String {
    match date {
        Some(s) if s.len() >= 7 => s[..7].to_string(),
        _ => "unknown".into(),
    }
}

pub fn month_from_ts(ts: i64) -> String {
    Utc.timestamp_opt(ts, 0)
        .single()
        .map(|t| t.format("%Y-%m").to_string())
        .unwrap_or_else(|| "unknown".into())
}

pub fn remove_dir_contents(path: &Path) -> std::io::Result<()> {
    if path.exists() {
        fs::remove_dir_all(path)?;
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::warehouse::types::SCHEMA_VERSION;
    use serde_json::json;

    #[test]
    fn candle_parse_dedup_and_no_l2() {
        let raw = json!({
            "end_period_ts": 1_700_000_060,
            "yes_bid": {"open":"0.7000","high":"0.7100","low":"0.6900","close":"0.7000"},
            "yes_ask": {"open":"0.7200","high":"0.7300","low":"0.7100","close":"0.7200"},
            "price": {"close":"0.7100","mean":"0.7246"},
            "volume": "12.50",
            "open_interest": "100.00"
        });
        let mut seen = BTreeSet::new();
        let now = Utc::now();
        let a = parse_candle_row(
            "T-SAS",
            "E",
            &raw,
            None,
            None,
            now,
            &mut seen,
            SCHEMA_VERSION,
        )
        .unwrap();
        let b = parse_candle_row(
            "T-SAS",
            "E",
            &raw,
            None,
            None,
            now,
            &mut seen,
            SCHEMA_VERSION,
        )
        .unwrap();
        assert_eq!(a.market_data_type, MARKET_DATA_TYPE_CANDLE_TOB);
        assert!(!a.orderbook_depth_available);
        assert!(a.is_valid);
        assert!(!a.is_duplicate);
        assert!(b.is_duplicate);
        assert_eq!(a.yes_bid_close_e4, Some(7000));
        assert_eq!(a.volume_hundredths, Some(1250));
    }

    #[test]
    fn trade_unknown_side() {
        let raw = json!({
            "trade_id": "t1",
            "created_time": "2026-06-14T03:30:45.993203Z",
            "yes_price_dollars": "0.7100",
            "no_price_dollars": "0.2900",
            "count_fp": "10.00"
        });
        let mut seen = BTreeSet::new();
        let t = parse_trade_row("T", "E", &raw, Utc::now(), &mut seen, SCHEMA_VERSION).unwrap();
        assert_eq!(t.side_classification, "unknown");
        let dup = parse_trade_row("T", "E", &raw, Utc::now(), &mut seen, SCHEMA_VERSION).unwrap();
        assert!(dup.is_duplicate);
    }
}
