use std::fs;
use std::sync::{Arc, Mutex};
use std::time::{SystemTime, UNIX_EPOCH};

use momento_core::{
    Bps, Contracts, EntryPriceGate, ExchangeTimestamp, Fee, FeeKind, Fill, FillId, GameId,
    KillSwitch, LIVE_CONFIRMATION, MarketEvent, Money, OrderState, Price, ReceivedAt,
    ReconciliationState, RiskDecision, RiskRejectReason, Side, SnapshotId, SnapshotSource,
    StrategyId, TradingMode, utc_now,
};
use momento_kalshi::{
    CREATE_ORDER_PATH, KalshiHttpRequest, KalshiMarket, KalshiTransport, KalshiVenue,
    LocalOrderBook, MarketBinding, ScriptedTransport, StaticIdentity, TransportOutcome,
    VenueIdentity, encode_client_order_id, encode_venue_order_id, game_id_for_event_ticker,
    map_market, market_id_for_ticker, parse_orderbook_delta, parse_orderbook_snapshot,
    parse_ws_frame, ts_ms,
};
use momento_positions::{InMemoryPositionTracker, PositionEvent, PositionTracker, TrackerPersist};
use momento_risk::{PaperRiskEngine, RiskConfig};
use momento_strategy_mlb::{
    MLB_STRATEGY_ID, MlbGamePhase, MlbGameSnapshot, MlbStrategy, MlbStrategySnapshot,
};
use momento_strategy_wnba::WnbaStrategy;
use momento_trading_engine::live::{
    entry_price_exceeds_max, finish_housekeeping_gates, ingest_fills, kill_file,
    kill_switch_requested, live_heartbeat, live_market_event_from_book,
    live_market_event_from_snapshot, live_without_confirmation_cannot_submit, observe_live_event,
    paper_mode_cannot_submit_production, poll_live_mlb_markets, refresh_open_mlb_positions,
    risk_approval_is_mandatory, snapshot_file, sync_working_orders,
};
use momento_trading_engine::runtime::{
    HostError, heartbeat_line, load_live_config, load_paper_config, persist_strategy,
    restore_strategy,
};

fn tmp_dir() -> std::path::PathBuf {
    let nanos = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap()
        .as_nanos();
    let dir = std::env::temp_dir().join(format!("momento-live-host-{nanos}"));
    fs::create_dir_all(&dir).unwrap();
    dir
}

#[test]
fn paper_config_loads_and_live_gate_is_off() {
    let path = std::path::Path::new(env!("CARGO_MANIFEST_DIR")).join("../../config/paper.toml");
    let cfg = load_paper_config(&path).unwrap();
    assert_eq!(cfg.mode, TradingMode::Paper);
    assert!(!cfg.live.enabled);
    assert!(heartbeat_line(&cfg).contains("live_implemented=false"));
    assert!(paper_mode_cannot_submit_production(&cfg));
}

#[test]
fn live_config_cannot_arm_paper_host() {
    let path = std::path::Path::new(env!("CARGO_MANIFEST_DIR")).join("../../config/live.toml");
    let err = load_paper_config(&path).unwrap_err();
    assert!(matches!(err, HostError::LiveNotImplemented));
}

#[test]
fn live_config_loads_when_all_three_gates_are_set() {
    let path = std::path::Path::new(env!("CARGO_MANIFEST_DIR")).join("../../config/live.toml");
    let cfg = load_live_config(&path).unwrap();
    assert_eq!(cfg.mode, TradingMode::Live);
    assert!(cfg.live.enabled);
    assert_eq!(cfg.live.confirmation, LIVE_CONFIRMATION);
    assert!(cfg.is_live_armed());
    assert!(!paper_mode_cannot_submit_production(&cfg));
}

#[test]
fn live_host_rejects_missing_confirmation() {
    let dir = tmp_dir();
    let path = dir.join("live.toml");
    fs::write(
        &path,
        r#"
mode = "live"
timezone = "America/Los_Angeles"
allocation_bps = 1250
max_entry_price_cents = 83
preferred_entry_price_cents = 80
min_entry_price_cents = 80
initial_bankroll_cents = 5000
[live]
enabled = true
confirmation = ""
"#,
    )
    .unwrap();
    assert!(load_live_config(&path).is_err());
    let cfg =
        momento_core::TradingConfig::from_toml_str(&fs::read_to_string(&path).unwrap()).unwrap();
    assert!(live_without_confirmation_cannot_submit(&cfg));
}

#[test]
fn entry_above_83_is_rejected_at_execution_boundary() {
    let max = Price::from_cents(83).unwrap();
    assert!(!entry_price_exceeds_max(
        Price::from_cents(83).unwrap(),
        max
    ));
    assert!(entry_price_exceeds_max(Price::from_cents(84).unwrap(), max));
}

#[test]
fn unapproved_risk_decision_cannot_execute() {
    let rejected = RiskDecision::Rejected {
        decision_id: momento_core::RiskDecisionId::from_raw(1),
        reason: RiskRejectReason::KillSwitchActive,
        snapshot_id: SnapshotId::from_raw(1),
    };
    assert!(!risk_approval_is_mandatory(&rejected));
}

#[test]
fn kill_switch_file_blocks_new_exposure_signal() {
    let dir = tmp_dir();
    assert!(!kill_switch_requested(&dir));
    fs::write(kill_file(&dir), "trip").unwrap();
    assert!(kill_switch_requested(&dir));
}

#[test]
fn strategy_and_tracker_state_survive_restart() {
    let dir = tmp_dir();
    let mut snap = MlbGameSnapshot::new(GameId::from_raw(10));
    snap.phase = MlbGamePhase::GameLocked;
    let strategy = MlbStrategy::restore(MlbStrategySnapshot { games: vec![snap] });
    persist_strategy(&dir, &strategy).unwrap();
    let restored = restore_strategy(&dir).unwrap();
    assert_eq!(
        restored.phase(GameId::from_raw(10)),
        MlbGamePhase::GameLocked
    );

    let tracker = InMemoryPositionTracker::new();
    let persist = tracker.snapshot_persist();
    let restored_tracker = InMemoryPositionTracker::restore_persist(persist);
    assert_eq!(
        restored_tracker.reconciliation_state(),
        momento_core::ReconciliationState::Healthy
    );
    assert!(!restored_tracker.has_unknown_orders());
    let _ = TrackerPersist {
        positions: Vec::new(),
        orders: Vec::new(),
        unknown: Vec::new(),
        recon: momento_core::ReconciliationState::Healthy,
        index: Vec::new(),
        event_keys: Vec::new(),
    };
}

#[test]
fn weekly_snapshot_file_round_trip_is_immutable_intra_week() {
    use momento_core::{Bps, Money, SnapshotSource, WeeklyBankrollSnapshot};
    let dir = tmp_dir();
    let snap = WeeklyBankrollSnapshot::capture(
        Money::from_usd(50, 0).unwrap(),
        Bps::PCT_12_5,
        utc_now(),
        SnapshotSource::ConfiguredInitial,
    )
    .unwrap();
    assert_eq!(snap.max_position_budget(), Money::from_usd(6, 25).unwrap());
    fs::write(
        snapshot_file(&dir),
        serde_json::to_string_pretty(&snap).unwrap(),
    )
    .unwrap();
    let loaded: WeeklyBankrollSnapshot =
        serde_json::from_str(&fs::read_to_string(snapshot_file(&dir)).unwrap()).unwrap();
    assert_eq!(loaded.snapshot_id(), snap.snapshot_id());
    assert_eq!(loaded.bankroll(), snap.bankroll());
}

