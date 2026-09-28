//! Production MLB live host. Requires explicit live arming.
//!
//! YES bid → 80/81 → Risk → production Create V2 entry.
//! Actual fills → 50% VWAP stop → production reduce-only IOC liquidation.
//! Venue-provided settlement proceeds only. Does not invent mid or fees.

use std::collections::{HashMap, HashSet};
use std::fs;
use std::io::Write;
use std::path::{Path, PathBuf};
use std::time::{Duration, Instant};

use momento_core::error::VenueError;
use momento_core::snapshot::belongs_to_week;
use momento_core::{
    ApprovedTradeIntent, AuditEvent, Bps, ClientOrderId, EntryPriceGate, ExchangeTimestamp,
    FeeKind, GameId, KillSwitch, LIVE_CONFIRMATION, MarketEvent, MomentoError, Money, Order,
    OrderPurpose, OrderState, Position, PositionLifecycle, PositionSizingMode, Price, ReceivedAt,
    ReconcileOutcome, ReconciliationState, RiskDecision, SettlementEvent, Side, SnapshotSource,
    StrategyId, TradingConfig, TradingMode, UnknownOrder, VenueAccount, VenueMarketSnapshot,
    VenueOrderId, VenueOrderStatus, VenueOrders, VenueSettlementView, WeeklyBankrollSnapshot,
    utc_now,
};
use momento_kalshi::{
    ApplyResult, BALANCE_PATH, BookQuote, ENV_KALSHI_ENV, EXCHANGE_STATUS_PATH, GetBalanceResponse,
    KalshiCredentials, KalshiEnvironment, KalshiFill, KalshiHttpRequest, KalshiTransport,
    KalshiVenue, LocalOrderBook, MARKETS_PATH, MarketBinding, ProductionReadOnlyTransport,
    ProductionTradingTransport, ProductionWs, REST_PRODUCTION, StaticIdentity, TransportOutcome,
    VenueIdentity, WsRead, count_fp_to_contracts, count_fp_to_hundredths,
    credentials_from_secret_file, decode_client_order_id, decode_venue_order_id,
    encode_client_order_id, encode_venue_order_id, game_id_for_event_ticker, is_http_not_found,
    map_fill, map_market, mapped_order_to_snapshot, market_id_for_ticker, not_found_snapshot,
    parse_fill_msg, parse_orderbook_delta, parse_orderbook_snapshot, parse_subscribed,
    parse_ws_frame, redact_secrets, refuse_if_demo, ts_ms,
};
use momento_positions::{
    ApplyStatus, InMemoryPositionTracker, PositionEvent, PositionTracker, TrackerPersist,
};
use momento_risk::{PaperRiskEngine, RiskConfig, RiskPersist};
use momento_strategy_mlb::{MLB_STRATEGY_ID, MlbContext, MlbDirective, MlbStrategy, StopExecution};
use momento_strategy_wnba::{WNBA_STRATEGY_ID, WnbaStrategy};
use serde::{Deserialize, Serialize};

use crate::runtime::{
    HostError, heartbeat_period, load_live_config, persist_strategy, persist_wnba_strategy,
    restore_strategy, restore_wnba_strategy,
};

pub const MLB_SERIES_TICKER: &str = "KXMLBGAME";
/// Confirmed from Kalshi production GET /series: Women's Pro Basketball Game.
pub const WNBA_SERIES_TICKER: &str = "KXWNBAGAME";
pub const KILL_FILE_NAME: &str = "KILL";
pub const SNAPSHOT_FILE_NAME: &str = "weekly-snapshot.json";
pub const LIVE_STATE_FILE_NAME: &str = "live-runtime.json";
pub const AUDIT_FILE_NAME: &str = "audit.jsonl";
const FILL_INGEST_PAGE_LIMIT: u32 = 100;
const FILL_INGEST_MAX_PAGES: usize = 20;

const MAX_ENTRY: u16 = 83;
/// $50 × 833 bps = 416 cents via truncating integer division. Exact 8.33% is $4.165.
const WNBA_PER_GAME_CENTS: i64 = 416;
const DISCOVERY_SECS: u64 = 30;
const WS_RECONNECT_MIN: Duration = Duration::from_secs(1);
const WS_RECONNECT_MAX: Duration = Duration::from_secs(30);

#[derive(Clone, Debug, Serialize, Deserialize)]
struct LiveRuntimeFile {
    tracker: TrackerPersist,
    risk: RiskPersist,
    venue_by_client: Vec<(u128, u128)>,
    unknown_submissions: Vec<u128>,
    #[serde(default)]
    identity: Vec<(String, u128, u128)>,
}

pub fn kill_file(state_dir: &Path) -> PathBuf {
    state_dir.join(KILL_FILE_NAME)
}

pub fn snapshot_file(state_dir: &Path) -> PathBuf {
    state_dir.join(SNAPSHOT_FILE_NAME)
}

pub fn live_state_file(state_dir: &Path) -> PathBuf {
    state_dir.join(LIVE_STATE_FILE_NAME)
}

pub fn kill_switch_requested(state_dir: &Path) -> bool {
    if kill_file(state_dir).exists() {
        return true;
    }
    match std::env::var("MOMENTO_KILL_SWITCH") {
        Ok(v) => matches!(
            v.trim().to_ascii_lowercase().as_str(),
            "1" | "true" | "on" | "tripped"
        ),
        Err(_) => false,
    }
}

pub fn aws_region() -> Option<String> {
    ["MOMENTO_AWS_REGION", "AWS_REGION", "AWS_DEFAULT_REGION"]
        .into_iter()
        .find_map(|k| std::env::var(k).ok().filter(|v| !v.trim().is_empty()))
}

pub fn paper_mode_cannot_submit_production(cfg: &TradingConfig) -> bool {
    matches!(cfg.mode, TradingMode::Paper | TradingMode::Replay)
}

pub fn live_without_confirmation_cannot_submit(cfg: &TradingConfig) -> bool {
    cfg.mode == TradingMode::Live && cfg.live.confirmation != LIVE_CONFIRMATION
}

pub fn entry_price_exceeds_max(price: Price, max: Price) -> bool {
    price > max
}

pub fn risk_approval_is_mandatory(decision: &RiskDecision) -> bool {
    matches!(decision, RiskDecision::Approved(_))
}

/// Production market-data → strategy event.
///
/// Path:
/// Kalshi WebSocket `orderbook_snapshot` / `orderbook_delta`
/// → local book best YES bid (and implied YES ask from best NO bid)
/// → this constructor (`MarketEvent.bid` is the MLB qualifying price).
///
/// REST `GET /markets` remains for discovery, bootstrap timestamps,
/// held-position settlement, and recovery. Last is never the 80/81/89 input.
/// `mid` stays `None`.
pub fn live_market_event_from_snapshot(snap: VenueMarketSnapshot) -> Option<MarketEvent> {
    let game_id = snap.game_id?;
    let market_id = snap.market_id?;
    let exchange_ts = snap.exchange_ts?;
    Some(MarketEvent {
        game_id,
        market_id,
        side: Some(Side::Yes),
        exchange_ts,
        received_at: snap.received_at,
        last: snap.last,
        bid: snap.bid,
        ask: snap.ask,
        mid: snap.mid,
        bid_depth: snap.bid_depth,
        ask_depth: snap.ask_depth,
        game_state: None,
    })
}

/// Local-book quote → strategy event. Qualifying price is best YES bid.
/// Last is omitted. Mid stays `None`.
pub fn live_market_event_from_book(
    binding: MarketBinding,
    quote: BookQuote,
    exchange_ts: ExchangeTimestamp,
    received_at: ReceivedAt,
) -> MarketEvent {
    MarketEvent {
        game_id: binding.game_id,
        market_id: binding.market_id,
        side: Some(Side::Yes),
        exchange_ts,
        received_at,
        last: None,
        bid: Some(quote.yes_bid),
        ask: Some(quote.yes_ask),
        mid: None,
        bid_depth: quote.yes_bid_depth,
        ask_depth: quote.yes_ask_depth,
        game_state: None,
    }
}

struct LiveDesk {
    mlb: MlbStrategy,
    wnba: WnbaStrategy,
}

impl LiveDesk {
    fn strategy_mut(&mut self, strategy_id: StrategyId) -> Option<&mut MlbStrategy> {
        if strategy_id == MLB_STRATEGY_ID {
            Some(&mut self.mlb)
        } else if strategy_id == WNBA_STRATEGY_ID {
            Some(self.wnba.inner_mut())
        } else {
            None
        }
    }

    fn for_ticker_mut(&mut self, ticker: &str) -> Option<(&mut MlbStrategy, StrategyId)> {
        if ticker.starts_with(WNBA_SERIES_TICKER) {
            Some((self.wnba.inner_mut(), WNBA_STRATEGY_ID))
        } else if ticker.starts_with(MLB_SERIES_TICKER) {
            Some((&mut self.mlb, MLB_STRATEGY_ID))
        } else {
            None
        }
    }
}

pub(crate) fn per_game_budget(snapshot: &WeeklyBankrollSnapshot, strategy_id: StrategyId) -> Money {
    if strategy_id == StrategyId::MLB || strategy_id == StrategyId::RESEARCH_ITI {
        return snapshot.max_position_budget();
    }
    if strategy_id == StrategyId::WNBA {
        return snapshot
            .bankroll()
            .checked_mul_bps(Bps::PCT_8_33)
            .unwrap_or(Money::ZERO);
    }
    Money::ZERO
}

fn capture_policy_snapshot(cfg: &TradingConfig) -> Result<WeeklyBankrollSnapshot, HostError> {
    let now = utc_now();
    let source = match cfg.sizing_mode {
        PositionSizingMode::PctCurrent => SnapshotSource::AccountBalance,
        _ => SnapshotSource::ConfiguredInitial,
    };
    match cfg.sizing_mode {
        PositionSizingMode::FixedCents => {
            let cents = cfg.max_position_budget_cents.unwrap_or(0);
            if cents <= 0 {
                return Err(HostError::Config(
                    "FIXED_CENTS requires max_position_budget_cents > 0".into(),
                ));
            }
            WeeklyBankrollSnapshot::capture_with_budget(
                cfg.initial_bankroll(),
                cfg.allocation(),
                Money::from_cents(cents),
                now,
                source,
            )
        }
        _ => WeeklyBankrollSnapshot::capture(cfg.initial_bankroll(), cfg.allocation(), now, source),
    }
    .map_err(|e| HostError::Config(e.to_string()))
}

fn expected_policy_budget(cfg: &TradingConfig) -> Result<Money, HostError> {
    match cfg.sizing_mode {
        PositionSizingMode::FixedCents => {
            let cents = cfg.max_position_budget_cents.unwrap_or(0);
            if cents <= 0 {
                return Err(HostError::Config(
                    "FIXED_CENTS requires max_position_budget_cents > 0".into(),
                ));
            }
            Ok(Money::from_cents(cents))
        }
        _ => cfg
            .initial_bankroll()
            .checked_mul_bps(cfg.allocation())
            .map_err(|e| HostError::Config(e.to_string())),
    }
}

fn position_is_open(position: &Position) -> bool {
    position.filled_quantity().get() > 0
        && !matches!(
            position.lifecycle(),
            PositionLifecycle::Settled | PositionLifecycle::Flat
        )
}

