//! Kalshi venue adapter. Mapping only. No live orders.

use std::collections::{HashMap, HashSet};

use momento_core::error::VenueError;
use momento_core::{
    ClientOrderId, Contracts, FillView, MappedOrderView, MarketEvent, MomentoError, Money, Order,
    OrderPurpose, PositionId, ReceivedAt, ReconcileOutcome, Side, UnknownOrder, VenueAccount,
    VenueFills, VenueMarketData, VenueMarketDiscovery, VenueMarketSnapshot, VenueOrderId,
    VenueOrderStatus, VenueOrders, VenueSettlement, VenueSettlementView,
};

use crate::identity::VenueIdentity;
use crate::mapping::{
    best_yes_bid_from_orderbook, decode_client_order_id, decode_venue_order_id,
    encode_client_order_id, encode_venue_order_id, map_fill, map_market, map_order, map_settlement,
};
use crate::parse::signature_payload;
use crate::transport::{KalshiHttpRequest, KalshiTransport, TransportOutcome};
use crate::types::{
    CREATE_ORDER_PATH, CreateOrderV2Request, CreateOrderV2Response, FILLS_PATH, GetFillsResponse,
    GetMarketResponse, GetMarketsResponse, GetOrderResponse, GetOrderbookResponse,
    GetOrdersResponse, HISTORICAL_CUTOFF_PATH, HistoricalCutoffResponse, KalshiFill, KalshiOrder,
    MARKETS_PATH, ORDERS_PATH, REST_PRODUCTION,
};

const RECONCILE_STATUSES: [&str; 3] = ["resting", "canceled", "executed"];
const RECONCILE_MAX_PAGES: usize = 20;
use crate::ws::WsDedupe;

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
enum AdapterAccess {
    Disabled,
    Scripted,
    Sandbox,
    Production,
}

/// Create V2 liquidation acknowledgement. IOC `remaining_count` is the
/// venue's final remainder after unfilled contracts are canceled.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct ReduceOnlyAck {
    pub venue_order_id: VenueOrderId,
    pub fill_count: Contracts,
    pub remaining_count: Contracts,
}

pub struct KalshiVenue<T, I> {
    transport: T,
    identity: I,
    access: AdapterAccess,
    received_at: ReceivedAt,
    unknown_submissions: HashSet<u128>,
    venue_by_client: HashMap<u128, VenueOrderId>,
    seen_fills: HashSet<String>,
    ws: WsDedupe,
}

impl<T: KalshiTransport, I: VenueIdentity> KalshiVenue<T, I> {
    pub fn disabled(transport: T, identity: I, received_at: ReceivedAt) -> Self {
        Self {
            transport,
            identity,
            access: AdapterAccess::Disabled,
            received_at,
            unknown_submissions: HashSet::new(),
            venue_by_client: HashMap::new(),
            seen_fills: HashSet::new(),
            ws: WsDedupe::new(),
        }
    }

    /// Test venue that consumes scripted HTTP/WS fixtures. Still cannot arm live trading.
    pub fn scripted(transport: T, identity: I, received_at: ReceivedAt) -> Self {
        Self {
            transport,
            identity,
            access: AdapterAccess::Scripted,
            received_at,
            unknown_submissions: HashSet::new(),
            venue_by_client: HashMap::new(),
            seen_fills: HashSet::new(),
            ws: WsDedupe::new(),
        }
    }

    /// Remote demo/sandbox venue. Must not be constructed with a production transport.
    pub fn sandbox(transport: T, identity: I, received_at: ReceivedAt) -> Self {
        Self {
            transport,
            identity,
            access: AdapterAccess::Sandbox,
            received_at,
            unknown_submissions: HashSet::new(),
            venue_by_client: HashMap::new(),
            seen_fills: HashSet::new(),
            ws: WsDedupe::new(),
        }
    }

    /// Production order venue. Caller must have armed live config separately.
    pub fn production(transport: T, identity: I, received_at: ReceivedAt) -> Self {
        Self {
            transport,
            identity,
            access: AdapterAccess::Production,
            received_at,
            unknown_submissions: HashSet::new(),
            venue_by_client: HashMap::new(),
            seen_fills: HashSet::new(),
            ws: WsDedupe::new(),
        }
    }

