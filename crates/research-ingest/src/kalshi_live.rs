//! Authorized live Kalshi discovery. Lands source JSON only — never MarketState / L2 invention.
//!
//! Historical `GET /historical/markets` filters are mutually exclusive. Timestamp
//! filters on that endpoint are ignored and must not be used. Discovery uses
//! `series_ticker=KXMLBGAME`, then client-side date-token attribution.

use std::collections::BTreeSet;
use std::sync::Mutex;
use std::thread;
use std::time::{Duration, Instant};

use chrono::{DateTime, NaiveDate};
use momento_kalshi::{KalshiMarket, PublicMarketClient};
use momento_research_data::discovery::day_window;
use momento_research_event::identity::kalshi_event_date_token;
use serde_json::{Value, json};

use crate::error::IngestError;
use crate::kalshi::{DiscoveredMarket, KalshiDiscoverySource};
use crate::source::FetchOutcome;
use crate::types::{DateWindow, IdentityMapping, MarketCompleteness, SOURCE_KALSHI_DISCOVERY};

pub struct LiveKalshiSource {
    client: PublicMarketClient,
    min_interval: Duration,
    last_call: Mutex<Instant>,
    pub fetch_trades: bool,
    pub fetch_candles: bool,
}

impl LiveKalshiSource {
    pub fn production(rate_limit_ms: u64) -> Self {
        Self {
            client: PublicMarketClient::production(),
            min_interval: Duration::from_millis(rate_limit_ms.max(120)),
            last_call: Mutex::new(Instant::now() - Duration::from_secs(1)),
            fetch_trades: true,
            fetch_candles: true,
        }
    }

    fn wait(&self) {
        let mut last = self.last_call.lock().unwrap_or_else(|e| e.into_inner());
        let elapsed = last.elapsed();
        if elapsed < self.min_interval {
            thread::sleep(self.min_interval - elapsed);
        }
        *last = Instant::now();
    }

    fn venue<T, E: ToString>(
        &self,
        what: &str,
        mut op: impl FnMut() -> Result<T, E>,
    ) -> Result<T, IngestError> {
        let mut backoff = Duration::from_millis(2000);
        for attempt in 0..12 {
            self.wait();
            match op() {
                Ok(v) => return Ok(v),
                Err(e) if is_rate_limited(&e) => {
                    eprintln!(
                        "kalshi 429 {what} attempt {} sleep {}ms",
                        attempt + 1,
                        backoff.as_millis()
                    );
                    thread::sleep(backoff);
                    backoff = (backoff * 2).min(Duration::from_secs(30));
                }
                Err(e) => {
                    return Err(IngestError::SourceFailure(format!(
                        "{what}: {}",
                        e.to_string()
                    )));
                }
            }
        }
        Err(IngestError::SourceFailure(format!(
            "{what}: 429 retries exhausted"
        )))
    }

    /// Historical trades first; live trades only if historical fails.
    /// Dual API failure is `Err` so the dest file is not written (retryable).
    pub fn fetch_windowed_trades(
        &self,
        ticker: &str,
        min_ts: i64,
        max_ts: i64,
    ) -> Result<(String, Vec<serde_json::Value>, String), IngestError> {
        match self.venue("kalshi historical trades", || {
            self.client.list_all_trades(ticker, min_ts, max_ts, true)
        }) {
            Ok(t) => {
                let v = serde_json::to_value(&t).map_err(|e| IngestError::Serde(e.to_string()))?;
                let trades = v.as_array().cloned().unwrap_or_default();
                Ok(("OBSERVED_HISTORICAL".into(), trades, String::new()))
            }
            Err(hist_err) => {
                match self.venue("kalshi live trades", || {
                    self.client.list_all_trades(ticker, min_ts, max_ts, false)
                }) {
                    Ok(t) => {
                        let v = serde_json::to_value(&t)
                            .map_err(|e| IngestError::Serde(e.to_string()))?;
                        let trades = v.as_array().cloned().unwrap_or_default();
                        Ok(("OBSERVED_LIVE".into(), trades, String::new()))
                    }
                    Err(live_err) => Err(IngestError::SourceFailure(format!(
                        "historical={hist_err} live={live_err}"
                    ))),
                }
            }
        }
    }

