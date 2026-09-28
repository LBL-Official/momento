use std::fs;
use std::sync::{Arc, Mutex};
use std::time::{SystemTime, UNIX_EPOCH};

use momento_core::{
    ExchangeTimestamp, MarketEvent, Price, ReceivedAt, RiskDecision, Side, SnapshotSource,
    TradingMode, utc_now,
};
use momento_kalshi::{
    CREATE_ORDER_PATH, KalshiHttpRequest, KalshiTransport, KalshiVenue, MarketBinding,
    REST_DEMO_ORIGIN, REST_PRODUCTION, ScriptedTransport, StaticIdentity, TransportOutcome,
    encode_venue_order_id, game_id_for_event_ticker, market_id_for_ticker, refuse_if_production,
};
use momento_positions::InMemoryPositionTracker;
use momento_risk::{PaperRiskEngine, RiskConfig};
use momento_strategy_research_iti::{ItiGamePhase, ItiStrategy};
use momento_trading_engine::demo::{
    demo_env_is_production, demo_preflight_config, demo_preflight_env_label, observe_demo_event,
    restore_iti_strategy, submit_demo_approved,
};
use momento_trading_engine::runtime::{HostError, load_demo_config, load_live_config};

fn tmp_dir() -> std::path::PathBuf {
    let nanos = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap()
        .as_nanos();
    let dir = std::env::temp_dir().join(format!(
        "momento-demo-host-{}-{}",
        nanos,
        std::process::id()
    ));
    fs::create_dir_all(&dir).unwrap();
    dir
}

fn demo_toml() -> &'static str {
    r#"
mode = "demo"
timezone = "America/Los_Angeles"
allocation_bps = 1250
max_entry_price_cents = 59
preferred_entry_price_cents = 20
min_entry_price_cents = 20
initial_bankroll_cents = 5000
sizing_mode = "FIXED_CENTS"
max_position_budget_cents = 625
strategy_profile = "research_iti"
iti_entry_cents = 20
iti_win_cents = 60
iti_loss_cents = 10
sport = "mlb"
[live]
enabled = false
confirmation = ""
"#
}

fn write_demo_cfg() -> (std::path::PathBuf, momento_core::TradingConfig) {
    let dir = tmp_dir();
    let path = dir.join("demo.toml");
    fs::write(&path, demo_toml()).unwrap();
    let cfg = load_demo_config(&path).unwrap();
    (dir, cfg)
}

fn weekly50() -> momento_core::WeeklyBankrollSnapshot {
    momento_core::WeeklyBankrollSnapshot::capture(
        momento_core::Money::from_usd(50, 0).unwrap(),
        momento_core::Bps::PCT_12_5,
        utc_now(),
        SnapshotSource::Test,
    )
    .unwrap()
}

fn iti_risk(
    cfg: &momento_core::TradingConfig,
    snap: &momento_core::WeeklyBankrollSnapshot,
) -> PaperRiskEngine {
    PaperRiskEngine::paper(snap.clone(), RiskConfig::from_trading_config(cfg).unwrap())
}

fn bound_identity() -> (
    StaticIdentity,
    String,
    momento_core::MarketId,
    momento_core::GameId,
) {
    let ticker = "KXMLBGAME-TEST".to_string();
    let event_ticker = "KXMLBGAME-EVT";
    let market_id = market_id_for_ticker(&ticker);
    let game_id = game_id_for_event_ticker(event_ticker);
    let mut identity = StaticIdentity::new();
    identity.bind(
        ticker.clone(),
        MarketBinding {
            market_id,
            game_id,
            position_id: None,
        },
    );
    (identity, ticker, market_id, game_id)
}

fn quote_event(
    bid: u16,
    market_id: momento_core::MarketId,
    game_id: momento_core::GameId,
) -> MarketEvent {
    let t = utc_now();
    MarketEvent {
        game_id,
        market_id,
        side: Some(Side::Yes),
        exchange_ts: ExchangeTimestamp::from_utc(t),
        received_at: ReceivedAt::from_utc(t),
        last: None,
        bid: Some(Price::from_cents(bid).unwrap()),
        ask: Some(Price::from_cents(bid.saturating_add(1).min(99)).unwrap()),
        mid: None,
        bid_depth: Some(4),
        ask_depth: Some(4),
        game_state: None,
    }
}

