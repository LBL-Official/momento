//! Ticker → domain identity lookup. Never generates PositionId.

use std::collections::HashMap;

use rsa::sha2::{Digest, Sha256};

use momento_core::{GameId, MarketId, PositionId};

/// Stable host identity from a venue ticker. Not a PositionId generator.
pub fn stable_u128(kind: &str, value: &str) -> u128 {
    let mut h = Sha256::new();
    h.update(kind.as_bytes());
    h.update([0]);
    h.update(value.as_bytes());
    let out = h.finalize();
    let mut bytes = [0u8; 16];
    bytes.copy_from_slice(&out[..16]);
    u128::from_be_bytes(bytes)
}

pub fn game_id_for_event_ticker(event_ticker: &str) -> GameId {
    GameId::from_raw(stable_u128("game", event_ticker))
}

pub fn market_id_for_ticker(ticker: &str) -> MarketId {
    MarketId::from_raw(stable_u128("market", ticker))
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct MarketBinding {
    pub market_id: MarketId,
    pub game_id: GameId,
    pub position_id: Option<PositionId>,
}

pub trait VenueIdentity {
    fn lookup_ticker(&self, ticker: &str) -> Option<MarketBinding>;
    fn ticker_for_game(&self, game: GameId) -> Option<String>;
    /// Authoritative ticker for stop/liquidation. Never substitute [`Self::ticker_for_game`].
    fn ticker_for_market(&self, market: MarketId) -> Option<String>;
}

#[derive(Clone, Debug, Default)]
pub struct StaticIdentity {
    by_ticker: HashMap<String, MarketBinding>,
}

impl StaticIdentity {
    pub fn new() -> Self {
        Self::default()
    }

    pub fn bind(&mut self, ticker: impl Into<String>, binding: MarketBinding) {
        self.by_ticker.insert(ticker.into(), binding);
    }

    pub fn snapshot_bindings(&self) -> Vec<(String, MarketBinding)> {
        self.by_ticker
            .iter()
            .map(|(ticker, binding)| (ticker.clone(), *binding))
            .collect()
    }
}

impl VenueIdentity for StaticIdentity {
    fn lookup_ticker(&self, ticker: &str) -> Option<MarketBinding> {
        self.by_ticker.get(ticker).copied()
    }

    fn ticker_for_game(&self, game: GameId) -> Option<String> {
        self.by_ticker
            .iter()
            .find(|(_, b)| b.game_id == game)
            .map(|(t, _)| t.clone())
    }

    fn ticker_for_market(&self, market: MarketId) -> Option<String> {
        self.by_ticker
            .iter()
            .find(|(_, b)| b.market_id == market)
            .map(|(t, _)| t.clone())
    }
}
