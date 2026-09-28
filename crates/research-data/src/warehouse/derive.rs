//! Point-in-time derived features. Causal tables set `look_ahead = false`.

use std::collections::BTreeMap;

use super::types::{
    CausalCandleFeatures, ComplementarityRow, NbaCandleRow, NbaGameRow, NbaTradeRow, TradeMinuteAgg,
};

pub fn mid_e4(bid: Option<i64>, ask: Option<i64>) -> Option<i64> {
    match (bid, ask) {
        (Some(b), Some(a)) => Some((b + a) / 2),
        _ => None,
    }
}

pub fn spread_e4(bid: Option<i64>, ask: Option<i64>) -> Option<i64> {
    match (bid, ask) {
        (Some(b), Some(a)) => Some(a - b),
        _ => None,
    }
}

pub fn spread_bps(spread: Option<i64>, mid: Option<i64>) -> Option<i64> {
    match (spread, mid) {
        (Some(s), Some(m)) if m > 0 => Some(s.saturating_mul(10_000) / m),
        _ => None,
    }
}

/// Causal returns: feature at index `i` uses only `0..=i`.
pub fn causal_features(candles: &[NbaCandleRow]) -> Vec<CausalCandleFeatures> {
    let mut rows = candles.to_vec();
    rows.sort_by_key(|c| c.end_period_ts);
    let mids: Vec<Option<i64>> = rows
        .iter()
        .map(|c| mid_e4(c.yes_bid_close_e4, c.yes_ask_close_e4))
        .collect();
    rows.iter()
        .enumerate()
        .map(|(i, c)| {
            let mid = mids[i];
            let spr = spread_e4(c.yes_bid_close_e4, c.yes_ask_close_e4);
            CausalCandleFeatures {
                ticker: c.ticker.clone(),
                end_period_ts: c.end_period_ts,
                mid_close_e4: mid,
                spread_e4: spr,
                spread_bps: spread_bps(spr, mid),
                return_1m_e4: lagged_return(&mids, i, 1),
                return_5m_e4: lagged_return(&mids, i, 5),
                return_15m_e4: lagged_return(&mids, i, 15),
                look_ahead: false,
            }
        })
        .collect()
}

fn lagged_return(mids: &[Option<i64>], i: usize, lag: usize) -> Option<i64> {
    if i < lag {
        return None;
    }
    match (mids[i], mids[i - lag]) {
        (Some(now), Some(prev)) => Some(now - prev),
        _ => None,
    }
}

pub fn complementarity(games: &[NbaGameRow], candles: &[NbaCandleRow]) -> Vec<ComplementarityRow> {
    type Book = BTreeMap<i64, (Option<i64>, Option<i64>)>;
    let mut by_ticker: BTreeMap<&str, Book> = BTreeMap::new();
    for c in candles {
        by_ticker
            .entry(&c.ticker)
            .or_default()
            .insert(c.end_period_ts, (c.yes_bid_close_e4, c.yes_ask_close_e4));
    }
    let mut out = Vec::new();
    for game in games {
        if game.market_tickers.len() != 2 {
            continue;
        }
        let a = &game.market_tickers[0];
        let b = &game.market_tickers[1];
        let Some(a_map) = by_ticker.get(a.as_str()) else {
            continue;
        };
        let Some(b_map) = by_ticker.get(b.as_str()) else {
            continue;
        };
        for (ts, (ab, aa)) in a_map {
            if let Some((bb, ba)) = b_map.get(ts) {
                let a_mid = mid_e4(*ab, *aa);
                let b_mid = mid_e4(*bb, *ba);
                let combined = match (a_mid, b_mid) {
                    (Some(x), Some(y)) => Some(x + y),
                    _ => None,
                };
                out.push(ComplementarityRow {
                    event_id: game.event_id.clone(),
                    end_period_ts: *ts,
                    a_ticker: a.clone(),
                    b_ticker: b.clone(),
                    a_mid_e4: a_mid,
                    b_mid_e4: b_mid,
                    combined_mid_e4: combined,
                    complementarity_error_e4: combined.map(|s| s - 10_000),
                });
            }
        }
    }
    out
}

