//! Completeness and two-sided market validation. Anomalies are flagged, not dropped.

use std::collections::{BTreeMap, BTreeSet};

use chrono::Utc;

use super::types::{
    NbaCandleRow, NbaEventRow, NbaGameRow, NbaMarketRow, NbaTradeRow, WarehouseReport,
};

#[allow(clippy::too_many_arguments)]
pub fn validate_counts(
    sport: &str,
    series: &str,
    season: &str,
    events: &[NbaEventRow],
    markets: &[NbaMarketRow],
    games: &[NbaGameRow],
    candles: u64,
    trades: u64,
    markets_with_candles: u64,
    markets_with_trades: u64,
    duplicate_candles: u64,
    duplicate_trades: u64,
    earliest_candle: Option<String>,
    latest_candle: Option<String>,
    coverage_ratio: Option<String>,
    failed_requests: u64,
    extra_anomalies: Vec<String>,
) -> WarehouseReport {
    let empty_c = Vec::new();
    let empty_t = Vec::new();
    let mut report = validate_dataset(
        sport,
        series,
        season,
        events,
        markets,
        games,
        &empty_c,
        &empty_t,
        failed_requests,
    );
    report.candles = candles;
    report.trades = trades;
    report.markets_with_candles = markets_with_candles;
    report.markets_without_candles = markets.len() as u64 - markets_with_candles;
    report.markets_with_trades = markets_with_trades;
    report.markets_without_trades = markets.len() as u64 - markets_with_trades;
    report.duplicate_candles = duplicate_candles;
    report.duplicate_trades = duplicate_trades;
    report.earliest_candle = earliest_candle;
    report.latest_candle = latest_candle;
    report.coverage_ratio = coverage_ratio;
    report.anomalies.extend(extra_anomalies);
    if failed_requests == 0 && report.games_missing_market == 0 {
        report.validation_status = "PASS".into();
    }
    report
}