    pub fn signature_payload(timestamp_ms: &str, method: &str, path: &str) -> String {
        signature_payload(timestamp_ms, method, path)
    }

    pub fn production_rest_base() -> &'static str {
        REST_PRODUCTION
    }

    pub fn ws_dedupe(&mut self) -> &mut WsDedupe {
        &mut self.ws
    }

    pub fn identity_mut(&mut self) -> &mut I {
        &mut self.identity
    }

    pub fn identity(&self) -> &I {
        &self.identity
    }

    pub fn bind_seen_venue_order(&mut self, client: ClientOrderId, venue: VenueOrderId) {
        self.venue_by_client.insert(client.raw(), venue);
    }

    pub fn set_received_at(&mut self, received_at: ReceivedAt) {
        self.received_at = received_at;
    }

    pub fn venue_map_snapshot(&self) -> Vec<(u128, u128)> {
        self.venue_by_client
            .iter()
            .map(|(c, v)| (*c, v.raw()))
            .collect()
    }

    pub fn restore_venue_map(&mut self, pairs: Vec<(u128, u128)>) {
        for (client, venue) in pairs {
            self.venue_by_client
                .insert(client, VenueOrderId::from_raw(venue));
        }
    }

    pub fn unknown_snapshot(&self) -> Vec<u128> {
        self.unknown_submissions.iter().copied().collect()
    }

    pub fn restore_unknown_submissions(&mut self, ids: Vec<u128>) {
        self.unknown_submissions.extend(ids);
    }

    pub fn is_unknown(&self, id: ClientOrderId) -> bool {
        self.unknown_submissions.contains(&id.raw())
    }

    pub fn seen_fill(&self, id: &str) -> bool {
        self.seen_fills.contains(id)
    }

    fn require_orders(&self) -> Result<(), VenueError> {
        match self.access {
            AdapterAccess::Disabled => Err(VenueError::LiveDisabled),
            AdapterAccess::Scripted | AdapterAccess::Sandbox | AdapterAccess::Production => Ok(()),
        }
    }

    /// Liquidation ticker must match `order.market_id` via `ticker_for_market`.
    /// GameId lookup is never used as a fallback.
    fn require_liquidation_ticker(&self, order: &Order, ticker: &str) -> Result<(), MomentoError> {
        let Some(market_id) = order.market_id() else {
            return Err(VenueError::Unsupported(
                "liquidation missing MarketId; fail closed".into(),
            )
            .into());
        };
        let Some(side) = order.side() else {
            return Err(
                VenueError::Unsupported("liquidation missing side; fail closed".into()).into(),
            );
        };
        if side != Side::Yes {
            return Err(
                VenueError::Unsupported("liquidation side is not YES; fail closed".into()).into(),
            );
        }
        let Some(expected) = self.identity.ticker_for_market(market_id) else {
            return Err(VenueError::IdentityNotMapped(market_id.raw().to_string()).into());
        };
        if expected != ticker {
            return Err(VenueError::Unsupported(
                "liquidation ticker does not match position MarketId".into(),
            )
            .into());
        }
        Ok(())
    }

    pub fn submit_post_only(
        &mut self,
        order: &Order,
        ticker: &str,
    ) -> Result<VenueOrderId, MomentoError> {
        self.require_orders()?;
        if self
            .unknown_submissions
            .contains(&order.client_order_id().raw())
        {
            return Err(VenueError::AmbiguousSubmission.into());
        }
        if order.purpose() != OrderPurpose::Entry {
            return Err(VenueError::Unsupported("entry adapter only in M4".into()).into());
        }
        let req = CreateOrderV2Request {
            ticker: ticker.to_string(),
            client_order_id: encode_client_order_id(order.client_order_id()),
            side: "bid".into(),
            count: format!("{}.00", order.quantities().requested.get()),
            price: crate::parse::price_to_dollars(order.price()),
            time_in_force: "good_till_canceled".into(),
            self_trade_prevention_type: "taker_at_cross".into(),
            post_only: true,
            reduce_only: Some(false),
        };
        let body = serde_json::to_string(&req)
            .map_err(|e| VenueError::MalformedResponse(e.to_string()))?;
        match self.transport.execute(KalshiHttpRequest {
            method: "POST".into(),
            path: CREATE_ORDER_PATH.into(),
            body: Some(body),
        }) {
            TransportOutcome::Timeout => {
                self.unknown_submissions
                    .insert(order.client_order_id().raw());
                Err(VenueError::Timeout.into())
            }
            TransportOutcome::Http { status: 401, .. } => {
                Err(VenueError::AuthenticationFailed.into())
            }
            TransportOutcome::Http {
                status: status @ (400 | 404),
                body,
            } => Err(create_not_accepted("order", status, &body)),
            TransportOutcome::Http { status: 409, .. } => {
                self.unknown_submissions
                    .insert(order.client_order_id().raw());
                Err(VenueError::AmbiguousSubmission.into())
            }
            TransportOutcome::Http {
                status: 200 | 201,
                body,
            } => {
                let parsed = parse_create_order_body(&body)?;
                let immediate = crate::parse::count_fp_to_contracts(&parsed.fill_count)?;
                if immediate.get() > 0 {
                    return Err(VenueError::Unsupported(
                        "post-only create reported an immediate fill".into(),
                    )
                    .into());
                }
                let _ = (
                    parsed.remaining_count.as_str(),
                    parsed.ts_ms,
                    parsed.average_fill_price.as_ref(),
                    parsed.average_fee_paid.as_ref(),
                );
                if let Some(cid) = parsed.client_order_id.as_deref() {
                    if decode_client_order_id(cid)? != order.client_order_id() {
                        return Err(VenueError::MalformedResponse(
                            "client_order_id mismatch".into(),
                        )
                        .into());
                    }
                }
                let venue_id = decode_venue_order_id(&parsed.order_id)?;
                self.venue_by_client
                    .insert(order.client_order_id().raw(), venue_id);
                Ok(venue_id)
            }
            TransportOutcome::Http { status, body } => Err(VenueError::MalformedResponse(format!(
                "unexpected HTTP {status}: {body}"
            ))
            .into()),
        }
    }

    /// Official Create V2 reduce-only sell YES: `side=ask`, `post_only=false`,
    /// `reduce_only=true`, `time_in_force=immediate_or_cancel`.
    /// Immediate `fill_count` is not applied as a domain fill (fills arrive on
    /// the official fill stream). `remaining_count` is the IOC remainder after
    /// unfilled contracts are canceled.
    pub fn submit_reduce_only_liquidation_on(
        &mut self,
        order: &Order,
        ticker: &str,
    ) -> Result<ReduceOnlyAck, MomentoError> {
        self.require_orders()?;
        if self
            .unknown_submissions
            .contains(&order.client_order_id().raw())
        {
            return Err(VenueError::AmbiguousSubmission.into());
        }
        if order.purpose() != OrderPurpose::Liquidation {
            return Err(VenueError::Unsupported(
                "liquidation adapter requires liquidation purpose".into(),
            )
            .into());
        }
        self.require_liquidation_ticker(order, ticker)?;
        let req = CreateOrderV2Request {
            ticker: ticker.to_string(),
            client_order_id: encode_client_order_id(order.client_order_id()),
            side: "ask".into(),
            count: format!("{}.00", order.quantities().requested.get()),
            price: crate::parse::price_to_dollars(order.price()),
            time_in_force: "immediate_or_cancel".into(),
            self_trade_prevention_type: "taker_at_cross".into(),
            post_only: false,
            reduce_only: Some(true),
        };
        let body = serde_json::to_string(&req)
            .map_err(|e| VenueError::MalformedResponse(e.to_string()))?;
        match self.transport.execute(KalshiHttpRequest {
            method: "POST".into(),
            path: CREATE_ORDER_PATH.into(),
            body: Some(body),
        }) {
            TransportOutcome::Timeout => {
                self.unknown_submissions
                    .insert(order.client_order_id().raw());
                Err(VenueError::Timeout.into())
            }
            TransportOutcome::Http { status: 401, .. } => {
                Err(VenueError::AuthenticationFailed.into())
            }
            TransportOutcome::Http {
                status: status @ (400 | 404),
                body,
            } => Err(create_not_accepted("liquidation", status, &body)),
            TransportOutcome::Http { status: 409, .. } => {
                self.unknown_submissions
                    .insert(order.client_order_id().raw());
                Err(VenueError::AmbiguousSubmission.into())
            }
            TransportOutcome::Http {
                status: 200 | 201,
                body,
            } => {
                let parsed = parse_create_order_body(&body)?;
                let fill_count = crate::parse::count_fp_to_contracts(&parsed.fill_count)?;
                let remaining_count = crate::parse::count_fp_to_contracts(&parsed.remaining_count)?;
                if let Some(cid) = parsed.client_order_id.as_deref() {
                    if decode_client_order_id(cid)? != order.client_order_id() {
                        return Err(VenueError::MalformedResponse(
                            "client_order_id mismatch".into(),
                        )
                        .into());
                    }
                }
                let venue_id = decode_venue_order_id(&parsed.order_id)?;
                self.venue_by_client
                    .insert(order.client_order_id().raw(), venue_id);
                Ok(ReduceOnlyAck {
                    venue_order_id: venue_id,
                    fill_count,
                    remaining_count,
                })
            }
            TransportOutcome::Http { status, body } => Err(VenueError::MalformedResponse(format!(
                "unexpected HTTP {status}: {body}"
            ))
            .into()),
        }
    }

    pub fn get_orderbook_best_yes_bid(
        &mut self,
        ticker: &str,
    ) -> Result<Option<momento_core::Price>, MomentoError> {
        self.require_orders()?;
        match self.transport.execute(KalshiHttpRequest {
            method: "GET".into(),
            path: format!("/trade-api/v2/markets/{ticker}/orderbook"),
            body: None,
        }) {
            TransportOutcome::Timeout => Err(VenueError::Timeout.into()),
            TransportOutcome::Http { status: 401, .. } => {
                Err(VenueError::AuthenticationFailed.into())
            }
            TransportOutcome::Http { status: 200, body } => {
                let parsed: GetOrderbookResponse = serde_json::from_str(&body)
                    .map_err(|e| VenueError::MalformedResponse(e.to_string()))?;
                Ok(best_yes_bid_from_orderbook(&parsed)?)
            }
            TransportOutcome::Http { status, body } => Err(VenueError::MalformedResponse(format!(
                "orderbook HTTP {status}: {body}"
            ))
            .into()),
        }
    }

    pub fn get_market_with_settlement(
        &mut self,
        ticker: &str,
    ) -> Result<(VenueMarketSnapshot, VenueSettlementView), MomentoError> {
        let parsed = self.market_body(ticker)?;
        let binding = self.identity.lookup_ticker(&parsed.market.ticker);
        let snap = map_market(
            &parsed.market,
            self.received_at,
            binding.map(|b| b.market_id),
            binding.map(|b| b.game_id),
        )?;
        let settlement = map_settlement(&parsed.market)?;
        Ok((snap, settlement))
    }

    pub fn ingest_fill_json(
        &mut self,
        raw: &str,
        position_id: PositionId,
    ) -> Result<Option<FillView>, MomentoError> {
        let parsed: KalshiFill =
            serde_json::from_str(raw).map_err(|e| VenueError::MalformedResponse(e.to_string()))?;
        let (fill, venue_fill_id) = map_fill(&parsed, position_id, self.received_at)?;
        if !self.seen_fills.insert(venue_fill_id.clone()) {
            return Ok(None);
        }
        Ok(Some(FillView {
            fill,
            venue_fill_id,
        }))
    }

    fn market_body(&mut self, ticker: &str) -> Result<GetMarketResponse, MomentoError> {
        self.require_orders()?;
        match self.transport.execute(KalshiHttpRequest {
            method: "GET".into(),
            path: format!("/trade-api/v2/markets/{ticker}"),
            body: None,
        }) {
            TransportOutcome::Timeout => Err(VenueError::Timeout.into()),
            TransportOutcome::Http { status: 401, .. } => {
                Err(VenueError::AuthenticationFailed.into())
            }
            TransportOutcome::Http { status: 200, body } => serde_json::from_str(&body)
                .map_err(|e| VenueError::MalformedResponse(e.to_string()).into()),
            TransportOutcome::Http { status, body } => Err(VenueError::MalformedResponse(format!(
                "unexpected HTTP {status}: {body}"
            ))
            .into()),
        }
    }

    pub fn list_markets(&mut self, query: &str) -> Result<GetMarketsResponse, MomentoError> {
        self.require_orders()?;
        let path = if query.is_empty() {
            MARKETS_PATH.to_string()
        } else {
            format!("{MARKETS_PATH}?{query}")
        };
        match self.transport.execute(KalshiHttpRequest {
            method: "GET".into(),
            path,
            body: None,
        }) {
            TransportOutcome::Timeout => Err(VenueError::Timeout.into()),
            TransportOutcome::Http { status: 401, .. } => {
                Err(VenueError::AuthenticationFailed.into())
            }
            TransportOutcome::Http { status: 200, body } => serde_json::from_str(&body)
                .map_err(|e| VenueError::MalformedResponse(e.to_string()).into()),
            TransportOutcome::Http { status, body } => Err(VenueError::MalformedResponse(format!(
                "unexpected HTTP {status}: {body}"
            ))
            .into()),
        }
    }

    pub fn list_orders(&mut self, query: &str) -> Result<GetOrdersResponse, MomentoError> {
        self.require_orders()?;
        let path = if query.is_empty() {
            ORDERS_PATH.to_string()
        } else {
            format!("{ORDERS_PATH}?{query}")
        };
        match self.transport.execute(KalshiHttpRequest {
            method: "GET".into(),
            path,
            body: None,
        }) {
            TransportOutcome::Timeout => Err(VenueError::Timeout.into()),
            TransportOutcome::Http { status: 401, .. } => {
                Err(VenueError::AuthenticationFailed.into())
            }
            TransportOutcome::Http { status: 200, body } => serde_json::from_str(&body)
                .map_err(|e| VenueError::MalformedResponse(e.to_string()).into()),
            TransportOutcome::Http { status, body } => Err(VenueError::MalformedResponse(format!(
                "unexpected HTTP {status}: {body}"
            ))
            .into()),
        }
    }

    pub fn list_fills(&mut self, query: &str) -> Result<GetFillsResponse, MomentoError> {
        self.require_orders()?;
        let path = if query.is_empty() {
            FILLS_PATH.to_string()
        } else {
            format!("{FILLS_PATH}?{query}")
        };
        match self.transport.execute(KalshiHttpRequest {
            method: "GET".into(),
            path,
            body: None,
        }) {
            TransportOutcome::Timeout => Err(VenueError::Timeout.into()),
            TransportOutcome::Http { status: 401, .. } => {
                Err(VenueError::AuthenticationFailed.into())
            }
            TransportOutcome::Http { status: 200, body } => serde_json::from_str(&body)
                .map_err(|e| VenueError::MalformedResponse(e.to_string()).into()),
            TransportOutcome::Http { status, body } => Err(VenueError::MalformedResponse(format!(
                "unexpected HTTP {status}: {body}"
            ))
            .into()),
        }
    }

    /// Official live `GET /portfolio/orders` omits canceled/executed rows older
    /// than [`HistoricalCutoffResponse::orders_updated_ts`]. Those cannot be
    /// proven absent without historical orders, which this adapter does not
    /// call.
    fn live_orders_hide_client(
        &mut self,
        client_order_id: ClientOrderId,
    ) -> Result<bool, MomentoError> {
        self.require_orders()?;
        match self.transport.execute(KalshiHttpRequest {
            method: "GET".into(),
            path: HISTORICAL_CUTOFF_PATH.to_string(),
            body: None,
        }) {
            TransportOutcome::Timeout => Err(VenueError::Timeout.into()),
            TransportOutcome::Http { status: 401, .. } => {
                Err(VenueError::AuthenticationFailed.into())
            }
            TransportOutcome::Http { status: 200, body } => {
                let parsed: HistoricalCutoffResponse = serde_json::from_str(&body)
                    .map_err(|e| VenueError::MalformedResponse(e.to_string()))?;
                Ok(match parsed.orders_updated_ts {
                    Some(cutoff) => client_order_unix_secs(client_order_id) < cutoff,
                    None => false,
                })
            }
            TransportOutcome::Http { status, body } => Err(VenueError::MalformedResponse(format!(
                "unexpected HTTP {status}: {body}"
            ))
            .into()),
        }
    }

    fn find_client_order(
        &mut self,
        client_order_id: ClientOrderId,
        status: &str,
        min_ts: Option<i64>,
    ) -> Result<Option<KalshiOrder>, MomentoError> {
        let mut cursor: Option<String> = None;
        for _ in 0..RECONCILE_MAX_PAGES {
            let mut query = format!("status={status}&limit=1000");
            if let Some(ts) = min_ts {
                query.push_str(&format!("&min_ts={ts}"));
            }
            if let Some(c) = cursor.as_deref() {
                query.push_str("&cursor=");
                query.push_str(c);
            }
            let page = self.list_orders(&query)?;
            for order in page.orders {
                if decode_client_order_id(&order.client_order_id).ok() == Some(client_order_id) {
                    return Ok(Some(order));
                }
            }
            match page.cursor.filter(|c| !c.is_empty()) {
                Some(next) => cursor = Some(next),
                None => return Ok(None),
            }
        }
        Err(VenueError::MalformedResponse("reconcile list truncated".into()).into())
    }
}