/// Test/host entry into the live observe → Risk → submit path.
/// Does not itself open a Kalshi socket; the venue transport decides that.
#[allow(clippy::too_many_arguments)]
pub fn observe_live_event<T: KalshiTransport, I: VenueIdentity>(
    state_dir: &Path,
    cfg: &TradingConfig,
    strategy: &mut MlbStrategy,
    tracker: &mut InMemoryPositionTracker,
    risk: &PaperRiskEngine,
    venue: &mut KalshiVenue<T, I>,
    snapshot: &WeeklyBankrollSnapshot,
    event: MarketEvent,
) {
    observe_one(
        state_dir,
        cfg,
        strategy,
        MLB_STRATEGY_ID,
        tracker,
        risk,
        venue,
        snapshot,
        event,
    )
}

pub fn poll_live_mlb_markets<T: KalshiTransport>(
    venue: &mut KalshiVenue<T, StaticIdentity>,
    received_at: ReceivedAt,
) -> Result<Vec<MarketEvent>, HostError> {
    poll_mlb_markets(venue, received_at)
}

pub fn run_live(config_path: &Path, state_dir: &Path) -> Result<(), HostError> {
    let cfg = load_live_config(config_path)?;
    eprintln!(
        "momento-trading-engine start config={} state_dir={} mode={:?} live.enabled={} live_implemented=true confirmation_set={} order_submission=enabled liquidation=enabled stop_monitor=active live_capable=true",
        config_path.display(),
        state_dir.display(),
        cfg.mode,
        cfg.live.enabled,
        cfg.live.confirmation == LIVE_CONFIRMATION
    );

    let creds = load_production_credentials()?;
    preflight(&cfg, state_dir, &creds)?;

    let snapshot = load_or_create_snapshot(&cfg, state_dir)?;
    let risk_config =
        RiskConfig::from_trading_config(&cfg).map_err(|e| HostError::Config(e.to_string()))?;
    let (tracker, risk, mut venue_by_client, mut unknown_submissions, identity_bindings) =
        if live_state_file(state_dir).exists() {
            let persist = load_runtime(state_dir)?;
            let tracker = InMemoryPositionTracker::restore_persist(persist.tracker);
            let risk = PaperRiskEngine::restore(persist.risk, risk_config);
            risk.adopt_fill_authoritative_occupancy(tracker.positions());
            (
                tracker,
                risk,
                persist.venue_by_client,
                persist.unknown_submissions,
                persist.identity,
            )
        } else {
            (
                InMemoryPositionTracker::new(),
                PaperRiskEngine::paper(snapshot.clone(), risk_config),
                Vec::new(),
                Vec::new(),
                Vec::new(),
            )
        };
    let desk = LiveDesk {
        mlb: restore_strategy(state_dir)?,
        wnba: restore_wnba_strategy(state_dir)?,
    };
    let transport = ProductionTradingTransport::production(creds.clone())
        .map_err(|e| HostError::Venue(e.to_string()))?;
    let mut identity = StaticIdentity::new();
    for (ticker, market_id, game_id) in identity_bindings {
        identity.bind(
            ticker,
            MarketBinding {
                market_id: momento_core::MarketId::from_raw(market_id),
                game_id: GameId::from_raw(game_id),
                position_id: None,
            },
        );
    }
    let mut venue = KalshiVenue::production(transport, identity, ReceivedAt::from_utc(utc_now()));
    venue.restore_venue_map(std::mem::take(&mut venue_by_client));
    venue.restore_unknown_submissions(std::mem::take(&mut unknown_submissions));
    run_loop(cfg, state_dir, snapshot, desk, tracker, risk, venue, creds)
}

struct LiveWs {
    socket: Option<ProductionWs>,
    book: LocalOrderBook,
    open_tickers: HashSet<String>,
    subscribed_tickers: HashSet<String>,
    orderbook_sid: Option<u64>,
    fill_sid: Option<u64>,
    last_quotes: HashMap<String, (u16, u16)>,
    rest_exchange_ts: HashMap<String, ExchangeTimestamp>,
    reconnect_at: Instant,
    backoff: Duration,
    last_recv_to_book_us: u64,
    last_book_to_observe_us: u64,
    observed: HashSet<GameId>,
}

impl LiveWs {
    fn new() -> Self {
        Self {
            socket: None,
            book: LocalOrderBook::new(),
            open_tickers: HashSet::new(),
            subscribed_tickers: HashSet::new(),
            orderbook_sid: None,
            fill_sid: None,
            last_quotes: HashMap::new(),
            rest_exchange_ts: HashMap::new(),
            reconnect_at: Instant::now(),
            backoff: WS_RECONNECT_MIN,
            last_recv_to_book_us: 0,
            last_book_to_observe_us: 0,
            observed: HashSet::new(),
        }
    }

    fn market_data_ok(&self) -> bool {
        self.socket.is_some() && !self.book.has_gap()
    }

    fn drop_socket(&mut self, reason: &str) {
        if let Some(sock) = self.socket.take() {
            sock.close();
        }
        self.book.clear();
        self.subscribed_tickers.clear();
        self.orderbook_sid = None;
        self.fill_sid = None;
        self.last_quotes.clear();
        self.backoff = self.backoff.saturating_mul(2).min(WS_RECONNECT_MAX);
        self.reconnect_at = Instant::now() + self.backoff;
        eprintln!(
            "momento ws_disconnected reason={} retry_ms={} flatten=false new_entry_blocked_until_resync=true",
            redact_secrets(reason),
            self.backoff.as_millis()
        );
    }
}

#[allow(clippy::too_many_arguments)]
fn run_loop(
    cfg: TradingConfig,
    state_dir: &Path,
    mut snapshot: WeeklyBankrollSnapshot,
    mut desk: LiveDesk,
    mut tracker: InMemoryPositionTracker,
    risk: PaperRiskEngine,
    mut venue: KalshiVenue<ProductionTradingTransport, StaticIdentity>,
    creds: KalshiCredentials,
) -> Result<(), HostError> {
    snapshot = ensure_weekly_snapshot(&cfg, state_dir, snapshot, &risk, &mut tracker)?;
    persist_all(state_dir, &desk, &tracker, &risk, &venue)?;
    let mut ws = LiveWs::new();
    let mut last_housekeeping = Instant::now()
        .checked_sub(heartbeat_period())
        .unwrap_or_else(Instant::now);
    let mut last_discovery = Instant::now()
        .checked_sub(Duration::from_secs(DISCOVERY_SECS))
        .unwrap_or_else(Instant::now);

    loop {
        snapshot = ensure_weekly_snapshot(&cfg, state_dir, snapshot, &risk, &mut tracker)?;
        if kill_switch_requested(state_dir) {
            risk.trip_kill_switch();
            eprintln!("momento kill_switch=TRIPPED new_entry_blocked=true flatten=false");
        }

        if ws.socket.is_none() && Instant::now() >= ws.reconnect_at {
            connect_production_ws(&creds, &mut ws);
        }

        let incoming = ws.socket.as_mut().map(|socket| socket.read());
        match incoming {
            Some(Ok(WsRead::Text(text))) => {
                let received = Instant::now();
                if let Err(err) = handle_ws_text(
                    state_dir,
                    &cfg,
                    &mut desk,
                    &mut tracker,
                    &risk,
                    &mut venue,
                    &snapshot,
                    &mut ws,
                    &text,
                    received,
                ) {
                    ws.drop_socket(&err.to_string());
                }
            }
            Some(Ok(WsRead::Idle)) | None => {}
            Some(Err(err)) => ws.drop_socket(&err.to_string()),
        }

        let now = Instant::now();
        if now.duration_since(last_discovery) >= Duration::from_secs(DISCOVERY_SECS) {
            let received_at = ReceivedAt::from_utc(utc_now());
            venue.set_received_at(received_at);
            match discover_open_markets(&mut venue, received_at, &mut ws.rest_exchange_ts) {
                Ok(tickers) => {
                    ws.open_tickers = tickers;
                    sync_ws_markets(&mut ws);
                    last_discovery = now;
                }
                Err(err) => {
                    eprintln!(
                        "momento market_discovery_error={}",
                        redact_secrets(&err.to_string())
                    );
                    last_discovery = now;
                }
            }
        }

        if now.duration_since(last_housekeeping) >= heartbeat_period() {
            run_desk_housekeeping(
                state_dir,
                &cfg,
                &mut desk,
                &mut tracker,
                &risk,
                &mut venue,
                &snapshot,
                &ws.observed,
            );
            persist_all(state_dir, &desk, &tracker, &risk, &venue)?;
            let market_data_ok = ws.market_data_ok();
            eprintln!(
                "{} ws={} books={} orderbook_sid={} fill_sid={} recv_to_book_us={} book_to_observe_us={}",
                live_heartbeat(
                    &cfg,
                    &tracker,
                    &risk,
                    &desk.mlb,
                    &desk.wnba,
                    ws.book.market_count(),
                    market_data_ok
                ),
                if ws.socket.is_some() {
                    "connected"
                } else {
                    "disconnected"
                },
                ws.book.market_count(),
                ws.orderbook_sid
                    .map(|s| s.to_string())
                    .unwrap_or_else(|| "none".into()),
                ws.fill_sid
                    .map(|s| s.to_string())
                    .unwrap_or_else(|| "none".into()),
                ws.last_recv_to_book_us,
                ws.last_book_to_observe_us
            );
            ws.observed.clear();
            last_housekeeping = now;
        }
    }
}

fn connect_production_ws(creds: &KalshiCredentials, ws: &mut LiveWs) {
    match ProductionWs::connect(creds) {
        Ok(mut socket) => {
            if let Err(err) = socket.subscribe_fills() {
                eprintln!(
                    "momento ws_fill_subscribe_failed={}",
                    redact_secrets(&err.to_string())
                );
                ws.backoff = ws.backoff.saturating_mul(2).min(WS_RECONNECT_MAX);
                ws.reconnect_at = Instant::now() + ws.backoff;
                socket.close();
                return;
            }
            let tickers: Vec<String> = ws.open_tickers.iter().cloned().collect();
            if !tickers.is_empty() {
                if let Err(err) = socket.subscribe_orderbook(&tickers) {
                    eprintln!(
                        "momento ws_orderbook_subscribe_failed={}",
                        redact_secrets(&err.to_string())
                    );
                    ws.backoff = ws.backoff.saturating_mul(2).min(WS_RECONNECT_MAX);
                    ws.reconnect_at = Instant::now() + ws.backoff;
                    socket.close();
                    return;
                }
                ws.subscribed_tickers = ws.open_tickers.clone();
            }
            ws.book.clear();
            ws.last_quotes.clear();
            ws.backoff = WS_RECONNECT_MIN;
            ws.socket = Some(socket);
            eprintln!(
                "momento ws_connected=true url=production fill=subscribed orderbook_tickers={}",
                ws.subscribed_tickers.len()
            );
        }
        Err(err) => {
            ws.backoff = ws.backoff.saturating_mul(2).min(WS_RECONNECT_MAX);
            ws.reconnect_at = Instant::now() + ws.backoff;
            eprintln!(
                "momento ws_connect_failed={} retry_ms={} flatten=false",
                redact_secrets(&err.to_string()),
                ws.backoff.as_millis()
            );
        }
    }
}

