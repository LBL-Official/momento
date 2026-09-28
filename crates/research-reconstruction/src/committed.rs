//! Turn DATA-INGEST handoffs or verified W2 collect manifests into committed refs.

use std::fs;
use std::path::{Path, PathBuf};

use serde::{Deserialize, Serialize};

use momento_research_event::collect::CollectReport;
use momento_research_ingest::{CommitStatus, CommittedArtifact, SOURCE_STATSAPI, W1CommitHandoff};

use crate::error::W3Error;
use crate::gate::verify_checksum;
use crate::lifecycle::{MlbGameLifecycle, classify_schedule_status};

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct SkippedGame {
    pub game_pk: String,
    pub official_date: String,
    pub source_status: String,
    pub lifecycle: MlbGameLifecycle,
    pub reason: String,
}

#[derive(Clone, Debug)]
pub struct CommittedSet {
    pub source_label: String,
    pub envelopes: Vec<PathBuf>,
    pub artifacts: Vec<CommittedArtifact>,
    pub skipped: Vec<SkippedGame>,
    pub duplicates: usize,
    pub checksum_failures: Vec<String>,
}

pub fn from_ingest_handoff(handoff: &W1CommitHandoff) -> Result<CommittedSet, W3Error> {
    crate::gate::assert_handoff_committed(handoff)?;
    let mut envelopes = Vec::new();
    let mut seen = std::collections::BTreeSet::new();
    let mut duplicates = 0usize;
    for a in &handoff.artifacts {
        if a.source != SOURCE_STATSAPI {
            continue;
        }
        if !seen.insert(a.sha256.clone()) {
            duplicates += 1;
            continue;
        }
        envelopes.push(PathBuf::from(&a.path));
    }
    Ok(CommittedSet {
        source_label: format!("ingest-handoff:{}", handoff.run_id),
        envelopes,
        artifacts: handoff.artifacts.clone(),
        skipped: Vec::new(),
        duplicates,
        checksum_failures: Vec::new(),
    })
}

pub fn from_w2_collect_manifest(path: &Path) -> Result<CommittedSet, W3Error> {
    let body = fs::read_to_string(path)?;
    let report: CollectReport = serde_json::from_str(&body)?;
    let mut envelopes = Vec::new();
    let mut artifacts = Vec::new();
    let mut skipped = Vec::new();
    let mut checksum_failures = Vec::new();
    let mut seen = std::collections::BTreeSet::new();
    let mut duplicates = 0usize;

    for g in &report.games {
        let life = classify_schedule_status(&g.status);
        if g.skipped || g.envelope_path.is_empty() {
            skipped.push(SkippedGame {
                game_pk: g.game_pk.clone(),
                official_date: g.official_date.clone(),
                source_status: g.status.clone(),
                lifecycle: life,
                reason: "not a committed PBP artifact (skipped/non-final)".into(),
            });
            continue;
        }
        let env = PathBuf::from(&g.envelope_path);
        match verify_checksum(&env, &g.sha256) {
            Ok(()) => {
                if !seen.insert(g.sha256.clone()) {
                    duplicates += 1;
                    continue;
                }
                envelopes.push(env.clone());
                artifacts.push(CommittedArtifact {
                    artifact_id: format!("{SOURCE_STATSAPI}:{}", g.game_pk),
                    source: SOURCE_STATSAPI.into(),
                    path: env.display().to_string(),
                    sha256: g.sha256.clone(),
                    partition_id: g.game_pk.clone(),
                    date: g.official_date.clone(),
                    commit_status: CommitStatus::Committed,
                });
            }
            Err(e) => checksum_failures.push(e.to_string()),
        }
    }

    Ok(CommittedSet {
        source_label: format!("w2-collect-manifest:{}", path.display()),
        envelopes,
        artifacts,
        skipped,
        duplicates,
        checksum_failures,
    })
}
