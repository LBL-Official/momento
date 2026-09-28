//! Research ITI First Touch / REACH. Proposes intents only. Not 80/81.
//!
//! Observation basis is YES bid. Warehouse First Touch used candle
//! `yes_bid_close`; that difference stays labeled. Candle path ≠ fill.

#![forbid(unsafe_code)]

mod strategy;

pub use strategy::{
    ItiContext, ItiDirective, ItiGamePhase, ItiGameSnapshot, ItiIssue, ItiPrices, ItiStrategy,
    ItiStrategySnapshot, ItiTurn, RESEARCH_ITI_STRATEGY_ID, ReachExecution,
};
