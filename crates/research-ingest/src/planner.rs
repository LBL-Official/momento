//! Historical and forward window partitioning. Not a completeness claim.

use chrono::{Duration, NaiveDate};

use crate::types::DateWindow;

pub const DEFAULT_CHUNK_DAYS: i64 = 7;

/// Split a window into contiguous chunks. Empty if start > end.
pub fn partition_window(window: &DateWindow, chunk_days: i64) -> Vec<DateWindow> {
    let span = chunk_days.max(1);
    let mut out = Vec::new();
    let mut start = window.start;
    let mut i = 0u32;
    while start <= window.end {
        let raw_end = start + Duration::days(span - 1);
        let end = if raw_end > window.end {
            window.end
        } else {
            raw_end
        };
        out.push(DateWindow {
            label: format!("{}#{}", window.label, i),
            start,
            end,
        });
        match end.succ_opt() {
            Some(next) => start = next,
            None => break,
        }
        i += 1;
    }
    out
}

pub fn required_mlb_partitions(as_of: NaiveDate, chunk_days: i64) -> Vec<DateWindow> {
    DateWindow::required_mlb_windows(as_of)
        .iter()
        .flat_map(|w| partition_window(w, chunk_days))
        .collect()
}

/// Re-query `[watermark - overlap, as_of]` so late/corrected source can land.
pub fn overlap_window(
    watermark: NaiveDate,
    overlap_days: i64,
    as_of: NaiveDate,
    label: &str,
) -> DateWindow {
    let back = overlap_days.max(0);
    let start = watermark - Duration::days(back);
    DateWindow {
        label: format!("{label}-overlap"),
        start,
        end: as_of.max(start),
    }
}

pub fn forward_window(as_of: NaiveDate, lookback_days: i64) -> DateWindow {
    let span = lookback_days.max(1) - 1;
    DateWindow {
        label: "forward".into(),
        start: as_of - Duration::days(span),
        end: as_of,
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn partitions_2024_calendar_year() {
        let parts = partition_window(&DateWindow::mlb_calendar_2024(), 7);
        assert_eq!(
            parts.first().unwrap().start,
            NaiveDate::from_ymd_opt(2024, 1, 1).unwrap()
        );
        assert_eq!(
            parts.last().unwrap().end,
            NaiveDate::from_ymd_opt(2024, 12, 31).unwrap()
        );
        assert!(parts.len() >= 52);
        assert!(
            parts
                .windows(2)
                .all(|w| w[0].end.succ_opt() == Some(w[1].start))
        );
    }

    #[test]
    fn partitions_2025_and_2026_through_as_of() {
        let as_of = NaiveDate::from_ymd_opt(2026, 8, 26).unwrap();
        let y2025 = partition_window(&DateWindow::mlb_calendar_2025(), 31);
        assert_eq!(
            y2025.last().unwrap().end,
            NaiveDate::from_ymd_opt(2025, 12, 31).unwrap()
        );
        let y2026 = partition_window(&DateWindow::mlb_calendar_2026_through(as_of), 31);
        assert_eq!(y2026.last().unwrap().end, as_of);
        assert!(y2026.first().unwrap().start <= NaiveDate::from_ymd_opt(2026, 1, 1).unwrap());
        let required = required_mlb_partitions(as_of, 30);
        assert!(required.iter().any(|w| w.label.starts_with("mlb-2024")));
        assert!(required.iter().any(|w| w.label.starts_with("mlb-2025")));
        assert!(required.iter().any(|w| w.label.starts_with("mlb-2026")));
    }

    #[test]
    fn overlap_reaches_back_from_watermark() {
        let wm = NaiveDate::from_ymd_opt(2026, 6, 30).unwrap();
        let as_of = NaiveDate::from_ymd_opt(2026, 7, 2).unwrap();
        let w = overlap_window(wm, 3, as_of, "pbp");
        assert_eq!(w.start, NaiveDate::from_ymd_opt(2026, 6, 27).unwrap());
        assert_eq!(w.end, as_of);
    }
}
