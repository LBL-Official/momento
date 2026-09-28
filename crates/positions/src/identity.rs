//! Position identity: one GameId maps to one PositionId.

use std::collections::HashMap;

use momento_core::{GameId, PositionId, StrategyId};

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum PositionIndexError {
    ConflictingPositionId,
}

/// Enforces ONE GAME = ONE LOGICAL POSITION for a strategy.
#[derive(Clone, Debug, Default)]
pub struct GamePositionIndex {
    by_game: HashMap<(u128, u128), PositionId>,
}

impl GamePositionIndex {
    pub fn new() -> Self {
        Self::default()
    }

    pub fn id_for(&mut self, strategy: StrategyId, game: GameId) -> PositionId {
        *self
            .by_game
            .entry((strategy.raw(), game.raw()))
            .or_insert_with(PositionId::generate)
    }

    pub fn register(
        &mut self,
        strategy: StrategyId,
        game: GameId,
        id: PositionId,
    ) -> Result<(), PositionIndexError> {
        match self.by_game.get(&(strategy.raw(), game.raw())) {
            Some(existing) if *existing != id => Err(PositionIndexError::ConflictingPositionId),
            Some(_) => Ok(()),
            None => {
                self.by_game.insert((strategy.raw(), game.raw()), id);
                Ok(())
            }
        }
    }

    pub fn get(&self, strategy: StrategyId, game: GameId) -> Option<PositionId> {
        self.by_game.get(&(strategy.raw(), game.raw())).copied()
    }

    pub fn entries(&self) -> Vec<(u128, u128, u128)> {
        self.by_game
            .iter()
            .map(|((strategy, game), id)| (*strategy, *game, id.raw()))
            .collect()
    }
}
