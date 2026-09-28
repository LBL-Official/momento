//! Fill-authoritative position. One [`PositionId`] per game.

use serde::{Deserialize, Serialize};

use crate::error::PositionError;
use crate::fee::FeeKind;
use crate::fill::Fill;
use crate::ids::{GameId, MarketId, PositionId, SnapshotId, StrategyId};
use crate::market::Side;
use crate::money::{Contracts, EconomicExposure, Money};
use crate::time::{ExchangeTimestamp, ReceivedAt};

/// Permanent game-level entry lock. Independent of position lifecycle.
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub enum GameLock {
    Unlocked,
    Locked {
        exchange_ts: ExchangeTimestamp,
        received_at: ReceivedAt,
    },
}

impl GameLock {
    pub const fn is_locked(&self) -> bool {
        matches!(self, Self::Locked { .. })
    }

    /// Idempotent. Cannot unlock.
    pub fn lock(&mut self, exchange_ts: ExchangeTimestamp, received_at: ReceivedAt) {
        if !self.is_locked() {
            *self = Self::Locked {
                exchange_ts,
                received_at,
            };
        }
    }
}

/// Temporary pause when price > max entry. Distinct from [`GameLock`].
#[derive(Clone, Copy, Debug, Default, PartialEq, Eq, Serialize, Deserialize)]
pub enum EntryPriceGate {
    #[default]
    Permitted,
    PausedAboveMaxPrice,
}

/// Position lifecycle. There is no take-profit variant.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub enum PositionLifecycle {
    Flat,
    Building,
    OpenPartial,
    OpenComplete,
    Holding,
    StopTriggered,
    LiquidationActive,
    SettlementPending,
    Settled,
}

impl PositionLifecycle {
    pub const fn is_flat(self) -> bool {
        matches!(self, Self::Flat)
    }

    pub const fn is_complete_open(self) -> bool {
        matches!(self, Self::OpenComplete)
    }
}

/// Allowed ways a position may exit. No take-profit. No discretionary exit.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub enum PositionExitCause {
    StopLoss,
    Settlement,
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct Position {
    id: PositionId,
    game_id: GameId,
    market_id: Option<MarketId>,
    side: Option<Side>,
    strategy_id: StrategyId,
    snapshot_id: SnapshotId,
    approved_economic_budget: Money,
    submitted_quantity: Contracts,
    working_quantity: Contracts,
    filled_quantity: Contracts,
    cancelled_quantity: Contracts,
    actual_exposure: EconomicExposure,
    entry_fees: Money,
    liquidation_fees: Money,
    fill_history: Vec<Fill>,
    game_lock: GameLock,
    entry_price_gate: EntryPriceGate,
    lifecycle: PositionLifecycle,
    entry_abandoned: bool,
    settlement_proceeds: Option<Money>,
}

impl Position {
    pub fn new_for_game(
        id: PositionId,
        game_id: GameId,
        strategy_id: StrategyId,
        snapshot_id: SnapshotId,
        approved_economic_budget: Money,
        market_id: Option<MarketId>,
        side: Option<Side>,
    ) -> Self {
        Self {
            id,
            game_id,
            market_id,
            side,
            strategy_id,
            snapshot_id,
            approved_economic_budget,
            submitted_quantity: Contracts::ZERO,
            working_quantity: Contracts::ZERO,
            filled_quantity: Contracts::ZERO,
            cancelled_quantity: Contracts::ZERO,
            actual_exposure: EconomicExposure::ZERO,
            entry_fees: Money::ZERO,
            liquidation_fees: Money::ZERO,
            fill_history: Vec::new(),
            game_lock: GameLock::Unlocked,
            entry_price_gate: EntryPriceGate::Permitted,
            lifecycle: PositionLifecycle::Building,
            entry_abandoned: false,
            settlement_proceeds: None,
        }
    }

    pub const fn id(&self) -> PositionId {
        self.id
    }

    pub const fn game_id(&self) -> GameId {
        self.game_id
    }

    pub const fn strategy_id(&self) -> StrategyId {
        self.strategy_id
    }

    pub const fn market_id(&self) -> Option<MarketId> {
        self.market_id
    }

