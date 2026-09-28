//! Normalized NBA warehouse records.
//!
//! Historical Kalshi `KXNBAGAME` data is 1-minute top-of-book / candlestick
//! data plus public trades. It is **not** historical L2.

use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use serde_json::Value;

pub const SCHEMA_VERSION: &str = "nba_market_data_schema_v1";
pub const NCAAB_SCHEMA_VERSION: &str = "ncaab_market_data_schema_v1";
pub const TENNIS_SCHEMA_VERSION: &str = "tennis_market_data_schema_v1";
pub const MARKET_DATA_TYPE_CANDLE_TOB: &str = "CANDLESTICK_TOP_OF_BOOK";
pub const MARKET_DATA_TYPE_L2_SNAPSHOT: &str = "L2_SNAPSHOT";
pub const MARKET_DATA_TYPE_L2_DELTA: &str = "L2_DELTA";

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum SeasonPhase {
    Exhibition,
    Preseason,
    RegularSeason,
    PlayIn,
    Playoffs,
    Finals,
    ConferenceTournament,
    NcaaTournament,
    OtherPostseason,
    /// Tennis only: Australian Open, Roland Garros, Wimbledon, US Open.
    GrandSlam,
    Unknown,
}

impl SeasonPhase {
    pub fn as_str(self) -> &'static str {
        match self {
            Self::Exhibition => "EXHIBITION",
            Self::Preseason => "PRESEASON",
            Self::RegularSeason => "REGULAR_SEASON",
            Self::PlayIn => "PLAY_IN",
            Self::Playoffs => "PLAYOFFS",
            Self::Finals => "FINALS",
            Self::ConferenceTournament => "CONFERENCE_TOURNAMENT",
            Self::NcaaTournament => "NCAA_TOURNAMENT",
            Self::OtherPostseason => "OTHER_POSTSEASON",
            Self::GrandSlam => "GRAND_SLAM",
            Self::Unknown => "UNKNOWN",
        }
    }

    pub fn parse(raw: &str) -> Self {
        match raw {
            "EXHIBITION" => Self::Exhibition,
            "PRESEASON" => Self::Preseason,
            "REGULAR_SEASON" => Self::RegularSeason,
            "PLAY_IN" => Self::PlayIn,
            "PLAYOFFS" => Self::Playoffs,
            "FINALS" => Self::Finals,
            "CONFERENCE_TOURNAMENT" => Self::ConferenceTournament,
            "NCAA_TOURNAMENT" => Self::NcaaTournament,
            "OTHER_POSTSEASON" => Self::OtherPostseason,
            "GRAND_SLAM" => Self::GrandSlam,
            _ => Self::Unknown,
        }
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum JobStatus {
    Pending,
    Downloading,
    Complete,
    Failed,
    Retry,
}

impl JobStatus {
    pub fn as_str(self) -> &'static str {
        match self {
            Self::Pending => "PENDING",
            Self::Downloading => "DOWNLOADING",
            Self::Complete => "COMPLETE",
            Self::Failed => "FAILED",
            Self::Retry => "RETRY",
        }
    }
}

/// Dollar string → integer ten-thousandths (`0.7100` → `7100`). No f64.
pub fn dollars_to_e4(raw: &str) -> Option<i64> {
    let s = raw.trim();
    if s.is_empty() {
        return None;
    }
    let (sign, s) = if let Some(rest) = s.strip_prefix('-') {
        (-1i64, rest)
    } else {
        (1i64, s)
    };
    let (whole, frac) = match s.split_once('.') {
        Some((w, f)) => (w, f),
        None => (s, ""),
    };
    if whole.is_empty() || !whole.chars().all(|c| c.is_ascii_digit()) {
        return None;
    }
    if !frac.chars().all(|c| c.is_ascii_digit()) || frac.len() > 6 {
        return None;
    }
    let whole_n: i64 = whole.parse().ok()?;
    let mut e4 = 0i64;
    for (i, ch) in frac.chars().enumerate() {
        let d = i64::from(ch.to_digit(10)?);
        match i {
            0 => e4 += d * 1000,
            1 => e4 += d * 100,
            2 => e4 += d * 10,
            3 => e4 += d,
            _ if d != 0 => return None,
            _ => {}
        }
    }
    whole_n
        .checked_mul(10_000)?
        .checked_add(e4)?
        .checked_mul(sign)
}

pub fn count_fp_to_hundredths(raw: &str) -> Option<i64> {
    momento_kalshi::count_fp_to_hundredths(raw).ok()
}