fn sync_ws_markets(ws: &mut LiveWs) {
    if ws.socket.is_none() {
        return;
    }
    let to_add: Vec<String> = ws
        .open_tickers
        .difference(&ws.subscribed_tickers)
        .cloned()
        .collect();
    let to_del: Vec<String> = ws
        .subscribed_tickers
        .difference(&ws.open_tickers)
        .cloned()
        .collect();
    if let Some(sid) = ws.orderbook_sid {
        if !to_add.is_empty() {
            let added = ws
                .socket
                .as_mut()
                .map(|socket| socket.add_markets(sid, &to_add));
            match added {
                Some(Ok(_)) => {
                    eprintln!("momento ws_add_markets n={}", to_add.len());
                    ws.subscribed_tickers.extend(to_add);
                }
                Some(Err(err)) => eprintln!(
                    "momento ws_add_markets_failed={}",
                    redact_secrets(&err.to_string())
                ),
                None => {}
            }
        }
        if !to_del.is_empty() {
            let deleted = ws
                .socket
                .as_mut()
                .map(|socket| socket.delete_markets(sid, &to_del));
            match deleted {
                Some(Ok(_)) => {
                    for ticker in &to_del {
                        ws.subscribed_tickers.remove(ticker);
                        ws.book.remove(ticker);
                        ws.last_quotes.remove(ticker);
                    }
                    eprintln!("momento ws_delete_markets n={}", to_del.len());
                }
                Some(Err(err)) => eprintln!(
                    "momento ws_delete_markets_failed={}",
                    redact_secrets(&err.to_string())
                ),
                None => {}
            }
        }
        return;
    }
    if ws.subscribed_tickers.is_empty() && !ws.open_tickers.is_empty() {
        let tickers: Vec<String> = ws.open_tickers.iter().cloned().collect();
        let subscribed = ws
            .socket
            .as_mut()
            .map(|socket| socket.subscribe_orderbook(&tickers));
        match subscribed {
            Some(Ok(_)) => {
                ws.subscribed_tickers = ws.open_tickers.clone();
                eprintln!("momento ws_orderbook_subscribe tickers={}", tickers.len());
            }
            Some(Err(err)) => eprintln!(
                "momento ws_orderbook_subscribe_failed={}",
                redact_secrets(&err.to_string())
            ),
            None => {}
        }
    }
}

#[allow(clippy::too_many_arguments)]
fn handle_ws_text<T: KalshiTransport, I: VenueIdentity>(
    state_dir: &Path,
    cfg: &TradingConfig,
    desk: &mut LiveDesk,
    tracker: &mut InMemoryPositionTracker,
    risk: &PaperRiskEngine,
    venue: &mut KalshiVenue<T, I>,
    snapshot: &WeeklyBankrollSnapshot,
    ws: &mut LiveWs,
    raw: &str,
    received: Instant,
) -> Result<(), VenueError> {
    let env = parse_ws_frame(raw)?;
    match env.msg_type.as_str() {
        "subscribed" => {
            let msg = parse_subscribed(&env)?;
            match msg.channel.as_str() {
                "orderbook_delta" => {
                    ws.orderbook_sid = Some(msg.sid);
                    eprintln!(
                        "momento ws_subscribed channel=orderbook_delta sid={}",
                        msg.sid
                    );
                }
                "fill" => {
                    ws.fill_sid = Some(msg.sid);
                    eprintln!("momento ws_subscribed channel=fill sid={}", msg.sid);
                }
                other => eprintln!("momento ws_subscribed channel={other} sid={}", msg.sid),
            }
            Ok(())
        }
        "orderbook_snapshot" => {
            let sid = env
                .sid
                .ok_or_else(|| VenueError::MalformedResponse("snapshot missing sid".into()))?;
            let seq = env
                .seq
                .ok_or_else(|| VenueError::MalformedResponse("snapshot missing seq".into()))?;
            let msg = parse_orderbook_snapshot(&env)?;
            match ws.book.apply_snapshot(sid, seq, &msg) {
                Err(err) => {
                    eprintln!(
                        "momento book_skipped ticker={} err={}",
                        msg.market_ticker,
                        redact_secrets(&err.to_string())
                    );
                    Ok(())
                }
                Ok(ApplyResult::Gap) => Err(VenueError::MalformedResponse(
                    "orderbook sequence gap".into(),
                )),
                Ok(ApplyResult::Updated { ticker, quote }) => {
                    ws.last_recv_to_book_us =
                        u64::try_from(received.elapsed().as_micros()).unwrap_or(u64::MAX);
                    if let Some(quote) = quote {
                        observe_book_quote(
                            state_dir, cfg, desk, tracker, risk, venue, snapshot, ws, &ticker,
                            quote,
                        );
                    }
                    Ok(())
                }
                Ok(ApplyResult::Ignored | ApplyResult::Unready { .. }) => Ok(()),
            }
        }
        "orderbook_delta" => {
            let sid = env
                .sid
                .ok_or_else(|| VenueError::MalformedResponse("delta missing sid".into()))?;
            let seq = env
                .seq
                .ok_or_else(|| VenueError::MalformedResponse("delta missing seq".into()))?;
            let msg = parse_orderbook_delta(&env)?;
            match ws.book.apply_delta(sid, seq, &msg) {
                Err(err) => {
                    eprintln!(
                        "momento book_skipped ticker={} err={}",
                        msg.market_ticker,
                        redact_secrets(&err.to_string())
                    );
                    Ok(())
                }
                Ok(ApplyResult::Gap) => Err(VenueError::MalformedResponse(
                    "orderbook sequence gap".into(),
                )),
                Ok(ApplyResult::Updated { ticker, quote }) => {
                    ws.last_recv_to_book_us =
                        u64::try_from(received.elapsed().as_micros()).unwrap_or(u64::MAX);
                    if let Some(quote) = quote {
                        observe_book_quote(
                            state_dir, cfg, desk, tracker, risk, venue, snapshot, ws, &ticker,
                            quote,
                        );
                    }
                    Ok(())
                }
                Ok(ApplyResult::Ignored | ApplyResult::Unready { .. }) => Ok(()),
            }
        }
        "fill" => {
            let fill = parse_fill_msg(&env)?;
            ingest_one_fill(tracker, risk, fill);
            Ok(())
        }
        "error" => {
            let detail = env
                .msg
                .as_ref()
                .map(ToString::to_string)
                .unwrap_or_else(|| "websocket error".into());
            Err(VenueError::MalformedResponse(redact_secrets(&detail)))
        }
        _ => Ok(()),
    }
}

#[allow(clippy::too_many_arguments)]
fn observe_book_quote<T: KalshiTransport, I: VenueIdentity>(
    state_dir: &Path,
    cfg: &TradingConfig,
    desk: &mut LiveDesk,
    tracker: &mut InMemoryPositionTracker,
    risk: &PaperRiskEngine,
    venue: &mut KalshiVenue<T, I>,
    snapshot: &WeeklyBankrollSnapshot,
    ws: &mut LiveWs,
    ticker: &str,
    quote: BookQuote,
) {
    let bid_ask = (quote.yes_bid.cents(), quote.yes_ask.cents());
    if ws.last_quotes.get(ticker) == Some(&bid_ask) {
        return;
    }
    let Some(binding) = venue.identity().lookup_ticker(ticker) else {
        return;
    };
    let exchange_ts = quote
        .ts_ms
        .map(ts_ms)
        .or_else(|| ws.rest_exchange_ts.get(ticker).copied());
    let Some(exchange_ts) = exchange_ts else {
        return;
    };
    ws.last_quotes.insert(ticker.to_string(), bid_ask);
    let received_at = ReceivedAt::from_utc(utc_now());
    venue.set_received_at(received_at);
    let event = live_market_event_from_book(binding, quote, exchange_ts, received_at);
    let Some((strategy, strategy_id)) = desk.for_ticker_mut(ticker) else {
        return;
    };
    let started = Instant::now();
    observe_one(
        state_dir,
        cfg,
        strategy,
        strategy_id,
        tracker,
        risk,
        venue,
        snapshot,
        event,
    );
    ws.last_book_to_observe_us = u64::try_from(started.elapsed().as_micros()).unwrap_or(u64::MAX);
    ws.observed.insert(binding.game_id);
    eprintln!(
        "momento yes_bid_update ticker={} bid={} ask={} recv_to_book_us={} book_to_observe_us={}",
        ticker,
        quote.yes_bid.cents(),
        quote.yes_ask.cents(),
        ws.last_recv_to_book_us,
        ws.last_book_to_observe_us
    );
}

fn discover_open_markets(
    venue: &mut KalshiVenue<ProductionTradingTransport, StaticIdentity>,
    received_at: ReceivedAt,
    rest_ts: &mut HashMap<String, ExchangeTimestamp>,
) -> Result<HashSet<String>, HostError> {
    let mut tickers = HashSet::new();
    let mlb = discover_open_series(venue, MLB_SERIES_TICKER, received_at, rest_ts);
    let wnba = discover_open_series(venue, WNBA_SERIES_TICKER, received_at, rest_ts);
    match mlb {
        Ok(t) => tickers.extend(t),
        Err(err) => eprintln!(
            "momento mlb_discovery_error={}",
            redact_secrets(&err.to_string())
        ),
    }
    match wnba {
        Ok(t) => tickers.extend(t),
        Err(err) => eprintln!(
            "momento wnba_discovery_error={}",
            redact_secrets(&err.to_string())
        ),
    }
    Ok(tickers)
}

fn discover_open_series(
    venue: &mut KalshiVenue<ProductionTradingTransport, StaticIdentity>,
    series: &str,
    received_at: ReceivedAt,
    rest_ts: &mut HashMap<String, ExchangeTimestamp>,
) -> Result<HashSet<String>, HostError> {
    let mut tickers = HashSet::new();
    let mut cursor: Option<String> = None;
    for _ in 0..20 {
        let mut query = format!("series_ticker={series}&status=open&limit=1000");
        if let Some(c) = cursor.as_deref() {
            query.push_str("&cursor=");
            query.push_str(c);
        }
        let page = venue
            .list_markets(&query)
            .map_err(|e| HostError::Venue(redact_secrets(&e.to_string())))?;
        for market in page.markets {
            if market.event_ticker.trim().is_empty() || market.ticker.trim().is_empty() {
                continue;
            }
            let game_id = game_id_for_event_ticker(&market.event_ticker);
            let market_id = market_id_for_ticker(&market.ticker);
            venue.identity_mut().bind(
                market.ticker.clone(),
                MarketBinding {
                    market_id,
                    game_id,
                    position_id: None,
                },
            );
            if let Ok(snap) = map_market(&market, received_at, Some(market_id), Some(game_id)) {
                if let Some(ts) = snap.exchange_ts {
                    rest_ts.insert(market.ticker.clone(), ts);
                }
            }
            tickers.insert(market.ticker);
        }
        match page.cursor.filter(|c| !c.is_empty()) {
            Some(next) => cursor = Some(next),
            None => break,
        }
    }
    Ok(tickers)
}

