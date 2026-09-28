//! 03:00 America/Los_Angeles reconciliation schedule.

use chrono::{DateTime, Duration, NaiveDate, Utc};
use chrono_tz::America::Los_Angeles;

use crate::manifest::{CompletenessStatus, DailyManifest, list_manifest_dates};
use crate::paths::ResearchPaths;
use crate::sport::{ResearchSeason, ResearchSport};

pub const COLLECTION_HOUR_PST: u32 = 3;

#[derive(Clone, Debug)]
pub struct CollectionSchedule {
    pub timezone: &'static str,
    pub hour_local: u32,
}

pub fn collection_schedule() -> CollectionSchedule {
    CollectionSchedule {
        timezone: "America/Los_Angeles",
        hour_local: COLLECTION_HOUR_PST,
    }
}

pub fn next_collection_run(now: DateTime<Utc>) -> DateTime<Utc> {
    let local = now.with_timezone(&Los_Angeles);
    let today_run = local
        .date_naive()
        .and_hms_opt(COLLECTION_HOUR_PST, 0, 0)
        .expect("3am")
        .and_local_timezone(Los_Angeles)
        .single()
        .expect("3am local");
    if local < today_run {
        today_run.with_timezone(&Utc)
    } else {
        (today_run + Duration::days(1)).with_timezone(&Utc)
    }
}

pub fn season_start_date(season: &ResearchSeason) -> NaiveDate {
    if season.label == "2025-2026" {
        NaiveDate::from_ymd_opt(2025, 3, 1).expect("season start")
    } else {
        Utc::now().date_naive() - Duration::days(30)
    }
}

pub fn dates_through_yesterday(now: DateTime<Utc>, season: &ResearchSeason) -> Vec<NaiveDate> {
    let end = now.with_timezone(&Los_Angeles).date_naive() - Duration::days(1);
    let mut date = season_start_date(season);
    let mut out = Vec::new();
    while date <= end {
        out.push(date);
        date += Duration::days(1);
    }
    out
}

pub fn backfill_dates(
    paths: &ResearchPaths,
    sport: ResearchSport,
    season: &ResearchSeason,
    now: DateTime<Utc>,
) -> std::io::Result<Vec<NaiveDate>> {
    let expected = dates_through_yesterday(now, season);
    let existing = list_manifest_dates(paths, sport)?;
    let mut missing = Vec::new();
    for date in &expected {
        match DailyManifest::read(paths, sport, *date)? {
            None => missing.push(*date),
            Some(m) if m.completeness_status != CompletenessStatus::Complete => missing.push(*date),
            Some(_) => {}
        }
    }
    // Also include dates with no manifest but stale partial staging cleaned by reconcile.
    for date in &expected {
        if !existing.contains(date) && !missing.contains(date) {
            // already complete handled above
        }
    }
    Ok(missing)
}
