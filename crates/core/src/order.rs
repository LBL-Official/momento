use serde::{Deserialize, Serialize};

use crate::error::OrderError;
use crate::ids::{ClientOrderId, GameId, MarketId, PositionId, RiskDecisionId, VenueOrderId};
use crate::market::Side;
use crate::money::{Contracts, Price};

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub enum OrderPurpose {
    Entry,
    Liquidation,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub enum OrderState {
    New,
    Submitting,
    Acknowledged,
    Working,
    PartiallyFilled,
    Filled,
    CancelPending,
    Cancelled,
    Rejected,
    Expired,
    Unknown,
}

impl OrderState {
    pub const fn as_str(self) -> &'static str {
        match self {
            Self::New => "NEW",
            Self::Submitting => "SUBMITTING",
            Self::Acknowledged => "ACKNOWLEDGED",
            Self::Working => "WORKING",
            Self::PartiallyFilled => "PARTIALLY_FILLED",
            Self::Filled => "FILLED",
            Self::CancelPending => "CANCEL_PENDING",
            Self::Cancelled => "CANCELLED",
            Self::Rejected => "REJECTED",
            Self::Expired => "EXPIRED",
            Self::Unknown => "UNKNOWN",
        }
    }

    pub const fn requires_reconciliation(self) -> bool {
        matches!(self, Self::Unknown)
    }

    pub const fn is_terminal(self) -> bool {
        matches!(
            self,
            Self::Filled | Self::Cancelled | Self::Rejected | Self::Expired
        )
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct OrderQuantities {
    pub requested: Contracts,
    pub filled: Contracts,
    pub cancelled: Contracts,
    pub remaining: Contracts,
}

impl OrderQuantities {
    pub fn new_requested(requested: Contracts) -> Self {
        Self {
            requested,
            filled: Contracts::ZERO,
            cancelled: Contracts::ZERO,
            remaining: requested,
        }
    }
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct Order {
    client_order_id: ClientOrderId,
    venue_order_id: Option<VenueOrderId>,
    position_id: PositionId,
    game_id: GameId,
    #[serde(default)]
    market_id: Option<MarketId>,
    #[serde(default)]
    side: Option<Side>,
    risk_decision_id: RiskDecisionId,
    purpose: OrderPurpose,
    state: OrderState,
    price: Price,
    quantities: OrderQuantities,
}

impl Order {
    pub fn new_entry(
        client_order_id: ClientOrderId,
        position_id: PositionId,
        game_id: GameId,
        risk_decision_id: RiskDecisionId,
        price: Price,
        requested: Contracts,
    ) -> Self {
        Self {
            client_order_id,
            venue_order_id: None,
            position_id,
            game_id,
            market_id: None,
            side: None,
            risk_decision_id,
            purpose: OrderPurpose::Entry,
            state: OrderState::New,
            price,
            quantities: OrderQuantities::new_requested(requested),
        }
    }

    #[allow(clippy::too_many_arguments)]
    pub fn new_liquidation(
        client_order_id: ClientOrderId,
        position_id: PositionId,
        game_id: GameId,
        risk_decision_id: RiskDecisionId,
        price: Price,
        requested: Contracts,
        market_id: MarketId,
        side: Side,
    ) -> Self {
        Self {
            client_order_id,
            venue_order_id: None,
            position_id,
            game_id,
            market_id: Some(market_id),
            side: Some(side),
            risk_decision_id,
            purpose: OrderPurpose::Liquidation,
            state: OrderState::New,
            price,
            quantities: OrderQuantities::new_requested(requested),
        }
    }

    pub const fn client_order_id(&self) -> ClientOrderId {
        self.client_order_id
    }

    pub const fn venue_order_id(&self) -> Option<VenueOrderId> {
        self.venue_order_id
    }

    pub const fn position_id(&self) -> PositionId {
        self.position_id
    }

    pub const fn game_id(&self) -> GameId {
        self.game_id
    }

    pub const fn market_id(&self) -> Option<MarketId> {
        self.market_id
    }

    pub const fn side(&self) -> Option<Side> {
        self.side
    }

    pub const fn purpose(&self) -> OrderPurpose {
        self.purpose
    }

    pub const fn state(&self) -> OrderState {
        self.state
    }

    pub const fn price(&self) -> Price {
        self.price
    }

    pub const fn quantities(&self) -> OrderQuantities {
        self.quantities
    }

    pub fn submitted_is_not_filled(&self) -> bool {
        self.quantities.requested.get() != self.quantities.filled.get()
            || self.state != OrderState::Filled
    }

    pub fn mark_submitting(&mut self) -> Result<(), OrderError> {
        self.transition(OrderState::Submitting)
    }

    pub fn mark_ack(&mut self, venue_order_id: VenueOrderId) -> Result<(), OrderError> {
        self.venue_order_id = Some(venue_order_id);
        self.transition(OrderState::Acknowledged)?;
        self.transition(OrderState::Working)
    }

    pub fn mark_unknown(&mut self) {
        self.state = OrderState::Unknown;
    }

    /// Attach a venue id without changing lifecycle. Used when a fill arrives
    /// before the acknowledgement.
    pub fn attach_venue_id(&mut self, venue_order_id: VenueOrderId) {
        if self.venue_order_id.is_none() {
            self.venue_order_id = Some(venue_order_id);
        }
    }

    /// Reconciliation recovery. Not a normal trading transition.
    pub fn recover_from_unknown(&mut self, venue_order_id: VenueOrderId) {
        self.venue_order_id = Some(venue_order_id);
        self.state = OrderState::Working;
    }

    pub fn apply_fill_qty(&mut self, filled_delta: Contracts) -> Result<(), OrderError> {
        if self.state == OrderState::Unknown {
            return Err(OrderError::UnknownRequiresReconciliation);
        }
        let filled = self
            .quantities
            .filled
            .checked_add(filled_delta)
            .map_err(|_| OrderError::InvalidTransition {
                from: self.state.as_str(),
                to: "FILL",
            })?;
        if filled.get() > self.quantities.requested.get() {
            return Err(OrderError::InvalidTransition {
                from: self.state.as_str(),
                to: "FILL_EXCEEDS_REQUESTED",
            });
        }
        self.quantities.filled = filled;
        self.quantities.remaining =
            self.quantities.requested.checked_sub(filled).map_err(|_| {
                OrderError::InvalidTransition {
                    from: self.state.as_str(),
                    to: "FILL",
                }
            })?;
        self.quantities.remaining = Contracts::from_u32(
            self.quantities
                .requested
                .get()
                .saturating_sub(self.quantities.filled.get() + self.quantities.cancelled.get()),
        );
        if self.quantities.filled.get() >= self.quantities.requested.get() {
            self.state = OrderState::Filled;
        } else {
            self.state = OrderState::PartiallyFilled;
        }
        Ok(())
    }

    pub fn mark_cancel_pending(&mut self) -> Result<(), OrderError> {
        if self.state == OrderState::Unknown {
            return Err(OrderError::UnknownRequiresReconciliation);
        }
        self.transition(OrderState::CancelPending)
    }

    pub fn mark_cancelled(&mut self) -> Result<(), OrderError> {
        if self.state == OrderState::Unknown {
            return Err(OrderError::UnknownRequiresReconciliation);
        }
        self.quantities.cancelled = self.quantities.remaining;
        self.quantities.remaining = Contracts::ZERO;
        self.state = OrderState::Cancelled;
        Ok(())
    }

    pub fn mark_rejected(&mut self) -> Result<(), OrderError> {
        self.state = OrderState::Rejected;
        self.quantities.remaining = Contracts::ZERO;
        Ok(())
    }

    /// WORKING / PARTIALLY_FILLED → EXPIRED. UNKNOWN must be reconciled first.
    pub fn mark_expired(&mut self) -> Result<(), OrderError> {
        if self.state == OrderState::Unknown {
            return Err(OrderError::UnknownRequiresReconciliation);
        }
        if !matches!(
            self.state,
            OrderState::Working | OrderState::PartiallyFilled
        ) {
            return Err(OrderError::InvalidTransition {
                from: self.state.as_str(),
                to: OrderState::Expired.as_str(),
            });
        }
        self.quantities.cancelled = self.quantities.remaining;
        self.quantities.remaining = Contracts::ZERO;
        self.state = OrderState::Expired;
        Ok(())
    }

    fn transition(&mut self, to: OrderState) -> Result<(), OrderError> {
        let allowed = matches!(
            (self.state, to),
            (OrderState::New, OrderState::Submitting)
                | (OrderState::Submitting, OrderState::Acknowledged)
                | (OrderState::Acknowledged, OrderState::Working)
                | (OrderState::Working, OrderState::CancelPending)
                | (OrderState::PartiallyFilled, OrderState::CancelPending)
                | (OrderState::Working, OrderState::PartiallyFilled)
                | (OrderState::Working, OrderState::Filled)
        );
        if allowed || self.state == to {
            self.state = to;
            Ok(())
        } else {
            Err(OrderError::InvalidTransition {
                from: self.state.as_str(),
                to: to.as_str(),
            })
        }
    }
}
