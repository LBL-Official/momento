//! Deterministic B1 identities. No wall-clock, no random UUIDs.

use sha2::{Digest, Sha256};

pub fn hex_id(kind: &str, parts: &[&str]) -> String {
    let mut h = Sha256::new();
    h.update(kind.as_bytes());
    for p in parts {
        h.update([0u8]);
        h.update(p.as_bytes());
    }
    format!("{:x}", h.finalize())
}

pub fn snapshot_id(
    dataset_version: &str,
    w8_opportunity_id: &str,
    entry_observation_id: &str,
) -> String {
    hex_id(
        "b1.snapshot",
        &[dataset_version, w8_opportunity_id, entry_observation_id],
    )
}
