//! Milestone 5: fill-authoritative tracker, reconciliation, GAME_LOCKED.

use chrono::{TimeZone, Utc};
use momento_core::{
    AuditEvent, Bps, ClientOrderId, Contracts, ExchangeTimestamp, Fee, FeeKind, Fill, FillId,
    GameId, MarketId, Money, Order, OrderPresence, OrderState, PositionId, PositionLifecycle,
    Price, ReceivedAt, ReconcileOutcome, ReconciliationState, RiskDecisionId, SettlementEvent,
    Side, SnapshotSource, StrategyId, VenueOrderId, VenueOrderSnapshot, WeeklyBankrollSnapshot,
};
use momento_positions::{
    ApplyStatus, InMemoryPositionTracker, PositionEvent, PositionTracker, TrackerError,
};

fn usd(d: i64, c: u8) -> Money {
    Money::from_usd(d, c).unwrap()
}

fn px(c: u16) -> Price {
    Price::from_cents(c).unwrap()
}

fn ts() -> (ExchangeTimestamp, ReceivedAt) {
    let t = Utc
        .with_ymd_and_hms(2026, 8, 24, 18, 0, 0)
        .single()
        .unwrap();
    (ExchangeTimestamp::from_utc(t), ReceivedAt::from_utc(t))
}

fn snapshot() -> WeeklyBankrollSnapshot {
    let now = Utc
        .with_ymd_and_hms(2026, 8, 24, 16, 0, 0)
        .single()
        .unwrap();
    WeeklyBankrollSnapshot::capture(usd(50, 0), Bps::PCT_12_5, now, SnapshotSource::Test).unwrap()
}

fn open(tracker: &mut InMemoryPositionTracker) -> PositionId {
    tracker
        .get_or_create(
            StrategyId::from_raw(1),
            GameId::from_raw(10),
            &snapshot(),
            Some(MarketId::from_raw(2)),
            Some(Side::Yes),
        )
        .id()
}

fn entry_order(pid: PositionId, client: u128, qty: u32) -> Order {
    Order::new_entry(
        ClientOrderId::from_raw(client),
        pid,
        GameId::from_raw(10),
        RiskDecisionId::from_raw(1),
        px(80),
        Contracts::from_u32(qty),
    )
}

fn entry_fill(
    pid: PositionId,
    client: u128,
    fill: u128,
    qty: u32,
    premium: Money,
    fee: Money,
) -> Fill {
    let (ex, recv) = ts();
    Fill::new(
        FillId::from_raw(fill),
        pid,
        ClientOrderId::from_raw(client),
        Some(VenueOrderId::from_raw(client)),
        Contracts::from_u32(qty),
        px(80),
        premium,
        Fee::new(fee, FeeKind::Entry),
        ex,
        recv,
    )
}

fn submit(tracker: &mut InMemoryPositionTracker, pid: PositionId, client: u128, qty: u32) {
    tracker
        .apply_event(PositionEvent::OrderSubmitted {
            order: entry_order(pid, client, qty),
        })
        .unwrap();
}

fn working(tracker: &mut InMemoryPositionTracker, client: u128) {
    tracker
        .apply_event(PositionEvent::OrderWorking {
            client_order_id: ClientOrderId::from_raw(client),
            venue_order_id: VenueOrderId::from_raw(client),
        })
        .unwrap();
}

fn empty_snapshot(presence: OrderPresence) -> VenueOrderSnapshot {
    VenueOrderSnapshot {
        presence,
        venue_order_id: None,
        venue_status: None,
        venue_filled: None,
        venue_remaining: None,
        venue_fill_prices: Vec::new(),
        venue_fees: None,
        fills: Vec::new(),
        exchange_ts: None,
        contradictory: false,
        insufficient: false,
        authoritative: true,
    }
}

#[test]
fn one_game_one_position_id() {
    let mut tracker = InMemoryPositionTracker::new();
    let a = open(&mut tracker);
    let b = open(&mut tracker);
    assert_eq!(a, b);
}

#[test]
fn multiple_orders_one_position_id() {
    let mut tracker = InMemoryPositionTracker::new();
    let pid = open(&mut tracker);
    submit(&mut tracker, pid, 1, 7);
    working(&mut tracker, 1);
    tracker
        .apply_event(PositionEvent::PartialFill {
            fill: entry_fill(pid, 1, 10, 3, usd(2, 40), Money::ZERO),
        })
        .unwrap();
    tracker
        .apply_event(PositionEvent::Cancelled {
            client_order_id: ClientOrderId::from_raw(1),
        })
        .unwrap();
    submit(&mut tracker, pid, 2, 1);
    working(&mut tracker, 2);
    tracker
        .apply_event(PositionEvent::FullFill {
            fill: entry_fill(pid, 2, 11, 1, usd(0, 80), Money::ZERO),
        })
        .unwrap();
    assert_eq!(tracker.get(pid).unwrap().id(), pid);
    assert_eq!(tracker.get(pid).unwrap().fill_history().len(), 2);
    assert_ne!(
        tracker
            .order(ClientOrderId::from_raw(1))
            .unwrap()
            .client_order_id(),
        tracker
            .order(ClientOrderId::from_raw(2))
            .unwrap()
            .client_order_id()
    );
}

