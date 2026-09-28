//! Paper execution composed with Risk and PositionTracker.
//!
//! Accepts only [`ApprovedTradeIntent`]. Does not approve exposure.
//! Does not duplicate reservation accounting.

use std::collections::HashMap;

use momento_core::{
    ApprovedTradeIntent, AuditEvent, AuditMeta, ClientOrderId, Contracts, ExchangeTimestamp, Fee,
    FeeKind, Fill, FillId, GameId, MarketId, Money, OrderState, Position, PositionId, Price,
    ReceivedAt, ReconcileOutcome, ReconciliationState, RiskDecision, Side, StrategyId, TradeIntent,
    WeeklyBankrollSnapshot, contract_premium,
};
use momento_positions::{InMemoryPositionTracker, PositionTracker};
use momento_risk::{FeeModel, PaperRiskEngine, RiskConfig, ZeroFeeModel};

use crate::{ExecutionEngine, ExecutionError, PaperExecution};

struct OrderMeta {
    approved: ApprovedTradeIntent,
    filled_economic: Money,
}

/// Deterministic paper execution. Tests inject outcomes; no random fills.
pub struct PaperExecutionEngine<F: FeeModel = ZeroFeeModel> {
    snapshot: WeeklyBankrollSnapshot,
    risk: PaperRiskEngine<F>,
    positions: InMemoryPositionTracker,
    venue: PaperExecution,
    fees: F,
    max_entry_price: Price,
    orders: HashMap<u128, OrderMeta>,
}

impl PaperExecutionEngine<ZeroFeeModel> {
    pub fn paper(snapshot: WeeklyBankrollSnapshot) -> Self {
        let config = RiskConfig::mlb_paper_experimental().expect("80¢ and 83¢ are valid prices");
        Self::new(snapshot, config, ZeroFeeModel)
    }
}

impl<F: FeeModel> PaperExecutionEngine<F> {
    pub fn new(snapshot: WeeklyBankrollSnapshot, config: RiskConfig, fees: F) -> Self {
        let max_entry_price = config.max_entry_price;
        let risk = PaperRiskEngine::new(
            snapshot.clone(),
            config,
            fees.clone(),
            momento_risk::SnapshotPaperBalance::from_bankroll(snapshot.bankroll()),
            momento_core::InMemoryAuditLog::default(),
        );
        Self {
            snapshot,
            risk,
            positions: InMemoryPositionTracker::new(),
            venue: PaperExecution::new(),
            fees,
            max_entry_price,
            orders: HashMap::new(),
        }
    }

    pub fn snapshot(&self) -> &WeeklyBankrollSnapshot {
        &self.snapshot
    }

    pub fn risk(&self) -> &PaperRiskEngine<F> {
        &self.risk
    }

    pub fn positions(&self) -> &InMemoryPositionTracker {
        &self.positions
    }

    pub fn fee_model_id(&self) -> momento_core::FeeModelId {
        self.fees.model_id()
    }

    pub fn open_game(
        &mut self,
        strategy: StrategyId,
        game: GameId,
        market: MarketId,
        side: Side,
    ) -> PositionId {
        self.positions
            .get_or_create(strategy, game, &self.snapshot, Some(market), Some(side))
            .id()
    }

    pub fn position(&self, id: PositionId) -> Option<&Position> {
        self.positions.get(id)
    }

    pub fn decide_entry(&self, intent: &TradeIntent) -> RiskDecision {
        let Some(pos) = self.positions.get(intent.build.position_id).cloned() else {
            return RiskDecision::Rejected {
                decision_id: momento_core::RiskDecisionId::generate(),
                reason: momento_core::RiskRejectReason::DuplicateGamePosition,
                snapshot_id: self.snapshot.snapshot_id(),
            };
        };
        self.risk.decide_entry(intent, &pos)
    }

    /// Only [`RiskDecision::Approved`] may be submitted.
    pub fn execute(&mut self, decision: RiskDecision) -> Result<ClientOrderId, ExecutionError> {
        match decision {
            RiskDecision::Approved(intent) => self.execute_approved(intent),
            RiskDecision::Rejected { .. } => Err(ExecutionError::NotApproved),
        }
    }

