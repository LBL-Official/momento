//! Official B1 chronological cuts.
//!
//! Do not re-cut a universe to improve an answer. Completed experiments freeze
//! the cuts they were created with.

use crate::search::{ChronoSplit, SearchRow};

/// TRAIN: official date strictly before this instant (date string compare).
pub const TRAIN_BEFORE: &str = "2025-10-07";
/// VAL: official date strictly before this instant (and not TRAIN).
pub const VAL_BEFORE: &str = "2026-05-03";
/// Observed TEST end on the locked first-exact-83 extract.
pub const TEST_END_OBSERVED: &str = "2026-06-27";

/// Apply the locked official cuts. TEST end is the max date in `rows`.
pub fn apply_official_chrono_split(rows: &mut [SearchRow]) -> (String, String, String) {
    apply_configured_chrono_split(rows, TRAIN_BEFORE, VAL_BEFORE)
}

/// Apply caller-supplied cuts. Same comparison as the official helper.
pub fn apply_configured_chrono_split(
    rows: &mut [SearchRow],
    train_before: &str,
    val_before: &str,
) -> (String, String, String) {
    let test_end = rows
        .iter()
        .map(|r| r.date.as_str())
        .max()
        .unwrap_or("")
        .to_string();
    for r in rows.iter_mut() {
        r.chrono = if r.date.as_str() < train_before {
            ChronoSplit::Train
        } else if r.date.as_str() < val_before {
            ChronoSplit::Validation
        } else {
            ChronoSplit::Test
        };
    }
    (train_before.to_string(), val_before.to_string(), test_end)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn official_cuts_are_locked() {
        assert_eq!(TRAIN_BEFORE, "2025-10-07");
        assert_eq!(VAL_BEFORE, "2026-05-03");
        assert_eq!(TEST_END_OBSERVED, "2026-06-27");
    }

    #[test]
    fn official_split_assigns_boundaries() {
        let mk = |date: &str| SearchRow {
            game_id: date.into(),
            date: date.into(),
            month: date.chars().take(7).collect(),
            entry_cents: 83,
            qty: 7,
            chrono: ChronoSplit::Train,
            settlement_win: None,
            mfe: None,
            mae: None,
            exit_ret: Default::default(),
            feats: Default::default(),
        };
        let mut rows = vec![
            mk("2025-10-06"),
            mk("2025-10-07"),
            mk("2026-05-02"),
            mk("2026-05-03"),
            mk("2026-06-27"),
        ];
        let (t, v, e) = apply_official_chrono_split(&mut rows);
        assert_eq!(t, TRAIN_BEFORE);
        assert_eq!(v, VAL_BEFORE);
        assert_eq!(e, "2026-06-27");
        assert_eq!(rows[0].chrono, ChronoSplit::Train);
        assert_eq!(rows[1].chrono, ChronoSplit::Validation);
        assert_eq!(rows[2].chrono, ChronoSplit::Validation);
        assert_eq!(rows[3].chrono, ChronoSplit::Test);
        assert_eq!(rows[4].chrono, ChronoSplit::Test);
    }
}
