//! Five-open-position cap. Risk is the authority. Strategy cannot bypass it.

use std::sync::Arc;
use std::thread;

use chrono::{TimeZone, Utc};
use momento_core::{
    AdditionalExposure, BuildPositionIntent, ClientOrderId, Contracts, EntryStyle, Fee, FeeKind,
    Fill, FillId, GameId, MarketId, Money, Position, PositionId, PositionLifecycle, Price,
    ReconcileOutcome, RiskDecision, RiskRejectReason, Side, SnapshotSource, StrategyId,
    TradeIntent, WeeklyBankrollSnapshot,
};
use momento_risk::{PaperRiskEngine, RiskConfig};

fn usd(d: i64, c: u8) -> Money {
    Money::from_usd(d, c).unwrap()
}

fn px(c: u16) -> Price {
    Price::from_cents(c).unwrap()
}

fn snapshot50() -> WeeklyBankrollSnapshot {
    let now = Utc
        .with_ymd_and_hms(2026, 8, 24, 16, 0, 0)
        .single()
        .unwrap();
    WeeklyBankrollSnapshot::capture(
        usd(50, 0),
        momento_core::Bps::PCT_12_5,
        now,
        SnapshotSource::Test,
    )
    .unwrap()
}

fn engine(snapshot: WeeklyBankrollSnapshot) -> PaperRiskEngine {
    PaperRiskEngine::paper(snapshot, RiskConfig::mlb_paper_experimental().unwrap())
}

fn position(snapshot: &WeeklyBankrollSnapshot, n: u128) -> Position {
    Position::new_for_game(
        PositionId::from_raw(n),
        GameId::from_raw(100 + n),
        StrategyId::from_raw(1),
        snapshot.snapshot_id(),
        snapshot.max_position_budget(),
        Some(MarketId::from_raw(2)),
        Some(Side::Yes),
    )
}

fn remainder(pos: &Position) -> TradeIntent {
    TradeIntent::build(BuildPositionIntent {
        strategy_id: StrategyId::from_raw(1),
        game_id: pos.game_id(),
        market_id: MarketId::from_raw(2),
        side: Side::Yes,
        position_id: pos.id(),
        limit_price: px(80),
        style: EntryStyle::MakerOnly,
        additional: AdditionalExposure::RemainderOfApprovedBudget,
    })
}

fn ts() -> (momento_core::ExchangeTimestamp, momento_core::ReceivedAt) {
    let t = Utc
        .with_ymd_and_hms(2026, 8, 24, 18, 0, 0)
        .single()
        .unwrap();
    (
        momento_core::ExchangeTimestamp::from_utc(t),
        momento_core::ReceivedAt::from_utc(t),
    )
}

fn approved(d: RiskDecision) -> momento_core::ApprovedTradeIntent {
    match d {
        RiskDecision::Approved(a) => a,
        other => panic!("expected approval, got {other:?}"),
    }
}

fn rejected_reason(d: &RiskDecision) -> RiskRejectReason {
    match d {
        RiskDecision::Rejected { reason, .. } => *reason,
        RiskDecision::Approved(_) => panic!("expected rejection"),
    }
}

fn apply_entry_fill(pos: &mut Position, order: ClientOrderId, qty: u32, premium: Money) {
    let (ex, recv) = ts();
    pos.apply_entry_fill(Fill::new(
        FillId::generate(),
        pos.id(),
        order,
        None,
        Contracts::from_u32(qty),
        px(80),
        premium,
        Fee::zero(FeeKind::Entry),
        ex,
        recv,
    ))
    .unwrap();
}

fn apply_liquidation_fill(pos: &mut Position, qty: u32) {
    let (ex, recv) = ts();
    pos.apply_liquidation_fill(Fill::new(
        FillId::generate(),
        pos.id(),
        ClientOrderId::generate(),
        None,
        Contracts::from_u32(qty),
        px(80),
        Money::from_cents(i64::from(qty) * 80),
        Fee::zero(FeeKind::Liquidation),
        ex,
        recv,
    ))
    .unwrap();
}

