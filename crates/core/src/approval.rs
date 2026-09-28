//! Risk decision types. Only [`ApprovedTradeIntent`] may be executed.
//!
//! Construction of [`ApprovedTradeIntent`] requires [`RiskGrant`]. The grant is
//! obtained through [`RiskGrant::for_risk_engine`]. Execution accepts this type
//! only; it cannot accept [`crate::intent::TradeIntent`].

use serde::{Deserialize, Serialize};

use crate::fee::FeeModelId;
use crate::ids::{
    ClientOrderId, GameId, MarketId, PositionId, RiskDecisionId, SnapshotId, StrategyId,
};
use crate::intent::TradeIntent;
use crate::market::Side;
use crate::money::{Contracts, Money, Price};
use crate::time::utc_now;
use chrono::{DateTime, Utc};

/// Token proving a risk engine constructed the approval.
#[derive(Clone, Copy, Debug)]
pub struct RiskGrant {
    _private: (),
}

impl RiskGrant {
    /// For implementations of the risk engine only.
    pub const fn for_risk_engine() -> Self {
        Self { _private: () }
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub enum RiskRejectReason {
    MaxPositionExceeded,
    DailyTradeLimit,
    DuplicateGamePosition,
    MarketNotAllowed,
    StaleData,
    KillSwitch,
    InsufficientCapital,
    InvalidPrice,
    InvalidQuantity,
    RiskStateUnknown,
    ReconciliationRequired,
    GameLocked,
    EntryPausedAboveMaxPrice,
    WeeklySnapshotMissing,
    PositionLimitExceeded,
    EntryPriceAboveMaximum,
    KillSwitchActive,
    IncrementalBudgetExceeded,
    InsufficientAvailableCapacity,
    UnsupportedTradeType,
    LiveModeDisabled,
    SnapshotMismatch,
    DailyWinCountLimit,
    DailyLossCountLimit,
    DailyWinCentsLimit,
    DailyLossCentsLimit,
    SessionPnlUnavailable,
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct ApprovedTradeIntent {
    decision_id: RiskDecisionId,
    snapshot_id: SnapshotId,
    strategy_id: StrategyId,
    game_id: GameId,
    market_id: MarketId,
    side: Side,
    position_id: PositionId,
    client_order_id: ClientOrderId,
    limit_price: Price,
    max_contracts: Contracts,
    requested_incremental: Money,
    max_economic: Money,
    original_budget: Money,
    remaining_budget_after: Money,
    fee_estimate: Money,
    fee_model_id: FeeModelId,
    approved_at: DateTime<Utc>,
}

impl ApprovedTradeIntent {
    #[allow(clippy::too_many_arguments)]
    pub fn from_risk_approval(
        _grant: RiskGrant,
        decision_id: RiskDecisionId,
        snapshot_id: SnapshotId,
        intent: &TradeIntent,
        client_order_id: ClientOrderId,
        max_contracts: Contracts,
        max_economic: Money,
        original_budget: Money,
    ) -> Self {
        let b = &intent.build;
        Self {
            decision_id,
            snapshot_id,
            strategy_id: b.strategy_id,
            game_id: b.game_id,
            market_id: b.market_id,
            side: b.side,
            position_id: b.position_id,
            client_order_id,
            limit_price: b.limit_price,
            max_contracts,
            requested_incremental: max_economic,
            max_economic,
            original_budget,
            remaining_budget_after: original_budget.saturating_sub(max_economic),
            fee_estimate: Money::ZERO,
            fee_model_id: FeeModelId::unspecified_legacy(),
            approved_at: utc_now(),
        }
    }

    /// Full M2 constructor. Callers outside risk must not use this.
    #[allow(clippy::too_many_arguments)]
    pub fn from_risk_engine(
        _grant: RiskGrant,
        decision_id: RiskDecisionId,
        snapshot_id: SnapshotId,
        intent: &TradeIntent,
        client_order_id: ClientOrderId,
        max_contracts: Contracts,
        requested_incremental: Money,
        max_economic: Money,
        original_budget: Money,
        remaining_budget_after: Money,
        fee_estimate: Money,
        fee_model_id: FeeModelId,
    ) -> Self {
        let b = &intent.build;
        Self {
            decision_id,
            snapshot_id,
            strategy_id: b.strategy_id,
            game_id: b.game_id,
            market_id: b.market_id,
            side: b.side,
            position_id: b.position_id,
            client_order_id,
            limit_price: b.limit_price,
            max_contracts,
            requested_incremental,
            max_economic,
            original_budget,
            remaining_budget_after,
            fee_estimate,
            fee_model_id,
            approved_at: utc_now(),
        }
    }

    pub const fn decision_id(&self) -> RiskDecisionId {
        self.decision_id
    }

    pub const fn snapshot_id(&self) -> SnapshotId {
        self.snapshot_id
    }

    pub const fn position_id(&self) -> PositionId {
        self.position_id
    }

    pub const fn game_id(&self) -> GameId {
        self.game_id
    }

    pub const fn client_order_id(&self) -> ClientOrderId {
        self.client_order_id
    }

    pub const fn limit_price(&self) -> Price {
        self.limit_price
    }

    pub const fn max_contracts(&self) -> Contracts {
        self.max_contracts
    }

    pub const fn max_economic(&self) -> Money {
        self.max_economic
    }

    pub const fn original_budget(&self) -> Money {
        self.original_budget
    }

    pub const fn strategy_id(&self) -> StrategyId {
        self.strategy_id
    }

    pub const fn market_id(&self) -> MarketId {
        self.market_id
    }

    pub const fn side(&self) -> Side {
        self.side
    }

    pub const fn requested_incremental(&self) -> Money {
        self.requested_incremental
    }

    pub const fn remaining_budget_after(&self) -> Money {
        self.remaining_budget_after
    }

    pub const fn fee_estimate(&self) -> Money {
        self.fee_estimate
    }

    pub fn fee_model_id(&self) -> &FeeModelId {
        &self.fee_model_id
    }

    pub const fn approved_at(&self) -> DateTime<Utc> {
        self.approved_at
    }
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub enum RiskDecision {
    Approved(ApprovedTradeIntent),
    Rejected {
        decision_id: RiskDecisionId,
        reason: RiskRejectReason,
        snapshot_id: SnapshotId,
    },
}
