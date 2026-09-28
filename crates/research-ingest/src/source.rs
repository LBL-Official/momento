//! Partition discovery and fetch. Fixtures for tests; live StatsAPI is opt-in.

use std::collections::BTreeMap;
use std::process::Command;
use std::thread;
use std::time::Duration;

use chrono::NaiveDate;
use serde_json::Value;

use crate::error::IngestError;
use crate::types::{DateWindow, SOURCE_STATSAPI};

pub const STATSAPI_BASE: &str = "https://statsapi.mlb.com";
pub const INGEST_USER_AGENT: &str = "MomentoResearch-INGEST/2.1 (historical PBP; not live trading)";

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct DiscoveredPartition {
    pub source: String,
    pub date: NaiveDate,
    pub partition_id: String,
    pub status_hint: String,
    pub home_abbreviation: String,
    pub away_abbreviation: String,
    /// StatsAPI `gameNumber`. 1 for a single game; 2 for the nightcap.
    pub game_number: u8,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub enum FetchOutcome {
    Bytes(Vec<u8>),
    Missing,
    Failure(String),
}

pub trait PartitionSource {
    fn list_partitions(&self, window: &DateWindow)
    -> Result<Vec<DiscoveredPartition>, IngestError>;
    fn fetch(&self, partition: &DiscoveredPartition) -> Result<FetchOutcome, IngestError>;
}

#[derive(Clone, Debug, Default)]
pub struct FixtureSource {
    pub partitions: Vec<DiscoveredPartition>,
    pub fetches: BTreeMap<String, FetchOutcome>,
}

impl PartitionSource for FixtureSource {
    fn list_partitions(
        &self,
        window: &DateWindow,
    ) -> Result<Vec<DiscoveredPartition>, IngestError> {
        Ok(self
            .partitions
            .iter()
            .filter(|p| window.contains(p.date))
            .cloned()
            .collect())
    }

    fn fetch(&self, partition: &DiscoveredPartition) -> Result<FetchOutcome, IngestError> {
        self.fetches
            .get(&partition.partition_id)
            .cloned()
            .ok_or_else(|| {
                IngestError::SourceFailure(format!("no fixture {}", partition.partition_id))
            })
    }
}

/// Used when network PBP is not enabled. Lists nothing; never fabricates games.
#[derive(Clone, Debug, Default)]
pub struct EmptyPbpSource;

impl PartitionSource for EmptyPbpSource {
    fn list_partitions(
        &self,
        _window: &DateWindow,
    ) -> Result<Vec<DiscoveredPartition>, IngestError> {
        Ok(Vec::new())
    }

    fn fetch(&self, partition: &DiscoveredPartition) -> Result<FetchOutcome, IngestError> {
        Err(IngestError::SourceFailure(format!(
            "network PBP disabled; refusing fetch of {}",
            partition.partition_id
        )))
    }
}

/// Live StatsAPI. Only used when `IngestPlan.network_enabled` is true.
#[derive(Clone, Debug)]
pub struct LiveStatsApiSource;

fn curl_get(url: &str) -> Result<Vec<u8>, IngestError> {
    let out = Command::new("curl")
        .args([
            "-sS",
            "-L",
            "--fail",
            "--max-time",
            "90",
            "-A",
            INGEST_USER_AGENT,
            url,
        ])
        .output()
        .map_err(|e| IngestError::SourceFailure(format!("curl: {e}")))?;
    if !out.status.success() {
        return Err(IngestError::SourceFailure(format!(
            "curl {url} exit {:?}",
            out.status.code()
        )));
    }
    Ok(out.stdout)
}

impl PartitionSource for LiveStatsApiSource {
    fn list_partitions(
        &self,
        window: &DateWindow,
    ) -> Result<Vec<DiscoveredPartition>, IngestError> {
        let start = window.start.format("%Y-%m-%d");
        let end = window.end.format("%Y-%m-%d");
        let url = format!(
            "{STATSAPI_BASE}/api/v1/schedule?sportId=1&startDate={start}&endDate={end}&hydrate=team"
        );
        let bytes = curl_get(&url)?;
        let sched: Value = serde_json::from_slice(&bytes)?;
        let mut out = Vec::new();
        for date_block in sched
            .get("dates")
            .and_then(|v| v.as_array())
            .cloned()
            .unwrap_or_default()
        {
            let date_s = date_block
                .get("date")
                .and_then(|v| v.as_str())
                .unwrap_or_default();
            let Ok(date) = NaiveDate::parse_from_str(date_s, "%Y-%m-%d") else {
                continue;
            };
            for g in date_block
                .get("games")
                .and_then(|v| v.as_array())
                .cloned()
                .unwrap_or_default()
            {
                let Some(pk) = g.get("gamePk").and_then(|v| v.as_i64()) else {
                    continue;
                };
                let status = g
                    .pointer("/status/detailedState")
                    .and_then(|v| v.as_str())
                    .unwrap_or("Unknown");
                let home = g
                    .pointer("/teams/home/team/abbreviation")
                    .and_then(|v| v.as_str())
                    .unwrap_or("")
                    .to_string();
                let away = g
                    .pointer("/teams/away/team/abbreviation")
                    .and_then(|v| v.as_str())
                    .unwrap_or("")
                    .to_string();
                out.push(DiscoveredPartition {
                    source: SOURCE_STATSAPI.into(),
                    date,
                    partition_id: pk.to_string(),
                    status_hint: status.into(),
                    home_abbreviation: home,
                    away_abbreviation: away,
                    game_number: observed_game_number(&g),
                });
            }
        }
        Ok(out)
    }

    fn fetch(&self, partition: &DiscoveredPartition) -> Result<FetchOutcome, IngestError> {
        if partition.status_hint != "Final" {
            return Ok(FetchOutcome::Missing);
        }
        let url = format!(
            "{STATSAPI_BASE}/api/v1.1/game/{}/feed/live",
            partition.partition_id
        );
        match curl_get(&url) {
            Ok(feed) => Ok(FetchOutcome::Bytes(feed)),
            Err(e) => Ok(FetchOutcome::Failure(e.to_string())),
        }
    }
}

fn observed_game_number(game: &Value) -> u8 {
    game.get("gameNumber")
        .and_then(|v| {
            v.as_u64()
                .map(|n| n as u8)
                .or_else(|| v.as_str().and_then(|s| s.parse().ok()))
        })
        .filter(|n| *n >= 1)
        .unwrap_or(1)
}

pub fn fetch_with_retries(
    source: &dyn PartitionSource,
    partition: &DiscoveredPartition,
    max_retries: u32,
    sleep_ms: u64,
) -> Result<FetchOutcome, IngestError> {
    let attempts = 1 + max_retries;
    for i in 0..attempts {
        match source.fetch(partition)? {
            ok @ (FetchOutcome::Bytes(_) | FetchOutcome::Missing) => return Ok(ok),
            FetchOutcome::Failure(_) if i + 1 < attempts => {
                if sleep_ms > 0 {
                    thread::sleep(Duration::from_millis(sleep_ms));
                }
            }
            FetchOutcome::Failure(msg) => {
                return Err(IngestError::RetryExhausted(format!(
                    "{}: {msg}",
                    partition.partition_id
                )));
            }
        }
    }
    Err(IngestError::RetryExhausted(partition.partition_id.clone()))
}
