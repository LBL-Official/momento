//! Honest window coverage. Never infer COMPLETE from a requested date range.

use chrono::NaiveDate;
use serde::{Deserialize, Serialize};

use crate::versions::COVERAGE_VERSION;

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct WindowCoverage {
    pub label: String,
    pub start: String,
    pub end: String,
    pub discovered: usize,
    pub fetched: usize,
    pub committed: usize,
    pub reconstructed: usize,
    pub valid: usize,
    pub failed: usize,
    pub unavailable: usize,
    pub skipped: usize,
    pub duplicate: usize,
    pub completeness_claimed: bool,
    pub notes: String,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct W3CoverageReport {
    pub coverage_version: String,
    pub windows: Vec<WindowCoverage>,
    pub historical_pbp_events: usize,
    pub synthetic_events_excluded: usize,
    pub postponed: usize,
    pub cancelled: usize,
    pub suspended: usize,
    pub identity_mapped: usize,
    pub identity_unmatched: usize,
    pub identity_ambiguous: usize,
    pub theta_values_calculated: usize,
}

pub fn empty_window(label: &str, start: NaiveDate, end: NaiveDate, reason: &str) -> WindowCoverage {
    WindowCoverage {
        label: label.into(),
        start: start.to_string(),
        end: end.to_string(),
        discovered: 0,
        fetched: 0,
        committed: 0,
        reconstructed: 0,
        valid: 0,
        failed: 0,
        unavailable: 1,
        skipped: 0,
        duplicate: 0,
        completeness_claimed: false,
        notes: reason.into(),
    }
}

pub struct WindowCounts {
    pub discovered: usize,
    pub fetched: usize,
    pub committed: usize,
    pub reconstructed: usize,
    pub valid: usize,
    pub failed: usize,
    pub skipped: usize,
    pub duplicate: usize,
}

pub fn measured_window(
    label: &str,
    start: &str,
    end: &str,
    counts: WindowCounts,
) -> WindowCoverage {
    WindowCoverage {
        label: label.into(),
        start: start.into(),
        end: end.into(),
        discovered: counts.discovered,
        fetched: counts.fetched,
        committed: counts.committed,
        reconstructed: counts.reconstructed,
        valid: counts.valid,
        failed: counts.failed,
        unavailable: 0,
        skipped: counts.skipped,
        duplicate: counts.duplicate,
        completeness_claimed: false,
        notes: "counts are measured from committed source, not from the requested range".into(),
    }
}

pub fn base_report() -> W3CoverageReport {
    W3CoverageReport {
        coverage_version: COVERAGE_VERSION.into(),
        windows: Vec::new(),
        historical_pbp_events: 0,
        synthetic_events_excluded: 0,
        postponed: 0,
        cancelled: 0,
        suspended: 0,
        identity_mapped: 0,
        identity_unmatched: 0,
        identity_ambiguous: 0,
        theta_values_calculated: 0,
    }
}
