//! W7 join points: GameId + timestamp + sequence + state_id. No prices.

use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};

use crate::types::ReconstructedGame;

/// Stable temporal join key for a later market-path waterfall. W6 does not attach prices.
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct StateJoinKey {
    pub game_id: String,
    pub canonical_timestamp: Option<DateTime<Utc>>,
    pub state_seq: u32,
    pub state_id: String,
    pub event_id: Option<String>,
}

pub fn join_points(game: &ReconstructedGame) -> Vec<StateJoinKey> {
    game.states
        .iter()
        .filter(|s| s.state_seq > 0)
        .map(|s| StateJoinKey {
            game_id: s.game_id.clone(),
            canonical_timestamp: s.canonical_timestamp.as_value().copied(),
            state_seq: s.state_seq,
            state_id: s.state_id.clone(),
            event_id: s.event_id.clone(),
        })
        .collect()
}
