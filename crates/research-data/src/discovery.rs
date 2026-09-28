//! Historical market discovery by calendar date and series.

use chrono::{DateTime, NaiveDate, TimeZone, Utc};
use chrono_tz::America::Los_Angeles;
use momento_core::error::VenueError;
use momento_kalshi::{KalshiMarket, PublicMarketClient};

use crate::identity::{DiscoveredMarket, metadata_from_kalshi};
use crate::sport::ResearchSport;

#[derive(Clone, Debug)]
pub struct DayWindow {
    pub start_ts: i64,
    pub end_ts: i64,
}

pub fn day_window(date: NaiveDate) -> DayWindow {
    let start = Los_Angeles
        .from_local_datetime(&date.and_hms_opt(0, 0, 0).expect("midnight"))
        .single()
        .expect("valid local midnight");
    let end = Los_Angeles
        .from_local_datetime(&date.and_hms_opt(23, 59, 59).expect("end of day"))
        .single()
        .expect("valid local end");
    DayWindow {
        start_ts: start.timestamp(),
        end_ts: end.timestamp(),
    }
}

pub fn discover_markets_for_day(
    client: &PublicMarketClient,
    sport: ResearchSport,
    date: NaiveDate,
    cutoff: Option<i64>,
) -> Result<Vec<DiscoveredMarket>, VenueError> {
    let window = day_window(date);
    let series = sport.series_ticker();
    let mut markets = Vec::new();

    let live_query = format!(
        "series_ticker={series}&min_close_ts={}&max_close_ts={}&status=closed&limit=1000&mve_filter=exclude",
        window.start_ts, window.end_ts
    );
    markets.extend(client.list_all_markets(live_query, false)?);

    let settled_query = format!(
        "series_ticker={series}&min_settled_ts={}&max_settled_ts={}&status=settled&limit=1000&mve_filter=exclude",
        window.start_ts, window.end_ts
    );
    markets.extend(client.list_all_markets(settled_query, false)?);

    if cutoff.is_some_and(|c| window.end_ts < c) {
        let hist_closed = format!(
            "series_ticker={series}&min_close_ts={}&max_close_ts={}&limit=1000",
            window.start_ts, window.end_ts
        );
        markets.extend(client.list_all_markets(hist_closed, true)?);
        let hist_settled = format!(
            "series_ticker={series}&min_settled_ts={}&max_settled_ts={}&limit=1000",
            window.start_ts, window.end_ts
        );
        markets.extend(client.list_all_markets(hist_settled, true)?);
    }

    Ok(dedupe_markets(markets, sport))
}

fn dedupe_markets(markets: Vec<KalshiMarket>, sport: ResearchSport) -> Vec<DiscoveredMarket> {
    let mut seen = std::collections::BTreeSet::new();
    let mut out = Vec::new();
    for market in markets {
        if !seen.insert(market.ticker.clone()) {
            continue;
        }
        if !market.ticker.starts_with(sport.series_ticker()) {
            continue;
        }
        out.push(DiscoveredMarket {
            metadata: metadata_from_kalshi(&market, sport),
            sport,
        });
    }
    out.sort_by(|a, b| a.metadata.ticker.cmp(&b.metadata.ticker));
    out
}

pub fn parse_exchange_time(raw: &str) -> Option<DateTime<Utc>> {
    DateTime::parse_from_rfc3339(raw)
        .ok()
        .map(|dt| dt.with_timezone(&Utc))
}
