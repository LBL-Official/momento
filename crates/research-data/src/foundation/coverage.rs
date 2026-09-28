//! Canonical coverage vocabulary (W1-A4).
//!
//! v1 DailyManifest `completeness_status` is NEVER redefined.
//! A June 2026 candle partition is not a complete lifetime reconstruction.

use serde::{Deserialize, Serialize};

use crate::manifest::CompletenessStatus;

/// Partition-level coverage (W0 coverage_v2 + user vocabulary mapping).
#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum PartitionCoverage {
    NotAttempted,
    ProbeEmpty,
    PartitionCompleteV1,
    Partial,
    Invalid,
    HistoricalApiUnavailable,
    Missing,
}

impl PartitionCoverage {
    pub fn from_v1(status: CompletenessStatus, markets_discovered: u32) -> Self {
        match status {
            CompletenessStatus::Complete => Self::PartitionCompleteV1,
            CompletenessStatus::Partial => Self::Partial,
            CompletenessStatus::Invalid => Self::Invalid,
            CompletenessStatus::Missing if markets_discovered == 0 => Self::ProbeEmpty,
            CompletenessStatus::Missing => Self::Missing,
        }
    }

    pub fn as_str(self) -> &'static str {
        match self {
            Self::NotAttempted => "NOT_ATTEMPTED",
            Self::ProbeEmpty => "PROBE_EMPTY",
            Self::PartitionCompleteV1 => "PARTITION_COMPLETE_V1",
            Self::Partial => "PARTIAL",
            Self::Invalid => "INVALID",
            Self::HistoricalApiUnavailable => "HISTORICAL_API_UNAVAILABLE",
            Self::Missing => "MISSING",
        }
    }
}

/// Per-dimension observation status (user-required vocabulary).
#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum DimensionStatus {
    Discovered,
    Partial,
    CompleteForSource,
    CompleteForWindow,
    Missing,
    Unavailable,
    NotApplicable,
}

impl DimensionStatus {
    pub fn as_str(self) -> &'static str {
        match self {
            Self::Discovered => "DISCOVERED",
            Self::Partial => "PARTIAL",
            Self::CompleteForSource => "COMPLETE_FOR_SOURCE",
            Self::CompleteForWindow => "COMPLETE_FOR_WINDOW",
            Self::Missing => "MISSING",
            Self::Unavailable => "UNAVAILABLE",
            Self::NotApplicable => "NOT_APPLICABLE",
        }
    }
}

pub const DIMENSION_VOCABULARY: &str = "\
DISCOVERED = source listed the object. \
PARTIAL = some but not all of the object's history is in the lake. \
COMPLETE_FOR_SOURCE = source has nothing further for this object (still may be window-limited). \
COMPLETE_FOR_WINDOW = complete relative to the v1 close/settled PT-day window only. \
MISSING = expected but not in this partition. \
UNAVAILABLE = cannot be obtained from known sources (e.g. historical L2, PBP locally). \
NOT_APPLICABLE = dimension does not apply (e.g. NBA in an MLB-only scan). \
PARTITION_COMPLETE_V1 ≠ lifetime-complete ≠ L2-complete ≠ PBP-complete. \
LIFETIME_UNVERIFIED = v1 partition is complete for the close/settled window but \
open_time→settlement path is not proven (dimension lifetime_path=UNAVAILABLE).";

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct CoverageRecord {
    pub v1_completeness: CompletenessStatus,
    pub partition: PartitionCoverage,
    pub market_discovered: DimensionStatus,
    pub market_fully_observed: DimensionStatus,
    pub settlement_observed: DimensionStatus,
    pub lifetime_path: DimensionStatus,
    pub tick_history: DimensionStatus,
    pub candle_1m: DimensionStatus,
    pub top_of_book: DimensionStatus,
    pub l2: DimensionStatus,
    pub pbp: DimensionStatus,
    pub synchronized_state: DimensionStatus,
    pub starting_price: DimensionStatus,
    pub notes: Vec<String>,
}

impl CoverageRecord {
    /// Honest mapping from a v1 daily manifest plus optional metadata facts.
    pub fn for_kalshi_v1_partition(
        v1: CompletenessStatus,
        markets_discovered: u32,
        trade_count: u64,
        orderbook_event_count: u64,
        settlement_rows: u32,
        metadata_rows: u32,
    ) -> Self {
        let partition = PartitionCoverage::from_v1(v1, markets_discovered);
        if matches!(
            partition,
            PartitionCoverage::ProbeEmpty | PartitionCoverage::Missing
        ) {
            return Self {
                v1_completeness: v1,
                partition,
                market_discovered: DimensionStatus::Missing,
                market_fully_observed: DimensionStatus::Unavailable,
                settlement_observed: DimensionStatus::Missing,
                lifetime_path: DimensionStatus::Unavailable,
                tick_history: DimensionStatus::Unavailable,
                candle_1m: DimensionStatus::Unavailable,
                top_of_book: DimensionStatus::Unavailable,
                l2: DimensionStatus::Unavailable,
                pbp: DimensionStatus::Unavailable,
                synchronized_state: DimensionStatus::Unavailable,
                starting_price: DimensionStatus::Unavailable,
                notes: vec![
                    "v1 MISSING/empty probe: 0 markets discovered for this PT close/settled window."
                        .into(),
                    "Do not infer that Kalshi never listed these games; record as PROBE_EMPTY."
                        .into(),
                    "PBP = UNAVAILABLE. L2_HISTORICAL_UNAVAILABLE. STARTING_PRICE_UNVERIFIED.".into(),
                ],
            };
        }

        let market_discovered = if markets_discovered > 0 {
            DimensionStatus::CompleteForWindow
        } else {
            DimensionStatus::Missing
        };

        let candle_1m = if orderbook_event_count > 0 {
            DimensionStatus::CompleteForWindow
        } else {
            DimensionStatus::Missing
        };

        let tick_history = if trade_count > 0 {
            // Public trades are trade prints, not quote ticks.
            DimensionStatus::Partial
        } else {
            DimensionStatus::Missing
        };

        let settlement_observed = if settlement_rows > 0 && metadata_rows > 0 {
            if settlement_rows == metadata_rows {
                DimensionStatus::Discovered
            } else {
                DimensionStatus::Partial
            }
        } else {
            DimensionStatus::Missing
        };

        Self {
            v1_completeness: v1,
            partition,
            market_discovered,
            market_fully_observed: DimensionStatus::Partial,
            settlement_observed,
            lifetime_path: DimensionStatus::Unavailable,
            tick_history,
            candle_1m,
            top_of_book: DimensionStatus::Unavailable,
            l2: DimensionStatus::Unavailable,
            pbp: DimensionStatus::Unavailable,
            synchronized_state: DimensionStatus::Unavailable,
            starting_price: DimensionStatus::Unavailable,
            notes: vec![
                "PARTITION_COMPLETE_V1 means all discovered close/settled-day markets were collected."
                    .into(),
                "Not equivalent to lifetime market reconstruction.".into(),
                "Candles are 1-minute close bid/ask, not ticks, not L2.".into(),
                "Public trades ≠ quote ticks. L2_HISTORICAL_UNAVAILABLE. PBP = UNAVAILABLE.".into(),
                "STARTING_PRICE_UNVERIFIED: first candle in this file is not MARKET_OPEN_PRICE.".into(),
                "PIT REST snapshots at ingest are not historical top-of-book.".into(),
            ],
        }
    }
}