    fn list_live_capped(
        &self,
        query: &str,
        max_pages: u32,
    ) -> Result<Vec<KalshiMarket>, IngestError> {
        let mut out = Vec::new();
        let mut cursor: Option<String> = None;
        for _ in 0..max_pages {
            let q = match &cursor {
                Some(c) => format!("{query}&cursor={c}"),
                None => query.to_string(),
            };
            let page = self.venue("kalshi live markets", || self.client.list_markets(&q))?;
            out.extend(page.markets);
            match page.cursor.filter(|c| !c.is_empty()) {
                Some(next) => cursor = Some(next),
                None => return Ok(out),
            }
        }
        Ok(out)
    }

    fn list_historical_kxmlb_in_window(
        &self,
        window: &DateWindow,
    ) -> Result<Vec<KalshiMarket>, IngestError> {
        let mut out = Vec::new();
        let mut cursor: Option<String> = None;
        for _ in 0..50u32 {
            let mut query = "series_ticker=KXMLBGAME&limit=1000".to_string();
            if let Some(c) = &cursor {
                query.push_str("&cursor=");
                query.push_str(c);
            }
            let page = self.venue("kalshi historical markets", || {
                self.client.list_historical_markets(&query)
            })?;
            let mut dated = Vec::new();
            for m in page.markets {
                if !m.ticker.starts_with("KXMLBGAME") {
                    continue;
                }
                if let Some(d) = event_ticker_date(&m.event_ticker) {
                    dated.push(d);
                    if window.contains(d) {
                        out.push(m);
                    }
                }
            }
            if historical_page_is_before_window(&dated, window) {
                return Ok(out);
            }
            match page.cursor.filter(|c| !c.is_empty()) {
                Some(next) => cursor = Some(next),
                None => return Ok(out),
            }
        }
        Err(IngestError::SourceFailure(
            "kalshi historical pagination exceeded 50 pages; refusing silent truncate".into(),
        ))
    }
}

/// Parse the calendar date encoded in a Kalshi MLB event_ticker.
pub fn event_ticker_date(event_ticker: &str) -> Option<NaiveDate> {
    let date_s = kalshi_event_date_token(event_ticker)?;
    NaiveDate::parse_from_str(&date_s, "%Y-%m-%d").ok()
}

/// Attribute a Kalshi event_ticker to a calendar date inside `window`.
/// Never infers a date from settlement timestamps.
pub fn date_in_window(event_ticker: &str, window: &DateWindow) -> Option<NaiveDate> {
    let date = event_ticker_date(event_ticker)?;
    window.contains(date).then_some(date)
}

/// Historical MLB pages are newest-first. If every dated market on a page is
/// strictly before `window.start`, later pages cannot contain the window.
pub fn historical_page_is_before_window(dates: &[NaiveDate], window: &DateWindow) -> bool {
    !dates.is_empty() && dates.iter().all(|d| *d < window.start)
}

fn discovered(market: &KalshiMarket, date: NaiveDate) -> DiscoveredMarket {
    DiscoveredMarket {
        date,
        ticker: market.ticker.clone(),
        event_ticker: Some(market.event_ticker.clone()).filter(|s| !s.is_empty()),
        series: market
            .series_ticker
            .clone()
            .or_else(|| Some("KXMLBGAME".into())),
        mapping: IdentityMapping::Unmatched,
        observed_game_pk: None,
        completeness: Some(MarketCompleteness::MarketMetadataOnly),
        notes: format!(
            "open={:?} close={:?} result={:?}",
            market.open_time, market.close_time, market.result
        ),
        open_time: market.open_time.clone(),
        close_time: market.close_time.clone(),
        result: market.result.clone(),
        settlement_ts: market.settlement_ts.clone(),
        settlement_value_dollars: market.settlement_value_dollars.clone(),
        status: market.status.clone(),
    }
}