#[allow(clippy::too_many_arguments)]
fn observe_one<T: KalshiTransport, I: VenueIdentity>(
    state_dir: &Path,
    cfg: &TradingConfig,
    strategy: &mut MlbStrategy,
    strategy_id: StrategyId,
    tracker: &mut InMemoryPositionTracker,
    risk: &PaperRiskEngine,
    venue: &mut KalshiVenue<T, I>,
    snapshot: &WeeklyBankrollSnapshot,
    event: MarketEvent,
) {
    let assigned = tracker
        .get_or_create_with_budget(
            strategy_id,
            event.game_id,
            snapshot,
            per_game_budget(snapshot, strategy_id),
            Some(event.market_id),
            event.side,
        )
        .id();
    let recon = tracker.reconciliation_state();
    let kill = risk.kill_switch();
    let has_working_entry = tracker.has_working_entry(event.game_id);
    let unknown_entry_order = tracker.has_unknown_entry(event.game_id);
    let has_working_liquidation = tracker.has_working_liquidation_for_position(assigned);
    let unknown_liquidation_order = tracker.has_unknown_liquidation_for_position(assigned);
    let ctx = MlbContext {
        event: &event,
        position: tracker.get(assigned),
        assigned_position_id: Some(assigned),
        recon,
        kill_switch: kill,
        data_stale: false,
        has_working_entry,
        unknown_entry_order,
        has_working_liquidation,
        unknown_liquidation_order,
    };
    let turn = strategy.observe(&ctx);
    for ev in turn.audit {
        append_audit(state_dir, &ev);
        risk.append_audit(ev);
    }
    for directive in turn.directives {
        match directive {
            MlbDirective::Build(intent) => {
                if recon.blocks_new_exposure() || tracker.has_unknown_orders() {
                    eprintln!(
                        "momento entry_blocked recon={:?} unknown=true game={}",
                        recon,
                        intent.build.game_id.raw()
                    );
                    continue;
                }
                // Strategy already returned to the 80–83 band. Clear a temporary
                // above-max pause so Risk sees Permitted. 89 game-lock still
                // blocks resume (resume_entry_if_unlocked is a no-op when locked).
                if let Some(pos) = tracker.get_mut(intent.build.position_id) {
                    if pos.entry_price_gate() == EntryPriceGate::PausedAboveMaxPrice {
                        pos.resume_entry_if_unlocked();
                        eprintln!(
                            "momento entry_gate=resumed game={} position={}",
                            intent.build.game_id.raw(),
                            intent.build.position_id.raw()
                        );
                    }
                }
                let Some(pos) = tracker.get(intent.build.position_id).cloned() else {
                    continue;
                };
                match risk.decide_entry(&intent, &pos) {
                    RiskDecision::Approved(approved) => {
                        if let Err(err) = submit_approved(cfg, tracker, risk, venue, approved) {
                            eprintln!(
                                "momento submit_refused={}",
                                redact_secrets(&err.to_string())
                            );
                        }
                    }
                    RiskDecision::Rejected { reason, .. } => {
                        eprintln!("momento risk_rejected={reason:?}");
                    }
                }
            }
            MlbDirective::CancelRemainingEntries { game_id, .. } => {
                let _ = tracker.apply_event(PositionEvent::GameLocked {
                    game_id,
                    exchange_ts: event.exchange_ts,
                    received_at: event.received_at,
                });
                risk.lock_game(game_id);
                cancel_entry_orders(tracker, risk, venue, game_id);
            }
            MlbDirective::PauseEntry { game_id } => {
                if let Some(id) = tracker.id_for_game(game_id) {
                    if let Some(pos) = tracker.get_mut(id) {
                        pos.pause_entry_above_max_price();
                    }
                }
            }
            MlbDirective::StopWatch(signal) => {
                eprintln!(
                    "momento stop_monitor=active game={} position={} rounding=half_vwap_hundredths flatten=false",
                    signal.game_id.raw(),
                    signal.position_id.raw()
                );
            }
            MlbDirective::ExecuteStop(exec) => {
                cancel_entry_orders(tracker, risk, venue, exec.game_id);
                if let Some(pos) = tracker.get_mut(exec.position_id) {
                    pos.trigger_stop();
                    pos.begin_liquidation();
                }
                if let Err(err) = submit_liquidation(cfg, tracker, risk, venue, &exec) {
                    eprintln!(
                        "momento liquidation_refused={}",
                        redact_secrets(&err.to_string())
                    );
                }
            }
        }
    }
}

fn submit_approved<T: KalshiTransport, I: VenueIdentity>(
    cfg: &TradingConfig,
    tracker: &mut InMemoryPositionTracker,
    risk: &PaperRiskEngine,
    venue: &mut KalshiVenue<T, I>,
    approved: ApprovedTradeIntent,
) -> Result<ClientOrderId, HostError> {
    if !cfg.is_live_armed() {
        risk.on_cancel(approved.client_order_id());
        return Err(HostError::LiveDisarmed);
    }
    if paper_mode_cannot_submit_production(cfg) {
        risk.on_cancel(approved.client_order_id());
        return Err(HostError::LiveNotImplemented);
    }
    let max = cfg
        .max_entry_price()
        .map_err(|e| HostError::Config(e.to_string()))?;
    if entry_price_exceeds_max(approved.limit_price(), max)
        || approved.limit_price().cents() > MAX_ENTRY
    {
        risk.on_cancel(approved.client_order_id());
        return Err(HostError::Config("entry exceeds 83 cents".into()));
    }
    if tracker.reconciliation_state().blocks_new_exposure() || tracker.has_unknown_orders() {
        return Err(HostError::Venue(
            "UNKNOWN blocks additional exposure".into(),
        ));
    }
    if tracker.order(approved.client_order_id()).is_some() {
        return Ok(approved.client_order_id());
    }
    let ticker = venue
        .identity()
        .ticker_for_market(approved.market_id())
        .ok_or_else(|| HostError::Venue("market ticker is not mapped".into()))?;

    let order = Order::new_entry(
        approved.client_order_id(),
        approved.position_id(),
        approved.game_id(),
        approved.decision_id(),
        approved.limit_price(),
        approved.max_contracts(),
    );
    if let Some(pos) = tracker.get_mut(approved.position_id()) {
        pos.bind_entry_identity(approved.market_id(), approved.side())
            .map_err(|e| HostError::Venue(e.to_string()))?;
        pos.record_submission(approved.max_contracts())
            .map_err(|e| HostError::Venue(e.to_string()))?;
    }
    let _ = tracker.apply_event(PositionEvent::OrderSubmitted {
        order: order.clone(),
    });
    let submitted = Instant::now();
    match venue.submit_post_only(&order, &ticker) {
        Ok(venue_id) => {
            let _ = tracker.apply_event(PositionEvent::OrderWorking {
                client_order_id: approved.client_order_id(),
                venue_order_id: venue_id,
            });
            eprintln!(
                "momento latency_us submit_to_ack={} client={}",
                u64::try_from(submitted.elapsed().as_micros()).unwrap_or(u64::MAX),
                approved.client_order_id().raw()
            );
            Ok(approved.client_order_id())
        }
        Err(MomentoError::Venue(VenueError::Timeout | VenueError::AmbiguousSubmission)) => {
            let _ = tracker.apply_event(PositionEvent::Unknown {
                client_order_id: approved.client_order_id(),
            });
            risk.mark_unknown(approved.client_order_id(), approved.position_id());
            Err(HostError::Venue(
                "order state UNKNOWN; reconcile before additional exposure".into(),
            ))
        }
        Err(MomentoError::Venue(VenueError::Unsupported(msg))) => {
            let _ = tracker.apply_event(PositionEvent::Rejected {
                client_order_id: approved.client_order_id(),
            });
            risk.on_cancel(approved.client_order_id());
            Err(HostError::Venue(msg))
        }
        Err(other) => {
            let _ = tracker.apply_event(PositionEvent::Unknown {
                client_order_id: approved.client_order_id(),
            });
            risk.mark_unknown(approved.client_order_id(), approved.position_id());
            Err(HostError::Venue(redact_secrets(&other.to_string())))
        }
    }
}

/// For a reduce-only ask, a lower YES bid is more executable. Use the current
/// local-book suggested limit, and if the venue book is even lower, follow it.
/// Never raise the limit back toward a disappeared stop price.
fn more_executable_ask_limit(suggested: Price, rest_bid: Option<Price>) -> Price {
    match rest_bid {
        Some(rest) if rest.cents() < suggested.cents() => rest,
        _ => suggested,
    }
}

fn submit_liquidation<T: KalshiTransport, I: VenueIdentity>(
    cfg: &TradingConfig,
    tracker: &mut InMemoryPositionTracker,
    risk: &PaperRiskEngine,
    venue: &mut KalshiVenue<T, I>,
    exec: &StopExecution,
) -> Result<ClientOrderId, HostError> {
    if !cfg.is_live_armed() {
        return Err(HostError::LiveDisarmed);
    }
    if paper_mode_cannot_submit_production(cfg) {
        return Err(HostError::LiveNotImplemented);
    }
    if tracker.has_working_liquidation_for_position(exec.position_id)
        || tracker.has_unknown_liquidation_for_position(exec.position_id)
    {
        return Err(HostError::Venue(
            "liquidation already working or UNKNOWN; reconcile before resubmit".into(),
        ));
    }
    let Some(pos) = tracker.get(exec.position_id).cloned() else {
        return Err(HostError::Venue("liquidation position missing".into()));
    };
    if pos.filled_quantity().get() == 0 {
        return Err(HostError::Venue("no filled quantity to reduce".into()));
    }
    let Some(market_id) = pos.market_id() else {
        return Err(HostError::Venue(
            "liquidation missing position MarketId; fail closed".into(),
        ));
    };
    let Some(side) = pos.side() else {
        return Err(HostError::Venue(
            "liquidation missing position side; fail closed".into(),
        ));
    };
    if exec.market_id != market_id || exec.side != side {
        return Err(HostError::Venue(
            "liquidation identity does not match position MarketId/side; fail closed".into(),
        ));
    }
    if exec.position_id != pos.id() {
        return Err(HostError::Venue(
            "liquidation PositionId does not match tracker position; fail closed".into(),
        ));
    }
    let (decision_id, client_order_id) = risk
        .approve_liquidation(&pos)
        .map_err(|reason| HostError::Venue(format!("liquidation risk rejected: {reason:?}")))?;
    if tracker.order(client_order_id).is_some() {
        return Ok(client_order_id);
    }
    let ticker = venue
        .identity()
        .ticker_for_market(market_id)
        .ok_or_else(|| HostError::Venue("liquidation ticker is not mapped for MarketId".into()))?;
    let rest_bid = match venue.get_orderbook_best_yes_bid(&ticker) {
        Ok(bid) => bid,
        Err(err) => {
            eprintln!(
                "momento orderbook_unavailable fallback_suggested_limit err={}",
                redact_secrets(&err.to_string())
            );
            None
        }
    };
    let limit = more_executable_ask_limit(exec.suggested_limit, rest_bid);
    let qty = if pos.filled_quantity().get() < exec.quantity.get() {
        pos.filled_quantity()
    } else {
        exec.quantity
    };
    if qty.get() == 0 {
        return Err(HostError::Venue("liquidation quantity is zero".into()));
    }
    let order = Order::new_liquidation(
        client_order_id,
        exec.position_id,
        exec.game_id,
        decision_id,
        limit,
        qty,
        market_id,
        side,
    );
    let _ = tracker.apply_event(PositionEvent::OrderSubmitted {
        order: order.clone(),
    });
    match venue.submit_reduce_only_liquidation_on(&order, &ticker) {
        Ok(ack) => {
            let _ = tracker.apply_event(PositionEvent::OrderWorking {
                client_order_id,
                venue_order_id: ack.venue_order_id,
            });
            eprintln!(
                "momento liquidation_submitted game={} position={} market={} side={:?} qty={} limit_cents={} ticker={} client={} fill_count={} remaining_count={}",
                exec.game_id.raw(),
                exec.position_id.raw(),
                market_id.raw(),
                side,
                qty.get(),
                limit.cents(),
                ticker,
                client_order_id.raw(),
                ack.fill_count.get(),
                ack.remaining_count.get()
            );
            if ack.remaining_count.get() == 0 && ack.fill_count.get() == 0 {
                let _ = tracker.apply_event(PositionEvent::Cancelled { client_order_id });
                risk.on_cancel(client_order_id);
                eprintln!(
                    "momento liquidation_ioc_unfilled_cancelled position={} client={} continue=true flatten=false",
                    exec.position_id.raw(),
                    client_order_id.raw()
                );
            }
            Ok(client_order_id)
        }
        Err(MomentoError::Venue(VenueError::Timeout | VenueError::AmbiguousSubmission)) => {
            let _ = tracker.apply_event(PositionEvent::Unknown { client_order_id });
            risk.mark_unknown(client_order_id, exec.position_id);
            Err(HostError::Venue(
                "liquidation state UNKNOWN; reconcile before resubmit".into(),
            ))
        }
        Err(MomentoError::Venue(VenueError::Unsupported(msg))) => {
            let _ = tracker.apply_event(PositionEvent::Rejected { client_order_id });
            risk.on_cancel(client_order_id);
            Err(HostError::Venue(msg))
        }
        Err(other) => {
            let _ = tracker.apply_event(PositionEvent::Unknown { client_order_id });
            risk.mark_unknown(client_order_id, exec.position_id);
            Err(HostError::Venue(redact_secrets(&other.to_string())))
        }
    }
}