fn open_partial(e: &PaperRiskEngine, snap: &WeeklyBankrollSnapshot, n: u128) -> Position {
    let mut pos = position(snap, n);
    let a = approved(e.decide_entry(&remainder(&pos), &pos));
    apply_entry_fill(&mut pos, a.client_order_id(), 3, usd(2, 40));
    e.on_fill(pos.fill_history().last().unwrap());
    e.on_cancel(a.client_order_id());
    pos
}

fn assert_cap_rejected(d: RiskDecision) {
    assert_eq!(rejected_reason(&d), RiskRejectReason::PositionLimitExceeded);
}

#[test]
fn confirmed_cap_is_five() {
    let snap = snapshot50();
    let e = engine(snap);
    assert_eq!(e.max_open_positions(), 5);
    assert_eq!(e.open_slot_count(), 0);
}

#[test]
fn positions_one_through_five_can_be_approved() {
    let snap = snapshot50();
    let e = engine(snap.clone());
    for n in 1..=5 {
        let pos = open_partial(&e, &snap, n);
        assert_eq!(pos.id(), PositionId::from_raw(n));
        assert!(pos.filled_quantity().get() > 0);
        assert_eq!(e.open_slot_count(), n as u32);
    }
    assert_eq!(snap.bankroll(), usd(50, 0));
    assert_eq!(snap.max_position_budget(), usd(6, 25));
}

#[test]
fn position_six_is_rejected() {
    let snap = snapshot50();
    let e = engine(snap.clone());
    for n in 1..=5 {
        let _ = open_partial(&e, &snap, n);
    }
    let sixth = position(&snap, 6);
    assert_cap_rejected(e.decide_entry(&remainder(&sixth), &sixth));
    assert_eq!(e.open_slot_count(), 5);
}

#[test]
fn partial_fill_positions_count_toward_the_five() {
    let snap = snapshot50();
    let e = engine(snap.clone());
    for n in 1..=5 {
        let pos = open_partial(&e, &snap, n);
        assert_eq!(pos.lifecycle(), PositionLifecycle::OpenPartial);
        assert_eq!(pos.filled_quantity().get(), 3);
    }
    let sixth = position(&snap, 6);
    assert_cap_rejected(e.decide_entry(&remainder(&sixth), &sixth));
}

#[test]
fn game_locked_positions_still_count() {
    let snap = snapshot50();
    let e = engine(snap.clone());
    let mut locked = open_partial(&e, &snap, 1);
    let (ex, recv) = ts();
    locked.apply_game_lock(ex, recv);
    e.lock_game(locked.game_id());
    assert!(locked.game_lock().is_locked());
    assert!(locked.filled_quantity().get() > 0);
    for n in 2..=5 {
        let _ = open_partial(&e, &snap, n);
    }
    assert_eq!(e.open_slot_count(), 5);
    let sixth = position(&snap, 6);
    assert_cap_rejected(e.decide_entry(&remainder(&sixth), &sixth));
    assert_eq!(
        rejected_reason(&e.decide_entry(&remainder(&locked), &locked)),
        RiskRejectReason::GameLocked
    );
}

#[test]
fn flat_positions_free_a_slot() {
    let snap = snapshot50();
    let e = engine(snap.clone());
    let mut first = open_partial(&e, &snap, 1);
    for n in 2..=5 {
        let _ = open_partial(&e, &snap, n);
    }
    assert_eq!(e.open_slot_count(), 5);
    let qty = first.filled_quantity().get();
    apply_liquidation_fill(&mut first, qty);
    e.on_fill(first.fill_history().last().unwrap());
    assert_eq!(first.lifecycle(), PositionLifecycle::Flat);
    assert_eq!(first.filled_quantity().get(), 0);
    assert_eq!(e.open_slot_count(), 4);
    let replacement = position(&snap, 6);
    approved(e.decide_entry(&remainder(&replacement), &replacement));
    assert_eq!(e.open_slot_count(), 5);
    let seventh = position(&snap, 7);
    assert_cap_rejected(e.decide_entry(&remainder(&seventh), &seventh));
    assert_eq!(e.weekly_snapshot().unwrap().bankroll(), usd(50, 0));
}

