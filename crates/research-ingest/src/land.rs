//! Immutable landing. Same bytes no-op; different bytes new version + alert.

use std::fs;
use std::path::PathBuf;

use chrono::{DateTime, Utc};
use serde_json::json;

use crate::error::IngestError;
use crate::paths::{IngestPaths, sha256_bytes, sha256_file};
use crate::source::DiscoveredPartition;
use crate::types::SOURCE_STATSAPI;

#[derive(Clone, Debug)]
pub enum LandResult {
    Written {
        path: PathBuf,
        sha256: String,
    },
    AlreadyKnown {
        path: PathBuf,
        sha256: String,
    },
    VersionConflict {
        original: PathBuf,
        original_sha: String,
        new_path: PathBuf,
        new_sha: String,
    },
}

pub fn wrap_statsapi_envelope(
    partition: &DiscoveredPartition,
    payload: Vec<u8>,
    retrieved_at: DateTime<Utc>,
) -> Result<Vec<u8>, IngestError> {
    let payload: serde_json::Value = serde_json::from_slice(&payload)?;
    let envelope = json!({
        "envelope_version": "W2.RAW.1.0.0",
        "fixture_kind": "HISTORICAL_SOURCE",
        "source": SOURCE_STATSAPI,
        "source_game_id": partition.partition_id,
        "retrieved_at": retrieved_at.to_rfc3339(),
        "payload": payload,
    });
    Ok(serde_json::to_vec(&envelope)?)
}

pub fn land_bytes(
    paths: &IngestPaths,
    partition: &DiscoveredPartition,
    bytes: &[u8],
) -> Result<LandResult, IngestError> {
    let dest = paths.landing_game(partition.date, &partition.partition_id);
    land_at_dest(dest, bytes, &partition.partition_id)
}

pub fn land_at_dest(
    dest: PathBuf,
    bytes: &[u8],
    logical_id: &str,
) -> Result<LandResult, IngestError> {
    if let Some(parent) = dest.parent() {
        fs::create_dir_all(parent)?;
    }
    let incoming = sha256_bytes(bytes);
    if dest.exists() {
        let existing = sha256_file(&dest)?;
        if existing == incoming {
            return Ok(LandResult::AlreadyKnown {
                path: dest,
                sha256: existing,
            });
        }
        let new_path = dest.with_file_name(format!(
            "{logical_id}.sha256-{}.envelope.json",
            &incoming[..12]
        ));
        fs::write(&new_path, bytes)?;
        let verify = sha256_file(&new_path)?;
        if verify != incoming {
            return Err(IngestError::ChecksumMismatch {
                path: new_path.display().to_string(),
                expected: incoming,
                actual: verify,
            });
        }
        return Ok(LandResult::VersionConflict {
            original: dest,
            original_sha: existing,
            new_path,
            new_sha: verify,
        });
    }
    fs::write(&dest, bytes)?;
    let verify = sha256_file(&dest)?;
    if verify != incoming {
        let _ = fs::remove_file(&dest);
        return Err(IngestError::ChecksumMismatch {
            path: dest.display().to_string(),
            expected: incoming,
            actual: verify,
        });
    }
    Ok(LandResult::Written {
        path: dest,
        sha256: verify,
    })
}
