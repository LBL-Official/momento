//! Milestone 1 mandatory invariants (core domain).

use chrono::{TimeZone, Utc};
use momento_core::arithmetic::contract_premium;
use momento_core::fee::{Fee, FeeKind};
use momento_core::{
    ClientOrderId, Contracts, ExchangeTimestamp, Fill, FillId, GameId, MarketId, Money, Position,
    PositionExitCause, PositionId, PositionLifecycle, Price, ReceivedAt, SnapshotId, StrategyId,
    VenueOrderId,
};

fn usd(dollars: i64, cents: u8) -> Money {
    Money::from_usd(dollars, cents).expect("usd")
}

fn px(cents: u16) -> Price {
    Price::from_cents(cents).expect("price")
}

fn now_ts() -> (ExchangeTimestamp, ReceivedAt) {
    let t = Utc
        .with_ymd_and_hms(2026, 8, 24, 18, 0, 0)
        .single()
        .unwrap();
    (ExchangeTimestamp::from_utc(t), ReceivedAt::from_utc(t))
}

fn position() -> Position {
    Position::new_for_game(
        PositionId::from_raw(1),
        GameId::from_raw(10),
        StrategyId::from_raw(1),
        SnapshotId::from_raw(7),
        usd(6, 25),
        Some(MarketId::from_raw(2)),
        None,
    )
}

fn entry_fill(
    position_id: PositionId,
    order: u128,
    qty: u32,
    price: Price,
    premium: Money,
) -> Fill {
    let (ex, recv) = now_ts();
    Fill::new(
        FillId::generate(),
        position_id,
        ClientOrderId::from_raw(order),
        Some(VenueOrderId::from_raw(order)),
        Contracts::from_u32(qty),
        price,
        premium,
        Fee::zero(FeeKind::Entry),
        ex,
        recv,
    )
}

#[test]
fn partial_fill_does_not_complete_position() {
    let mut pos = position();
    let premium = contract_premium(Contracts::from_u32(3), px(80)).unwrap();
    assert_eq!(premium, usd(2, 40));
    pos.apply_entry_fill(entry_fill(pos.id(), 1, 3, px(80), premium))
        .unwrap();

    assert_eq!(pos.approved_economic_budget(), usd(6, 25));
    assert_eq!(pos.actual_exposure().as_money(), usd(2, 40));
    assert_eq!(pos.remaining_economic_target().unwrap(), usd(3, 85));
    assert_eq!(pos.lifecycle(), PositionLifecycle::OpenPartial);
    assert!(!pos.lifecycle().is_complete_open());
}

#[test]
fn subsequent_fills_accumulate_same_position() {
    let mut pos = position();
    let id = pos.id();
    pos.apply_entry_fill(entry_fill(id, 1, 3, px(80), usd(2, 40)))
        .unwrap();
    pos.apply_entry_fill(entry_fill(id, 2, 1, px(80), usd(1, 0)))
        .unwrap();
    pos.apply_entry_fill(entry_fill(id, 3, 1, px(80), usd(1, 25)))
        .unwrap();

    assert_eq!(pos.id(), id);
    assert_eq!(pos.fill_history().len(), 3);
    assert_eq!(pos.actual_exposure().as_money(), usd(4, 65));
    assert_eq!(pos.remaining_economic_target().unwrap(), usd(1, 60));
    assert_eq!(pos.lifecycle(), PositionLifecycle::OpenPartial);
}

#[test]
fn submitted_quantity_is_not_filled_quantity() {
    let mut pos = position();
    pos.record_submission(Contracts::from_u32(7)).unwrap();
    assert_eq!(pos.submitted_quantity(), Contracts::from_u32(7));
    assert_eq!(pos.filled_quantity(), Contracts::ZERO);
    assert_eq!(pos.remaining_economic_target().unwrap(), usd(6, 25));
}

#[test]
fn remaining_target_uses_actual_fills_not_submitted() {
    let mut pos = position();
    pos.record_submission(Contracts::from_u32(7)).unwrap();
    pos.apply_entry_fill(entry_fill(pos.id(), 1, 3, px(80), usd(2, 40)))
        .unwrap();
    assert_eq!(pos.submitted_quantity(), Contracts::from_u32(7));
    assert_eq!(pos.remaining_economic_target().unwrap(), usd(3, 85));
}