#[test]
fn multiple_fills_one_position_id() {
    let mut tracker = InMemoryPositionTracker::new();
    let pid = open(&mut tracker);
    submit(&mut tracker, pid, 1, 7);
    working(&mut tracker, 1);
    tracker
        .apply_event(PositionEvent::PartialFill {
            fill: entry_fill(pid, 1, 10, 3, usd(2, 40), Money::ZERO),
        })
        .unwrap();
    tracker
        .apply_event(PositionEvent::PartialFill {
            fill: entry_fill(pid, 1, 11, 1, usd(0, 80), Money::ZERO),
        })
        .unwrap();
    let pos = tracker.get(pid).unwrap();
    assert_eq!(pos.id(), pid);
    assert_eq!(pos.fill_history().len(), 2);
    assert_eq!(pos.actual_exposure().as_money(), usd(3, 20));
}

#[test]
fn partial_fill_changes_actual_exposure() {
    let mut tracker = InMemoryPositionTracker::new();
    let pid = open(&mut tracker);
    submit(&mut tracker, pid, 1, 7);
    working(&mut tracker, 1);
    tracker
        .apply_event(PositionEvent::PartialFill {
            fill: entry_fill(pid, 1, 10, 3, usd(2, 40), Money::ZERO),
        })
        .unwrap();
    let pos = tracker.get(pid).unwrap();
    assert_eq!(pos.actual_exposure().as_money(), usd(2, 40));
    assert_eq!(pos.remaining_economic_target().unwrap(), usd(3, 85));
    assert_eq!(pos.lifecycle(), PositionLifecycle::OpenPartial);
}

#[test]
fn cancellation_does_not_erase_fills() {
    let mut tracker = InMemoryPositionTracker::new();
    let pid = open(&mut tracker);
    submit(&mut tracker, pid, 1, 7);
    working(&mut tracker, 1);
    tracker
        .apply_event(PositionEvent::PartialFill {
            fill: entry_fill(pid, 1, 10, 3, usd(2, 40), Money::ZERO),
        })
        .unwrap();
    tracker
        .apply_event(PositionEvent::Cancelled {
            client_order_id: ClientOrderId::from_raw(1),
        })
        .unwrap();
    let pos = tracker.get(pid).unwrap();
    assert_eq!(pos.fill_history().len(), 1);
    assert_eq!(pos.actual_exposure().as_money(), usd(2, 40));
    assert_eq!(pos.filled_quantity(), Contracts::from_u32(3));
    assert_eq!(
        tracker.order(ClientOrderId::from_raw(1)).unwrap().state(),
        OrderState::Cancelled
    );
}

#[test]
fn submitted_is_not_filled() {
    let mut tracker = InMemoryPositionTracker::new();
    let pid = open(&mut tracker);
    submit(&mut tracker, pid, 1, 7);
    let pos = tracker.get(pid).unwrap();
    assert_eq!(pos.submitted_quantity(), Contracts::from_u32(7));
    assert_eq!(pos.filled_quantity(), Contracts::ZERO);
    assert_eq!(pos.remaining_economic_target().unwrap(), usd(6, 25));
}

#[test]
fn working_is_not_filled() {
    let mut tracker = InMemoryPositionTracker::new();
    let pid = open(&mut tracker);
    submit(&mut tracker, pid, 1, 7);
    working(&mut tracker, 1);
    let pos = tracker.get(pid).unwrap();
    assert_eq!(pos.working_quantity(), Contracts::from_u32(7));
    assert_eq!(pos.filled_quantity(), Contracts::ZERO);
    assert_eq!(
        tracker.order(ClientOrderId::from_raw(1)).unwrap().state(),
        OrderState::Working
    );
}

#[test]
fn unknown_blocks_new_exposure() {
    let mut tracker = InMemoryPositionTracker::new();
    let pid = open(&mut tracker);
    submit(&mut tracker, pid, 1, 7);
    tracker
        .apply_event(PositionEvent::Unknown {
            client_order_id: ClientOrderId::from_raw(1),
        })
        .unwrap();
    assert!(tracker.reconciliation_state().blocks_new_exposure());
    assert!(!tracker.can_open_new_exposure());
    let err = tracker
        .apply_event(PositionEvent::OrderSubmitted {
            order: entry_order(pid, 2, 1),
        })
        .unwrap_err();
    assert!(matches!(err, TrackerError::NewExposureBlocked(_)));
}

#[test]
fn unknown_reservation_is_preserved() {
    let mut tracker = InMemoryPositionTracker::new();
    let pid = open(&mut tracker);
    submit(&mut tracker, pid, 1, 7);
    let submitted = tracker.get(pid).unwrap().submitted_quantity();
    let working_qty = tracker.get(pid).unwrap().working_quantity();
    tracker
        .apply_event(PositionEvent::Unknown {
            client_order_id: ClientOrderId::from_raw(1),
        })
        .unwrap();
    let pos = tracker.get(pid).unwrap();
    assert_eq!(pos.submitted_quantity(), submitted);
    assert_eq!(pos.working_quantity(), working_qty);
    assert_eq!(pos.filled_quantity(), Contracts::ZERO);
    assert_eq!(
        tracker.order(ClientOrderId::from_raw(1)).unwrap().state(),
        OrderState::Unknown
    );
}

