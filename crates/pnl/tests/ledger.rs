use chrono::{TimeZone, Utc};
use momento_core::{
    ClientOrderId, Contracts, ExchangeTimestamp, Fee, FeeKind, Fill, FillId, GameId, Money,
    Position, PositionId, PositionLifecycle, Price, ReceivedAt, SnapshotId, StrategyId,
};
use momento_pnl::{PnlBreakdown, UnrealizedPnl};

fn usd(d: i64, c: u8) -> Money {
    Money::from_usd(d, c).unwrap()
}

fn ts() -> (ExchangeTimestamp, ReceivedAt) {
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
        None,
        None,
    )
}

fn fill(kind: FeeKind, premium: Money, fee: Money, qty: u32, raw: u128) -> Fill {
    let (ex, recv) = ts();
    Fill::new(
        FillId::from_raw(raw),
        PositionId::from_raw(1),
        ClientOrderId::from_raw(raw),
        None,
        Contracts::from_u32(qty),
        Price::from_cents(80).unwrap(),
        premium,
        Fee::new(fee, kind),
        ex,
        recv,
    )
}

#[test]
fn pnl_ledger_separates_fees() {
    let mut pos = position();
    pos.apply_entry_fill(fill(FeeKind::Entry, usd(2, 40), usd(0, 5), 3, 1))
        .unwrap();
    pos.apply_liquidation_fill(fill(FeeKind::Liquidation, usd(1, 20), usd(0, 2), 1, 2))
        .unwrap();
    let ledger = PnlBreakdown::from_position(&pos);
    assert_eq!(ledger.entry_cost, usd(2, 40));
    assert_eq!(ledger.entry_fees, usd(0, 5));
    assert_eq!(ledger.liquidation_proceeds, usd(1, 20));
    assert_eq!(ledger.liquidation_fees, usd(0, 2));
    assert_eq!(ledger.total_fees, usd(0, 7));
    assert_eq!(ledger.settlement_proceeds, None);
    assert_eq!(ledger.realized_pnl, None);
    assert_eq!(ledger.unrealized_pnl, None);
}

#[test]
fn liquidation_proceeds_are_not_entry_capacity() {
    let mut pos = position();
    pos.apply_entry_fill(fill(FeeKind::Entry, usd(2, 40), Money::ZERO, 3, 1))
        .unwrap();
    let remaining_before = pos.remaining_economic_target().unwrap();
    pos.apply_liquidation_fill(fill(FeeKind::Liquidation, usd(1, 20), Money::ZERO, 1, 2))
        .unwrap();
    assert_eq!(pos.remaining_economic_target().unwrap(), remaining_before);
    let ledger = PnlBreakdown::from_position(&pos);
    assert_eq!(ledger.liquidation_proceeds, usd(1, 20));
    assert_eq!(ledger.entry_cost, usd(2, 40));
}

#[test]
fn settlement_finalizes_realized_from_supplied_proceeds() {
    let mut pos = position();
    pos.apply_entry_fill(fill(FeeKind::Entry, usd(2, 40), usd(0, 5), 3, 1))
        .unwrap();
    pos.apply_settlement(usd(3, 0)).unwrap();
    let ledger = PnlBreakdown::from_position(&pos);
    assert_eq!(ledger.settlement_proceeds, Some(usd(3, 0)));
    let realized = ledger.realized_pnl.expect("settlement realizes pnl");
    assert_eq!(realized.as_money(), usd(0, 55));
    assert_eq!(pos.lifecycle(), PositionLifecycle::Settled);
}

#[test]
fn unverified_mark_does_not_invent_unrealized() {
    let pos = position();
    let ledger = PnlBreakdown::from_position(&pos);
    assert_eq!(
        ledger.unrealized_with_unverified_mark(Price::from_cents(90).unwrap()),
        None::<UnrealizedPnl>
    );
}

#[test]
fn zero_fee_placeholder_is_not_profit_proof() {
    let mut pos = position();
    pos.apply_entry_fill(fill(FeeKind::Entry, usd(2, 40), Money::ZERO, 3, 1))
        .unwrap();
    let ledger = PnlBreakdown::from_position(&pos);
    assert_eq!(ledger.entry_fees, Money::ZERO);
    assert_eq!(ledger.realized_pnl, None);
}