impl<T: KalshiTransport, I: VenueIdentity> VenueMarketData for KalshiVenue<T, I> {
    fn poll_events(&mut self) -> Result<Vec<MarketEvent>, MomentoError> {
        Err(VenueError::Unsupported("live market-data poll is disabled in M4".into()).into())
    }
}

impl<T: KalshiTransport, I: VenueIdentity> VenueMarketDiscovery for KalshiVenue<T, I> {
    fn get_market(&mut self, ticker: &str) -> Result<VenueMarketSnapshot, MomentoError> {
        let parsed = self.market_body(ticker)?;
        let binding = self.identity.lookup_ticker(&parsed.market.ticker);
        Ok(map_market(
            &parsed.market,
            self.received_at,
            binding.map(|b| b.market_id),
            binding.map(|b| b.game_id),
        )?)
    }
}

impl<T: KalshiTransport, I: VenueIdentity> VenueOrderStatus for KalshiVenue<T, I> {
    fn get_order(&mut self, venue_order_id: VenueOrderId) -> Result<MappedOrderView, MomentoError> {
        self.require_orders()?;
        let id = encode_venue_order_id(venue_order_id);
        match self.transport.execute(KalshiHttpRequest {
            method: "GET".into(),
            path: format!("/trade-api/v2/portfolio/orders/{id}"),
            body: None,
        }) {
            TransportOutcome::Timeout => Err(VenueError::Timeout.into()),
            TransportOutcome::Http { status: 401, .. } => {
                Err(VenueError::AuthenticationFailed.into())
            }
            TransportOutcome::Http { status: 200, body } => {
                let parsed: GetOrderResponse = serde_json::from_str(&body)
                    .map_err(|e| VenueError::MalformedResponse(e.to_string()))?;
                Ok(map_order(&parsed.order)?)
            }
            TransportOutcome::Http { status: 404, body } => {
                Err(VenueError::MalformedResponse(format!("unexpected HTTP 404: {body}")).into())
            }
            TransportOutcome::Http { status, body } => Err(VenueError::MalformedResponse(format!(
                "unexpected HTTP {status}: {body}"
            ))
            .into()),
        }
    }
}