#[test]
fn found_reconciliation() {
    let mut tracker = InMemoryPositionTracker::new();
    let pid = open(&mut tracker);
    submit(&mut tracker, pid, 1, 7);
    tracker
        .apply_event(PositionEvent::Unknown {
            client_order_id: ClientOrderId::from_raw(1),
        })
        .unwrap();
    let mut snap = empty_snapshot(OrderPresence::Found);
    snap.venue_order_id = Some(VenueOrderId::from_raw(99));
    snap.venue_status = Some(OrderState::Working);
    snap.venue_filled = Some(Contracts::ZERO);
    snap.authoritative = true;
    let (_, recv) = ts();
    let result = tracker
        .reconcile(ClientOrderId::from_raw(1), snap, recv)
        .unwrap();
    assert_eq!(result.outcome, ReconcileOutcome::Found);
    assert!(result.authoritative);
    assert_eq!(result.position_id, pid);
    assert_eq!(result.client_order_id, ClientOrderId::from_raw(1));
    assert_eq!(result.venue_order_id, Some(VenueOrderId::from_raw(99)));
    assert_eq!(tracker.reconciliation_state(), ReconciliationState::Healthy);
    assert!(tracker.can_open_new_exposure());
    assert_eq!(
        tracker.order(ClientOrderId::from_raw(1)).unwrap().state(),
        OrderState::Working
    );
}

#[test]
fn not_found_reconciliation() {
    let mut tracker = InMemoryPositionTracker::new();
    let pid = open(&mut tracker);
    submit(&mut tracker, pid, 1, 7);
    tracker
        .apply_event(PositionEvent::Unknown {
            client_order_id: ClientOrderId::from_raw(1),
        })
        .unwrap();
    let (_, recv) = ts();
    let result = tracker
        .reconcile(
            ClientOrderId::from_raw(1),
            empty_snapshot(OrderPresence::NotFound),
            recv,
        )
        .unwrap();
    assert_eq!(result.outcome, ReconcileOutcome::NotFound);
    assert_eq!(tracker.get(pid).unwrap().filled_quantity(), Contracts::ZERO);
    assert_eq!(
        tracker.order(ClientOrderId::from_raw(1)).unwrap().state(),
        OrderState::Rejected
    );
    assert_eq!(tracker.reconciliation_state(), ReconciliationState::Healthy);
}

#[test]
fn ambiguous_reconciliation() {
    let mut tracker = InMemoryPositionTracker::new();
    let pid = open(&mut tracker);
    submit(&mut tracker, pid, 1, 7);
    working(&mut tracker, 1);
    tracker
        .apply_event(PositionEvent::PartialFill {
            fill: entry_fill(pid, 1, 10, 3, usd(2, 40), Money::ZERO),
        })
        .unwrap();
    let mut snap = empty_snapshot(OrderPresence::NotFound);
    snap.authoritative = true;
    let (_, recv) = ts();
    let result = tracker
        .reconcile(ClientOrderId::from_raw(1), snap, recv)
        .unwrap();
    assert_eq!(result.outcome, ReconcileOutcome::Ambiguous);
    assert!(!result.authoritative || result.outcome == ReconcileOutcome::Ambiguous);
    assert_eq!(
        tracker.reconciliation_state(),
        ReconciliationState::Ambiguous
    );
    assert_eq!(
        tracker.get(pid).unwrap().filled_quantity(),
        Contracts::from_u32(3)
    );
}

#[test]
fn duplicate_fill_different_received_at_is_not_ambiguous() {
    let mut tracker = InMemoryPositionTracker::new();
    let pid = open(&mut tracker);
    submit(&mut tracker, pid, 1, 7);
    working(&mut tracker, 1);
    let first = entry_fill(pid, 1, 10, 3, usd(2, 40), Money::ZERO);
    tracker
        .apply_event(PositionEvent::PartialFill {
            fill: first.clone(),
        })
        .unwrap();
    let later = Utc
        .with_ymd_and_hms(2026, 9, 16, 20, 0, 0)
        .single()
        .unwrap();
    let replay = Fill::new(
        first.fill_id(),
        first.position_id(),
        first.client_order_id(),
        first.venue_order_id(),
        first.quantity(),
        first.price(),
        first.premium(),
        first.fee(),
        first.exchange_ts(),
        ReceivedAt::from_utc(later),
    );
    let status = tracker
        .apply_event(PositionEvent::PartialFill { fill: replay })
        .unwrap();
    assert_eq!(status, ApplyStatus::DuplicateIgnored);
    assert_eq!(tracker.reconciliation_state(), ReconciliationState::Healthy);
    assert_eq!(tracker.get(pid).unwrap().fill_history().len(), 1);
}

