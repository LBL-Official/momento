//! Canonical provenance model (W1-A2).
//!
//! Distinguishes collector time from exchange/event time. `received_at` is never
//! treated as exchange time unless `TimestampRole::ExchangeOrEvent` is proven.

use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};

use super::observability::ObservabilityKind;

/// What a timestamp actually measures.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum TimestampRole {
    /// Kalshi trade `created_time` or similar venue event time.
    ExchangeOrEvent,
    /// Candle `end_period_ts` — end of a 1-minute bucket, not a tick.
    CandlePeriodEnd,
    /// Collector `received_at` / ingest wall clock.
    Ingestion,
    /// Market metadata `open_time` / `close_time` / `settlement_ts` as strings from venue.
    VenueMetadata,
    /// Unknown / not present.
    Unknown,
}

pub const TIMESTAMP_ROLE_NOTES: &str = "\
v1 RawMarketEvent.received_at is Ingestion (collector clock at backfill). \
Trade exchange time lives inside payload.created_time. \
Candle time is payload.end_period_ts (period end). \
REST orderbook snapshots in v1 have no historical exchange ts.";

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum SourceTimestampKind {
    TradeCreated,
    CandleEnd,
    VenueMetadata,
    IngestOnly,
    Unknown,
}

/// Traceability record for a dataset or file (not per-tick unless envelope v2).
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct ProvenanceRecord {
    pub source: String,
    pub retrieval_timestamp: Option<DateTime<Utc>>,
    pub source_timestamp_semantics: TimestampRole,
    pub collector_version: Option<String>,
    pub schema_version: Option<String>,
    pub request_query: Option<String>,
    pub original_path: String,
    pub checksum_sha256: Option<String>,
    pub coverage_period: Option<String>,
    pub coverage_status: String,
    pub observability: ObservabilityKind,
    pub notes: Vec<String>,
}

/// Optional capture metadata for a lake file provenance row.
///
/// Grouped so `for_lake_file` stays within Clippy's argument limit without
/// dropping fields. W1 catalog time leaves collector version and retrieval
/// unset; other callers may populate them.
#[derive(Clone, Debug, Default)]
pub struct LakeFileCapture {
    pub collector_version: Option<String>,
    pub schema_version: Option<String>,
    pub retrieval_timestamp: Option<DateTime<Utc>>,
}

impl ProvenanceRecord {
    /// File-level provenance. `request_query` and `coverage_period` stay unset;
    /// observability is Observed for the file's existence on disk.
    pub fn for_lake_file(
        source: impl Into<String>,
        path: impl Into<String>,
        checksum: Option<String>,
        capture: LakeFileCapture,
        coverage_status: impl Into<String>,
        semantics: TimestampRole,
        notes: Vec<String>,
    ) -> Self {
        Self {
            source: source.into(),
            retrieval_timestamp: capture.retrieval_timestamp,
            source_timestamp_semantics: semantics,
            collector_version: capture.collector_version,
            schema_version: capture.schema_version,
            request_query: None,
            original_path: path.into(),
            checksum_sha256: checksum,
            coverage_period: None,
            coverage_status: coverage_status.into(),
            observability: ObservabilityKind::Observed,
            notes,
        }
    }
}
