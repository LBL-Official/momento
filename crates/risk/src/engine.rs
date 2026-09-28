//! Single-process risk engine. Not an order router.

use std::collections::{HashMap, HashSet};
use std::sync::Mutex;

use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};

use momento_core::{
    AdditionalExposure, ApprovedTradeIntent, AuditEvent, AuditLog, AuditMeta, ClientOrderId, Fill,
    GameId, InMemoryAuditLog, KillSwitch, Money, PacificCalendarDay, Position, PositionId,
    PositionLifecycle, ReconcileOutcome, ReconciliationState, RiskDecision, RiskDecisionId,
    RiskGrant, RiskRejectReason, StrategyId, TradeIntent, WeeklyBankrollSnapshot,
    pacific_calendar_day, utc_now,
};

use crate::capacity::{AvailableCapacity, SnapshotPaperBalance};
use crate::config::RiskConfig;
use crate::fees::{FeeModel, ZeroFeeModel, size_entry};
use crate::reservation::{Reservation, ReservationBook};

struct Inner<F, C, A> {
    snapshot: Option<WeeklyBankrollSnapshot>,
    config: RiskConfig,
    fees: F,
    capacity: C,
    audit: A,
    kill_switch: KillSwitch,
    reservations: ReservationBook,
    game_locks: HashSet<u128>,
    recon_positions: HashSet<u128>,
    global_recon: bool,
    positions_by_game: HashMap<(u128, u128), PositionId>,
    /// Remaining fill-authoritative open contracts per PositionId.
    open_contracts: HashMap<u128, u32>,
    /// First-entry reservations that have not filled yet. Occupies a slot so
    /// concurrent approvals cannot open a sixth position. Released on cancel
    /// without a fill.
    pending_new_slots: HashSet<u128>,
    settled: HashSet<u128>,
    session: SessionLedger,
    clock_override: Option<DateTime<Utc>>,
}

/// Paper risk authority. Strategy cannot bypass this type.
pub struct PaperRiskEngine<F = ZeroFeeModel, C = SnapshotPaperBalance, A = InMemoryAuditLog> {
    inner: Mutex<Inner<F, C, A>>,
}

impl PaperRiskEngine<ZeroFeeModel, SnapshotPaperBalance, InMemoryAuditLog> {
    pub fn paper(snapshot: WeeklyBankrollSnapshot, config: RiskConfig) -> Self {
        let capacity = SnapshotPaperBalance::from_bankroll(snapshot.bankroll());
        Self {
            inner: Mutex::new(Inner {
                snapshot: Some(snapshot),
                config,
                fees: ZeroFeeModel,
                capacity,
                audit: InMemoryAuditLog::default(),
                kill_switch: KillSwitch::Armed,
                reservations: ReservationBook::default(),
                game_locks: HashSet::new(),
                recon_positions: HashSet::new(),
                global_recon: false,
                positions_by_game: HashMap::new(),
                open_contracts: HashMap::new(),
                pending_new_slots: HashSet::new(),
                settled: HashSet::new(),
                session: SessionLedger::default(),
                clock_override: None,
            }),
        }
    }

    pub fn restore(persist: RiskPersist, config: RiskConfig) -> Self {
        let capacity = SnapshotPaperBalance::from_bankroll(persist.snapshot.bankroll());
        let mut recon_positions = HashSet::new();
        for id in persist.recon_positions {
            recon_positions.insert(id);
        }
        let mut game_locks = HashSet::new();
        for id in persist.game_locks {
            game_locks.insert(id);
        }
        let mut positions_by_game = HashMap::new();
        for (strategy, game, pid) in persist.positions_by_game {
            positions_by_game.insert((strategy, game), PositionId::from_raw(pid));
        }
        let mut open_contracts = HashMap::new();
        for (pid, qty) in persist.open_contracts {
            if qty > 0 {
                open_contracts.insert(pid, qty);
            }
        }
        let mut pending_new_slots = HashSet::new();
        for id in persist.pending_new_slots {
            pending_new_slots.insert(id);
        }
        let mut settled = HashSet::new();
        for id in persist.settled {
            settled.insert(id);
        }
        Self {
            inner: Mutex::new(Inner {
                snapshot: Some(persist.snapshot),
                config,
                fees: ZeroFeeModel,
                capacity,
                audit: InMemoryAuditLog::default(),
                kill_switch: persist.kill_switch,
                reservations: ReservationBook::restore(persist.reservations),
                game_locks,
                recon_positions,
                global_recon: persist.global_recon,
                positions_by_game,
                open_contracts,
                pending_new_slots,
                settled,
                session: persist.session,
                clock_override: None,
            }),
        }
    }

