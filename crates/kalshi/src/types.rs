//! Official JSON shapes used by tests and mapping. Extra fields are ignored.

use serde::{Deserialize, Deserializer, Serialize};

fn optional_cutoff_unix<'de, D>(deserializer: D) -> Result<Option<i64>, D::Error>
where
    D: Deserializer<'de>,
{
    let value = Option::<serde_json::Value>::deserialize(deserializer)?;
    match value {
        None | Some(serde_json::Value::Null) => Ok(None),
        Some(serde_json::Value::Number(n)) => n.as_i64().map(Some).ok_or_else(|| {
            serde::de::Error::custom("cutoff timestamp number is not a signed 64-bit integer")
        }),
        Some(serde_json::Value::String(s)) => {
            if let Ok(dt) = chrono::DateTime::parse_from_rfc3339(&s) {
                return Ok(Some(dt.timestamp()));
            }
            s.parse::<i64>().map(Some).map_err(|_| {
                serde::de::Error::custom(format!(
                    "cutoff timestamp string is neither RFC3339 nor unix seconds: {s}"
                ))
            })
        }
        Some(other) => Err(serde::de::Error::custom(format!(
            "cutoff timestamp must be RFC3339 or unix seconds, got {other}"
        ))),
    }
}

fn null_or_absent_string<'de, D>(deserializer: D) -> Result<String, D::Error>
where
    D: Deserializer<'de>,
{
    Ok(Option::<String>::deserialize(deserializer)?.unwrap_or_default())
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct CreateOrderV2Request {
    pub ticker: String,
    pub client_order_id: String,
    pub side: String,
    pub count: String,
    pub price: String,
    pub time_in_force: String,
    pub self_trade_prevention_type: String,
    pub post_only: bool,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub reduce_only: Option<bool>,
}

#[derive(Clone, Debug, Deserialize)]
pub struct CreateOrderV2Response {
    pub order_id: String,
    pub client_order_id: Option<String>,
    pub fill_count: String,
    pub remaining_count: String,
    pub ts_ms: i64,
    pub average_fill_price: Option<String>,
    pub average_fee_paid: Option<String>,
}

#[derive(Clone, Debug, Deserialize)]
pub struct KalshiOrder {
    pub order_id: String,
    pub client_order_id: String,
    pub ticker: String,
    pub status: String,
    #[serde(default)]
    pub r#type: Option<String>,
    pub fill_count_fp: String,
    pub remaining_count_fp: String,
    pub initial_count_fp: String,
    pub yes_price_dollars: Option<String>,
    pub created_time: Option<String>,
    pub last_update_time: Option<String>,
    pub taker_fees_dollars: Option<String>,
    pub maker_fees_dollars: Option<String>,
}

#[derive(Clone, Debug, Deserialize)]
pub struct GetOrderResponse {
    pub order: KalshiOrder,
}

#[derive(Clone, Debug, Deserialize)]
pub struct CancelOrderV2Response {
    pub order_id: String,
    pub client_order_id: Option<String>,
    pub reduced_by: String,
    pub ts_ms: i64,
}

#[derive(Clone, Debug, Deserialize)]
pub struct KalshiMarket {
    pub ticker: String,
    #[serde(default)]
    pub event_ticker: String,
    #[serde(default)]
    pub series_ticker: Option<String>,
    #[serde(default)]
    pub status: Option<String>,
    #[serde(default)]
    pub subtitle: Option<String>,
    #[serde(default)]
    pub open_time: Option<String>,
    #[serde(default)]
    pub close_time: Option<String>,
    pub yes_bid_dollars: Option<String>,
    pub yes_ask_dollars: Option<String>,
    pub last_price_dollars: Option<String>,
    pub yes_bid_size_fp: Option<String>,
    pub yes_ask_size_fp: Option<String>,
    pub result: Option<String>,
    pub settlement_value_dollars: Option<String>,
    pub settlement_ts: Option<String>,
    pub updated_time: Option<String>,
    pub price_level_structure: Option<String>,
    #[serde(default)]
    pub price_ranges: Vec<KalshiPriceRange>,
}

#[derive(Clone, Debug, Deserialize)]
#[allow(dead_code)]
pub struct KalshiPriceRange {
    #[serde(default)]
    pub start: Option<String>,
    #[serde(default)]
    pub end: Option<String>,
    #[serde(default)]
    pub step: Option<String>,
}

#[derive(Clone, Debug, Deserialize)]
pub struct GetMarketResponse {
    pub market: KalshiMarket,
}

#[derive(Clone, Debug, Deserialize)]
pub struct KalshiFill {
    #[serde(default)]
    pub trade_id: Option<String>,
    #[serde(default)]
    pub fill_id: Option<String>,
    pub order_id: String,
    #[serde(default, deserialize_with = "null_or_absent_string")]
    pub client_order_id: String,
    /// Official REST fills send both `ticker` and `market_ticker`. A serde
    /// alias on one field rejects that page as a duplicate.
    #[serde(default, rename = "ticker")]
    ticker_raw: Option<String>,
    #[serde(default)]
    market_ticker: Option<String>,
    pub count_fp: String,
    #[serde(default)]
    pub yes_price_dollars: Option<String>,
    #[serde(default)]
    pub ts_ms: Option<i64>,
    #[serde(default)]
    pub ts: Option<i64>,
    #[serde(default)]
    pub created_time: Option<String>,
}

impl KalshiFill {
    pub fn ticker(&self) -> &str {
        self.ticker_raw
            .as_deref()
            .map(str::trim)
            .filter(|s| !s.is_empty())
            .or_else(|| {
                self.market_ticker
                    .as_deref()
                    .map(str::trim)
                    .filter(|s| !s.is_empty())
            })
            .unwrap_or("")
    }
}

#[derive(Clone, Debug, Deserialize)]
pub struct GetBalanceResponse {
    pub balance: i64,
    #[serde(default)]
    pub balance_dollars: Option<String>,
    #[serde(default)]
    pub portfolio_value: Option<i64>,
}

#[derive(Clone, Debug, Deserialize)]
pub struct GetMarketsResponse {
    #[serde(default)]
    pub markets: Vec<KalshiMarket>,
    #[serde(default)]
    pub cursor: Option<String>,
}

#[derive(Clone, Debug, Deserialize)]
pub struct GetFillsResponse {
    #[serde(default)]
    pub fills: Vec<KalshiFill>,
    #[serde(default)]
    pub cursor: Option<String>,
}

#[derive(Clone, Debug, Deserialize)]
pub struct GetOrdersResponse {
    #[serde(default)]
    pub orders: Vec<KalshiOrder>,
    #[serde(default)]
    pub cursor: Option<String>,
}

#[derive(Clone, Debug, Deserialize)]
pub struct WsEnvelope {
    #[serde(rename = "type")]
    pub msg_type: String,
    #[serde(default)]
    pub id: Option<u64>,
    #[serde(default)]
    pub sid: Option<u64>,
    #[serde(default)]
    pub seq: Option<u64>,
    #[serde(default)]
    pub msg: Option<serde_json::Value>,
}

#[derive(Clone, Debug, Deserialize)]
pub struct OrderbookDeltaMsg {
    pub market_ticker: String,
    #[serde(default)]
    pub market_id: Option<String>,
    #[serde(default)]
    pub price_dollars: Option<String>,
    #[serde(default)]
    pub delta_fp: Option<String>,
    #[serde(default)]
    pub side: Option<String>,
    #[serde(default)]
    pub ts_ms: Option<i64>,
}

#[derive(Clone, Debug, Deserialize)]
pub struct OrderbookSnapshotMsg {
    pub market_ticker: String,
    #[serde(default)]
    pub market_id: Option<String>,
    #[serde(default)]
    pub yes_dollars_fp: Option<Vec<[String; 2]>>,
    #[serde(default)]
    pub no_dollars_fp: Option<Vec<[String; 2]>>,
}

#[derive(Clone, Debug, Deserialize)]
pub struct SubscribedMsg {
    pub channel: String,
    pub sid: u64,
}

pub const REST_PRODUCTION: &str = "https://external-api.kalshi.com/trade-api/v2";
pub const REST_PRODUCTION_ORIGIN: &str = "https://external-api.kalshi.com";
/// Official demo Trade API (docs.kalshi.com demo_env).
pub const REST_DEMO: &str = "https://external-api.demo.kalshi.co/trade-api/v2";
/// Also-supported demo host (M8). Prefer REST_DEMO for new observe.
pub const REST_DEMO_SHARED: &str = "https://demo-api.kalshi.co/trade-api/v2";
pub const REST_DEMO_SHARED_ORIGIN: &str = "https://demo-api.kalshi.co";
pub const REST_DEMO_ORIGIN: &str = "https://external-api.demo.kalshi.co";
pub const WS_PRODUCTION: &str = "wss://external-api-ws.kalshi.com/trade-api/ws/v2";
pub const WS_DEMO: &str = "wss://external-api-ws.demo.kalshi.co/trade-api/ws/v2";
pub const WS_DEMO_SHARED: &str = "wss://demo-api.kalshi.co/trade-api/ws/v2";
pub const CREATE_ORDER_PATH: &str = "/trade-api/v2/portfolio/events/orders";
pub const EXCHANGE_STATUS_PATH: &str = "/trade-api/v2/exchange/status";
pub const WS_SIGN_PATH: &str = "/trade-api/ws/v2";
pub const BALANCE_PATH: &str = "/trade-api/v2/portfolio/balance";
pub const INTRA_TRANSFER_PATH: &str = "/trade-api/v2/portfolio/intra_exchange_instance_transfer";
pub const FILLS_PATH: &str = "/trade-api/v2/portfolio/fills";
pub const MARKETS_PATH: &str = "/trade-api/v2/markets";
pub const EVENTS_PATH: &str = "/trade-api/v2/events";
pub const ORDERS_PATH: &str = "/trade-api/v2/portfolio/orders";
pub const POSITIONS_PATH: &str = "/trade-api/v2/portfolio/positions";
pub const SETTLEMENTS_PATH: &str = "/trade-api/v2/portfolio/settlements";
pub const TRADES_PATH: &str = "/trade-api/v2/markets/trades";
pub const HISTORICAL_CUTOFF_PATH: &str = "/trade-api/v2/historical/cutoff";
pub const HISTORICAL_MARKETS_PATH: &str = "/trade-api/v2/historical/markets";
pub const HISTORICAL_TRADES_PATH: &str = "/trade-api/v2/historical/trades";

#[derive(Clone, Debug, Deserialize, Serialize)]
pub struct KalshiTrade {
    pub trade_id: String,
    pub ticker: String,
    pub count_fp: String,
    pub yes_price_dollars: String,
    pub no_price_dollars: String,
    #[serde(default)]
    pub taker_outcome_side: Option<String>,
    #[serde(default)]
    pub taker_book_side: Option<String>,
    #[serde(default)]
    pub taker_side: Option<String>,
    pub created_time: String,
    #[serde(default)]
    pub is_block_trade: bool,
}

#[derive(Clone, Debug, Deserialize, Serialize)]
pub struct GetTradesResponse {
    #[serde(default)]
    pub trades: Vec<KalshiTrade>,
    #[serde(default)]
    pub cursor: Option<String>,
}

#[derive(Clone, Debug, Deserialize, Serialize)]
pub struct HistoricalCutoffResponse {
    /// Unix seconds. Official payloads may send RFC3339 or an integer.
    #[serde(default, deserialize_with = "optional_cutoff_unix")]
    pub market_settled_ts: Option<i64>,
    #[serde(default, deserialize_with = "optional_cutoff_unix")]
    pub trades_created_ts: Option<i64>,
    #[serde(default, deserialize_with = "optional_cutoff_unix")]
    pub orders_updated_ts: Option<i64>,
    #[serde(default, deserialize_with = "optional_cutoff_unix")]
    pub market_positions_last_updated_ts: Option<i64>,
}

#[derive(Clone, Debug, Deserialize, Serialize)]
pub struct BidAskDistribution {
    /// Official historical candles use `open`; older docs used `open_dollars`.
    #[serde(alias = "open")]
    pub open_dollars: String,
    #[serde(alias = "low")]
    pub low_dollars: String,
    #[serde(alias = "high")]
    pub high_dollars: String,
    #[serde(alias = "close")]
    pub close_dollars: String,
}

#[derive(Clone, Debug, Default, Deserialize, Serialize)]
pub struct PriceDistribution {
    #[serde(default, alias = "open")]
    pub open_dollars: Option<String>,
    #[serde(default, alias = "low")]
    pub low_dollars: Option<String>,
    #[serde(default, alias = "high")]
    pub high_dollars: Option<String>,
    #[serde(default, alias = "close")]
    pub close_dollars: Option<String>,
    #[serde(default, alias = "mean")]
    pub mean_dollars: Option<String>,
    #[serde(default, alias = "previous")]
    pub previous_dollars: Option<String>,
}

#[derive(Clone, Debug, Deserialize, Serialize)]
pub struct MarketCandlestick {
    pub end_period_ts: i64,
    pub yes_bid: BidAskDistribution,
    pub yes_ask: BidAskDistribution,
    #[serde(default)]
    pub price: PriceDistribution,
    #[serde(default, alias = "volume")]
    pub volume_fp: String,
    #[serde(default, alias = "open_interest")]
    pub open_interest_fp: String,
}

#[derive(Clone, Debug, Deserialize, Serialize)]
pub struct GetEventsResponse {
    #[serde(default)]
    pub events: Vec<serde_json::Value>,
    #[serde(default)]
    pub cursor: Option<String>,
}

#[derive(Clone, Debug, Deserialize, Serialize)]
pub struct GetMarketCandlesticksResponse {
    pub ticker: String,
    #[serde(default)]
    pub candlesticks: Vec<MarketCandlestick>,
}

#[derive(Clone, Debug, Deserialize, Serialize)]
pub struct GetOrderbookResponse {
    pub orderbook_fp: KalshiOrderbookFp,
}

#[derive(Clone, Debug, Deserialize, Serialize)]
pub struct KalshiOrderbookFp {
    #[serde(default)]
    pub yes_dollars: Vec<[String; 2]>,
    #[serde(default)]
    pub no_dollars: Vec<[String; 2]>,
}

#[cfg(test)]
mod cutoff_ts_tests {
    use super::HistoricalCutoffResponse;

    /// Production `GET /historical/cutoff` observed 2026-08-27 returned RFC3339,
    /// not unix integers. Deserializing that payload as `i64` stalled reconcile.
    const PRODUCTION_CUTOFF: &str = r#"{
        "market_settled_ts":"2026-06-28T00:00:00Z",
        "trades_created_ts":"2026-06-28T00:00:00Z",
        "orders_updated_ts":"2026-06-28T00:00:00Z",
        "market_positions_last_updated_ts":"2026-06-28T00:00:00Z"
    }"#;

    #[test]
    fn cutoff_accepts_production_rfc3339() {
        let parsed: HistoricalCutoffResponse = serde_json::from_str(PRODUCTION_CUTOFF).unwrap();
        assert_eq!(parsed.orders_updated_ts, Some(1_782_604_800));
        assert_eq!(parsed.market_settled_ts, Some(1_782_604_800));
        assert_eq!(parsed.trades_created_ts, Some(1_782_604_800));
        assert_eq!(parsed.market_positions_last_updated_ts, Some(1_782_604_800));
    }

    #[test]
    fn cutoff_accepts_unix_integer() {
        let parsed: HistoricalCutoffResponse =
            serde_json::from_str(r#"{"orders_updated_ts":1700000000}"#).unwrap();
        assert_eq!(parsed.orders_updated_ts, Some(1_700_000_000));
        assert_eq!(parsed.market_settled_ts, None);
    }

    #[test]
    fn candlestick_accepts_unprefixed_historical_fields() {
        let raw = r#"{
            "end_period_ts": 1781400720,
            "open_interest": "13651239.20",
            "price": {"close":"0.7100","high":"0.7400","low":"0.7000","mean":"0.7246","open":"0.7300","previous":"0.7200"},
            "volume": "68982.94",
            "yes_ask": {"close":"0.7100","high":"0.7400","low":"0.7100","open":"0.7300"},
            "yes_bid": {"close":"0.7000","high":"0.7300","low":"0.7000","open":"0.7200"}
        }"#;
        let parsed: super::MarketCandlestick = serde_json::from_str(raw).unwrap();
        assert_eq!(parsed.yes_bid.close_dollars, "0.7000");
        assert_eq!(parsed.volume_fp, "68982.94");
        assert_eq!(parsed.open_interest_fp, "13651239.20");
        assert_eq!(parsed.price.close_dollars.as_deref(), Some("0.7100"));
    }

    #[test]
    fn candlestick_accepts_null_trade_price_keep_yes_bid() {
        let raw = r#"{
            "end_period_ts": 1781766000,
            "open_interest": "60809.37",
            "price": {"close":null,"high":null,"low":null,"mean":null,"open":null,"previous":"0.5400"},
            "volume": "0.00",
            "yes_ask": {"close":"0.5400","high":"0.5400","low":"0.5400","open":"0.5400"},
            "yes_bid": {"close":"0.5300","high":"0.5300","low":"0.5300","open":"0.5300"}
        }"#;
        let parsed: super::MarketCandlestick = serde_json::from_str(raw).unwrap();
        assert_eq!(parsed.yes_bid.close_dollars, "0.5300");
        assert_eq!(parsed.volume_fp, "0.00");
        assert_eq!(parsed.price.close_dollars, None);
    }

    #[test]
    fn cutoff_accepts_unix_string() {
        let parsed: HistoricalCutoffResponse =
            serde_json::from_str(r#"{"orders_updated_ts":"1700000000"}"#).unwrap();
        assert_eq!(parsed.orders_updated_ts, Some(1_700_000_000));
    }
}