fn cancel_entry_orders<T: KalshiTransport, I: VenueIdentity>(
    tracker: &mut InMemoryPositionTracker,
    risk: &PaperRiskEngine,
    venue: &mut KalshiVenue<T, I>,
    game_id: momento_core::GameId,
) {
    for order in tracker.entry_orders_for_game(game_id) {
        if order.state().is_terminal() || order.state() == momento_core::OrderState::Unknown {
            continue;
        }
        let _ = tracker.apply_event(PositionEvent::CancelRequested {
            client_order_id: order.client_order_id(),
        });
        match venue.cancel(order.client_order_id()) {
            Ok(()) => {
                let _ = tracker.apply_event(PositionEvent::Cancelled {
                    client_order_id: order.client_order_id(),
                });
                risk.on_cancel(order.client_order_id());
            }
            Err(MomentoError::Venue(VenueError::Timeout | VenueError::AmbiguousSubmission)) => {
                let _ = tracker.apply_event(PositionEvent::Unknown {
                    client_order_id: order.client_order_id(),
                });
                risk.mark_unknown(order.client_order_id(), order.position_id());
            }
            Err(err) if is_http_not_found(&err) => {
                let _ = tracker.apply_event(PositionEvent::Cancelled {
                    client_order_id: order.client_order_id(),
                });
                risk.on_cancel(order.client_order_id());
                eprintln!(
                    "momento occupancy_released reason=cancel_not_found client={} game={}",
                    order.client_order_id().raw(),
                    game_id.raw()
                );
            }
            Err(err) => {
                eprintln!(
                    "momento cancel_entry_failed={}",
                    redact_secrets(&err.to_string())
                );
            }
        }
    }
}

pub(crate) fn reconcile_unknowns<T: KalshiTransport, I: VenueIdentity>(
    venue: &mut KalshiVenue<T, I>,
    tracker: &mut InMemoryPositionTracker,
    risk: &PaperRiskEngine,
) {
    let ids: Vec<_> = tracker.unknown_order_ids().collect();
    if ids.is_empty() {
        return;
    }
    let received_at = ReceivedAt::from_utc(utc_now());
    for id in ids {
        let unknown = UnknownOrder {
            client_order_id: id,
        };
        match venue.reconcile_unknown(&unknown) {
            Ok(outcome) => {
                let applied = apply_venue_reconcile(venue, tracker, risk, id, outcome, received_at);
                eprintln!(
                    "momento reconcile client={} outcome={:?}",
                    id.raw(),
                    applied
                );
            }
            Err(err) => {
                tracker.mark_ambiguous();
                eprintln!(
                    "momento reconcile_error={}",
                    redact_secrets(&err.to_string())
                );
            }
        }
    }
}

fn apply_venue_reconcile<T: KalshiTransport, I: VenueIdentity>(
    venue: &mut KalshiVenue<T, I>,
    tracker: &mut InMemoryPositionTracker,
    risk: &PaperRiskEngine,
    id: ClientOrderId,
    outcome: ReconcileOutcome,
    received_at: ReceivedAt,
) -> ReconcileOutcome {
    let snapshot = match outcome {
        ReconcileOutcome::Ambiguous => {
            tracker.mark_ambiguous();
            if let Some(order) = tracker.order(id) {
                risk.reconcile_order(id, order.position_id(), ReconcileOutcome::Ambiguous);
            }
            return ReconcileOutcome::Ambiguous;
        }
        ReconcileOutcome::NotFound => not_found_snapshot(),
        ReconcileOutcome::Found => {
            let Ok(Some(venue_id)) = venue.venue_order_id(id) else {
                tracker.mark_ambiguous();
                if let Some(order) = tracker.order(id) {
                    risk.reconcile_order(id, order.position_id(), ReconcileOutcome::Ambiguous);
                }
                return ReconcileOutcome::Ambiguous;
            };
            match venue.get_order(venue_id) {
                Ok(view) => mapped_order_to_snapshot(&view),
                Err(err) => {
                    tracker.mark_ambiguous();
                    if let Some(order) = tracker.order(id) {
                        risk.reconcile_order(id, order.position_id(), ReconcileOutcome::Ambiguous);
                    }
                    eprintln!(
                        "momento reconcile_found_get_failed client={} err={}",
                        id.raw(),
                        redact_secrets(&err.to_string())
                    );
                    return ReconcileOutcome::Ambiguous;
                }
            }
        }
    };
    match tracker.reconcile(id, snapshot, received_at) {
        Ok(result) => {
            risk.reconcile_order(id, result.position_id, result.outcome);
            if result.outcome == ReconcileOutcome::Ambiguous {
                tracker.mark_ambiguous();
            }
            result.outcome
        }
        Err(err) => {
            tracker.mark_ambiguous();
            if let Some(order) = tracker.order(id) {
                risk.reconcile_order(id, order.position_id(), ReconcileOutcome::Ambiguous);
            }
            eprintln!(
                "momento reconcile_apply_failed client={} err={err:?}",
                id.raw()
            );
            ReconcileOutcome::Ambiguous
        }
    }
}

#[allow(clippy::too_many_arguments)]
pub fn refresh_open_mlb_positions<T: KalshiTransport, I: VenueIdentity>(
    state_dir: &Path,
    cfg: &TradingConfig,
    strategy: &mut MlbStrategy,
    tracker: &mut InMemoryPositionTracker,
    risk: &PaperRiskEngine,
    venue: &mut KalshiVenue<T, I>,
    snapshot: &WeeklyBankrollSnapshot,
    already_observed: &HashSet<GameId>,
) {
    let held: Vec<(
        momento_core::PositionId,
        GameId,
        Option<momento_core::MarketId>,
    )> = tracker
        .positions()
        .filter(|p| p.filled_quantity().get() > 0)
        .filter(|p| {
            !matches!(
                p.lifecycle(),
                PositionLifecycle::Settled | PositionLifecycle::Flat
            )
        })
        .map(|p| (p.id(), p.game_id(), p.market_id()))
        .collect();
    for (position_id, game_id, market_id) in held {
        let Some(market_id) = market_id else {
            eprintln!(
                "momento held_refresh_skipped_missing_market position={}",
                position_id.raw()
            );
            continue;
        };
        let Some(ticker) = venue.identity().ticker_for_market(market_id) else {
            eprintln!(
                "momento held_refresh_skipped_unmapped_market position={} market={}",
                position_id.raw(),
                market_id.raw()
            );
            continue;
        };
        match venue.get_market_with_settlement(&ticker) {
            Ok((snap, settlement)) => {
                apply_settlement_if_any(tracker, risk, position_id, game_id, settlement);
                if already_observed.contains(&game_id) {
                    continue;
                }
                if let Some(event) = live_market_event_from_snapshot(snap) {
                    observe_one(
                        state_dir,
                        cfg,
                        strategy,
                        MLB_STRATEGY_ID,
                        tracker,
                        risk,
                        venue,
                        snapshot,
                        event,
                    );
                }
            }
            Err(err) => {
                eprintln!(
                    "momento held_market_refresh_failed game={} err={}",
                    game_id.raw(),
                    redact_secrets(&err.to_string())
                );
            }
        }
    }
}

#[allow(clippy::too_many_arguments)]
fn refresh_held_positions<T: KalshiTransport, I: VenueIdentity>(
    state_dir: &Path,
    cfg: &TradingConfig,
    desk: &mut LiveDesk,
    tracker: &mut InMemoryPositionTracker,
    risk: &PaperRiskEngine,
    venue: &mut KalshiVenue<T, I>,
    snapshot: &WeeklyBankrollSnapshot,
    already_observed: &HashSet<GameId>,
) {
    let held: Vec<(
        momento_core::PositionId,
        GameId,
        StrategyId,
        Option<momento_core::MarketId>,
    )> = tracker
        .positions()
        .filter(|p| position_is_open(p))
        .map(|p| (p.id(), p.game_id(), p.strategy_id(), p.market_id()))
        .collect();
    for (position_id, game_id, strategy_id, market_id) in held {
        let Some(market_id) = market_id else {
            eprintln!(
                "momento held_refresh_skipped_missing_market position={}",
                position_id.raw()
            );
            continue;
        };
        let Some(ticker) = venue.identity().ticker_for_market(market_id) else {
            eprintln!(
                "momento held_refresh_skipped_unmapped_market position={} market={}",
                position_id.raw(),
                market_id.raw()
            );
            continue;
        };
        match venue.get_market_with_settlement(&ticker) {
            Ok((snap, settlement)) => {
                apply_settlement_if_any(tracker, risk, position_id, game_id, settlement);
                if already_observed.contains(&game_id) {
                    continue;
                }
                let Some(event) = live_market_event_from_snapshot(snap) else {
                    continue;
                };
                let Some(strategy) = desk.strategy_mut(strategy_id) else {
                    continue;
                };
                observe_one(
                    state_dir,
                    cfg,
                    strategy,
                    strategy_id,
                    tracker,
                    risk,
                    venue,
                    snapshot,
                    event,
                );
            }
            Err(err) => {
                eprintln!(
                    "momento held_market_refresh_failed game={} err={}",
                    game_id.raw(),
                    redact_secrets(&err.to_string())
                );
            }
        }
    }
}

