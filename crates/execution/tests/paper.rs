use chrono::{TimeZone, Utc};
use momento_core::{
    AdditionalExposure, ApprovedTradeIntent, Bps, BuildPositionIntent, ClientOrderId, Contracts,
    EntryStyle, GameId, LiquidationIntent, LiquidationReason, LiquidationStyle, MarketId, Money,
    OrderState, Position, PositionId, Price, ReconcileOutcome, ReconciliationState, RiskDecisionId,
    RiskGrant, Side, SnapshotSource, StrategyId, TradeIntent, WeeklyBankrollSnapshot,
};
use momento_execution::{ExecutionEngine, PaperExecution};

fn usd(d: i64, c: u8) -> Money {
    Money::from_usd(d, c).unwrap()
}

fn approved() -> (WeeklyBankrollSnapshot, Position, ApprovedTradeIntent) {
    let now = Utc
        .with_ymd_and_hms(2026, 8, 24, 16, 0, 0)
        .single()
        .unwrap();
    let snap =
        WeeklyBankrollSnapshot::capture(usd(50, 0), Bps::PCT_12_5, now, SnapshotSource::Test)
            .unwrap();
    let pos = Position::new_for_game(
        PositionId::from_raw(1),
        GameId::from_raw(10),
        StrategyId::from_raw(1),
        snap.snapshot_id(),
        snap.max_position_budget(),
        Some(MarketId::from_raw(2)),
        Some(Side::Yes),
    );
    let intent = TradeIntent::build(BuildPositionIntent {
        strategy_id: StrategyId::from_raw(1),
        game_id: pos.game_id(),
        market_id: MarketId::from_raw(2),
        side: Side::Yes,
        position_id: pos.id(),
        limit_price: Price::from_cents(80).unwrap(),
        style: EntryStyle::MakerOnly,
        additional: AdditionalExposure::RemainderOfApprovedBudget,
    });
    let approved = ApprovedTradeIntent::from_risk_approval(
        RiskGrant::for_risk_engine(),
        RiskDecisionId::generate(),
        snap.snapshot_id(),
        &intent,
        ClientOrderId::from_raw(11),
        Contracts::from_u32(7),
        usd(5, 60),
        snap.max_position_budget(),
    );
    (snap, pos, approved)
}

#[test]
fn paper_partial_fill_and_cancel() {
    let (_snap, _pos, intent) = approved();
    let mut paper = PaperExecution::new();
    let id = paper.submit_entry(intent).unwrap();
    paper.simulate_ack(id).unwrap();
    paper
        .simulate_partial_fill(
            id,
            Contracts::from_u32(3),
            Price::from_cents(80).unwrap(),
            usd(2, 40),
            momento_core::Fee::zero(momento_core::FeeKind::Entry),
            |_| {},
        )
        .unwrap();
    let order = paper.order(id).unwrap();
    assert_eq!(order.state(), OrderState::PartiallyFilled);
    assert_eq!(order.quantities().filled, Contracts::from_u32(3));
    assert_eq!(order.quantities().requested, Contracts::from_u32(7));
    paper.simulate_cancel(id).unwrap();
    assert_eq!(paper.order(id).unwrap().state(), OrderState::Cancelled);
}

#[test]
fn unknown_order_requires_reconciliation_not_failed() {
    let (_snap, _pos, intent) = approved();
    let mut paper = PaperExecution::new();
    let id = paper.submit_entry(intent).unwrap();
    paper.simulate_unknown(id).unwrap();
    assert_eq!(paper.order(id).unwrap().state(), OrderState::Unknown);
    assert!(paper.order(id).unwrap().state().requires_reconciliation());
    assert_eq!(paper.recon_state(), ReconciliationState::Required);
    assert!(paper.simulate_ack(id).is_err());
    paper.reconcile(id, ReconcileOutcome::Found).unwrap();
    assert_eq!(paper.recon_state(), ReconciliationState::Healthy);
}

#[test]
fn paper_liquidation_is_separate_order_purpose() {
    let (_snap, pos, _intent) = approved();
    let mut paper = PaperExecution::new();
    let liq = LiquidationIntent {
        position_id: pos.id(),
        game_id: pos.game_id(),
        market_id: pos.market_id().expect("paper fixture has MarketId"),
        side: pos.side().expect("paper fixture has side"),
        client_order_id: ClientOrderId::from_raw(99),
        reason: LiquidationReason::StopLoss,
        style: LiquidationStyle::AggressiveReduce,
    };
    let id = paper
        .submit_liquidation(liq, Contracts::from_u32(3), Price::from_cents(40).unwrap())
        .unwrap();
    assert_eq!(
        paper.purpose(id),
        Some(momento_core::OrderPurpose::Liquidation)
    );
}

#[test]
fn delayed_ack_then_full_fill() {
    let (_snap, _pos, intent) = approved();
    let mut paper = PaperExecution::new();
    let id = paper.submit_entry(intent).unwrap();
    assert_eq!(paper.order(id).unwrap().state(), OrderState::New);
    paper.simulate_ack(id).unwrap();
    paper
        .simulate_partial_fill(
            id,
            Contracts::from_u32(7),
            Price::from_cents(80).unwrap(),
            usd(5, 60),
            momento_core::Fee::zero(momento_core::FeeKind::Entry),
            |_| {},
        )
        .unwrap();
    assert_eq!(paper.order(id).unwrap().state(), OrderState::Filled);
}

#[test]
fn replace_on_unknown_is_blocked() {
    let (_snap, _pos, intent) = approved();
    let mut paper = PaperExecution::new();
    let id = paper.submit_entry(intent).unwrap();
    paper.simulate_unknown(id).unwrap();
    assert!(paper.simulate_replace(id, Contracts::from_u32(1)).is_err());
}

#[test]
fn venue_order_id_assigned_on_ack() {
    let (_snap, _pos, intent) = approved();
    let mut paper = PaperExecution::new();
    let id = paper.submit_entry(intent).unwrap();
    let venue = paper.simulate_ack(id).unwrap();
    assert_eq!(paper.order(id).unwrap().venue_order_id(), Some(venue));
}
