//! Isolated production host for a research ITI unit.
//!
//! Same First Touch / REACH machine as demo. Production Kalshi only after the
//! triple live gate. Does not load MLB 80/81. Does not share momento-live.service.

use std::path::Path;

use momento_core::error::VenueError;
use momento_core::{
    ApprovedTradeIntent, ClientOrderId, EntryPriceGate, GameId, LIVE_CONFIRMATION, MarketEvent,
    MomentoError, Order, ReceivedAt, ReconciliationState, RiskDecision, StrategyId, TradingConfig,
    TradingMode, WeeklyBankrollSnapshot, utc_now,
};
use momento_kalshi::{
    ENV_KALSHI_ENV, KalshiCredentials, KalshiEnvironment, KalshiTransport, KalshiVenue,
    MarketBinding, ProductionTradingTransport, REST_PRODUCTION, StaticIdentity, VenueIdentity,
    credentials_from_secret_file, redact_secrets, refuse_if_demo,
};
use momento_positions::{InMemoryPositionTracker, PositionEvent, PositionTracker};
use momento_risk::{PaperRiskEngine, RiskConfig};
use momento_strategy_research_iti::{
    ItiContext, ItiDirective, ItiStrategy, RESEARCH_ITI_STRATEGY_ID,
};

use crate::demo::{
    demo_series_ticker, ingest_fills, iti_prices, load_or_create_snapshot, load_runtime,
    persist_iti_strategy, persist_runtime, poll_demo_markets, restore_iti_strategy,
};
use crate::live::{
    entry_price_exceeds_max, kill_switch_requested, live_state_file,
    paper_mode_cannot_submit_production, per_game_budget,
};
use crate::runtime::{HostError, heartbeat_period, load_iti_live_config};

const FACTORY_STATE: &str = "/var/lib/momento/state";
const FACTORY_CONFIG: &str = "/var/lib/momento/config/live.toml";

pub fn factory_live_unit_refused(config_path: &Path, state_dir: &Path) -> Result<(), HostError> {
    let factory_unit = std::env::var("MOMENTO_FACTORY_UNIT").unwrap_or_default();
    if factory_unit.trim().eq_ignore_ascii_case("1")
        || factory_unit.trim().eq_ignore_ascii_case("true")
        || factory_unit.trim().eq_ignore_ascii_case("yes")
    {
        return Err(HostError::Preflight(
            "research_iti cannot run on the momento-live factory unit".into(),
        ));
    }
    let config = config_path.to_string_lossy();
    let state = state_dir.to_string_lossy();
    if config == FACTORY_CONFIG || state == FACTORY_STATE {
        return Err(HostError::Preflight(
            "research_iti cannot use factory live.toml or /var/lib/momento/state".into(),
        ));
    }
    Ok(())
}

pub fn iti_live_preflight_config(cfg: &TradingConfig) -> Result<(), HostError> {
    let mut failures: Vec<String> = Vec::new();
    if cfg.mode != TradingMode::Live {
        failures.push("config mode is not live".into());
    }
    if !cfg.is_research_iti() {
        failures.push("ITI live requires strategy_profile = research_iti".into());
    }
    if !cfg.is_live_armed() {
        failures.push("triple live gate is incomplete".into());
    }
    if cfg.iti_entry_cents.is_none() || cfg.iti_win_cents.is_none() || cfg.iti_loss_cents.is_none()
    {
        failures.push("ITI live prices are required".into());
    }
    if cfg.min_entry_price_cents == 80 && cfg.max_entry_price_cents == 83 {
        failures.push("ITI live cannot use the factory 80–83 band".into());
    }
    if paper_mode_cannot_submit_production(cfg) {
        failures.push("paper/replay cannot submit on the ITI live path".into());
    }
    if !failures.is_empty() {
        return Err(HostError::Preflight(failures.join("; ")));
    }
    Ok(())
}

pub fn iti_live_preflight_env_label(label: &str) -> Result<(), HostError> {
    if !label.trim().eq_ignore_ascii_case("production") {
        return Err(HostError::Preflight(
            "MOMENTO_KALSHI_ENV must be production on the ITI live path".into(),
        ));
    }
    Ok(())
}

fn load_iti_live_credentials() -> Result<KalshiCredentials, HostError> {
    refuse_if_demo(REST_PRODUCTION).map_err(|e| HostError::Venue(e.to_string()))?;
    iti_live_preflight_env_label(&std::env::var(ENV_KALSHI_ENV).unwrap_or_default())?;
    if let Ok(path) = std::env::var(momento_kalshi::ENV_KALSHI_SECRET_FILE) {
        return credentials_from_secret_file(KalshiEnvironment::Production, path.as_ref())
            .map_err(|e| HostError::Preflight(e.to_string()));
    }
    KalshiCredentials::from_production_env().map_err(|e| HostError::Preflight(e.to_string()))
}