    pub const fn side(&self) -> Option<Side> {
        self.side
    }

    /// Authoritative stop/liquidation identity is the market actually entered.
    ///
    /// `get_or_create` may first observe the opposite ticker under the same
    /// `GameId`. Unfilled identity may be overwritten by the approved entry.
    /// After fills exist, a different MarketId or side fails closed.
    pub fn bind_entry_identity(
        &mut self,
        market_id: MarketId,
        side: Side,
    ) -> Result<(), PositionError> {
        if self.filled_quantity.get() > 0 {
            match (self.market_id, self.side) {
                (Some(existing_market), Some(existing_side))
                    if existing_market != market_id || existing_side != side =>
                {
                    return Err(PositionError::FilledIdentityConflict);
                }
                _ => {}
            }
        }
        self.market_id = Some(market_id);
        self.side = Some(side);
        Ok(())
    }

    pub const fn snapshot_id(&self) -> SnapshotId {
        self.snapshot_id
    }

    /// Move an unfilled position onto a new weekly snapshot.
    ///
    /// Filled positions keep the snapshot they were opened under so last-week
    /// exposure is not rewritten. Resting working quantity is left unchanged so
    /// a second entry cannot be approved against a live prior-week order.
    /// Returns whether `snapshot_id` / budget were updated.
    pub fn rebind_unfilled_weekly_snapshot(
        &mut self,
        snapshot_id: SnapshotId,
        approved_economic_budget: Money,
    ) -> bool {
        if self.snapshot_id == snapshot_id {
            return false;
        }
        if self.filled_quantity.get() > 0 || self.working_quantity.get() > 0 {
            return false;
        }
        self.snapshot_id = snapshot_id;
        self.approved_economic_budget = approved_economic_budget;
        true
    }

    pub const fn approved_economic_budget(&self) -> Money {
        self.approved_economic_budget
    }

    pub const fn submitted_quantity(&self) -> Contracts {
        self.submitted_quantity
    }

    pub const fn working_quantity(&self) -> Contracts {
        self.working_quantity
    }

    pub const fn filled_quantity(&self) -> Contracts {
        self.filled_quantity
    }

    pub const fn cancelled_quantity(&self) -> Contracts {
        self.cancelled_quantity
    }

    pub const fn actual_exposure(&self) -> EconomicExposure {
        self.actual_exposure
    }

    pub const fn entry_fees(&self) -> Money {
        self.entry_fees
    }

    pub const fn liquidation_fees(&self) -> Money {
        self.liquidation_fees
    }

    pub fn fill_history(&self) -> &[Fill] {
        &self.fill_history
    }

    pub const fn game_lock(&self) -> &GameLock {
        &self.game_lock
    }

    pub const fn entry_price_gate(&self) -> EntryPriceGate {
        self.entry_price_gate
    }

    pub const fn lifecycle(&self) -> PositionLifecycle {
        self.lifecycle
    }

    pub const fn entry_abandoned(&self) -> bool {
        self.entry_abandoned
    }

    pub const fn settlement_proceeds(&self) -> Option<Money> {
        self.settlement_proceeds
    }

    /// Remaining economic target from actual fills + entry fees, never from submitted qty.
    pub fn remaining_economic_target(&self) -> Result<Money, PositionError> {
        let used = self
            .actual_exposure
            .as_money()
            .checked_add(self.entry_fees)
            .map_err(|_| PositionError::BudgetExceeded {
                budget: self.approved_economic_budget,
                used: self.actual_exposure.as_money(),
            })?;
        if used.cents() > self.approved_economic_budget.cents() {
            return Err(PositionError::BudgetExceeded {
                budget: self.approved_economic_budget,
                used,
            });
        }
        Ok(self.approved_economic_budget.saturating_sub(used))
    }

    /// After GAME_LOCKED the remainder is not actionable.
    pub fn actionable_remaining_entry(&self) -> Result<Money, PositionError> {
        if self.game_lock.is_locked() || self.entry_abandoned {
            return Ok(Money::ZERO);
        }
        self.remaining_economic_target()
    }

