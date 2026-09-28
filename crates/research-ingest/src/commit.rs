//! W1 commit gate: checksum-verified artifacts only.

use chrono::{DateTime, Utc};

use crate::error::IngestError;
use crate::paths::sha256_file;
use crate::types::{ARTIFACT_VERSION, CommitStatus, CommittedArtifact, PLANE, W1CommitHandoff};

pub fn commit_artifacts(
    run_id: &str,
    at: DateTime<Utc>,
    mut artifacts: Vec<CommittedArtifact>,
) -> Result<W1CommitHandoff, IngestError> {
    for a in &mut artifacts {
        if a.commit_status == CommitStatus::Pending {
            let on_disk = sha256_file(std::path::Path::new(&a.path))?;
            if on_disk != a.sha256 {
                a.commit_status = CommitStatus::Rejected;
                return Err(IngestError::ChecksumMismatch {
                    path: a.path.clone(),
                    expected: a.sha256.clone(),
                    actual: on_disk,
                });
            }
            a.commit_status = CommitStatus::Committed;
        }
    }
    Ok(W1CommitHandoff {
        run_id: run_id.to_string(),
        plane: PLANE.into(),
        artifact_version: ARTIFACT_VERSION.into(),
        committed_at: at,
        artifacts,
    })
}