#[test]
fn same_fill_id_qty_mismatch_on_open_is_ambiguous() {
    let mut tracker = InMemoryPositionTracker::new();
    let pid = open(&mut tracker);
    submit(&mut tracker, pid, 1, 7);
    working(&mut tracker, 1);
    tracker
        .apply_event(PositionEvent::PartialFill {
            fill: entry_fill(pid, 1, 10, 1, usd(0, 80), Money::ZERO),
        })
        .unwrap();
    let err = tracker
        .apply_event(PositionEvent::PartialFill {
            fill: entry_fill(pid, 1, 10, 7, usd(5, 60), Money::ZERO),
        })
        .unwrap_err();
    assert!(matches!(err, TrackerError::ConflictingEvent));
    assert_eq!(
        tracker.reconciliation_state(),
        ReconciliationState::Ambiguous
    );
    assert_eq!(tracker.get(pid).unwrap().filled_quantity().get(), 1);
}

#[test]
fn leftover_fill_on_already_filled_order_is_ignored() {
    let mut tracker = InMemoryPositionTracker::new();
    let pid = open(&mut tracker);
    submit(&mut tracker, pid, 1, 7);
    working(&mut tracker, 1);
    tracker
        .apply_event(PositionEvent::PartialFill {
            fill: entry_fill(pid, 1, 10, 7, usd(5, 60), Money::ZERO),
        })
        .unwrap();
    assert_eq!(tracker.get(pid).unwrap().filled_quantity().get(), 7);
    let leftover = entry_fill(pid, 1, 99, 7, usd(5, 60), Money::ZERO);
    let status = tracker
        .apply_event(PositionEvent::PartialFill { fill: leftover })
        .unwrap();
    assert_eq!(status, ApplyStatus::DuplicateIgnored);
    assert_eq!(tracker.reconciliation_state(), ReconciliationState::Healthy);
    assert_eq!(tracker.get(pid).unwrap().filled_quantity().get(), 7);
    assert_eq!(tracker.get(pid).unwrap().fill_history().len(), 1);
}

#[test]
fn leftover_fill_on_settled_position_is_ignored() {
    let mut tracker = InMemoryPositionTracker::new();
    let pid = open(&mut tracker);
    submit(&mut tracker, pid, 1, 7);
    working(&mut tracker, 1);
    tracker
        .apply_event(PositionEvent::PartialFill {
            fill: entry_fill(pid, 1, 10, 7, usd(5, 60), Money::ZERO),
        })
        .unwrap();
    let (_, recv) = ts();
    tracker
        .apply_settlement(SettlementEvent {
            position_id: pid,
            game_id: GameId::from_raw(10),
            proceeds: usd(7, 0),
            exchange_ts: None,
            received_at: recv,
        })
        .unwrap();
    let leftover = entry_fill(pid, 1, 99, 7, usd(5, 60), Money::ZERO);
    let status = tracker
        .apply_event(PositionEvent::PartialFill { fill: leftover })
        .unwrap();
    assert_eq!(status, ApplyStatus::DuplicateIgnored);
    assert_eq!(tracker.reconciliation_state(), ReconciliationState::Healthy);
    assert_eq!(tracker.get(pid).unwrap().filled_quantity().get(), 7);
}

#[test]
fn overlapping_leftover_fill_does_not_exceed_requested() {
    let mut tracker = InMemoryPositionTracker::new();
    let pid = open(&mut tracker);
    submit(&mut tracker, pid, 1, 7);
    working(&mut tracker, 1);
    tracker
        .apply_event(PositionEvent::PartialFill {
            fill: entry_fill(pid, 1, 10, 5, usd(4, 0), Money::ZERO),
        })
        .unwrap();
    let leftover = entry_fill(pid, 1, 99, 7, usd(5, 60), Money::ZERO);
    let status = tracker
        .apply_event(PositionEvent::PartialFill { fill: leftover })
        .unwrap();
    assert_eq!(status, ApplyStatus::DuplicateIgnored);
    assert_eq!(tracker.reconciliation_state(), ReconciliationState::Healthy);
    assert_eq!(tracker.get(pid).unwrap().filled_quantity().get(), 5);
}

#[test]
fn incremental_fill_still_applies() {
    let mut tracker = InMemoryPositionTracker::new();
    let pid = open(&mut tracker);
    submit(&mut tracker, pid, 1, 7);
    working(&mut tracker, 1);
    tracker
        .apply_event(PositionEvent::PartialFill {
            fill: entry_fill(pid, 1, 10, 3, usd(2, 40), Money::ZERO),
        })
        .unwrap();
    tracker
        .apply_event(PositionEvent::PartialFill {
            fill: entry_fill(pid, 1, 11, 4, usd(3, 20), Money::ZERO),
        })
        .unwrap();
    assert_eq!(tracker.get(pid).unwrap().filled_quantity().get(), 7);
    assert_eq!(tracker.reconciliation_state(), ReconciliationState::Healthy);
}

