use serde::{Deserialize, Serialize};

use crate::fee::{Fee, FeeKind};
use crate::ids::{ClientOrderId, FillId, PositionId, VenueOrderId};
use crate::money::{Contracts, Money, Price};
use crate::time::{ExchangeTimestamp, ReceivedAt};

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct Fill {
    fill_id: FillId,
    position_id: PositionId,
    client_order_id: ClientOrderId,
    venue_order_id: Option<VenueOrderId>,
    quantity: Contracts,
    price: Price,
    premium: Money,
    fee: Fee,
    exchange_ts: ExchangeTimestamp,
    received_at: ReceivedAt,
}

impl Fill {
    #[allow(clippy::too_many_arguments)]
    pub fn new(
        fill_id: FillId,
        position_id: PositionId,
        client_order_id: ClientOrderId,
        venue_order_id: Option<VenueOrderId>,
        quantity: Contracts,
        price: Price,
        premium: Money,
        fee: Fee,
        exchange_ts: ExchangeTimestamp,
        received_at: ReceivedAt,
    ) -> Self {
        Self {
            fill_id,
            position_id,
            client_order_id,
            venue_order_id,
            quantity,
            price,
            premium,
            fee,
            exchange_ts,
            received_at,
        }
    }

    pub const fn fill_id(&self) -> FillId {
        self.fill_id
    }

    pub const fn position_id(&self) -> PositionId {
        self.position_id
    }

    pub const fn client_order_id(&self) -> ClientOrderId {
        self.client_order_id
    }

    pub const fn quantity(&self) -> Contracts {
        self.quantity
    }

    pub const fn price(&self) -> Price {
        self.price
    }

    pub const fn premium(&self) -> Money {
        self.premium
    }

    pub const fn fee(&self) -> Fee {
        self.fee
    }

    pub fn with_fee_kind(mut self, kind: FeeKind) -> Self {
        self.fee = Fee::new(self.fee.amount(), kind);
        self
    }

    pub const fn is_entry_fee(&self) -> bool {
        matches!(self.fee.kind(), FeeKind::Entry)
    }

    pub const fn is_liquidation_fee(&self) -> bool {
        matches!(self.fee.kind(), FeeKind::Liquidation)
    }

    pub const fn venue_order_id(&self) -> Option<VenueOrderId> {
        self.venue_order_id
    }

    pub const fn exchange_ts(&self) -> ExchangeTimestamp {
        self.exchange_ts
    }

    pub const fn received_at(&self) -> ReceivedAt {
        self.received_at
    }

    /// Same venue fill event. Receipt time and exchange-ts mapping are local
    /// observations, not evidence of a different fill.
    pub fn same_venue_event(&self, other: &Self) -> bool {
        self.fill_id == other.fill_id
            && self.position_id == other.position_id
            && self.client_order_id == other.client_order_id
            && self.venue_order_id == other.venue_order_id
            && self.quantity == other.quantity
            && self.price == other.price
            && self.premium == other.premium
            && self.fee.amount() == other.fee.amount()
            && self.fee.kind() == other.fee.kind()
    }
}
