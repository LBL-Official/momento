//! Execution engine trait and deterministic paper venue.
//!
//! No network. No live Kalshi.

#![forbid(unsafe_code)]

mod engine;

use std::collections::HashMap;

use momento_core::{
    ApprovedTradeIntent, ClientOrderId, Contracts, Fill, FillId, LiquidationIntent, Money, Order,
    OrderPurpose, OrderState, Price, ReconcileOutcome, ReconciliationState, VenueOrderId,
};

pub use engine::{PaperExecutionEngine, PaperFill};

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum ExecutionError {
    NotApproved,
    ReconciliationRequired,
    UnknownOrder,
    PaperScript(String),
    ExceedsApprovedExposure,
    EntryPriceAboveMaximum,
    EntryNotPermitted,
    PositionMissing,
}

pub enum ExecutionEvent {
    Acknowledged {
        client_order_id: ClientOrderId,
        venue_order_id: VenueOrderId,
    },
    Fill(Fill),
    Cancelled {
        client_order_id: ClientOrderId,
    },
    Unknown {
        client_order_id: ClientOrderId,
    },
    Rejected {
        client_order_id: ClientOrderId,
    },
}

pub trait ExecutionEngine {
    fn submit_entry(
        &mut self,
        intent: ApprovedTradeIntent,
    ) -> Result<ClientOrderId, ExecutionError>;
    fn cancel_entry(&mut self, id: ClientOrderId) -> Result<(), ExecutionError>;
    fn amend_entry(&mut self, id: ClientOrderId, new_qty: Contracts) -> Result<(), ExecutionError>;
    fn submit_liquidation(
        &mut self,
        intent: LiquidationIntent,
        qty: Contracts,
        price: Price,
    ) -> Result<ClientOrderId, ExecutionError>;
    fn recon_state(&self) -> ReconciliationState;
}

/// Deterministic paper execution. Tests inject acks/fills/unknowns.
#[derive(Default)]
pub struct PaperExecution {
    orders: HashMap<u128, Order>,
    recon: ReconciliationState,
    next_venue: u128,
}

impl PaperExecution {
    pub fn new() -> Self {
        Self::default()
    }

    pub fn order(&self, id: ClientOrderId) -> Option<&Order> {
        self.orders.get(&id.raw())
    }

    pub fn simulate_ack(&mut self, id: ClientOrderId) -> Result<VenueOrderId, ExecutionError> {
        let order = self
            .orders
            .get_mut(&id.raw())
            .ok_or(ExecutionError::UnknownOrder)?;
        if order.state() == OrderState::Unknown {
            return Err(ExecutionError::ReconciliationRequired);
        }
        self.next_venue += 1;
        let venue = VenueOrderId::from_raw(self.next_venue);
        order
            .mark_submitting()
            .and_then(|_| order.mark_ack(venue))
            .map_err(|e| ExecutionError::PaperScript(e.to_string()))?;
        Ok(venue)
    }

    pub fn simulate_partial_fill(
        &mut self,
        id: ClientOrderId,
        qty: Contracts,
        price: Price,
        premium: Money,
        fee: momento_core::Fee,
        position_fill: impl FnOnce(Fill),
    ) -> Result<(), ExecutionError> {
        let order = self
            .orders
            .get_mut(&id.raw())
            .ok_or(ExecutionError::UnknownOrder)?;
        if order.state() == OrderState::Unknown {
            return Err(ExecutionError::ReconciliationRequired);
        }
        order
            .apply_fill_qty(qty)
            .map_err(|e| ExecutionError::PaperScript(e.to_string()))?;
        let fill = Fill::new(
            FillId::generate(),
            order.position_id(),
            id,
            order.venue_order_id(),
            qty,
            price,
            premium,
            fee,
            momento_core::ExchangeTimestamp::from_utc(momento_core::utc_now()),
            momento_core::ReceivedAt::now(),
        );
        position_fill(fill);
        Ok(())
    }

    pub fn simulate_cancel(&mut self, id: ClientOrderId) -> Result<(), ExecutionError> {
        let order = self
            .orders
            .get_mut(&id.raw())
            .ok_or(ExecutionError::UnknownOrder)?;
        if order.state() == OrderState::Unknown {
            return Err(ExecutionError::ReconciliationRequired);
        }
        order
            .mark_cancel_pending()
            .and_then(|_| order.mark_cancelled())
            .map_err(|e| ExecutionError::PaperScript(e.to_string()))?;
        Ok(())
    }

