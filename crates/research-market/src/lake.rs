//! Read-only Data-Real COMPLETE raw JSONL. Never treats PIT books as t_game L2.

use std::collections::BTreeMap;
use std::path::Path;

use chrono::NaiveDate;
use momento_research_data::checksum::sha256_file;
use momento_research_data::manifest::{CompletenessStatus, DailyManifest};
use momento_research_data::paths::ResearchPaths;
use momento_research_data::raw::read_raw_events;
use momento_research_data::schema::RawMarketEvent;
use momento_research_data::sport::{ResearchSeason, ResearchSport};

use crate::error::W4Error;
use crate::gate::verify_checksum;
use crate::types::ReconstructionAnomaly;

#[derive(Clone, Debug, Default)]
pub struct LakeDayIndex {
    pub by_ticker: BTreeMap<String, Vec<RawMarketEvent>>,
    pub verified: bool,
    pub notes: Vec<String>,
}

pub fn load_complete_raw_day(lake_root: &Path, date: NaiveDate) -> Result<LakeDayIndex, W4Error> {
    let paths = ResearchPaths {
        root: lake_root.to_path_buf(),
        season: ResearchSeason::current(),
    };
    let Some(manifest) = DailyManifest::read(&paths, ResearchSport::Mlb, date)? else {
        return Ok(LakeDayIndex {
            notes: vec![format!("no Data-Real MLB manifest for {date}")],
            ..LakeDayIndex::default()
        });
    };
    if manifest.completeness_status != CompletenessStatus::Complete {
        return Ok(LakeDayIndex {
            notes: vec![format!(
                "Data-Real {date} is {:?}, not COMPLETE — lake raw not merged",
                manifest.completeness_status
            )],
            ..LakeDayIndex::default()
        });
    }
    let raw_path = paths
        .raw_day(ResearchSport::Mlb, date)
        .join("events.jsonl.gz");
    if !raw_path.exists() {
        return Ok(LakeDayIndex {
            notes: vec![format!("missing {}", raw_path.display())],
            ..LakeDayIndex::default()
        });
    }
    let expected = manifest
        .checksums
        .get("events.jsonl.gz")
        .cloned()
        .ok_or_else(|| {
            W4Error::Uncommitted(format!(
                "COMPLETE manifest {} missing events.jsonl.gz checksum",
                date
            ))
        })?;
    verify_checksum(&raw_path, &expected)?;
    let _on_disk = sha256_file(&raw_path).map_err(|e| W4Error::Io(e.to_string()))?;
    let events = read_raw_events(&raw_path).map_err(|e| W4Error::Io(e.to_string()))?;
    let mut by_ticker: BTreeMap<String, Vec<RawMarketEvent>> = BTreeMap::new();
    for ev in events {
        let ticker = ev
            .ticker
            .clone()
            .or_else(|| {
                ev.payload
                    .get("ticker")
                    .and_then(|v| v.as_str())
                    .map(str::to_string)
            })
            .unwrap_or_default();
        if ticker.is_empty() {
            continue;
        }
        by_ticker.entry(ticker).or_default().push(ev);
    }
    Ok(LakeDayIndex {
        by_ticker,
        verified: true,
        notes: vec![format!("merged Data-Real COMPLETE raw for {date}")],
    })
}

pub fn lake_note_anomalies(index: &LakeDayIndex) -> Vec<ReconstructionAnomaly> {
    index
        .notes
        .iter()
        .map(|n| ReconstructionAnomaly {
            ticker: String::new(),
            code: "LAKE".into(),
            message: n.clone(),
        })
        .collect()
}
