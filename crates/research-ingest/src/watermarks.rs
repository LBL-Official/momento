//! Persistent watermarks. Never advance past a failed/uncommitted partition.

use std::fs;
use std::path::Path;

use chrono::NaiveDate;

use crate::error::IngestError;
use crate::paths::write_json_atomic;
use crate::types::{
    CoverageRow, PartitionStatus, SOURCE_KALSHI, SOURCE_KALSHI_DISCOVERY, SOURCE_STATSAPI,
    Watermark, WatermarkState,
};

pub fn load_watermarks(path: &Path) -> Result<WatermarkState, IngestError> {
    if !path.exists() {
        return Ok(WatermarkState::default());
    }
    let body = fs::read_to_string(path)?;
    Ok(serde_json::from_str(&body)?)
}

pub fn store_watermarks(path: &Path, state: &WatermarkState) -> Result<(), IngestError> {
    write_json_atomic(path, state)
}

fn parse_date(s: &str) -> Option<NaiveDate> {
    NaiveDate::parse_from_str(s, "%Y-%m-%d").ok()
}

fn date_blocked(statuses: &[PartitionStatus]) -> bool {
    statuses
        .iter()
        .any(|s| matches!(s, PartitionStatus::Failed | PartitionStatus::NotAttempted))
}

fn date_progress(statuses: &[PartitionStatus]) -> bool {
    statuses.iter().any(|s| {
        matches!(
            s,
            PartitionStatus::Complete
                | PartitionStatus::AlreadyKnown
                | PartitionStatus::VersionConflict
                | PartitionStatus::Discovered
                | PartitionStatus::Unmatched
                | PartitionStatus::Ambiguous
                | PartitionStatus::Skipped
                | PartitionStatus::Unavailable
        )
    })
}

/// Contiguous prefix watermark: first blocked date stops advancement.
pub fn contiguous_watermark(rows: &[CoverageRow], source: &str) -> Option<String> {
    let mut by_date: std::collections::BTreeMap<NaiveDate, Vec<PartitionStatus>> =
        std::collections::BTreeMap::new();
    for row in rows.iter().filter(|r| r.source == source) {
        if let Some(d) = parse_date(&row.date) {
            by_date.entry(d).or_default().push(row.status);
        }
    }
    let mut mark: Option<NaiveDate> = None;
    for (date, statuses) in by_date {
        if date_blocked(&statuses) {
            break;
        }
        if date_progress(&statuses) {
            mark = Some(date);
        }
    }
    mark.map(|d| d.to_string())
}

pub fn compute_state(rows: &[CoverageRow]) -> WatermarkState {
    let mut mlb_dates = Vec::new();
    let mut kalshi_dates = Vec::new();
    for row in rows {
        let progress = matches!(
            row.status,
            PartitionStatus::Complete
                | PartitionStatus::AlreadyKnown
                | PartitionStatus::VersionConflict
                | PartitionStatus::Unmatched
                | PartitionStatus::Ambiguous
        );
        if progress && row.source == SOURCE_STATSAPI {
            mlb_dates.push(row.date.clone());
        }
        if progress && row.source == SOURCE_KALSHI_DISCOVERY {
            kalshi_dates.push(row.date.clone());
        }
    }
    mlb_dates.sort();
    mlb_dates.dedup();
    kalshi_dates.sort();
    kalshi_dates.dedup();
    WatermarkState {
        mlb_schedule_discovery: contiguous_watermark(rows, SOURCE_STATSAPI),
        mlb_pbp_acquisition: contiguous_watermark(rows, SOURCE_STATSAPI),
        kalshi_market_discovery: contiguous_watermark(rows, SOURCE_KALSHI_DISCOVERY)
            .or_else(|| contiguous_watermark(rows, SOURCE_KALSHI)),
        kalshi_market_artifact: contiguous_watermark(rows, SOURCE_KALSHI_DISCOVERY)
            .or_else(|| contiguous_watermark(rows, SOURCE_KALSHI)),
        mlb_pbp_committed_dates: mlb_dates,
        kalshi_discovery_committed_dates: kalshi_dates,
    }
}

pub fn as_report_vec(state: &WatermarkState) -> Vec<Watermark> {
    vec![
        Watermark {
            source: "mlb_schedule_discovery".into(),
            last_committed_date: state.mlb_schedule_discovery.clone(),
        },
        Watermark {
            source: "mlb_pbp_acquisition".into(),
            last_committed_date: state.mlb_pbp_acquisition.clone(),
        },
        Watermark {
            source: "kalshi_market_discovery".into(),
            last_committed_date: state.kalshi_market_discovery.clone(),
        },
        Watermark {
            source: "kalshi_market_artifact".into(),
            last_committed_date: state.kalshi_market_artifact.clone(),
        },
    ]
}

#[cfg(test)]
mod tests {
    use super::*;

    fn row(date: &str, status: PartitionStatus) -> CoverageRow {
        CoverageRow {
            date: date.into(),
            source: SOURCE_STATSAPI.into(),
            partition_id: date.into(),
            status,
            sha256: None,
            path: None,
            notes: String::new(),
        }
    }

    #[test]
    fn failure_stops_watermark() {
        let rows = vec![
            row("2026-06-18", PartitionStatus::Complete),
            row("2026-06-19", PartitionStatus::Failed),
            row("2026-06-20", PartitionStatus::Complete),
        ];
        assert_eq!(
            contiguous_watermark(&rows, SOURCE_STATSAPI).as_deref(),
            Some("2026-06-18")
        );
    }
}
