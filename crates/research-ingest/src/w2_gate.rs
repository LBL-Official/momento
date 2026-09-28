//! W2 may consume only committed, checksum-verified W1 artifacts.

use std::path::{Path, PathBuf};

use momento_research_event::historical::{HistoricalReconstructionReport, reconstruct_paths};

use crate::error::IngestError;
use crate::paths::sha256_file;
use crate::types::{CommitStatus, SOURCE_STATSAPI, W1CommitHandoff};

pub fn canonicalize_committed(
    handoff: &W1CommitHandoff,
    lake_root: &Path,
) -> Result<Option<HistoricalReconstructionReport>, IngestError> {
    handoff
        .all_committed_and_verified()
        .map_err(IngestError::UncommittedW1)?;

    let mut envelopes = Vec::new();
    for a in &handoff.artifacts {
        if a.source != SOURCE_STATSAPI {
            continue;
        }
        if a.commit_status != CommitStatus::Committed {
            return Err(IngestError::UncommittedW1(a.artifact_id.clone()));
        }
        let path = PathBuf::from(&a.path);
        let on_disk = sha256_file(&path)?;
        if on_disk != a.sha256 {
            return Err(IngestError::ChecksumMismatch {
                path: a.path.clone(),
                expected: a.sha256.clone(),
                actual: on_disk,
            });
        }
        envelopes.push(path);
    }
    if envelopes.is_empty() {
        return Ok(None);
    }
    reconstruct_paths(&envelopes, lake_root, &handoff.run_id)
        .map_err(|e| IngestError::SourceFailure(format!("W2 canonicalize: {e}")))
        .map(Some)
}

/// Explicit refusal helper for tests (pending artifacts never reach W2).
pub fn assert_w2_may_consume(handoff: &W1CommitHandoff) -> Result<(), IngestError> {
    handoff
        .all_committed_and_verified()
        .map_err(IngestError::UncommittedW1)
}
