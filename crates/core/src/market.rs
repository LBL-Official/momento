use serde::{Deserialize, Serialize};

use crate::ids::{GameId, MarketId};
use crate::money::Price;
use crate::time::{ExchangeTimestamp, ReceivedAt};

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub enum Side {
    Yes,
    No,
}

/// Normalized market event. Detection of 80/81/89 is NOT implemented here.
///
/// MLB qualifying observation is [`MarketEvent::bid`] (Kalshi `yes_bid_dollars`).
/// [`MarketEvent::mid`] is not a venue field and is not used for 80/81/89.
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct MarketEvent {
    pub game_id: GameId,
    pub market_id: MarketId,
    pub side: Option<Side>,
    pub exchange_ts: ExchangeTimestamp,
    pub received_at: ReceivedAt,
    pub last: Option<Price>,
    pub bid: Option<Price>,
    pub ask: Option<Price>,
    pub mid: Option<Price>,
    pub bid_depth: Option<u32>,
    pub ask_depth: Option<u32>,
    /// Opaque score/game-state note. Strategy records it; it is not a model input.
    pub game_state: Option<String>,
}

impl MarketEvent {
    pub fn spread_cents(&self) -> Option<u16> {
        match (self.ask, self.bid) {
            (Some(ask), Some(bid)) if ask.cents() >= bid.cents() => Some(ask.cents() - bid.cents()),
            _ => None,
        }
    }
}