    pub fn simulate_reject(&mut self, id: ClientOrderId) -> Result<(), ExecutionError> {
        let order = self
            .orders
            .get_mut(&id.raw())
            .ok_or(ExecutionError::UnknownOrder)?;
        if order.state() == OrderState::Unknown {
            return Err(ExecutionError::ReconciliationRequired);
        }
        order
            .mark_rejected()
            .map_err(|e| ExecutionError::PaperScript(e.to_string()))?;
        Ok(())
    }

    pub fn simulate_expire(&mut self, id: ClientOrderId) -> Result<(), ExecutionError> {
        let order = self
            .orders
            .get_mut(&id.raw())
            .ok_or(ExecutionError::UnknownOrder)?;
        if order.state() == OrderState::Unknown {
            return Err(ExecutionError::ReconciliationRequired);
        }
        order
            .mark_expired()
            .map_err(|e| ExecutionError::PaperScript(e.to_string()))?;
        Ok(())
    }

    /// Timeout / unclear ack. Does NOT mean failed. Requires reconciliation.
    pub fn simulate_unknown(&mut self, id: ClientOrderId) -> Result<(), ExecutionError> {
        let order = self
            .orders
            .get_mut(&id.raw())
            .ok_or(ExecutionError::UnknownOrder)?;
        order.mark_unknown();
        self.recon = ReconciliationState::Required;
        Ok(())
    }

    pub fn reconcile(
        &mut self,
        id: ClientOrderId,
        outcome: ReconcileOutcome,
    ) -> Result<(), ExecutionError> {
        let order = self
            .orders
            .get_mut(&id.raw())
            .ok_or(ExecutionError::UnknownOrder)?;
        match outcome {
            ReconcileOutcome::Found => {
                if order.state() == OrderState::Unknown || order.venue_order_id().is_none() {
                    self.next_venue += 1;
                    let venue = VenueOrderId::from_raw(self.next_venue);
                    order.recover_from_unknown(venue);
                }
                self.recon = ReconciliationState::Healthy;
            }
            ReconcileOutcome::NotFound => {
                let _ = order.mark_rejected();
                self.recon = ReconciliationState::Healthy;
            }
            ReconcileOutcome::Ambiguous => {
                self.recon = ReconciliationState::Ambiguous;
            }
        }
        Ok(())
    }

    pub fn simulate_replace(
        &mut self,
        id: ClientOrderId,
        new_qty: Contracts,
    ) -> Result<(), ExecutionError> {
        self.amend_entry(id, new_qty)
    }
}

impl ExecutionEngine for PaperExecution {
    fn submit_entry(
        &mut self,
        intent: ApprovedTradeIntent,
    ) -> Result<ClientOrderId, ExecutionError> {
        if self.recon.blocks_new_exposure() {
            return Err(ExecutionError::ReconciliationRequired);
        }
        let id = intent.client_order_id();
        let order = Order::new_entry(
            id,
            intent.position_id(),
            intent.game_id(),
            intent.decision_id(),
            intent.limit_price(),
            intent.max_contracts(),
        );
        self.orders.insert(id.raw(), order);
        Ok(id)
    }

    fn cancel_entry(&mut self, id: ClientOrderId) -> Result<(), ExecutionError> {
        self.simulate_cancel(id)
    }

    fn amend_entry(
        &mut self,
        id: ClientOrderId,
        _new_qty: Contracts,
    ) -> Result<(), ExecutionError> {
        let order = self
            .orders
            .get(&id.raw())
            .ok_or(ExecutionError::UnknownOrder)?;
        if order.state() == OrderState::Unknown {
            return Err(ExecutionError::ReconciliationRequired);
        }
        Ok(())
    }

    fn submit_liquidation(
        &mut self,
        intent: LiquidationIntent,
        qty: Contracts,
        price: Price,
    ) -> Result<ClientOrderId, ExecutionError> {
        let id = intent.client_order_id;
        let order = Order::new_liquidation(
            id,
            intent.position_id,
            intent.game_id,
            momento_core::RiskDecisionId::generate(),
            price,
            qty,
            intent.market_id,
            intent.side,
        );
        self.orders.insert(id.raw(), order);
        Ok(id)
    }

    fn recon_state(&self) -> ReconciliationState {
        self.recon
    }
}

impl PaperExecution {
    pub fn purpose(&self, id: ClientOrderId) -> Option<OrderPurpose> {
        self.orders.get(&id.raw()).map(Order::purpose)
    }
}
