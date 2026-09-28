//! Isolated Kalshi Demo host for a research ITI unit.
//!
//! Observes YES bid → First Touch / REACH → existing Risk → Demo submit.
//! Production credentials, production origin, and ENABLE_LIVE_TRADING are refused.
//! Does not load MLB 80/81. Does not write ITI state into momento-live.

use std::fs;
use std::path::Path;

use momento_core::error::VenueError;
use momento_core::snapshot::belongs_to_week;
use momento_core::{
    ApprovedTradeIntent, ClientOrderId, EntryPriceGate, GameId, LIVE_CONFIRMATION, MarketEvent,
    MomentoError, Money, Order, PositionSizingMode, ReceivedAt, ReconciliationState, RiskDecision,
    SnapshotSource, StrategyId, TradingConfig, TradingMode, WeeklyBankrollSnapshot, utc_now,
};
use momento_kalshi::{
    ENV_KALSHI_ENV, KalshiCredentials, KalshiEnvironment, KalshiHttpRequest, KalshiTransport,
    KalshiVenue, MarketBinding, REST_DEMO_ORIGIN, SandboxHttpTransport, StaticIdentity,
    TransportOutcome, VenueIdentity, credentials_from_secret_file, game_id_for_event_ticker,
    map_market, market_id_for_ticker, redact_secrets, refuse_if_production,
};
use momento_positions::{InMemoryPositionTracker, PositionEvent, PositionTracker, TrackerPersist};
use momento_risk::{PaperRiskEngine, RiskConfig, RiskPersist};
use momento_strategy_research_iti::{
    ItiContext, ItiDirective, ItiPrices, ItiStrategy, ItiStrategySnapshot, RESEARCH_ITI_STRATEGY_ID,
};
use serde::{Deserialize, Serialize};

use crate::live::{
    LIVE_STATE_FILE_NAME, SNAPSHOT_FILE_NAME, entry_price_exceeds_max, kill_switch_requested,
    live_market_event_from_snapshot, live_state_file, paper_mode_cannot_submit_production,
    reconcile_unknowns, snapshot_file,
};
use crate::runtime::{HostError, heartbeat_period, load_demo_config};

pub const ITI_STATE_FILE_NAME: &str = "iti-strategy.json";

const MLB_SERIES: &str = "KXMLBGAME";
const NBA_SERIES: &str = "KXNBAGAME";
const NCAAB_SERIES: &str = "KXNCAAMBGAME";
const WNBA_SERIES: &str = "KXWNBAGAME";
const ATP_SERIES: &str = "KXATPMATCH";
const WTA_SERIES: &str = "KXWTAMATCH";

#[derive(Clone, Debug, Serialize, Deserialize)]
pub(crate) struct DemoRuntimeFile {
    pub(crate) tracker: TrackerPersist,
    pub(crate) risk: RiskPersist,
    pub(crate) venue_by_client: Vec<(u128, u128)>,
    pub(crate) unknown_submissions: Vec<u128>,
    #[serde(default)]
    pub(crate) identity: Vec<(String, u128, u128)>,
}

pub fn demo_series_ticker(sport: &str) -> Result<&'static str, HostError> {
    match sport.trim().to_ascii_lowercase().as_str() {
        "mlb" => Ok(MLB_SERIES),
        "nba" => Ok(NBA_SERIES),
        "ncaab" => Ok(NCAAB_SERIES),
        "wnba" => Ok(WNBA_SERIES),
        "atp" => Ok(ATP_SERIES),
        "wta" => Ok(WTA_SERIES),
        other => Err(HostError::Config(format!(
            "unsupported demo sport: {other}"
        ))),
    }
}

pub fn demo_env_is_production(label: &str) -> bool {
    matches!(
        label.trim().to_ascii_lowercase().as_str(),
        "production" | "prod" | "live"
    )
}