impl<T: KalshiTransport, I: VenueIdentity> VenueFills for KalshiVenue<T, I> {
    fn map_fill(
        &self,
        raw_json: &str,
        position_id: PositionId,
        received_at: ReceivedAt,
    ) -> Result<FillView, MomentoError> {
        let parsed: KalshiFill = serde_json::from_str(raw_json)
            .map_err(|e| VenueError::MalformedResponse(e.to_string()))?;
        let (fill, venue_fill_id) = map_fill(&parsed, position_id, received_at)?;
        Ok(FillView {
            fill,
            venue_fill_id,
        })
    }
}

impl<T: KalshiTransport, I: VenueIdentity> VenueSettlement for KalshiVenue<T, I> {
    fn get_settlement(&mut self, ticker: &str) -> Result<VenueSettlementView, MomentoError> {
        let parsed = self.market_body(ticker)?;
        Ok(map_settlement(&parsed.market)?)
    }
}

impl<T: KalshiTransport, I: VenueIdentity> VenueOrders for KalshiVenue<T, I> {
    fn submit_post_only_entry(&mut self, order: &Order) -> Result<(), MomentoError> {
        let ticker = self
            .identity
            .ticker_for_game(order.game_id())
            .ok_or_else(|| VenueError::IdentityNotMapped(order.game_id().raw().to_string()))?;
        self.submit_post_only(order, &ticker)?;
        Ok(())
    }