fn apply_settlement_if_any(
    tracker: &mut InMemoryPositionTracker,
    risk: &PaperRiskEngine,
    position_id: momento_core::PositionId,
    game_id: GameId,
    view: VenueSettlementView,
) {
    let Some(pos) = tracker.get(position_id) else {
        return;
    };
    if matches!(
        pos.lifecycle(),
        PositionLifecycle::Settled | PositionLifecycle::Flat
    ) {
        return;
    }
    if pos.filled_quantity().get() == 0 {
        return;
    }
    match (view.result, view.settlement_value) {
        (Some(_), Some(proceeds)) => {
            let realized = pos
                .actual_exposure()
                .as_money()
                .checked_add(pos.entry_fees())
                .ok()
                .and_then(|cost| proceeds.checked_sub(cost).ok());
            let received_at = ReceivedAt::from_utc(utc_now());
            let applied = tracker.apply_event(PositionEvent::Settlement(SettlementEvent {
                position_id,
                game_id,
                proceeds,
                exchange_ts: view.settlement_ts,
                received_at,
            }));
            if applied.is_ok() {
                risk.on_settlement(position_id);
                risk.on_realized_close(position_id, realized);
                eprintln!(
                    "momento settlement_applied position={} game={} proceeds_cents={}",
                    position_id.raw(),
                    game_id.raw(),
                    proceeds.cents()
                );
            }
        }
        (Some(_), None) => {
            risk.on_realized_close(position_id, None);
            eprintln!(
                "momento settlement_pending position={} game={} venue_result_without_value",
                position_id.raw(),
                game_id.raw()
            );
        }
        _ => {}
    }
}

pub fn sync_working_orders<T: KalshiTransport, I: VenueIdentity>(
    venue: &mut KalshiVenue<T, I>,
    tracker: &mut InMemoryPositionTracker,
    risk: &PaperRiskEngine,
) {
    let orders = tracker.non_terminal_known_orders();
    eprintln!("momento occupancy_sync n={}", orders.len());
    for order in orders {
        sync_one_working_order(venue, tracker, risk, order);
    }
}

/// Unfilled entry that must leave the 5-slot cap: local cancel already
/// requested, or the game is 89-locked / abandoned so the maker cannot stay.
/// Live unlocked Working makers are excluded — they are current exposure.
fn unfilled_entry_must_finish_cancel(tracker: &InMemoryPositionTracker, order: &Order) -> bool {
    if order.purpose() != OrderPurpose::Entry || order.quantities().filled.get() > 0 {
        return false;
    }
    if order.state() == OrderState::CancelPending {
        return true;
    }
    tracker
        .get(order.position_id())
        .is_some_and(|p| p.game_lock().is_locked() || p.entry_abandoned())
}

fn sync_one_working_order<T: KalshiTransport, I: VenueIdentity>(
    venue: &mut KalshiVenue<T, I>,
    tracker: &mut InMemoryPositionTracker,
    risk: &PaperRiskEngine,
    order: Order,
) {
    let must_finish = unfilled_entry_must_finish_cancel(tracker, &order);
    eprintln!(
        "momento occupancy_check client={} state={:?} must_finish={}",
        order.client_order_id().raw(),
        order.state(),
        must_finish
    );
    if must_finish {
        if order.state() != OrderState::CancelPending {
            let _ = tracker.apply_event(PositionEvent::CancelRequested {
                client_order_id: order.client_order_id(),
            });
        }
        match venue.cancel(order.client_order_id()) {
            Ok(()) => {
                if release_gone_unfilled_entry(tracker, risk, &order, "locked_cancel") {
                    return;
                }
            }
            Err(err) if is_http_not_found(&err) => {
                if release_gone_unfilled_entry(tracker, risk, &order, "locked_cancel_not_found") {
                    return;
                }
            }
            Err(MomentoError::Venue(VenueError::Timeout | VenueError::AmbiguousSubmission)) => {
                // Already CancelPending: a retry timeout must not freeze the
                // whole desk as UNKNOWN. Working+locked first cancel still
                // escalates so we do not invent a fill/cancel.
                if order.state() == OrderState::CancelPending {
                    eprintln!(
                        "momento locked_cancel_retry_timeout client={}",
                        order.client_order_id().raw()
                    );
                } else {
                    let _ = tracker.apply_event(PositionEvent::Unknown {
                        client_order_id: order.client_order_id(),
                    });
                    risk.mark_unknown(order.client_order_id(), order.position_id());
                    return;
                }
            }
            Err(err) => {
                eprintln!(
                    "momento locked_cancel_failed client={} err={}",
                    order.client_order_id().raw(),
                    redact_secrets(&err.to_string())
                );
            }
        }
    }

    let Some(venue_id) = order.venue_order_id() else {
        if must_finish {
            eprintln!(
                "momento occupancy_missing_venue_id client={}",
                order.client_order_id().raw()
            );
        }
        return;
    };
    match venue.get_order(venue_id) {
        Ok(view) => match view.state {
            OrderState::Cancelled | OrderState::Expired | OrderState::Rejected => {
                let _ = release_gone_unfilled_entry(tracker, risk, &order, "venue_canceled");
            }
            OrderState::Filled if view.filled.get() == 0 && must_finish => {
                let _ = release_gone_unfilled_entry(tracker, risk, &order, "venue_executed_empty");
            }
            OrderState::Filled => {
                eprintln!(
                    "momento occupancy_held_venue_filled client={} filled={}",
                    order.client_order_id().raw(),
                    view.filled.get()
                );
                if view.filled.get() > 0 {
                    ingest_fills_for_venue_order(venue, tracker, risk, venue_id);
                }
            }
            OrderState::Working | OrderState::PartiallyFilled | OrderState::CancelPending => {
                if must_finish {
                    eprintln!(
                        "momento occupancy_still_resting client={} venue_state={:?}",
                        order.client_order_id().raw(),
                        view.state
                    );
                }
            }
            other => {
                eprintln!(
                    "momento occupancy_status_unhandled client={} state={other:?}",
                    order.client_order_id().raw()
                );
            }
        },
        Err(err) if is_http_not_found(&err) => {
            if must_finish || order.state() == OrderState::CancelPending {
                let _ = release_gone_unfilled_entry(tracker, risk, &order, "order_not_found");
            } else {
                eprintln!(
                    "momento order_status_not_found_held client={} state={:?}",
                    order.client_order_id().raw(),
                    order.state()
                );
            }
        }
        Err(err) => {
            eprintln!(
                "momento order_status_refresh_failed client={} err={}",
                order.client_order_id().raw(),
                redact_secrets(&err.to_string())
            );
        }
    }
}

fn release_gone_unfilled_entry(
    tracker: &mut InMemoryPositionTracker,
    risk: &PaperRiskEngine,
    order: &Order,
    reason: &str,
) -> bool {
    if order.quantities().filled.get() > 0 {
        eprintln!(
            "momento occupancy_held_filled_not_found client={} filled={}",
            order.client_order_id().raw(),
            order.quantities().filled.get()
        );
        return false;
    }
    match tracker.apply_event(PositionEvent::Cancelled {
        client_order_id: order.client_order_id(),
    }) {
        Ok(_) => {
            risk.on_cancel(order.client_order_id());
            eprintln!(
                "momento occupancy_released reason={} client={} position={} open_slots={}",
                reason,
                order.client_order_id().raw(),
                order.position_id().raw(),
                risk.open_slot_count()
            );
            true
        }
        Err(err) => {
            eprintln!(
                "momento occupancy_release_failed reason={} client={} err={err:?}",
                reason,
                order.client_order_id().raw()
            );
            false
        }
    }
}

fn poll_mlb_markets<T: KalshiTransport>(
    venue: &mut KalshiVenue<T, StaticIdentity>,
    received_at: ReceivedAt,
) -> Result<Vec<MarketEvent>, HostError> {
    let mut events = Vec::new();
    let mut cursor: Option<String> = None;
    for _ in 0..20 {
        let mut query = format!("series_ticker={MLB_SERIES_TICKER}&status=open&limit=1000");
        if let Some(c) = cursor.as_deref() {
            query.push_str("&cursor=");
            query.push_str(c);
        }
        let page = venue
            .list_markets(&query)
            .map_err(|e| HostError::Venue(redact_secrets(&e.to_string())))?;
        for market in page.markets {
            if market.event_ticker.trim().is_empty() || market.ticker.trim().is_empty() {
                continue;
            }
            let game_id = game_id_for_event_ticker(&market.event_ticker);
            let market_id = market_id_for_ticker(&market.ticker);
            venue.identity_mut().bind(
                market.ticker.clone(),
                MarketBinding {
                    market_id,
                    game_id,
                    position_id: None,
                },
            );
            let snap = match map_market(&market, received_at, Some(market_id), Some(game_id)) {
                Ok(s) => s,
                Err(err) => {
                    eprintln!(
                        "momento market_skipped ticker={} err={}",
                        market.ticker,
                        redact_secrets(&err.to_string())
                    );
                    continue;
                }
            };
            let Some(event) = live_market_event_from_snapshot(snap) else {
                continue;
            };
            events.push(event);
        }
        match page.cursor.filter(|c| !c.is_empty()) {
            Some(next) => cursor = Some(next),
            None => break,
        }
    }
    Ok(events)
}

/// Automated desk housekeeping. Runs on every heartbeat inside
/// `momento-live.service`. This is the only unfreeze path.
///
/// It does not invent fills, does not cancel unlocked live makers, and
/// does not force Healthy while an UNKNOWN order still exists.
#[allow(clippy::too_many_arguments)]
fn run_desk_housekeeping<T: KalshiTransport, I: VenueIdentity>(
    state_dir: &Path,
    cfg: &TradingConfig,
    desk: &mut LiveDesk,
    tracker: &mut InMemoryPositionTracker,
    risk: &PaperRiskEngine,
    venue: &mut KalshiVenue<T, I>,
    snapshot: &WeeklyBankrollSnapshot,
    already_observed: &HashSet<GameId>,
) {
    reconcile_unknowns(venue, tracker, risk);
    risk.adopt_fill_authoritative_occupancy(tracker.positions());
    refresh_held_positions(
        state_dir,
        cfg,
        desk,
        tracker,
        risk,
        venue,
        snapshot,
        already_observed,
    );
    ingest_fills(venue, tracker, risk);
    sync_working_orders(venue, tracker, risk);
    finish_housekeeping_gates(tracker, risk);
}

/// Occupancy + recon gates after ingest/sync. Safe leftover fills are
/// already ignored by the tracker. Settled known reservations drop here
/// via adopt. Ambiguous clears only with no live uncertainty.
pub fn finish_housekeeping_gates(
    tracker: &mut InMemoryPositionTracker,
    risk: &PaperRiskEngine,
) -> bool {
    risk.adopt_fill_authoritative_occupancy(tracker.positions());
    let cleared = tracker.release_ambiguous_if_no_live_uncertainty();
    if cleared {
        eprintln!(
            "momento recon_cleared reason=no_unknown_no_live_uncertain order_submission=enabled"
        );
    }
    let submit = if tracker.reconciliation_state().blocks_new_exposure() {
        "blocked"
    } else {
        "enabled"
    };
    eprintln!(
        "momento housekeeping_ok recon={:?} order_submission={} open_slots={} unknown={}",
        tracker.reconciliation_state(),
        submit,
        risk.open_slot_count(),
        tracker.has_unknown_orders()
    );
    cleared
}