pub fn parse_rfc3339(raw: &str) -> Option<DateTime<Utc>> {
    DateTime::parse_from_rfc3339(raw)
        .ok()
        .map(|dt| dt.with_timezone(&Utc))
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct NbaEventRow {
    pub event_id: String,
    pub event_ticker: String,
    pub series_ticker: String,
    pub event_title: Option<String>,
    pub event_subtitle: Option<String>,
    pub event_category: Option<String>,
    pub mutually_exclusive: Option<bool>,
    pub last_updated_ts: Option<String>,
    pub sport: String,
    pub league: String,
    pub season: String,
    pub season_phase: String,
    pub phase_method: String,
    pub home_team_code: Option<String>,
    pub away_team_code: Option<String>,
    pub game_date: Option<String>,
    pub source: String,
    pub ingested_at: DateTime<Utc>,
    pub schema_version: String,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct NbaMarketRow {
    pub market_id: String,
    pub ticker: String,
    pub event_id: String,
    pub game_id: String,
    pub series_ticker: String,
    pub market_title: Option<String>,
    pub yes_subtitle: Option<String>,
    pub no_subtitle: Option<String>,
    pub team: Option<String>,
    pub opponent: Option<String>,
    pub market_status: Option<String>,
    pub result: Option<String>,
    pub settlement_value_e4: Option<i64>,
    pub volume_hundredths: Option<i64>,
    pub open_interest_hundredths: Option<i64>,
    pub last_price_e4: Option<i64>,
    pub yes_bid_e4: Option<i64>,
    pub yes_ask_e4: Option<i64>,
    pub open_time: Option<String>,
    pub close_time: Option<String>,
    pub expiration_time: Option<String>,
    pub settlement_time: Option<String>,
    pub created_time: Option<String>,
    pub updated_time: Option<String>,
    pub occurrence_datetime: Option<String>,
    pub sport: String,
    pub league: String,
    pub season: String,
    pub season_phase: String,
    pub source: String,
    pub ingested_at: DateTime<Utc>,
    pub schema_version: String,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct NbaGameRow {
    pub game_id: String,
    pub event_id: String,
    pub event_ticker: String,
    pub season: String,
    pub season_phase: String,
    pub phase_method: String,
    pub game_date: Option<String>,
    pub scheduled_start: Option<String>,
    pub home_team: Option<String>,
    pub away_team: Option<String>,
    pub home_team_code: Option<String>,
    pub away_team_code: Option<String>,
    pub home_market_ticker: Option<String>,
    pub away_market_ticker: Option<String>,
    pub market_tickers: Vec<String>,
    pub market_count: u32,
    pub event_status: Option<String>,
    pub settlement_status: Option<String>,
    pub event_title: Option<String>,
    pub event_subtitle: Option<String>,
    pub source: String,
    pub schema_version: String,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct NbaCandleRow {
    pub ticker: String,
    pub event_id: String,
    pub market_id: String,
    pub game_id: String,
    pub end_period_ts: i64,
    pub start_time: DateTime<Utc>,
    pub end_time: DateTime<Utc>,
    pub yes_bid_open_e4: Option<i64>,
    pub yes_bid_high_e4: Option<i64>,
    pub yes_bid_low_e4: Option<i64>,
    pub yes_bid_close_e4: Option<i64>,
    pub yes_ask_open_e4: Option<i64>,
    pub yes_ask_high_e4: Option<i64>,
    pub yes_ask_low_e4: Option<i64>,
    pub yes_ask_close_e4: Option<i64>,
    pub price_open_e4: Option<i64>,
    pub price_high_e4: Option<i64>,
    pub price_low_e4: Option<i64>,
    pub price_close_e4: Option<i64>,
    pub price_mean_e4: Option<i64>,
    pub price_previous_e4: Option<i64>,
    pub volume_hundredths: Option<i64>,
    pub open_interest_hundredths: Option<i64>,
    pub market_data_type: String,
    pub orderbook_depth_available: bool,
    pub is_valid: bool,
    pub is_duplicate: bool,
    pub is_pre_market: bool,
    pub is_post_market: bool,
    pub source: String,
    pub ingested_at: DateTime<Utc>,
    pub schema_version: String,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct NbaTradeRow {
    pub trade_id: String,
    pub ticker: String,
    pub event_id: String,
    pub market_id: String,
    pub game_id: String,
    pub timestamp: DateTime<Utc>,
    pub yes_price_e4: Option<i64>,
    pub no_price_e4: Option<i64>,
    pub quantity_hundredths: Option<i64>,
    pub taker_outcome_side: Option<String>,
    pub taker_book_side: Option<String>,
    pub taker_side: Option<String>,
    pub side_classification: String,
    pub is_block_trade: bool,
    pub is_duplicate: bool,
    pub source: String,
    pub ingested_at: DateTime<Utc>,
    pub schema_version: String,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct CausalCandleFeatures {
    pub ticker: String,
    pub end_period_ts: i64,
    pub mid_close_e4: Option<i64>,
    pub spread_e4: Option<i64>,
    pub spread_bps: Option<i64>,
    pub return_1m_e4: Option<i64>,
    pub return_5m_e4: Option<i64>,
    pub return_15m_e4: Option<i64>,
    pub look_ahead: bool,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct ComplementarityRow {
    pub event_id: String,
    pub end_period_ts: i64,
    pub a_ticker: String,
    pub b_ticker: String,
    pub a_mid_e4: Option<i64>,
    pub b_mid_e4: Option<i64>,
    pub combined_mid_e4: Option<i64>,
    pub complementarity_error_e4: Option<i64>,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct TradeMinuteAgg {
    pub ticker: String,
    pub minute_ts: i64,
    pub trade_count: u64,
    pub trade_volume_hundredths: i64,
    pub average_trade_size_hundredths: Option<i64>,
    pub median_trade_size_hundredths: Option<i64>,
    pub max_trade_size_hundredths: Option<i64>,
    pub buy_volume_hundredths: i64,
    pub sell_volume_hundredths: i64,
    pub unknown_side_volume_hundredths: i64,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct TickerJob {
    pub ticker: String,
    pub event_ticker: String,
    pub dataset_type: String,
    pub status: String,
    pub attempts: u32,
    pub started_at: Option<DateTime<Utc>>,
    pub completed_at: Option<DateTime<Utc>>,
    pub row_count: u64,
    pub error: Option<String>,
    pub checksum: Option<String>,
    pub cursor: Option<String>,
}

#[derive(Clone, Debug, Default, Serialize, Deserialize)]
pub struct IngestionManifest {
    pub jobs: Vec<TickerJob>,
}

impl IngestionManifest {
    pub fn job(&self, ticker: &str, dataset: &str) -> Option<&TickerJob> {
        self.jobs
            .iter()
            .find(|j| j.ticker == ticker && j.dataset_type == dataset)
    }

    pub fn job_mut(&mut self, ticker: &str, dataset: &str) -> &mut TickerJob {
        if let Some(i) = self
            .jobs
            .iter()
            .position(|j| j.ticker == ticker && j.dataset_type == dataset)
        {
            return &mut self.jobs[i];
        }
        self.jobs.push(TickerJob {
            ticker: ticker.to_string(),
            event_ticker: String::new(),
            dataset_type: dataset.to_string(),
            status: JobStatus::Pending.as_str().into(),
            attempts: 0,
            started_at: None,
            completed_at: None,
            row_count: 0,
            error: None,
            checksum: None,
            cursor: None,
        });
        self.jobs.last_mut().expect("just pushed")
    }
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct DatasetManifest {
    pub dataset_name: String,
    pub sport: String,
    pub series: String,
    pub season: String,
    pub generation_timestamp: DateTime<Utc>,
    pub api_base: String,
    pub historical_cutoff: Option<Value>,
    pub events_count: u64,
    pub markets_count: u64,
    pub games_count: u64,
    pub candles_count: u64,
    pub trades_count: u64,
    pub date_min: Option<String>,
    pub date_max: Option<String>,
    pub schema_version: String,
    pub code_version: String,
    pub checksum: String,
    pub market_data_type: String,
    pub orderbook_depth_available: bool,
}

#[derive(Clone, Debug, Default, Serialize, Deserialize)]
pub struct WarehouseReport {
    pub sport: String,
    pub series: String,
    pub season: String,
    pub events: u64,
    pub markets: u64,
    pub games: u64,
    pub games_with_two_markets: u64,
    pub games_missing_market: u64,
    pub candles: u64,
    pub trades: u64,
    pub markets_with_candles: u64,
    pub markets_without_candles: u64,
    pub markets_with_trades: u64,
    pub markets_without_trades: u64,
    pub earliest_candle: Option<String>,
    pub latest_candle: Option<String>,
    pub duplicate_candles: u64,
    pub duplicate_trades: u64,
    pub failed_requests: u64,
    pub coverage_ratio: Option<String>,
    pub anomalies: Vec<String>,
    pub validation_status: String,
}

pub fn json_str(v: &Value, key: &str) -> Option<String> {
    v.get(key).and_then(|x| {
        if x.is_null() {
            None
        } else if let Some(s) = x.as_str() {
            Some(s.to_string())
        } else {
            Some(x.to_string())
        }
    })
}

pub fn json_bool(v: &Value, key: &str) -> Option<bool> {
    v.get(key).and_then(|x| x.as_bool())
}