impl KalshiDiscoverySource for LiveKalshiSource {
    fn discover(&self, window: &DateWindow) -> Result<Vec<DiscoveredMarket>, IngestError> {
        let start_w = day_window(window.start);
        let end_w = day_window(window.end);
        let mut raw = Vec::new();
        raw.extend(self.list_historical_kxmlb_in_window(window)?);
        raw.extend(self.list_live_capped(
            &format!(
                "series_ticker=KXMLBGAME&min_settled_ts={}&max_settled_ts={}&limit=1000",
                start_w.start_ts, end_w.end_ts
            ),
            5,
        )?);
        raw.extend(self.list_live_capped(
            &format!(
                "series_ticker=KXMLBGAME&min_close_ts={}&max_close_ts={}&limit=1000",
                start_w.start_ts, end_w.end_ts
            ),
            5,
        )?);

        let mut seen = BTreeSet::new();
        let mut out = Vec::new();
        for m in raw {
            if !m.ticker.starts_with("KXMLBGAME") {
                continue;
            }
            if !seen.insert(m.ticker.clone()) {
                continue;
            }
            let Some(date) = date_in_window(&m.event_ticker, window) else {
                continue;
            };
            out.push(discovered(&m, date));
        }
        out.sort_by(|a, b| a.ticker.cmp(&b.ticker));
        Ok(out)
    }

    fn fetch_artifact(&self, market: &DiscoveredMarket) -> Result<FetchOutcome, IngestError> {
        if market.ticker.trim().is_empty() {
            return Err(IngestError::SourceFailure(
                "refusing empty Kalshi ticker".into(),
            ));
        }
        let window = day_window(market.date);
        let mut trades = serde_json::Value::Array(vec![]);
        let mut candles = serde_json::Value::Null;
        let mut n_trades = 0usize;
        let mut n_candles = 0usize;
        let mut trades_status = "NOT_REQUESTED";
        let mut candles_status = "NOT_REQUESTED";

        if self.fetch_trades {
            match self.venue("kalshi historical trades", || {
                self.client
                    .list_all_trades(&market.ticker, window.start_ts, window.end_ts, true)
            }) {
                Ok(t) => {
                    n_trades = t.len();
                    trades_status = "OBSERVED_HISTORICAL";
                    trades =
                        serde_json::to_value(&t).map_err(|e| IngestError::Serde(e.to_string()))?;
                }
                Err(hist_err) => {
                    match self.venue("kalshi live trades", || {
                        self.client.list_all_trades(
                            &market.ticker,
                            window.start_ts,
                            window.end_ts,
                            false,
                        )
                    }) {
                        Ok(t) => {
                            n_trades = t.len();
                            trades_status = "OBSERVED_LIVE";
                            trades = serde_json::to_value(&t)
                                .map_err(|e| IngestError::Serde(e.to_string()))?;
                        }
                        Err(live_err) => {
                            trades_status = "UNAVAILABLE";
                            trades = json!({
                                "unavailable": true,
                                "historical_error": hist_err.to_string(),
                                "live_error": live_err.to_string(),
                            });
                        }
                    }
                }
            }
        }
        if self.fetch_candles {
            let (c_start, c_end) = artifact_window(market);
            match self.fetch_candles_split(&market.ticker, c_start, c_end, 1) {
                Ok(c) => {
                    let arr = crate::kalshi::candlesticks_array(&c);
                    n_candles = arr.len();
                    candles_status = "OBSERVED_HISTORICAL";
                    candles = Value::Array(arr);
                }
                Err(e) => {
                    candles_status = "UNAVAILABLE";
                    candles = json!({
                        "unavailable": true,
                        "error": e.to_string(),
                    });
                }
            }
        }

        let completeness = if n_trades > 0 {
            MarketCompleteness::TradesOnly
        } else if n_candles > 0 {
            MarketCompleteness::CandlesOnly
        } else {
            MarketCompleteness::MarketMetadataOnly
        };
        let payload = json!({
            "source": SOURCE_KALSHI_DISCOVERY,
            "ticker": market.ticker,
            "event_ticker": market.event_ticker,
            "series": market.series,
            "completeness": completeness,
            "l2": "HISTORICAL_L2_UNAVAILABLE",
            "trades_status": trades_status,
            "candles_status": candles_status,
            "trade_count": n_trades,
            "candle_count": n_candles,
            "result": market.result,
            "settlement_ts": market.settlement_ts,
            "settlement_value_dollars": market.settlement_value_dollars,
            "open_time": market.open_time,
            "close_time": market.close_time,
            "status": market.status,
            "trades": trades,
            "candlesticks": candles,
        });
        Ok(FetchOutcome::Bytes(
            serde_json::to_vec(&payload).map_err(|e| IngestError::Serde(e.to_string()))?,
        ))
    }