    pub fn can_attempt_entry(&self) -> bool {
        if self.game_lock.is_locked() || self.entry_abandoned {
            return false;
        }
        if self.entry_price_gate == EntryPriceGate::PausedAboveMaxPrice {
            return false;
        }
        !matches!(
            self.lifecycle,
            PositionLifecycle::StopTriggered
                | PositionLifecycle::LiquidationActive
                | PositionLifecycle::SettlementPending
                | PositionLifecycle::Settled
                | PositionLifecycle::Flat
                | PositionLifecycle::OpenComplete
                | PositionLifecycle::Holding
        )
    }

    pub fn record_submission(&mut self, qty: Contracts) -> Result<(), PositionError> {
        if self.lifecycle == PositionLifecycle::Settled {
            return Err(PositionError::SettledCannotReopen);
        }
        if !self.can_attempt_entry() {
            return Err(PositionError::EntryNotPermitted);
        }
        self.submitted_quantity = self.submitted_quantity.checked_add(qty).map_err(|_| {
            PositionError::BudgetExceeded {
                budget: self.approved_economic_budget,
                used: self.actual_exposure.as_money(),
            }
        })?;
        self.working_quantity =
            self.working_quantity
                .checked_add(qty)
                .map_err(|_| PositionError::BudgetExceeded {
                    budget: self.approved_economic_budget,
                    used: self.actual_exposure.as_money(),
                })?;
        Ok(())
    }

    pub fn record_working_cancelled(&mut self, qty: Contracts) -> Result<(), PositionError> {
        self.working_quantity = self
            .working_quantity
            .checked_sub(qty)
            .unwrap_or(Contracts::ZERO);
        self.cancelled_quantity = self
            .cancelled_quantity
            .checked_add(qty)
            .unwrap_or(self.cancelled_quantity);
        Ok(())
    }

    pub fn pause_entry_above_max_price(&mut self) {
        if !self.game_lock.is_locked() {
            self.entry_price_gate = EntryPriceGate::PausedAboveMaxPrice;
        }
    }

    /// Resume entry if price returned to the permitted range and the game is not locked.
    pub fn resume_entry_if_unlocked(&mut self) {
        if !self.game_lock.is_locked() {
            self.entry_price_gate = EntryPriceGate::Permitted;
        }
    }

    pub fn apply_game_lock(&mut self, exchange_ts: ExchangeTimestamp, received_at: ReceivedAt) {
        tracing::info!(
            position_id = self.id.raw(),
            game_id = self.game_id.raw(),
            "game_locked_entry_disabled"
        );
        self.game_lock.lock(exchange_ts, received_at);
        self.entry_abandoned = true;
        // Cancel working conceptually; caller must cancel venue orders.
        self.working_quantity = Contracts::ZERO;
        // Do not flatten. Do not change fills.
    }

    pub fn trigger_stop(&mut self) {
        if self.lifecycle != PositionLifecycle::Settled {
            self.lifecycle = PositionLifecycle::StopTriggered;
        }
    }

    pub fn begin_liquidation(&mut self) {
        if self.lifecycle != PositionLifecycle::Settled {
            self.lifecycle = PositionLifecycle::LiquidationActive;
        }
    }

    /// Lifecycle-only settlement marker. Prefer [`Self::apply_settlement`] when
    /// proceeds are known. Does not invent Kalshi settlement economics.
    pub fn settle(&mut self) {
        if self.lifecycle != PositionLifecycle::Settled {
            self.lifecycle = PositionLifecycle::Settled;
        }
    }

    pub fn enter_holding(&mut self) -> Result<(), PositionError> {
        if self.lifecycle == PositionLifecycle::Settled {
            return Err(PositionError::SettledCannotReopen);
        }
        if matches!(
            self.lifecycle,
            PositionLifecycle::OpenPartial | PositionLifecycle::OpenComplete
        ) {
            self.lifecycle = PositionLifecycle::Holding;
        }
        Ok(())
    }

    pub fn enter_settlement_pending(&mut self) -> Result<(), PositionError> {
        if self.lifecycle == PositionLifecycle::Settled {
            return Err(PositionError::SettledCannotReopen);
        }
        self.lifecycle = PositionLifecycle::SettlementPending;
        Ok(())
    }