    pub fn replace_weekly_snapshot(&self, snapshot: WeeklyBankrollSnapshot) {
        if let Ok(mut g) = self.inner.lock() {
            g.capacity = SnapshotPaperBalance::from_bankroll(snapshot.bankroll());
            g.snapshot = Some(snapshot);
        }
    }
}

impl<F: FeeModel, C: AvailableCapacity, A: AuditLog> PaperRiskEngine<F, C, A> {
    pub fn new(
        snapshot: WeeklyBankrollSnapshot,
        config: RiskConfig,
        fees: F,
        capacity: C,
        audit: A,
    ) -> Self {
        Self {
            inner: Mutex::new(Inner {
                snapshot: Some(snapshot),
                config,
                fees,
                capacity,
                audit,
                kill_switch: KillSwitch::Armed,
                reservations: ReservationBook::default(),
                game_locks: HashSet::new(),
                recon_positions: HashSet::new(),
                global_recon: false,
                positions_by_game: HashMap::new(),
                open_contracts: HashMap::new(),
                pending_new_slots: HashSet::new(),
                settled: HashSet::new(),
                session: SessionLedger::default(),
                clock_override: None,
            }),
        }
    }

    pub fn trip_kill_switch(&self) {
        if let Ok(mut g) = self.inner.lock() {
            g.kill_switch = KillSwitch::Tripped;
        }
    }

    pub fn lock_game(&self, game_id: GameId) {
        if let Ok(mut g) = self.inner.lock() {
            g.game_locks.insert(game_id.raw());
        }
    }

    pub fn require_reconciliation(&self, position_id: PositionId) {
        if let Ok(mut g) = self.inner.lock() {
            g.recon_positions.insert(position_id.raw());
        }
    }

    pub fn complete_reconciliation(&self, position_id: PositionId) {
        if let Ok(mut g) = self.inner.lock() {
            g.recon_positions.remove(&position_id.raw());
            g.global_recon = false;
        }
    }

    /// UNKNOWN: keep reservation, block new exposure.
    pub fn mark_unknown(&self, order: ClientOrderId, position_id: PositionId) {
        if let Ok(mut g) = self.inner.lock() {
            g.reservations.mark_unknown(order);
            g.recon_positions.insert(position_id.raw());
        }
    }

    pub fn reconcile_order(
        &self,
        order: ClientOrderId,
        position_id: PositionId,
        outcome: ReconcileOutcome,
    ) {
        if let Ok(mut g) = self.inner.lock() {
            match outcome {
                ReconcileOutcome::Found => {
                    g.reservations.clear_unknown(order);
                    if !g.reservations.has_unknown_for_position(position_id) {
                        g.recon_positions.remove(&position_id.raw());
                    }
                }
                ReconcileOutcome::NotFound => {
                    g.reservations.clear_unknown(order);
                    g.reservations.cancel(order);
                    if !g.reservations.has_unknown_for_position(position_id) {
                        g.recon_positions.remove(&position_id.raw());
                    }
                    g.release_pending_if_idle(position_id);
                }
                ReconcileOutcome::Ambiguous => {
                    g.reservations.mark_unknown(order);
                    g.recon_positions.insert(position_id.raw());
                }
            }
        }
    }

    pub fn on_fill(&self, fill: &Fill) {
        if let Ok(mut g) = self.inner.lock() {
            let fee = if fill.is_entry_fee() {
                fill.fee().amount()
            } else {
                Money::ZERO
            };
            let economic = fill.premium().checked_add(fee).unwrap_or(fill.premium());
            g.reservations.apply_fill(fill.client_order_id(), economic);
            g.apply_fill_to_open_slots(fill);
        }
    }

    pub fn on_settlement(&self, position_id: PositionId) {
        if let Ok(mut g) = self.inner.lock() {
            g.mark_settled(position_id);
        }
    }