#[test]
fn settled_fill_qty_mismatch_does_not_block_new_exposure() {
    let mut tracker = InMemoryPositionTracker::new();
    let pid = open(&mut tracker);
    submit(&mut tracker, pid, 1, 7);
    working(&mut tracker, 1);
    tracker
        .apply_event(PositionEvent::PartialFill {
            fill: entry_fill(pid, 1, 10, 1, usd(0, 80), Money::ZERO),
        })
        .unwrap();
    let (_, recv) = ts();
    tracker
        .apply_settlement(SettlementEvent {
            position_id: pid,
            game_id: GameId::from_raw(10),
            proceeds: usd(1, 0),
            exchange_ts: None,
            received_at: recv,
        })
        .unwrap();
    tracker.mark_ambiguous();
    let status = tracker
        .apply_event(PositionEvent::PartialFill {
            fill: entry_fill(pid, 1, 10, 7, usd(5, 60), Money::ZERO),
        })
        .unwrap();
    assert_eq!(status, ApplyStatus::DuplicateIgnored);
    assert_eq!(tracker.get(pid).unwrap().filled_quantity().get(), 1);
    assert!(tracker.non_terminal_known_orders().is_empty());
    assert!(tracker.release_ambiguous_if_no_live_uncertainty());
    assert_eq!(tracker.reconciliation_state(), ReconciliationState::Healthy);
}

#[test]
fn release_ambiguous_refuses_while_unknown_exists() {
    let mut tracker = InMemoryPositionTracker::new();
    let pid = open(&mut tracker);
    submit(&mut tracker, pid, 1, 7);
    tracker
        .apply_event(PositionEvent::Unknown {
            client_order_id: ClientOrderId::from_raw(1),
        })
        .unwrap();
    tracker.mark_ambiguous();
    assert!(!tracker.release_ambiguous_if_no_live_uncertainty());
    assert_eq!(
        tracker.reconciliation_state(),
        ReconciliationState::Ambiguous
    );
    let _ = pid;
}

#[test]
fn duplicate_fill_is_idempotent() {
    let mut tracker = InMemoryPositionTracker::new();
    let pid = open(&mut tracker);
    submit(&mut tracker, pid, 1, 7);
    working(&mut tracker, 1);
    let fill = entry_fill(pid, 1, 10, 3, usd(2, 40), Money::ZERO);
    tracker
        .apply_event(PositionEvent::PartialFill { fill: fill.clone() })
        .unwrap();
    let status = tracker
        .apply_event(PositionEvent::PartialFill { fill })
        .unwrap();
    assert_eq!(status, ApplyStatus::DuplicateIgnored);
    assert_eq!(
        tracker.get(pid).unwrap().actual_exposure().as_money(),
        usd(2, 40)
    );
    assert_eq!(tracker.get(pid).unwrap().fill_history().len(), 1);
}

#[test]
fn duplicate_order_event_is_idempotent() {
    let mut tracker = InMemoryPositionTracker::new();
    let pid = open(&mut tracker);
    submit(&mut tracker, pid, 1, 7);
    let status = tracker
        .apply_event(PositionEvent::OrderSubmitted {
            order: entry_order(pid, 1, 7),
        })
        .unwrap();
    assert_eq!(status, ApplyStatus::DuplicateIgnored);
    assert_eq!(
        tracker.get(pid).unwrap().submitted_quantity(),
        Contracts::from_u32(7)
    );
}

#[test]
fn out_of_order_fill_before_ack() {
    let mut tracker = InMemoryPositionTracker::new();
    let pid = open(&mut tracker);
    submit(&mut tracker, pid, 1, 7);
    tracker
        .apply_event(PositionEvent::PartialFill {
            fill: entry_fill(pid, 1, 10, 3, usd(2, 40), Money::ZERO),
        })
        .unwrap();
    working(&mut tracker, 1);
    let pos = tracker.get(pid).unwrap();
    assert_eq!(pos.filled_quantity(), Contracts::from_u32(3));
    assert_eq!(pos.actual_exposure().as_money(), usd(2, 40));
    assert_eq!(
        tracker
            .order(ClientOrderId::from_raw(1))
            .unwrap()
            .venue_order_id(),
        Some(VenueOrderId::from_raw(1))
    );
}

#[test]
fn fill_after_cancel_request() {
    let mut tracker = InMemoryPositionTracker::new();
    let pid = open(&mut tracker);
    submit(&mut tracker, pid, 1, 7);
    working(&mut tracker, 1);
    tracker
        .apply_event(PositionEvent::CancelRequested {
            client_order_id: ClientOrderId::from_raw(1),
        })
        .unwrap();
    tracker
        .apply_event(PositionEvent::PartialFill {
            fill: entry_fill(pid, 1, 10, 3, usd(2, 40), Money::ZERO),
        })
        .unwrap();
    assert_eq!(
        tracker.get(pid).unwrap().actual_exposure().as_money(),
        usd(2, 40)
    );
}

#[test]
fn timeout_remains_unknown() {
    let mut tracker = InMemoryPositionTracker::new();
    let pid = open(&mut tracker);
    submit(&mut tracker, pid, 1, 7);
    tracker
        .apply_event(PositionEvent::Unknown {
            client_order_id: ClientOrderId::from_raw(1),
        })
        .unwrap();
    let order = tracker.order(ClientOrderId::from_raw(1)).unwrap();
    assert_eq!(order.state(), OrderState::Unknown);
    assert_ne!(order.state(), OrderState::Rejected);
    assert_ne!(order.state(), OrderState::Cancelled);
    assert_ne!(order.state(), OrderState::Filled);
    assert_eq!(tracker.get(pid).unwrap().filled_quantity(), Contracts::ZERO);
}

