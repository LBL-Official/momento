//! Identity stub v1 (W1). Official MLB game pk is always UNMAPPED — never invented.

use serde::{Deserialize, Serialize};

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum IdentityMatchStatus {
    Unmapped,
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct IdentityStubV1 {
    pub game_id: String,
    pub market_id: String,
    pub ticker: String,
    pub event_ticker: String,
    pub series: String,
    pub mlb_game_pk: Option<String>,
    pub match_status: IdentityMatchStatus,
    /// Venue metadata open_time string when present. Not MARKET_OPEN_PRICE.
    pub open_time: Option<String>,
}

impl IdentityStubV1 {
    pub fn unmapped(
        game_id: impl Into<String>,
        market_id: impl Into<String>,
        ticker: impl Into<String>,
        event_ticker: impl Into<String>,
        series: impl Into<String>,
    ) -> Self {
        Self {
            game_id: game_id.into(),
            market_id: market_id.into(),
            ticker: ticker.into(),
            event_ticker: event_ticker.into(),
            series: series.into(),
            mlb_game_pk: None,
            match_status: IdentityMatchStatus::Unmapped,
            open_time: None,
        }
    }
}