struct RecordingTransport {
    inner: ScriptedTransport,
    captured: Arc<Mutex<Vec<KalshiHttpRequest>>>,
}

impl KalshiTransport for RecordingTransport {
    fn execute(&mut self, request: KalshiHttpRequest) -> TransportOutcome {
        self.captured
            .lock()
            .expect("capture lock")
            .push(request.clone());
        self.inner.execute(request)
    }
}

#[test]
fn demo_config_loads_and_live_stays_locked() {
    let (_dir, cfg) = write_demo_cfg();
    assert_eq!(cfg.mode, TradingMode::Demo);
    assert!(cfg.is_research_iti());
    assert!(!cfg.is_live_armed());
    demo_preflight_config(&cfg).unwrap();
    let live = std::path::Path::new(env!("CARGO_MANIFEST_DIR")).join("../../config/live.toml");
    let live_cfg = load_live_config(&live).unwrap();
    assert_eq!(live_cfg.max_entry_price_cents, 83);
    assert_eq!(live_cfg.min_entry_price_cents, 80);
}

#[test]
fn production_env_is_refused() {
    assert!(demo_env_is_production("production"));
    assert!(demo_preflight_env_label("production").is_err());
    assert!(demo_preflight_env_label("prod").is_err());
    assert!(demo_preflight_env_label("demo").is_ok());
    assert!(refuse_if_production(REST_PRODUCTION).is_err());
    assert!(refuse_if_production(REST_DEMO_ORIGIN).is_ok());
}

#[test]
fn live_toml_cannot_load_as_demo() {
    let path = std::path::Path::new(env!("CARGO_MANIFEST_DIR")).join("../../config/live.toml");
    match load_demo_config(&path) {
        Err(HostError::Preflight(_) | HostError::Config(_)) => {}
        other => panic!("live toml must not load as demo: {other:?}"),
    }
}

#[test]
fn unapproved_intent_never_submitted() {
    let (dir, cfg) = write_demo_cfg();
    let snap = weekly50();
    let captured = Arc::new(Mutex::new(Vec::new()));
    let transport = RecordingTransport {
        inner: ScriptedTransport::new([]),
        captured: Arc::clone(&captured),
    };
    let (identity, _, market_id, game_id) = bound_identity();
    let mut venue = KalshiVenue::sandbox(transport, identity, ReceivedAt::from_utc(utc_now()));
    let mut strategy =
        ItiStrategy::new(momento_strategy_research_iti::ItiPrices::from_cents(20, 60, 10).unwrap());
    let mut tracker = InMemoryPositionTracker::new();
    let risk = iti_risk(&cfg, &snap);
    observe_demo_event(
        &dir,
        &cfg,
        &mut strategy,
        &mut tracker,
        &risk,
        &mut venue,
        &snap,
        quote_event(19, market_id, game_id),
    );
    observe_demo_event(
        &dir,
        &cfg,
        &mut strategy,
        &mut tracker,
        &risk,
        &mut venue,
        &snap,
        quote_event(70, market_id, game_id),
    );
    assert_eq!(strategy.phase(game_id), ItiGamePhase::EntryProposed);
    assert!(captured.lock().unwrap().is_empty());
    assert_eq!(tracker.snapshot_persist().orders.len(), 0);
}

#[test]
fn crossing_40_submits_after_risk() {
    let (dir, cfg) = write_demo_cfg();
    let snap = weekly50();
    let captured = Arc::new(Mutex::new(Vec::new()));
    let ack = format!(
        r#"{{"order_id":"{}","fill_count":"0.00","remaining_count":"7.00","ts_ms":1715793600123}}"#,
        encode_venue_order_id(momento_core::VenueOrderId::from_raw(99))
    );
    let transport = RecordingTransport {
        inner: ScriptedTransport::new([TransportOutcome::Http {
            status: 201,
            body: ack,
        }]),
        captured: Arc::clone(&captured),
    };
    let (identity, _, market_id, game_id) = bound_identity();
    let mut venue = KalshiVenue::sandbox(transport, identity, ReceivedAt::from_utc(utc_now()));
    let mut strategy = restore_iti_strategy(
        &dir,
        momento_strategy_research_iti::ItiPrices::from_cents(20, 60, 10).unwrap(),
    )
    .unwrap();
    let mut tracker = InMemoryPositionTracker::new();
    let risk = iti_risk(&cfg, &snap);
    observe_demo_event(
        &dir,
        &cfg,
        &mut strategy,
        &mut tracker,
        &risk,
        &mut venue,
        &snap,
        quote_event(19, market_id, game_id),
    );
    observe_demo_event(
        &dir,
        &cfg,
        &mut strategy,
        &mut tracker,
        &risk,
        &mut venue,
        &snap,
        quote_event(40, market_id, game_id),
    );
    let reqs = captured.lock().unwrap();
    assert!(
        reqs.iter()
            .any(|r| r.path.contains(CREATE_ORDER_PATH) && r.method.eq_ignore_ascii_case("POST"))
    );
}