    /// Record a confirmed close. `None` means settlement/P&L was unread.
    /// Win/loss limits fail closed while unread. Does not block liquidation.
    pub fn on_realized_close(&self, position_id: PositionId, realized: Option<Money>) {
        if let Ok(mut g) = self.inner.lock() {
            g.on_realized_close(position_id, realized);
        }
    }

    pub fn set_clock(&self, now: DateTime<Utc>) {
        if let Ok(mut g) = self.inner.lock() {
            g.clock_override = Some(now);
            g.roll_session_day();
        }
    }

    pub fn session_ledger(&self) -> SessionLedger {
        self.inner
            .lock()
            .map(|g| g.session.clone())
            .unwrap_or_default()
    }

    pub fn on_cancel(&self, order: ClientOrderId) -> bool {
        self.inner
            .lock()
            .map(|mut g| {
                let pid = g.reservations.position_id_for(order);
                let released = g.reservations.cancel(order);
                if let Some(pid) = pid {
                    g.release_pending_if_idle(pid);
                }
                released
            })
            .unwrap_or(false)
    }

    pub fn reserved_for(&self, position_id: PositionId) -> Money {
        self.inner
            .lock()
            .map(|g| g.reservations.reserved_for_position(position_id))
            .unwrap_or(Money::ZERO)
    }

    pub fn audit_events(&self) -> Vec<AuditEvent> {
        self.inner
            .lock()
            .map(|g| g.audit.events().to_vec())
            .unwrap_or_default()
    }

    /// Execution records lifecycle events on the same append-only log as Risk.
    pub fn append_audit(&self, event: AuditEvent) {
        if let Ok(mut g) = self.inner.lock() {
            g.audit.append(event);
        }
    }

    pub fn snapshot_id(&self) -> Option<momento_core::SnapshotId> {
        self.inner
            .lock()
            .ok()
            .and_then(|g| g.snapshot.as_ref().map(WeeklyBankrollSnapshot::snapshot_id))
    }

    pub fn kill_switch(&self) -> KillSwitch {
        self.inner
            .lock()
            .map(|g| g.kill_switch)
            .unwrap_or(KillSwitch::Tripped)
    }

    pub fn weekly_snapshot(&self) -> Option<WeeklyBankrollSnapshot> {
        self.inner.lock().ok().and_then(|g| g.snapshot.clone())
    }

    pub fn has_unknown_reservations(&self) -> bool {
        self.inner
            .lock()
            .map(|g| g.reservations.has_any_unknown())
            .unwrap_or(true)
    }

    pub fn persist_state(&self) -> Option<RiskPersist> {
        let g = self.inner.lock().ok()?;
        Some(RiskPersist {
            snapshot: g.snapshot.clone()?,
            kill_switch: g.kill_switch,
            reservations: g.reservations.snapshot(),
            game_locks: g.game_locks.iter().copied().collect(),
            recon_positions: g.recon_positions.iter().copied().collect(),
            global_recon: g.global_recon,
            positions_by_game: g
                .positions_by_game
                .iter()
                .map(|((s, game), pid)| (*s, *game, pid.raw()))
                .collect(),
            open_contracts: g
                .open_contracts
                .iter()
                .map(|(pid, qty)| (*pid, *qty))
                .collect(),
            pending_new_slots: g.pending_new_slots.iter().copied().collect(),
            settled: g.settled.iter().copied().collect(),
            session: g.session.clone(),
        })
    }

    pub fn open_slot_count(&self) -> u32 {
        self.inner
            .lock()
            .map(|g| g.open_slot_count())
            .unwrap_or(u32::MAX)
    }

    pub fn max_open_positions(&self) -> u32 {
        self.inner
            .lock()
            .map(|g| g.config.max_open_positions)
            .unwrap_or(0)
    }

    /// Rebuild occupancy from fill-authoritative positions. Pending unfilled
    /// first-entry reservations are preserved so concurrent approvals stay capped.
    pub fn adopt_fill_authoritative_occupancy<'a, I>(&self, positions: I)
    where
        I: IntoIterator<Item = &'a Position>,
    {
        if let Ok(mut g) = self.inner.lock() {
            g.adopt_fill_authoritative_occupancy(positions);
        }
    }

