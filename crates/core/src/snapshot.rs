//! Weekly bankroll snapshot. Immutable after creation.
//!
//! Week boundary: Monday 04:00 America/Los_Angeles. DST-safe (not naive UTC).

use chrono::{DateTime, Datelike, Duration, NaiveDate, NaiveTime, TimeZone, Utc};
use chrono_tz::{America::Los_Angeles, Tz};
use serde::{Deserialize, Serialize};

use crate::error::{SnapshotError, TimeError};
use crate::ids::SnapshotId;
use crate::money::{Bps, Money};

const TIMEZONE_NAME: &str = "America/Los_Angeles";
/// Portfolio / weekly snapshot rolls at this local hour on Monday.
const WEEK_START_HOUR: u32 = 4;

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub struct TradingWeekId {
    /// Calendar date of the Monday that starts the week, in Pacific local time.
    pub year: i32,
    pub month: u32,
    pub day: u32,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub struct PacificCalendarDay {
    pub year: i32,
    pub month: u32,
    pub day: u32,
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub enum SnapshotSource {
    ConfiguredInitial,
    AccountBalance,
    Test,
}

/// Immutable weekly bankroll snapshot.
///
/// A later account balance change must not mutate an existing snapshot.
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct WeeklyBankrollSnapshot {
    snapshot_id: SnapshotId,
    bankroll: Money,
    max_position_budget: Money,
    allocation_bps: Bps,
    captured_at_utc: DateTime<Utc>,
    timezone: String,
    week: TradingWeekId,
    week_start_utc: DateTime<Utc>,
    source: SnapshotSource,
}

impl WeeklyBankrollSnapshot {
    pub fn capture(
        bankroll: Money,
        allocation_bps: Bps,
        now_utc: DateTime<Utc>,
        source: SnapshotSource,
    ) -> Result<Self, SnapshotError> {
        let week_start_pacific = pacific_week_start(now_utc)?;
        let week = TradingWeekId {
            year: week_start_pacific.year(),
            month: week_start_pacific.month(),
            day: week_start_pacific.day(),
        };
        let max_position_budget = bankroll.checked_mul_bps(allocation_bps)?;
        let snapshot_id = SnapshotId::generate();
        tracing::info!(
            snapshot_id = snapshot_id.raw(),
            bankroll_cents = bankroll.cents(),
            max_position_budget_cents = max_position_budget.cents(),
            timezone = TIMEZONE_NAME,
            "weekly_bankroll_snapshot_created"
        );
        Ok(Self {
            snapshot_id,
            bankroll,
            max_position_budget,
            allocation_bps,
            captured_at_utc: now_utc,
            timezone: TIMEZONE_NAME.to_string(),
            week,
            week_start_utc: week_start_pacific.with_timezone(&Utc),
            source,
        })
    }

    /// Capture with an explicit per-game budget (`FIXED_CENTS`).
    ///
    /// `allocation_bps` is stored for display / unit-%. Risk sizes from
    /// `max_position_budget`, not from recomputing `bankroll × bps`.
    pub fn capture_with_budget(
        bankroll: Money,
        allocation_bps: Bps,
        max_position_budget: Money,
        now_utc: DateTime<Utc>,
        source: SnapshotSource,
    ) -> Result<Self, SnapshotError> {
        if max_position_budget.cents() <= 0 {
            return Err(SnapshotError::InvalidBudget);
        }
        let week_start_pacific = pacific_week_start(now_utc)?;
        let week = TradingWeekId {
            year: week_start_pacific.year(),
            month: week_start_pacific.month(),
            day: week_start_pacific.day(),
        };
        let snapshot_id = SnapshotId::generate();
        tracing::info!(
            snapshot_id = snapshot_id.raw(),
            bankroll_cents = bankroll.cents(),
            max_position_budget_cents = max_position_budget.cents(),
            timezone = TIMEZONE_NAME,
            "weekly_bankroll_snapshot_created"
        );
        Ok(Self {
            snapshot_id,
            bankroll,
            max_position_budget,
            allocation_bps,
            captured_at_utc: now_utc,
            timezone: TIMEZONE_NAME.to_string(),
            week,
            week_start_utc: week_start_pacific.with_timezone(&Utc),
            source,
        })
    }

    pub const fn snapshot_id(&self) -> SnapshotId {
        self.snapshot_id
    }

    pub const fn bankroll(&self) -> Money {
        self.bankroll
    }

    pub const fn max_position_budget(&self) -> Money {
        self.max_position_budget
    }

    pub const fn allocation_bps(&self) -> Bps {
        self.allocation_bps
    }

    pub fn timezone(&self) -> &str {
        &self.timezone
    }

    pub const fn week(&self) -> TradingWeekId {
        self.week
    }

    pub const fn week_start_utc(&self) -> DateTime<Utc> {
        self.week_start_utc
    }

    pub const fn captured_at_utc(&self) -> DateTime<Utc> {
        self.captured_at_utc
    }

    pub const fn source(&self) -> &SnapshotSource {
        &self.source
    }
}

/// Monday 04:00 America/Los_Angeles of the trading week containing `at`.
///
/// Monday 00:00–03:59:59 Pacific still belongs to the prior week.
pub fn pacific_week_start(at: DateTime<Utc>) -> Result<DateTime<Tz>, TimeError> {
    let local = at.with_timezone(&Los_Angeles);
    let days_from_monday = i64::from(local.weekday().num_days_from_monday());
    let monday_date = local
        .date_naive()
        .checked_sub_signed(Duration::days(days_from_monday))
        .ok_or(TimeError::InvalidDate)?;
    let this_monday = pacific_monday_at_hour(monday_date, WEEK_START_HOUR)?;
    if local < this_monday {
        let prev_monday = monday_date
            .checked_sub_signed(Duration::days(7))
            .ok_or(TimeError::InvalidDate)?;
        pacific_monday_at_hour(prev_monday, WEEK_START_HOUR)
    } else {
        Ok(this_monday)
    }
}

fn pacific_monday_at_hour(date: NaiveDate, hour: u32) -> Result<DateTime<Tz>, TimeError> {
    let time = NaiveTime::from_hms_opt(hour, 0, 0).ok_or(TimeError::InvalidDate)?;
    let naive = date.and_time(time);
    match Los_Angeles.from_local_datetime(&naive) {
        chrono::LocalResult::Single(dt) => Ok(dt),
        chrono::LocalResult::Ambiguous(_, _) => Err(TimeError::AmbiguousLocalTime),
        chrono::LocalResult::None => Err(TimeError::InvalidLocalTime),
    }
}

pub fn belongs_to_week(at: DateTime<Utc>, week: TradingWeekId) -> Result<bool, TimeError> {
    let start = pacific_week_start(at)?;
    Ok(start.year() == week.year && start.month() == week.month && start.day() == week.day)
}

/// Pacific calendar date (midnight America/Los_Angeles). Session limits use this,
/// not the Monday 04:00 weekly roll.
pub fn pacific_calendar_day(at: DateTime<Utc>) -> PacificCalendarDay {
    let local = at.with_timezone(&Los_Angeles);
    PacificCalendarDay {
        year: local.year(),
        month: local.month(),
        day: local.day(),
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use chrono::{TimeZone, Timelike};

    fn utc(y: i32, m: u32, d: u32, h: u32, min: u32) -> DateTime<Utc> {
        Utc.with_ymd_and_hms(y, m, d, h, min, 0).single().unwrap()
    }

    #[test]
    fn snapshot_is_immutable_when_balance_changes() {
        let snap = WeeklyBankrollSnapshot::capture(
            Money::from_usd(50, 0).unwrap(),
            Bps::PCT_12_5,
            utc(2026, 8, 24, 16, 0),
            SnapshotSource::Test,
        )
        .unwrap();
        assert_eq!(snap.bankroll(), Money::from_usd(50, 0).unwrap());
        assert_eq!(snap.max_position_budget(), Money::from_usd(6, 25).unwrap());
        let later_balance = Money::from_usd(55, 0).unwrap();
        assert_ne!(later_balance, snap.bankroll());
        assert_eq!(snap.bankroll(), Money::from_usd(50, 0).unwrap());
        assert_eq!(snap.max_position_budget(), Money::from_usd(6, 25).unwrap());
    }

    #[test]
    fn monday_midnight_pacific_is_not_monday_midnight_utc() {
        // 2026-08-24 is a Monday. 00:00 PDT = 07:00 UTC.
        let monday_pacific_midnight = Los_Angeles
            .with_ymd_and_hms(2026, 8, 24, 0, 0, 0)
            .single()
            .unwrap();
        let as_utc = monday_pacific_midnight.with_timezone(&Utc);
        assert_eq!(as_utc, utc(2026, 8, 24, 7, 0));

        // Monday 00:00 UTC is still Sunday afternoon Pacific — previous week.
        let monday_utc_midnight = utc(2026, 8, 24, 0, 0);
        let week_of_utc_midnight = pacific_week_start(monday_utc_midnight).unwrap();
        assert_eq!(week_of_utc_midnight.date_naive().day(), 17);
        assert_eq!(week_of_utc_midnight.hour(), 4);

        // Monday 00:00 Pacific is before the 04:00 roll — still the prior week.
        let week_of_pacific_monday_midnight = pacific_week_start(as_utc).unwrap();
        assert_eq!(week_of_pacific_monday_midnight.date_naive().day(), 17);
        assert_eq!(week_of_pacific_monday_midnight.hour(), 4);
    }

    #[test]
    fn monday_before_4am_pacific_stays_prior_week() {
        let mon_359 = Los_Angeles
            .with_ymd_and_hms(2026, 8, 24, 3, 59, 59)
            .single()
            .unwrap()
            .with_timezone(&Utc);
        let start = pacific_week_start(mon_359).unwrap();
        assert_eq!(start.day(), 17);
        assert_eq!(start.hour(), 4);
    }

    #[test]
    fn monday_4am_pacific_starts_new_week() {
        let mon_4 = Los_Angeles
            .with_ymd_and_hms(2026, 8, 24, 4, 0, 0)
            .single()
            .unwrap();
        assert_eq!(mon_4.with_timezone(&Utc), utc(2026, 8, 24, 11, 0));
        let start = pacific_week_start(mon_4.with_timezone(&Utc)).unwrap();
        assert_eq!(start.year(), 2026);
        assert_eq!(start.month(), 8);
        assert_eq!(start.day(), 24);
        assert_eq!(start.hour(), 4);
    }

    #[test]
    fn sunday_evening_pacific_belongs_to_week_starting_prior_monday() {
        // Sunday 2026-08-23 23:30 PDT.
        let sunday_evening = Los_Angeles
            .with_ymd_and_hms(2026, 8, 23, 23, 30, 0)
            .single()
            .unwrap()
            .with_timezone(&Utc);
        let start = pacific_week_start(sunday_evening).unwrap();
        assert_eq!(start.year(), 2026);
        assert_eq!(start.month(), 8);
        assert_eq!(start.day(), 17);
        assert_eq!(start.hour(), 4);
    }

    #[test]
    fn pdt_and_pst_monday_boundaries_use_local_4am() {
        // 2026-03-09 is a Monday during PDT (DST started 2026-03-08).
        let march_monday = Los_Angeles
            .with_ymd_and_hms(2026, 3, 9, 4, 0, 0)
            .single()
            .unwrap();
        assert_eq!(
            march_monday.with_timezone(&Utc).format("%H").to_string(),
            "11"
        );

        // 2026-01-05 is a Monday during PST. 04:00 PST = 12:00 UTC.
        let jan_monday = Los_Angeles
            .with_ymd_and_hms(2026, 1, 5, 4, 0, 0)
            .single()
            .unwrap();
        assert_eq!(
            jan_monday.with_timezone(&Utc).format("%H").to_string(),
            "12"
        );

        let march_week = pacific_week_start(march_monday.with_timezone(&Utc)).unwrap();
        let jan_week = pacific_week_start(jan_monday.with_timezone(&Utc)).unwrap();
        assert_eq!(march_week.day(), 9);
        assert_eq!(march_week.hour(), 4);
        assert_eq!(jan_week.day(), 5);
        assert_eq!(jan_week.hour(), 4);
    }

    #[test]
    fn capture_with_budget_is_not_bankroll_times_bps() {
        let snap = WeeklyBankrollSnapshot::capture_with_budget(
            Money::from_usd(39, 31).unwrap(),
            Bps::PCT_12_5,
            Money::from_cents(331),
            utc(2026, 8, 24, 16, 0),
            SnapshotSource::Test,
        )
        .unwrap();
        assert_eq!(snap.bankroll().cents(), 3931);
        assert_eq!(snap.max_position_budget().cents(), 331);
        assert_ne!(
            snap.max_position_budget(),
            snap.bankroll().checked_mul_bps(Bps::PCT_12_5).unwrap()
        );
    }

    #[test]
    fn pacific_calendar_day_uses_la_midnight() {
        // 2026-08-24 06:59 UTC is still 2026-08-23 23:59 PDT.
        let before = utc(2026, 8, 24, 6, 59);
        let after = utc(2026, 8, 24, 7, 0);
        let prior = pacific_calendar_day(before);
        let next = pacific_calendar_day(after);
        assert_eq!(
            prior,
            PacificCalendarDay {
                year: 2026,
                month: 8,
                day: 23
            }
        );
        assert_eq!(
            next,
            PacificCalendarDay {
                year: 2026,
                month: 8,
                day: 24
            }
        );
    }
}