#[test]
fn settlement_frees_a_slot() {
    let snap = snapshot50();
    let e = engine(snap.clone());
    let mut first = open_partial(&e, &snap, 1);
    for n in 2..=5 {
        let _ = open_partial(&e, &snap, n);
    }
    first.apply_settlement(usd(3, 0)).unwrap();
    e.on_settlement(first.id());
    assert_eq!(first.lifecycle(), PositionLifecycle::Settled);
    assert_eq!(e.open_slot_count(), 4);
    let replacement = position(&snap, 6);
    approved(e.decide_entry(&remainder(&replacement), &replacement));
}

#[test]
fn adopt_releases_known_reservation_on_settled_position() {
    let snap = snapshot50();
    let e = engine(snap.clone());
    let mut pos = position(&snap, 1);
    approved(e.decide_entry(&remainder(&pos), &pos));
    assert!(e.reserved_for(pos.id()).cents() > 0);
    pos.apply_settlement(usd(0, 0)).unwrap();
    e.on_settlement(pos.id());
    e.adopt_fill_authoritative_occupancy(std::iter::once(&pos));
    assert_eq!(e.reserved_for(pos.id()).cents(), 0);
    assert!(!e.has_unknown_reservations());
    assert_eq!(e.open_slot_count(), 0);
}

#[test]
fn adopt_keeps_unknown_reservation_on_settled_position() {
    let snap = snapshot50();
    let e = engine(snap.clone());
    let mut pos = position(&snap, 1);
    let approved = approved(e.decide_entry(&remainder(&pos), &pos));
    e.mark_unknown(approved.client_order_id(), pos.id());
    pos.apply_settlement(usd(0, 0)).unwrap();
    e.on_settlement(pos.id());
    e.adopt_fill_authoritative_occupancy(std::iter::once(&pos));
    assert!(e.has_unknown_reservations());
    assert!(e.reserved_for(pos.id()).cents() > 0);
}

#[test]
fn unfilled_game_lock_keeps_slot_until_cancel_confirms() {
    let snap = snapshot50();
    let e = engine(snap.clone());
    let mut orders = Vec::new();
    for n in 1..=5 {
        let mut pos = position(&snap, n);
        let a = approved(e.decide_entry(&remainder(&pos), &pos));
        let (ex, recv) = ts();
        pos.apply_game_lock(ex, recv);
        e.lock_game(pos.game_id());
        orders.push(a.client_order_id());
    }
    assert_eq!(e.open_slot_count(), 5);
    let sixth = position(&snap, 6);
    assert_cap_rejected(e.decide_entry(&remainder(&sixth), &sixth));
    assert!(e.on_cancel(orders[0]));
    assert_eq!(e.open_slot_count(), 4);
    approved(e.decide_entry(&remainder(&sixth), &sixth));
    assert_eq!(e.open_slot_count(), 5);
}

#[test]
fn zero_fill_cancel_does_not_keep_a_slot() {
    let snap = snapshot50();
    let e = engine(snap.clone());
    let mut orders = Vec::new();
    for n in 1..=5 {
        let pos = position(&snap, n);
        let a = approved(e.decide_entry(&remainder(&pos), &pos));
        orders.push(a.client_order_id());
    }
    assert_eq!(e.open_slot_count(), 5);
    let sixth = position(&snap, 6);
    assert_cap_rejected(e.decide_entry(&remainder(&sixth), &sixth));
    for order in orders {
        assert!(e.on_cancel(order));
    }
    assert_eq!(e.open_slot_count(), 0);
    approved(e.decide_entry(&remainder(&sixth), &sixth));
}

