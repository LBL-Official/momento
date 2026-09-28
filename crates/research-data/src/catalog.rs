//! Local research catalog for Notion handoff.

use std::fs;

use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};

use crate::manifest::{CompletenessStatus, DailyManifest, list_manifest_dates};
use crate::paths::ResearchPaths;
use crate::schema::SCHEMA_VERSION;
use crate::sport::{ResearchSeason, ResearchSport};

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
pub struct SportCatalogEntry {
    pub sport: String,
    pub season: String,
    pub dates_collected: u32,
    pub complete_dates: u32,
    pub partial_dates: u32,
    pub missing_dates: u32,
    pub total_markets: u32,
    pub total_events: u64,
    pub latest_collection_time: Option<DateTime<Utc>>,
    pub manifest_dir: String,
    pub validation_status: String,
    pub schema_version: String,
    pub notion_handoff: String,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
pub struct ResearchCatalog {
    pub updated_at: DateTime<Utc>,
    pub entries: Vec<SportCatalogEntry>,
}

impl ResearchCatalog {
    pub fn rebuild(paths: &ResearchPaths, season: &ResearchSeason) -> std::io::Result<Self> {
        let mut entries = Vec::new();
        for sport in [ResearchSport::Mlb, ResearchSport::Wnba] {
            entries.push(build_sport_entry(paths, sport, season)?);
        }
        Ok(Self {
            updated_at: Utc::now(),
            entries,
        })
    }

    pub fn write(&self, paths: &ResearchPaths) -> std::io::Result<()> {
        let path = paths.catalog_path();
        paths.ensure_parents(&path)?;
        let tmp = path.with_extension("json.tmp");
        fs::write(
            &tmp,
            serde_json::to_string_pretty(self).map_err(std::io::Error::other)?,
        )?;
        fs::rename(tmp, path)?;
        Ok(())
    }

    pub fn read(paths: &ResearchPaths) -> std::io::Result<Option<Self>> {
        let path = paths.catalog_path();
        if !path.exists() {
            return Ok(None);
        }
        let body = fs::read_to_string(path)?;
        Ok(Some(
            serde_json::from_str(&body).map_err(std::io::Error::other)?,
        ))
    }
}

fn build_sport_entry(
    paths: &ResearchPaths,
    sport: ResearchSport,
    season: &ResearchSeason,
) -> std::io::Result<SportCatalogEntry> {
    let dates = list_manifest_dates(paths, sport)?;
    let mut complete = 0;
    let mut partial = 0;
    let mut missing = 0;
    let mut total_markets = 0;
    let mut total_events = 0u64;
    let mut latest: Option<DateTime<Utc>> = None;
    let mut validation = "unknown".to_string();

    for date in &dates {
        if let Some(m) = DailyManifest::read(paths, sport, *date)? {
            total_markets += m.markets_collected;
            total_events += m.normalized_event_count;
            if let Some(done) = m.collection_completed_at {
                latest = Some(latest.map_or(done, |l| l.max(done)));
            }
            match m.completeness_status {
                CompletenessStatus::Complete => complete += 1,
                CompletenessStatus::Partial => partial += 1,
                CompletenessStatus::Missing | CompletenessStatus::Invalid => missing += 1,
            }
            if m.invalid_records == 0 {
                validation = "passing".into();
            } else {
                validation = "failing".into();
            }
        }
    }

    Ok(SportCatalogEntry {
        sport: sport.dir_name().to_string(),
        season: season.label.clone(),
        dates_collected: dates.len() as u32,
        complete_dates: complete,
        partial_dates: partial,
        missing_dates: missing,
        total_markets,
        total_events,
        latest_collection_time: latest,
        manifest_dir: paths.manifests_dir(sport).display().to_string(),
        validation_status: validation,
        schema_version: SCHEMA_VERSION.to_string(),
        notion_handoff:
            "Use this catalog.json as the Notion index source; high-volume Parquet remains on disk."
                .into(),
    })
}
