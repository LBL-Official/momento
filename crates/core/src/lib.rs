//! Momento core domain types.
//!
//! This crate contains exact financial types, identifiers, state machines,
//! audit events, and venue-agnostic traits. It performs no I/O and does not
//! implement MLB signal detection or Kalshi transport.

#![forbid(unsafe_code)]

pub mod approval;
pub mod arithmetic;
pub mod audit;
pub mod basis;
pub mod config;
pub mod error;
pub mod fee;
pub mod fill;
pub mod ids;
pub mod intent;
pub mod market;
pub mod money;
pub mod order;
pub mod position;
pub mod reconciliation;
pub mod snapshot;
pub mod states;
pub mod time;
pub mod venue;

pub use approval::{ApprovedTradeIntent, RiskDecision, RiskGrant, RiskRejectReason};
pub use arithmetic::contract_premium;
pub use audit::{AuditEvent, AuditLog, AuditMeta, InMemoryAuditLog, StateCorrectionKind};
pub use basis::{
    BasisPrice, EntryBasisCalculator, ProposedHalfEntryStop, ProposedVwapEntryBasis,
    StopThresholdPolicy, half_entry_stop_from_fills, yes_bid_reaches_stop,
};
pub use config::{
    LIVE_CONFIRMATION, LiveGate, PositionSizingMode, StrategyProfile, TradingConfig, TradingMode,
};
pub use error::MomentoError;
pub use error::{ConfigError, VenueError};
pub use fee::{Fee, FeeKind, FeeModelId};
pub use fill::Fill;
pub use ids::{
    ClientOrderId, EventId, FillId, GameId, MarketId, PositionId, RiskDecisionId, SnapshotId,
    StrategyId, VenueOrderId,
};
pub use intent::{
    AdditionalExposure, BuildPositionIntent, EntryStyle, LiquidationIntent, LiquidationReason,
    LiquidationStyle, TradeIntent,
};
pub use market::{MarketEvent, Side};
pub use money::{Bps, Contracts, EconomicExposure, Money, Price};
pub use order::{Order, OrderPurpose, OrderQuantities, OrderState};
pub use position::{EntryPriceGate, GameLock, Position, PositionExitCause, PositionLifecycle};
pub use reconciliation::{
    OrderPresence, ReconcileOutcome, ReconciliationResult, ReconciliationState, SettlementEvent,
    UnknownOrder, VenueExposureView, VenueOpenOrders, VenueOrderSnapshot, VenueReportedExposure,
};
pub use snapshot::{
    PacificCalendarDay, SnapshotSource, TradingWeekId, WeeklyBankrollSnapshot, pacific_calendar_day,
};
pub use states::KillSwitch;
pub use time::{ExchangeTimestamp, ProcessedAt, ReceivedAt, utc_now};
pub use venue::{
    FillView, MappedOrderView, VenueAccount, VenueFills, VenueMarketData, VenueMarketDiscovery,
    VenueMarketSnapshot, VenueOrderStatus, VenueOrders, VenueSettlement, VenueSettlementView,
};
