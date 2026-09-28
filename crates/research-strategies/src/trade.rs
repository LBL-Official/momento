//! FIRST01 game-scoped trade lifecycle — one canonical opportunity per [`GameId`].
//!
//! Mirrors live `MlbStrategy` + position gates:
//! - `first_80` binds one MarketId+Side for the game (never cleared).
//! - After any filled exposure reaches OpenComplete/Flat, live `can_attempt_entry`
//!   permanently blocks further entry for that position/game.
//! - Opponent markets after binding are ignored for sequencing.
//! - Multiple `Build` intents may occur for the *same* opportunity while
//!   PositionBuilding (remainder), but never a second independent opportunity.

use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};

use momento_core::Side;

use crate::first01::{FIRST01_NAME, FIRST01_VERSION};

pub const ENTRY_REASON_FIRST01: &str = "FIRST01_80_TO_81_CONFIRMED_MAKER";

/// Deterministic opportunity identity: GameId + MarketId + Side + sequence.
#[derive(Clone, Debug, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub struct OpportunityId(pub String);

impl OpportunityId {
    pub fn new(game_id: u128, market_id: u128, side: Side, sequence: u32) -> Self {
        Self(format!("{game_id}:{market_id}:{side:?}:{sequence}"))
    }
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct TradeId(pub String);

impl TradeId {
    pub fn from_opportunity(opportunity_id: &OpportunityId) -> Self {
        Self(format!("trade:{}", opportunity_id.0))
    }

    pub fn numbered(n: u64) -> Self {
        Self(format!("FIRST01-{n:06}"))
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum OpportunityLifecycle {
    Open,
    IntentEmitted,
    EntryWorking,
    PartiallyFilled,
    PositionOpen,
    LiquidationActive,
    TradeComplete,
    Unfilled,
    GameLocked,
    PriceInvalidated,
}

#[derive(Clone, Copy, Debug, Default, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum GameTradePhase {
    #[default]
    NoTrade,
    OpportunityOpen,
    EntryWorking,
    PartiallyFilled,
    PositionOpen,
    LiquidationActive,
    TradeComplete,
    Unfilled,
    GameLocked,
}

/// Why a quote did or did not advance the game lifecycle.
#[derive(Clone, Copy, Debug, Default, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum LifecycleAction {
    #[default]
    Observed,
    FirstThresholdRecorded,
    ConfirmationPending,
    OpportunityCreated,
    IntentEmitted,
    SuppressedByExistingGameTrade,
    SuppressedByOpponentMarket,
    SuppressedByWorkingEntry,
    SuppressedByPosition,
    SuppressedByLiquidation,
    SuppressedByGameLock,
    SuppressedByLifecycleConsumed,
    SuppressedAboveMax,
    SuppressedMakerIneligible,
    GameLocked,
}

/// Host-supplied execution state — mirrors live [`MlbContext`] entry gates.
#[derive(Clone, Copy, Debug, Default, PartialEq, Eq)]
pub struct EntryContext {
    pub has_working_entry: bool,
    pub position_filled_qty: u32,
    pub position_net_qty: u32,
    /// Remaining entry contracts still actionable (budget remainder).
    pub remaining_entry_qty: u32,
    pub liquidation_active: bool,
    /// Live `PositionLifecycle::Flat | OpenComplete | Settled`.
    pub position_entry_closed: bool,
}

impl EntryContext {
    pub fn game_trade_active(self) -> bool {
        self.has_working_entry || self.position_net_qty > 0 || self.liquidation_active
    }

    pub fn blocks_new_opportunity(self) -> bool {
        self.game_trade_active() || self.position_entry_closed || self.position_filled_qty > 0
    }

    /// Live may emit another Build for remainder while PositionBuilding.
    pub fn allows_remainder_intent(self) -> bool {
        !self.has_working_entry
            && !self.liquidation_active
            && !self.position_entry_closed
            && self.position_filled_qty > 0
            && self.position_net_qty > 0
            && self.remaining_entry_qty > 0
    }