pub fn trade_minute_agg(trades: &[NbaTradeRow]) -> Vec<TradeMinuteAgg> {
    let mut groups: BTreeMap<(String, i64), Vec<&NbaTradeRow>> = BTreeMap::new();
    for t in trades {
        if t.is_duplicate {
            continue;
        }
        let minute = t.timestamp.timestamp() / 60 * 60;
        groups
            .entry((t.ticker.clone(), minute))
            .or_default()
            .push(t);
    }
    groups
        .into_iter()
        .map(|((ticker, minute_ts), rows)| {
            let mut sizes: Vec<i64> = rows.iter().filter_map(|t| t.quantity_hundredths).collect();
            sizes.sort_unstable();
            let vol: i64 = sizes.iter().sum();
            let count = rows.len() as u64;
            let mut buy = 0i64;
            let mut sell = 0i64;
            let mut unknown = 0i64;
            for t in &rows {
                let q = t.quantity_hundredths.unwrap_or(0);
                match t.side_classification.as_str() {
                    "buy_yes" => buy += q,
                    "sell_yes" => sell += q,
                    _ => unknown += q,
                }
            }
            TradeMinuteAgg {
                ticker,
                minute_ts,
                trade_count: count,
                trade_volume_hundredths: vol,
                average_trade_size_hundredths: if count > 0 {
                    Some(vol / count as i64)
                } else {
                    None
                },
                median_trade_size_hundredths: sizes.get(sizes.len() / 2).copied(),
                max_trade_size_hundredths: sizes.last().copied(),
                buy_volume_hundredths: buy,
                sell_volume_hundredths: sell,
                unknown_side_volume_hundredths: unknown,
            }
        })
        .collect()
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::warehouse::types::{MARKET_DATA_TYPE_CANDLE_TOB, SCHEMA_VERSION};
    use chrono::{TimeZone, Utc};

    fn candle(ts: i64, bid: i64, ask: i64) -> NbaCandleRow {
        NbaCandleRow {
            ticker: "T".into(),
            event_id: "E".into(),
            market_id: "M".into(),
            game_id: "G".into(),
            end_period_ts: ts,
            start_time: Utc.timestamp_opt(ts - 60, 0).unwrap(),
            end_time: Utc.timestamp_opt(ts, 0).unwrap(),
            yes_bid_open_e4: Some(bid),
            yes_bid_high_e4: Some(bid),
            yes_bid_low_e4: Some(bid),
            yes_bid_close_e4: Some(bid),
            yes_ask_open_e4: Some(ask),
            yes_ask_high_e4: Some(ask),
            yes_ask_low_e4: Some(ask),
            yes_ask_close_e4: Some(ask),
            price_open_e4: None,
            price_high_e4: None,
            price_low_e4: None,
            price_close_e4: None,
            price_mean_e4: None,
            price_previous_e4: None,
            volume_hundredths: None,
            open_interest_hundredths: None,
            market_data_type: MARKET_DATA_TYPE_CANDLE_TOB.into(),
            orderbook_depth_available: false,
            is_valid: true,
            is_duplicate: false,
            is_pre_market: false,
            is_post_market: false,
            source: "test".into(),
            ingested_at: Utc::now(),
            schema_version: SCHEMA_VERSION.into(),
        }
    }

    #[test]
    fn no_lookahead_on_returns() {
        let rows = vec![
            candle(100, 5000, 5200),
            candle(160, 5300, 5500),
            candle(220, 5400, 5600),
        ];
        let feats = causal_features(&rows);
        assert!(!feats.iter().any(|f| f.look_ahead));
        assert_eq!(feats[0].return_1m_e4, None);
        assert_eq!(feats[1].return_1m_e4, Some(5400 - 5100));
        assert_eq!(feats[2].return_5m_e4, None);
        assert_eq!(feats[2].return_1m_e4, Some(5500 - 5400));
    }

    #[test]
    fn mid_requires_both_sides() {
        assert_eq!(mid_e4(Some(1), None), None);
        assert_eq!(mid_e4(Some(7000), Some(7200)), Some(7100));
    }
}