#[allow(clippy::too_many_arguments)]
pub fn validate_dataset(
    sport: &str,
    series: &str,
    season: &str,
    events: &[NbaEventRow],
    markets: &[NbaMarketRow],
    games: &[NbaGameRow],
    candles: &[NbaCandleRow],
    trades: &[NbaTradeRow],
    failed_requests: u64,
) -> WarehouseReport {
    let mut anomalies = Vec::new();
    let mut event_ids = BTreeSet::new();
    for e in events {
        if !event_ids.insert(e.event_id.clone()) {
            anomalies.push(format!("duplicate event {}", e.event_id));
        }
    }
    let mut market_tickers = BTreeSet::new();
    for m in markets {
        if !market_tickers.insert(m.ticker.clone()) {
            anomalies.push(format!("duplicate market {}", m.ticker));
        }
    }

    let games_two = games.iter().filter(|g| g.market_count == 2).count() as u64;
    let games_missing = games.iter().filter(|g| g.market_count != 2).count() as u64;
    for g in games {
        if g.market_count != 2 {
            anomalies.push(format!(
                "unexpected market count {} for {}",
                g.market_count, g.event_ticker
            ));
        }
        if g.market_count == 2 {
            let teams: BTreeSet<_> = markets
                .iter()
                .filter(|m| m.event_id == g.event_id)
                .filter_map(|m| m.team.clone())
                .collect();
            if teams.len() != 2 {
                anomalies.push(format!("team mismatch on {}", g.event_ticker));
            }
        }
    }

    let mut candle_keys = BTreeSet::new();
    let mut dup_candles = 0u64;
    let mut candle_tickers = BTreeSet::new();
    let mut earliest = None;
    let mut latest = None;
    for c in candles {
        if !candle_keys.insert((c.ticker.clone(), c.end_period_ts)) || c.is_duplicate {
            dup_candles += 1;
        }
        candle_tickers.insert(c.ticker.clone());
        let t = c.end_time;
        earliest = Some(earliest.map_or(t, |e: chrono::DateTime<Utc>| e.min(t)));
        latest = Some(latest.map_or(t, |e: chrono::DateTime<Utc>| e.max(t)));
        if c.orderbook_depth_available {
            anomalies.push(format!(
                "L2 flag set on historical candle {} @ {}",
                c.ticker, c.end_period_ts
            ));
        }
        if c.market_data_type != "CANDLESTICK_TOP_OF_BOOK" {
            anomalies.push(format!(
                "unexpected market_data_type {}",
                c.market_data_type
            ));
        }
    }

    let mut trade_ids = BTreeSet::new();
    let mut dup_trades = 0u64;
    let mut trade_tickers = BTreeSet::new();
    for t in trades {
        if !trade_ids.insert(t.trade_id.clone()) || t.is_duplicate {
            dup_trades += 1;
        }
        trade_tickers.insert(t.ticker.clone());
    }

    let mut coverage_ratios = Vec::new();
    let mut by_ticker: BTreeMap<&str, Vec<&NbaCandleRow>> = BTreeMap::new();
    for c in candles {
        by_ticker.entry(&c.ticker).or_default().push(c);
    }
    for (ticker, rows) in &by_ticker {
        if rows.len() < 2 {
            continue;
        }
        let min_ts = rows.iter().map(|c| c.end_period_ts).min().unwrap_or(0);
        let max_ts = rows.iter().map(|c| c.end_period_ts).max().unwrap_or(0);
        let expected = ((max_ts - min_ts) / 60 + 1).max(1);
        let ratio = rows.len() as f64 / expected as f64;
        coverage_ratios.push(ratio);
        if ratio < 0.1 {
            anomalies.push(format!("low candle coverage {ticker}: {ratio:.4}"));
        }
    }
    let coverage = if coverage_ratios.is_empty() {
        None
    } else {
        let mean = coverage_ratios.iter().sum::<f64>() / coverage_ratios.len() as f64;
        Some(format!("{:.4}", mean))
    };

    let markets_with_candles = candle_tickers.len() as u64;
    let markets_with_trades = trade_tickers.len() as u64;
    let status = if failed_requests == 0 && games_missing == 0 {
        "PASS"
    } else if failed_requests == 0 {
        "PASS_WITH_ANOMALIES"
    } else {
        "FAIL"
    };

    WarehouseReport {
        sport: sport.to_string(),
        series: series.to_string(),
        season: season.to_string(),
        events: events.len() as u64,
        markets: markets.len() as u64,
        games: games.len() as u64,
        games_with_two_markets: games_two,
        games_missing_market: games_missing,
        candles: candles.len() as u64,
        trades: trades.len() as u64,
        markets_with_candles,
        markets_without_candles: markets.len() as u64 - markets_with_candles,
        markets_with_trades,
        markets_without_trades: markets.len() as u64 - markets_with_trades,
        earliest_candle: earliest.map(|t| t.to_rfc3339()),
        latest_candle: latest.map(|t| t.to_rfc3339()),
        duplicate_candles: dup_candles,
        duplicate_trades: dup_trades,
        failed_requests,
        coverage_ratio: coverage,
        anomalies,
        validation_status: status.into(),
    }
}

pub fn render_report(report: &WarehouseReport) -> String {
    format!(
        "{} {} DATASET VALIDATION\n\
=================================\n\n\
Season:\n{}\n\n\
Events:\n{}\n\n\
Markets:\n{}\n\n\
Games:\n{}\n\n\
Games with 2 markets:\n{}\n\n\
Games missing market:\n{}\n\n\
Candles:\n{}\n\n\
Trades:\n{}\n\n\
Markets with candles:\n{}\n\n\
Markets with trades:\n{}\n\n\
Earliest candle:\n{}\n\n\
Latest candle:\n{}\n\n\
Duplicate candles:\n{}\n\n\
Duplicate trades:\n{}\n\n\
Failed requests:\n{}\n\n\
Coverage:\n{}\n\n\
Potential anomalies:\n{}\n\n\
Validation status:\n{}\n\n\
Historical data available:\n1-minute top-of-book + trades\n\n\
Historical L2:\nNOT AVAILABLE\n\n\
Future live L2:\nARCHITECTURE READY (market_data_type)\n",
        report.sport.to_ascii_uppercase(),
        report.series,
        report.season,
        report.events,
        report.markets,
        report.games,
        report.games_with_two_markets,
        report.games_missing_market,
        report.candles,
        report.trades,
        report.markets_with_candles,
        report.markets_with_trades,
        report.earliest_candle.as_deref().unwrap_or("n/a"),
        report.latest_candle.as_deref().unwrap_or("n/a"),
        report.duplicate_candles,
        report.duplicate_trades,
        report.failed_requests,
        report.coverage_ratio.as_deref().unwrap_or("n/a"),
        if report.anomalies.is_empty() {
            "(none)".into()
        } else {
            report.anomalies.join("\n")
        },
        report.validation_status,
    )
}
