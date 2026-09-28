//! Read committed Kalshi discovery envelopes and identity pairs. No network.

use std::collections::BTreeMap;
use std::fs;
use std::path::{Path, PathBuf};

use chrono::NaiveDate;
use momento_research_ingest::types::{
    CommittedArtifact, GameMarketPair, IdentityMapping, W1CommitHandoff,
};
use serde::Deserialize;
use serde_json::Value;

use crate::error::W4Error;
use crate::gate::{artifact_is_committed_discovery, assert_handoff_committed, verify_checksum};
use crate::versions::SERIES_MLB;

#[derive(Clone, Debug)]
pub struct IdentityIndex {
    pub by_ticker: BTreeMap<String, GameMarketPair>,
    pub path: Option<PathBuf>,
}

impl IdentityIndex {
    pub fn empty() -> Self {
        Self {
            by_ticker: BTreeMap::new(),
            path: None,
        }
    }

    pub fn lookup(&self, ticker: &str) -> Option<&GameMarketPair> {
        self.by_ticker.get(ticker)
    }
}

pub fn load_identity_pairs(path: &Path) -> Result<IdentityIndex, W4Error> {
    let body = fs::read_to_string(path)?;
    let pairs: Vec<GameMarketPair> = serde_json::from_str(&body)?;
    let mut by_ticker = BTreeMap::new();
    for p in pairs {
        if !p.ticker.is_empty() {
            by_ticker.insert(p.ticker.clone(), p);
        }
    }
    Ok(IdentityIndex {
        by_ticker,
        path: Some(path.to_path_buf()),
    })
}

pub fn load_handoff(path: &Path) -> Result<W1CommitHandoff, W4Error> {
    let body = fs::read_to_string(path)?;
    Ok(serde_json::from_str(&body)?)
}

pub fn latest_run_paths(ingest_root: &Path) -> Result<(PathBuf, PathBuf), W4Error> {
    let runs = ingest_root.join("runs");
    if !runs.is_dir() {
        return Err(W4Error::Uncommitted(format!(
            "no ingest runs at {}",
            runs.display()
        )));
    }
    let mut dirs: Vec<PathBuf> = fs::read_dir(&runs)?
        .filter_map(|e| e.ok())
        .map(|e| e.path())
        .filter(|p| p.is_dir())
        .collect();
    dirs.sort();
    let last = dirs
        .last()
        .ok_or_else(|| W4Error::Uncommitted(format!("empty ingest runs at {}", runs.display())))?;
    let handoff = last.join("w1_handoff.json");
    let pairs = last.join("game_market_pairs.json");
    if !handoff.exists() {
        return Err(W4Error::Uncommitted(format!(
            "missing {}",
            handoff.display()
        )));
    }
    Ok((handoff, pairs))
}

#[derive(Clone, Debug)]
pub struct CommittedEnvelope {
    pub artifact: CommittedArtifact,
    pub path: PathBuf,
}

pub fn committed_envelopes_for_date(
    handoff: &W1CommitHandoff,
    date: NaiveDate,
) -> Result<Vec<CommittedEnvelope>, W4Error> {
    assert_handoff_committed(handoff)?;
    let date_s = date.to_string();
    let mut out = Vec::new();
    for a in &handoff.artifacts {
        if !artifact_is_committed_discovery(&a.source, a.commit_status) {
            continue;
        }
        if a.date != date_s {
            continue;
        }
        if !a.partition_id.starts_with(SERIES_MLB) && !a.artifact_id.contains(SERIES_MLB) {
            continue;
        }
        let path = PathBuf::from(&a.path);
        verify_checksum(&path, &a.sha256)?;
        out.push(CommittedEnvelope {
            artifact: a.clone(),
            path,
        });
    }
    Ok(out)
}

#[derive(Clone, Debug, Deserialize)]
pub struct DiscoveryEnvelope {
    #[serde(default)]
    pub ticker: String,
    #[serde(default)]
    pub event_ticker: Option<String>,
    #[serde(default)]
    pub identity_mapping: Option<IdentityMapping>,
    #[serde(default)]
    pub observed_game_pk: Option<String>,
    #[serde(default)]
    pub series: Option<String>,
    #[serde(default)]
    pub retrieved_at: Option<String>,
    #[serde(default)]
    pub payload: Value,
}

pub fn parse_envelope_bytes(bytes: &[u8]) -> Result<DiscoveryEnvelope, W4Error> {
    Ok(serde_json::from_slice(bytes)?)
}

pub fn read_envelope(path: &Path) -> Result<DiscoveryEnvelope, W4Error> {
    let bytes = fs::read(path)?;
    parse_envelope_bytes(&bytes)
}

pub fn attach_identity(
    env: &DiscoveryEnvelope,
    index: &IdentityIndex,
) -> (IdentityMapping, Option<String>) {
    if let Some(p) = index.lookup(&env.ticker) {
        let pk = if p.mapping == IdentityMapping::Mapped {
            p.game_pk.clone()
        } else {
            None
        };
        return (p.mapping, pk);
    }
    let mapping = env.identity_mapping.unwrap_or(IdentityMapping::Unmatched);
    let pk = if mapping == IdentityMapping::Mapped {
        env.observed_game_pk.clone()
    } else {
        None
    };
    (mapping, pk)
}
