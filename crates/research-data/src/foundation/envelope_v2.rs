//! Additive raw envelope v2 (W1-A4 / W1-LEDGER-A2). Never overwrites v1 gzip.

use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};

use crate::schema::RawMarketEvent;

use super::ENVELOPE_V2_SCHEMA;
use super::observability::ObservabilityKind;
use super::provenance::SourceTimestampKind;

#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
pub struct RawEnvelopeV2 {
    pub schema_version: String,
    pub source: String,
    pub endpoint: String,
    pub ticker: Option<String>,
    pub source_record_id: Option<String>,
    pub source_timestamp: Option<String>,
    pub source_timestamp_kind: SourceTimestampKind,
    /// Why `source_timestamp` is absent. Never a substitute clock.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub source_timestamp_missing_reason: Option<String>,
    pub ingestion_timestamp: DateTime<Utc>,
    pub raw_file: String,
    pub line: u64,
    pub payload_sha256: String,
    /// Payload presence. Not “game-time L2 exists.” PIT books stay `IngestOnly`.
    pub observability: ObservabilityKind,
    pub payload: serde_json::Value,
}

pub fn payload_sha256(payload: &serde_json::Value) -> String {
    let bytes = serde_json::to_vec(payload).unwrap_or_default();
    format!("{:x}", Sha256::digest(bytes))
}

/// Lift a v1 raw row into v2 without mutating the v1 file.
///
/// `source_timestamp` is taken from the payload when a documented field exists.
/// Otherwise it is None with `IngestOnly` — never filled from `received_at`.
pub fn envelope_from_v1(v1: &RawMarketEvent, raw_file: &str, line: u64) -> RawEnvelopeV2 {
    let (source_timestamp, kind, record_id, missing_reason) = extract_source_clock(v1);
    RawEnvelopeV2 {
        schema_version: ENVELOPE_V2_SCHEMA.to_string(),
        source: v1.source.clone(),
        endpoint: v1.endpoint.clone(),
        ticker: v1.ticker.clone(),
        source_record_id: record_id,
        source_timestamp,
        source_timestamp_kind: kind,
        source_timestamp_missing_reason: missing_reason,
        ingestion_timestamp: v1.received_at,
        raw_file: raw_file.to_string(),
        line,
        payload_sha256: payload_sha256(&v1.payload),
        observability: ObservabilityKind::Observed,
        payload: v1.payload.clone(),
    }
}

fn extract_source_clock(
    v1: &RawMarketEvent,
) -> (
    Option<String>,
    SourceTimestampKind,
    Option<String>,
    Option<String>,
) {
    match v1.endpoint.as_str() {
        "markets/trades" => {
            let ts = v1
                .payload
                .get("created_time")
                .and_then(|v| v.as_str())
                .map(str::to_string);
            let id = v1
                .payload
                .get("trade_id")
                .and_then(|v| v.as_str())
                .map(str::to_string);
            let kind = if ts.is_some() {
                SourceTimestampKind::TradeCreated
            } else {
                SourceTimestampKind::Unknown
            };
            let missing = ts
                .is_none()
                .then_some("trade payload missing created_time".to_string());
            (ts, kind, id, missing)
        }
        "candlesticks" => candle_source_clock(&v1.payload, v1.ticker.clone()),
        "markets/orderbook" => (
            None,
            SourceTimestampKind::IngestOnly,
            v1.ticker.clone(),
            Some("PIT REST book is ingest-time only; not game-time L2".into()),
        ),
        "market_metadata" => {
            let ts = v1
                .payload
                .get("open_time")
                .and_then(|v| v.as_str())
                .map(str::to_string);
            let missing = ts
                .is_none()
                .then_some("metadata payload missing open_time".to_string());
            (
                ts,
                SourceTimestampKind::VenueMetadata,
                v1.ticker.clone(),
                missing,
            )
        }
        _ => (
            None,
            SourceTimestampKind::IngestOnly,
            v1.ticker.clone(),
            Some(format!(
                "endpoint {} has no documented exchange clock",
                v1.endpoint
            )),
        ),
    }
}

fn candle_source_clock(
    payload: &serde_json::Value,
    ticker: Option<String>,
) -> (
    Option<String>,
    SourceTimestampKind,
    Option<String>,
    Option<String>,
) {
    // Closeout bar: CandleEnd must never pair with an empty source_timestamp.
    if let Some(ts) = unix_seconds_to_rfc3339(payload.get("end_period_ts")) {
        return (Some(ts), SourceTimestampKind::CandleEnd, ticker, None);
    }
    let Some(arr) = payload.get("candlesticks").and_then(|v| v.as_array()) else {
        return (
            None,
            SourceTimestampKind::Unknown,
            ticker,
            Some("candlestick payload has no end_period_ts".into()),
        );
    };
    let ends: Vec<String> = arr
        .iter()
        .filter_map(|c| unix_seconds_to_rfc3339(c.get("end_period_ts")))
        .collect();
    match ends.as_slice() {
        [] => (
            None,
            SourceTimestampKind::Unknown,
            ticker,
            Some("candlesticks[] missing end_period_ts".into()),
        ),
        [only] => (
            Some(only.clone()),
            SourceTimestampKind::CandleEnd,
            ticker,
            None,
        ),
        [.., last] => (
            Some(last.clone()),
            SourceTimestampKind::CandleEnd,
            Some(format!("candlestick_batch_count={}", arr.len())),
            None,
        ),
    }
}

