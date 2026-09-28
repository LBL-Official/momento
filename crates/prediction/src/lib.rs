//! Prediction types. No model. No TradeIntent.

#![forbid(unsafe_code)]

use momento_core::{GameId, MarketId};

/// Placeholder forecast type. Probabilities are not money and must not be
/// converted to [`momento_core::Price`] via floating point.
#[derive(Clone, Debug)]
pub struct Forecast {
    pub game_id: GameId,
    pub market_id: MarketId,
}

impl Forecast {
    pub fn unimplemented() -> Self {
        Self {
            game_id: GameId::from_raw(0),
            market_id: MarketId::from_raw(0),
        }
    }
}
