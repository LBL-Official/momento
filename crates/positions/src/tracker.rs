//! Fill-authoritative position tracker and typed reconciliation.

use std::collections::{HashMap, HashSet};

use serde::{Deserialize, Serialize};

use momento_core::{
    AuditEvent, AuditLog, AuditMeta, ClientOrderId, Contracts, Fill, FillId, GameId,
    InMemoryAuditLog, Money, Order, OrderPurpose, OrderState, Position, PositionId,
    PositionLifecycle, ReceivedAt, ReconcileOutcome, ReconciliationResult, ReconciliationState,
    SettlementEvent, Side, StateCorrectionKind, StrategyId, VenueOrderId, VenueOrderSnapshot,
    WeeklyBankrollSnapshot, error::PositionError,
};

use crate::error::TrackerError;
use crate::events::{ApplyStatus, PositionEvent};
use crate::identity::{GamePositionIndex, PositionIndexError};

pub trait PositionTracker {
    fn get(&self, id: PositionId) -> Option<&Position>;
    fn get_mut(&mut self, id: PositionId) -> Option<&mut Position>;
    fn apply_entry_fill(&mut self, fill: Fill) -> Result<(), PositionError>;
    fn reconciliation_state(&self) -> ReconciliationState;
}

#[derive(Clone, Debug)]
struct TrackedOrder {
    order: Order,
    cancel_requested: bool,
    unknown: bool,
}

/// Fill-authoritative in-memory tracker. Does not submit orders. Does not
/// create a second PositionId for an unfilled remainder.
#[derive(Clone, Debug)]
pub struct InMemoryPositionTracker {
    index: GamePositionIndex,
    positions: HashMap<u128, Position>,
    orders: HashMap<u128, TrackedOrder>,
    fills: HashMap<u128, Fill>,
    fills_by_order: HashMap<u128, Vec<u128>>,
    event_keys: HashSet<String>,
    unknown_orders: HashSet<u128>,
    recon: ReconciliationState,
    audit: InMemoryAuditLog,
}

impl Default for InMemoryPositionTracker {
    fn default() -> Self {
        Self::new()
    }
}

impl InMemoryPositionTracker {
    pub fn new() -> Self {
        Self {
            index: GamePositionIndex::new(),
            positions: HashMap::new(),
            orders: HashMap::new(),
            fills: HashMap::new(),
            fills_by_order: HashMap::new(),
            event_keys: HashSet::new(),
            unknown_orders: HashSet::new(),
            recon: ReconciliationState::Healthy,
            audit: InMemoryAuditLog::default(),
        }
    }

    pub fn index(&self) -> &GamePositionIndex {
        &self.index
    }

    pub fn audit_events(&self) -> &[AuditEvent] {
        self.audit.events()
    }

    pub fn id_for_game(&self, game: GameId) -> Option<PositionId> {
        self.positions
            .values()
            .find(|p| p.game_id() == game)
            .map(Position::id)
    }

    pub fn positions(&self) -> impl Iterator<Item = &Position> {
        self.positions.values()
    }

    pub fn order(&self, id: ClientOrderId) -> Option<&Order> {
        self.orders.get(&id.raw()).map(|t| &t.order)
    }

    pub fn order_by_venue_id(&self, venue_order_id: VenueOrderId) -> Option<&Order> {
        self.orders
            .values()
            .find(|t| t.order.venue_order_id() == Some(venue_order_id))
            .map(|t| &t.order)
    }

