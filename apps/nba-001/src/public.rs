//! Unsigned production market data: series, events, candles, and Kalshi
//! `live_data` for the game period. Official Kalshi endpoints only.

use std::time::Duration;

use momento_kalshi::{
    MarketCandlestick, PublicMarketClient, count_fp_to_hundredths, dollars_to_price_cents,
};
use momento_strategy_nba::{ClockObservation, EventDescriptor, MarketDescriptor, MinuteBar};
use serde::Serialize;
use serde_json::Value;

const CALL_DELAY: Duration = Duration::from_millis(150);
/// One day of one-minute candles per request.
pub const CANDLE_CHUNK_S: i64 = 86_400;

#[derive(Clone, Debug, Serialize)]
pub struct SeriesInfo {
    pub ticker: String,
    pub exchange_index: Option<i64>,
    pub fee_type: Option<String>,
    pub fee_multiplier_raw: Value,
    pub last_updated_ts: Option<String>,
}

#[derive(Clone, Debug, Serialize)]
pub struct MarketView {
    pub desc: MarketDescriptor,
    pub open_time: Option<String>,
    pub yes_bid_cents: Option<u16>,
    pub yes_ask_cents: Option<u16>,
}

#[derive(Clone, Debug, Serialize)]
pub struct EventView {
    pub desc: EventDescriptor,
    pub title: Option<String>,
    pub sub_title: Option<String>,
    pub event_exchange_index: Option<i64>,
    pub markets: Vec<MarketView>,
}

pub struct Public {
    client: PublicMarketClient,
    pub calls_total: u64,
    pub errors_total: u64,
    pub last_ok_at: Option<i64>,
    pub last_error: Option<String>,
}

fn s(v: &Value, k: &str) -> Option<String> {
    v.get(k).and_then(|x| x.as_str()).map(str::to_string)
}

fn price(v: &Value, k: &str) -> Option<u16> {
    v.get(k)
        .and_then(|x| x.as_str())
        .and_then(|raw| dollars_to_price_cents(raw).ok())
        .map(|p| p.cents())
}

pub fn parse_market(m: &Value) -> Option<MarketView> {
    Some(MarketView {
        desc: MarketDescriptor {
            ticker: s(m, "ticker")?,
            event_ticker: s(m, "event_ticker").unwrap_or_default(),
            status: s(m, "status"),
            yes_sub_title: s(m, "yes_sub_title"),
            rules_primary: s(m, "rules_primary"),
            rules_secondary: s(m, "rules_secondary"),
            close_time: s(m, "close_time"),
            expected_expiration_time: s(m, "expected_expiration_time"),
            settlement_timer_seconds: m.get("settlement_timer_seconds").and_then(|x| x.as_i64()),
            exchange_index: m.get("exchange_index").and_then(|x| x.as_i64()),
        },
        open_time: s(m, "open_time"),
        yes_bid_cents: price(m, "yes_bid_dollars"),
        yes_ask_cents: price(m, "yes_ask_dollars"),
    })
}

pub fn parse_event(e: &Value) -> Option<EventView> {
    let markets = e
        .get("markets")
        .and_then(|m| m.as_array())
        .map(|arr| arr.iter().filter_map(parse_market).collect())
        .unwrap_or_default();
    Some(EventView {
        desc: EventDescriptor {
            event_ticker: s(e, "event_ticker")?,
            series_ticker: s(e, "series_ticker"),
            mutually_exclusive: e.get("mutually_exclusive").and_then(|x| x.as_bool()),
        },
        title: s(e, "title"),
        sub_title: s(e, "sub_title"),
        event_exchange_index: e.get("exchange_index").and_then(|x| x.as_i64()),
        markets,
    })
}

pub fn bar_from_candle(c: &MarketCandlestick) -> MinuteBar {
    let cents = |raw: &str| dollars_to_price_cents(raw).ok().map(|p| p.cents());
    let volume = count_fp_to_hundredths(&c.volume_fp)
        .ok()
        .and_then(|h| u64::try_from(h).ok());
    MinuteBar {
        end_ts: c.end_period_ts,
        yes_bid_close: cents(&c.yes_bid.close_dollars),
        yes_ask_close: cents(&c.yes_ask.close_dollars),
        yes_bid_low: cents(&c.yes_bid.low_dollars),
        volume,
    }
}

pub fn parse_live_data(v: &Value, received_at: i64) -> Option<ClockObservation> {
    let d = v.get("live_data")?.get("details")?;
    Some(ClockObservation {
        received_at,
        source_updated_at: d.get("last_updated_ts").and_then(|x| x.as_i64()),
        status: s(d, "status").unwrap_or_else(|| "unknown".into()),
        period: d
            .get("period")
            .and_then(|x| x.as_u64())
            .and_then(|p| u8::try_from(p).ok()),
        period_type: s(d, "period_type"),
        period_remaining: s(d, "period_remaining_time"),
    })
}

