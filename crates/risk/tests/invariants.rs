use chrono::{TimeZone, Utc};
use momento_core::{
    AdditionalExposure, Bps, BuildPositionIntent, EntryStyle, GameId, MarketId, Money, Position,
    PositionId, Price, RiskDecision, RiskRejectReason, Side, SnapshotSource, StrategyId,
    TradeIntent, WeeklyBankrollSnapshot,
};
use momento_core::{KillSwitch, ReconciliationState};
use momento_risk::{InvariantRisk, RiskEngine, would_exceed_original_budget};

fn usd(d: i64, c: u8) -> Money {
    Money::from_usd(d, c).unwrap()
}

fn snapshot() -> WeeklyBankrollSnapshot {
    let now = Utc
        .with_ymd_and_hms(2026, 8, 24, 16, 0, 0)
        .single()
        .unwrap();
    WeeklyBankrollSnapshot::capture(usd(50, 0), Bps::PCT_12_5, now, SnapshotSource::Test).unwrap()
}

fn position_for(snapshot: &WeeklyBankrollSnapshot) -> Position {
    Position::new_for_game(
        PositionId::from_raw(1),
        GameId::from_raw(10),
        StrategyId::from_raw(1),
        snapshot.snapshot_id(),
        snapshot.max_position_budget(),
        Some(MarketId::from_raw(2)),
        Some(Side::Yes),
    )
}

fn intent(price: Price, position: &Position) -> TradeIntent {
    TradeIntent::build(BuildPositionIntent {
        strategy_id: StrategyId::from_raw(1),
        game_id: position.game_id(),
        market_id: MarketId::from_raw(2),
        side: Side::Yes,
        position_id: position.id(),
        limit_price: price,
        style: EntryStyle::MakerOnly,
        additional: AdditionalExposure::RemainderOfApprovedBudget,
    })
}

#[test]
fn entry_price_above_83_is_rejected() {
    let snap = snapshot();
    let pos = position_for(&snap);
    let risk = InvariantRisk::new(Price::from_cents(83).unwrap());
    let decision = risk.evaluate_entry(
        &intent(Price::from_cents(84).unwrap(), &pos),
        &pos,
        &snap,
        ReconciliationState::Healthy,
        KillSwitch::Armed,
    );
    match decision {
        RiskDecision::Rejected {
            reason: RiskRejectReason::InvalidPrice,
            snapshot_id,
            ..
        } => assert_eq!(snapshot_id, snap.snapshot_id()),
        other => panic!("expected invalid price, got {other:?}"),
    }
}

#[test]
fn risk_approval_is_tied_to_weekly_snapshot() {
    let snap = snapshot();
    let other = snapshot();
    let pos = position_for(&snap);
    let risk = InvariantRisk::new(Price::from_cents(83).unwrap());
    let decision = risk.evaluate_entry(
        &intent(Price::from_cents(80).unwrap(), &pos),
        &pos,
        &other,
        ReconciliationState::Healthy,
        KillSwitch::Armed,
    );
    assert!(matches!(
        decision,
        RiskDecision::Rejected {
            reason: RiskRejectReason::SnapshotMismatch,
            ..
        }
    ));
}

#[test]
fn approval_references_snapshot_on_success() {
    let snap = snapshot();
    let pos = position_for(&snap);
    let risk = InvariantRisk::new(Price::from_cents(83).unwrap());
    match risk.evaluate_entry(
        &intent(Price::from_cents(80).unwrap(), &pos),
        &pos,
        &snap,
        ReconciliationState::Healthy,
        KillSwitch::Armed,
    ) {
        RiskDecision::Approved(a) => {
            assert_eq!(a.snapshot_id(), snap.snapshot_id());
            assert_eq!(a.original_budget(), usd(6, 25));
        }
        other => panic!("expected approval {other:?}"),
    }
}

#[test]
fn incremental_orders_cannot_bypass_original_budget() {
    let snap = snapshot();
    let mut pos = position_for(&snap);
    let fill_premium = usd(2, 40);
    let (ex, recv) = {
        let t = Utc
            .with_ymd_and_hms(2026, 8, 24, 18, 0, 0)
            .single()
            .unwrap();
        (
            momento_core::ExchangeTimestamp::from_utc(t),
            momento_core::ReceivedAt::from_utc(t),
        )
    };
    pos.apply_entry_fill(momento_core::Fill::new(
        momento_core::FillId::generate(),
        pos.id(),
        momento_core::ClientOrderId::from_raw(1),
        None,
        momento_core::Contracts::from_u32(3),
        Price::from_cents(80).unwrap(),
        fill_premium,
        momento_core::Fee::zero(momento_core::FeeKind::Entry),
        ex,
        recv,
    ))
    .unwrap();

    assert!(would_exceed_original_budget(
        &pos,
        usd(4, 0),
        Money::ZERO,
        snap.max_position_budget(),
        snap.snapshot_id(),
    ));
    assert!(!would_exceed_original_budget(
        &pos,
        usd(3, 85),
        Money::ZERO,
        snap.max_position_budget(),
        snap.snapshot_id(),
    ));
}

#[test]
fn game_locked_rejects_entry() {
    let snap = snapshot();
    let mut pos = position_for(&snap);
    let t = Utc
        .with_ymd_and_hms(2026, 8, 24, 18, 0, 0)
        .single()
        .unwrap();
    pos.apply_game_lock(
        momento_core::ExchangeTimestamp::from_utc(t),
        momento_core::ReceivedAt::from_utc(t),
    );
    let risk = InvariantRisk::new(Price::from_cents(83).unwrap());
    assert!(matches!(
        risk.evaluate_entry(
            &intent(Price::from_cents(80).unwrap(), &pos),
            &pos,
            &snap,
            ReconciliationState::Healthy,
            KillSwitch::Armed,
        ),
        RiskDecision::Rejected {
            reason: RiskRejectReason::GameLocked,
            ..
        }
    ));
}