    /// Authoritative settlement. Does not compute $1/contract or fees.
    pub fn apply_settlement(&mut self, proceeds: Money) -> Result<(), PositionError> {
        if self.lifecycle == PositionLifecycle::Settled && self.settlement_proceeds.is_some() {
            if self.settlement_proceeds != Some(proceeds) {
                return Err(PositionError::ConflictingEvent);
            }
            return Ok(());
        }
        if self.lifecycle == PositionLifecycle::Settled && self.settlement_proceeds.is_none() {
            self.settlement_proceeds = Some(proceeds);
            return Ok(());
        }
        self.settlement_proceeds = Some(proceeds);
        self.lifecycle = PositionLifecycle::Settled;
        Ok(())
    }

    pub fn apply_entry_fill(&mut self, fill: Fill) -> Result<(), PositionError> {
        if self.lifecycle == PositionLifecycle::Settled {
            return Err(PositionError::SettledCannotReopen);
        }
        if fill.position_id() != self.id {
            return Err(PositionError::EntryNotPermitted);
        }
        let new_exposure = self
            .actual_exposure
            .as_money()
            .checked_add(fill.premium())
            .map_err(|_| PositionError::BudgetExceeded {
                budget: self.approved_economic_budget,
                used: self.actual_exposure.as_money(),
            })?;
        let mut new_entry_fees = self.entry_fees;
        if fill.fee().kind() == FeeKind::Entry {
            new_entry_fees = new_entry_fees
                .checked_add(fill.fee().amount())
                .map_err(|_| PositionError::BudgetExceeded {
                    budget: self.approved_economic_budget,
                    used: new_exposure,
                })?;
        }
        let used = new_exposure.checked_add(new_entry_fees).map_err(|_| {
            PositionError::BudgetExceeded {
                budget: self.approved_economic_budget,
                used: new_exposure,
            }
        })?;
        if used.cents() > self.approved_economic_budget.cents() {
            return Err(PositionError::BudgetExceeded {
                budget: self.approved_economic_budget,
                used,
            });
        }

        self.actual_exposure = EconomicExposure::from_money(new_exposure);
        self.entry_fees = new_entry_fees;
        self.filled_quantity = self
            .filled_quantity
            .checked_add(fill.quantity())
            .map_err(|_| PositionError::BudgetExceeded {
                budget: self.approved_economic_budget,
                used,
            })?;
        let fill_qty = fill.quantity();
        self.working_quantity = self
            .working_quantity
            .checked_sub(fill_qty)
            .unwrap_or(Contracts::ZERO);
        self.fill_history.push(fill);

        self.refresh_lifecycle_after_entry();
        Ok(())
    }

    pub fn apply_liquidation_fill(&mut self, fill: Fill) -> Result<(), PositionError> {
        if self.lifecycle == PositionLifecycle::Settled {
            return Err(PositionError::SettledCannotReopen);
        }
        if fill.quantity().get() > self.filled_quantity.get() {
            return Err(PositionError::LiquidationExceedsOpen);
        }
        self.filled_quantity = self
            .filled_quantity
            .checked_sub(fill.quantity())
            .map_err(|_| PositionError::LiquidationExceedsOpen)?;
        if fill.fee().kind() == FeeKind::Liquidation {
            self.liquidation_fees = self
                .liquidation_fees
                .checked_add(fill.fee().amount())
                .map_err(|_| PositionError::BudgetExceeded {
                    budget: self.approved_economic_budget,
                    used: self.liquidation_fees,
                })?;
        }
        self.fill_history.push(fill);
        if self.filled_quantity == Contracts::ZERO {
            self.lifecycle = PositionLifecycle::Flat;
        } else {
            self.lifecycle = PositionLifecycle::LiquidationActive;
        }
        Ok(())
    }

