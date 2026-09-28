//! MLB strategy: first 80, same-side 81, maker 80–83, first 89 GAME_LOCKED.
//!
//! Does not own bankroll, fees, orders, or Kalshi transport.

#![forbid(unsafe_code)]

mod quote;
mod state;
mod stop;
mod strategy;

pub use quote::{
    CONFIRM_81_CENTS, FIRST_80_CENTS, LOCK_89_CENTS, MAX_ENTRY_CENTS, QuoteReject, ValidQuote,
    maker_limit, qualifying_price, validate_quote,
};
pub use state::{FirstTrigger, MlbGamePhase, MlbGameSnapshot, MlbStrategySnapshot};
pub use stop::{
    loss_reduction_in_progress, quote_is_position_stop_eligible, stop_threshold,
    yes_bid_triggers_stop,
};
pub use strategy::{
    MLB_STRATEGY_ID, MlbContext, MlbDirective, MlbIssue, MlbStrategy, MlbTurn, StopExecution,
    StopRounding, StopWatchSignal,
};

/// This crate implements the MLB sport strategy only.
pub const SPORT: momento_sports::SportId = momento_sports::SportId::Mlb;