pub fn demo_preflight_config(cfg: &TradingConfig) -> Result<(), HostError> {
    let mut failures: Vec<String> = Vec::new();
    if cfg.mode != TradingMode::Demo {
        failures.push("config mode is not demo".into());
    }
    if cfg.live.enabled {
        failures.push("live.enabled must be false on demo".into());
    }
    if cfg.live.confirmation == LIVE_CONFIRMATION {
        failures.push("demo forbids ENABLE_LIVE_TRADING".into());
    }
    if !cfg.is_research_iti() {
        failures.push("demo requires strategy_profile = research_iti".into());
    }
    if cfg.iti_entry_cents.is_none() || cfg.iti_win_cents.is_none() || cfg.iti_loss_cents.is_none()
    {
        failures.push("demo research_iti prices are required".into());
    }
    if cfg.is_live_armed() {
        failures.push("demo cannot be live-armed".into());
    }
    if paper_mode_cannot_submit_production(cfg) {
        failures.push("paper/replay cannot submit on the demo path".into());
    }
    if !failures.is_empty() {
        return Err(HostError::Preflight(failures.join("; ")));
    }
    Ok(())
}

pub fn demo_preflight_env_label(label: &str) -> Result<(), HostError> {
    if demo_env_is_production(label) {
        return Err(HostError::Preflight(
            "production Kalshi environment is refused on the demo path".into(),
        ));
    }
    if !label.trim().eq_ignore_ascii_case("demo") && !label.trim().eq_ignore_ascii_case("sandbox") {
        return Err(HostError::Preflight(
            "MOMENTO_KALSHI_ENV must be demo".into(),
        ));
    }
    Ok(())
}

pub fn demo_preflight_env() -> Result<(), HostError> {
    demo_preflight_env_label(&std::env::var(ENV_KALSHI_ENV).unwrap_or_default())
}

pub(crate) fn iti_prices(cfg: &TradingConfig) -> Result<ItiPrices, HostError> {
    let entry = cfg
        .iti_entry_cents
        .ok_or_else(|| HostError::Config("iti_entry_cents missing".into()))?;
    let win = cfg
        .iti_win_cents
        .ok_or_else(|| HostError::Config("iti_win_cents missing".into()))?;
    let loss = cfg
        .iti_loss_cents
        .ok_or_else(|| HostError::Config("iti_loss_cents missing".into()))?;
    ItiPrices::from_cents(entry, win, loss).map_err(|e| HostError::Config(e.to_string()))
}

fn iti_state_file(state_dir: &Path) -> std::path::PathBuf {
    state_dir.join(ITI_STATE_FILE_NAME)
}

pub fn restore_iti_strategy(state_dir: &Path, prices: ItiPrices) -> Result<ItiStrategy, HostError> {
    let path = iti_state_file(state_dir);
    if !path.exists() {
        return Ok(ItiStrategy::new(prices));
    }
    let raw = fs::read_to_string(&path).map_err(|e| HostError::Io(e.to_string()))?;
    let snap: ItiStrategySnapshot =
        serde_json::from_str(&raw).map_err(|e| HostError::Io(e.to_string()))?;
    if snap.prices.entry_cents != prices.entry.cents()
        || snap.prices.win_cents != prices.win.cents()
        || snap.prices.loss_cents != prices.loss.cents()
    {
        return Err(HostError::Config(
            "iti-strategy.json prices do not match this unit's ITI spec".into(),
        ));
    }
    ItiStrategy::restore(snap).map_err(|e| HostError::Io(e.to_string()))
}

pub fn persist_iti_strategy(state_dir: &Path, strategy: &ItiStrategy) -> Result<(), HostError> {
    fs::create_dir_all(state_dir).map_err(|e| HostError::Io(e.to_string()))?;
    let path = iti_state_file(state_dir);
    let tmp = state_dir.join(format!("{ITI_STATE_FILE_NAME}.tmp"));
    let json = serde_json::to_string_pretty(&strategy.snapshot())
        .map_err(|e| HostError::Io(e.to_string()))?;
    fs::write(&tmp, json).map_err(|e| HostError::Io(e.to_string()))?;
    fs::rename(tmp, path).map_err(|e| HostError::Io(e.to_string()))
}

