use serde::{Deserialize, Serialize};

use crate::ids::{ClientOrderId, GameId, PositionId, VenueOrderId};
use crate::money::{Contracts, Money, Price};
use crate::order::OrderState;
use crate::time::{ExchangeTimestamp, ReceivedAt};

/// Process-level exposure gate. Only [`Healthy`] permits new exposure.
///
/// `Required` is the M1–M3 name for reconciliation-required. `Reconciling`
/// and `Ambiguous` are M5 additions. Found/NotFound are outcomes, not gates:
/// they return the process to [`Healthy`] only after authoritative evidence.
#[derive(Clone, Copy, Debug, Default, PartialEq, Eq, Serialize, Deserialize)]
pub enum ReconciliationState {
    #[default]
    Healthy,
    Required,
    Reconciling,
    Ambiguous,
}

impl ReconciliationState {
    pub const fn blocks_new_exposure(self) -> bool {
        !matches!(self, Self::Healthy)
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub enum ReconcileOutcome {
    Found,
    NotFound,
    Ambiguous,
}

impl ReconcileOutcome {
    pub const fn allows_trading(self) -> bool {
        matches!(self, Self::Found | Self::NotFound)
    }

    pub const fn as_str(self) -> &'static str {
        match self {
            Self::Found => "FOUND",
            Self::NotFound => "NOT_FOUND",
            Self::Ambiguous => "AMBIGUOUS",
        }
    }
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct UnknownOrder {
    pub client_order_id: ClientOrderId,
}

/// Typed comparison of local vs venue state. Never silently overwrites history.
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct ReconciliationResult {
    pub client_order_id: ClientOrderId,
    pub venue_order_id: Option<VenueOrderId>,
    pub position_id: PositionId,
    pub game_id: GameId,
    pub local_status: OrderState,
    pub venue_status: Option<OrderState>,
    pub local_filled: Contracts,
    pub venue_filled: Option<Contracts>,
    pub local_price: Option<Price>,
    pub venue_fill_prices: Vec<Price>,
    pub local_fees: Money,
    pub venue_fees: Option<Money>,
    pub exchange_ts: Option<ExchangeTimestamp>,
    pub received_at: ReceivedAt,
    pub authoritative: bool,
    pub outcome: ReconcileOutcome,
}

/// Venue-neutral snapshot used by the tracker to reconcile one order.
///
/// `presence` is explicit. Timeout/empty transport must not be encoded as
/// [`OrderPresence::NotFound`].
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct VenueOrderSnapshot {
    pub presence: OrderPresence,
    pub venue_order_id: Option<VenueOrderId>,
    pub venue_status: Option<OrderState>,
    pub venue_filled: Option<Contracts>,
    pub venue_remaining: Option<Contracts>,
    pub venue_fill_prices: Vec<Price>,
    pub venue_fees: Option<Money>,
    pub fills: Vec<crate::fill::Fill>,
    pub exchange_ts: Option<ExchangeTimestamp>,
    /// True when the venue payload contradicts itself.
    pub contradictory: bool,
    /// True when the venue did not supply enough data to decide.
    pub insufficient: bool,
    pub authoritative: bool,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub enum OrderPresence {
    Found,
    NotFound,
    /// Transport/timeout/partial payload. Not evidence the order is absent.
    Unknown,
}

/// Venue-neutral reconciliation queries. Implementations must not invent
/// Kalshi endpoints; a paper/fake source is valid for M5.
pub trait VenueOpenOrders {
    fn list_open_orders(
        &self,
    ) -> Result<Vec<crate::venue::MappedOrderView>, crate::error::MomentoError>;
}

/// Optional venue-reported exposure. Kalshi may not provide an equivalent;
/// leave unimplemented rather than guessing.
pub trait VenueReportedExposure {
    fn reported_exposure(
        &self,
        ticker: &str,
    ) -> Result<Option<VenueExposureView>, crate::error::MomentoError>;
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct VenueExposureView {
    pub ticker: String,
    pub contracts: Option<Contracts>,
}

/// Authoritative settlement event. Proceeds are supplied by the caller from
/// verified venue data; this type does not compute Kalshi settlement math.
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct SettlementEvent {
    pub position_id: PositionId,
    pub game_id: GameId,
    pub proceeds: Money,
    pub exchange_ts: Option<ExchangeTimestamp>,
    pub received_at: ReceivedAt,
}
