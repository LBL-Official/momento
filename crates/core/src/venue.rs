//! Venue traits live in core so execution does not depend on `momento-kalshi`.

use crate::error::MomentoError;
use crate::ids::{ClientOrderId, GameId, MarketId, PositionId, VenueOrderId};
use crate::market::{MarketEvent, Side};
use crate::money::{Contracts, Money, Price};
use crate::order::{Order, OrderState};
use crate::reconciliation::{ReconcileOutcome, UnknownOrder};
use crate::time::{ExchangeTimestamp, ReceivedAt};

/// Market data source. Implementations must preserve exchange vs receipt timestamps.
pub trait VenueMarketData {
    fn poll_events(&mut self) -> Result<Vec<MarketEvent>, MomentoError>;
}

pub trait VenueOrders {
    fn submit_post_only_entry(&mut self, order: &Order) -> Result<(), MomentoError>;
    fn cancel(&mut self, client_order_id: ClientOrderId) -> Result<(), MomentoError>;
    fn amend(
        &mut self,
        client_order_id: ClientOrderId,
        new_qty: Contracts,
    ) -> Result<(), MomentoError>;
    fn submit_reduce_only_liquidation(&mut self, order: &Order) -> Result<(), MomentoError>;
    fn reconcile_unknown(
        &mut self,
        unknown: &UnknownOrder,
    ) -> Result<ReconcileOutcome, MomentoError>;
}

pub trait VenueAccount {
    fn available_balance(&self) -> Result<Money, MomentoError>;
    fn venue_order_id(
        &self,
        client_order_id: ClientOrderId,
    ) -> Result<Option<VenueOrderId>, MomentoError>;
}

/// Venue-neutral market discovery. Does not create PositionId.
pub trait VenueMarketDiscovery {
    fn get_market(&mut self, ticker: &str) -> Result<VenueMarketSnapshot, MomentoError>;
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct VenueMarketSnapshot {
    pub ticker: String,
    pub event_ticker: String,
    pub market_id: Option<MarketId>,
    pub game_id: Option<GameId>,
    pub bid: Option<Price>,
    pub ask: Option<Price>,
    pub last: Option<Price>,
    /// Official Kalshi docs do not define mid. Always `None`. Do not derive it.
    pub mid: Option<Price>,
    pub bid_depth: Option<u32>,
    pub ask_depth: Option<u32>,
    pub exchange_ts: Option<ExchangeTimestamp>,
    pub received_at: ReceivedAt,
}

pub trait VenueOrderStatus {
    fn get_order(&mut self, venue_order_id: VenueOrderId) -> Result<MappedOrderView, MomentoError>;
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct MappedOrderView {
    pub client_order_id: ClientOrderId,
    pub venue_order_id: VenueOrderId,
    pub ticker: String,
    pub state: OrderState,
    pub requested: Contracts,
    pub filled: Contracts,
    pub remaining: Contracts,
}

/// Fill retrieval. `position_id` is supplied by the caller; the venue must not create it.
pub trait VenueFills {
    fn map_fill(
        &self,
        raw_json: &str,
        position_id: PositionId,
        received_at: ReceivedAt,
    ) -> Result<FillView, MomentoError>;
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct FillView {
    pub fill: crate::fill::Fill,
    pub venue_fill_id: String,
}

pub trait VenueSettlement {
    fn get_settlement(&mut self, ticker: &str) -> Result<VenueSettlementView, MomentoError>;
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct VenueSettlementView {
    pub ticker: String,
    pub result: Option<Side>,
    pub settlement_value: Option<Money>,
    pub settlement_ts: Option<ExchangeTimestamp>,
}
