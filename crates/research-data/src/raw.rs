//! Immutable gzip JSONL raw archive.

use std::fs::File;
use std::io::{BufRead, BufReader, Write};
use std::path::{Path, PathBuf};

use chrono::Utc;
use flate2::Compression;
use flate2::read::GzDecoder;
use flate2::write::GzEncoder;
use serde::{Deserialize, Serialize};

use crate::paths::ResearchPaths;
use crate::schema::RawMarketEvent;
use crate::sport::ResearchSport;

use chrono::NaiveDate;

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct RawArchiveSummary {
    pub path: PathBuf,
    pub event_count: u64,
}

pub struct RawArchiveWriter {
    encoder: GzEncoder<File>,
    path: PathBuf,
    count: u64,
}

impl RawArchiveWriter {
    pub fn create(path: &Path) -> std::io::Result<Self> {
        if let Some(parent) = path.parent() {
            std::fs::create_dir_all(parent)?;
        }
        let file = File::create(path)?;
        Ok(Self {
            encoder: GzEncoder::new(file, Compression::default()),
            path: path.to_path_buf(),
            count: 0,
        })
    }

    pub fn append(&mut self, event: &RawMarketEvent) -> std::io::Result<()> {
        let line = serde_json::to_string(event).map_err(std::io::Error::other)?;
        writeln!(self.encoder, "{line}")?;
        self.count += 1;
        Ok(())
    }

    pub fn append_payload(
        &mut self,
        source: &str,
        endpoint: &str,
        ticker: Option<&str>,
        payload: serde_json::Value,
    ) -> std::io::Result<()> {
        self.append(&RawMarketEvent {
            received_at: Utc::now(),
            source: source.to_string(),
            endpoint: endpoint.to_string(),
            ticker: ticker.map(str::to_string),
            payload,
        })
    }

    pub fn finish(self) -> std::io::Result<RawArchiveSummary> {
        self.encoder.finish()?;
        Ok(RawArchiveSummary {
            path: self.path,
            event_count: self.count,
        })
    }

    pub fn event_count(&self) -> u64 {
        self.count
    }
}

pub fn read_raw_events(path: &Path) -> std::io::Result<Vec<RawMarketEvent>> {
    let file = File::open(path)?;
    let reader = BufReader::new(GzDecoder::new(file));
    let mut out = Vec::new();
    for line in reader.lines() {
        let line = line?;
        if line.trim().is_empty() {
            continue;
        }
        let event: RawMarketEvent = serde_json::from_str(&line).map_err(std::io::Error::other)?;
        out.push(event);
    }
    Ok(out)
}

pub fn raw_file_name(kind: &str) -> String {
    format!("{kind}.jsonl.gz")
}

pub fn staging_raw_path(
    paths: &ResearchPaths,
    sport: ResearchSport,
    date: NaiveDate,
    kind: &str,
) -> PathBuf {
    paths.raw_staging_day(sport, date).join(raw_file_name(kind))
}

pub fn published_raw_path(
    paths: &ResearchPaths,
    sport: ResearchSport,
    date: NaiveDate,
    kind: &str,
) -> PathBuf {
    paths.raw_day(sport, date).join(raw_file_name(kind))
}
