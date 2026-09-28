//! WNBA strategy: same 80 / same-side 81 / maker 80–83 / first 89 GAME_LOCKED
//! machine as MLB. Own GameId state. Own StrategyId.
//!
//! Does not own bankroll, fees, orders, or Kalshi transport.

#![forbid(unsafe_code)]

use momento_core::StrategyId;
use momento_strategy_mlb::{
    MlbContext, MlbDirective, MlbIssue, MlbStrategy, MlbStrategySnapshot, MlbTurn,
};

pub use momento_strategy_mlb::{
    CONFIRM_81_CENTS, FIRST_80_CENTS, LOCK_89_CENTS, MAX_ENTRY_CENTS, QuoteReject, StopExecution,
    StopRounding, StopWatchSignal, ValidQuote, maker_limit, qualifying_price,
};

pub const WNBA_STRATEGY_ID: StrategyId = StrategyId::WNBA;

/// This crate implements the WNBA sport strategy only.
pub const SPORT: momento_sports::SportId = momento_sports::SportId::Wnba;

pub type WnbaContext<'a> = MlbContext<'a>;
pub type WnbaDirective = MlbDirective;
pub type WnbaIssue = MlbIssue;
pub type WnbaTurn = MlbTurn;
pub type WnbaStrategySnapshot = MlbStrategySnapshot;

/// Thin identity wrapper around the shared 80/81/89 observer.
#[derive(Clone, Debug)]
pub struct WnbaStrategy {
    inner: MlbStrategy,
}

impl Default for WnbaStrategy {
    fn default() -> Self {
        Self::new()
    }
}

impl WnbaStrategy {
    pub fn new() -> Self {
        Self {
            inner: MlbStrategy::for_strategy(WNBA_STRATEGY_ID),
        }
    }

    pub fn snapshot(&self) -> WnbaStrategySnapshot {
        self.inner.snapshot()
    }

    pub fn restore(snapshot: WnbaStrategySnapshot) -> Self {
        Self {
            inner: MlbStrategy::restore_for(WNBA_STRATEGY_ID, snapshot),
        }
    }

    pub fn strategy_id(&self) -> StrategyId {
        self.inner.strategy_id()
    }

    pub fn inner(&self) -> &MlbStrategy {
        &self.inner
    }

    pub fn inner_mut(&mut self) -> &mut MlbStrategy {
        &mut self.inner
    }

    pub fn observe(&mut self, ctx: &WnbaContext<'_>) -> WnbaTurn {
        self.inner.observe(ctx)
    }
}