    fn fetch_candlesticks(
        &self,
        market: &DiscoveredMarket,
    ) -> Result<Option<FetchOutcome>, IngestError> {
        let (start_ts, end_ts) = artifact_window(market);
        match self.fetch_candles_split(&market.ticker, start_ts, end_ts, 1) {
            Ok(candles) => {
                let n = crate::kalshi::candlesticks_array(&candles).len();
                let payload = json!({
                    "ticker": market.ticker,
                    "candlesticks": crate::kalshi::candlesticks_array(&candles),
                    "candles_status": "OBSERVED_HISTORICAL",
                    "candle_count": n,
                    "window_start_ts": start_ts,
                    "window_end_ts": end_ts,
                    "period_interval": 1,
                    "l2": "HISTORICAL_L2_UNAVAILABLE",
                });
                Ok(Some(FetchOutcome::Bytes(
                    serde_json::to_vec(&payload).map_err(|e| IngestError::Serde(e.to_string()))?,
                )))
            }
            Err(e) => Ok(Some(FetchOutcome::Failure(e.to_string()))),
        }
    }
}

/// Official market open/close when present. Otherwise the Pacific event day.
pub fn artifact_window(market: &DiscoveredMarket) -> (i64, i64) {
    let open = market.open_time.as_deref().and_then(parse_venue_ts);
    let close = market.close_time.as_deref().and_then(parse_venue_ts);
    if let (Some(start), Some(end)) = (open, close)
        && end > start
    {
        return (start, end);
    }
    let window = day_window(market.date);
    (window.start_ts, window.end_ts)
}

fn is_rate_limited(err: &impl ToString) -> bool {
    err.to_string().contains("429")
}

fn parse_venue_ts(raw: &str) -> Option<i64> {
    DateTime::parse_from_rfc3339(raw.trim())
        .ok()
        .map(|t| t.timestamp())
}

/// Kalshi rejects windows that would return more than 5000 1-minute bars.
const MAX_CANDLES_PER_REQUEST: i64 = 4900;

fn candle_span_exceeds_api_limit(start: i64, end: i64, period_minutes: u32) -> bool {
    let step = i64::from(period_minutes.max(1)) * 60;
    if step <= 0 || end <= start {
        return false;
    }
    (end - start) / step > MAX_CANDLES_PER_REQUEST
}