impl Public {
    pub fn production() -> Self {
        Self {
            client: PublicMarketClient::production(),
            calls_total: 0,
            errors_total: 0,
            last_ok_at: None,
            last_error: None,
        }
    }

    fn get(&mut self, path: &str, now: i64) -> Result<Value, String> {
        self.calls_total += 1;
        std::thread::sleep(CALL_DELAY);
        let result = match self.client.get_status_body(path) {
            Ok((200, body)) => serde_json::from_str(&body).map_err(|e| format!("json {path}: {e}")),
            Ok((status, _)) => Err(format!(
                "HTTP {status} {}",
                path.split('?').next().unwrap_or(path)
            )),
            Err(e) => Err(format!("{e}")),
        };
        match &result {
            Ok(_) => self.last_ok_at = Some(now),
            Err(e) => {
                self.errors_total += 1;
                self.last_error = Some(e.clone());
            }
        }
        result
    }

    pub fn series(&mut self, ticker: &str, now: i64) -> Result<SeriesInfo, String> {
        let v = self.get(&format!("/trade-api/v2/series/{ticker}"), now)?;
        let sv = v.get("series").ok_or("series missing")?;
        Ok(SeriesInfo {
            ticker: ticker.to_string(),
            exchange_index: sv.get("exchange_index").and_then(|x| x.as_i64()),
            fee_type: s(sv, "fee_type"),
            fee_multiplier_raw: sv.get("fee_multiplier").cloned().unwrap_or(Value::Null),
            last_updated_ts: s(sv, "last_updated_ts"),
        })
    }

    pub fn open_events(&mut self, series: &str, now: i64) -> Result<Vec<EventView>, String> {
        let mut out = Vec::new();
        let mut cursor: Option<String> = None;
        for _ in 0..20 {
            let mut path = format!(
                "/trade-api/v2/events?series_ticker={series}&status=open&with_nested_markets=true&limit=200"
            );
            if let Some(c) = &cursor {
                path.push_str(&format!("&cursor={c}"));
            }
            let v = self.get(&path, now)?;
            if let Some(events) = v.get("events").and_then(|e| e.as_array()) {
                out.extend(events.iter().filter_map(parse_event));
            }
            match v
                .get("cursor")
                .and_then(|c| c.as_str())
                .filter(|c| !c.is_empty())
            {
                Some(next) => cursor = Some(next.to_string()),
                None => return Ok(out),
            }
        }
        Err("events pagination exceeded 20 pages".into())
    }

    pub fn event(&mut self, event_ticker: &str, now: i64) -> Result<EventView, String> {
        let v = self.get(
            &format!("/trade-api/v2/events/{event_ticker}?with_nested_markets=true"),
            now,
        )?;
        let mut ev = v.get("event").cloned().ok_or("event missing")?;
        if ev.get("markets").is_none()
            && let Some(m) = v.get("markets")
            && let Some(obj) = ev.as_object_mut()
        {
            obj.insert("markets".into(), m.clone());
        }
        parse_event(&ev).ok_or_else(|| "event parse".into())
    }

    /// (milestone id, start_date) for an event, if Kalshi lists one.
    pub fn milestone(
        &mut self,
        event_ticker: &str,
        now: i64,
    ) -> Result<Option<(String, Option<String>)>, String> {
        let v = self.get(
            &format!("/trade-api/v2/milestones?limit=5&related_event_ticker={event_ticker}"),
            now,
        )?;
        let found = v
            .get("milestones")
            .and_then(|m| m.as_array())
            .and_then(|arr| {
                arr.iter()
                    .find(|m| m.get("type").and_then(|t| t.as_str()) == Some("basketball_game"))
            })
            .and_then(|m| Some((s(m, "id")?, s(m, "start_date"))));
        Ok(found)
    }

    pub fn live_data(&mut self, milestone_id: &str, now: i64) -> Result<ClockObservation, String> {
        let v = self.get(
            &format!("/trade-api/v2/live_data/basketball_game/milestone/{milestone_id}"),
            now,
        )?;
        parse_live_data(&v, now).ok_or_else(|| "live_data parse".into())
    }

    pub fn candles(
        &mut self,
        series: &str,
        ticker: &str,
        start: i64,
        end: i64,
        now: i64,
    ) -> Result<Vec<MinuteBar>, String> {
        let v = self.get(
            &format!(
                "/trade-api/v2/series/{series}/markets/{ticker}/candlesticks?start_ts={start}&end_ts={end}&period_interval=1"
            ),
            now,
        )?;
        let arr = v
            .get("candlesticks")
            .and_then(|c| c.as_array())
            .cloned()
            .unwrap_or_default();
        let mut bars = Vec::with_capacity(arr.len());
        for raw in arr {
            let c: MarketCandlestick =
                serde_json::from_value(raw).map_err(|e| format!("candle parse: {e}"))?;
            bars.push(bar_from_candle(&c));
        }
        bars.sort_by_key(|b| b.end_ts);
        Ok(bars)
    }
}
