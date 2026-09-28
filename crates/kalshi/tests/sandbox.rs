//! M8 sandbox mapping + M5 reconciliation against demo-shaped payloads.
//! These tests do not open sockets and do not require credentials.

use chrono::{TimeZone, Utc};
use momento_core::{
    Bps, ClientOrderId, Contracts, GameId, MarketId, Money, Order, OrderPresence, OrderState,
    Price, ReceivedAt, ReconcileOutcome, ReconciliationState, RiskDecisionId, SnapshotSource,
    StrategyId, VenueOrderId, VenueOrderSnapshot, WeeklyBankrollSnapshot,
};
use momento_kalshi::{
    REST_DEMO_SHARED, REST_PRODUCTION, WS_PRODUCTION, mapped_order_to_snapshot, redact_secrets,
    refuse_if_production,
};
use momento_pnl::PnlBreakdown;
use momento_positions::{InMemoryPositionTracker, PositionEvent, PositionTracker};
use momento_strategy_mlb::{MlbGamePhase, MlbGameSnapshot, MlbStrategy, MlbStrategySnapshot};

fn recv() -> ReceivedAt {
    ReceivedAt::from_utc(
        Utc.with_ymd_and_hms(2026, 8, 24, 18, 0, 0)
            .single()
            .unwrap(),
    )
}

fn snapshot() -> WeeklyBankrollSnapshot {
    WeeklyBankrollSnapshot::capture(
        Money::from_usd(50, 0).unwrap(),
        Bps::PCT_12_5,
        Utc.with_ymd_and_hms(2026, 8, 24, 16, 0, 0)
            .single()
            .unwrap(),
        SnapshotSource::Test,
    )
    .unwrap()
}

#[test]
fn production_urls_are_refused() {
    assert!(refuse_if_production(REST_PRODUCTION).is_err());
    assert!(refuse_if_production(WS_PRODUCTION).is_err());
    assert!(refuse_if_production(REST_DEMO_SHARED).is_ok());
}

#[test]
fn redaction_strips_signatures_and_tokens() {
    let raw = "KALSHI-ACCESS-SIGNATURE: deadbeef\nAuthorization: Bearer secret-token\n";
    let out = redact_secrets(raw);
    assert!(!out.contains("deadbeef"));
    assert!(!out.contains("secret-token"));
}

#[test]
fn m6_snapshot_survives_disconnect() {
    let mut game = MlbGameSnapshot::new(GameId::from_raw(10));
    game.phase = MlbGamePhase::GameLocked;
    let restored = MlbStrategy::restore(MlbStrategySnapshot { games: vec![game] });
    assert_eq!(
        restored.phase(GameId::from_raw(10)),
        MlbGamePhase::GameLocked
    );
}

#[test]
fn sandbox_portfolio_reconciles_and_pnl_is_not_invented() {
    let mut tracker = InMemoryPositionTracker::new();
    let pid = tracker
        .get_or_create(
            StrategyId::from_raw(1),
            GameId::from_raw(10),
            &snapshot(),
            Some(MarketId::from_raw(2)),
            Some(momento_core::Side::Yes),
        )
        .id();
    let order = Order::new_entry(
        ClientOrderId::from_raw(1),
        pid,
        GameId::from_raw(10),
        RiskDecisionId::from_raw(1),
        Price::from_cents(80).unwrap(),
        Contracts::from_u32(1),
    );
    tracker
        .apply_event(PositionEvent::OrderSubmitted { order })
        .unwrap();
    tracker
        .apply_event(PositionEvent::Unknown {
            client_order_id: ClientOrderId::from_raw(1),
        })
        .unwrap();
    let view = momento_core::MappedOrderView {
        client_order_id: ClientOrderId::from_raw(1),
        venue_order_id: VenueOrderId::from_raw(99),
        ticker: "DEMO-MKT".into(),
        state: OrderState::Working,
        requested: Contracts::from_u32(1),
        filled: Contracts::ZERO,
        remaining: Contracts::from_u32(1),
    };
    let mut snap: VenueOrderSnapshot = mapped_order_to_snapshot(&view);
    snap.presence = OrderPresence::Found;
    let result = tracker
        .reconcile(ClientOrderId::from_raw(1), snap, recv())
        .unwrap();
    assert_eq!(result.outcome, ReconcileOutcome::Found);
    assert_eq!(tracker.reconciliation_state(), ReconciliationState::Healthy);
    let pnl = PnlBreakdown::from_position(tracker.get(pid).unwrap());
    assert!(pnl.realized_pnl.is_none());
    assert!(pnl.unrealized_pnl.is_none());
}