    /// Drop last-week known (not UNKNOWN) reservations and idle pending slots
    /// for positions rebound onto a new weekly snapshot.
    pub fn release_prior_week_unfilled_occupancy(&self, position_ids: &[PositionId]) {
        if let Ok(mut g) = self.inner.lock() {
            for &pid in position_ids {
                g.release_prior_week_unfilled_occupancy(pid);
            }
        }
    }

    /// Approve or reject ENTRY. Does not submit orders or mutate fills.
    pub fn decide_entry(&self, intent: &TradeIntent, position: &Position) -> RiskDecision {
        match self.inner.lock() {
            Ok(mut g) => g.decide_entry(intent, position),
            Err(_) => RiskDecision::Rejected {
                decision_id: RiskDecisionId::generate(),
                reason: RiskRejectReason::RiskStateUnknown,
                snapshot_id: position.snapshot_id(),
            },
        }
    }

    /// Approve reduce-only liquidation of existing fills. Does not create exposure.
    /// Kill switch does not block. UNKNOWN/AMBIGUOUS blocks until reconciled.
    pub fn approve_liquidation(
        &self,
        position: &Position,
    ) -> Result<(RiskDecisionId, ClientOrderId), RiskRejectReason> {
        match self.inner.lock() {
            Ok(mut g) => g.approve_liquidation(position),
            Err(_) => Err(RiskRejectReason::RiskStateUnknown),
        }
    }
}

impl<F: FeeModel, C: AvailableCapacity, A: AuditLog> Inner<F, C, A> {
    fn approve_liquidation(
        &mut self,
        position: &Position,
    ) -> Result<(RiskDecisionId, ClientOrderId), RiskRejectReason> {
        if self.global_recon || self.recon_positions.contains(&position.id().raw()) {
            return Err(RiskRejectReason::ReconciliationRequired);
        }
        if position.filled_quantity().get() == 0 {
            return Err(RiskRejectReason::InvalidQuantity);
        }
        if matches!(
            position.lifecycle(),
            PositionLifecycle::Settled | PositionLifecycle::Flat
        ) {
            return Err(RiskRejectReason::UnsupportedTradeType);
        }
        let decision_id = RiskDecisionId::generate();
        let client_order_id = ClientOrderId::generate();
        self.audit.append(AuditEvent::LiquidationStarted {
            meta: AuditMeta::now(),
            position_id: position.id(),
        });
        Ok((decision_id, client_order_id))
    }

