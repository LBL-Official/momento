//! Local Kalshi availability audit for 2025 vs 2026 MLB (W1-A5).
//! Does not query Kalshi. Documents recovery queries without executing them.

use chrono::Datelike;
use serde::{Deserialize, Serialize};

use super::coverage::DimensionStatus;
use super::integrity::IntegrityReport;
use super::observability::ObservabilityKind;

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct YearSlice {
    pub year: i32,
    pub probe_or_partition_dates: u32,
    pub partition_complete_v1_dates: u32,
    pub probe_empty_dates: u32,
    pub games: u32,
    pub markets: u32,
    pub trades: u64,
    pub candle_or_ob_events: u64,
    pub metadata: DimensionStatus,
    pub trades_layer: DimensionStatus,
    pub candles: DimensionStatus,
    pub top_of_book_historical: DimensionStatus,
    pub l2: DimensionStatus,
    pub settlement: DimensionStatus,
    pub market_open_observations: DimensionStatus,
    pub market_close_observations: DimensionStatus,
    pub pbp: DimensionStatus,
    pub notes: Vec<String>,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct RecoveryQuery {
    pub missing: String,
    pub source: String,
    pub query: String,
    pub limitations: String,
    pub launched: bool,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct KalshiAvailabilityAudit {
    pub sport: String,
    pub series: String,
    pub mlb_2025: YearSlice,
    pub mlb_2026: YearSlice,
    pub recovery_queries: Vec<RecoveryQuery>,
    pub observability: ObservabilityKind,
}

pub fn audit_mlb(integrity: &IntegrityReport) -> KalshiAvailabilityAudit {
    let mlb: Vec<_> = integrity
        .partitions
        .iter()
        .filter(|p| p.sport == "MLB")
        .collect();
    let y2025: Vec<_> = mlb
        .iter()
        .filter(|p| p.date.year() == 2025)
        .copied()
        .collect();
    let y2026: Vec<_> = mlb
        .iter()
        .filter(|p| p.date.year() == 2026)
        .copied()
        .collect();

    KalshiAvailabilityAudit {
        sport: "MLB".into(),
        series: "KXMLBGAME".into(),
        mlb_2025: year_slice(2025, &y2025, true),
        mlb_2026: year_slice(2026, &y2026, false),
        recovery_queries: vec![
            RecoveryQuery {
                missing: "2025 KXMLBGAME markets (local lake has only empty probes)".into(),
                source: "Kalshi GET /historical/markets and /historical/trades /historical/markets/{ticker}/candlesticks".into(),
                query: "series_ticker=KXMLBGAME&min_close_ts={pt_day_start}&max_close_ts={pt_day_end} plus min_settled_ts/max_settled_ts; then per ticker historical trades+candles. Official docs: https://docs.kalshi.com/getting_started/historical_data".into(),
                limitations: "As of 2026-08-25 collection, discovery returned 0 markets for 2025 probe dates. Historical retention/cutoff may permanently UNAVAILABLE some days. Do not fabricate.".into(),
                launched: false,
            },
            RecoveryQuery {
                missing: "2026-03-01..2026-06-17 and 2026-07-01..end of season KXMLBGAME".into(),
                source: "Same historical REST as above; Jun 1–17 already probed empty locally".into(),
                query: "Same windowed discovery. Earliest tickers in this lake are 26JUN18.".into(),
                limitations: "Jun 1–17 2026 PROBE_EMPTY at collect time. Rest of season NOT_ATTEMPTED in this lake. W1 does not launch bulk collect.".into(),
                launched: false,
            },
            RecoveryQuery {
                missing: "Historical L2 / queue".into(),
                source: "None retrospectively. Prospective Kalshi WebSocket orderbook_delta only.".into(),
                query: "N/A — no historical L2 endpoint.".into(),
                limitations: "UNAVAILABLE. Never infer from candles or trades.".into(),
                launched: false,
            },
            RecoveryQuery {
                missing: "Market-open / lifetime starting prices".into(),
                source: "Kalshi historical candlesticks+trades from metadata.open_time through settlement, not merely close-day window".into(),
                query: "Per ticker: candlesticks start_ts=open_time, end_ts=close/settlement; trades same bounds.".into(),
                limitations: "v1 collector used PT close/settled calendar day only. First candle on that day is NOT proven market-open. W1 does not backfill lifetime.".into(),
                launched: false,
            },
            RecoveryQuery {
                missing: "MLB PBP / official game state".into(),
                source: "Not Kalshi. Candidate sources (not downloaded): MLB Stats API, Baseball Savant. License/ToS required before W2+.".into(),
                query: "Not authorized in W1.".into(),
                limitations: "PBP = UNAVAILABLE locally. Do not scrape in W1.".into(),
                launched: false,
            },
        ],
        observability: ObservabilityKind::Observed,
    }
}

fn year_slice(
    year: i32,
    parts: &[&super::integrity::PartitionIntegrity],
    all_empty_expected: bool,
) -> YearSlice {
    use super::coverage::PartitionCoverage;
    let complete = parts
        .iter()
        .filter(|p| p.coverage.partition == PartitionCoverage::PartitionCompleteV1)
        .count() as u32;
    let empty = parts
        .iter()
        .filter(|p| p.coverage.partition == PartitionCoverage::ProbeEmpty)
        .count() as u32;
    let games = parts.iter().map(|p| p.unique_event_tickers).sum::<u32>();
    let markets = parts.iter().map(|p| p.unique_tickers).sum::<u32>();
    let trades = parts.iter().map(|p| p.trade_count).sum::<u64>();
    let ob_events = parts.iter().map(|p| p.orderbook_event_count).sum::<u64>();

    let has_content = complete > 0;
    YearSlice {
        year,
        probe_or_partition_dates: parts.len() as u32,
        partition_complete_v1_dates: complete,
        probe_empty_dates: empty,
        games,
        markets,
        trades,
        candle_or_ob_events: ob_events,
        metadata: if has_content {
            DimensionStatus::CompleteForWindow
        } else {
            DimensionStatus::Unavailable
        },
        trades_layer: if has_content {
            DimensionStatus::CompleteForWindow
        } else {
            DimensionStatus::Unavailable
        },
        candles: if has_content {
            DimensionStatus::CompleteForWindow
        } else {
            DimensionStatus::Unavailable
        },
        top_of_book_historical: DimensionStatus::Unavailable,
        l2: DimensionStatus::Unavailable,
        settlement: if has_content {
            DimensionStatus::Discovered
        } else {
            DimensionStatus::Unavailable
        },
        market_open_observations: DimensionStatus::Unavailable,
        market_close_observations: if has_content {
            DimensionStatus::Partial
        } else {
            DimensionStatus::Unavailable
        },
        pbp: DimensionStatus::Unavailable,
        notes: if all_empty_expected {
            vec![
                "2025: no COMPLETE partitions locally. Empty probes are not 2025 games.".into(),
                "Do not fabricate 2025.".into(),
            ]
        } else {
            vec![
                "2026 local COMPLETE window is 2026-06-18..2026-06-30 only (if present).".into(),
                "Jun 1–17 probes are empty. Rest of 2026 not in this lake.".into(),
                "Do not infer L2 from candles. Do not infer open price from first close-day candle.".into(),
            ]
        },
    }
}