    pub fn execute_approved(
        &mut self,
        intent: ApprovedTradeIntent,
    ) -> Result<ClientOrderId, ExecutionError> {
        if intent.limit_price() > self.max_entry_price {
            self.risk.on_cancel(intent.client_order_id());
            return Err(ExecutionError::EntryPriceAboveMaximum);
        }
        if self.venue.recon_state().blocks_new_exposure() {
            return Err(ExecutionError::ReconciliationRequired);
        }

        let position_id = intent.position_id();
        let pos = self
            .positions
            .get_mut(position_id)
            .ok_or(ExecutionError::PositionMissing)?;
        if !pos.can_attempt_entry() {
            self.risk.on_cancel(intent.client_order_id());
            return Err(ExecutionError::EntryNotPermitted);
        }
        pos.bind_entry_identity(intent.market_id(), intent.side())
            .map_err(|e| ExecutionError::PaperScript(e.to_string()))?;
        pos.record_submission(intent.max_contracts())
            .map_err(|e| ExecutionError::PaperScript(e.to_string()))?;

        let id = self.venue.submit_entry(intent.clone())?;

        self.orders.insert(
            id.raw(),
            OrderMeta {
                approved: intent.clone(),
                filled_economic: Money::ZERO,
            },
        );

        self.risk.append_audit(AuditEvent::OrderSubmitted {
            meta: AuditMeta::now(),
            client_order_id: id,
            position_id,
            game_id: intent.game_id(),
        });
        self.append_position_updated(position_id);
        Ok(id)
    }

    pub fn accept(
        &mut self,
        id: ClientOrderId,
    ) -> Result<momento_core::VenueOrderId, ExecutionError> {
        let venue_id = self.venue.simulate_ack(id)?;
        self.risk.append_audit(AuditEvent::OrderAcknowledged {
            meta: AuditMeta::now(),
            client_order_id: id,
        });
        self.risk.append_audit(AuditEvent::OrderWorking {
            meta: AuditMeta::now(),
            client_order_id: id,
        });
        Ok(venue_id)
    }

    pub fn fill(&mut self, cmd: PaperFill) -> Result<Fill, ExecutionError> {
        let meta = self
            .orders
            .get(&cmd.client_order_id.raw())
            .ok_or(ExecutionError::UnknownOrder)?;
        let approved = meta.approved.clone();
        let already = meta.filled_economic;

        if self
            .venue
            .order(cmd.client_order_id)
            .map(momento_core::Order::state)
            == Some(OrderState::Unknown)
        {
            return Err(ExecutionError::ReconciliationRequired);
        }

        let remaining_qty = self
            .venue
            .order(cmd.client_order_id)
            .map(|o| o.quantities().remaining)
            .ok_or(ExecutionError::UnknownOrder)?;
        if cmd.quantity.get() > remaining_qty.get() {
            return Err(ExecutionError::ExceedsApprovedExposure);
        }

        let premium = contract_premium(cmd.quantity, cmd.price)
            .map_err(|e| ExecutionError::PaperScript(e.to_string()))?;
        let fee_amt = self
            .fees
            .estimate_entry_fee(cmd.quantity, cmd.price)
            .map_err(|_| ExecutionError::PaperScript("fee estimate overflow".into()))?;
        let economic = premium
            .checked_add(fee_amt)
            .map_err(|e| ExecutionError::PaperScript(e.to_string()))?;
        let next_economic = already
            .checked_add(economic)
            .map_err(|e| ExecutionError::PaperScript(e.to_string()))?;
        if next_economic.cents() > approved.max_economic().cents() {
            return Err(ExecutionError::ExceedsApprovedExposure);
        }

        let pos = self
            .positions
            .get(approved.position_id())
            .ok_or(ExecutionError::PositionMissing)?;
        let used = pos
            .actual_exposure()
            .as_money()
            .checked_add(pos.entry_fees())
            .and_then(|u| u.checked_add(economic))
            .map_err(|e| ExecutionError::PaperScript(e.to_string()))?;
        if used.cents() > approved.original_budget().cents() {
            return Err(ExecutionError::ExceedsApprovedExposure);
        }

        let fee = Fee::new(fee_amt, FeeKind::Entry);
        let mut produced = None;
        self.venue.simulate_partial_fill(
            cmd.client_order_id,
            cmd.quantity,
            cmd.price,
            premium,
            fee,
            |fill| produced = Some(fill),
        )?;
        let mut fill = produced
            .ok_or_else(|| ExecutionError::PaperScript("paper venue produced no fill".into()))?;
        if let Some(id) = cmd.fill_id {
            fill = Fill::new(
                id,
                fill.position_id(),
                fill.client_order_id(),
                None,
                fill.quantity(),
                fill.price(),
                fill.premium(),
                fill.fee(),
                cmd.exchange_ts,
                cmd.received_at,
            );
        } else {
            fill = Fill::new(
                fill.fill_id(),
                fill.position_id(),
                fill.client_order_id(),
                None,
                fill.quantity(),
                fill.price(),
                fill.premium(),
                fill.fee(),
                cmd.exchange_ts,
                cmd.received_at,
            );
        }

        self.positions
            .apply_entry_fill(fill.clone())
            .map_err(|e| ExecutionError::PaperScript(e.to_string()))?;
        self.risk.on_fill(&fill);

        if let Some(meta) = self.orders.get_mut(&cmd.client_order_id.raw()) {
            meta.filled_economic = next_economic;
        }

        let order_state = self
            .venue
            .order(cmd.client_order_id)
            .map(momento_core::Order::state);
        if order_state == Some(OrderState::Filled) {
            self.risk.append_audit(AuditEvent::OrderFilled {
                meta: AuditMeta::now(),
                fill_id: fill.fill_id(),
                client_order_id: cmd.client_order_id,
                position_id: fill.position_id(),
            });
        } else {
            self.risk.append_audit(AuditEvent::OrderPartiallyFilled {
                meta: AuditMeta::now(),
                fill_id: fill.fill_id(),
                client_order_id: cmd.client_order_id,
                position_id: fill.position_id(),
                premium: fill.premium(),
            });
        }
        self.append_position_updated(fill.position_id());
        Ok(fill)
    }