    fn decide_entry(&mut self, intent: &TradeIntent, position: &Position) -> RiskDecision {
        let decision_id = RiskDecisionId::generate();
        let build = &intent.build;

        let Some(snapshot) = self.snapshot.clone() else {
            return self.reject(
                RejectCtx {
                    decision_id,
                    snapshot_id: momento_core::SnapshotId::from_raw(0),
                    game_id: build.game_id,
                    position_id: Some(position.id()),
                    reason: RiskRejectReason::WeeklySnapshotMissing,
                    requested: Money::ZERO,
                },
                position,
            );
        };
        let snapshot_id = snapshot.snapshot_id();
        let Some(allocation) = self.config.allocation_for(build.strategy_id) else {
            return self.reject(
                RejectCtx {
                    decision_id,
                    snapshot_id,
                    game_id: build.game_id,
                    position_id: Some(position.id()),
                    reason: RiskRejectReason::UnsupportedTradeType,
                    requested: Money::ZERO,
                },
                position,
            );
        };
        self.roll_session_day();
        let original_budget = if build.strategy_id == StrategyId::MLB
            || build.strategy_id == StrategyId::RESEARCH_ITI
        {
            snapshot.max_position_budget()
        } else {
            match snapshot.bankroll().checked_mul_bps(allocation) {
                Ok(m) => m,
                Err(_) => {
                    return self.reject(
                        RejectCtx {
                            decision_id,
                            snapshot_id,
                            game_id: build.game_id,
                            position_id: Some(position.id()),
                            reason: RiskRejectReason::InsufficientAvailableCapacity,
                            requested: Money::ZERO,
                        },
                        position,
                    );
                }
            }
        };

        let reject = |this: &mut Self, reason, requested: Money| {
            this.reject(
                RejectCtx {
                    decision_id,
                    snapshot_id,
                    game_id: build.game_id,
                    position_id: Some(position.id()),
                    reason,
                    requested,
                },
                position,
            )
        };

        if position.snapshot_id() != snapshot_id {
            return reject(self, RiskRejectReason::SnapshotMismatch, Money::ZERO);
        }
        if build.game_id != position.game_id() || build.position_id != position.id() {
            return reject(self, RiskRejectReason::DuplicateGamePosition, Money::ZERO);
        }

        let key = (build.strategy_id.raw(), build.game_id.raw());
        if let Some(existing) = self.positions_by_game.get(&key) {
            if *existing != position.id() {
                return reject(self, RiskRejectReason::DuplicateGamePosition, Money::ZERO);
            }
        }

        if self.kill_switch.is_tripped() {
            return reject(self, RiskRejectReason::KillSwitchActive, Money::ZERO);
        }

        let recon = self.global_recon
            || self.reservations.has_any_unknown()
            || !self.recon_positions.is_empty();
        if recon {
            return reject(self, RiskRejectReason::ReconciliationRequired, Money::ZERO);
        }

        if self.game_locks.contains(&build.game_id.raw()) || position.game_lock().is_locked() {
            return reject(self, RiskRejectReason::GameLocked, Money::ZERO);
        }

        if position.entry_price_gate() == momento_core::EntryPriceGate::PausedAboveMaxPrice {
            return reject(
                self,
                RiskRejectReason::EntryPausedAboveMaxPrice,
                Money::ZERO,
            );
        }

        if !position.can_attempt_entry() {
            return reject(self, RiskRejectReason::GameLocked, Money::ZERO);
        }

        if build.limit_price > self.config.max_entry_price {
            return reject(self, RiskRejectReason::EntryPriceAboveMaximum, Money::ZERO);
        }
        if build.limit_price < self.config.min_entry_price {
            return reject(self, RiskRejectReason::InvalidPrice, Money::ZERO);
        }

        let actual = match position
            .actual_exposure()
            .as_money()
            .checked_add(position.entry_fees())
        {
            Ok(m) => m,
            Err(_) => return reject(self, RiskRejectReason::PositionLimitExceeded, Money::ZERO),
        };
        let reserved = self.reservations.reserved_for_position(position.id());
        let remaining = original_budget
            .saturating_sub(actual)
            .saturating_sub(reserved);

        let requested = match build.additional {
            AdditionalExposure::RemainderOfApprovedBudget => remaining,
            AdditionalExposure::NotMoreThan(cap) => {
                if cap.cents() < remaining.cents() {
                    cap
                } else {
                    remaining
                }
            }
        };

        if requested.cents() <= 0 {
            return reject(self, RiskRejectReason::IncrementalBudgetExceeded, requested);
        }

        let (qty, premium, fee) = match size_entry(requested, build.limit_price, &self.fees) {
            Ok(v) => v,
            Err(_) => return reject(self, RiskRejectReason::InvalidQuantity, requested),
        };
        if qty.get() == 0 {
            return reject(self, RiskRejectReason::InvalidQuantity, requested);
        }

        let economic = match premium.checked_add(fee) {
            Ok(m) => m,
            Err(_) => return reject(self, RiskRejectReason::InvalidQuantity, requested),
        };

        if actual
            .checked_add(reserved)
            .and_then(|u| u.checked_add(economic))
            .map(|u| u.cents() > original_budget.cents())
            .unwrap_or(true)
        {
            return reject(self, RiskRejectReason::IncrementalBudgetExceeded, requested);
        }

        if economic.cents() > self.capacity.available().cents() {
            return reject(
                self,
                RiskRejectReason::InsufficientAvailableCapacity,
                requested,
            );
        }

        self.sync_from_position(position);
        let opening_new_slot = self.would_open_new_slot(position);
        if opening_new_slot {
            if let Some(reason) = self.session_entry_blocked() {
                return reject(self, reason, requested);
            }
            if self.reservations.has_any_unknown()
                || self.global_recon
                || !self.recon_positions.is_empty()
            {
                return reject(self, RiskRejectReason::ReconciliationRequired, requested);
            }
            if self.open_slot_count() >= self.config.max_open_positions {
                return reject(self, RiskRejectReason::PositionLimitExceeded, requested);
            }
        }

        if let Some(max_games) = self.config.max_concurrent_games {
            let mut games: HashSet<u128> = self.positions_by_game.keys().map(|k| k.1).collect();
            games.insert(build.game_id.raw());
            if u32::try_from(games.len()).unwrap_or(u32::MAX) > max_games {
                return reject(self, RiskRejectReason::PositionLimitExceeded, requested);
            }
        }

        let remaining_after = original_budget
            .saturating_sub(actual)
            .saturating_sub(reserved)
            .saturating_sub(economic);

        let client_order_id = ClientOrderId::generate();
        self.reservations.insert(Reservation {
            client_order_id,
            position_id: position.id(),
            game_id: build.game_id,
            remaining: economic,
            unknown: false,
        });
        self.positions_by_game.insert(key, position.id());
        if opening_new_slot {
            self.pending_new_slots.insert(position.id().raw());
            self.session.record_entry(position.id().raw());
        }

        let approved = ApprovedTradeIntent::from_risk_engine(
            RiskGrant::for_risk_engine(),
            decision_id,
            snapshot_id,
            intent,
            client_order_id,
            qty,
            requested,
            economic,
            original_budget,
            remaining_after,
            fee,
            self.fees.model_id(),
        );

        self.audit.append(AuditEvent::RiskApproval {
            meta: AuditMeta::now(),
            intent: approved.clone(),
            requested_exposure: requested,
            approved_exposure: economic,
            actual_exposure: actual,
            reserved_exposure: reserved.checked_add(economic).unwrap_or(reserved),
            remaining_capacity: remaining_after,
            fee_estimate: fee,
            fee_model_id: self.fees.model_id(),
        });

        RiskDecision::Approved(approved)
    }