    fn cancel(&mut self, client_order_id: ClientOrderId) -> Result<(), MomentoError> {
        self.require_orders()?;
        if self.unknown_submissions.contains(&client_order_id.raw()) {
            return Err(VenueError::AmbiguousSubmission.into());
        }
        let Some(venue_id) = self.venue_by_client.get(&client_order_id.raw()).copied() else {
            return Err(VenueError::MalformedResponse("no venue order id".into()).into());
        };
        let path = format!(
            "/trade-api/v2/portfolio/events/orders/{}",
            encode_venue_order_id(venue_id)
        );
        match self.transport.execute(KalshiHttpRequest {
            method: "DELETE".into(),
            path,
            body: None,
        }) {
            TransportOutcome::Timeout => {
                self.unknown_submissions.insert(client_order_id.raw());
                Err(VenueError::Timeout.into())
            }
            TransportOutcome::Http { status: 200, body } => {
                let parsed: crate::types::CancelOrderV2Response = serde_json::from_str(&body)
                    .map_err(|e| VenueError::MalformedResponse(e.to_string()))?;
                let _ = crate::parse::count_fp_to_contracts(&parsed.reduced_by)?;
                let _ = (
                    parsed.order_id.as_str(),
                    parsed.ts_ms,
                    parsed.client_order_id.as_ref(),
                );
                Ok(())
            }
            TransportOutcome::Http { status: 404, .. } => {
                // Order is already gone. Idempotent cancel: not on the book.
                Ok(())
            }
            TransportOutcome::Http { status: 401, .. } => {
                Err(VenueError::AuthenticationFailed.into())
            }
            TransportOutcome::Http { status, body } => {
                Err(VenueError::MalformedResponse(format!("cancel HTTP {status}: {body}")).into())
            }
        }
    }