    fn refresh_lifecycle_after_entry(&mut self) {
        if matches!(
            self.lifecycle,
            PositionLifecycle::StopTriggered
                | PositionLifecycle::LiquidationActive
                | PositionLifecycle::SettlementPending
                | PositionLifecycle::Settled
                | PositionLifecycle::Flat
                | PositionLifecycle::Holding
        ) {
            return;
        }
        let remaining = self
            .remaining_economic_target()
            .map(|m| m.cents())
            .unwrap_or(0);
        if remaining <= 0 && self.filled_quantity.get() > 0 {
            self.lifecycle = PositionLifecycle::OpenComplete;
        } else if self.filled_quantity.get() > 0 {
            self.lifecycle = PositionLifecycle::OpenPartial;
        } else {
            self.lifecycle = PositionLifecycle::Building;
        }
    }
}

#[cfg(test)]
mod bind_entry_identity_tests {
    use super::*;
    use crate::fee::{Fee, FeeKind};
    use crate::fill::Fill;
    use crate::ids::{ClientOrderId, FillId};
    use crate::money::{Contracts, Money, Price};
    use chrono::{TimeZone, Utc};

    fn pos(market: u128, side: Option<Side>) -> Position {
        Position::new_for_game(
            PositionId::from_raw(1),
            GameId::from_raw(10),
            StrategyId::from_raw(1),
            SnapshotId::from_raw(7),
            Money::from_usd(6, 25).unwrap(),
            Some(MarketId::from_raw(market)),
            side,
        )
    }

    fn fill(pos: &Position) -> Fill {
        let t = Utc
            .with_ymd_and_hms(2026, 8, 25, 18, 0, 0)
            .single()
            .unwrap();
        Fill::new(
            FillId::from_raw(1),
            pos.id(),
            ClientOrderId::from_raw(1),
            None,
            Contracts::from_u32(7),
            Price::from_cents(81).unwrap(),
            Money::from_cents(567),
            Fee::zero(FeeKind::Entry),
            ExchangeTimestamp::from_utc(t),
            ReceivedAt::from_utc(t),
        )
    }

    #[test]
    fn unfilled_opponent_stamp_is_overwritten_by_actual_entry_market() {
        let mut p = pos(302, Some(Side::Yes));
        p.bind_entry_identity(MarketId::from_raw(301), Side::Yes)
            .unwrap();
        assert_eq!(p.market_id(), Some(MarketId::from_raw(301)));
        assert_eq!(p.side(), Some(Side::Yes));
    }

    #[test]
    fn filled_position_rejects_opponent_rebind() {
        let mut p = pos(301, Some(Side::Yes));
        p.apply_entry_fill(fill(&p)).unwrap();
        let err = p
            .bind_entry_identity(MarketId::from_raw(302), Side::Yes)
            .unwrap_err();
        assert_eq!(err, PositionError::FilledIdentityConflict);
        assert_eq!(p.market_id(), Some(MarketId::from_raw(301)));
    }

    #[test]
    fn unfilled_position_rebinds_to_new_weekly_snapshot() {
        let mut p = pos(301, Some(Side::Yes));
        let next = SnapshotId::from_raw(99);
        let budget = Money::from_usd(6, 25).unwrap();
        assert!(p.rebind_unfilled_weekly_snapshot(next, budget));
        assert_eq!(p.snapshot_id(), next);
        assert_eq!(p.approved_economic_budget(), budget);
        assert!(!p.rebind_unfilled_weekly_snapshot(next, budget));
    }

    #[test]
    fn filled_position_keeps_prior_weekly_snapshot() {
        let mut p = pos(301, Some(Side::Yes));
        p.apply_entry_fill(fill(&p)).unwrap();
        let prior = p.snapshot_id();
        assert!(!p.rebind_unfilled_weekly_snapshot(
            SnapshotId::from_raw(99),
            Money::from_usd(6, 25).unwrap()
        ));
        assert_eq!(p.snapshot_id(), prior);
    }

    #[test]
    fn working_unfilled_position_keeps_prior_weekly_snapshot() {
        let mut p = pos(301, Some(Side::Yes));
        p.record_submission(Contracts::from_u32(7)).unwrap();
        let prior = p.snapshot_id();
        assert!(!p.rebind_unfilled_weekly_snapshot(
            SnapshotId::from_raw(99),
            Money::from_usd(6, 25).unwrap()
        ));
        assert_eq!(p.snapshot_id(), prior);
    }
}