    pub fn unknown_order_ids(&self) -> impl Iterator<Item = ClientOrderId> + '_ {
        self.unknown_orders
            .iter()
            .copied()
            .map(ClientOrderId::from_raw)
    }

    pub fn can_open_new_exposure(&self) -> bool {
        !self.recon.blocks_new_exposure()
    }

    pub fn reconciliation_state(&self) -> ReconciliationState {
        self.recon
    }

    pub fn snapshot_persist(&self) -> TrackerPersist {
        TrackerPersist {
            positions: self.positions.values().cloned().collect(),
            orders: self
                .orders
                .values()
                .map(|t| PersistedOrder {
                    order: t.order.clone(),
                    cancel_requested: t.cancel_requested,
                    unknown: t.unknown,
                })
                .collect(),
            unknown: self.unknown_orders.iter().copied().collect(),
            recon: self.recon,
            index: self.index.entries(),
            event_keys: self.event_keys.iter().cloned().collect(),
        }
    }

    pub fn restore_persist(persist: TrackerPersist) -> Self {
        let mut t = Self::new();
        t.recon = persist.recon;
        t.event_keys = persist.event_keys.into_iter().collect();
        for (strategy, game, pid) in persist.index {
            let _ = t.index.register(
                StrategyId::from_raw(strategy),
                GameId::from_raw(game),
                PositionId::from_raw(pid),
            );
        }
        for pos in persist.positions {
            for fill in pos.fill_history() {
                t.fills.insert(fill.fill_id().raw(), fill.clone());
                t.fills_by_order
                    .entry(fill.client_order_id().raw())
                    .or_default()
                    .push(fill.fill_id().raw());
            }
            t.positions.insert(pos.id().raw(), pos);
        }
        for persisted in persist.orders {
            let unknown = persisted.unknown
                || persist
                    .unknown
                    .contains(&persisted.order.client_order_id().raw());
            if unknown {
                t.unknown_orders
                    .insert(persisted.order.client_order_id().raw());
            }
            t.orders.insert(
                persisted.order.client_order_id().raw(),
                TrackedOrder {
                    order: persisted.order,
                    cancel_requested: persisted.cancel_requested,
                    unknown,
                },
            );
        }
        t
    }

    pub fn entry_orders_for_game(&self, game: GameId) -> Vec<Order> {
        self.orders
            .values()
            .filter(|t| t.order.game_id() == game && t.order.purpose() == OrderPurpose::Entry)
            .map(|t| t.order.clone())
            .collect()
    }

    pub fn has_working_entry(&self, game: GameId) -> bool {
        self.entry_orders_for_game(game)
            .iter()
            .any(|o| !o.state().is_terminal() && o.state() != OrderState::Unknown)
    }

    pub fn has_unknown_entry(&self, game: GameId) -> bool {
        self.entry_orders_for_game(game)
            .iter()
            .any(|o| self.unknown_orders.contains(&o.client_order_id().raw()))
    }

    pub fn liquidation_orders_for_game(&self, game: GameId) -> Vec<Order> {
        self.orders
            .values()
            .filter(|t| t.order.game_id() == game && t.order.purpose() == OrderPurpose::Liquidation)
            .map(|t| t.order.clone())
            .collect()
    }

    pub fn has_working_liquidation(&self, game: GameId) -> bool {
        self.liquidation_orders_for_game(game)
            .iter()
            .any(|o| !o.state().is_terminal() && o.state() != OrderState::Unknown)
    }

    pub fn has_unknown_liquidation(&self, game: GameId) -> bool {
        self.liquidation_orders_for_game(game)
            .iter()
            .any(|o| self.unknown_orders.contains(&o.client_order_id().raw()))
    }

    fn liquidation_orders_for_position(&self, position: PositionId) -> Vec<Order> {
        self.orders
            .values()
            .filter(|t| {
                t.order.position_id() == position && t.order.purpose() == OrderPurpose::Liquidation
            })
            .map(|t| t.order.clone())
            .collect()
    }

    /// Duplicate-liquidation guard is position-scoped, not GameId-scoped.
    pub fn has_working_liquidation_for_position(&self, position: PositionId) -> bool {
        self.liquidation_orders_for_position(position)
            .iter()
            .any(|o| !o.state().is_terminal() && o.state() != OrderState::Unknown)
    }

    pub fn has_unknown_liquidation_for_position(&self, position: PositionId) -> bool {
        self.liquidation_orders_for_position(position)
            .iter()
            .any(|o| self.unknown_orders.contains(&o.client_order_id().raw()))
    }

    pub fn non_terminal_known_orders(&self) -> Vec<Order> {
        self.orders
            .values()
            .filter(|t| {
                !t.unknown
                    && !t.order.state().is_terminal()
                    && t.order.state() != OrderState::Unknown
                    && self
                        .positions
                        .get(&t.order.position_id().raw())
                        .is_some_and(|p| p.lifecycle() != PositionLifecycle::Settled)
            })
            .map(|t| t.order.clone())
            .collect()
    }

    fn has_live_uncertain_order(&self) -> bool {
        self.orders.values().any(|t| {
            if t.unknown || t.order.state() == OrderState::Unknown {
                return true;
            }
            if t.order.state().is_terminal() {
                return false;
            }
            match self.positions.get(&t.order.position_id().raw()) {
                Some(pos) => pos.lifecycle() != PositionLifecycle::Settled,
                None => true,
            }
        })
    }

    /// Ambiguous is sticky in persist. Clear it only when nothing live is
    /// unknown and the only leftover non-terminal orders sit on Settled
    /// positions (historical debris, not open exposure).
    pub fn release_ambiguous_if_no_live_uncertainty(&mut self) -> bool {
        if self.recon != ReconciliationState::Ambiguous {
            return false;
        }
        if self.has_unknown_orders() || self.has_live_uncertain_order() {
            return false;
        }
        self.complete_reconciliation();
        true
    }

    pub fn has_unknown_orders(&self) -> bool {
        !self.unknown_orders.is_empty()
    }

    pub fn get_or_create(
        &mut self,
        strategy: StrategyId,
        game: GameId,
        snapshot: &WeeklyBankrollSnapshot,
        market_id: Option<momento_core::MarketId>,
        side: Option<Side>,
    ) -> &mut Position {
        self.get_or_create_with_budget(
            strategy,
            game,
            snapshot,
            snapshot.max_position_budget(),
            market_id,
            side,
        )
    }

    pub fn get_or_create_with_budget(
        &mut self,
        strategy: StrategyId,
        game: GameId,
        snapshot: &WeeklyBankrollSnapshot,
        original_budget: Money,
        market_id: Option<momento_core::MarketId>,
        side: Option<Side>,
    ) -> &mut Position {
        let id = self.index.id_for(strategy, game);
        match self.positions.entry(id.raw()) {
            std::collections::hash_map::Entry::Vacant(slot) => {
                slot.insert(Position::new_for_game(
                    id,
                    game,
                    strategy,
                    snapshot.snapshot_id(),
                    original_budget,
                    market_id,
                    side,
                ));
            }
            std::collections::hash_map::Entry::Occupied(_) => {}
        }
        let can_rebind = self
            .positions
            .get(&id.raw())
            .is_some_and(Self::position_can_rebind_week)
            && !self.has_working_entry(game)
            && !self.has_unknown_entry(game);
        if can_rebind {
            if let Some(pos) = self.positions.get_mut(&id.raw()) {
                let _ =
                    pos.rebind_unfilled_weekly_snapshot(snapshot.snapshot_id(), original_budget);
            }
        }
        self.positions
            .get_mut(&id.raw())
            .expect("position inserted or already present")
    }

    fn position_can_rebind_week(pos: &Position) -> bool {
        pos.filled_quantity().get() == 0 && pos.working_quantity().get() == 0
    }

    /// Rebind unfilled, idle positions onto `snapshot`.
    ///
    /// Skips fills, resting working quantity, and games with a working or
    /// UNKNOWN entry order so week-roll cannot create duplicate exposure.
    pub fn rebind_unfilled_positions_to_snapshot(
        &mut self,
        snapshot: &WeeklyBankrollSnapshot,
        mut budget_for: impl FnMut(StrategyId) -> Money,
    ) -> Vec<PositionId> {
        let raw_ids: Vec<u128> = self.positions.keys().copied().collect();
        let mut rebound = Vec::new();
        for raw in raw_ids {
            let Some(pos) = self.positions.get(&raw) else {
                continue;
            };
            if !Self::position_can_rebind_week(pos) {
                continue;
            }
            let game = pos.game_id();
            if self.has_working_entry(game) || self.has_unknown_entry(game) {
                continue;
            }
            let budget = budget_for(pos.strategy_id());
            if let Some(pos) = self.positions.get_mut(&raw) {
                if pos.rebind_unfilled_weekly_snapshot(snapshot.snapshot_id(), budget) {
                    rebound.push(pos.id());
                }
            }
        }
        rebound
    }

    /// Rejects an attempt to attach a different PositionId to an existing game.
    pub fn register_position_identity(
        &mut self,
        strategy: StrategyId,
        game: GameId,
        id: PositionId,
    ) -> Result<(), TrackerError> {
        match self.index.register(strategy, game, id) {
            Ok(()) => Ok(()),
            Err(PositionIndexError::ConflictingPositionId) => {
                let existing = self.index.get(strategy, game).unwrap_or(id);
                Err(TrackerError::SecondPositionForGame {
                    game,
                    existing,
                    attempted: id,
                })
            }
        }
    }

    pub fn require_reconciliation(&mut self) {
        if self.recon != ReconciliationState::Ambiguous {
            self.recon = ReconciliationState::Required;
        }
    }

    pub fn start_reconciliation(&mut self, client_order_id: ClientOrderId) {
        self.recon = ReconciliationState::Reconciling;
        if let Some(tracked) = self.orders.get(&client_order_id.raw()) {
            self.audit.append(AuditEvent::ReconciliationStarted {
                meta: AuditMeta::now(),
                client_order_id,
                position_id: tracked.order.position_id(),
            });
        }
    }

    pub fn mark_ambiguous(&mut self) {
        self.recon = ReconciliationState::Ambiguous;
    }

    pub fn complete_reconciliation(&mut self) {
        if self.unknown_orders.is_empty() {
            self.recon = ReconciliationState::Healthy;
        }
    }

    pub fn apply_event(&mut self, event: PositionEvent) -> Result<ApplyStatus, TrackerError> {
        match event {
            PositionEvent::OrderSubmitted { order } => self.on_submitted(order),
            PositionEvent::OrderWorking {
                client_order_id,
                venue_order_id,
            } => self.on_working(client_order_id, venue_order_id),
            PositionEvent::PartialFill { fill } | PositionEvent::FullFill { fill } => {
                self.apply_fill_event(fill, false)
            }
            PositionEvent::LiquidationFill { fill } => self.apply_fill_event(fill, true),
            PositionEvent::CancelRequested { client_order_id } => {
                self.on_cancel_requested(client_order_id)
            }
            PositionEvent::Cancelled { client_order_id } => self.on_cancelled(client_order_id),
            PositionEvent::Rejected { client_order_id } => self.on_rejected(client_order_id),
            PositionEvent::Expired { client_order_id } => self.on_expired(client_order_id),
            PositionEvent::Unknown { client_order_id } => self.on_unknown(client_order_id),
            PositionEvent::GameLocked {
                game_id,
                exchange_ts,
                received_at,
            } => {
                self.lock_game(game_id, exchange_ts, received_at)?;
                Ok(ApplyStatus::Applied)
            }
            PositionEvent::Settlement(event) => {
                self.apply_settlement(event)?;
                Ok(ApplyStatus::Applied)
            }
        }
    }

    pub fn lock_game(
        &mut self,
        game_id: GameId,
        exchange_ts: momento_core::ExchangeTimestamp,
        received_at: ReceivedAt,
    ) -> Result<(), TrackerError> {
        let Some(position_id) = self.id_for_game(game_id) else {
            return Ok(());
        };
        let pos = self
            .positions
            .get_mut(&position_id.raw())
            .ok_or(TrackerError::MissingPosition(position_id))?;
        pos.apply_game_lock(exchange_ts, received_at);
        self.audit.append(AuditEvent::GameLocked {
            meta: AuditMeta::now(),
            game_id,
            position_id,
            exchange_ts,
            received_at,
        });
        Ok(())
    }

    pub fn apply_settlement(&mut self, event: SettlementEvent) -> Result<(), TrackerError> {
        let pos = self
            .positions
            .get_mut(&event.position_id.raw())
            .ok_or(TrackerError::MissingPosition(event.position_id))?;
        if pos.game_id() != event.game_id {
            return Err(TrackerError::ConflictingEvent);
        }
        pos.enter_settlement_pending()?;
        pos.apply_settlement(event.proceeds)?;
        self.audit.append(AuditEvent::Settlement {
            meta: AuditMeta::now(),
            position_id: event.position_id,
            settlement_value: event.proceeds,
        });
        Ok(())
    }

    /// Typed reconciliation. Does not retry. Does not invent fills.
    pub fn reconcile(
        &mut self,
        client_order_id: ClientOrderId,
        snapshot: VenueOrderSnapshot,
        received_at: ReceivedAt,
    ) -> Result<ReconciliationResult, TrackerError> {
        self.start_reconciliation(client_order_id);
        let tracked = self
            .orders
            .get(&client_order_id.raw())
            .ok_or(TrackerError::MissingOrder(client_order_id))?;
        let position_id = tracked.order.position_id();
        let game_id = tracked.order.game_id();
        let local_status = tracked.order.state();
        let local_price = Some(tracked.order.price());
        let local_filled = self.filled_for_order(client_order_id);
        let local_fees = self.fees_for_order(client_order_id);

        self.audit.append(AuditEvent::ReconciliationRequested {
            meta: AuditMeta::now(),
            client_order_id,
            position_id,
            game_id,
        });

        let outcome = self.decide_outcome(client_order_id, local_filled, &snapshot)?;

        let result = ReconciliationResult {
            client_order_id,
            venue_order_id: snapshot.venue_order_id.or_else(|| {
                self.orders
                    .get(&client_order_id.raw())
                    .and_then(|t| t.order.venue_order_id())
            }),
            position_id,
            game_id,
            local_status,
            venue_status: snapshot.venue_status,
            local_filled,
            venue_filled: snapshot.venue_filled,
            local_price,
            venue_fill_prices: snapshot.venue_fill_prices.clone(),
            local_fees,
            venue_fees: snapshot.venue_fees,
            exchange_ts: snapshot.exchange_ts,
            received_at,
            authoritative: snapshot.authoritative
                && matches!(
                    outcome,
                    ReconcileOutcome::Found | ReconcileOutcome::NotFound
                ),
            outcome,
        };

        self.apply_outcome(client_order_id, &snapshot, &result)?;
        self.emit_outcome_audit(&result);
        self.audit.append(AuditEvent::ReconciliationCompleted {
            meta: AuditMeta::now(),
            client_order_id,
            outcome,
        });
        Ok(result)
    }

    fn decide_outcome(
        &self,
        client_order_id: ClientOrderId,
        local_filled: Contracts,
        snapshot: &VenueOrderSnapshot,
    ) -> Result<ReconcileOutcome, TrackerError> {
        if snapshot.contradictory || snapshot.insufficient {
            return Ok(ReconcileOutcome::Ambiguous);
        }
        match snapshot.presence {
            momento_core::OrderPresence::Unknown => Ok(ReconcileOutcome::Ambiguous),
            momento_core::OrderPresence::NotFound => {
                if local_filled.get() > 0 {
                    Ok(ReconcileOutcome::Ambiguous)
                } else {
                    Ok(ReconcileOutcome::NotFound)
                }
            }
            momento_core::OrderPresence::Found => {
                if let Some(venue_filled) = snapshot.venue_filled {
                    if venue_filled.get() != local_filled.get() {
                        let incoming: u32 = snapshot
                            .fills
                            .iter()
                            .filter(|f| !self.fills.contains_key(&f.fill_id().raw()))
                            .map(|f| f.quantity().get())
                            .sum();
                        let explained = local_filled.get().saturating_add(incoming);
                        if explained != venue_filled.get() {
                            return Ok(ReconcileOutcome::Ambiguous);
                        }
                    }
                }
                if let Some(venue_id) = snapshot.venue_order_id {
                    if let Some(local_id) = self
                        .orders
                        .get(&client_order_id.raw())
                        .and_then(|t| t.order.venue_order_id())
                    {
                        if local_id != venue_id {
                            return Ok(ReconcileOutcome::Ambiguous);
                        }
                    }
                }
                Ok(ReconcileOutcome::Found)
            }
        }
    }

    fn apply_outcome(
        &mut self,
        client_order_id: ClientOrderId,
        snapshot: &VenueOrderSnapshot,
        result: &ReconciliationResult,
    ) -> Result<(), TrackerError> {
        match result.outcome {
            ReconcileOutcome::Ambiguous => {
                self.recon = ReconciliationState::Ambiguous;
                if let Some(t) = self.orders.get_mut(&client_order_id.raw()) {
                    t.order.mark_unknown();
                    t.unknown = true;
                }
                self.unknown_orders.insert(client_order_id.raw());
                self.audit.append(AuditEvent::ConflictingEventDetected {
                    meta: AuditMeta::now(),
                    position_id: result.position_id,
                    client_order_id,
                    local_status: result.local_status,
                    venue_status: result.venue_status,
                });
            }
            ReconcileOutcome::NotFound => {
                if let Some(t) = self.orders.get_mut(&client_order_id.raw()) {
                    let remaining = t.order.quantities().remaining;
                    let _ = t.order.mark_rejected();
                    t.unknown = false;
                    if remaining.get() > 0 {
                        if let Some(pos) = self.positions.get_mut(&result.position_id.raw()) {
                            let _ = pos.record_working_cancelled(remaining);
                        }
                    }
                }
                self.unknown_orders.remove(&client_order_id.raw());
                self.audit.append(AuditEvent::StateCorrection {
                    meta: AuditMeta::now(),
                    position_id: result.position_id,
                    client_order_id: Some(client_order_id),
                    kind: StateCorrectionKind::OrderMarkedNotFound,
                });
                self.rebuild_recon_gate();
            }
            ReconcileOutcome::Found => {
                if let Some(venue_id) = snapshot.venue_order_id {
                    if let Some(t) = self.orders.get_mut(&client_order_id.raw()) {
                        if t.order.state() == OrderState::Unknown
                            || t.order.venue_order_id().is_none()
                        {
                            t.order.recover_from_unknown(venue_id);
                            t.unknown = false;
                            self.audit.append(AuditEvent::OrderRebuilt {
                                meta: AuditMeta::now(),
                                client_order_id,
                                venue_order_id: Some(venue_id),
                                state: t.order.state(),
                            });
                        }
                    }
                }
                let fills = snapshot.fills.clone();
                for fill in fills {
                    let _ = self.apply_fill_event(fill, false)?;
                }
                self.unknown_orders.remove(&client_order_id.raw());
                self.rebuild_recon_gate();
                let pos = self.positions.get(&result.position_id.raw());
                if let Some(pos) = pos {
                    self.audit.append(AuditEvent::PositionRebuilt {
                        meta: AuditMeta::now(),
                        position_id: result.position_id,
                        game_id: result.game_id,
                        filled_quantity: pos.filled_quantity(),
                    });
                }
            }
        }
        Ok(())
    }

    fn emit_outcome_audit(&mut self, result: &ReconciliationResult) {
        let meta = AuditMeta::now();
        match result.outcome {
            ReconcileOutcome::Found => self.audit.append(AuditEvent::ReconciliationFound {
                meta,
                result: result.clone(),
            }),
            ReconcileOutcome::NotFound => self.audit.append(AuditEvent::ReconciliationNotFound {
                meta,
                result: result.clone(),
            }),
            ReconcileOutcome::Ambiguous => self.audit.append(AuditEvent::ReconciliationAmbiguous {
                meta,
                result: result.clone(),
            }),
        }
    }

    fn rebuild_recon_gate(&mut self) {
        if self.unknown_orders.is_empty() {
            self.recon = ReconciliationState::Healthy;
        } else if self.recon != ReconciliationState::Ambiguous {
            self.recon = ReconciliationState::Required;
        }
    }

    fn on_submitted(&mut self, order: Order) -> Result<ApplyStatus, TrackerError> {
        let key = format!("submitted:{}", order.client_order_id().raw());
        if self.event_keys.contains(&key) {
            self.audit_duplicate(None, Some(order.client_order_id()), None);
            return Ok(ApplyStatus::DuplicateIgnored);
        }
        if self.recon.blocks_new_exposure() {
            return Err(TrackerError::NewExposureBlocked(self.recon));
        }
        let pos = self
            .positions
            .get(&order.position_id().raw())
            .ok_or(TrackerError::MissingPosition(order.position_id()))?;
        if pos.game_id() != order.game_id() {
            return Err(TrackerError::ConflictingEvent);
        }
        if pos.lifecycle() == momento_core::PositionLifecycle::Settled {
            return Err(TrackerError::SettledCannotReopen);
        }
        let strategy_id = pos.strategy_id();
        let game_id = order.game_id();
        let position_id = order.position_id();
        let requested = order.quantities().requested;
        let is_entry = order.purpose() == momento_core::OrderPurpose::Entry;
        let can_enter = pos.can_attempt_entry();
        self.register_position_identity(strategy_id, game_id, position_id)?;
        if !can_enter && is_entry {
            return Err(TrackerError::Position(PositionError::EntryNotPermitted));
        }
        if is_entry {
            self.positions
                .get_mut(&position_id.raw())
                .ok_or(TrackerError::MissingPosition(position_id))?
                .record_submission(requested)?;
        }
        let id = order.client_order_id();
        self.orders.insert(
            id.raw(),
            TrackedOrder {
                order,
                cancel_requested: false,
                unknown: false,
            },
        );
        self.event_keys.insert(format!("submitted:{}", id.raw()));
        self.audit.append(AuditEvent::OrderSubmitted {
            meta: AuditMeta::now(),
            client_order_id: id,
            position_id,
            game_id,
        });
        Ok(ApplyStatus::Applied)
    }

    fn on_working(
        &mut self,
        client_order_id: ClientOrderId,
        venue_order_id: VenueOrderId,
    ) -> Result<ApplyStatus, TrackerError> {
        let key = format!("working:{}:{}", client_order_id.raw(), venue_order_id.raw());
        if !self.event_keys.insert(key) {
            self.audit_duplicate(None, Some(client_order_id), Some(venue_order_id));
            return Ok(ApplyStatus::DuplicateIgnored);
        }
        let tracked = self
            .orders
            .get_mut(&client_order_id.raw())
            .ok_or(TrackerError::MissingOrder(client_order_id))?;
        if tracked.unknown {
            return Err(TrackerError::Position(
                PositionError::ReconciliationRequired,
            ));
        }
        tracked.order.attach_venue_id(venue_order_id);
        if tracked.order.state() == OrderState::New {
            tracked.order.mark_submitting()?;
            tracked.order.mark_ack(venue_order_id)?;
        }
        self.audit.append(AuditEvent::OrderWorking {
            meta: AuditMeta::now(),
            client_order_id,
        });
        Ok(ApplyStatus::Applied)
    }

    fn on_cancel_requested(
        &mut self,
        client_order_id: ClientOrderId,
    ) -> Result<ApplyStatus, TrackerError> {
        let key = format!("cancel_req:{}", client_order_id.raw());
        if !self.event_keys.insert(key) {
            self.audit_duplicate(None, Some(client_order_id), None);
            return Ok(ApplyStatus::DuplicateIgnored);
        }
        let tracked = self
            .orders
            .get_mut(&client_order_id.raw())
            .ok_or(TrackerError::MissingOrder(client_order_id))?;
        if tracked.unknown {
            return Err(TrackerError::Position(
                PositionError::ReconciliationRequired,
            ));
        }
        tracked.cancel_requested = true;
        let _ = tracked.order.mark_cancel_pending();
        Ok(ApplyStatus::Applied)
    }

    fn on_cancelled(
        &mut self,
        client_order_id: ClientOrderId,
    ) -> Result<ApplyStatus, TrackerError> {
        let key = format!("cancelled:{}", client_order_id.raw());
        if !self.event_keys.insert(key) {
            self.audit_duplicate(None, Some(client_order_id), None);
            return Ok(ApplyStatus::DuplicateIgnored);
        }
        self.finish_release(client_order_id, ReleaseKind::Cancel)
    }

    fn on_rejected(&mut self, client_order_id: ClientOrderId) -> Result<ApplyStatus, TrackerError> {
        let key = format!("rejected:{}", client_order_id.raw());
        if !self.event_keys.insert(key) {
            self.audit_duplicate(None, Some(client_order_id), None);
            return Ok(ApplyStatus::DuplicateIgnored);
        }
        self.finish_release(client_order_id, ReleaseKind::Reject)
    }

    fn on_expired(&mut self, client_order_id: ClientOrderId) -> Result<ApplyStatus, TrackerError> {
        let key = format!("expired:{}", client_order_id.raw());
        if !self.event_keys.insert(key) {
            self.audit_duplicate(None, Some(client_order_id), None);
            return Ok(ApplyStatus::DuplicateIgnored);
        }
        self.finish_release(client_order_id, ReleaseKind::Expire)
    }

    fn finish_release(
        &mut self,
        client_order_id: ClientOrderId,
        kind: ReleaseKind,
    ) -> Result<ApplyStatus, TrackerError> {
        let tracked = self
            .orders
            .get_mut(&client_order_id.raw())
            .ok_or(TrackerError::MissingOrder(client_order_id))?;
        if tracked.unknown {
            return Err(TrackerError::Position(
                PositionError::ReconciliationRequired,
            ));
        }
        let remaining = tracked.order.quantities().remaining;
        let position_id = tracked.order.position_id();
        match kind {
            ReleaseKind::Cancel => tracked.order.mark_cancelled()?,
            ReleaseKind::Reject => tracked.order.mark_rejected()?,
            ReleaseKind::Expire => tracked.order.mark_expired()?,
        }
        if remaining.get() > 0 {
            if let Some(pos) = self.positions.get_mut(&position_id.raw()) {
                let _ = pos.record_working_cancelled(remaining);
            }
        }
        let event = match kind {
            ReleaseKind::Cancel => AuditEvent::OrderCancelled {
                meta: AuditMeta::now(),
                client_order_id,
            },
            ReleaseKind::Reject => AuditEvent::OrderRejected {
                meta: AuditMeta::now(),
                client_order_id,
            },
            ReleaseKind::Expire => AuditEvent::OrderExpired {
                meta: AuditMeta::now(),
                client_order_id,
            },
        };
        self.audit.append(event);
        Ok(ApplyStatus::Applied)
    }

    fn on_unknown(&mut self, client_order_id: ClientOrderId) -> Result<ApplyStatus, TrackerError> {
        let key = format!("unknown:{}", client_order_id.raw());
        if !self.event_keys.insert(key) {
            self.audit_duplicate(None, Some(client_order_id), None);
            return Ok(ApplyStatus::DuplicateIgnored);
        }
        let tracked = self
            .orders
            .get_mut(&client_order_id.raw())
            .ok_or(TrackerError::MissingOrder(client_order_id))?;
        tracked.order.mark_unknown();
        tracked.unknown = true;
        let position_id = tracked.order.position_id();
        self.unknown_orders.insert(client_order_id.raw());
        self.recon = ReconciliationState::Required;
        self.audit.append(AuditEvent::OrderUnknown {
            meta: AuditMeta::now(),
            client_order_id,
        });
        self.audit.append(AuditEvent::ReconciliationRequired {
            meta: AuditMeta::now(),
            client_order_id,
        });
        self.audit.append(AuditEvent::StateCorrection {
            meta: AuditMeta::now(),
            position_id,
            client_order_id: Some(client_order_id),
            kind: StateCorrectionKind::UnknownPreserved,
        });
        Ok(ApplyStatus::Applied)
    }

    fn apply_fill_event(
        &mut self,
        fill: Fill,
        liquidation: bool,
    ) -> Result<ApplyStatus, TrackerError> {
        if let Some(existing) = self.fills.get(&fill.fill_id().raw()) {
            if existing.same_venue_event(&fill) {
                self.audit_duplicate(
                    Some(fill.fill_id()),
                    Some(fill.client_order_id()),
                    fill.venue_order_id(),
                );
                return Ok(ApplyStatus::DuplicateIgnored);
            }
            let settled = self
                .positions
                .get(&fill.position_id().raw())
                .is_some_and(|p| p.lifecycle() == PositionLifecycle::Settled);
            if settled {
                // Settled history is not overwritten. Qty/ts mapping drift on
                // a closed game is not live exposure and must not freeze the desk.
                self.audit_duplicate(
                    Some(fill.fill_id()),
                    Some(fill.client_order_id()),
                    fill.venue_order_id(),
                );
                return Ok(ApplyStatus::DuplicateIgnored);
            }
            self.recon = ReconciliationState::Ambiguous;
            self.audit.append(AuditEvent::ConflictingEventDetected {
                meta: AuditMeta::now(),
                position_id: fill.position_id(),
                client_order_id: fill.client_order_id(),
                local_status: self
                    .orders
                    .get(&fill.client_order_id().raw())
                    .map(|t| t.order.state())
                    .unwrap_or(OrderState::Unknown),
                venue_status: None,
            });
            return Err(TrackerError::ConflictingEvent);
        }

        let position_id = fill.position_id();
        let pos = self
            .positions
            .get(&position_id.raw())
            .ok_or(TrackerError::MissingPosition(position_id))?;
        let strategy = pos.strategy_id();
        let game = pos.game_id();
        if let Some(existing_id) = self.index.get(strategy, game) {
            if existing_id != position_id {
                return Err(TrackerError::SecondPositionForGame {
                    game,
                    existing: existing_id,
                    attempted: position_id,
                });
            }
        }

        // Leftover venue rows (coalesced fractionals, duplicate trade_ids)
        // must not over-fill an already-complete order and must not freeze
        // the desk. This is not a fill and does not invent qty.
        if let Some(tracked) = self.orders.get(&fill.client_order_id().raw()) {
            let filled = tracked.order.quantities().filled.get();
            let requested = tracked.order.quantities().requested.get();
            if filled >= requested || filled.saturating_add(fill.quantity().get()) > requested {
                self.audit_duplicate(
                    Some(fill.fill_id()),
                    Some(fill.client_order_id()),
                    fill.venue_order_id(),
                );
                return Ok(ApplyStatus::DuplicateIgnored);
            }
        }

        if let Some(tracked) = self.orders.get_mut(&fill.client_order_id().raw()) {
            if tracked.unknown {
                return Err(TrackerError::Position(
                    PositionError::ReconciliationRequired,
                ));
            }
            // Late fill after cancel request is allowed. Do not erase prior fills.
            if tracked.order.position_id() != position_id {
                return Err(TrackerError::SecondPositionForGame {
                    game: tracked.order.game_id(),
                    existing: tracked.order.position_id(),
                    attempted: position_id,
                });
            }
            tracked.order.apply_fill_qty(fill.quantity())?;
        }

        if liquidation {
            self.positions
                .get_mut(&position_id.raw())
                .ok_or(TrackerError::MissingPosition(position_id))?
                .apply_liquidation_fill(fill.clone())?;
        } else {
            self.positions
                .get_mut(&position_id.raw())
                .ok_or(TrackerError::MissingPosition(position_id))?
                .apply_entry_fill(fill.clone())?;
        }

        self.fills.insert(fill.fill_id().raw(), fill.clone());
        self.fills_by_order
            .entry(fill.client_order_id().raw())
            .or_default()
            .push(fill.fill_id().raw());
        self.event_keys
            .insert(format!("fill:{}", fill.fill_id().raw()));

        self.audit.append(AuditEvent::FillRebuilt {
            meta: AuditMeta::now(),
            fill_id: fill.fill_id(),
            position_id,
            client_order_id: fill.client_order_id(),
        });
        let pos = self.positions[&position_id.raw()].clone();
        if liquidation {
            self.audit.append(AuditEvent::LiquidationFilled {
                meta: AuditMeta::now(),
                fill_id: fill.fill_id(),
                position_id,
                fee: fill.fee().amount(),
            });
        } else if self
            .orders
            .get(&fill.client_order_id().raw())
            .map(|t| t.order.state())
            == Some(OrderState::Filled)
        {
            self.audit.append(AuditEvent::OrderFilled {
                meta: AuditMeta::now(),
                fill_id: fill.fill_id(),
                client_order_id: fill.client_order_id(),
                position_id,
            });
        } else {
            self.audit.append(AuditEvent::OrderPartiallyFilled {
                meta: AuditMeta::now(),
                fill_id: fill.fill_id(),
                client_order_id: fill.client_order_id(),
                position_id,
                premium: fill.premium(),
            });
        }
        self.audit.append(AuditEvent::PositionUpdated {
            meta: AuditMeta::now(),
            position_id,
            game_id: pos.game_id(),
            actual_exposure: pos.actual_exposure().as_money(),
            filled_quantity: pos.filled_quantity(),
            submitted_quantity: pos.submitted_quantity(),
            working_quantity: pos.working_quantity(),
            remaining_target: pos.remaining_economic_target().unwrap_or(Money::ZERO),
        });
        Ok(ApplyStatus::Applied)
    }

    fn filled_for_order(&self, client_order_id: ClientOrderId) -> Contracts {
        let mut qty = 0u32;
        if let Some(ids) = self.fills_by_order.get(&client_order_id.raw()) {
            for id in ids {
                if let Some(fill) = self.fills.get(id) {
                    qty = qty.saturating_add(fill.quantity().get());
                }
            }
        }
        Contracts::from_u32(qty)
    }

    fn fees_for_order(&self, client_order_id: ClientOrderId) -> Money {
        let mut fees = Money::ZERO;
        if let Some(ids) = self.fills_by_order.get(&client_order_id.raw()) {
            for id in ids {
                if let Some(fill) = self.fills.get(id) {
                    fees = fees.checked_add(fill.fee().amount()).unwrap_or(fees);
                }
            }
        }
        fees
    }

    fn audit_duplicate(
        &mut self,
        fill_id: Option<FillId>,
        client_order_id: Option<ClientOrderId>,
        venue_order_id: Option<VenueOrderId>,
    ) {
        self.audit.append(AuditEvent::DuplicateEventIgnored {
            meta: AuditMeta::now(),
            fill_id,
            client_order_id,
            venue_order_id,
        });
    }
}

