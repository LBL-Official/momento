//! Window-level coverage. Completeness is measured, never inferred.

use crate::types::{
    CoverageRow, DateWindow, PartitionStatus, SOURCE_STATSAPI, WindowCoverage, WindowStatus,
};

pub fn summarize_window(window: &DateWindow, source: &str, rows: &[CoverageRow]) -> WindowCoverage {
    let in_window: Vec<&CoverageRow> = rows
        .iter()
        .filter(|r| {
            r.source == source
                && chrono::NaiveDate::parse_from_str(&r.date, "%Y-%m-%d")
                    .ok()
                    .is_some_and(|d| window.contains(d))
        })
        .collect();
    let scheduled = in_window.len();
    let discovered = in_window
        .iter()
        .filter(|r| {
            r.status != PartitionStatus::Unavailable && r.status != PartitionStatus::NotAttempted
        })
        .count();
    let fetched = in_window
        .iter()
        .filter(|r| {
            matches!(
                r.status,
                PartitionStatus::Complete
                    | PartitionStatus::AlreadyKnown
                    | PartitionStatus::VersionConflict
                    | PartitionStatus::Failed
            )
        })
        .count();
    let committed = in_window
        .iter()
        .filter(|r| {
            matches!(
                r.status,
                PartitionStatus::Complete
                    | PartitionStatus::AlreadyKnown
                    | PartitionStatus::VersionConflict
            )
        })
        .count();
    let failed = in_window
        .iter()
        .filter(|r| r.status == PartitionStatus::Failed)
        .count();
    let unavailable = in_window
        .iter()
        .filter(|r| r.status == PartitionStatus::Unavailable)
        .count();
    let skipped = in_window
        .iter()
        .filter(|r| r.status == PartitionStatus::Skipped)
        .count();
    let duplicates = in_window
        .iter()
        .filter(|r| r.status == PartitionStatus::AlreadyKnown)
        .count();
    let checksum_conflicts = in_window
        .iter()
        .filter(|r| r.status == PartitionStatus::VersionConflict)
        .count();
    let status = window_status(scheduled, committed, failed, unavailable);
    WindowCoverage {
        label: window.label.clone(),
        start: window.start.to_string(),
        end: window.end.to_string(),
        source: source.into(),
        scheduled,
        discovered,
        fetched,
        committed,
        reconstructed_ready: committed,
        failed,
        unavailable,
        skipped,
        duplicates,
        checksum_conflicts,
        status,
        completeness_claimed: status == WindowStatus::Complete,
        notes: if status == WindowStatus::Unavailable {
            "NO_SOURCE_EVIDENCE — not fabricated COMPLETE".into()
        } else {
            "counts measured from artifacts".into()
        },
    }
}

fn window_status(
    scheduled: usize,
    committed: usize,
    failed: usize,
    unavailable: usize,
) -> WindowStatus {
    if scheduled == 0 {
        return WindowStatus::Unavailable;
    }
    if committed == 0 && failed > 0 {
        return WindowStatus::Failed;
    }
    if committed == 0 {
        return WindowStatus::Unavailable;
    }
    if failed > 0 || unavailable > 0 {
        return WindowStatus::CompleteWithGaps;
    }
    WindowStatus::Complete
}

pub fn summarize_plan_windows(windows: &[DateWindow], rows: &[CoverageRow]) -> Vec<WindowCoverage> {
    windows
        .iter()
        .map(|w| summarize_window(w, SOURCE_STATSAPI, rows))
        .collect()
}