#[test]
fn concurrent_approvals_cannot_create_six_positions() {
    let snap = snapshot50();
    let e = Arc::new(engine(snap.clone()));
    for n in 1..=5 {
        let _ = open_partial(&e, &snap, n);
    }
    let p6 = Arc::new(position(&snap, 6));
    let p7 = Arc::new(position(&snap, 7));
    let i6 = Arc::new(remainder(&p6));
    let i7 = Arc::new(remainder(&p7));
    let e1 = Arc::clone(&e);
    let e2 = Arc::clone(&e);
    let t1 = {
        let p = Arc::clone(&p6);
        let i = Arc::clone(&i6);
        thread::spawn(move || e1.decide_entry(&i, &p))
    };
    let t2 = {
        let p = Arc::clone(&p7);
        let i = Arc::clone(&i7);
        thread::spawn(move || e2.decide_entry(&i, &p))
    };
    let r1 = t1.join().unwrap();
    let r2 = t2.join().unwrap();
    let approved_n = matches!(r1, RiskDecision::Approved(_)) as u8
        + matches!(r2, RiskDecision::Approved(_)) as u8;
    assert_eq!(approved_n, 0);
    assert_eq!(e.open_slot_count(), 5);
}

#[test]
fn concurrent_new_slots_serialize_to_the_fifth() {
    let snap = snapshot50();
    let e = Arc::new(engine(snap.clone()));
    for n in 1..=4 {
        let _ = open_partial(&e, &snap, n);
    }
    let p5 = Arc::new(position(&snap, 5));
    let p6 = Arc::new(position(&snap, 6));
    let i5 = Arc::new(remainder(&p5));
    let i6 = Arc::new(remainder(&p6));
    let e1 = Arc::clone(&e);
    let e2 = Arc::clone(&e);
    let t1 = {
        let p = Arc::clone(&p5);
        let i = Arc::clone(&i5);
        thread::spawn(move || e1.decide_entry(&i, &p))
    };
    let t2 = {
        let p = Arc::clone(&p6);
        let i = Arc::clone(&i6);
        thread::spawn(move || e2.decide_entry(&i, &p))
    };
    let r1 = t1.join().unwrap();
    let r2 = t2.join().unwrap();
    let approved_n = matches!(r1, RiskDecision::Approved(_)) as u8
        + matches!(r2, RiskDecision::Approved(_)) as u8;
    assert_eq!(approved_n, 1);
    assert_eq!(e.open_slot_count(), 5);
}

#[test]
fn unknown_reconciliation_prevents_new_exposure() {
    let snap = snapshot50();
    let e = engine(snap.clone());
    let first = open_partial(&e, &snap, 1);
    for n in 2..=4 {
        let _ = open_partial(&e, &snap, n);
    }
    let pending = position(&snap, 5);
    let a = approved(e.decide_entry(&remainder(&pending), &pending));
    e.mark_unknown(a.client_order_id(), pending.id());
    let sixth = position(&snap, 6);
    assert_eq!(
        rejected_reason(&e.decide_entry(&remainder(&sixth), &sixth)),
        RiskRejectReason::ReconciliationRequired
    );
    assert_eq!(
        rejected_reason(&e.decide_entry(&remainder(&first), &first)),
        RiskRejectReason::ReconciliationRequired
    );
}

#[test]
fn ambiguous_reconciliation_prevents_new_exposure() {
    let snap = snapshot50();
    let e = engine(snap.clone());
    let first = open_partial(&e, &snap, 1);
    for n in 2..=4 {
        let _ = open_partial(&e, &snap, n);
    }
    e.require_reconciliation(first.id());
    let fifth = position(&snap, 5);
    assert_eq!(
        rejected_reason(&e.decide_entry(&remainder(&fifth), &fifth)),
        RiskRejectReason::ReconciliationRequired
    );
}

#[test]
fn ambiguous_unknown_on_open_book_blocks_a_new_slot() {
    let snap = snapshot50();
    let e = engine(snap.clone());
    for n in 1..=4 {
        let _ = open_partial(&e, &snap, n);
    }
    let fifth = position(&snap, 5);
    let a = approved(e.decide_entry(&remainder(&fifth), &fifth));
    e.reconcile_order(a.client_order_id(), fifth.id(), ReconcileOutcome::Ambiguous);
    let sixth = position(&snap, 6);
    assert_eq!(
        rejected_reason(&e.decide_entry(&remainder(&sixth), &sixth)),
        RiskRejectReason::ReconciliationRequired
    );
}