    pub fn cancel(&mut self, id: ClientOrderId) -> Result<(), ExecutionError> {
        self.release_known_outcome(id, KnownRelease::Cancel)
    }

    pub fn reject(&mut self, id: ClientOrderId) -> Result<(), ExecutionError> {
        self.release_known_outcome(id, KnownRelease::Reject)
    }

    pub fn expire(&mut self, id: ClientOrderId) -> Result<(), ExecutionError> {
        self.release_known_outcome(id, KnownRelease::Expire)
    }

    /// UNKNOWN keeps the reservation and requires reconciliation.
    pub fn unknown(&mut self, id: ClientOrderId) -> Result<(), ExecutionError> {
        let position_id = self
            .venue
            .order(id)
            .map(momento_core::Order::position_id)
            .ok_or(ExecutionError::UnknownOrder)?;
        self.venue.simulate_unknown(id)?;
        self.risk.mark_unknown(id, position_id);
        self.positions.require_reconciliation();
        self.risk.append_audit(AuditEvent::OrderUnknown {
            meta: AuditMeta::now(),
            client_order_id: id,
        });
        self.risk.append_audit(AuditEvent::ReconciliationRequired {
            meta: AuditMeta::now(),
            client_order_id: id,
        });
        Ok(())
    }

    pub fn reconcile(
        &mut self,
        id: ClientOrderId,
        outcome: ReconcileOutcome,
    ) -> Result<(), ExecutionError> {
        let position_id = self
            .venue
            .order(id)
            .map(momento_core::Order::position_id)
            .ok_or(ExecutionError::UnknownOrder)?;
        self.positions.start_reconciliation(id);
        self.venue.reconcile(id, outcome)?;
        self.risk.reconcile_order(id, position_id, outcome);
        match outcome {
            ReconcileOutcome::Found | ReconcileOutcome::NotFound => {
                self.positions.complete_reconciliation();
            }
            ReconcileOutcome::Ambiguous => {
                self.positions.mark_ambiguous();
            }
        }
        self.risk.append_audit(AuditEvent::ReconciliationCompleted {
            meta: AuditMeta::now(),
            client_order_id: id,
            outcome,
        });
        Ok(())
    }