#[test]
fn exact_20_is_approved_19_is_not() {
    let snap = weekly50();
    let mut cfg = RiskConfig::mlb_paper_experimental().unwrap();
    cfg.min_entry_price = Price::from_cents(20).unwrap();
    cfg.max_entry_price = Price::from_cents(59).unwrap();
    let risk = PaperRiskEngine::paper(snap.clone(), cfg);
    let pos = momento_core::Position::new_for_game(
        momento_core::PositionId::from_raw(1),
        momento_core::GameId::from_raw(10),
        momento_core::StrategyId::RESEARCH_ITI,
        snap.snapshot_id(),
        snap.max_position_budget(),
        Some(momento_core::MarketId::from_raw(2)),
        Some(Side::Yes),
    );
    let intent = |cents: u16| {
        momento_core::TradeIntent::build(momento_core::BuildPositionIntent {
            strategy_id: momento_core::StrategyId::RESEARCH_ITI,
            game_id: pos.game_id(),
            market_id: momento_core::MarketId::from_raw(2),
            side: Side::Yes,
            position_id: pos.id(),
            limit_price: Price::from_cents(cents).unwrap(),
            style: momento_core::EntryStyle::MakerOnly,
            additional: momento_core::AdditionalExposure::RemainderOfApprovedBudget,
        })
    };
    match risk.decide_entry(&intent(19), &pos) {
        RiskDecision::Rejected { .. } => {}
        other => panic!("19 must reject, got {other:?}"),
    }
    match risk.decide_entry(&intent(20), &pos) {
        RiskDecision::Approved(a) => assert_eq!(a.limit_price().cents(), 20),
        other => panic!("20 must approve, got {other:?}"),
    }
}

#[test]
fn submit_demo_refuses_when_live_armed() {
    let (_dir, mut cfg) = write_demo_cfg();
    cfg.live.enabled = true;
    cfg.live.confirmation = momento_core::LIVE_CONFIRMATION.to_string();
    cfg.mode = TradingMode::Live;
    let snap = weekly50();
    let risk = PaperRiskEngine::paper(snap.clone(), RiskConfig::mlb_paper_experimental().unwrap());
    let mut tracker = InMemoryPositionTracker::new();
    let (identity, _, _, _) = bound_identity();
    let mut venue = KalshiVenue::sandbox(
        ScriptedTransport::new([]),
        identity,
        ReceivedAt::from_utc(utc_now()),
    );
    let pos = momento_core::Position::new_for_game(
        momento_core::PositionId::from_raw(1),
        momento_core::GameId::from_raw(10),
        momento_core::StrategyId::MLB,
        snap.snapshot_id(),
        snap.max_position_budget(),
        Some(momento_core::MarketId::from_raw(2)),
        Some(Side::Yes),
    );
    let approved = match risk.decide_entry(
        &momento_core::TradeIntent::build(momento_core::BuildPositionIntent {
            strategy_id: momento_core::StrategyId::MLB,
            game_id: pos.game_id(),
            market_id: momento_core::MarketId::from_raw(2),
            side: Side::Yes,
            position_id: pos.id(),
            limit_price: Price::from_cents(80).unwrap(),
            style: momento_core::EntryStyle::MakerOnly,
            additional: momento_core::AdditionalExposure::RemainderOfApprovedBudget,
        }),
        &pos,
    ) {
        RiskDecision::Approved(a) => a,
        other => panic!("{other:?}"),
    };
    assert!(submit_demo_approved(&cfg, &mut tracker, &risk, &mut venue, approved).is_err());
}