    pub fn blocks_entry_intent(self) -> bool {
        self.has_working_entry
            || self.liquidation_active
            || self.position_entry_closed
            || (self.position_filled_qty > 0 && self.remaining_entry_qty == 0)
    }
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct QuoteObservation {
    pub strategy: String,
    pub strategy_version: u32,
    pub game_id: u128,
    pub market_id: u128,
    pub ticker: String,
    pub side: Side,
    pub exchange_timestamp_ms: i64,
    pub received_timestamp: DateTime<Utc>,
    pub bid_cents: u16,
    pub ask_cents: u16,
    pub qualifying_bid_cents: u16,
    pub entry_phase: GameTradePhase,
    pub qualifies_first01: bool,
    pub lifecycle_action: LifecycleAction,
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct EntryOpportunity {
    pub opportunity_id: OpportunityId,
    pub trade_id: TradeId,
    pub game_id: u128,
    pub market_id: u128,
    pub ticker: String,
    pub side: Side,
    pub sequence: u32,
    pub first_80_timestamp_ms: i64,
    pub first_80_price_cents: u16,
    pub confirmation_81_timestamp_ms: i64,
    pub confirmation_81_price_cents: u16,
    pub qualifying_timestamp_ms: i64,
    pub qualifying_bid_cents: u16,
    pub qualifying_ask_cents: u16,
    pub maker_limit_cents: u16,
    pub entry_reason: String,
    pub lifecycle: OpportunityLifecycle,
    pub game_trade_phase: GameTradePhase,
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct EntryIntent {
    pub intent_id: String,
    pub opportunity_id: OpportunityId,
    pub trade_id: TradeId,
    pub strategy: String,
    pub strategy_version: u32,
    pub game_id: u128,
    pub market_id: u128,
    pub ticker: String,
    pub side: Side,
    pub exchange_timestamp_ms: i64,
    pub received_timestamp: DateTime<Utc>,
    pub first_80_timestamp_ms: i64,
    pub confirmation_81_timestamp_ms: i64,
    pub maker_limit_cents: u16,
    pub bid_cents: u16,
    pub ask_cents: u16,
    pub first_threshold_cents: u16,
    pub confirmation_threshold_cents: u16,
    pub maximum_entry_price_cents: u16,
    pub entry_reason: String,
    pub is_remainder: bool,
}

impl EntryIntent {
    #[allow(clippy::too_many_arguments)]
    pub fn new(
        opportunity: &EntryOpportunity,
        exchange_timestamp_ms: i64,
        received_timestamp: DateTime<Utc>,
        first_threshold_cents: u16,
        confirmation_threshold_cents: u16,
        maximum_entry_price_cents: u16,
        is_remainder: bool,
        intent_seq: u32,
    ) -> Self {
        Self {
            intent_id: format!("intent:{}:{}", opportunity.opportunity_id.0, intent_seq),
            opportunity_id: opportunity.opportunity_id.clone(),
            trade_id: opportunity.trade_id.clone(),
            strategy: FIRST01_NAME.to_string(),
            strategy_version: FIRST01_VERSION,
            game_id: opportunity.game_id,
            market_id: opportunity.market_id,
            ticker: opportunity.ticker.clone(),
            side: opportunity.side,
            exchange_timestamp_ms,
            received_timestamp,
            first_80_timestamp_ms: opportunity.first_80_timestamp_ms,
            confirmation_81_timestamp_ms: opportunity.confirmation_81_timestamp_ms,
            maker_limit_cents: opportunity.maker_limit_cents,
            bid_cents: opportunity.qualifying_bid_cents,
            ask_cents: opportunity.qualifying_ask_cents,
            first_threshold_cents,
            confirmation_threshold_cents,
            maximum_entry_price_cents,
            entry_reason: ENTRY_REASON_FIRST01.to_string(),
            is_remainder,
        }
    }
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub(crate) struct ActiveOpportunityState {
    pub opportunity: EntryOpportunity,
    pub intent_emitted: bool,
    pub intent_count: u32,
    pub had_position: bool,
}