    /// Test command: first 89% observed. Cancels working entry; does not flatten.
    pub fn lock_game(
        &mut self,
        game_id: GameId,
        exchange_ts: ExchangeTimestamp,
        received_at: ReceivedAt,
    ) -> Result<(), ExecutionError> {
        let working: Vec<ClientOrderId> = self
            .orders
            .iter()
            .filter_map(|(raw, meta)| {
                if meta.approved.game_id() != game_id {
                    return None;
                }
                let id = ClientOrderId::from_raw(*raw);
                let state = self.venue.order(id).map(momento_core::Order::state)?;
                if state == OrderState::Unknown || state.is_terminal() {
                    None
                } else {
                    Some(id)
                }
            })
            .collect();

        for id in working {
            self.cancel(id)?;
        }

        let position_id = self
            .orders
            .values()
            .find(|m| m.approved.game_id() == game_id)
            .map(|m| m.approved.position_id())
            .or_else(|| self.positions.id_for_game(game_id));

        if let Some(position_id) = position_id {
            if let Some(pos) = self.positions.get_mut(position_id) {
                pos.apply_game_lock(exchange_ts, received_at);
            }
            self.risk.lock_game(game_id);
            self.risk.append_audit(AuditEvent::GameLocked {
                meta: AuditMeta::now(),
                game_id,
                position_id,
                exchange_ts,
                received_at,
            });
            self.append_position_updated(position_id);
        }
        Ok(())
    }

    pub fn order_state(&self, id: ClientOrderId) -> Option<OrderState> {
        self.venue.order(id).map(momento_core::Order::state)
    }

    pub fn order_quantities(&self, id: ClientOrderId) -> Option<momento_core::OrderQuantities> {
        self.venue.order(id).map(momento_core::Order::quantities)
    }

    pub fn reserved_for(&self, position_id: PositionId) -> Money {
        self.risk.reserved_for(position_id)
    }

    pub fn recon_state(&self) -> ReconciliationState {
        self.venue.recon_state()
    }

    pub fn audit_events(&self) -> Vec<AuditEvent> {
        self.risk.audit_events()
    }

    fn release_known_outcome(
        &mut self,
        id: ClientOrderId,
        kind: KnownRelease,
    ) -> Result<(), ExecutionError> {
        let position_id = self
            .venue
            .order(id)
            .map(momento_core::Order::position_id)
            .ok_or(ExecutionError::UnknownOrder)?;
        let remaining = self
            .venue
            .order(id)
            .map(|o| o.quantities().remaining)
            .unwrap_or(Contracts::ZERO);

        match kind {
            KnownRelease::Cancel => self.venue.simulate_cancel(id)?,
            KnownRelease::Reject => self.venue.simulate_reject(id)?,
            KnownRelease::Expire => self.venue.simulate_expire(id)?,
        }

        if remaining.get() > 0 {
            if let Some(pos) = self.positions.get_mut(position_id) {
                let _ = pos.record_working_cancelled(remaining);
            }
        }
        self.risk.on_cancel(id);

        let event = match kind {
            KnownRelease::Cancel => AuditEvent::OrderCancelled {
                meta: AuditMeta::now(),
                client_order_id: id,
            },
            KnownRelease::Reject => AuditEvent::OrderRejected {
                meta: AuditMeta::now(),
                client_order_id: id,
            },
            KnownRelease::Expire => AuditEvent::OrderExpired {
                meta: AuditMeta::now(),
                client_order_id: id,
            },
        };
        self.risk.append_audit(event);
        self.append_position_updated(position_id);
        Ok(())
    }

    fn append_position_updated(&self, position_id: PositionId) {
        let Some(pos) = self.positions.get(position_id) else {
            return;
        };
        let remaining = pos.remaining_economic_target().unwrap_or(Money::ZERO);
        self.risk.append_audit(AuditEvent::PositionUpdated {
            meta: AuditMeta::now(),
            position_id,
            game_id: pos.game_id(),
            actual_exposure: pos.actual_exposure().as_money(),
            filled_quantity: pos.filled_quantity(),
            submitted_quantity: pos.submitted_quantity(),
            working_quantity: pos.working_quantity(),
            remaining_target: remaining,
        });
    }
}

enum KnownRelease {
    Cancel,
    Reject,
    Expire,
}

/// Deterministic fill command. Premium is `qty * price`; fee comes from [`FeeModel`].
pub struct PaperFill {
    pub client_order_id: ClientOrderId,
    pub quantity: Contracts,
    pub price: Price,
    pub fill_id: Option<FillId>,
    pub exchange_ts: ExchangeTimestamp,
    pub received_at: ReceivedAt,
}