#[test]
fn cap_survives_restart_and_state_reload() {
    let snap = snapshot50();
    let e = engine(snap.clone());
    let mut positions = Vec::new();
    for n in 1..=5 {
        positions.push(open_partial(&e, &snap, n));
    }
    let persist = e.persist_state().unwrap();
    let restored = PaperRiskEngine::restore(
        persist.clone(),
        RiskConfig::mlb_paper_experimental().unwrap(),
    );
    assert_eq!(restored.open_slot_count(), 5);
    let sixth = position(&snap, 6);
    assert_cap_rejected(restored.decide_entry(&remainder(&sixth), &sixth));

    let mut stale = persist;
    stale.open_contracts.clear();
    stale.pending_new_slots.clear();
    let recovered = PaperRiskEngine::restore(stale, RiskConfig::mlb_paper_experimental().unwrap());
    assert_eq!(recovered.open_slot_count(), 0);
    recovered.adopt_fill_authoritative_occupancy(positions.iter());
    assert_eq!(recovered.open_slot_count(), 5);
    assert_cap_rejected(recovered.decide_entry(&remainder(&sixth), &sixth));
}

#[test]
fn cap_is_enforced_independently_of_strategy() {
    let snap = snapshot50();
    let e = engine(snap.clone());
    let mut proposed: Vec<Position> = (1..=6).map(|n| position(&snap, n)).collect();
    let mut approvals = 0u32;
    let mut rejections = 0u32;
    for pos in &mut proposed {
        match e.decide_entry(&remainder(pos), pos) {
            RiskDecision::Approved(a) => {
                approvals += 1;
                apply_entry_fill(pos, a.client_order_id(), 3, usd(2, 40));
                e.on_fill(pos.fill_history().last().unwrap());
            }
            RiskDecision::Rejected {
                reason: RiskRejectReason::PositionLimitExceeded,
                ..
            } => rejections += 1,
            other => panic!("unexpected {other:?}"),
        }
    }
    assert_eq!(approvals, 5);
    assert_eq!(rejections, 1);
    assert_eq!(e.open_slot_count(), 5);
}

#[test]
fn liquidation_proceeds_are_not_recycled_into_entry_capacity() {
    let snap = snapshot50();
    let e = engine(snap.clone());
    let mut first = open_partial(&e, &snap, 1);
    for n in 2..=5 {
        let _ = open_partial(&e, &snap, n);
    }
    let qty = first.filled_quantity().get();
    apply_liquidation_fill(&mut first, qty);
    e.on_fill(first.fill_history().last().unwrap());
    assert_eq!(e.weekly_snapshot().unwrap().bankroll(), usd(50, 0));
    assert_eq!(
        e.weekly_snapshot().unwrap().max_position_budget(),
        usd(6, 25)
    );
    let replacement = position(&snap, 6);
    let a = approved(e.decide_entry(&remainder(&replacement), &replacement));
    assert!(a.max_economic().cents() <= usd(6, 25).cents());
    assert_eq!(a.original_budget(), usd(6, 25));
}

#[test]
fn maker_only_80_to_83_is_unchanged() {
    let snap = snapshot50();
    let e = engine(snap.clone());
    let pos = position(&snap, 1);
    approved(e.decide_entry(
        &TradeIntent::build(BuildPositionIntent {
            strategy_id: StrategyId::from_raw(1),
            game_id: pos.game_id(),
            market_id: MarketId::from_raw(2),
            side: Side::Yes,
            position_id: pos.id(),
            limit_price: px(83),
            style: EntryStyle::MakerOnly,
            additional: AdditionalExposure::RemainderOfApprovedBudget,
        }),
        &pos,
    ));
    let pos2 = position(&snap, 2);
    assert_eq!(
        rejected_reason(&e.decide_entry(
            &TradeIntent::build(BuildPositionIntent {
                strategy_id: StrategyId::from_raw(1),
                game_id: pos2.game_id(),
                market_id: MarketId::from_raw(2),
                side: Side::Yes,
                position_id: pos2.id(),
                limit_price: px(84),
                style: EntryStyle::MakerOnly,
                additional: AdditionalExposure::RemainderOfApprovedBudget,
            }),
            &pos2,
        )),
        RiskRejectReason::EntryPriceAboveMaximum
    );
}