#[test]
fn reconciliation_can_resolve_unknown() {
    let mut tracker = InMemoryPositionTracker::new();
    let pid = open(&mut tracker);
    submit(&mut tracker, pid, 1, 7);
    tracker
        .apply_event(PositionEvent::Unknown {
            client_order_id: ClientOrderId::from_raw(1),
        })
        .unwrap();
    assert_eq!(
        tracker.reconciliation_state(),
        ReconciliationState::Required
    );
    let mut snap = empty_snapshot(OrderPresence::Found);
    snap.venue_order_id = Some(VenueOrderId::from_raw(7));
    snap.venue_filled = Some(Contracts::ZERO);
    let (_, recv) = ts();
    tracker
        .reconcile(ClientOrderId::from_raw(1), snap, recv)
        .unwrap();
    assert_eq!(tracker.reconciliation_state(), ReconciliationState::Healthy);
    assert_eq!(tracker.get(pid).unwrap().id(), pid);
}

#[test]
fn game_locked_blocks_new_exposure() {
    let mut tracker = InMemoryPositionTracker::new();
    let pid = open(&mut tracker);
    submit(&mut tracker, pid, 1, 7);
    working(&mut tracker, 1);
    tracker
        .apply_event(PositionEvent::PartialFill {
            fill: entry_fill(pid, 1, 10, 3, usd(2, 40), Money::ZERO),
        })
        .unwrap();
    let (ex, recv) = ts();
    tracker
        .apply_event(PositionEvent::GameLocked {
            game_id: GameId::from_raw(10),
            exchange_ts: ex,
            received_at: recv,
        })
        .unwrap();
    let err = tracker
        .apply_event(PositionEvent::OrderSubmitted {
            order: entry_order(pid, 2, 1),
        })
        .unwrap_err();
    assert!(matches!(
        err,
        TrackerError::Position(momento_core::error::PositionError::EntryNotPermitted)
    ));
}

#[test]
fn game_locked_does_not_liquidate() {
    let mut tracker = InMemoryPositionTracker::new();
    let pid = open(&mut tracker);
    submit(&mut tracker, pid, 1, 7);
    working(&mut tracker, 1);
    tracker
        .apply_event(PositionEvent::PartialFill {
            fill: entry_fill(pid, 1, 10, 3, usd(2, 40), Money::ZERO),
        })
        .unwrap();
    let (ex, recv) = ts();
    tracker.lock_game(GameId::from_raw(10), ex, recv).unwrap();
    let pos = tracker.get(pid).unwrap();
    assert_eq!(pos.lifecycle(), PositionLifecycle::OpenPartial);
    assert!(!pos.lifecycle().is_flat());
    assert_ne!(pos.lifecycle(), PositionLifecycle::LiquidationActive);
    assert_eq!(pos.actual_exposure().as_money(), usd(2, 40));
}

#[test]
fn partial_position_plus_game_locked_preserves_position() {
    let mut tracker = InMemoryPositionTracker::new();
    let pid = open(&mut tracker);
    submit(&mut tracker, pid, 1, 7);
    working(&mut tracker, 1);
    tracker
        .apply_event(PositionEvent::PartialFill {
            fill: entry_fill(pid, 1, 10, 3, usd(2, 40), Money::ZERO),
        })
        .unwrap();
    tracker
        .apply_event(PositionEvent::Cancelled {
            client_order_id: ClientOrderId::from_raw(1),
        })
        .unwrap();
    let (ex, recv) = ts();
    tracker.lock_game(GameId::from_raw(10), ex, recv).unwrap();
    let pos = tracker.get(pid).unwrap();
    assert_eq!(pos.id(), pid);
    assert_eq!(pos.actual_exposure().as_money(), usd(2, 40));
    assert_eq!(pos.remaining_economic_target().unwrap(), usd(3, 85));
    assert_eq!(pos.actionable_remaining_entry().unwrap(), Money::ZERO);
    assert!(pos.entry_abandoned());
}

#[test]
fn remaining_target_abandoned_after_lock() {
    let mut tracker = InMemoryPositionTracker::new();
    let pid = open(&mut tracker);
    submit(&mut tracker, pid, 1, 7);
    working(&mut tracker, 1);
    tracker
        .apply_event(PositionEvent::PartialFill {
            fill: entry_fill(pid, 1, 10, 3, usd(2, 40), Money::ZERO),
        })
        .unwrap();
    let (ex, recv) = ts();
    tracker.lock_game(GameId::from_raw(10), ex, recv).unwrap();
    assert_eq!(
        tracker
            .get(pid)
            .unwrap()
            .actionable_remaining_entry()
            .unwrap(),
        Money::ZERO
    );
}

#[test]
fn no_second_position_id() {
    let mut tracker = InMemoryPositionTracker::new();
    let pid = open(&mut tracker);
    let err = tracker
        .register_position_identity(
            StrategyId::from_raw(1),
            GameId::from_raw(10),
            PositionId::from_raw(999),
        )
        .unwrap_err();
    assert!(matches!(
        err,
        TrackerError::SecondPositionForGame {
            attempted,
            existing,
            ..
        } if attempted == PositionId::from_raw(999) && existing == pid
    ));
}

