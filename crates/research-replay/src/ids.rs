//! Deterministic W8 identities. No wall-clock, no insertion order.

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

pub fn replay_event_id(
    w7_ver: &str,
    game_id: &str,
    observation_id: &str,
    event_type: &str,
) -> String {
    hex_id("w8.event", &[w7_ver, game_id, observation_id, event_type])
}

pub fn opportunity_id(
    w7_ver: &str,
    game_id: &str,
    market_id: &str,
    side: &str,
    first80_obs: &str,
) -> String {
    hex_id(
        "w8.opportunity",
        &[w7_ver, game_id, market_id, side, first80_obs],
    )
}