    fn reject(&mut self, ctx: RejectCtx, position: &Position) -> RiskDecision {
        let actual = position
            .actual_exposure()
            .as_money()
            .checked_add(position.entry_fees())
            .unwrap_or(position.actual_exposure().as_money());
        let reserved = ctx
            .position_id
            .map(|id| self.reservations.reserved_for_position(id))
            .unwrap_or(Money::ZERO);
        let remaining = self
            .snapshot
            .as_ref()
            .map(WeeklyBankrollSnapshot::max_position_budget)
            .unwrap_or(Money::ZERO)
            .saturating_sub(actual)
            .saturating_sub(reserved);

        self.audit.append(AuditEvent::RiskRejection {
            meta: AuditMeta::now(),
            decision_id: ctx.decision_id,
            snapshot_id: ctx.snapshot_id,
            game_id: ctx.game_id,
            position_id: ctx.position_id,
            reason: ctx.reason,
            requested_exposure: ctx.requested,
            actual_exposure: actual,
            reserved_exposure: reserved,
            remaining_capacity: remaining,
            fee_estimate: Money::ZERO,
        });

        RiskDecision::Rejected {
            decision_id: ctx.decision_id,
            reason: ctx.reason,
            snapshot_id: ctx.snapshot_id,
        }
    }

    fn sync_from_position(&mut self, position: &Position) {
        let pid = position.id().raw();
        if position.lifecycle() == PositionLifecycle::Settled {
            self.mark_settled(position.id());
            return;
        }
        if position.lifecycle() == PositionLifecycle::Flat || position.filled_quantity().get() == 0
        {
            self.open_contracts.remove(&pid);
            if position.lifecycle() == PositionLifecycle::Flat {
                self.release_pending_if_idle(position.id());
            }
            return;
        }
        self.settled.remove(&pid);
        self.open_contracts
            .insert(pid, position.filled_quantity().get());
        self.pending_new_slots.remove(&pid);
    }

    fn would_open_new_slot(&self, position: &Position) -> bool {
        !self.occupies_slot(position.id())
    }

    fn occupies_slot(&self, position_id: PositionId) -> bool {
        let pid = position_id.raw();
        if self.settled.contains(&pid) {
            return false;
        }
        if self.open_contracts.get(&pid).copied().unwrap_or(0) > 0 {
            return true;
        }
        self.pending_new_slots.contains(&pid)
    }