    fn amend(
        &mut self,
        _client_order_id: ClientOrderId,
        _new_qty: Contracts,
    ) -> Result<(), MomentoError> {
        Err(
            VenueError::Unsupported("amend validity across ClientOrderId is unresolved".into())
                .into(),
        )
    }

    fn submit_reduce_only_liquidation(&mut self, order: &Order) -> Result<(), MomentoError> {
        let market_id = order.market_id().ok_or_else(|| {
            VenueError::Unsupported("liquidation missing MarketId; fail closed".into())
        })?;
        let ticker = self
            .identity
            .ticker_for_market(market_id)
            .ok_or_else(|| VenueError::IdentityNotMapped(market_id.raw().to_string()))?;
        self.submit_reduce_only_liquidation_on(order, &ticker)?;
        Ok(())
    }

    fn reconcile_unknown(
        &mut self,
        unknown: &UnknownOrder,
    ) -> Result<ReconcileOutcome, MomentoError> {
        if let Some(venue_id) = self
            .venue_by_client
            .get(&unknown.client_order_id.raw())
            .copied()
        {
            match self.get_order(venue_id) {
                Ok(_) => {
                    self.unknown_submissions
                        .remove(&unknown.client_order_id.raw());
                    Ok(ReconcileOutcome::Found)
                }
                Err(MomentoError::Venue(
                    VenueError::Timeout | VenueError::UnknownVenueStatus(_),
                )) => Ok(ReconcileOutcome::Ambiguous),
                Err(ref err) if crate::is_http_not_found(err) => {
                    self.unknown_submissions
                        .remove(&unknown.client_order_id.raw());
                    Ok(ReconcileOutcome::NotFound)
                }
                Err(other) => Err(other),
            }
        } else {
            match self.live_orders_hide_client(unknown.client_order_id) {
                Ok(true) => return Ok(ReconcileOutcome::Ambiguous),
                Ok(false) => {}
                Err(MomentoError::Venue(
                    VenueError::Timeout | VenueError::UnknownVenueStatus(_),
                )) => return Ok(ReconcileOutcome::Ambiguous),
                Err(other) => return Err(other),
            }
            let min_ts = client_order_unix_secs(unknown.client_order_id).saturating_sub(2);
            for status in RECONCILE_STATUSES {
                let min = if status == "resting" {
                    None
                } else {
                    Some(min_ts)
                };
                match self.find_client_order(unknown.client_order_id, status, min) {
                    Ok(Some(order)) => {
                        let venue_id = decode_venue_order_id(&order.order_id)?;
                        self.venue_by_client
                            .insert(unknown.client_order_id.raw(), venue_id);
                        self.unknown_submissions
                            .remove(&unknown.client_order_id.raw());
                        return Ok(ReconcileOutcome::Found);
                    }
                    Ok(None) => {}
                    Err(MomentoError::Venue(
                        VenueError::Timeout | VenueError::UnknownVenueStatus(_),
                    )) => return Ok(ReconcileOutcome::Ambiguous),
                    Err(MomentoError::Venue(VenueError::MalformedResponse(ref s)))
                        if s.contains("reconcile list truncated") =>
                    {
                        return Ok(ReconcileOutcome::Ambiguous);
                    }
                    Err(other) => return Err(other),
                }
            }
            self.unknown_submissions
                .remove(&unknown.client_order_id.raw());
            Ok(ReconcileOutcome::NotFound)
        }
    }
}

