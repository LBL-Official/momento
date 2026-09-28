//! Order/fill events applied to the fill-authoritative tracker.
//!
//! These are domain events, not venue payloads. Submitted quantity is never a fill.

use momento_core::{
    ClientOrderId, ExchangeTimestamp, Fill, GameId, Order, ReceivedAt, SettlementEvent,
    VenueOrderId,
};

#[derive(Clone, Debug, PartialEq, Eq)]
pub enum PositionEvent {
    OrderSubmitted {
        order: Order,
    },
    OrderWorking {
        client_order_id: ClientOrderId,
        venue_order_id: VenueOrderId,
    },
    PartialFill {
        fill: Fill,
    },
    FullFill {
        fill: Fill,
    },
    LiquidationFill {
        fill: Fill,
    },
    CancelRequested {
        client_order_id: ClientOrderId,
    },
    Cancelled {
        client_order_id: ClientOrderId,
    },
    Rejected {
        client_order_id: ClientOrderId,
    },
    Expired {
        client_order_id: ClientOrderId,
    },
    Unknown {
        client_order_id: ClientOrderId,
    },
    GameLocked {
        game_id: GameId,
        exchange_ts: ExchangeTimestamp,
        received_at: ReceivedAt,
    },
    Settlement(SettlementEvent),
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum ApplyStatus {
    Applied,
    DuplicateIgnored,
}