pub fn ingest_fills<T: KalshiTransport, I: VenueIdentity>(
    venue: &mut KalshiVenue<T, I>,
    tracker: &mut InMemoryPositionTracker,
    risk: &PaperRiskEngine,
) {
    let mut cursor: Option<String> = None;
    let mut fractional = Vec::new();
    let mut integer_orders = HashSet::new();
    for _ in 0..FILL_INGEST_MAX_PAGES {
        let mut query = format!("limit={FILL_INGEST_PAGE_LIMIT}");
        if let Some(c) = cursor.as_deref() {
            query.push_str("&cursor=");
            query.push_str(c);
        }
        let page = match venue.list_fills(&query) {
            Ok(page) => page,
            Err(err) => {
                eprintln!(
                    "momento fill_page_unreadable query={query} err={}",
                    redact_secrets(&err.to_string())
                );
                return;
            }
        };
        ingest_fill_page_into(
            tracker,
            risk,
            page.fills,
            &mut fractional,
            &mut integer_orders,
        );
        match page.cursor.filter(|c| !c.is_empty()) {
            Some(next) => cursor = Some(next),
            None => break,
        }
    }
    apply_coalesced_fills(tracker, risk, &integer_orders, fractional);
}

fn ingest_fills_for_venue_order<T: KalshiTransport, I: VenueIdentity>(
    venue: &mut KalshiVenue<T, I>,
    tracker: &mut InMemoryPositionTracker,
    risk: &PaperRiskEngine,
    venue_order_id: VenueOrderId,
) {
    let mut cursor: Option<String> = None;
    let mut fractional = Vec::new();
    let mut integer_orders = HashSet::new();
    for _ in 0..FILL_INGEST_MAX_PAGES {
        let mut query = format!(
            "limit={FILL_INGEST_PAGE_LIMIT}&order_id={}",
            encode_venue_order_id(venue_order_id)
        );
        if let Some(c) = cursor.as_deref() {
            query.push_str("&cursor=");
            query.push_str(c);
        }
        let page = match venue.list_fills(&query) {
            Ok(page) => page,
            Err(err) => {
                eprintln!(
                    "momento fill_page_unreadable query={query} err={}",
                    redact_secrets(&err.to_string())
                );
                return;
            }
        };
        ingest_fill_page_into(
            tracker,
            risk,
            page.fills,
            &mut fractional,
            &mut integer_orders,
        );
        match page.cursor.filter(|c| !c.is_empty()) {
            Some(next) => cursor = Some(next),
            None => break,
        }
    }
    apply_coalesced_fills(tracker, risk, &integer_orders, fractional);
}

fn ingest_fill_page_into(
    tracker: &mut InMemoryPositionTracker,
    risk: &PaperRiskEngine,
    fills: Vec<KalshiFill>,
    fractional: &mut Vec<KalshiFill>,
    integer_orders: &mut HashSet<String>,
) {
    for raw in fills {
        if count_fp_to_contracts(&raw.count_fp).is_ok() {
            integer_orders.insert(raw.order_id.clone());
            ingest_one_fill(tracker, risk, raw);
        } else {
            fractional.push(raw);
        }
    }
}

fn apply_coalesced_fills(
    tracker: &mut InMemoryPositionTracker,
    risk: &PaperRiskEngine,
    integer_orders: &HashSet<String>,
    fractional: Vec<KalshiFill>,
) {
    for raw in coalesce_fractional_fills(fractional) {
        if integer_orders.contains(&raw.order_id) {
            eprintln!(
                "momento fill_coalesce_skipped_integer_already_applied order={}",
                raw.order_id
            );
            continue;
        }
        ingest_one_fill(tracker, risk, raw);
    }
}

/// Venue sometimes splits an integer contract fill across fractional `count_fp`
/// rows (observed 6.65 + 0.35 = 7.00). Domain contracts stay integers. Only
/// the fills endpoint rows are used; `get_order` fill counts are not applied.
fn coalesce_fractional_fills(rows: Vec<KalshiFill>) -> Vec<KalshiFill> {
    let mut by_order: HashMap<String, Vec<KalshiFill>> = HashMap::new();
    for row in rows {
        by_order.entry(row.order_id.clone()).or_default().push(row);
    }
    let mut out = Vec::new();
    for (order_id, mut group) in by_order {
        if group
            .iter()
            .any(|r| count_fp_to_contracts(&r.count_fp).is_ok())
        {
            continue;
        }
        let prices: HashSet<Option<String>> =
            group.iter().map(|r| r.yes_price_dollars.clone()).collect();
        if prices.len() != 1 {
            eprintln!(
                "momento fill_fractional_unrepresentable order={} reason=mixed_price n={}",
                order_id,
                group.len()
            );
            continue;
        }
        let mut hundredths: i64 = 0;
        let mut ok = true;
        for row in &group {
            match count_fp_to_hundredths(&row.count_fp) {
                Ok(n) => hundredths = hundredths.saturating_add(n),
                Err(_) => {
                    ok = false;
                    break;
                }
            }
        }
        if !ok || hundredths <= 0 || hundredths % 100 != 0 {
            eprintln!(
                "momento fill_fractional_unrepresentable order={} hundredths={} n={}",
                order_id,
                hundredths,
                group.len()
            );
            continue;
        }
        let contracts = u32::try_from(hundredths / 100).unwrap_or(0);
        if contracts == 0 {
            continue;
        }
        group.sort_by(|a, b| a.created_time.cmp(&b.created_time));
        let mut combined = group.remove(0);
        combined.count_fp = format!("{contracts}.00");
        eprintln!(
            "momento fill_coalesced order={} contracts={} parts={} hundredths={}",
            order_id,
            contracts,
            group.len() + 1,
            hundredths
        );
        out.push(combined);
    }
    out
}

pub fn ingest_one_fill(
    tracker: &mut InMemoryPositionTracker,
    risk: &PaperRiskEngine,
    raw: KalshiFill,
) {
    let Some(order) = local_order_for_fill(tracker, &raw) else {
        return;
    };
    if order.quantities().filled.get() >= order.quantities().requested.get()
        || order.state() == OrderState::Filled
    {
        return;
    }
    let mut raw = raw;
    if raw.client_order_id.trim().is_empty() {
        raw.client_order_id = encode_client_order_id(order.client_order_id());
    }
    let position_id = order.position_id();
    let purpose = order.purpose();
    let received_at = ReceivedAt::from_utc(utc_now());
    let (fill, _) = match map_fill(&raw, position_id, received_at) {
        Ok(mapped) => mapped,
        Err(err) => {
            eprintln!(
                "momento fill_map_failed order={} err={}",
                raw.order_id,
                redact_secrets(&err.to_string())
            );
            return;
        }
    };
    let fill = if purpose == OrderPurpose::Liquidation {
        fill.with_fee_kind(FeeKind::Liquidation)
    } else {
        fill
    };
    let event = if purpose == OrderPurpose::Liquidation {
        PositionEvent::LiquidationFill { fill: fill.clone() }
    } else {
        PositionEvent::PartialFill { fill: fill.clone() }
    };
    match tracker.apply_event(event) {
        Ok(ApplyStatus::Applied) => {
            risk.on_fill(&fill);
            eprintln!(
                "momento fill_applied client={} fill={} qty={} price_cents={}",
                fill.client_order_id().raw(),
                fill.fill_id().raw(),
                fill.quantity().get(),
                fill.price().cents()
            );
        }
        Ok(ApplyStatus::DuplicateIgnored) => {}
        Err(err) => {
            eprintln!(
                "momento fill_apply_failed order={} err={err:?}",
                raw.order_id
            );
        }
    }
}

fn local_order_for_fill(tracker: &InMemoryPositionTracker, raw: &KalshiFill) -> Option<Order> {
    if let Ok(cid) = decode_client_order_id(&raw.client_order_id) {
        if let Some(order) = tracker.order(cid) {
            return Some(order.clone());
        }
    }
    let vid = decode_venue_order_id(&raw.order_id).ok()?;
    tracker.order_by_venue_id(vid).cloned()
}

fn persist_all(
    state_dir: &Path,
    desk: &LiveDesk,
    tracker: &InMemoryPositionTracker,
    risk: &PaperRiskEngine,
    venue: &KalshiVenue<ProductionTradingTransport, StaticIdentity>,
) -> Result<(), HostError> {
    persist_strategy(state_dir, &desk.mlb)?;
    persist_wnba_strategy(state_dir, &desk.wnba)?;
    let risk_state = risk
        .persist_state()
        .ok_or_else(|| HostError::Io("risk persist missing snapshot".into()))?;
    let file = LiveRuntimeFile {
        tracker: tracker.snapshot_persist(),
        risk: risk_state,
        venue_by_client: venue.venue_map_snapshot(),
        unknown_submissions: venue.unknown_snapshot(),
        identity: venue
            .identity()
            .snapshot_bindings()
            .into_iter()
            .map(|(ticker, binding)| (ticker, binding.market_id.raw(), binding.game_id.raw()))
            .collect(),
    };
    atomic_json(state_dir, LIVE_STATE_FILE_NAME, &file)
}

fn load_runtime(state_dir: &Path) -> Result<LiveRuntimeFile, HostError> {
    let raw =
        fs::read_to_string(live_state_file(state_dir)).map_err(|e| HostError::Io(e.to_string()))?;
    serde_json::from_str(&raw).map_err(|e| HostError::Io(e.to_string()))
}

fn load_or_create_snapshot(
    cfg: &TradingConfig,
    state_dir: &Path,
) -> Result<WeeklyBankrollSnapshot, HostError> {
    fs::create_dir_all(state_dir).map_err(|e| HostError::Io(e.to_string()))?;
    let path = snapshot_file(state_dir);
    let now = utc_now();
    if path.exists() {
        let raw = fs::read_to_string(&path).map_err(|e| HostError::Io(e.to_string()))?;
        let snap: WeeklyBankrollSnapshot =
            serde_json::from_str(&raw).map_err(|e| HostError::Io(e.to_string()))?;
        let same_week =
            belongs_to_week(now, snap.week()).map_err(|e| HostError::Config(e.to_string()))?;
        if same_week {
            return Ok(snap);
        }
    }
    let snap = capture_policy_snapshot(cfg)?;
    atomic_json(state_dir, SNAPSHOT_FILE_NAME, &snap)?;
    Ok(snap)
}

fn ensure_weekly_snapshot(
    cfg: &TradingConfig,
    state_dir: &Path,
    current: WeeklyBankrollSnapshot,
    risk: &PaperRiskEngine,
    tracker: &mut InMemoryPositionTracker,
) -> Result<WeeklyBankrollSnapshot, HostError> {
    let now = utc_now();
    let same =
        belongs_to_week(now, current.week()).map_err(|e| HostError::Config(e.to_string()))?;
    let snap = if same {
        current
    } else {
        let snap = capture_policy_snapshot(cfg)?;
        atomic_json(state_dir, SNAPSHOT_FILE_NAME, &snap)?;
        eprintln!(
            "momento weekly_snapshot_reset bankroll_cents={} per_game_cents={}",
            snap.bankroll().cents(),
            snap.max_position_budget().cents()
        );
        snap
    };
    if risk.snapshot_id() != Some(snap.snapshot_id()) {
        risk.replace_weekly_snapshot(snap.clone());
    }
    let rebound = tracker.rebind_unfilled_positions_to_snapshot(&snap, |strategy_id| {
        per_game_budget(&snap, strategy_id)
    });
    if !rebound.is_empty() {
        risk.release_prior_week_unfilled_occupancy(&rebound);
        eprintln!(
            "momento weekly_snapshot_rebind positions={} snapshot_id={}",
            rebound.len(),
            snap.snapshot_id().raw()
        );
    }
    Ok(snap)
}

