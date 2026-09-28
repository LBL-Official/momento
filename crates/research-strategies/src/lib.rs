//! Versioned research strategy models. Isolated from live trading.
//!
//! FIRST01 is the canonical baseline representation of the current live
//! MLB + WNBA 80/81/89 entry and 50% position-scoped stop exit logic.

#![forbid(unsafe_code)]

pub mod entries;
pub mod exits;
pub mod first01;
pub mod identity;
pub mod model;
pub mod params;
pub mod quote;
pub mod signals;
pub mod trade;

pub use entries::{EntryEngine, EntryObservation, EntryPhase, EntryTurn};
pub use exits::{ExitEngine, ExitObservation, ExitTurn, ResearchPosition, ResearchPositionFill};
pub use first01::{
    FIRST01_DEFAULT_ENTRY, FIRST01_DEFAULT_EXIT, FIRST01_MARKET_UNIVERSE, FIRST01_NAME,
    FIRST01_VERSION, First01Model,
};
pub use identity::{EntryStateKey, PositionScope};
pub use model::{StrategyModel, StrategyRunMetadata};
pub use params::{EffectiveParameters, EntryParameters, ExitParameters, ExperimentOverrides};
pub use quote::{QuoteReject, StrategyQuote, ValidQuote};
pub use signals::{EntrySignal, ExitReason, ExitSignal, LiquidationState};
pub use trade::{
    ENTRY_REASON_FIRST01, EntryContext, EntryIntent, EntryOpportunity, GameTradePhase,
    LifecycleAction, OpportunityId, OpportunityLifecycle, QuoteObservation, TradeId,
};