    fn open_slot_count(&self) -> u32 {
        let mut ids: HashSet<u128> = HashSet::new();
        for (pid, qty) in &self.open_contracts {
            if *qty > 0 && !self.settled.contains(pid) {
                ids.insert(*pid);
            }
        }
        for pid in &self.pending_new_slots {
            if !self.settled.contains(pid) {
                ids.insert(*pid);
            }
        }
        u32::try_from(ids.len()).unwrap_or(u32::MAX)
    }

    fn apply_fill_to_open_slots(&mut self, fill: &Fill) {
        let pid = fill.position_id().raw();
        if fill.is_liquidation_fee() {
            let remaining = self
                .open_contracts
                .get(&pid)
                .copied()
                .unwrap_or(0)
                .saturating_sub(fill.quantity().get());
            if remaining == 0 {
                self.open_contracts.remove(&pid);
                self.release_pending_if_idle(fill.position_id());
            } else {
                self.open_contracts.insert(pid, remaining);
            }
            return;
        }
        let next = self
            .open_contracts
            .get(&pid)
            .copied()
            .unwrap_or(0)
            .saturating_add(fill.quantity().get());
        self.open_contracts.insert(pid, next);
        self.pending_new_slots.remove(&pid);
        self.settled.remove(&pid);
    }

    fn mark_settled(&mut self, position_id: PositionId) {
        let pid = position_id.raw();
        self.open_contracts.remove(&pid);
        self.pending_new_slots.remove(&pid);
        self.settled.insert(pid);
    }

    fn release_prior_week_unfilled_occupancy(&mut self, position_id: PositionId) {
        for order in self.reservations.known_order_ids_for_position(position_id) {
            self.reservations.cancel(order);
        }
        self.release_pending_if_idle(position_id);
    }

    fn release_pending_if_idle(&mut self, position_id: PositionId) {
        let pid = position_id.raw();
        let open = self.open_contracts.get(&pid).copied().unwrap_or(0);
        if open == 0 && !self.reservations.has_for_position(position_id) {
            self.pending_new_slots.remove(&pid);
        }
    }

    fn now(&self) -> DateTime<Utc> {
        self.clock_override.unwrap_or_else(utc_now)
    }

    fn roll_session_day(&mut self) {
        let today = pacific_calendar_day(self.now());
        if self.session.trading_day != Some(today) {
            self.session = SessionLedger {
                trading_day: Some(today),
                ..SessionLedger::default()
            };
        }
    }

    fn session_entry_blocked(&self) -> Option<RiskRejectReason> {
        if self.config.win_loss_limits_set() && !self.session.pnl_available {
            return Some(RiskRejectReason::SessionPnlUnavailable);
        }
        if let Some(max) = self.config.max_daily_entries {
            if self.session.entries_today >= max {
                return Some(RiskRejectReason::DailyTradeLimit);
            }
        }
        if let Some(max) = self.config.max_daily_wins {
            if self.session.wins >= max {
                return Some(RiskRejectReason::DailyWinCountLimit);
            }
        }
        if let Some(max) = self.config.max_daily_losses {
            if self.session.losses >= max {
                return Some(RiskRejectReason::DailyLossCountLimit);
            }
        }
        if let Some(max) = self.config.max_daily_win_cents {
            if self.session.realized_pnl_cents >= max.cents() {
                return Some(RiskRejectReason::DailyWinCentsLimit);
            }
        }
        if let Some(max) = self.config.max_daily_loss_cents {
            if self.session.realized_pnl_cents <= -max.cents() {
                return Some(RiskRejectReason::DailyLossCentsLimit);
            }
        }
        None
    }

    fn on_realized_close(&mut self, position_id: PositionId, realized: Option<Money>) {
        self.roll_session_day();
        match realized {
            None => {
                self.session.pnl_available = false;
            }
            Some(pnl) => {
                let pid = position_id.raw();
                if self.session.counted_closes.contains(&pid) {
                    return;
                }
                self.session.counted_closes.push(pid);
                self.session.pnl_available = true;
                self.session.realized_pnl_cents += pnl.cents();
                if pnl.cents() > 0 {
                    self.session.wins = self.session.wins.saturating_add(1);
                } else if pnl.cents() < 0 {
                    self.session.losses = self.session.losses.saturating_add(1);
                }
            }
        }
    }