fn atomic_json<T: Serialize>(state_dir: &Path, name: &str, value: &T) -> Result<(), HostError> {
    fs::create_dir_all(state_dir).map_err(|e| HostError::Io(e.to_string()))?;
    let path = state_dir.join(name);
    let tmp = state_dir.join(format!("{name}.tmp"));
    let json = serde_json::to_string_pretty(value).map_err(|e| HostError::Io(e.to_string()))?;
    fs::write(&tmp, json).map_err(|e| HostError::Io(e.to_string()))?;
    fs::rename(tmp, path).map_err(|e| HostError::Io(e.to_string()))
}

fn append_audit(state_dir: &Path, event: &AuditEvent) {
    let Ok(()) = fs::create_dir_all(state_dir) else {
        return;
    };
    let Ok(json) = serde_json::to_string(event) else {
        return;
    };
    let line = redact_secrets(&json);
    if let Ok(mut f) = fs::OpenOptions::new()
        .create(true)
        .append(true)
        .open(state_dir.join(AUDIT_FILE_NAME))
    {
        let _ = writeln!(f, "{line}");
    }
}

pub fn live_heartbeat(
    cfg: &TradingConfig,
    tracker: &InMemoryPositionTracker,
    risk: &PaperRiskEngine,
    mlb: &MlbStrategy,
    wnba: &WnbaStrategy,
    markets: usize,
    market_data_ok: bool,
) -> String {
    let unknown = tracker.unknown_order_ids().count();
    let open_mlb = tracker
        .positions()
        .filter(|p| p.strategy_id() == MLB_STRATEGY_ID && position_is_open(p))
        .count();
    let open_wnba = tracker
        .positions()
        .filter(|p| p.strategy_id() == WNBA_STRATEGY_ID && position_is_open(p))
        .count();
    let open_desk = open_mlb + open_wnba;
    let recon = match tracker.reconciliation_state() {
        ReconciliationState::Healthy if unknown == 0 => "healthy",
        ReconciliationState::Healthy => "unknown_orders",
        ReconciliationState::Required | ReconciliationState::Reconciling => "required",
        ReconciliationState::Ambiguous => "ambiguous",
    };
    let kill = if risk.kill_switch().is_tripped() {
        "tripped"
    } else {
        "not_tripped"
    };
    let live_capable = cfg.is_live_armed() && !paper_mode_cannot_submit_production(cfg);
    let new_entry_blocked = tracker.reconciliation_state().blocks_new_exposure()
        || unknown > 0
        || risk.kill_switch().is_tripped();
    let market_data = if market_data_ok {
        "healthy"
    } else {
        "unhealthy"
    };
    format!(
        "momento heartbeat mode={:?} live.enabled={} live.confirmation={} production_auth=true market_data={} mlb_strategy=active wnba_strategy=active strategy=active risk=healthy reconciliation={} unknown_orders={} kill_switch={} open_mlb_positions={} open_wnba_positions={} open_desk_positions={} position_cap={} position_cap_scope=desk mlb_allocation_bps={} wnba_allocation_bps=833 mlb_per_game_cents={} wnba_per_game_cents={WNBA_PER_GAME_CENTS} order_submission={} liquidation={} stop_monitor=active live_capable={} live_implemented=true confirmation_set={} markets={} strategy_games={} wnba_games={} bankroll_cents={} per_game_cents={} open_slots={} max_open_slots={}",
        cfg.mode,
        cfg.live.enabled,
        cfg.live.confirmation == LIVE_CONFIRMATION,
        market_data,
        recon,
        unknown,
        kill,
        open_mlb,
        open_wnba,
        open_desk,
        risk.max_open_positions(),
        cfg.allocation_bps,
        risk.weekly_snapshot()
            .map(|s| s.max_position_budget().cents())
            .unwrap_or(0),
        if live_capable && !new_entry_blocked {
            "enabled"
        } else {
            "blocked"
        },
        if live_capable {
            "enabled"
        } else {
            "unimplemented"
        },
        live_capable,
        cfg.live.confirmation == LIVE_CONFIRMATION,
        markets,
        mlb.snapshot().games.len(),
        wnba.snapshot().games.len(),
        risk.weekly_snapshot()
            .map(|s| s.bankroll().cents())
            .unwrap_or(0),
        risk.weekly_snapshot()
            .map(|s| s.max_position_budget().cents())
            .unwrap_or(0),
        risk.open_slot_count(),
        risk.max_open_positions(),
    )
}

fn load_production_credentials() -> Result<KalshiCredentials, HostError> {
    refuse_if_demo(REST_PRODUCTION).map_err(|e| HostError::Venue(e.to_string()))?;
    let env = std::env::var(ENV_KALSHI_ENV).unwrap_or_default();
    if env != "production" {
        return Err(HostError::Preflight(
            "MOMENTO_KALSHI_ENV must be production".into(),
        ));
    }
    if let Ok(path) = std::env::var(momento_kalshi::ENV_KALSHI_SECRET_FILE) {
        return credentials_from_secret_file(KalshiEnvironment::Production, path.as_ref())
            .map_err(|e| HostError::Venue(e.to_string()));
    }
    KalshiCredentials::from_production_env().map_err(|e| HostError::Venue(e.to_string()))
}

fn preflight(
    cfg: &TradingConfig,
    state_dir: &Path,
    creds: &KalshiCredentials,
) -> Result<(), HostError> {
    let mut failures: Vec<String> = Vec::new();
    if cfg.mode != TradingMode::Live {
        failures.push("config mode is not live".into());
    }
    if !cfg.live.enabled {
        failures.push("live.enabled is not true".into());
    }
    if cfg.live.confirmation != LIVE_CONFIRMATION {
        failures.push("live.confirmation is not ENABLE_LIVE_TRADING".into());
    }
    if paper_mode_cannot_submit_production(cfg) {
        failures.push("paper mode is selected".into());
    }
    if aws_region().as_deref() != Some("us-east-1") {
        failures.push("AWS region is not us-east-1".into());
    }
    if std::env::var(ENV_KALSHI_ENV).ok().as_deref() != Some("production") {
        failures.push("production Kalshi environment is not selected".into());
    }
    if creds.environment() != KalshiEnvironment::Production {
        failures.push("credentials are not production-tagged".into());
    }
    if cfg.max_entry_price_cents != MAX_ENTRY {
        failures.push("entry <=83¢ is not active".into());
    }
    if cfg.allocation_bps == 0 || cfg.allocation_bps > 10_000 {
        failures.push("allocation_bps is not 1..=10000".into());
    }
    if kill_switch_requested(state_dir) {
        failures.push("kill switch is not OFF".into());
    }

    let mut transport = ProductionReadOnlyTransport::production(creds.clone())
        .map_err(|e| HostError::Preflight(e.to_string()))?;
    match transport.execute(KalshiHttpRequest {
        method: "GET".into(),
        path: EXCHANGE_STATUS_PATH.into(),
        body: None,
    }) {
        TransportOutcome::Http { status: 200, .. } => {}
        other => failures.push(format!("production authentication failed: {other:?}")),
    }
    match transport.execute(KalshiHttpRequest {
        method: "GET".into(),
        path: BALANCE_PATH.into(),
        body: None,
    }) {
        TransportOutcome::Http { status: 200, body } => {
            let parsed: Result<GetBalanceResponse, _> = serde_json::from_str(&body);
            let present = parsed
                .ok()
                .map(|b| b.balance_dollars.is_some() || b.balance >= 0)
                .unwrap_or_else(|| body.contains("balance"));
            if !present {
                failures.push("production account balance is not readable".into());
            }
        }
        other => failures.push(format!("production balance read failed: {other:?}")),
    }
    match transport.execute(KalshiHttpRequest {
        method: "GET".into(),
        path: format!("{MARKETS_PATH}?series_ticker={MLB_SERIES_TICKER}&status=open&limit=1"),
        body: None,
    }) {
        TransportOutcome::Http { status: 200, .. } => {}
        other => failures.push(format!(
            "MLB market-data connection is not healthy: {other:?}"
        )),
    }
    match transport.execute(KalshiHttpRequest {
        method: "GET".into(),
        path: format!("{MARKETS_PATH}?series_ticker={WNBA_SERIES_TICKER}&status=open&limit=1"),
        body: None,
    }) {
        TransportOutcome::Http { status: 200, .. } => {}
        other => failures.push(format!(
            "WNBA market-data connection is not healthy: {other:?}"
        )),
    }
    if transport.mutating_request_was_sent() {
        failures.push("read-only preflight sent a mutating request".into());
    }

    let snapshot = load_or_create_snapshot(cfg, state_dir)?;
    match expected_policy_budget(cfg) {
        Ok(expected) => {
            if snapshot.max_position_budget().cents() != expected.cents() {
                failures
                    .push("weekly snapshot budget does not match configured sizing policy".into());
            }
        }
        Err(err) => failures.push(err.to_string()),
    }

    let risk_config =
        RiskConfig::from_trading_config(cfg).map_err(|e| HostError::Config(e.to_string()))?;
    let risk = if live_state_file(state_dir).exists() {
        let persist = load_runtime(state_dir)?;
        PaperRiskEngine::restore(persist.risk, risk_config)
    } else {
        PaperRiskEngine::paper(snapshot.clone(), risk_config)
    };
    if risk.kill_switch() != KillSwitch::Armed {
        failures.push("risk kill switch is not OFF".into());
    }
    if risk.weekly_snapshot().is_none() {
        failures.push("risk engine is missing weekly snapshot".into());
    }

    let tracker = if live_state_file(state_dir).exists() {
        let persist = load_runtime(state_dir)?;
        InMemoryPositionTracker::restore_persist(persist.tracker)
    } else {
        InMemoryPositionTracker::new()
    };
    if tracker.reconciliation_state() != ReconciliationState::Healthy
        || tracker.has_unknown_orders()
        || risk.has_unknown_reservations()
    {
        eprintln!(
            "momento preflight recon={:?} unknown_orders={} unknown_reservations={} new_entry_blocked=true start_allowed=true reconcile_in_loop=true",
            tracker.reconciliation_state(),
            tracker.has_unknown_orders(),
            risk.has_unknown_reservations()
        );
    }
    risk.adopt_fill_authoritative_occupancy(tracker.positions());
    if risk.max_open_positions() != 5 {
        failures.push("max open desk positions is not 5".into());
    }
    restore_strategy(state_dir)?;
    restore_wnba_strategy(state_dir)?;

    eprintln!(
        "momento preflight auth=checked balance=checked risk=checked snapshot_cents={} per_game_cents={} open_slots={} max_open_slots={} recon={:?} unknown={} kill={:?} live_armed={} region={} env=production entry_max={} risk_approval_mandatory=true",
        snapshot.bankroll().cents(),
        snapshot.max_position_budget().cents(),
        risk.open_slot_count(),
        risk.max_open_positions(),
        tracker.reconciliation_state(),
        tracker.has_unknown_orders(),
        risk.kill_switch(),
        cfg.is_live_armed(),
        aws_region().unwrap_or_default(),
        cfg.max_entry_price_cents
    );

    if !failures.is_empty() {
        return Err(HostError::Preflight(format!(
            "pre-live validation failed (fail closed): {}",
            failures.join("; ")
        )));
    }
    Ok(())
}
