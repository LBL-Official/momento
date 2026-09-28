//! Consume ONLY committed + checksum-verified artifacts.

use std::path::Path;

use momento_research_data::checksum::sha256_file;
use momento_research_ingest::{CommitStatus, W1CommitHandoff};

use crate::error::W3Error;

pub fn assert_handoff_committed(handoff: &W1CommitHandoff) -> Result<(), W3Error> {
    handoff
        .all_committed_and_verified()
        .map_err(W3Error::Uncommitted)?;
    for a in &handoff.artifacts {
        if a.commit_status != CommitStatus::Committed {
            return Err(W3Error::Uncommitted(a.artifact_id.clone()));
        }
        verify_checksum(Path::new(&a.path), &a.sha256)?;
    }
    Ok(())
}

pub fn verify_checksum(path: &Path, expected: &str) -> Result<(), W3Error> {
    if expected.is_empty() {
        return Err(W3Error::Uncommitted(format!(
            "{} has empty checksum",
            path.display()
        )));
    }
    let actual = sha256_file(path).map_err(|e| W3Error::Io(e.to_string()))?;
    if actual != expected {
        return Err(W3Error::ChecksumMismatch {
            path: path.display().to_string(),
            expected: expected.to_string(),
            actual,
        });
    }
    Ok(())
}