#[test]
fn settlement_cannot_reopen_position() {
    let mut tracker = InMemoryPositionTracker::new();
    let pid = open(&mut tracker);
    submit(&mut tracker, pid, 1, 7);
    working(&mut tracker, 1);
    tracker
        .apply_event(PositionEvent::PartialFill {
            fill: entry_fill(pid, 1, 10, 3, usd(2, 40), Money::ZERO),
        })
        .unwrap();
    let (_, recv) = ts();
    tracker
        .apply_settlement(SettlementEvent {
            position_id: pid,
            game_id: GameId::from_raw(10),
            proceeds: usd(3, 0),
            exchange_ts: None,
            received_at: recv,
        })
        .unwrap();
    assert_eq!(
        tracker.get(pid).unwrap().lifecycle(),
        PositionLifecycle::Settled
    );
    let err = tracker
        .apply_event(PositionEvent::OrderSubmitted {
            order: entry_order(pid, 2, 1),
        })
        .unwrap_err();
    assert!(matches!(err, TrackerError::SettledCannotReopen));
    let err = tracker.apply_entry_fill(entry_fill(pid, 2, 99, 1, usd(0, 80), Money::ZERO));
    assert!(err.is_err());
}

#[test]
fn conflicting_venue_local_state_is_ambiguous() {
    let mut tracker = InMemoryPositionTracker::new();
    let pid = open(&mut tracker);
    submit(&mut tracker, pid, 1, 7);
    working(&mut tracker, 1);
    tracker
        .apply_event(PositionEvent::PartialFill {
            fill: entry_fill(pid, 1, 10, 3, usd(2, 40), Money::ZERO),
        })
        .unwrap();
    let mut snap = empty_snapshot(OrderPresence::Found);
    snap.venue_filled = Some(Contracts::from_u32(5));
    snap.fills = Vec::new();
    snap.contradictory = false;
    snap.insufficient = false;
    let (_, recv) = ts();
    let result = tracker
        .reconcile(ClientOrderId::from_raw(1), snap, recv)
        .unwrap();
    assert_eq!(result.outcome, ReconcileOutcome::Ambiguous);
    assert_eq!(
        tracker.reconciliation_state(),
        ReconciliationState::Ambiguous
    );
}

#[test]
fn no_new_exposure_during_ambiguous() {
    let mut tracker = InMemoryPositionTracker::new();
    let pid = open(&mut tracker);
    submit(&mut tracker, pid, 1, 7);
    working(&mut tracker, 1);
    tracker
        .apply_event(PositionEvent::PartialFill {
            fill: entry_fill(pid, 1, 10, 3, usd(2, 40), Money::ZERO),
        })
        .unwrap();
    let mut snap = empty_snapshot(OrderPresence::Found);
    snap.insufficient = true;
    let (_, recv) = ts();
    tracker
        .reconcile(ClientOrderId::from_raw(1), snap, recv)
        .unwrap();
    let err = tracker
        .apply_event(PositionEvent::OrderSubmitted {
            order: entry_order(pid, 2, 1),
        })
        .unwrap_err();
    assert!(matches!(
        err,
        TrackerError::NewExposureBlocked(ReconciliationState::Ambiguous)
    ));
}

#[test]
fn reconciliation_events_are_auditable() {
    let mut tracker = InMemoryPositionTracker::new();
    let pid = open(&mut tracker);
    submit(&mut tracker, pid, 1, 7);
    tracker
        .apply_event(PositionEvent::Unknown {
            client_order_id: ClientOrderId::from_raw(1),
        })
        .unwrap();
    let mut snap = empty_snapshot(OrderPresence::Found);
    snap.venue_order_id = Some(VenueOrderId::from_raw(3));
    snap.venue_filled = Some(Contracts::ZERO);
    let (_, recv) = ts();
    tracker
        .reconcile(ClientOrderId::from_raw(1), snap, recv)
        .unwrap();
    let events = tracker.audit_events();
    assert!(
        events
            .iter()
            .any(|e| matches!(e, AuditEvent::ReconciliationRequired { .. }))
    );
    assert!(
        events
            .iter()
            .any(|e| matches!(e, AuditEvent::ReconciliationRequested { .. }))
    );
    assert!(
        events
            .iter()
            .any(|e| matches!(e, AuditEvent::ReconciliationStarted { .. }))
    );
    assert!(
        events
            .iter()
            .any(|e| matches!(e, AuditEvent::ReconciliationFound { .. }))
    );
    assert!(
        events
            .iter()
            .any(|e| matches!(e, AuditEvent::ReconciliationCompleted { .. }))
    );
    let _ = pid;
}

#[test]
fn fill_timestamps_are_preserved() {
    let mut tracker = InMemoryPositionTracker::new();
    let pid = open(&mut tracker);
    submit(&mut tracker, pid, 1, 7);
    working(&mut tracker, 1);
    let fill = entry_fill(pid, 1, 10, 3, usd(2, 40), Money::ZERO);
    let ex = fill.exchange_ts();
    let recv = fill.received_at();
    tracker
        .apply_event(PositionEvent::PartialFill { fill })
        .unwrap();
    let stored = &tracker.get(pid).unwrap().fill_history()[0];
    assert_eq!(stored.exchange_ts(), ex);
    assert_eq!(stored.received_at(), recv);
}