enum ReleaseKind {
    Cancel,
    Reject,
    Expire,
}

impl PositionTracker for InMemoryPositionTracker {
    fn get(&self, id: PositionId) -> Option<&Position> {
        self.positions.get(&id.raw())
    }

    fn get_mut(&mut self, id: PositionId) -> Option<&mut Position> {
        self.positions.get_mut(&id.raw())
    }

    fn apply_entry_fill(&mut self, fill: Fill) -> Result<(), PositionError> {
        match self.apply_fill_event(fill, false) {
            Ok(_) => Ok(()),
            Err(TrackerError::Position(e)) => Err(e),
            Err(TrackerError::SettledCannotReopen) => Err(PositionError::SettledCannotReopen),
            Err(TrackerError::ConflictingEvent) => Err(PositionError::ConflictingEvent),
            Err(TrackerError::MissingPosition(_)) => Err(PositionError::EntryNotPermitted),
            Err(TrackerError::NewExposureBlocked(_)) => Err(PositionError::ReconciliationRequired),
            Err(_) => Err(PositionError::EntryNotPermitted),
        }
    }

    fn reconciliation_state(&self) -> ReconciliationState {
        self.recon
    }
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct PersistedOrder {
    pub order: Order,
    pub cancel_requested: bool,
    pub unknown: bool,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct TrackerPersist {
    pub positions: Vec<Position>,
    pub orders: Vec<PersistedOrder>,
    pub unknown: Vec<u128>,
    pub recon: ReconciliationState,
    pub index: Vec<(u128, u128, u128)>,
    #[serde(default)]
    pub event_keys: Vec<String>,
}