impl LiveKalshiSource {
    fn fetch_candles_split(
        &self,
        ticker: &str,
        start: i64,
        end: i64,
        period: u32,
    ) -> Result<Value, IngestError> {
        if end <= start {
            return Ok(json!([]));
        }
        if candle_span_exceeds_api_limit(start, end, period) {
            let mid = start + (end - start) / 2;
            let a = self.fetch_candles_split(ticker, start, mid, period)?;
            let b = self.fetch_candles_split(ticker, mid, end, period)?;
            return Ok(merge_candle_arrays(a, b));
        }
        match self.venue("kalshi historical candlesticks", || {
            self.client
                .get_historical_candlesticks_value(ticker, start, end, period)
        }) {
            Ok(body) => Ok(Value::Array(crate::kalshi::candlesticks_array(&body))),
            Err(_) if end - start > 3_600 => {
                let mid = start + (end - start) / 2;
                let a = self.fetch_candles_split(ticker, start, mid, period)?;
                let b = self.fetch_candles_split(ticker, mid, end, period)?;
                Ok(merge_candle_arrays(a, b))
            }
            Err(e) => Err(IngestError::SourceFailure(format!(
                "kalshi historical candlesticks: {e}"
            ))),
        }
    }
}

fn merge_candle_arrays(a: Value, b: Value) -> Value {
    let mut out = crate::kalshi::candlesticks_array(&a);
    out.extend(crate::kalshi::candlesticks_array(&b));
    Value::Array(out)
}

#[cfg(test)]
mod tests {
    use super::*;
    use chrono::NaiveDate;

    fn window(day: NaiveDate) -> DateWindow {
        DateWindow {
            label: "t".into(),
            start: day,
            end: day,
        }
    }

    #[test]
    fn date_token_keeps_matching_day() {
        let d = NaiveDate::from_ymd_opt(2026, 6, 18).unwrap();
        assert_eq!(
            date_in_window("KXMLBGAME-26JUN18NYYBOS", &window(d)),
            Some(d)
        );
    }

    #[test]
    fn date_token_drops_other_day() {
        let d = NaiveDate::from_ymd_opt(2026, 6, 18).unwrap();
        assert_eq!(date_in_window("KXMLBGAME-26JUN25NYMLAA", &window(d)), None);
    }

    #[test]
    fn date_token_drops_undated_ticker() {
        let d = NaiveDate::from_ymd_opt(2026, 6, 18).unwrap();
        assert_eq!(date_in_window("KXMLBGAME", &window(d)), None);
        assert_eq!(date_in_window("", &window(d)), None);
    }

    #[test]
    fn newest_first_page_before_window_stops() {
        let d = NaiveDate::from_ymd_opt(2026, 6, 18).unwrap();
        let w = window(d);
        let older = vec![
            NaiveDate::from_ymd_opt(2026, 6, 10).unwrap(),
            NaiveDate::from_ymd_opt(2026, 6, 11).unwrap(),
        ];
        assert!(historical_page_is_before_window(&older, &w));
        assert!(!historical_page_is_before_window(
            &[NaiveDate::from_ymd_opt(2026, 6, 18).unwrap()],
            &w
        ));
        assert!(!historical_page_is_before_window(&[], &w));
    }

    #[test]
    fn artifact_window_uses_official_open_close() {
        let d = NaiveDate::from_ymd_opt(2026, 6, 18).unwrap();
        let market = DiscoveredMarket {
            date: d,
            ticker: "KXMLBGAME-X-NYY".into(),
            event_ticker: None,
            series: Some("KXMLBGAME".into()),
            mapping: IdentityMapping::Unmatched,
            observed_game_pk: None,
            completeness: None,
            notes: String::new(),
            open_time: Some("2026-06-18T16:00:00Z".into()),
            close_time: Some("2026-06-19T03:00:00Z".into()),
            result: None,
            settlement_ts: None,
            settlement_value_dollars: None,
            status: None,
        };
        let (start, end) = artifact_window(&market);
        assert_eq!(start, 1_781_798_400);
        assert_eq!(end, 1_781_838_000);
        assert!(end > start);
    }

    #[test]
    fn rate_limit_detects_429() {
        assert!(is_rate_limited(&"status code 429"));
        assert!(!is_rate_limited(&"status code 500"));
    }
}