#[test]
fn unknown_presence_is_ambiguous_not_not_found() {
    let mut tracker = InMemoryPositionTracker::new();
    let pid = open(&mut tracker);
    submit(&mut tracker, pid, 1, 7);
    tracker
        .apply_event(PositionEvent::Unknown {
            client_order_id: ClientOrderId::from_raw(1),
        })
        .unwrap();
    let mut snap = empty_snapshot(OrderPresence::Unknown);
    snap.authoritative = false;
    let (_, recv) = ts();
    let result = tracker
        .reconcile(ClientOrderId::from_raw(1), snap, recv)
        .unwrap();
    assert_eq!(result.outcome, ReconcileOutcome::Ambiguous);
    assert_eq!(
        tracker.order(ClientOrderId::from_raw(1)).unwrap().state(),
        OrderState::Unknown
    );
    assert_eq!(tracker.get(pid).unwrap().filled_quantity(), Contracts::ZERO);
}

#[test]
fn get_or_create_rebinds_unfilled_position_to_new_weekly_snapshot() {
    let mut tracker = InMemoryPositionTracker::new();
    let old = snapshot();
    let pid = tracker
        .get_or_create(
            StrategyId::from_raw(1),
            GameId::from_raw(10),
            &old,
            Some(MarketId::from_raw(2)),
            Some(Side::Yes),
        )
        .id();
    assert_eq!(tracker.get(pid).unwrap().snapshot_id(), old.snapshot_id());
    let new = snapshot();
    assert_ne!(old.snapshot_id(), new.snapshot_id());
    tracker.get_or_create(
        StrategyId::from_raw(1),
        GameId::from_raw(10),
        &new,
        Some(MarketId::from_raw(2)),
        Some(Side::Yes),
    );
    assert_eq!(tracker.get(pid).unwrap().snapshot_id(), new.snapshot_id());
}

#[test]
fn get_or_create_does_not_rebind_filled_position() {
    let mut tracker = InMemoryPositionTracker::new();
    let old = snapshot();
    let pid = tracker
        .get_or_create(
            StrategyId::from_raw(1),
            GameId::from_raw(10),
            &old,
            Some(MarketId::from_raw(2)),
            Some(Side::Yes),
        )
        .id();
    submit(&mut tracker, pid, 1, 7);
    working(&mut tracker, 1);
    tracker
        .apply_event(PositionEvent::PartialFill {
            fill: entry_fill(pid, 1, 10, 3, usd(2, 40), Money::ZERO),
        })
        .unwrap();
    let new = snapshot();
    tracker.get_or_create(
        StrategyId::from_raw(1),
        GameId::from_raw(10),
        &new,
        Some(MarketId::from_raw(2)),
        Some(Side::Yes),
    );
    assert_eq!(tracker.get(pid).unwrap().snapshot_id(), old.snapshot_id());
}

#[test]
fn get_or_create_does_not_rebind_unknown_entry() {
    let mut tracker = InMemoryPositionTracker::new();
    let old = snapshot();
    let pid = tracker
        .get_or_create(
            StrategyId::from_raw(1),
            GameId::from_raw(10),
            &old,
            Some(MarketId::from_raw(2)),
            Some(Side::Yes),
        )
        .id();
    submit(&mut tracker, pid, 1, 7);
    tracker
        .apply_event(PositionEvent::Unknown {
            client_order_id: ClientOrderId::from_raw(1),
        })
        .unwrap();
    let new = snapshot();
    tracker.get_or_create(
        StrategyId::from_raw(1),
        GameId::from_raw(10),
        &new,
        Some(MarketId::from_raw(2)),
        Some(Side::Yes),
    );
    assert_eq!(tracker.get(pid).unwrap().snapshot_id(), old.snapshot_id());
}

#[test]
fn bulk_rebind_skips_working_entry_and_updates_idle() {
    let mut tracker = InMemoryPositionTracker::new();
    let old = snapshot();
    let idle = tracker
        .get_or_create(
            StrategyId::from_raw(1),
            GameId::from_raw(10),
            &old,
            Some(MarketId::from_raw(2)),
            Some(Side::Yes),
        )
        .id();
    let working_pid = tracker
        .get_or_create(
            StrategyId::from_raw(1),
            GameId::from_raw(11),
            &old,
            Some(MarketId::from_raw(3)),
            Some(Side::Yes),
        )
        .id();
    tracker
        .get_mut(working_pid)
        .unwrap()
        .record_submission(Contracts::from_u32(7))
        .unwrap();
    let new = snapshot();
    let rebound = tracker.rebind_unfilled_positions_to_snapshot(&new, |_| usd(6, 25));
    assert_eq!(rebound, vec![idle]);
    assert_eq!(tracker.get(idle).unwrap().snapshot_id(), new.snapshot_id());
    assert_eq!(
        tracker.get(working_pid).unwrap().snapshot_id(),
        old.snapshot_id()
    );
}