fn atomic_json<T: Serialize>(state_dir: &Path, name: &str, value: &T) -> Result<(), HostError> {
    fs::create_dir_all(state_dir).map_err(|e| HostError::Io(e.to_string()))?;
    let path = state_dir.join(name);
    let tmp = state_dir.join(format!("{name}.tmp"));
    let json = serde_json::to_string_pretty(value).map_err(|e| HostError::Io(e.to_string()))?;
    fs::write(&tmp, json).map_err(|e| HostError::Io(e.to_string()))?;
    fs::rename(tmp, path).map_err(|e| HostError::Io(e.to_string()))
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

pub(crate) fn load_or_create_snapshot(
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

pub(crate) fn load_runtime(state_dir: &Path) -> Result<DemoRuntimeFile, HostError> {
    let raw =
        fs::read_to_string(live_state_file(state_dir)).map_err(|e| HostError::Io(e.to_string()))?;
    serde_json::from_str(&raw).map_err(|e| HostError::Io(e.to_string()))
}

pub(crate) fn persist_runtime<T: KalshiTransport>(
    state_dir: &Path,
    strategy: &ItiStrategy,
    tracker: &InMemoryPositionTracker,
    risk: &PaperRiskEngine,
    venue: &KalshiVenue<T, StaticIdentity>,
) -> Result<(), HostError> {
    persist_iti_strategy(state_dir, strategy)?;
    let risk_state = risk
        .persist_state()
        .ok_or_else(|| HostError::Io("risk persist missing snapshot".into()))?;
    let file = DemoRuntimeFile {
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

fn load_demo_credentials() -> Result<KalshiCredentials, HostError> {
    refuse_if_production(REST_DEMO_ORIGIN).map_err(|e| HostError::Venue(e.to_string()))?;
    demo_preflight_env()?;
    if let Ok(path) = std::env::var(momento_kalshi::ENV_KALSHI_SECRET_FILE) {
        return credentials_from_secret_file(KalshiEnvironment::Demo, path.as_ref())
            .map_err(|e| HostError::Preflight(e.to_string()));
    }
    KalshiCredentials::from_env().map_err(|e| HostError::Preflight(e.to_string()))
}

fn demo_cannot_submit(cfg: &TradingConfig) -> Result<(), HostError> {
    demo_preflight_config(cfg)?;
    if let Ok(env) = std::env::var(ENV_KALSHI_ENV) {
        demo_preflight_env_label(&env)?;
    }
    Ok(())
}

pub fn submit_demo_approved<T: KalshiTransport, I: VenueIdentity>(
    cfg: &TradingConfig,
    tracker: &mut InMemoryPositionTracker,
    risk: &PaperRiskEngine,
    venue: &mut KalshiVenue<T, I>,
    approved: ApprovedTradeIntent,
) -> Result<ClientOrderId, HostError> {
    if let Err(err) = demo_cannot_submit(cfg) {
        risk.on_cancel(approved.client_order_id());
        return Err(err);
    }
    let max = cfg
        .max_entry_price()
        .map_err(|e| HostError::Config(e.to_string()))?;
    if entry_price_exceeds_max(approved.limit_price(), max) {
        risk.on_cancel(approved.client_order_id());
        return Err(HostError::Config(format!(
            "entry exceeds demo max {} cents",
            max.cents()
        )));
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
    match venue.submit_post_only(&order, &ticker) {
        Ok(venue_id) => {
            let _ = tracker.apply_event(PositionEvent::OrderWorking {
                client_order_id: approved.client_order_id(),
                venue_order_id: venue_id,
            });
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

fn submit_demo_reach<T: KalshiTransport, I: VenueIdentity>(
    cfg: &TradingConfig,
    tracker: &mut InMemoryPositionTracker,
    risk: &PaperRiskEngine,
    venue: &mut KalshiVenue<T, I>,
    exec: &momento_strategy_research_iti::ReachExecution,
) -> Result<ClientOrderId, HostError> {
    demo_cannot_submit(cfg)?;
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
    let (decision_id, client_order_id) = risk
        .approve_liquidation(&pos)
        .map_err(|reason| HostError::Venue(format!("liquidation risk rejected: {reason:?}")))?;
    if tracker.order(client_order_id).is_some() {
        return Ok(client_order_id);
    }
    let ticker = venue
        .identity()
        .ticker_for_market(exec.market_id)
        .ok_or_else(|| HostError::Venue("liquidation ticker is not mapped".into()))?;
    let order = Order::new_liquidation(
        client_order_id,
        exec.position_id,
        exec.game_id,
        decision_id,
        exec.suggested_limit,
        exec.quantity,
        exec.market_id,
        exec.side,
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
            Ok(client_order_id)
        }
        Err(MomentoError::Venue(VenueError::Timeout | VenueError::AmbiguousSubmission)) => {
            let _ = tracker.apply_event(PositionEvent::Unknown { client_order_id });
            risk.mark_unknown(client_order_id, exec.position_id);
            Err(HostError::Venue(
                "liquidation state UNKNOWN; reconcile before resubmit".into(),
            ))
        }
        Err(other) => {
            let _ = tracker.apply_event(PositionEvent::Unknown { client_order_id });
            risk.mark_unknown(client_order_id, exec.position_id);
            Err(HostError::Venue(redact_secrets(&other.to_string())))
        }
    }
}

#[allow(clippy::too_many_arguments)]
pub fn observe_demo_event<T: KalshiTransport, I: VenueIdentity>(
    _state_dir: &Path,
    cfg: &TradingConfig,
    strategy: &mut ItiStrategy,
    tracker: &mut InMemoryPositionTracker,
    risk: &PaperRiskEngine,
    venue: &mut KalshiVenue<T, I>,
    snapshot: &WeeklyBankrollSnapshot,
    event: MarketEvent,
) {
    let assigned = tracker
        .get_or_create_with_budget(
            RESEARCH_ITI_STRATEGY_ID,
            event.game_id,
            snapshot,
            crate::live::per_game_budget(snapshot, StrategyId::RESEARCH_ITI),
            Some(event.market_id),
            event.side,
        )
        .id();
    let recon = tracker.reconciliation_state();
    let ctx = ItiContext {
        event: &event,
        position: tracker.get(assigned),
        assigned_position_id: Some(assigned),
        recon,
        kill_switch: risk.kill_switch(),
        has_working_entry: tracker.has_working_entry(event.game_id),
        unknown_entry_order: tracker.has_unknown_entry(event.game_id),
        has_working_liquidation: tracker.has_working_liquidation_for_position(assigned),
        unknown_liquidation_order: tracker.has_unknown_liquidation_for_position(assigned),
    };
    let turn = strategy.observe(&ctx);
    for directive in turn.directives {
        match directive {
            ItiDirective::Build(intent) => {
                if recon.blocks_new_exposure() || tracker.has_unknown_orders() {
                    continue;
                }
                if let Some(pos) = tracker.get_mut(intent.build.position_id) {
                    if pos.entry_price_gate() == EntryPriceGate::PausedAboveMaxPrice {
                        pos.resume_entry_if_unlocked();
                    }
                }
                let Some(pos) = tracker.get(intent.build.position_id).cloned() else {
                    continue;
                };
                match risk.decide_entry(&intent, &pos) {
                    RiskDecision::Approved(approved) => {
                        if let Err(err) = submit_demo_approved(cfg, tracker, risk, venue, approved)
                        {
                            eprintln!(
                                "momento demo_submit_refused={}",
                                redact_secrets(&err.to_string())
                            );
                        }
                    }
                    RiskDecision::Rejected { reason, .. } => {
                        eprintln!("momento demo_risk_rejected={reason:?}");
                    }
                }
            }
            ItiDirective::ExecuteReach(exec) => {
                if let Some(pos) = tracker.get_mut(exec.position_id) {
                    pos.begin_liquidation();
                }
                if let Err(err) = submit_demo_reach(cfg, tracker, risk, venue, &exec) {
                    eprintln!(
                        "momento demo_reach_refused={}",
                        redact_secrets(&err.to_string())
                    );
                }
            }
        }
    }
}

pub fn poll_demo_markets<T: KalshiTransport>(
    venue: &mut KalshiVenue<T, StaticIdentity>,
    received_at: ReceivedAt,
    series: &str,
) -> Result<Vec<MarketEvent>, HostError> {
    let mut events = Vec::new();
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
            let snap = match map_market(&market, received_at, Some(market_id), Some(game_id)) {
                Ok(s) => s,
                Err(_) => continue,
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

pub(crate) use crate::live::ingest_fills;

pub fn run_demo(config_path: &Path, state_dir: &Path) -> Result<(), HostError> {
    let cfg = load_demo_config(config_path)?;
    demo_preflight_config(&cfg)?;
    demo_preflight_env()?;
    if kill_switch_requested(state_dir) {
        return Err(HostError::Preflight("kill switch is not OFF".into()));
    }
    let sport = cfg
        .sport
        .as_deref()
        .ok_or_else(|| HostError::Config("demo sport required".into()))?;
    let series = demo_series_ticker(sport)?;
    let prices = iti_prices(&cfg)?;
    let creds = load_demo_credentials()?;
    if creds.environment() != KalshiEnvironment::Demo {
        return Err(HostError::Preflight(
            "credentials are not demo-tagged".into(),
        ));
    }
    eprintln!(
        "momento-trading-engine start config={} state_dir={} mode=demo strategy_profile=research_iti sport={} series={} live.enabled=false live_armed=false",
        config_path.display(),
        state_dir.display(),
        sport,
        series
    );

    let snapshot = load_or_create_snapshot(&cfg, state_dir)?;
    let risk_config =
        RiskConfig::from_trading_config(&cfg).map_err(|e| HostError::Config(e.to_string()))?;
    let (mut tracker, risk, venue_by_client, unknown_submissions, identity_bindings) =
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
    if tracker.reconciliation_state() != ReconciliationState::Healthy
        || tracker.has_unknown_orders()
    {
        eprintln!(
            "momento demo_preflight recon={:?} unknown={} new_entry_blocked=true",
            tracker.reconciliation_state(),
            tracker.has_unknown_orders()
        );
    }
    let mut strategy = restore_iti_strategy(state_dir, prices)?;
    let transport =
        SandboxHttpTransport::demo(creds).map_err(|e| HostError::Venue(e.to_string()))?;
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
    let mut venue = KalshiVenue::sandbox(transport, identity, ReceivedAt::from_utc(utc_now()));
    venue.restore_venue_map(venue_by_client);
    venue.restore_unknown_submissions(unknown_submissions);
    persist_runtime(state_dir, &strategy, &tracker, &risk, &venue)?;

    loop {
        if kill_switch_requested(state_dir) {
            risk.trip_kill_switch();
            eprintln!("momento kill_switch=TRIPPED new_entry_blocked=true flatten=false");
        }
        let received_at = ReceivedAt::from_utc(utc_now());
        venue.set_received_at(received_at);
        match poll_demo_markets(&mut venue, received_at, series) {
            Ok(events) => {
                for event in events {
                    observe_demo_event(
                        state_dir,
                        &cfg,
                        &mut strategy,
                        &mut tracker,
                        &risk,
                        &mut venue,
                        &snapshot,
                        event,
                    );
                }
            }
            Err(err) => eprintln!(
                "momento demo_poll_error={}",
                redact_secrets(&err.to_string())
            ),
        }
        reconcile_unknowns(&mut venue, &mut tracker, &risk);
        ingest_fills(&mut venue, &mut tracker, &risk);
        if tracker.release_ambiguous_if_no_live_uncertainty() {
            eprintln!("momento recon_cleared reason=no_unknown_no_live_uncertain env=demo");
        }
        persist_runtime(state_dir, &strategy, &tracker, &risk, &venue)?;
        eprintln!(
            "momento demo_heartbeat sport={} series={} games={} open_slots={} unknown={} live_armed=false env=demo",
            sport,
            series,
            strategy.snapshot().games.len(),
            risk.open_slot_count(),
            tracker.unknown_order_ids().count()
        );
        std::thread::sleep(heartbeat_period());
    }
}

/// Read-only Demo exchange probe used by preflight tests. Does not submit.
pub fn demo_read_only_preflight<T: KalshiTransport>(
    transport: &mut T,
    path: &str,
) -> Result<(), HostError> {
    match transport.execute(KalshiHttpRequest {
        method: "GET".into(),
        path: path.into(),
        body: None,
    }) {
        TransportOutcome::Http { status: 200, .. } => Ok(()),
        other => Err(HostError::Preflight(format!(
            "demo preflight failed: {other:?}"
        ))),
    }
}
