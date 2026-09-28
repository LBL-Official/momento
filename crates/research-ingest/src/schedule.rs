//! Sunday 00:00 America/Los_Angeles weekly ingest cadence.

use chrono::{DateTime, Datelike, Duration, NaiveDate, Utc, Weekday};
use chrono_tz::America::Los_Angeles;

pub const INGEST_HOUR_PACIFIC: u32 = 0;
pub const INGEST_WEEKDAY: Weekday = Weekday::Sun;

#[derive(Clone, Debug)]
pub struct IngestSchedule {
    pub timezone: &'static str,
    pub weekday: Weekday,
    pub hour_local: u32,
}

pub fn ingest_schedule() -> IngestSchedule {
    IngestSchedule {
        timezone: "America/Los_Angeles",
        weekday: INGEST_WEEKDAY,
        hour_local: INGEST_HOUR_PACIFIC,
    }
}

/// Next Sunday 00:00 Pacific (exclusive of `now` if already at/after that instant).
pub fn next_weekly_ingest(now: DateTime<Utc>) -> DateTime<Utc> {
    let local = now.with_timezone(&Los_Angeles);
    let days_until = (7 + INGEST_WEEKDAY.num_days_from_sunday() as i64
        - local.weekday().num_days_from_sunday() as i64)
        % 7;
    let mut date = local.date_naive() + Duration::days(days_until);
    let candidate = midnight_pacific(date);
    if candidate <= local {
        date += Duration::days(7);
        midnight_pacific(date).with_timezone(&Utc)
    } else {
        candidate.with_timezone(&Utc)
    }
}

fn midnight_pacific(date: NaiveDate) -> chrono::DateTime<chrono_tz::Tz> {
    date.and_hms_opt(INGEST_HOUR_PACIFIC, 0, 0)
        .expect("midnight")
        .and_local_timezone(Los_Angeles)
        .single()
        .expect("Sunday 00:00 Pacific is not a DST gap")
}

/// Incremental window: `lookback_days` through yesterday Pacific (inclusive).
pub fn weekly_window(now: DateTime<Utc>, lookback_days: i64) -> crate::types::DateWindow {
    let yesterday = now.with_timezone(&Los_Angeles).date_naive() - Duration::days(1);
    let span = lookback_days.max(1) - 1;
    crate::types::DateWindow {
        label: "weekly".into(),
        start: yesterday - Duration::days(span),
        end: yesterday,
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use chrono::{TimeZone, Timelike};

    #[test]
    fn next_run_is_sunday_midnight_pacific() {
        let sat = Los_Angeles
            .with_ymd_and_hms(2026, 8, 22, 23, 0, 0)
            .single()
            .unwrap()
            .with_timezone(&Utc);
        let next = next_weekly_ingest(sat);
        let local = next.with_timezone(&Los_Angeles);
        assert_eq!(local.weekday(), Weekday::Sun);
        assert_eq!(local.hour(), 0);
        assert_eq!(local.minute(), 0);
        assert_eq!(
            local.date_naive(),
            NaiveDate::from_ymd_opt(2026, 8, 23).unwrap()
        );
    }
}