    fn adopt_fill_authoritative_occupancy<'a, I>(&mut self, positions: I)
    where
        I: IntoIterator<Item = &'a Position>,
    {
        self.open_contracts.clear();
        self.settled.clear();
        for position in positions {
            let pid = position.id().raw();
            if position.lifecycle() == PositionLifecycle::Settled {
                self.pending_new_slots.remove(&pid);
                self.settled.insert(pid);
                // Known leftover reservations on a Settled game are not live
                // exposure. UNKNOWN reservations stay until reconcile.
                let orders = self
                    .reservations
                    .known_order_ids_for_position(position.id());
                for order in orders {
                    self.reservations.cancel(order);
                }
                continue;
            }
            let qty = position.filled_quantity().get();
            if qty > 0 {
                self.open_contracts.insert(pid, qty);
                self.pending_new_slots.remove(&pid);
            }
        }
    }
}

struct RejectCtx {
    decision_id: RiskDecisionId,
    snapshot_id: momento_core::SnapshotId,
    game_id: GameId,
    position_id: Option<PositionId>,
    reason: RiskRejectReason,
    requested: Money,
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct SessionLedger {
    #[serde(default)]
    pub trading_day: Option<PacificCalendarDay>,
    #[serde(default)]
    pub entries_today: u32,
    #[serde(default)]
    pub wins: u32,
    #[serde(default)]
    pub losses: u32,
    #[serde(default)]
    pub realized_pnl_cents: i64,
    #[serde(default = "default_pnl_available")]
    pub pnl_available: bool,
    #[serde(default)]
    pub counted_entries: Vec<u128>,
    #[serde(default)]
    pub counted_closes: Vec<u128>,
}

fn default_pnl_available() -> bool {
    true
}

impl SessionLedger {
    fn record_entry(&mut self, position_id: u128) {
        if self.counted_entries.contains(&position_id) {
            return;
        }
        self.counted_entries.push(position_id);
        self.entries_today = self.entries_today.saturating_add(1);
    }
}

impl Default for SessionLedger {
    fn default() -> Self {
        Self {
            trading_day: None,
            entries_today: 0,
            wins: 0,
            losses: 0,
            realized_pnl_cents: 0,
            pnl_available: true,
            counted_entries: Vec::new(),
            counted_closes: Vec::new(),
        }
    }
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct RiskPersist {
    pub snapshot: WeeklyBankrollSnapshot,
    pub kill_switch: KillSwitch,
    pub reservations: Vec<Reservation>,
    pub game_locks: Vec<u128>,
    pub recon_positions: Vec<u128>,
    pub global_recon: bool,
    pub positions_by_game: Vec<(u128, u128, u128)>,
    #[serde(default)]
    pub open_contracts: Vec<(u128, u32)>,
    #[serde(default)]
    pub pending_new_slots: Vec<u128>,
    #[serde(default)]
    pub settled: Vec<u128>,
    #[serde(default)]
    pub session: SessionLedger,
}

impl crate::RiskEngine for PaperRiskEngine {
    fn evaluate_entry(
        &self,
        intent: &TradeIntent,
        position: &Position,
        snapshot: &WeeklyBankrollSnapshot,
        recon: ReconciliationState,
        kill_switch: KillSwitch,
    ) -> RiskDecision {
        if recon.blocks_new_exposure() {
            self.require_reconciliation(position.id());
        }
        if kill_switch.is_tripped() {
            self.trip_kill_switch();
        }
        if let Ok(mut g) = self.inner.lock() {
            if g.snapshot.as_ref().map(WeeklyBankrollSnapshot::snapshot_id)
                != Some(snapshot.snapshot_id())
            {
                return g.reject(
                    RejectCtx {
                        decision_id: RiskDecisionId::generate(),
                        snapshot_id: snapshot.snapshot_id(),
                        game_id: intent.build.game_id,
                        position_id: Some(position.id()),
                        reason: RiskRejectReason::SnapshotMismatch,
                        requested: Money::ZERO,
                    },
                    position,
                );
            }
        }
        self.decide_entry(intent, position)
    }
}