#[test]
fn kill_switch_enum_does_not_flatten() {
    assert!(!KillSwitch::Armed.is_tripped());
    assert!(KillSwitch::Tripped.is_tripped());
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

fn live_cfg() -> momento_core::TradingConfig {
    let path = std::path::Path::new(env!("CARGO_MANIFEST_DIR")).join("../../config/live.toml");
    load_live_config(&path).unwrap()
}

fn weekly50() -> momento_core::WeeklyBankrollSnapshot {
    momento_core::WeeklyBankrollSnapshot::capture(
        Money::from_usd(50, 0).unwrap(),
        Bps::PCT_12_5,
        utc_now(),
        SnapshotSource::Test,
    )
    .unwrap()
}

fn bound_identity() -> (StaticIdentity, String, momento_core::MarketId, GameId) {
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
    mid: Option<u16>,
    bid: u16,
    ask: u16,
    last: u16,
    market_id: momento_core::MarketId,
    game_id: GameId,
) -> MarketEvent {
    let t = utc_now();
    MarketEvent {
        game_id,
        market_id,
        side: Some(Side::Yes),
        exchange_ts: ExchangeTimestamp::from_utc(t),
        received_at: ReceivedAt::from_utc(t),
        last: Some(Price::from_cents(last).unwrap()),
        bid: Some(Price::from_cents(bid).unwrap()),
        ask: Some(Price::from_cents(ask).unwrap()),
        mid: mid.map(|c| Price::from_cents(c).unwrap()),
        bid_depth: Some(10),
        ask_depth: Some(4),
        game_state: None,
    }
}

#[test]
fn production_map_market_does_not_produce_mlb_mid() {
    let t = utc_now();
    let received = ReceivedAt::from_utc(t);
    let market: KalshiMarket = serde_json::from_str(
        r#"{"ticker":"KXMLBGAME-TEST","event_ticker":"KXMLBGAME-EVT","yes_bid_dollars":"0.8000","yes_ask_dollars":"0.8300","last_price_dollars":"0.8100","yes_bid_size_fp":"10.00","yes_ask_size_fp":"4.00","updated_time":"2026-08-24T18:00:00Z","result":"","price_level_structure":"linear_cent"}"#,
    )
    .unwrap();
    let snap = map_market(
        &market,
        received,
        Some(market_id_for_ticker("KXMLBGAME-TEST")),
        Some(game_id_for_event_ticker("KXMLBGAME-EVT")),
    )
    .unwrap();
    assert_eq!(snap.last, Some(Price::from_cents(81).unwrap()));
    assert_eq!(snap.bid, Some(Price::from_cents(80).unwrap()));
    assert_eq!(snap.ask, Some(Price::from_cents(83).unwrap()));
    assert_eq!(snap.mid, None);
    let event = live_market_event_from_snapshot(snap).unwrap();
    assert_eq!(event.mid, None);
    assert_eq!(event.bid, Some(Price::from_cents(80).unwrap()));
    assert_eq!(event.ask, Some(Price::from_cents(83).unwrap()));
    assert_eq!(event.last, Some(Price::from_cents(81).unwrap()));
}

#[test]
fn production_poll_path_leaves_mid_none_and_does_not_submit() {
    let captured = Arc::new(Mutex::new(Vec::new()));
    let transport = RecordingTransport {
        inner: ScriptedTransport::new([TransportOutcome::Http {
            status: 200,
            body: r#"{"markets":[{"ticker":"KXMLBGAME-TEST","event_ticker":"KXMLBGAME-EVT","yes_bid_dollars":"0.8000","yes_ask_dollars":"0.8300","last_price_dollars":"0.8100","yes_bid_size_fp":"10.00","yes_ask_size_fp":"4.00","updated_time":"2026-08-24T18:00:00Z","result":"","price_level_structure":"linear_cent"}],"cursor":null}"#.into(),
        }]),
        captured: Arc::clone(&captured),
    };
    let (identity, _, _, _) = bound_identity();
    let mut venue = KalshiVenue::production(transport, identity, ReceivedAt::from_utc(utc_now()));
    let events = poll_live_mlb_markets(&mut venue, ReceivedAt::from_utc(utc_now())).unwrap();
    assert_eq!(events.len(), 1);
    assert_eq!(events[0].mid, None);
    assert_eq!(events[0].bid, Some(Price::from_cents(80).unwrap()));
    assert_eq!(events[0].ask, Some(Price::from_cents(83).unwrap()));
    assert_eq!(events[0].last, Some(Price::from_cents(81).unwrap()));
    let reqs = captured.lock().unwrap();
    assert!(reqs.iter().all(|r| r.method.eq_ignore_ascii_case("GET")));
    assert!(reqs.iter().all(|r| r.path.contains("/markets")));
    assert!(!reqs.iter().any(|r| r.path.contains("/orders")));
}

#[test]
fn production_poll_events_do_not_submit_when_yes_bid_missing() {
    let dir = tmp_dir();
    let cfg = live_cfg();
    let snap = weekly50();
    let captured = Arc::new(Mutex::new(Vec::new()));
    let transport = RecordingTransport {
        inner: ScriptedTransport::new([]),
        captured: Arc::clone(&captured),
    };
    let (identity, _, market_id, game_id) = bound_identity();
    let mut venue = KalshiVenue::production(transport, identity, ReceivedAt::from_utc(utc_now()));
    let mut strategy = MlbStrategy::new();
    let mut tracker = InMemoryPositionTracker::new();
    let risk = PaperRiskEngine::paper(snap.clone(), RiskConfig::mlb_paper_experimental().unwrap());
    let mut missing_bid = quote_event(None, 80, 82, 81, market_id, game_id);
    missing_bid.bid = None;
    observe_live_event(
        &dir,
        &cfg,
        &mut strategy,
        &mut tracker,
        &risk,
        &mut venue,
        &snap,
        missing_bid,
    );
    assert!(strategy.first_80(game_id).is_none());
    assert!(captured.lock().unwrap().is_empty());
    assert_eq!(tracker.snapshot_persist().orders.len(), 0);
}

#[test]
fn last_99_and_ask_99_with_yes_bid_79_do_not_reach_submit() {
    let dir = tmp_dir();
    let cfg = live_cfg();
    let snap = weekly50();
    let captured = Arc::new(Mutex::new(Vec::new()));
    let transport = RecordingTransport {
        inner: ScriptedTransport::new([]),
        captured: Arc::clone(&captured),
    };
    let (identity, _, market_id, game_id) = bound_identity();
    let mut venue = KalshiVenue::production(transport, identity, ReceivedAt::from_utc(utc_now()));
    let mut strategy = MlbStrategy::new();
    let mut tracker = InMemoryPositionTracker::new();
    let risk = PaperRiskEngine::paper(snap.clone(), RiskConfig::mlb_paper_experimental().unwrap());
    observe_live_event(
        &dir,
        &cfg,
        &mut strategy,
        &mut tracker,
        &risk,
        &mut venue,
        &snap,
        quote_event(None, 79, 99, 99, market_id, game_id),
    );
    assert!(strategy.first_80(game_id).is_none());
    assert!(strategy.first_89(game_id).is_none());
    assert!(captured.lock().unwrap().is_empty());
}

#[test]
fn qualifying_80_then_81_reaches_submit_approved_without_production_http() {
    let dir = tmp_dir();
    let cfg = live_cfg();
    assert!(cfg.is_live_armed());
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
    let (identity, ticker, market_id, game_id) = bound_identity();
    let mut venue = KalshiVenue::production(transport, identity, ReceivedAt::from_utc(utc_now()));
    let mut strategy = MlbStrategy::new();
    let mut tracker = InMemoryPositionTracker::new();
    let risk = PaperRiskEngine::paper(snap.clone(), RiskConfig::mlb_paper_experimental().unwrap());

    observe_live_event(
        &dir,
        &cfg,
        &mut strategy,
        &mut tracker,
        &risk,
        &mut venue,
        &snap,
        quote_event(None, 80, 81, 99, market_id, game_id),
    );
    assert!(strategy.first_80(game_id).is_some());
    assert_eq!(
        strategy.phase(game_id),
        MlbGamePhase::WaitingFor81Confirmation
    );
    assert!(captured.lock().unwrap().is_empty());

    observe_live_event(
        &dir,
        &cfg,
        &mut strategy,
        &mut tracker,
        &risk,
        &mut venue,
        &snap,
        quote_event(None, 81, 82, 99, market_id, game_id),
    );
    assert_eq!(strategy.phase(game_id), MlbGamePhase::EntryEligible);
    let reqs = captured.lock().unwrap().clone();
    assert_eq!(reqs.len(), 1);
    assert_eq!(reqs[0].method, "POST");
    assert_eq!(reqs[0].path, CREATE_ORDER_PATH);
    let body = reqs[0].body.as_deref().unwrap();
    assert!(body.contains(&ticker));
    assert!(body.contains("\"post_only\":true"));
    assert!(body.contains("\"price\":\"0.8100\""));
    assert!(!body.contains("https://external-api.kalshi.com"));
    assert_eq!(tracker.snapshot_persist().orders.len(), 1);
}

#[test]
fn week_roll_rebinds_unfilled_so_81_can_submit() {
    let dir = tmp_dir();
    let cfg = live_cfg();
    let old = weekly50();
    let new = weekly50();
    assert_ne!(old.snapshot_id(), new.snapshot_id());
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
    let (identity, ticker, market_id, game_id) = bound_identity();
    let mut venue = KalshiVenue::production(transport, identity, ReceivedAt::from_utc(utc_now()));
    let mut strategy = MlbStrategy::new();
    let mut tracker = InMemoryPositionTracker::new();
    let risk = PaperRiskEngine::paper(old.clone(), RiskConfig::mlb_paper_experimental().unwrap());

    observe_live_event(
        &dir,
        &cfg,
        &mut strategy,
        &mut tracker,
        &risk,
        &mut venue,
        &old,
        quote_event(None, 80, 81, 99, market_id, game_id),
    );
    assert!(strategy.first_80(game_id).is_some());
    let pid = tracker.id_for_game(game_id).unwrap();
    assert_eq!(tracker.get(pid).unwrap().snapshot_id(), old.snapshot_id());

    risk.replace_weekly_snapshot(new.clone());
    observe_live_event(
        &dir,
        &cfg,
        &mut strategy,
        &mut tracker,
        &risk,
        &mut venue,
        &new,
        quote_event(None, 81, 82, 99, market_id, game_id),
    );
    assert_eq!(tracker.get(pid).unwrap().snapshot_id(), new.snapshot_id());
    assert_eq!(strategy.phase(game_id), MlbGamePhase::EntryEligible);
    let reqs = captured.lock().unwrap().clone();
    assert_eq!(reqs.len(), 1);
    assert_eq!(reqs[0].method, "POST");
    assert_eq!(reqs[0].path, CREATE_ORDER_PATH);
    assert!(reqs[0].body.as_deref().unwrap().contains(&ticker));
}

#[test]
fn return_to_band_after_above_max_pause_reaches_submit() {
    let dir = tmp_dir();
    let cfg = live_cfg();
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
    let (identity, ticker, market_id, game_id) = bound_identity();
    let mut venue = KalshiVenue::production(transport, identity, ReceivedAt::from_utc(utc_now()));
    let mut strategy = MlbStrategy::new();
    let mut tracker = InMemoryPositionTracker::new();
    let risk = PaperRiskEngine::paper(snap.clone(), RiskConfig::mlb_paper_experimental().unwrap());

    observe_live_event(
        &dir,
        &cfg,
        &mut strategy,
        &mut tracker,
        &risk,
        &mut venue,
        &snap,
        quote_event(None, 80, 81, 99, market_id, game_id),
    );
    let pid = tracker.id_for_game(game_id).unwrap();
    observe_live_event(
        &dir,
        &cfg,
        &mut strategy,
        &mut tracker,
        &risk,
        &mut venue,
        &snap,
        quote_event(None, 84, 85, 99, market_id, game_id),
    );
    assert_eq!(
        tracker.get(pid).unwrap().entry_price_gate(),
        EntryPriceGate::PausedAboveMaxPrice
    );
    assert!(captured.lock().unwrap().is_empty());

    observe_live_event(
        &dir,
        &cfg,
        &mut strategy,
        &mut tracker,
        &risk,
        &mut venue,
        &snap,
        quote_event(None, 81, 82, 99, market_id, game_id),
    );
    assert_eq!(
        tracker.get(pid).unwrap().entry_price_gate(),
        EntryPriceGate::Permitted
    );
    let reqs = captured.lock().unwrap().clone();
    assert_eq!(reqs.len(), 1);
    assert_eq!(reqs[0].method, "POST");
    assert_eq!(reqs[0].path, CREATE_ORDER_PATH);
    assert!(reqs[0].body.as_deref().unwrap().contains(&ticker));
}

#[test]
fn yes_bid_89_cancel_404_releases_unfilled_slot() {
    let dir = tmp_dir();
    let cfg = live_cfg();
    let snap = weekly50();
    let ack = format!(
        r#"{{"order_id":"{}","fill_count":"0.00","remaining_count":"7.00","ts_ms":1715793600123}}"#,
        encode_venue_order_id(momento_core::VenueOrderId::from_raw(99))
    );
    let transport = ScriptedTransport::new([
        TransportOutcome::Http {
            status: 201,
            body: ack,
        },
        TransportOutcome::Http {
            status: 404,
            body: r#"{"error":{"code":"not_found","message":"order not found"}}"#.into(),
        },
    ]);
    let (identity, _, market_id, game_id) = bound_identity();
    let mut venue = KalshiVenue::production(transport, identity, ReceivedAt::from_utc(utc_now()));
    let mut strategy = MlbStrategy::new();
    let mut tracker = InMemoryPositionTracker::new();
    let risk = PaperRiskEngine::paper(snap.clone(), RiskConfig::mlb_paper_experimental().unwrap());

    observe_live_event(
        &dir,
        &cfg,
        &mut strategy,
        &mut tracker,
        &risk,
        &mut venue,
        &snap,
        quote_event(None, 80, 81, 99, market_id, game_id),
    );
    observe_live_event(
        &dir,
        &cfg,
        &mut strategy,
        &mut tracker,
        &risk,
        &mut venue,
        &snap,
        quote_event(None, 81, 82, 99, market_id, game_id),
    );
    assert_eq!(risk.open_slot_count(), 1);

    observe_live_event(
        &dir,
        &cfg,
        &mut strategy,
        &mut tracker,
        &risk,
        &mut venue,
        &snap,
        quote_event(None, 89, 90, 99, market_id, game_id),
    );
    assert_eq!(strategy.phase(game_id), MlbGamePhase::GameLocked);
    let order = &tracker.entry_orders_for_game(game_id)[0];
    assert_eq!(order.state(), OrderState::Cancelled);
    assert_eq!(order.quantities().filled.get(), 0);
    assert_eq!(risk.open_slot_count(), 0);
}

#[test]
fn cancel_pending_get_404_releases_unfilled_slot() {
    let dir = tmp_dir();
    let cfg = live_cfg();
    let snap = weekly50();
    let ack = format!(
        r#"{{"order_id":"{}","fill_count":"0.00","remaining_count":"7.00","ts_ms":1715793600123}}"#,
        encode_venue_order_id(momento_core::VenueOrderId::from_raw(99))
    );
    let transport = ScriptedTransport::new([
        TransportOutcome::Http {
            status: 201,
            body: ack,
        },
        TransportOutcome::Http {
            status: 404,
            body: r#"{"error":{"code":"not_found","message":"order not found"}}"#.into(),
        },
    ]);
    let (identity, _, market_id, game_id) = bound_identity();
    let mut venue = KalshiVenue::production(transport, identity, ReceivedAt::from_utc(utc_now()));
    let mut strategy = MlbStrategy::new();
    let mut tracker = InMemoryPositionTracker::new();
    let risk = PaperRiskEngine::paper(snap.clone(), RiskConfig::mlb_paper_experimental().unwrap());

    observe_live_event(
        &dir,
        &cfg,
        &mut strategy,
        &mut tracker,
        &risk,
        &mut venue,
        &snap,
        quote_event(None, 80, 81, 99, market_id, game_id),
    );
    observe_live_event(
        &dir,
        &cfg,
        &mut strategy,
        &mut tracker,
        &risk,
        &mut venue,
        &snap,
        quote_event(None, 81, 82, 99, market_id, game_id),
    );
    let cid = tracker.entry_orders_for_game(game_id)[0].client_order_id();
    tracker
        .apply_event(PositionEvent::CancelRequested {
            client_order_id: cid,
        })
        .unwrap();
    assert_eq!(
        tracker.entry_orders_for_game(game_id)[0].state(),
        OrderState::CancelPending
    );
    assert_eq!(risk.open_slot_count(), 1);

    sync_working_orders(&mut venue, &mut tracker, &risk);
    assert_eq!(
        tracker.entry_orders_for_game(game_id)[0].state(),
        OrderState::Cancelled
    );
    assert_eq!(risk.open_slot_count(), 0);
}

#[test]
fn working_get_404_does_not_release_live_unfilled_slot() {
    let dir = tmp_dir();
    let cfg = live_cfg();
    let snap = weekly50();
    let ack = format!(
        r#"{{"order_id":"{}","fill_count":"0.00","remaining_count":"7.00","ts_ms":1715793600123}}"#,
        encode_venue_order_id(momento_core::VenueOrderId::from_raw(99))
    );
    let transport = ScriptedTransport::new([
        TransportOutcome::Http {
            status: 201,
            body: ack,
        },
        TransportOutcome::Http {
            status: 404,
            body: r#"{"error":{"code":"not_found","message":"order not found"}}"#.into(),
        },
    ]);
    let (identity, _, market_id, game_id) = bound_identity();
    let mut venue = KalshiVenue::production(transport, identity, ReceivedAt::from_utc(utc_now()));
    let mut strategy = MlbStrategy::new();
    let mut tracker = InMemoryPositionTracker::new();
    let risk = PaperRiskEngine::paper(snap.clone(), RiskConfig::mlb_paper_experimental().unwrap());

    observe_live_event(
        &dir,
        &cfg,
        &mut strategy,
        &mut tracker,
        &risk,
        &mut venue,
        &snap,
        quote_event(None, 80, 81, 99, market_id, game_id),
    );
    observe_live_event(
        &dir,
        &cfg,
        &mut strategy,
        &mut tracker,
        &risk,
        &mut venue,
        &snap,
        quote_event(None, 81, 82, 99, market_id, game_id),
    );
    assert_eq!(risk.open_slot_count(), 1);
    sync_working_orders(&mut venue, &mut tracker, &risk);
    assert_eq!(
        tracker.entry_orders_for_game(game_id)[0].state(),
        OrderState::Working
    );
    assert_eq!(risk.open_slot_count(), 1);
}

fn kalshi_get_order_json(status: &str, fill: &str, remaining: &str) -> String {
    format!(
        r#"{{"order":{{"order_id":"{}","client_order_id":"{}","ticker":"KXMLBGAME-TEST","status":"{status}","type":"limit","fill_count_fp":"{fill}","remaining_count_fp":"{remaining}","initial_count_fp":"7.00","yes_price_dollars":"0.8100"}}}}"#,
        encode_venue_order_id(momento_core::VenueOrderId::from_raw(99)),
        encode_client_order_id(momento_core::ClientOrderId::from_raw(1))
    )
}

#[allow(clippy::too_many_arguments)]
fn submit_qualifying_maker(
    dir: &std::path::Path,
    cfg: &momento_core::TradingConfig,
    snap: &momento_core::WeeklyBankrollSnapshot,
    strategy: &mut MlbStrategy,
    tracker: &mut InMemoryPositionTracker,
    risk: &PaperRiskEngine,
    venue: &mut KalshiVenue<impl KalshiTransport, impl VenueIdentity>,
    market_id: momento_core::MarketId,
    game_id: GameId,
) {
    observe_live_event(
        dir,
        cfg,
        strategy,
        tracker,
        risk,
        venue,
        snap,
        quote_event(None, 80, 81, 99, market_id, game_id),
    );
    observe_live_event(
        dir,
        cfg,
        strategy,
        tracker,
        risk,
        venue,
        snap,
        quote_event(None, 81, 82, 99, market_id, game_id),
    );
}

#[test]
fn live_working_unlocked_resting_sync_does_not_delete() {
    let dir = tmp_dir();
    let cfg = live_cfg();
    let snap = weekly50();
    let captured = Arc::new(Mutex::new(Vec::new()));
    let ack = format!(
        r#"{{"order_id":"{}","fill_count":"0.00","remaining_count":"7.00","ts_ms":1715793600123}}"#,
        encode_venue_order_id(momento_core::VenueOrderId::from_raw(99))
    );
    let transport = RecordingTransport {
        inner: ScriptedTransport::new([
            TransportOutcome::Http {
                status: 201,
                body: ack,
            },
            TransportOutcome::Http {
                status: 200,
                body: kalshi_get_order_json("resting", "0.00", "7.00"),
            },
        ]),
        captured: Arc::clone(&captured),
    };
    let (identity, _, market_id, game_id) = bound_identity();
    let mut venue = KalshiVenue::production(transport, identity, ReceivedAt::from_utc(utc_now()));
    let mut strategy = MlbStrategy::new();
    let mut tracker = InMemoryPositionTracker::new();
    let risk = PaperRiskEngine::paper(snap.clone(), RiskConfig::mlb_paper_experimental().unwrap());

    submit_qualifying_maker(
        &dir,
        &cfg,
        &snap,
        &mut strategy,
        &mut tracker,
        &risk,
        &mut venue,
        market_id,
        game_id,
    );
    assert_eq!(risk.open_slot_count(), 1);
    captured.lock().unwrap().clear();
    sync_working_orders(&mut venue, &mut tracker, &risk);
    let reqs = captured.lock().unwrap().clone();
    assert!(reqs.iter().any(|r| r.method.eq_ignore_ascii_case("GET")));
    assert!(
        reqs.iter()
            .all(|r| !r.method.eq_ignore_ascii_case("DELETE"))
    );
    assert_eq!(
        tracker.entry_orders_for_game(game_id)[0].state(),
        OrderState::Working
    );
    assert_eq!(risk.open_slot_count(), 1);
}

#[test]
fn cancel_pending_releases_when_get_status_is_unmapped() {
    let dir = tmp_dir();
    let cfg = live_cfg();
    let snap = weekly50();
    let ack = format!(
        r#"{{"order_id":"{}","fill_count":"0.00","remaining_count":"7.00","ts_ms":1715793600123}}"#,
        encode_venue_order_id(momento_core::VenueOrderId::from_raw(99))
    );
    let transport = ScriptedTransport::new([
        TransportOutcome::Http {
            status: 201,
            body: ack,
        },
        TransportOutcome::Http {
            status: 200,
            body: kalshi_get_order_json("pending", "0.00", "7.00"),
        },
        TransportOutcome::Http {
            status: 404,
            body: r#"{"error":{"code":"not_found","message":"order not found"}}"#.into(),
        },
    ]);
    let (identity, _, market_id, game_id) = bound_identity();
    let mut venue = KalshiVenue::production(transport, identity, ReceivedAt::from_utc(utc_now()));
    let mut strategy = MlbStrategy::new();
    let mut tracker = InMemoryPositionTracker::new();
    let risk = PaperRiskEngine::paper(snap.clone(), RiskConfig::mlb_paper_experimental().unwrap());

    submit_qualifying_maker(
        &dir,
        &cfg,
        &snap,
        &mut strategy,
        &mut tracker,
        &risk,
        &mut venue,
        market_id,
        game_id,
    );
    let cid = tracker.entry_orders_for_game(game_id)[0].client_order_id();
    tracker
        .apply_event(PositionEvent::CancelRequested {
            client_order_id: cid,
        })
        .unwrap();
    assert_eq!(risk.open_slot_count(), 1);

    sync_working_orders(&mut venue, &mut tracker, &risk);
    assert_eq!(
        tracker.entry_orders_for_game(game_id)[0].state(),
        OrderState::Cancelled
    );
    assert_eq!(risk.open_slot_count(), 0);
}

#[test]
fn cancel_pending_executed_empty_releases_slot() {
    let dir = tmp_dir();
    let cfg = live_cfg();
    let snap = weekly50();
    let ack = format!(
        r#"{{"order_id":"{}","fill_count":"0.00","remaining_count":"7.00","ts_ms":1715793600123}}"#,
        encode_venue_order_id(momento_core::VenueOrderId::from_raw(99))
    );
    let transport = ScriptedTransport::new([
        TransportOutcome::Http {
            status: 201,
            body: ack,
        },
        TransportOutcome::Http {
            status: 400,
            body: r#"{"error":{"code":"bad_request","message":"cannot cancel executed order"}}"#
                .into(),
        },
        TransportOutcome::Http {
            status: 200,
            body: kalshi_get_order_json("executed", "0.00", "0.00"),
        },
    ]);
    let (identity, _, market_id, game_id) = bound_identity();
    let mut venue = KalshiVenue::production(transport, identity, ReceivedAt::from_utc(utc_now()));
    let mut strategy = MlbStrategy::new();
    let mut tracker = InMemoryPositionTracker::new();
    let risk = PaperRiskEngine::paper(snap.clone(), RiskConfig::mlb_paper_experimental().unwrap());

    submit_qualifying_maker(
        &dir,
        &cfg,
        &snap,
        &mut strategy,
        &mut tracker,
        &risk,
        &mut venue,
        market_id,
        game_id,
    );
    let cid = tracker.entry_orders_for_game(game_id)[0].client_order_id();
    tracker
        .apply_event(PositionEvent::CancelRequested {
            client_order_id: cid,
        })
        .unwrap();
    assert_eq!(risk.open_slot_count(), 1);

    sync_working_orders(&mut venue, &mut tracker, &risk);
    assert_eq!(
        tracker.entry_orders_for_game(game_id)[0].state(),
        OrderState::Cancelled
    );
    assert_eq!(risk.open_slot_count(), 0);
}

fn mlb_open_markets_page(bid: &str, ask: &str, last: &str, updated: &str) -> String {
    format!(
        r#"{{"markets":[{{"ticker":"KXMLBGAME-TEST","event_ticker":"KXMLBGAME-EVT","yes_bid_dollars":"{bid}","yes_ask_dollars":"{ask}","last_price_dollars":"{last}","yes_bid_size_fp":"10.00","yes_ask_size_fp":"4.00","updated_time":"{updated}","result":"","price_level_structure":"linear_cent","price_ranges":[{{"start":"0.0000","end":"1.0000","step":"0.0100"}}]}}],"cursor":null}}"#
    )
}

#[test]
fn production_poll_yes_bid_80_then_81_reaches_scripted_submit() {
    let dir = tmp_dir();
    let cfg = live_cfg();
    let snap = weekly50();
    let captured = Arc::new(Mutex::new(Vec::new()));
    let ack = format!(
        r#"{{"order_id":"{}","fill_count":"0.00","remaining_count":"7.00","ts_ms":1715793600123}}"#,
        encode_venue_order_id(momento_core::VenueOrderId::from_raw(99))
    );
    let transport = RecordingTransport {
        inner: ScriptedTransport::new([
            TransportOutcome::Http {
                status: 200,
                body: mlb_open_markets_page("0.8000", "0.8100", "0.9900", "2026-08-01T18:00:01Z"),
            },
            TransportOutcome::Http {
                status: 200,
                body: mlb_open_markets_page("0.8100", "0.8200", "0.9900", "2026-08-01T18:00:02Z"),
            },
            TransportOutcome::Http {
                status: 201,
                body: ack,
            },
        ]),
        captured: Arc::clone(&captured),
    };
    let (identity, ticker, _, game_id) = bound_identity();
    let mut venue = KalshiVenue::production(transport, identity, ReceivedAt::from_utc(utc_now()));
    let mut strategy = MlbStrategy::new();
    let mut tracker = InMemoryPositionTracker::new();
    let risk = PaperRiskEngine::paper(snap.clone(), RiskConfig::mlb_paper_experimental().unwrap());

    let first_poll = poll_live_mlb_markets(&mut venue, ReceivedAt::from_utc(utc_now())).unwrap();
    assert_eq!(first_poll.len(), 1);
    assert_eq!(first_poll[0].mid, None);
    assert_eq!(first_poll[0].bid, Some(Price::from_cents(80).unwrap()));
    assert_eq!(first_poll[0].last, Some(Price::from_cents(99).unwrap()));
    observe_live_event(
        &dir,
        &cfg,
        &mut strategy,
        &mut tracker,
        &risk,
        &mut venue,
        &snap,
        first_poll.into_iter().next().unwrap(),
    );
    assert!(strategy.first_80(game_id).is_some());
    assert!(
        captured
            .lock()
            .unwrap()
            .iter()
            .all(|r| r.method.eq_ignore_ascii_case("GET"))
    );

    let second_poll = poll_live_mlb_markets(&mut venue, ReceivedAt::from_utc(utc_now())).unwrap();
    assert_eq!(second_poll[0].bid, Some(Price::from_cents(81).unwrap()));
    observe_live_event(
        &dir,
        &cfg,
        &mut strategy,
        &mut tracker,
        &risk,
        &mut venue,
        &snap,
        second_poll.into_iter().next().unwrap(),
    );
    assert_eq!(strategy.phase(game_id), MlbGamePhase::EntryEligible);
    let reqs = captured.lock().unwrap().clone();
    let posts: Vec<_> = reqs
        .iter()
        .filter(|r| r.method.eq_ignore_ascii_case("POST"))
        .collect();
    assert_eq!(posts.len(), 1);
    assert_eq!(posts[0].path, CREATE_ORDER_PATH);
    let body = posts[0].body.as_deref().unwrap();
    assert!(body.contains(&ticker));
    assert!(body.contains("\"post_only\":true"));
    assert!(body.contains("\"price\":\"0.8100\""));
    assert!(!body.contains("0.9900"));
}

#[test]
fn live_heartbeat_distinguishes_capable_order_submission() {
    let cfg = live_cfg();
    let snap = weekly50();
    let tracker = InMemoryPositionTracker::new();
    let risk = PaperRiskEngine::paper(snap, RiskConfig::mlb_paper_experimental().unwrap());
    let strategy = MlbStrategy::new();
    let wnba = WnbaStrategy::new();
    let line = live_heartbeat(&cfg, &tracker, &risk, &strategy, &wnba, 3, true);
    assert!(line.contains("mode=Live"));
    assert!(line.contains("live.enabled=true"));
    assert!(line.contains("production_auth=true"));
    assert!(line.contains("market_data=healthy"));
    assert!(line.contains("strategy=active"));
    assert!(line.contains("mlb_strategy=active"));
    assert!(line.contains("wnba_strategy=active"));
    assert!(line.contains("risk=healthy"));
    assert!(line.contains("reconciliation=healthy"));
    assert!(line.contains("unknown_orders=0"));
    assert!(line.contains("kill_switch=not_tripped"));
    assert!(line.contains("open_mlb_positions=0"));
    assert!(line.contains("open_wnba_positions=0"));
    assert!(line.contains("open_desk_positions=0"));
    assert!(line.contains("position_cap=5"));
    assert!(line.contains("position_cap_scope=desk"));
    assert!(line.contains("mlb_allocation_bps=1250"));
    assert!(line.contains("wnba_allocation_bps=833"));
    assert!(line.contains("mlb_per_game_cents=625"));
    assert!(line.contains("wnba_per_game_cents=416"));
    assert!(line.contains("order_submission=enabled"));
    assert!(line.contains("liquidation=enabled"));
    assert!(line.contains("stop_monitor=active"));
    assert!(line.contains("live_capable=true"));
}

#[test]
fn filled_position_yes_bid_40_submits_reduce_only_liquidation_without_production_http() {
    let dir = tmp_dir();
    let cfg = live_cfg();
    let snap = weekly50();
    let captured = Arc::new(Mutex::new(Vec::new()));
    let ack = format!(
        r#"{{"order_id":"{}","fill_count":"0.00","remaining_count":"0.00","ts_ms":1715793600123}}"#,
        encode_venue_order_id(momento_core::VenueOrderId::from_raw(77))
    );
    let transport = RecordingTransport {
        inner: ScriptedTransport::new([
            TransportOutcome::Timeout,
            TransportOutcome::Http {
                status: 201,
                body: ack,
            },
        ]),
        captured: Arc::clone(&captured),
    };
    let (identity, ticker, market_id, game_id) = bound_identity();
    let mut venue = KalshiVenue::production(transport, identity, ReceivedAt::from_utc(utc_now()));
    let mut strategy = MlbStrategy::new();
    let mut tracker = InMemoryPositionTracker::new();
    let risk = PaperRiskEngine::paper(snap.clone(), RiskConfig::mlb_paper_experimental().unwrap());
    let pid = tracker
        .get_or_create(
            MLB_STRATEGY_ID,
            game_id,
            &snap,
            Some(market_id),
            Some(Side::Yes),
        )
        .id();
    let t = utc_now();
    let fill = Fill::new(
        FillId::from_raw(1),
        pid,
        momento_core::ClientOrderId::from_raw(1),
        None,
        Contracts::from_u32(3),
        Price::from_cents(80).unwrap(),
        Money::from_usd(2, 40).unwrap(),
        Fee::zero(FeeKind::Entry),
        ExchangeTimestamp::from_utc(t),
        ReceivedAt::from_utc(t),
    );
    tracker
        .apply_event(PositionEvent::PartialFill { fill: fill.clone() })
        .unwrap();
    risk.on_fill(&fill);

    observe_live_event(
        &dir,
        &cfg,
        &mut strategy,
        &mut tracker,
        &risk,
        &mut venue,
        &snap,
        quote_event(None, 40, 41, 80, market_id, game_id),
    );
    let reqs = captured.lock().unwrap().clone();
    let posts: Vec<_> = reqs
        .iter()
        .filter(|r| r.method.eq_ignore_ascii_case("POST"))
        .collect();
    assert_eq!(posts.len(), 1);
    assert_eq!(posts[0].path, CREATE_ORDER_PATH);
    let body = posts[0].body.as_deref().unwrap();
    assert!(body.contains(&ticker));
    assert!(body.contains("\"side\":\"ask\""));
    assert!(body.contains("\"reduce_only\":true"));
    assert!(body.contains("\"post_only\":false"));
    assert!(body.contains("\"time_in_force\":\"immediate_or_cancel\""));
    assert!(!body.contains("https://external-api.kalshi.com"));
    assert!(
        !tracker.has_working_liquidation(game_id),
        "IOC remaining 0 fill 0 must not stay WORKING"
    );
    assert!(!tracker.has_unknown_liquidation(game_id));
    assert_eq!(
        tracker.get(pid).unwrap().lifecycle(),
        momento_core::PositionLifecycle::LiquidationActive
    );
}

#[test]
fn col_quote_does_not_liquidate_wsh_position_same_game() {
    let dir = tmp_dir();
    let cfg = live_cfg();
    let snap = weekly50();
    let captured = Arc::new(Mutex::new(Vec::new()));
    let ack = format!(
        r#"{{"order_id":"{}","fill_count":"0.00","remaining_count":"0.00","ts_ms":1715793600123}}"#,
        encode_venue_order_id(momento_core::VenueOrderId::from_raw(88))
    );
    let transport = RecordingTransport {
        inner: ScriptedTransport::new([TransportOutcome::Http {
            status: 201,
            body: ack,
        }]),
        captured: Arc::clone(&captured),
    };
    let wsh_ticker = "KXMLBGAME-26AUG241845COLWSH-WSH".to_string();
    let col_ticker = "KXMLBGAME-26AUG241845COLWSH-COL".to_string();
    let event_ticker = "KXMLBGAME-26AUG241845COLWSH";
    let wsh_market = market_id_for_ticker(&wsh_ticker);
    let col_market = market_id_for_ticker(&col_ticker);
    let game_id = game_id_for_event_ticker(event_ticker);
    let mut identity = StaticIdentity::new();
    identity.bind(
        wsh_ticker.clone(),
        MarketBinding {
            market_id: wsh_market,
            game_id,
            position_id: None,
        },
    );
    identity.bind(
        col_ticker.clone(),
        MarketBinding {
            market_id: col_market,
            game_id,
            position_id: None,
        },
    );
    let mut venue = KalshiVenue::production(transport, identity, ReceivedAt::from_utc(utc_now()));
    let mut strategy = MlbStrategy::new();
    let mut tracker = InMemoryPositionTracker::new();
    let risk = PaperRiskEngine::paper(snap.clone(), RiskConfig::mlb_paper_experimental().unwrap());
    let pid = tracker
        .get_or_create(
            MLB_STRATEGY_ID,
            game_id,
            &snap,
            Some(wsh_market),
            Some(Side::Yes),
        )
        .id();
    let t = utc_now();
    let fill = Fill::new(
        FillId::from_raw(7),
        pid,
        momento_core::ClientOrderId::from_raw(7),
        None,
        Contracts::from_u32(7),
        Price::from_cents(81).unwrap(),
        Money::from_cents(567),
        Fee::zero(FeeKind::Entry),
        ExchangeTimestamp::from_utc(t),
        ReceivedAt::from_utc(t),
    );
    tracker
        .apply_event(PositionEvent::PartialFill { fill: fill.clone() })
        .unwrap();
    risk.on_fill(&fill);

    observe_live_event(
        &dir,
        &cfg,
        &mut strategy,
        &mut tracker,
        &risk,
        &mut venue,
        &snap,
        quote_event(None, 17, 18, 17, col_market, game_id),
    );
    observe_live_event(
        &dir,
        &cfg,
        &mut strategy,
        &mut tracker,
        &risk,
        &mut venue,
        &snap,
        quote_event(None, 80, 81, 80, wsh_market, game_id),
    );
    assert!(
        captured
            .lock()
            .unwrap()
            .iter()
            .all(|r| !r.method.eq_ignore_ascii_case("POST")),
        "COL 17 and WSH 80 must not submit liquidation"
    );

    observe_live_event(
        &dir,
        &cfg,
        &mut strategy,
        &mut tracker,
        &risk,
        &mut venue,
        &snap,
        quote_event(None, 40, 41, 40, wsh_market, game_id),
    );
    let reqs = captured.lock().unwrap().clone();
    let posts: Vec<_> = reqs
        .iter()
        .filter(|r| r.method.eq_ignore_ascii_case("POST"))
        .collect();
    assert_eq!(posts.len(), 1);
    let body = posts[0].body.as_deref().unwrap();
    assert!(body.contains(&wsh_ticker));
    assert!(!body.contains(&col_ticker));
    assert!(body.contains("\"reduce_only\":true"));
}

#[test]
fn ioc_zero_fill_then_gap_to_24_submits_again_at_current_bid() {
    let dir = tmp_dir();
    let cfg = live_cfg();
    let snap = weekly50();
    let captured = Arc::new(Mutex::new(Vec::new()));
    let book_40 =
        r#"{"orderbook_fp":{"yes_dollars":[["0.4000","1.00"]],"no_dollars":[]}}"#.to_string();
    let book_24 =
        r#"{"orderbook_fp":{"yes_dollars":[["0.2400","1.00"]],"no_dollars":[]}}"#.to_string();
    let transport = RecordingTransport {
        inner: ScriptedTransport::new([
            TransportOutcome::Http {
                status: 200,
                body: book_40,
            },
            TransportOutcome::Http {
                status: 201,
                body: create_ack(77),
            },
            TransportOutcome::Http {
                status: 200,
                body: book_24,
            },
            TransportOutcome::Http {
                status: 201,
                body: create_ack(78),
            },
        ]),
        captured: Arc::clone(&captured),
    };
    let (identity, ticker, market_id, game_id) = bound_identity();
    let mut venue = KalshiVenue::production(transport, identity, ReceivedAt::from_utc(utc_now()));
    let mut strategy = MlbStrategy::new();
    let mut tracker = InMemoryPositionTracker::new();
    let risk = PaperRiskEngine::paper(snap.clone(), RiskConfig::mlb_paper_experimental().unwrap());
    let pid = tracker
        .get_or_create(
            MLB_STRATEGY_ID,
            game_id,
            &snap,
            Some(market_id),
            Some(Side::Yes),
        )
        .id();
    fill_held_yes(&mut tracker, &risk, pid, 7, 81, 1);

    observe_live_event(
        &dir,
        &cfg,
        &mut strategy,
        &mut tracker,
        &risk,
        &mut venue,
        &snap,
        quote_event(None, 40, 41, 40, market_id, game_id),
    );
    assert!(
        !tracker.has_working_liquidation_for_position(pid),
        "zero-fill IOC must not block the next reduction"
    );
    assert!(!tracker.has_unknown_liquidation_for_position(pid));
    assert_eq!(
        tracker.get(pid).unwrap().lifecycle(),
        momento_core::PositionLifecycle::LiquidationActive
    );

    observe_live_event(
        &dir,
        &cfg,
        &mut strategy,
        &mut tracker,
        &risk,
        &mut venue,
        &snap,
        quote_event(None, 24, 25, 24, market_id, game_id),
    );
    let reqs = captured.lock().unwrap().clone();
    let posts: Vec<_> = reqs
        .iter()
        .filter(|r| r.method.eq_ignore_ascii_case("POST"))
        .collect();
    assert_eq!(posts.len(), 2);
    let first = posts[0].body.as_deref().unwrap();
    let second = posts[1].body.as_deref().unwrap();
    assert!(first.contains(&ticker));
    assert!(second.contains(&ticker));
    assert!(first.contains("\"price\":\"0.4000\""));
    assert!(second.contains("\"price\":\"0.2400\""));
    assert!(second.contains("\"reduce_only\":true"));
    assert!(second.contains("\"time_in_force\":\"immediate_or_cancel\""));
    assert!(!tracker.has_unknown_liquidation_for_position(pid));
}

#[test]
fn working_liquidation_does_not_duplicate_while_ioc_awaiting_fill_stream() {
    let dir = tmp_dir();
    let cfg = live_cfg();
    let snap = weekly50();
    let captured = Arc::new(Mutex::new(Vec::new()));
    let ack_working = format!(
        r#"{{"order_id":"{}","fill_count":"3.00","remaining_count":"0.00","ts_ms":1715793600123}}"#,
        encode_venue_order_id(momento_core::VenueOrderId::from_raw(91))
    );
    let transport = RecordingTransport {
        inner: ScriptedTransport::new([
            TransportOutcome::Timeout,
            TransportOutcome::Http {
                status: 201,
                body: ack_working,
            },
            TransportOutcome::Timeout,
        ]),
        captured: Arc::clone(&captured),
    };
    let (identity, ticker, market_id, game_id) = bound_identity();
    let mut venue = KalshiVenue::production(transport, identity, ReceivedAt::from_utc(utc_now()));
    let mut strategy = MlbStrategy::new();
    let mut tracker = InMemoryPositionTracker::new();
    let risk = PaperRiskEngine::paper(snap.clone(), RiskConfig::mlb_paper_experimental().unwrap());
    let pid = tracker
        .get_or_create(
            MLB_STRATEGY_ID,
            game_id,
            &snap,
            Some(market_id),
            Some(Side::Yes),
        )
        .id();
    fill_held_yes(&mut tracker, &risk, pid, 7, 81, 1);

    observe_live_event(
        &dir,
        &cfg,
        &mut strategy,
        &mut tracker,
        &risk,
        &mut venue,
        &snap,
        quote_event(None, 40, 41, 40, market_id, game_id),
    );
    assert!(tracker.has_working_liquidation_for_position(pid));
    observe_live_event(
        &dir,
        &cfg,
        &mut strategy,
        &mut tracker,
        &risk,
        &mut venue,
        &snap,
        quote_event(None, 24, 25, 24, market_id, game_id),
    );
    let posts: Vec<_> = captured
        .lock()
        .unwrap()
        .iter()
        .filter(|r| r.method.eq_ignore_ascii_case("POST"))
        .cloned()
        .collect();
    assert_eq!(posts.len(), 1, "must not duplicate while WORKING");
    assert!(posts[0].body.as_deref().unwrap().contains(&ticker));
}

#[test]
fn unknown_liquidation_does_not_blind_retry() {
    let dir = tmp_dir();
    let cfg = live_cfg();
    let snap = weekly50();
    let captured = Arc::new(Mutex::new(Vec::new()));
    let transport = RecordingTransport {
        inner: ScriptedTransport::new([
            TransportOutcome::Timeout,
            TransportOutcome::Timeout,
            TransportOutcome::Timeout,
        ]),
        captured: Arc::clone(&captured),
    };
    let (identity, _ticker, market_id, game_id) = bound_identity();
    let mut venue = KalshiVenue::production(transport, identity, ReceivedAt::from_utc(utc_now()));
    let mut strategy = MlbStrategy::new();
    let mut tracker = InMemoryPositionTracker::new();
    let risk = PaperRiskEngine::paper(snap.clone(), RiskConfig::mlb_paper_experimental().unwrap());
    let pid = tracker
        .get_or_create(
            MLB_STRATEGY_ID,
            game_id,
            &snap,
            Some(market_id),
            Some(Side::Yes),
        )
        .id();
    fill_held_yes(&mut tracker, &risk, pid, 7, 81, 1);

    observe_live_event(
        &dir,
        &cfg,
        &mut strategy,
        &mut tracker,
        &risk,
        &mut venue,
        &snap,
        quote_event(None, 24, 25, 24, market_id, game_id),
    );
    assert!(tracker.has_unknown_liquidation_for_position(pid));
    observe_live_event(
        &dir,
        &cfg,
        &mut strategy,
        &mut tracker,
        &risk,
        &mut venue,
        &snap,
        quote_event(None, 24, 25, 24, market_id, game_id),
    );
    let posts: Vec<_> = captured
        .lock()
        .unwrap()
        .iter()
        .filter(|r| r.method.eq_ignore_ascii_case("POST"))
        .cloned()
        .collect();
    assert_eq!(posts.len(), 1, "UNKNOWN must not blindly retry");
}

const TWO_SIDED_MLB: &[(&str, &str, &str, &str)] = &[
    (
        "CHC vs AZ",
        "KXMLBGAME-26AUG25CHCAZ",
        "KXMLBGAME-26AUG25CHCAZ-CHC",
        "KXMLBGAME-26AUG25CHCAZ-AZ",
    ),
    (
        "CLE vs LAA",
        "KXMLBGAME-26AUG25CLELAA",
        "KXMLBGAME-26AUG25CLELAA-CLE",
        "KXMLBGAME-26AUG25CLELAA-LAA",
    ),
    (
        "TEX vs CWS",
        "KXMLBGAME-26AUG25TEXCWS",
        "KXMLBGAME-26AUG25TEXCWS-TEX",
        "KXMLBGAME-26AUG25TEXCWS-CWS",
    ),
    (
        "COL vs WSH",
        "KXMLBGAME-26AUG241845COLWSH",
        "KXMLBGAME-26AUG241845COLWSH-WSH",
        "KXMLBGAME-26AUG241845COLWSH-COL",
    ),
];

fn bind_two_sided(
    event_ticker: &str,
    held_ticker: &str,
    opponent_ticker: &str,
) -> (
    StaticIdentity,
    momento_core::MarketId,
    momento_core::MarketId,
    GameId,
) {
    let held_market = market_id_for_ticker(held_ticker);
    let opponent_market = market_id_for_ticker(opponent_ticker);
    let game_id = game_id_for_event_ticker(event_ticker);
    assert_ne!(held_market, opponent_market);
    let mut identity = StaticIdentity::new();
    identity.bind(
        held_ticker.to_string(),
        MarketBinding {
            market_id: held_market,
            game_id,
            position_id: None,
        },
    );
    identity.bind(
        opponent_ticker.to_string(),
        MarketBinding {
            market_id: opponent_market,
            game_id,
            position_id: None,
        },
    );
    (identity, held_market, opponent_market, game_id)
}

fn create_ack(raw: u128) -> String {
    format!(
        r#"{{"order_id":"{}","fill_count":"0.00","remaining_count":"0.00","ts_ms":1715793600123}}"#,
        encode_venue_order_id(momento_core::VenueOrderId::from_raw(raw))
    )
}

fn fill_held_yes(
    tracker: &mut InMemoryPositionTracker,
    risk: &PaperRiskEngine,
    pid: momento_core::PositionId,
    qty: u32,
    cents: u16,
    fill_raw: u128,
) {
    let t = utc_now();
    let fill = Fill::new(
        FillId::from_raw(fill_raw),
        pid,
        momento_core::ClientOrderId::from_raw(fill_raw),
        None,
        Contracts::from_u32(qty),
        Price::from_cents(cents).unwrap(),
        Money::from_cents(i64::from(qty) * i64::from(cents)),
        Fee::zero(FeeKind::Entry),
        ExchangeTimestamp::from_utc(t),
        ReceivedAt::from_utc(t),
    );
    tracker
        .apply_event(PositionEvent::PartialFill { fill: fill.clone() })
        .unwrap();
    risk.on_fill(&fill);
}

fn opponent_quote_must_not_liquidate_held(
    label: &str,
    event_ticker: &str,
    held_ticker: &str,
    opponent_ticker: &str,
) {
    let dir = tmp_dir();
    let cfg = live_cfg();
    let snap = weekly50();
    let captured = Arc::new(Mutex::new(Vec::new()));
    let transport = RecordingTransport {
        inner: ScriptedTransport::new([TransportOutcome::Http {
            status: 201,
            body: create_ack(88),
        }]),
        captured: Arc::clone(&captured),
    };
    let (identity, held_market, opponent_market, game_id) =
        bind_two_sided(event_ticker, held_ticker, opponent_ticker);
    let mut venue = KalshiVenue::production(transport, identity, ReceivedAt::from_utc(utc_now()));
    let mut strategy = MlbStrategy::new();
    let mut tracker = InMemoryPositionTracker::new();
    let risk = PaperRiskEngine::paper(snap.clone(), RiskConfig::mlb_paper_experimental().unwrap());
    let pid = tracker
        .get_or_create(
            MLB_STRATEGY_ID,
            game_id,
            &snap,
            Some(held_market),
            Some(Side::Yes),
        )
        .id();
    fill_held_yes(&mut tracker, &risk, pid, 7, 81, 7);

    observe_live_event(
        &dir,
        &cfg,
        &mut strategy,
        &mut tracker,
        &risk,
        &mut venue,
        &snap,
        quote_event(None, 17, 18, 17, opponent_market, game_id),
    );
    observe_live_event(
        &dir,
        &cfg,
        &mut strategy,
        &mut tracker,
        &risk,
        &mut venue,
        &snap,
        quote_event(None, 80, 81, 80, held_market, game_id),
    );
    assert!(
        captured
            .lock()
            .unwrap()
            .iter()
            .all(|r| !r.method.eq_ignore_ascii_case("POST")),
        "{label}: opponent 17 and held 80 must not submit liquidation"
    );

    observe_live_event(
        &dir,
        &cfg,
        &mut strategy,
        &mut tracker,
        &risk,
        &mut venue,
        &snap,
        quote_event(None, 40, 41, 40, held_market, game_id),
    );
    let reqs = captured.lock().unwrap().clone();
    let posts: Vec<_> = reqs
        .iter()
        .filter(|r| r.method.eq_ignore_ascii_case("POST"))
        .collect();
    assert_eq!(posts.len(), 1, "{label}");
    let body = posts[0].body.as_deref().unwrap();
    assert!(body.contains(held_ticker), "{label}: liquidation ticker");
    assert!(
        !body.contains(opponent_ticker),
        "{label}: opponent ticker must not appear"
    );
    assert!(body.contains("\"reduce_only\":true"), "{label}");
}

#[test]
fn two_sided_mlb_games_cannot_cross_liquidate() {
    for (label, event, held, opponent) in TWO_SIDED_MLB {
        opponent_quote_must_not_liquidate_held(label, event, held, opponent);
    }
}

#[test]
fn opponent_observed_first_cannot_own_stop_after_held_entry() {
    let dir = tmp_dir();
    let cfg = live_cfg();
    let snap = weekly50();
    let captured = Arc::new(Mutex::new(Vec::new()));
    let transport = RecordingTransport {
        inner: ScriptedTransport::new([TransportOutcome::Http {
            status: 201,
            body: create_ack(91),
        }]),
        captured: Arc::clone(&captured),
    };
    let event = "KXMLBGAME-26AUG25CHCAZ";
    let chc = "KXMLBGAME-26AUG25CHCAZ-CHC";
    let az = "KXMLBGAME-26AUG25CHCAZ-AZ";
    let (identity, chc_market, az_market, game_id) = bind_two_sided(event, chc, az);
    let mut venue = KalshiVenue::production(transport, identity, ReceivedAt::from_utc(utc_now()));
    let mut strategy = MlbStrategy::new();
    let mut tracker = InMemoryPositionTracker::new();
    let risk = PaperRiskEngine::paper(snap.clone(), RiskConfig::mlb_paper_experimental().unwrap());

    observe_live_event(
        &dir,
        &cfg,
        &mut strategy,
        &mut tracker,
        &risk,
        &mut venue,
        &snap,
        quote_event(None, 50, 51, 50, az_market, game_id),
    );
    let pid = tracker.id_for_game(game_id).expect("game position");
    assert_eq!(
        tracker.get(pid).unwrap().market_id(),
        Some(az_market),
        "first observed ticker may stamp GameId position"
    );

    observe_live_event(
        &dir,
        &cfg,
        &mut strategy,
        &mut tracker,
        &risk,
        &mut venue,
        &snap,
        quote_event(None, 80, 81, 80, chc_market, game_id),
    );
    observe_live_event(
        &dir,
        &cfg,
        &mut strategy,
        &mut tracker,
        &risk,
        &mut venue,
        &snap,
        quote_event(None, 81, 82, 81, chc_market, game_id),
    );
    assert_eq!(
        tracker.get(pid).unwrap().market_id(),
        Some(chc_market),
        "approved CHC entry must rebind stop identity off AZ"
    );
    fill_held_yes(&mut tracker, &risk, pid, 7, 81, 11);

    observe_live_event(
        &dir,
        &cfg,
        &mut strategy,
        &mut tracker,
        &risk,
        &mut venue,
        &snap,
        quote_event(None, 17, 18, 17, az_market, game_id),
    );
    let posts_after_az: Vec<_> = captured
        .lock()
        .unwrap()
        .iter()
        .filter(|r| r.method.eq_ignore_ascii_case("POST"))
        .cloned()
        .collect();
    assert_eq!(posts_after_az.len(), 1, "only the CHC maker entry");
    assert!(posts_after_az[0].body.as_deref().unwrap().contains(chc));
    assert!(
        posts_after_az[0]
            .body
            .as_deref()
            .unwrap()
            .contains("\"post_only\":true")
    );
    assert!(
        !posts_after_az[0]
            .body
            .as_deref()
            .unwrap()
            .contains("\"reduce_only\":true"),
        "AZ 17 must not liquidate the CHC position"
    );
}

#[test]
fn venue_settlement_proceeds_mark_position_settled_without_synthetic_fill() {
    let dir = tmp_dir();
    let cfg = live_cfg();
    let snap = weekly50();
    let captured = Arc::new(Mutex::new(Vec::new()));
    let market = r#"{"market":{"ticker":"KXMLBGAME-TEST","event_ticker":"KXMLBGAME-EVT","yes_bid_dollars":"1.0000","yes_ask_dollars":"1.0000","last_price_dollars":"1.0000","result":"yes","settlement_value_dollars":"3.0000","settlement_ts":"2026-08-01T19:00:00Z","updated_time":"2026-08-01T19:00:00Z","price_level_structure":"linear_cent"}}"#;
    let transport = RecordingTransport {
        inner: ScriptedTransport::new([TransportOutcome::Http {
            status: 200,
            body: market.into(),
        }]),
        captured: Arc::clone(&captured),
    };
    let (identity, _, market_id, game_id) = bound_identity();
    let mut venue = KalshiVenue::production(transport, identity, ReceivedAt::from_utc(utc_now()));
    let mut strategy = MlbStrategy::new();
    let mut tracker = InMemoryPositionTracker::new();
    let risk = PaperRiskEngine::paper(snap.clone(), RiskConfig::mlb_paper_experimental().unwrap());
    let pid = tracker
        .get_or_create(
            MLB_STRATEGY_ID,
            game_id,
            &snap,
            Some(market_id),
            Some(Side::Yes),
        )
        .id();
    let t = utc_now();
    let fill = Fill::new(
        FillId::from_raw(9),
        pid,
        momento_core::ClientOrderId::from_raw(9),
        None,
        Contracts::from_u32(3),
        Price::from_cents(80).unwrap(),
        Money::from_usd(2, 40).unwrap(),
        Fee::zero(FeeKind::Entry),
        ExchangeTimestamp::from_utc(t),
        ReceivedAt::from_utc(t),
    );
    tracker
        .apply_event(PositionEvent::PartialFill { fill: fill.clone() })
        .unwrap();
    risk.on_fill(&fill);
    refresh_open_mlb_positions(
        &dir,
        &cfg,
        &mut strategy,
        &mut tracker,
        &risk,
        &mut venue,
        &snap,
        &std::collections::HashSet::from([game_id]),
    );
    let pos = tracker.get(pid).unwrap();
    assert_eq!(pos.lifecycle(), momento_core::PositionLifecycle::Settled);
    let reqs = captured.lock().unwrap();
    assert!(reqs.iter().all(|r| r.method.eq_ignore_ascii_case("GET")));
    assert!(!reqs.iter().any(|r| r.path.contains("/orders")));
}

fn apply_official_book_frame(book: &mut LocalOrderBook, raw: &str) -> momento_kalshi::BookQuote {
    let env = parse_ws_frame(raw).unwrap();
    let result = match env.msg_type.as_str() {
        "orderbook_snapshot" => book
            .apply_snapshot(
                env.sid.unwrap(),
                env.seq.unwrap(),
                &parse_orderbook_snapshot(&env).unwrap(),
            )
            .unwrap(),
        "orderbook_delta" => book
            .apply_delta(
                env.sid.unwrap(),
                env.seq.unwrap(),
                &parse_orderbook_delta(&env).unwrap(),
            )
            .unwrap(),
        other => panic!("unexpected {other}"),
    };
    match result {
        momento_kalshi::ApplyResult::Updated {
            quote: Some(quote), ..
        } => quote,
        other => panic!("expected quote, got {other:?}"),
    }
}

#[test]
fn websocket_book_yes_bid_80_then_81_reaches_scripted_submit() {
    let dir = tmp_dir();
    let cfg = live_cfg();
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
    let (identity, ticker, market_id, game_id) = bound_identity();
    let binding = identity.lookup_ticker(&ticker).unwrap();
    let mut venue = KalshiVenue::production(transport, identity, ReceivedAt::from_utc(utc_now()));
    let mut strategy = MlbStrategy::new();
    let mut tracker = InMemoryPositionTracker::new();
    let risk = PaperRiskEngine::paper(snap.clone(), RiskConfig::mlb_paper_experimental().unwrap());
    let mut book = LocalOrderBook::new();

    let q80 = apply_official_book_frame(
        &mut book,
        r#"{"type":"orderbook_snapshot","sid":2,"seq":2,"msg":{"market_ticker":"KXMLBGAME-TEST","market_id":"9b0f6b43-5b68-4f9f-9f02-9a2d1b8ac1a1","yes_dollars_fp":[["0.8000","10.00"]],"no_dollars_fp":[["0.1800","4.00"]]}}"#,
    );
    assert_eq!(q80.yes_bid, Price::from_cents(80).unwrap());
    assert_eq!(q80.yes_ask, Price::from_cents(82).unwrap());
    let received = ReceivedAt::from_utc(utc_now());
    let event = live_market_event_from_book(binding, q80, ts_ms(1715793600000), received);
    assert_eq!(event.mid, None);
    assert_eq!(event.last, None);
    assert_eq!(event.bid, Some(Price::from_cents(80).unwrap()));
    observe_live_event(
        &dir,
        &cfg,
        &mut strategy,
        &mut tracker,
        &risk,
        &mut venue,
        &snap,
        event,
    );
    assert!(captured.lock().unwrap().is_empty());

    let q81 = apply_official_book_frame(
        &mut book,
        r#"{"type":"orderbook_delta","sid":2,"seq":3,"msg":{"market_ticker":"KXMLBGAME-TEST","market_id":"9b0f6b43-5b68-4f9f-9f02-9a2d1b8ac1a1","price_dollars":"0.8100","delta_fp":"5.00","side":"yes","ts_ms":1715793601000}}"#,
    );
    assert_eq!(q81.yes_bid, Price::from_cents(81).unwrap());
    let event = live_market_event_from_book(binding, q81, ts_ms(1715793601000), received);
    observe_live_event(
        &dir,
        &cfg,
        &mut strategy,
        &mut tracker,
        &risk,
        &mut venue,
        &snap,
        event,
    );
    let reqs = captured.lock().unwrap().clone();
    assert_eq!(reqs.len(), 1);
    assert_eq!(reqs[0].method, "POST");
    assert_eq!(reqs[0].path, CREATE_ORDER_PATH);
    let body = reqs[0].body.as_deref().unwrap();
    assert!(body.contains(&ticker));
    assert!(body.contains("\"post_only\":true"));
    assert!(body.contains("\"price\":\"0.8100\""));
    assert_eq!(market_id, binding.market_id);
    assert_eq!(game_id, binding.game_id);
}

#[test]
fn websocket_seq_gap_does_not_emit_strategy_quote() {
    let mut book = LocalOrderBook::new();
    let _ = apply_official_book_frame(
        &mut book,
        r#"{"type":"orderbook_snapshot","sid":2,"seq":2,"msg":{"market_ticker":"KXMLBGAME-TEST","market_id":"9b0f6b43-5b68-4f9f-9f02-9a2d1b8ac1a1","yes_dollars_fp":[["0.8000","10.00"]],"no_dollars_fp":[["0.1800","4.00"]]}}"#,
    );
    let env = parse_ws_frame(
        r#"{"type":"orderbook_delta","sid":2,"seq":5,"msg":{"market_ticker":"KXMLBGAME-TEST","market_id":"9b0f6b43-5b68-4f9f-9f02-9a2d1b8ac1a1","price_dollars":"0.8100","delta_fp":"5.00","side":"yes","ts_ms":1715793601000}}"#,
    )
    .unwrap();
    let applied = book
        .apply_delta(
            env.sid.unwrap(),
            env.seq.unwrap(),
            &parse_orderbook_delta(&env).unwrap(),
        )
        .unwrap();
    assert_eq!(applied, momento_kalshi::ApplyResult::Gap);
    assert!(book.quote("KXMLBGAME-TEST").is_none());
}

fn venue_fill_json(
    trade: u128,
    venue_order: u128,
    count: &str,
    price: &str,
    client: Option<u128>,
) -> String {
    let client_field = match client {
        Some(cid) => format!(
            r#""client_order_id":"{}","#,
            encode_client_order_id(momento_core::ClientOrderId::from_raw(cid))
        ),
        None => String::new(),
    };
    format!(
        r#"{{"trade_id":"{}","order_id":"{}",{client_field}"ticker":"KXMLBGAME-TEST","market_ticker":"KXMLBGAME-TEST","count_fp":"{count}","yes_price_dollars":"{price}","created_time":"2026-09-13T20:52:38Z"}}"#,
        encode_venue_order_id(momento_core::VenueOrderId::from_raw(trade)),
        encode_venue_order_id(momento_core::VenueOrderId::from_raw(venue_order)),
    )
}

fn fills_page(fills: &[String], cursor: Option<&str>) -> String {
    let cursor = match cursor {
        Some(c) => format!(r#""{c}""#),
        None => "null".into(),
    };
    format!(r#"{{"fills":[{}],"cursor":{cursor}}}"#, fills.join(","))
}

fn submit_ack(venue_order: u128) -> String {
    format!(
        r#"{{"order_id":"{}","fill_count":"0.00","remaining_count":"7.00","ts_ms":1715793600123}}"#,
        encode_venue_order_id(momento_core::VenueOrderId::from_raw(venue_order))
    )
}

#[test]
fn venue_fill_without_client_order_id_is_applied_via_order_id() {
    let dir = tmp_dir();
    let cfg = live_cfg();
    let snap = weekly50();
    let transport = ScriptedTransport::new([
        TransportOutcome::Http {
            status: 201,
            body: submit_ack(99),
        },
        TransportOutcome::Http {
            status: 200,
            body: fills_page(&[venue_fill_json(11, 99, "7.00", "0.8100", None)], None),
        },
    ]);
    let (identity, _, market_id, game_id) = bound_identity();
    let mut venue = KalshiVenue::production(transport, identity, ReceivedAt::from_utc(utc_now()));
    let mut strategy = MlbStrategy::new();
    let mut tracker = InMemoryPositionTracker::new();
    let risk = PaperRiskEngine::paper(snap.clone(), RiskConfig::mlb_paper_experimental().unwrap());
    submit_qualifying_maker(
        &dir,
        &cfg,
        &snap,
        &mut strategy,
        &mut tracker,
        &risk,
        &mut venue,
        market_id,
        game_id,
    );
    assert_eq!(risk.open_slot_count(), 1);
    assert_eq!(risk.max_open_positions(), 5);
    assert_eq!(
        tracker.entry_orders_for_game(game_id)[0]
            .quantities()
            .filled
            .get(),
        0
    );

    ingest_fills(&mut venue, &mut tracker, &risk);
    risk.adopt_fill_authoritative_occupancy(tracker.positions());

    let order = tracker.entry_orders_for_game(game_id)[0].clone();
    assert_eq!(order.state(), OrderState::Filled);
    assert_eq!(order.quantities().filled.get(), 7);
    let pos = tracker.get(order.position_id()).unwrap();
    assert_eq!(pos.filled_quantity().get(), 7);
    assert_eq!(pos.fill_history().len(), 1);
    assert_eq!(risk.open_slot_count(), 1);
    assert_eq!(risk.max_open_positions(), 5);
}

#[test]
fn venue_fill_reconciliation_is_idempotent() {
    let dir = tmp_dir();
    let cfg = live_cfg();
    let snap = weekly50();
    let page = fills_page(&[venue_fill_json(11, 99, "7.00", "0.8100", None)], None);
    let transport = ScriptedTransport::new([
        TransportOutcome::Http {
            status: 201,
            body: submit_ack(99),
        },
        TransportOutcome::Http {
            status: 200,
            body: page.clone(),
        },
        TransportOutcome::Http {
            status: 200,
            body: page,
        },
    ]);
    let (identity, _, market_id, game_id) = bound_identity();
    let mut venue = KalshiVenue::production(transport, identity, ReceivedAt::from_utc(utc_now()));
    let mut strategy = MlbStrategy::new();
    let mut tracker = InMemoryPositionTracker::new();
    let risk = PaperRiskEngine::paper(snap.clone(), RiskConfig::mlb_paper_experimental().unwrap());
    submit_qualifying_maker(
        &dir,
        &cfg,
        &snap,
        &mut strategy,
        &mut tracker,
        &risk,
        &mut venue,
        market_id,
        game_id,
    );

    ingest_fills(&mut venue, &mut tracker, &risk);
    ingest_fills(&mut venue, &mut tracker, &risk);
    risk.adopt_fill_authoritative_occupancy(tracker.positions());

    let order = tracker.entry_orders_for_game(game_id)[0].clone();
    assert_eq!(order.quantities().filled.get(), 7);
    assert_eq!(
        tracker
            .get(order.position_id())
            .unwrap()
            .fill_history()
            .len(),
        1
    );
    assert_eq!(
        tracker.reconciliation_state(),
        momento_core::ReconciliationState::Healthy
    );
    assert_eq!(risk.open_slot_count(), 1);
}

#[test]
fn first_fill_page_cannot_hide_older_venue_fill() {
    let dir = tmp_dir();
    let cfg = live_cfg();
    let snap = weekly50();
    let other = venue_fill_json(1, 1, "3.00", "0.8000", Some(1));
    let ours = venue_fill_json(11, 99, "7.00", "0.8100", None);
    let captured = Arc::new(Mutex::new(Vec::new()));
    let transport = RecordingTransport {
        inner: ScriptedTransport::new([
            TransportOutcome::Http {
                status: 201,
                body: submit_ack(99),
            },
            TransportOutcome::Http {
                status: 200,
                body: fills_page(&[other], Some("page2")),
            },
            TransportOutcome::Http {
                status: 200,
                body: fills_page(&[ours], None),
            },
        ]),
        captured: Arc::clone(&captured),
    };
    let (identity, _, market_id, game_id) = bound_identity();
    let mut venue = KalshiVenue::production(transport, identity, ReceivedAt::from_utc(utc_now()));
    let mut strategy = MlbStrategy::new();
    let mut tracker = InMemoryPositionTracker::new();
    let risk = PaperRiskEngine::paper(snap.clone(), RiskConfig::mlb_paper_experimental().unwrap());
    submit_qualifying_maker(
        &dir,
        &cfg,
        &snap,
        &mut strategy,
        &mut tracker,
        &risk,
        &mut venue,
        market_id,
        game_id,
    );
    captured.lock().unwrap().clear();

    ingest_fills(&mut venue, &mut tracker, &risk);

    let reqs = captured.lock().unwrap().clone();
    assert!(
        reqs.iter()
            .any(|r| r.path.contains("cursor=page2") && r.path.contains("/portfolio/fills"))
    );
    assert_eq!(
        tracker.entry_orders_for_game(game_id)[0]
            .quantities()
            .filled
            .get(),
        7
    );
}

#[test]
fn get_order_filled_does_not_fabricate_a_local_fill() {
    let dir = tmp_dir();
    let cfg = live_cfg();
    let snap = weekly50();
    let transport = ScriptedTransport::new([
        TransportOutcome::Http {
            status: 201,
            body: submit_ack(99),
        },
        TransportOutcome::Http {
            status: 200,
            body: kalshi_get_order_json("executed", "7.00", "0.00"),
        },
        TransportOutcome::Http {
            status: 200,
            body: fills_page(&[], None),
        },
    ]);
    let (identity, _, market_id, game_id) = bound_identity();
    let mut venue = KalshiVenue::production(transport, identity, ReceivedAt::from_utc(utc_now()));
    let mut strategy = MlbStrategy::new();
    let mut tracker = InMemoryPositionTracker::new();
    let risk = PaperRiskEngine::paper(snap.clone(), RiskConfig::mlb_paper_experimental().unwrap());
    submit_qualifying_maker(
        &dir,
        &cfg,
        &snap,
        &mut strategy,
        &mut tracker,
        &risk,
        &mut venue,
        market_id,
        game_id,
    );

    sync_working_orders(&mut venue, &mut tracker, &risk);

    let order = tracker.entry_orders_for_game(game_id)[0].clone();
    assert_eq!(order.state(), OrderState::Working);
    assert_eq!(order.quantities().filled.get(), 0);
    assert!(
        tracker
            .get(order.position_id())
            .unwrap()
            .fill_history()
            .is_empty()
    );
    assert_eq!(risk.open_slot_count(), 1);
}

#[test]
fn five_stale_working_reservations_clear_after_authoritative_fills() {
    let dir = tmp_dir();
    let cfg = live_cfg();
    let snap = weekly50();
    let mut identity = StaticIdentity::new();
    let mut games = Vec::new();
    let mut acks = Vec::new();
    let mut fills = Vec::new();
    for i in 0..5u128 {
        let ticker = format!("KXMLBGAME-TEST-{i}");
        let event = format!("KXMLBGAME-EVT-{i}");
        let market_id = market_id_for_ticker(&ticker);
        let game_id = game_id_for_event_ticker(&event);
        identity.bind(
            ticker,
            MarketBinding {
                market_id,
                game_id,
                position_id: None,
            },
        );
        games.push((market_id, game_id, 200 + i));
        acks.push(TransportOutcome::Http {
            status: 201,
            body: submit_ack(200 + i),
        });
        fills.push(venue_fill_json(300 + i, 200 + i, "7.00", "0.8100", None));
    }
    acks.push(TransportOutcome::Http {
        status: 200,
        body: fills_page(&fills, None),
    });
    let transport = ScriptedTransport::new(acks);
    let mut venue = KalshiVenue::production(transport, identity, ReceivedAt::from_utc(utc_now()));
    let mut strategy = MlbStrategy::new();
    let mut tracker = InMemoryPositionTracker::new();
    let risk = PaperRiskEngine::paper(snap.clone(), RiskConfig::mlb_paper_experimental().unwrap());
    assert_eq!(risk.max_open_positions(), 5);

    for (market_id, game_id, _) in games.iter().copied() {
        submit_qualifying_maker(
            &dir,
            &cfg,
            &snap,
            &mut strategy,
            &mut tracker,
            &risk,
            &mut venue,
            market_id,
            game_id,
        );
    }
    assert_eq!(risk.open_slot_count(), 5);

    ingest_fills(&mut venue, &mut tracker, &risk);
    risk.adopt_fill_authoritative_occupancy(tracker.positions());

    for (_, game_id, _) in games {
        let order = tracker.entry_orders_for_game(game_id)[0].clone();
        assert_eq!(order.state(), OrderState::Filled);
        assert_eq!(order.quantities().filled.get(), 7);
        assert_eq!(
            tracker
                .get(order.position_id())
                .unwrap()
                .fill_history()
                .len(),
            1
        );
    }
    assert_eq!(risk.open_slot_count(), 5);
    assert_eq!(risk.max_open_positions(), 5);
}

#[test]
fn fractional_fill_parts_coalesce_to_integer_contracts() {
    let dir = tmp_dir();
    let cfg = live_cfg();
    let snap = weekly50();
    let transport = ScriptedTransport::new([
        TransportOutcome::Http {
            status: 201,
            body: submit_ack(99),
        },
        TransportOutcome::Http {
            status: 200,
            body: fills_page(
                &[
                    venue_fill_json(11, 99, "6.65", "0.8100", None),
                    venue_fill_json(12, 99, "0.35", "0.8100", None),
                ],
                None,
            ),
        },
    ]);
    let (identity, _, market_id, game_id) = bound_identity();
    let mut venue = KalshiVenue::production(transport, identity, ReceivedAt::from_utc(utc_now()));
    let mut strategy = MlbStrategy::new();
    let mut tracker = InMemoryPositionTracker::new();
    let risk = PaperRiskEngine::paper(snap.clone(), RiskConfig::mlb_paper_experimental().unwrap());
    submit_qualifying_maker(
        &dir,
        &cfg,
        &snap,
        &mut strategy,
        &mut tracker,
        &risk,
        &mut venue,
        market_id,
        game_id,
    );

    ingest_fills(&mut venue, &mut tracker, &risk);
    risk.adopt_fill_authoritative_occupancy(tracker.positions());

    let order = tracker.entry_orders_for_game(game_id)[0].clone();
    assert_eq!(order.state(), OrderState::Filled);
    assert_eq!(order.quantities().filled.get(), 7);
    assert_eq!(
        tracker
            .get(order.position_id())
            .unwrap()
            .fill_history()
            .len(),
        1
    );
    assert_eq!(risk.open_slot_count(), 1);
}

#[test]
fn fractional_fill_coalesce_is_idempotent() {
    let dir = tmp_dir();
    let cfg = live_cfg();
    let snap = weekly50();
    let page = fills_page(
        &[
            venue_fill_json(11, 99, "6.65", "0.8100", None),
            venue_fill_json(12, 99, "0.35", "0.8100", None),
        ],
        None,
    );
    let transport = ScriptedTransport::new([
        TransportOutcome::Http {
            status: 201,
            body: submit_ack(99),
        },
        TransportOutcome::Http {
            status: 200,
            body: page.clone(),
        },
        TransportOutcome::Http {
            status: 200,
            body: page,
        },
    ]);
    let (identity, _, market_id, game_id) = bound_identity();
    let mut venue = KalshiVenue::production(transport, identity, ReceivedAt::from_utc(utc_now()));
    let mut strategy = MlbStrategy::new();
    let mut tracker = InMemoryPositionTracker::new();
    let risk = PaperRiskEngine::paper(snap.clone(), RiskConfig::mlb_paper_experimental().unwrap());
    submit_qualifying_maker(
        &dir,
        &cfg,
        &snap,
        &mut strategy,
        &mut tracker,
        &risk,
        &mut venue,
        market_id,
        game_id,
    );

    ingest_fills(&mut venue, &mut tracker, &risk);
    ingest_fills(&mut venue, &mut tracker, &risk);
    risk.adopt_fill_authoritative_occupancy(tracker.positions());

    let order = tracker.entry_orders_for_game(game_id)[0].clone();
    assert_eq!(order.quantities().filled.get(), 7);
    assert_eq!(
        tracker
            .get(order.position_id())
            .unwrap()
            .fill_history()
            .len(),
        1
    );
}

#[test]
fn leftover_integer_fill_row_does_not_exceed_or_block() {
    let dir = tmp_dir();
    let cfg = live_cfg();
    let snap = weekly50();
    let first = fills_page(&[venue_fill_json(11, 99, "7.00", "0.8200", None)], None);
    let leftover = fills_page(&[venue_fill_json(12, 99, "7.00", "0.8200", None)], None);
    let transport = ScriptedTransport::new([
        TransportOutcome::Http {
            status: 201,
            body: submit_ack(99),
        },
        TransportOutcome::Http {
            status: 200,
            body: first,
        },
        TransportOutcome::Http {
            status: 200,
            body: leftover,
        },
    ]);
    let (identity, _, market_id, game_id) = bound_identity();
    let mut venue = KalshiVenue::production(transport, identity, ReceivedAt::from_utc(utc_now()));
    let mut strategy = MlbStrategy::new();
    let mut tracker = InMemoryPositionTracker::new();
    let risk = PaperRiskEngine::paper(snap.clone(), RiskConfig::mlb_paper_experimental().unwrap());
    submit_qualifying_maker(
        &dir,
        &cfg,
        &snap,
        &mut strategy,
        &mut tracker,
        &risk,
        &mut venue,
        market_id,
        game_id,
    );

    ingest_fills(&mut venue, &mut tracker, &risk);
    ingest_fills(&mut venue, &mut tracker, &risk);
    risk.adopt_fill_authoritative_occupancy(tracker.positions());

    let order = tracker.entry_orders_for_game(game_id)[0].clone();
    assert_eq!(order.quantities().filled.get(), 7);
    assert_eq!(
        tracker
            .get(order.position_id())
            .unwrap()
            .fill_history()
            .len(),
        1
    );
    assert_eq!(
        tracker.reconciliation_state(),
        momento_core::ReconciliationState::Healthy
    );
}

#[test]
fn housekeeping_gates_unfreeze_settled_ambiguous_without_unknown() {
    let snap = weekly50();
    let risk = PaperRiskEngine::paper(snap.clone(), RiskConfig::mlb_paper_experimental().unwrap());
    let mut tracker = InMemoryPositionTracker::new();
    let pid = tracker
        .get_or_create(
            StrategyId::MLB,
            GameId::from_raw(10),
            &snap,
            Some(momento_core::MarketId::from_raw(2)),
            Some(Side::Yes),
        )
        .id();
    tracker
        .get_mut(pid)
        .unwrap()
        .apply_settlement(Money::from_cents(0))
        .unwrap();
    tracker.mark_ambiguous();
    assert!(tracker.reconciliation_state().blocks_new_exposure());
    let cleared = finish_housekeeping_gates(&mut tracker, &risk);
    assert!(cleared);
    assert_eq!(tracker.reconciliation_state(), ReconciliationState::Healthy);
    assert!(!tracker.reconciliation_state().blocks_new_exposure());
}

#[test]
fn lone_fractional_fill_does_not_apply() {
    let dir = tmp_dir();
    let cfg = live_cfg();
    let snap = weekly50();
    let transport = ScriptedTransport::new([
        TransportOutcome::Http {
            status: 201,
            body: submit_ack(99),
        },
        TransportOutcome::Http {
            status: 200,
            body: fills_page(&[venue_fill_json(11, 99, "6.65", "0.8100", None)], None),
        },
    ]);
    let (identity, _, market_id, game_id) = bound_identity();
    let mut venue = KalshiVenue::production(transport, identity, ReceivedAt::from_utc(utc_now()));
    let mut strategy = MlbStrategy::new();
    let mut tracker = InMemoryPositionTracker::new();
    let risk = PaperRiskEngine::paper(snap.clone(), RiskConfig::mlb_paper_experimental().unwrap());
    submit_qualifying_maker(
        &dir,
        &cfg,
        &snap,
        &mut strategy,
        &mut tracker,
        &risk,
        &mut venue,
        market_id,
        game_id,
    );

    ingest_fills(&mut venue, &mut tracker, &risk);
    risk.adopt_fill_authoritative_occupancy(tracker.positions());

    let order = tracker.entry_orders_for_game(game_id)[0].clone();
    assert_eq!(order.state(), OrderState::Working);
    assert_eq!(order.quantities().filled.get(), 0);
    assert!(
        tracker
            .get(order.position_id())
            .unwrap()
            .fill_history()
            .is_empty()
    );
    assert_eq!(risk.open_slot_count(), 1);
}

#[test]
fn mixed_price_fractional_fills_do_not_coalesce() {
    let dir = tmp_dir();
    let cfg = live_cfg();
    let snap = weekly50();
    let transport = ScriptedTransport::new([
        TransportOutcome::Http {
            status: 201,
            body: submit_ack(99),
        },
        TransportOutcome::Http {
            status: 200,
            body: fills_page(
                &[
                    venue_fill_json(11, 99, "6.65", "0.8100", None),
                    venue_fill_json(12, 99, "0.35", "0.8200", None),
                ],
                None,
            ),
        },
    ]);
    let (identity, _, market_id, game_id) = bound_identity();
    let mut venue = KalshiVenue::production(transport, identity, ReceivedAt::from_utc(utc_now()));
    let mut strategy = MlbStrategy::new();
    let mut tracker = InMemoryPositionTracker::new();
    let risk = PaperRiskEngine::paper(snap.clone(), RiskConfig::mlb_paper_experimental().unwrap());
    submit_qualifying_maker(
        &dir,
        &cfg,
        &snap,
        &mut strategy,
        &mut tracker,
        &risk,
        &mut venue,
        market_id,
        game_id,
    );

    ingest_fills(&mut venue, &mut tracker, &risk);

    let order = tracker.entry_orders_for_game(game_id)[0].clone();
    assert_eq!(order.state(), OrderState::Working);
    assert_eq!(order.quantities().filled.get(), 0);
    assert!(
        tracker
            .get(order.position_id())
            .unwrap()
            .fill_history()
            .is_empty()
    );
}

#[test]
fn fractional_parts_split_across_fill_pages_still_coalesce() {
    let dir = tmp_dir();
    let cfg = live_cfg();
    let snap = weekly50();
    let transport = ScriptedTransport::new([
        TransportOutcome::Http {
            status: 201,
            body: submit_ack(99),
        },
        TransportOutcome::Http {
            status: 200,
            body: fills_page(
                &[venue_fill_json(11, 99, "6.65", "0.8100", None)],
                Some("page2"),
            ),
        },
        TransportOutcome::Http {
            status: 200,
            body: fills_page(&[venue_fill_json(12, 99, "0.35", "0.8100", None)], None),
        },
    ]);
    let (identity, _, market_id, game_id) = bound_identity();
    let mut venue = KalshiVenue::production(transport, identity, ReceivedAt::from_utc(utc_now()));
    let mut strategy = MlbStrategy::new();
    let mut tracker = InMemoryPositionTracker::new();
    let risk = PaperRiskEngine::paper(snap.clone(), RiskConfig::mlb_paper_experimental().unwrap());
    submit_qualifying_maker(
        &dir,
        &cfg,
        &snap,
        &mut strategy,
        &mut tracker,
        &risk,
        &mut venue,
        market_id,
        game_id,
    );

    ingest_fills(&mut venue, &mut tracker, &risk);

    assert_eq!(
        tracker.entry_orders_for_game(game_id)[0]
            .quantities()
            .filled
            .get(),
        7
    );
}

#[test]
fn integer_fill_plus_fractional_parts_do_not_double_count() {
    let dir = tmp_dir();
    let cfg = live_cfg();
    let snap = weekly50();
    let transport = ScriptedTransport::new([
        TransportOutcome::Http {
            status: 201,
            body: submit_ack(99),
        },
        TransportOutcome::Http {
            status: 200,
            body: fills_page(
                &[
                    venue_fill_json(10, 99, "7.00", "0.8100", None),
                    venue_fill_json(11, 99, "6.65", "0.8100", None),
                    venue_fill_json(12, 99, "0.35", "0.8100", None),
                ],
                None,
            ),
        },
    ]);
    let (identity, _, market_id, game_id) = bound_identity();
    let mut venue = KalshiVenue::production(transport, identity, ReceivedAt::from_utc(utc_now()));
    let mut strategy = MlbStrategy::new();
    let mut tracker = InMemoryPositionTracker::new();
    let risk = PaperRiskEngine::paper(snap.clone(), RiskConfig::mlb_paper_experimental().unwrap());
    submit_qualifying_maker(
        &dir,
        &cfg,
        &snap,
        &mut strategy,
        &mut tracker,
        &risk,
        &mut venue,
        market_id,
        game_id,
    );

    ingest_fills(&mut venue, &mut tracker, &risk);

    let order = tracker.entry_orders_for_game(game_id)[0].clone();
    assert_eq!(order.quantities().filled.get(), 7);
    assert_eq!(
        tracker
            .get(order.position_id())
            .unwrap()
            .fill_history()
            .len(),
        1
    );
}
