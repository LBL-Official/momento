//! Kalshi adapter boundary.
//!
//! M8: demo/sandbox REST+WebSocket.
//! M9: production read-only authentication.
//! M10: production trading transport. Live arming is a config gate in the host.
//!
//! Official sources inspected for M4:
//! - https://docs.kalshi.com/getting_started/api_keys
//! - https://docs.kalshi.com/getting_started/quick_start_authenticated_requests
//! - https://docs.kalshi.com/getting_started/quick_start_create_order
//! - https://docs.kalshi.com/api-reference/orders/create-order-v2
//! - https://docs.kalshi.com/api-reference/orders/get-order
//! - https://docs.kalshi.com/api-reference/orders/get-orders
//! - https://docs.kalshi.com/api-reference/orders/cancel-order-v2
//! - https://docs.kalshi.com/api-reference/market/get-market
//! - https://docs.kalshi.com/getting_started/fixed_point_migration
//! - https://docs.kalshi.com/getting_started/fee_rounding
//! - https://docs.kalshi.com/getting_started/market_settlement
//! - https://docs.kalshi.com/getting_started/quick_start_websockets
//! - https://docs.kalshi.com/websockets/websocket-connection
//! - https://docs.kalshi.com/websockets/orderbook-updates
//! - https://docs.kalshi.com/websockets/user-fills
//! - https://docs.kalshi.com/api-reference/exchange/get-series-fee-changes
//! - https://docs.kalshi.com/getting_started/api_environments

#![forbid(unsafe_code)]

mod auth;
mod book;
mod http;
mod identity;
mod mapping;
mod parse;
mod production;
mod public_data;
mod redact;
mod sandbox;
mod secret;
mod transport;
mod types;
mod venue;
mod ws;

use momento_core::{
    ClientOrderId, Contracts, MomentoError, Order, ReconcileOutcome, UnknownOrder, VenueAccount,
    VenueMarketData, VenueOrders,
};

pub use auth::{
    ENV_KALSHI_ENV, ENV_KALSHI_KEY_ID, ENV_KALSHI_KEY_PATH, KalshiCredentials, KalshiEnvironment,
    SandboxCredentials, is_demo_url, is_production_url, refuse_if_demo, refuse_if_production,
    require_demo_env, require_host_matches_credentials, require_production_env,
};
pub use book::{
    ApplyResult, BookDepth, BookLevel, BookQuote, LocalOrderBook, SeqOutcome, SeqTracker,
};
pub use identity::{
    MarketBinding, StaticIdentity, VenueIdentity, game_id_for_event_ticker, market_id_for_ticker,
    stable_u128,
};
pub use mapping::{
    best_yes_bid_from_orderbook, decode_client_order_id, decode_venue_order_id,
    encode_client_order_id, encode_venue_order_id, is_http_not_found, map_fill, map_market,
    map_order, map_order_state, map_settlement, mapped_order_to_snapshot, not_found_snapshot,
    ts_ms,
};
pub use parse::{
    client_order_id_to_kalshi, count_fp_to_contracts, count_fp_to_hundredths,
    dollars_to_money_cents, dollars_to_price_cents, kalshi_to_u128, signature_payload,
    signed_count_fp_to_i64,
};
pub use production::{
    ProductionObserveTransport, ProductionReadOnlyTransport, ProductionTradingTransport,
    create_order_is_blocked, is_mutating_kalshi_request, production_observe_allows,
    production_read_only_allows, production_trading_allows,
};
pub use public_data::PublicMarketClient;
pub use redact::{is_secret_header, redact_header_value, redact_secrets};
pub use sandbox::{SandboxHttpTransport, SandboxWs};
pub use secret::{
    ENV_KALSHI_SECRET_ARN, ENV_KALSHI_SECRET_FILE, credentials_from_secret_file,
    credentials_from_secret_json,
};
pub use transport::{
    DisabledLiveTransport, KalshiHttpRequest, KalshiTransport, ScriptedTransport, TransportOutcome,
};
pub use types::{
    BALANCE_PATH, CREATE_ORDER_PATH, EVENTS_PATH, EXCHANGE_STATUS_PATH, FILLS_PATH,
    GetBalanceResponse, GetEventsResponse, GetFillsResponse, GetMarketCandlesticksResponse,
    GetMarketsResponse, GetOrderbookResponse, GetOrdersResponse, GetTradesResponse,
    HISTORICAL_CUTOFF_PATH, HISTORICAL_MARKETS_PATH, HISTORICAL_TRADES_PATH,
    HistoricalCutoffResponse, INTRA_TRANSFER_PATH, KalshiFill, KalshiMarket, KalshiTrade,
    MARKETS_PATH, MarketCandlestick, ORDERS_PATH, OrderbookDeltaMsg, OrderbookSnapshotMsg,
    POSITIONS_PATH, REST_DEMO, REST_DEMO_ORIGIN, REST_DEMO_SHARED, REST_DEMO_SHARED_ORIGIN,
    REST_PRODUCTION, REST_PRODUCTION_ORIGIN, SETTLEMENTS_PATH, SubscribedMsg, TRADES_PATH, WS_DEMO,
    WS_DEMO_SHARED, WS_PRODUCTION, WS_SIGN_PATH,
};
pub use venue::{KalshiVenue, ReduceOnlyAck};
pub use ws::{
    ProductionWs, WsDedupe, WsRead, parse_fill_msg, parse_orderbook_delta,
    parse_orderbook_snapshot, parse_subscribed, parse_ws_frame,
};