#[test]
fn liquidation_state_does_not_permit_a_sixth() {
    let snap = snapshot50();
    let e = engine(snap.clone());
    let mut first = open_partial(&e, &snap, 1);
    for n in 2..=5 {
        let _ = open_partial(&e, &snap, n);
    }
    first.begin_liquidation();
    apply_liquidation_fill(&mut first, 1);
    e.on_fill(first.fill_history().last().unwrap());
    assert_eq!(first.lifecycle(), PositionLifecycle::LiquidationActive);
    assert!(first.filled_quantity().get() > 0);
    assert_eq!(e.open_slot_count(), 5);
    let sixth = position(&snap, 6);
    assert_cap_rejected(e.decide_entry(&remainder(&sixth), &sixth));
}

fn position_for(snapshot: &WeeklyBankrollSnapshot, n: u128, strategy: StrategyId) -> Position {
    Position::new_for_game(
        PositionId::from_raw(n),
        GameId::from_raw(1000 + n),
        strategy,
        snapshot.snapshot_id(),
        if strategy == StrategyId::WNBA {
            snapshot
                .bankroll()
                .checked_mul_bps(momento_core::Bps::PCT_8_33)
                .unwrap()
        } else {
            snapshot.max_position_budget()
        },
        Some(MarketId::from_raw(2)),
        Some(Side::Yes),
    )
}

fn remainder_for(pos: &Position, strategy: StrategyId) -> TradeIntent {
    TradeIntent::build(BuildPositionIntent {
        strategy_id: strategy,
        game_id: pos.game_id(),
        market_id: MarketId::from_raw(2),
        side: Side::Yes,
        position_id: pos.id(),
        limit_price: px(80),
        style: EntryStyle::MakerOnly,
        additional: AdditionalExposure::RemainderOfApprovedBudget,
    })
}

fn open_partial_for(
    e: &PaperRiskEngine,
    snap: &WeeklyBankrollSnapshot,
    n: u128,
    strategy: StrategyId,
) -> Position {
    let mut pos = position_for(snap, n, strategy);
    let a = approved(e.decide_entry(&remainder_for(&pos, strategy), &pos));
    apply_entry_fill(&mut pos, a.client_order_id(), 3, usd(2, 40));
    e.on_fill(pos.fill_history().last().unwrap());
    e.on_cancel(a.client_order_id());
    pos
}

#[test]
fn wnba_8_33_percent_is_four_16_and_mlb_stays_six_25() {
    let snap = snapshot50();
    let e = engine(snap.clone());
    let wnba = position_for(&snap, 1, StrategyId::WNBA);
    let mlb = position_for(&snap, 2, StrategyId::MLB);
    let w = approved(e.decide_entry(&remainder_for(&wnba, StrategyId::WNBA), &wnba));
    let m = approved(e.decide_entry(&remainder_for(&mlb, StrategyId::MLB), &mlb));
    assert_eq!(w.original_budget(), usd(4, 16));
    assert_eq!(m.original_budget(), usd(6, 25));
    assert_eq!(snap.max_position_budget(), usd(6, 25));
    assert_eq!(snap.bankroll(), usd(50, 0));
}

#[test]
fn three_mlb_and_two_wnba_reject_a_sixth() {
    let snap = snapshot50();
    let e = engine(snap.clone());
    for n in 1..=3 {
        let _ = open_partial_for(&e, &snap, n, StrategyId::MLB);
    }
    for n in 4..=5 {
        let _ = open_partial_for(&e, &snap, n, StrategyId::WNBA);
    }
    assert_eq!(e.open_slot_count(), 5);
    let sixth_mlb = position_for(&snap, 6, StrategyId::MLB);
    let sixth_wnba = position_for(&snap, 7, StrategyId::WNBA);
    assert_cap_rejected(e.decide_entry(&remainder_for(&sixth_mlb, StrategyId::MLB), &sixth_mlb));
    assert_cap_rejected(e.decide_entry(&remainder_for(&sixth_wnba, StrategyId::WNBA), &sixth_wnba));
}