impl<T: KalshiTransport, I: VenueIdentity> VenueAccount for KalshiVenue<T, I> {
    fn available_balance(&self) -> Result<Money, MomentoError> {
        Err(VenueError::Unsupported("live available balance is unresolved for M4".into()).into())
    }

    fn venue_order_id(
        &self,
        client_order_id: ClientOrderId,
    ) -> Result<Option<VenueOrderId>, MomentoError> {
        Ok(self.venue_by_client.get(&client_order_id.raw()).copied())
    }
}

fn parse_create_order_body(body: &str) -> Result<CreateOrderV2Response, VenueError> {
    if let Ok(parsed) = serde_json::from_str::<CreateOrderV2Response>(body) {
        return Ok(parsed);
    }
    #[derive(serde::Deserialize)]
    struct Wrap {
        order: crate::types::KalshiOrder,
    }
    let wrap: Wrap =
        serde_json::from_str(body).map_err(|e| VenueError::MalformedResponse(e.to_string()))?;
    Ok(CreateOrderV2Response {
        order_id: wrap.order.order_id,
        client_order_id: Some(wrap.order.client_order_id),
        fill_count: wrap.order.fill_count_fp,
        remaining_count: wrap.order.remaining_count_fp,
        ts_ms: 0,
        average_fill_price: wrap.order.yes_price_dollars,
        average_fee_paid: wrap.order.taker_fees_dollars,
    })
}

fn create_not_accepted(kind: &str, status: u16, body: &str) -> MomentoError {
    VenueError::Unsupported(format!(
        "{kind} rejected by venue HTTP {status}: {}",
        crate::redact::redact_secrets(body)
    ))
    .into()
}

fn client_order_unix_secs(id: ClientOrderId) -> i64 {
    i64::try_from(id.raw() / 1_000_000_000).unwrap_or(0)
}