fn unix_seconds_to_rfc3339(value: Option<&serde_json::Value>) -> Option<String> {
    let ts = value.and_then(|v| v.as_i64())?;
    DateTime::<Utc>::from_timestamp(ts, 0).map(|d| d.to_rfc3339())
}

#[cfg(test)]
mod tests {
    use super::*;
    use chrono::TimeZone;

    #[test]
    fn received_at_is_not_copied_to_source_timestamp_for_orderbook() {
        let v1 = RawMarketEvent {
            received_at: Utc.with_ymd_and_hms(2026, 8, 25, 17, 51, 0).unwrap(),
            source: "rest".into(),
            endpoint: "markets/orderbook".into(),
            ticker: Some("KXMLBGAME-X".into()),
            payload: serde_json::json!({"orderbook_fp": {}}),
        };
        let v2 = envelope_from_v1(&v1, "events.jsonl.gz", 1);
        assert!(v2.source_timestamp.is_none());
        assert_eq!(v2.source_timestamp_kind, SourceTimestampKind::IngestOnly);
        assert_eq!(v2.ingestion_timestamp, v1.received_at);
        assert_eq!(v2.observability, ObservabilityKind::Observed);
        assert!(
            v2.source_timestamp_missing_reason
                .as_deref()
                .unwrap()
                .contains("ingest-time")
        );
    }

    #[test]
    fn single_candlestick_copies_end_period_ts() {
        let v1 = RawMarketEvent {
            received_at: Utc.with_ymd_and_hms(2026, 8, 25, 17, 51, 0).unwrap(),
            source: "rest".into(),
            endpoint: "candlesticks".into(),
            ticker: Some("T".into()),
            payload: serde_json::json!({
                "ticker": "T",
                "candlesticks": [{"end_period_ts": 1718668800}]
            }),
        };
        let v2 = envelope_from_v1(&v1, "events.jsonl.gz", 2);
        assert_eq!(
            v2.source_timestamp.as_deref(),
            Some("2024-06-18T00:00:00+00:00")
        );
        assert_eq!(v2.source_timestamp_kind, SourceTimestampKind::CandleEnd);
        assert!(v2.source_timestamp_missing_reason.is_none());
        assert_ne!(
            v2.source_timestamp.as_deref(),
            Some(v1.received_at.to_rfc3339().as_str())
        );
    }

    #[test]
    fn candlestick_batch_preserves_last_end_period_ts_as_envelope_clock() {
        let v1 = RawMarketEvent {
            received_at: Utc.with_ymd_and_hms(2026, 8, 25, 17, 51, 0).unwrap(),
            source: "rest".into(),
            endpoint: "candlesticks".into(),
            ticker: Some("T".into()),
            payload: serde_json::json!({
                "candlesticks": [
                    {"end_period_ts": 1718668800},
                    {"end_period_ts": 1718668860}
                ]
            }),
        };
        let v2 = envelope_from_v1(&v1, "events.jsonl.gz", 4);
        assert_eq!(
            v2.source_timestamp.as_deref(),
            Some("2024-06-18T00:01:00+00:00")
        );
        assert_eq!(v2.source_timestamp_kind, SourceTimestampKind::CandleEnd);
        assert_eq!(
            v2.source_record_id.as_deref(),
            Some("candlestick_batch_count=2")
        );
        assert_eq!(
            v2.payload["candlesticks"][0]["end_period_ts"].as_i64(),
            Some(1718668800)
        );
        assert_ne!(
            v2.source_timestamp.as_deref(),
            Some(v1.received_at.to_rfc3339().as_str())
        );
    }

    #[test]
    fn candle_end_never_pairs_with_empty_source_timestamp() {
        let cases = [
            serde_json::json!({"end_period_ts": 1718668800}),
            serde_json::json!({"candlesticks": [{"end_period_ts": 1718668800}]}),
            serde_json::json!({
                "candlesticks": [
                    {"end_period_ts": 1718668800},
                    {"end_period_ts": 1718668860}
                ]
            }),
            serde_json::json!({}),
            serde_json::json!({"candlesticks": []}),
        ];
        for payload in cases {
            let v1 = RawMarketEvent {
                received_at: Utc.with_ymd_and_hms(2026, 8, 25, 17, 51, 0).unwrap(),
                source: "rest".into(),
                endpoint: "candlesticks".into(),
                ticker: Some("T".into()),
                payload,
            };
            let v2 = envelope_from_v1(&v1, "events.jsonl.gz", 1);
            if v2.source_timestamp_kind == SourceTimestampKind::CandleEnd {
                assert!(
                    v2.source_timestamp.is_some(),
                    "CandleEnd requires source_timestamp"
                );
            }
        }
    }

    #[test]
    fn trade_uses_created_time() {
        let v1 = RawMarketEvent {
            received_at: Utc.with_ymd_and_hms(2026, 8, 25, 17, 51, 0).unwrap(),
            source: "rest".into(),
            endpoint: "markets/trades".into(),
            ticker: Some("T".into()),
            payload: serde_json::json!({
                "created_time": "2026-06-18T00:01:00Z",
                "trade_id": "abc"
            }),
        };
        let v2 = envelope_from_v1(&v1, "events.jsonl.gz", 3);
        assert_eq!(v2.source_timestamp.as_deref(), Some("2026-06-18T00:01:00Z"));
        assert_eq!(v2.source_timestamp_kind, SourceTimestampKind::TradeCreated);
        assert_eq!(v2.source_record_id.as_deref(), Some("abc"));
        assert_eq!(v2.line, 3);
    }
}