/// Marker for a production Kalshi **trading** transport. Not implemented in M9.
pub struct UnimplementedLiveKalshi {
    _private: (),
}

impl UnimplementedLiveKalshi {
    /// Live Kalshi is intentionally unconstructable in this milestone.
    pub fn connect_live() -> Result<Self, MomentoError> {
        Err(MomentoError::Config(
            momento_core::error::ConfigError::LiveNotImplemented,
        ))
    }
}

/// Trait bundle the live adapter must implement later.
pub trait KalshiAdapter:
    VenueMarketData + VenueOrders + VenueAccount + momento_core::VenueMarketDiscovery
{
}

impl<T> KalshiAdapter for T where
    T: VenueMarketData + VenueOrders + VenueAccount + momento_core::VenueMarketDiscovery
{
}

/// Documented surface the future HTTP/WS adapter must fill. Methods return
/// "not implemented" and must not be called from strategy or risk.
pub trait KalshiEventMarketApi {
    fn submit_post_only_entry(&mut self, order: &Order) -> Result<(), MomentoError>;
    fn cancel_order(&mut self, client_order_id: ClientOrderId) -> Result<(), MomentoError>;
    fn amend_order(
        &mut self,
        client_order_id: ClientOrderId,
        new_qty: Contracts,
    ) -> Result<(), MomentoError>;
    fn submit_reduce_only_liquidation(&mut self, order: &Order) -> Result<(), MomentoError>;
    fn reconcile(&mut self, unknown: &UnknownOrder) -> Result<ReconcileOutcome, MomentoError>;
}

pub struct UnimplementedEventMarketApi;

impl KalshiEventMarketApi for UnimplementedEventMarketApi {
    fn submit_post_only_entry(&mut self, _order: &Order) -> Result<(), MomentoError> {
        Err(MomentoError::Config(
            momento_core::error::ConfigError::LiveNotImplemented,
        ))
    }

    fn cancel_order(&mut self, _client_order_id: ClientOrderId) -> Result<(), MomentoError> {
        Err(MomentoError::Config(
            momento_core::error::ConfigError::LiveNotImplemented,
        ))
    }

    fn amend_order(
        &mut self,
        _client_order_id: ClientOrderId,
        _new_qty: Contracts,
    ) -> Result<(), MomentoError> {
        Err(MomentoError::Config(
            momento_core::error::ConfigError::LiveNotImplemented,
        ))
    }

    fn submit_reduce_only_liquidation(&mut self, _order: &Order) -> Result<(), MomentoError> {
        Err(MomentoError::Config(
            momento_core::error::ConfigError::LiveNotImplemented,
        ))
    }

    fn reconcile(&mut self, _unknown: &UnknownOrder) -> Result<ReconcileOutcome, MomentoError> {
        Err(MomentoError::Config(
            momento_core::error::ConfigError::LiveNotImplemented,
        ))
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn live_connect_is_impossible() {
        assert!(UnimplementedLiveKalshi::connect_live().is_err());
        let mut api = UnimplementedEventMarketApi;
        assert!(api.cancel_order(ClientOrderId::from_raw(1)).is_err());
    }
}
