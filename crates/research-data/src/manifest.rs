//! Daily collection manifests.

use std::collections::BTreeMap;
use std::fs;
use std::path::Path;

use chrono::{DateTime, NaiveDate, Utc};
use serde::{Deserialize, Serialize};

use crate::paths::ResearchPaths;
use crate::schema::{COLLECTOR_VERSION, SCHEMA_VERSION};
use crate::sport::{ResearchSeason, ResearchSport};

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum CompletenessStatus {
    Complete,
    Partial,
    Missing,
    Invalid,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
pub struct DailyManifest {
    pub sport: String,
    pub season: String,
    pub date: NaiveDate,
    pub collection_started_at: DateTime<Utc>,
    pub collection_completed_at: Option<DateTime<Utc>>,
    pub markets_discovered: u32,
    pub markets_collected: u32,
    pub raw_event_count: u64,
    pub normalized_event_count: u64,
    pub trade_count: u64,
    pub orderbook_event_count: u64,
    pub sequence_gaps: u32,
    pub invalid_records: u32,
    pub missing_markets: Vec<String>,
    pub completeness_status: CompletenessStatus,
    pub collector_version: String,
    pub schema_version: String,
    pub checksums: BTreeMap<String, String>,
    pub notes: Vec<String>,
}

impl DailyManifest {
    pub fn new(sport: ResearchSport, season: &ResearchSeason, date: NaiveDate) -> Self {
        Self {
            sport: sport.dir_name().to_string(),
            season: season.label.clone(),
            date,
            collection_started_at: Utc::now(),
            collection_completed_at: None,
            markets_discovered: 0,
            markets_collected: 0,
            raw_event_count: 0,
            normalized_event_count: 0,
            trade_count: 0,
            orderbook_event_count: 0,
            sequence_gaps: 0,
            invalid_records: 0,
            missing_markets: Vec::new(),
            completeness_status: CompletenessStatus::Missing,
            collector_version: COLLECTOR_VERSION.to_string(),
            schema_version: SCHEMA_VERSION.to_string(),
            checksums: BTreeMap::new(),
            notes: Vec::new(),
        }
    }

    pub fn finalize_status(&mut self) {
        if self.invalid_records > 0 {
            self.completeness_status = CompletenessStatus::Invalid;
        } else if self.markets_discovered == 0 {
            self.completeness_status = CompletenessStatus::Missing;
        } else if !self.missing_markets.is_empty()
            || self.markets_collected < self.markets_discovered
        {
            self.completeness_status = CompletenessStatus::Partial;
        } else {
            self.completeness_status = CompletenessStatus::Complete;
        }
        self.collection_completed_at = Some(Utc::now());
    }

    pub fn write_atomic(&self, paths: &ResearchPaths, sport: ResearchSport) -> std::io::Result<()> {
        let dest = paths.manifest_path(sport, self.date);
        paths.ensure_parents(&dest)?;
        let tmp = dest.with_extension("json.tmp");
        let body = serde_json::to_string_pretty(self).map_err(std::io::Error::other)?;
        fs::write(&tmp, body)?;
        fs::rename(tmp, dest)?;
        Ok(())
    }

    pub fn read(
        paths: &ResearchPaths,
        sport: ResearchSport,
        date: NaiveDate,
    ) -> std::io::Result<Option<Self>> {
        let path = paths.manifest_path(sport, date);
        if !path.exists() {
            return Ok(None);
        }
        let body = fs::read_to_string(path)?;
        let manifest: Self = serde_json::from_str(&body).map_err(std::io::Error::other)?;
        Ok(Some(manifest))
    }
}

pub fn list_manifest_dates(
    paths: &ResearchPaths,
    sport: ResearchSport,
) -> std::io::Result<Vec<NaiveDate>> {
    let dir = paths.manifests_dir(sport);
    if !dir.exists() {
        return Ok(Vec::new());
    }
    let mut dates = Vec::new();
    for entry in fs::read_dir(dir)? {
        let entry = entry?;
        let name = entry.file_name().to_string_lossy().to_string();
        if let Some(rest) = name.strip_prefix("date=") {
            if let Some(date_str) = rest.strip_suffix(".json") {
                if let Ok(date) = NaiveDate::parse_from_str(date_str, "%Y-%m-%d") {
                    dates.push(date);
                }
            }
        }
    }
    dates.sort();
    Ok(dates)
}

pub fn remove_path_if_exists(path: &Path) -> std::io::Result<()> {
    if path.exists() {
        if path.is_dir() {
            fs::remove_dir_all(path)?;
        } else {
            fs::remove_file(path)?;
        }
    }
    Ok(())
}
