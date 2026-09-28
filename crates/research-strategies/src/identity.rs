//! Market and position identity for research signals.

use serde::{Deserialize, Serialize};

use momento_core::{GameId, MarketId, PositionId, Side};

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub struct EntryStateKey {
    pub game_id: u128,
    pub market_id: u128,
    pub side: Side,
}

impl EntryStateKey {
    pub fn new(game_id: GameId, market_id: MarketId, side: Side) -> Self {
        Self {
            game_id: game_id.raw(),
            market_id: market_id.raw(),
            side,
        }
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub struct PositionScope {
    pub position_id: u128,
    pub game_id: u128,
    pub market_id: u128,
    pub side: Side,
}

impl PositionScope {
    pub fn new(position_id: PositionId, game_id: GameId, market_id: MarketId, side: Side) -> Self {
        Self {
            position_id: position_id.raw(),
            game_id: game_id.raw(),
            market_id: market_id.raw(),
            side,
        }
    }
}