pub fn submit_iti_live_approved<T: KalshiTransport, I: VenueIdentity>(
    cfg: &TradingConfig,
    tracker: &mut InMemoryPositionTracker,
    risk: &PaperRiskEngine,
    venue: &mut KalshiVenue<T, I>,
    approved: ApprovedTradeIntent,
) -> Result<ClientOrderId, HostError> {
    if let Err(err) = iti_live_preflight_config(cfg) {
        risk.on_cancel(approved.client_order_id());
        return Err(err);
    }
    if let Err(err) =
        iti_live_preflight_env_label(&std::env::var(ENV_KALSHI_ENV).unwrap_or_default())
    {
        risk.on_cancel(approved.client_order_id());
        return Err(err);
    }
    let max = cfg
        .max_entry_price()
        .map_err(|e| HostError::Config(e.to_string()))?;
    if entry_price_exceeds_max(approved.limit_price(), max) {
        risk.on_cancel(approved.client_order_id());
        return Err(HostError::Config(format!(
            "entry exceeds ITI live max {} cents",
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

fn submit_iti_live_reach<T: KalshiTransport, I: VenueIdentity>(
    cfg: &TradingConfig,
    tracker: &mut InMemoryPositionTracker,
    risk: &PaperRiskEngine,
    venue: &mut KalshiVenue<T, I>,
    exec: &momento_strategy_research_iti::ReachExecution,
) -> Result<ClientOrderId, HostError> {
    iti_live_preflight_config(cfg)?;
    iti_live_preflight_env_label(&std::env::var(ENV_KALSHI_ENV).unwrap_or_default())?;
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

pub fn observe_iti_live_event<T: KalshiTransport, I: VenueIdentity>(
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
            per_game_budget(snapshot, StrategyId::RESEARCH_ITI),
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
                        if let Err(err) =
                            submit_iti_live_approved(cfg, tracker, risk, venue, approved)
                        {
                            eprintln!(
                                "momento iti_live_submit_refused={}",
                                redact_secrets(&err.to_string())
                            );
                        }
                    }
                    RiskDecision::Rejected { reason, .. } => {
                        eprintln!("momento iti_live_risk_rejected={reason:?}");
                    }
                }
            }
            ItiDirective::ExecuteReach(exec) => {
                if let Some(pos) = tracker.get_mut(exec.position_id) {
                    pos.begin_liquidation();
                }
                if let Err(err) = submit_iti_live_reach(cfg, tracker, risk, venue, &exec) {
                    eprintln!(
                        "momento iti_live_reach_refused={}",
                        redact_secrets(&err.to_string())
                    );
                }
            }
        }
    }
}

pub fn run_iti_live(config_path: &Path, state_dir: &Path) -> Result<(), HostError> {
    factory_live_unit_refused(config_path, state_dir)?;
    let cfg = load_iti_live_config(config_path)?;
    iti_live_preflight_config(&cfg)?;
    iti_live_preflight_env_label(&std::env::var(ENV_KALSHI_ENV).unwrap_or_default())?;
    if kill_switch_requested(state_dir) {
        return Err(HostError::Preflight("kill switch is not OFF".into()));
    }
    let sport = cfg
        .sport
        .as_deref()
        .ok_or_else(|| HostError::Config("ITI live sport required".into()))?;
    let series = demo_series_ticker(sport)?;
    let prices = iti_prices(&cfg)?;
    let creds = load_iti_live_credentials()?;
    if creds.environment() != KalshiEnvironment::Production {
        return Err(HostError::Preflight(
            "credentials are not production-tagged".into(),
        ));
    }
    eprintln!(
        "momento-trading-engine start config={} state_dir={} mode=live strategy_profile=research_iti sport={} series={} live.enabled=true live_armed=true factory_unit=false confirmation={}",
        config_path.display(),
        state_dir.display(),
        sport,
        series,
        cfg.live.confirmation == LIVE_CONFIRMATION
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
            "momento iti_live_preflight recon={:?} unknown={} new_entry_blocked=true",
            tracker.reconciliation_state(),
            tracker.has_unknown_orders()
        );
    }
    let mut strategy = restore_iti_strategy(state_dir, prices)?;
    persist_iti_strategy(state_dir, &strategy)?;
    let transport = ProductionTradingTransport::production(creds)
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
                    observe_iti_live_event(
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
                "momento iti_live_poll_error={}",
                redact_secrets(&err.to_string())
            ),
        }
        ingest_fills(&mut venue, &mut tracker, &risk);
        if tracker.release_ambiguous_if_no_live_uncertainty() {
            eprintln!(
                "momento recon_cleared reason=no_unknown_no_live_uncertain env=production_iti"
            );
        }
        persist_runtime(state_dir, &strategy, &tracker, &risk, &venue)?;
        eprintln!(
            "momento iti_live_heartbeat sport={} series={} games={} open_slots={} live_armed=true env=production",
            sport,
            series,
            strategy.snapshot().games.len(),
            risk.open_slot_count()
        );
        std::thread::sleep(heartbeat_period());
    }
}
