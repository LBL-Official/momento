//! Consume ONLY committed + checksum-verified Kalshi discovery artifacts.

use std::path::Path;

use momento_research_data::checksum::sha256_file;
use momento_research_ingest::types::{CommitStatus, SOURCE_KALSHI_DISCOVERY, W1CommitHandoff};

use crate::error::W4Error;

pub fn assert_handoff_committed(handoff: &W1CommitHandoff) -> Result<(), W4Error> {
    handoff
        .all_committed_and_verified()
        .map_err(W4Error::Uncommitted)?;
    Ok(())
}

pub fn verify_checksum(path: &Path, expected: &str) -> Result<(), W4Error> {
    if expected.is_empty() {
        return Err(W4Error::Uncommitted(format!(
            "{} has empty checksum",
            path.display()
        )));
    }
    let actual = sha256_file(path).map_err(|e| W4Error::Io(e.to_string()))?;
    if actual != expected {
        return Err(W4Error::ChecksumMismatch {
            path: path.display().to_string(),
            expected: expected.to_string(),
            actual,
        });
    }
    Ok(())
}

pub fn is_kalshi_discovery(source: &str) -> bool {
    source == SOURCE_KALSHI_DISCOVERY
}

pub fn artifact_is_committed_discovery(source: &str, status: CommitStatus) -> bool {
    is_kalshi_discovery(source) && status == CommitStatus::Committed
}
