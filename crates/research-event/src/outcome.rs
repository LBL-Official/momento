//! Outcome-only object. Never attached to replay-at-t game state.

use serde::{Deserialize, Serialize};

use crate::event::Score;
use crate::identity::CanonicalGameId;

/// Terminal / label store. Forbidden as a historical feature at t < terminal.
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct GameOutcome {
    pub game_id: CanonicalGameId,
    pub final_score: Score,
    pub winner: Winner,
    pub outcome_source: String,
    pub observability: String,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum Winner {
    Home,
    Away,
    Tie,
    Unavailable,
}

impl GameOutcome {
    pub fn from_final_score(
        game_id: CanonicalGameId,
        score: Score,
        source: impl Into<String>,
    ) -> Self {
        let winner = if score.home > score.away {
            Winner::Home
        } else if score.away > score.home {
            Winner::Away
        } else {
            Winner::Tie
        };
        Self {
            game_id,
            final_score: score,
            winner,
            outcome_source: source.into(),
            observability: "OUTCOME_LABEL".into(),
        }
    }
}