#[test]
fn four_mlb_and_one_wnba_reject_a_sixth() {
    let snap = snapshot50();
    let e = engine(snap.clone());
    for n in 1..=4 {
        let _ = open_partial_for(&e, &snap, n, StrategyId::MLB);
    }
    let _ = open_partial_for(&e, &snap, 5, StrategyId::WNBA);
    let sixth = position_for(&snap, 6, StrategyId::WNBA);
    assert_cap_rejected(e.decide_entry(&remainder_for(&sixth, StrategyId::WNBA), &sixth));
}

#[test]
fn five_mlb_rejects_wnba() {
    let snap = snapshot50();
    let e = engine(snap.clone());
    for n in 1..=5 {
        let _ = open_partial_for(&e, &snap, n, StrategyId::MLB);
    }
    let wnba = position_for(&snap, 6, StrategyId::WNBA);
    assert_cap_rejected(e.decide_entry(&remainder_for(&wnba, StrategyId::WNBA), &wnba));
}

#[test]
fn five_wnba_rejects_mlb() {
    let snap = snapshot50();
    let e = engine(snap.clone());
    for n in 1..=5 {
        let _ = open_partial_for(&e, &snap, n, StrategyId::WNBA);
    }
    let mlb = position_for(&snap, 6, StrategyId::MLB);
    assert_cap_rejected(e.decide_entry(&remainder_for(&mlb, StrategyId::MLB), &mlb));
}

#[test]
fn concurrent_mlb_and_wnba_cannot_open_a_sixth() {
    let snap = snapshot50();
    let e = Arc::new(engine(snap.clone()));
    for n in 1..=4 {
        let _ = open_partial_for(&e, &snap, n, StrategyId::MLB);
    }
    let mlb = Arc::new(position_for(&snap, 5, StrategyId::MLB));
    let wnba = Arc::new(position_for(&snap, 6, StrategyId::WNBA));
    let i_mlb = Arc::new(remainder_for(&mlb, StrategyId::MLB));
    let i_wnba = Arc::new(remainder_for(&wnba, StrategyId::WNBA));
    let e1 = Arc::clone(&e);
    let e2 = Arc::clone(&e);
    let t1 = {
        let p = Arc::clone(&mlb);
        let i = Arc::clone(&i_mlb);
        thread::spawn(move || e1.decide_entry(&i, &p))
    };
    let t2 = {
        let p = Arc::clone(&wnba);
        let i = Arc::clone(&i_wnba);
        thread::spawn(move || e2.decide_entry(&i, &p))
    };
    let r1 = t1.join().unwrap();
    let r2 = t2.join().unwrap();
    let approved_n = matches!(r1, RiskDecision::Approved(_)) as u8
        + matches!(r2, RiskDecision::Approved(_)) as u8;
    assert_eq!(approved_n, 1);
    assert_eq!(e.open_slot_count(), 5);
}

#[test]
fn restart_preserves_mixed_desk_cap() {
    let snap = snapshot50();
    let e = engine(snap.clone());
    for n in 1..=3 {
        let _ = open_partial_for(&e, &snap, n, StrategyId::MLB);
    }
    for n in 4..=5 {
        let _ = open_partial_for(&e, &snap, n, StrategyId::WNBA);
    }
    let persist = e.persist_state().unwrap();
    let restored = PaperRiskEngine::restore(persist, RiskConfig::mlb_paper_experimental().unwrap());
    assert_eq!(restored.open_slot_count(), 5);
    let sixth = position_for(&snap, 6, StrategyId::WNBA);
    assert_cap_rejected(restored.decide_entry(&remainder_for(&sixth, StrategyId::WNBA), &sixth));
}