#[test]
fn cumulative_exposure_cannot_exceed_budget() {
    let mut pos = position();
    pos.apply_entry_fill(entry_fill(pos.id(), 1, 3, px(80), usd(2, 40)))
        .unwrap();
    let err = pos
        .apply_entry_fill(entry_fill(pos.id(), 2, 5, px(80), usd(4, 0)))
        .unwrap_err();
    assert!(matches!(
        err,
        momento_core::error::PositionError::BudgetExceeded { .. }
    ));
    assert_eq!(pos.actual_exposure().as_money(), usd(2, 40));
}

#[test]
fn game_locked_is_permanent_and_does_not_flatten() {
    let mut pos = position();
    pos.apply_entry_fill(entry_fill(pos.id(), 1, 3, px(80), usd(2, 40)))
        .unwrap();
    let (ex, recv) = now_ts();
    pos.apply_game_lock(ex, recv);
    pos.apply_game_lock(ex, recv);

    assert!(pos.game_lock().is_locked());
    assert!(!pos.can_attempt_entry());
    assert_eq!(pos.actionable_remaining_entry().unwrap(), Money::ZERO);
    assert_eq!(pos.actual_exposure().as_money(), usd(2, 40));
    assert_eq!(pos.lifecycle(), PositionLifecycle::OpenPartial);
    assert!(!pos.lifecycle().is_flat());
}

#[test]
fn pause_above_83_may_resume_if_unlocked() {
    let mut pos = position();
    pos.pause_entry_above_max_price();
    assert!(!pos.can_attempt_entry());
    pos.resume_entry_if_unlocked();
    assert!(pos.can_attempt_entry());
}

#[test]
fn after_game_locked_cannot_resume_entry() {
    let mut pos = position();
    let (ex, recv) = now_ts();
    pos.apply_game_lock(ex, recv);
    pos.resume_entry_if_unlocked();
    assert!(pos.game_lock().is_locked());
    assert!(!pos.can_attempt_entry());
}

#[test]
fn stop_triggered_is_not_flat() {
    let mut pos = position();
    pos.apply_entry_fill(entry_fill(pos.id(), 1, 3, px(80), usd(2, 40)))
        .unwrap();
    pos.trigger_stop();
    assert_eq!(pos.lifecycle(), PositionLifecycle::StopTriggered);
    assert!(!pos.lifecycle().is_flat());
}

#[test]
fn liquidation_active_is_not_flat_until_fills_confirm() {
    let mut pos = position();
    pos.apply_entry_fill(entry_fill(pos.id(), 1, 3, px(80), usd(2, 40)))
        .unwrap();
    pos.trigger_stop();
    pos.begin_liquidation();
    assert_eq!(pos.lifecycle(), PositionLifecycle::LiquidationActive);
    assert!(!pos.lifecycle().is_flat());

    let (ex, recv) = now_ts();
    let liq = Fill::new(
        FillId::generate(),
        pos.id(),
        ClientOrderId::from_raw(9),
        None,
        Contracts::from_u32(1),
        px(40),
        usd(0, 40),
        Fee::new(usd(0, 2), FeeKind::Liquidation),
        ex,
        recv,
    );
    pos.apply_liquidation_fill(liq).unwrap();
    assert_eq!(pos.lifecycle(), PositionLifecycle::LiquidationActive);
    assert_eq!(pos.liquidation_fees(), usd(0, 2));
    assert_eq!(pos.entry_fees(), Money::ZERO);
}

#[test]
fn exit_causes_are_only_stop_and_settlement() {
    fn classify(cause: PositionExitCause) -> &'static str {
        match cause {
            PositionExitCause::StopLoss => "stop",
            PositionExitCause::Settlement => "settlement",
        }
    }
    assert_eq!(classify(PositionExitCause::StopLoss), "stop");
    assert_eq!(classify(PositionExitCause::Settlement), "settlement");
}

#[test]
fn liquidation_fees_are_separate_from_entry_fees() {
    let mut pos = position();
    let (ex, recv) = now_ts();
    let entry = Fill::new(
        FillId::generate(),
        pos.id(),
        ClientOrderId::from_raw(1),
        None,
        Contracts::from_u32(3),
        px(80),
        usd(2, 40),
        Fee::new(usd(0, 5), FeeKind::Entry),
        ex,
        recv,
    );
    pos.apply_entry_fill(entry).unwrap();
    assert_eq!(pos.entry_fees(), usd(0, 5));
    assert_eq!(pos.liquidation_fees(), Money::ZERO);
    assert_eq!(pos.remaining_economic_target().unwrap(), usd(3, 80));
}
