use std::sync::Arc;
use std::thread;

use chrono::{TimeZone, Utc};
use momento_core::{
    AdditionalExposure, AuditEvent, Bps, BuildPositionIntent, ClientOrderId, Contracts, EntryStyle,
    Fee, FeeKind, FeeModelId, Fill, FillId, GameId, MarketId, Money, Position, PositionId,
    PositionLifecycle, Price, ReconcileOutcome, RiskDecision, RiskRejectReason, Side,
    SnapshotSource, StrategyId, TradeIntent, WeeklyBankrollSnapshot,
};
use momento_risk::{
    AvailableCapacity, FeeModel, PaperRiskEngine, RiskConfig, SnapshotPaperBalance, ZeroFeeModel,
};

fn usd(d: i64, c: u8) -> Money {
    Money::from_usd(d, c).unwrap()
}

fn px(c: u16) -> Price {
    Price::from_cents(c).unwrap()
}

fn snapshot_at(bankroll: Money) -> WeeklyBankrollSnapshot {
    let now = Utc
        .with_ymd_and_hms(2026, 8, 24, 16, 0, 0)
        .single()
        .unwrap();
    WeeklyBankrollSnapshot::capture(bankroll, Bps::PCT_12_5, now, SnapshotSource::Test).unwrap()
}

fn snapshot50() -> WeeklyBankrollSnapshot {
    snapshot_at(usd(50, 0))
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

fn intent_at(price: Price, position: &Position, additional: AdditionalExposure) -> TradeIntent {
    TradeIntent::build(BuildPositionIntent {
        strategy_id: StrategyId::from_raw(1),
        game_id: position.game_id(),
        market_id: MarketId::from_raw(2),
        side: Side::Yes,
        position_id: position.id(),
        limit_price: price,
        style: EntryStyle::MakerOnly,
        additional,
    })
}

fn remainder(position: &Position, price: Price) -> TradeIntent {
    intent_at(
        price,
        position,
        AdditionalExposure::RemainderOfApprovedBudget,
    )
}

fn engine(snapshot: WeeklyBankrollSnapshot) -> PaperRiskEngine {
    PaperRiskEngine::paper(snapshot, RiskConfig::mlb_paper_experimental().unwrap())
}

fn apply_fill(pos: &mut Position, order: ClientOrderId, qty: u32, price: Price, premium: Money) {
    let t = Utc
        .with_ymd_and_hms(2026, 8, 24, 18, 0, 0)
        .single()
        .unwrap();
    pos.apply_entry_fill(Fill::new(
        FillId::generate(),
        pos.id(),
        order,
        None,
        Contracts::from_u32(qty),
        price,
        premium,
        Fee::zero(FeeKind::Entry),
        momento_core::ExchangeTimestamp::from_utc(t),
        momento_core::ReceivedAt::from_utc(t),
    ))
    .unwrap();
}

fn approved(d: RiskDecision) -> momento_core::ApprovedTradeIntent {
    match d {
        RiskDecision::Approved(a) => a,
        other => panic!("expected approval, got {other:?}"),
    }
}

#[test]
fn snapshot_50_produces_6_25_budget() {
    let snap = snapshot50();
    assert_eq!(snap.bankroll(), usd(50, 0));
    assert_eq!(snap.max_position_budget(), usd(6, 25));
}

#[test]
fn weekly_snapshot_is_immutable_and_ignores_later_balance() {
    let snap = snapshot50();
    let later = usd(55, 0);
    assert_ne!(later, snap.bankroll());
    assert_eq!(snap.max_position_budget(), usd(6, 25));
}

#[test]
fn later_55_does_not_increase_existing_week_budget() {
    let snap = snapshot50();
    let e = engine(snap.clone());
    let pos = position_for(&snap);
    let a = approved(e.decide_entry(&remainder(&pos, px(80)), &pos));
    assert_eq!(a.original_budget(), usd(6, 25));
    let _ignored = snapshot_at(usd(55, 0));
    assert_eq!(a.original_budget(), usd(6, 25));
}

#[test]
fn first_incremental_approval_succeeds_within_budget() {
    let snap = snapshot50();
    let e = engine(snap.clone());
    let pos = position_for(&snap);
    let a = approved(e.decide_entry(&remainder(&pos, px(80)), &pos));
    assert!(a.max_economic().cents() <= usd(6, 25).cents());
    assert_eq!(a.snapshot_id(), snap.snapshot_id());
    assert_eq!(a.position_id(), pos.id());
}

#[test]
fn multiple_incremental_approvals_consume_same_budget() {
    let snap = snapshot50();
    let e = engine(snap.clone());
    let mut pos = position_for(&snap);
    let a1 = approved(e.decide_entry(
        &intent_at(px(80), &pos, AdditionalExposure::NotMoreThan(usd(2, 40))),
        &pos,
    ));
    apply_fill(&mut pos, a1.client_order_id(), 3, px(80), usd(2, 40));
    e.on_fill(pos.fill_history().last().unwrap());
    let a2 = approved(e.decide_entry(
        &intent_at(px(80), &pos, AdditionalExposure::NotMoreThan(usd(1, 0))),
        &pos,
    ));
    apply_fill(&mut pos, a2.client_order_id(), 1, px(80), usd(0, 80));
    e.on_fill(pos.fill_history().last().unwrap());
    let a3 = approved(e.decide_entry(
        &intent_at(px(80), &pos, AdditionalExposure::NotMoreThan(usd(1, 25))),
        &pos,
    ));
    assert_eq!(a1.position_id(), a2.position_id());
    assert_eq!(a2.position_id(), a3.position_id());
    assert_eq!(a1.snapshot_id(), a3.snapshot_id());
    assert_eq!(a1.original_budget(), usd(6, 25));
    assert_eq!(pos.id(), a1.position_id());
    let used = pos
        .actual_exposure()
        .as_money()
        .checked_add(e.reserved_for(pos.id()))
        .unwrap();
    assert!(used.cents() <= usd(6, 25).cents());
}

#[test]
fn partial_fills_do_not_create_another_position_id() {
    let snap = snapshot50();
    let e = engine(snap.clone());
    let mut pos = position_for(&snap);
    let id = pos.id();
    let a1 = approved(e.decide_entry(&remainder(&pos, px(80)), &pos));
    apply_fill(&mut pos, a1.client_order_id(), 3, px(80), usd(2, 40));
    e.on_fill(pos.fill_history().last().unwrap());
    e.on_cancel(a1.client_order_id());
    let a2 = approved(e.decide_entry(&remainder(&pos, px(80)), &pos));
    assert_eq!(a1.position_id(), id);
    assert_eq!(a2.position_id(), id);
}

#[test]
fn submitted_quantity_is_not_actual_exposure() {
    let snap = snapshot50();
    let e = engine(snap.clone());
    let mut pos = position_for(&snap);
    pos.record_submission(Contracts::from_u32(7)).unwrap();
    assert_eq!(pos.submitted_quantity().get(), 7);
    assert_eq!(pos.actual_exposure().as_money(), Money::ZERO);
    let a = approved(e.decide_entry(&remainder(&pos, px(80)), &pos));
    assert!(a.max_economic().cents() > 0);
}

#[test]
fn actual_fill_reduces_remaining_capacity() {
    let snap = snapshot50();
    let e = engine(snap.clone());
    let mut pos = position_for(&snap);
    let a1 = approved(e.decide_entry(&remainder(&pos, px(80)), &pos));
    let before = a1.max_economic();
    apply_fill(&mut pos, a1.client_order_id(), 3, px(80), usd(2, 40));
    e.on_fill(pos.fill_history().last().unwrap());
    e.on_cancel(a1.client_order_id());
    let a2 = approved(e.decide_entry(&remainder(&pos, px(80)), &pos));
    assert!(a2.max_economic().cents() < before.cents());
    assert_eq!(pos.remaining_economic_target().unwrap(), usd(3, 85));
}

#[test]
fn two_simultaneous_requests_cannot_oversubscribe_budget() {
    let snap = snapshot50();
    let e = Arc::new(engine(snap.clone()));
    let pos = Arc::new(position_for(&snap));
    let intent = Arc::new(remainder(&pos, px(80)));
    let e1 = Arc::clone(&e);
    let e2 = Arc::clone(&e);
    let p1 = Arc::clone(&pos);
    let p2 = Arc::clone(&pos);
    let i1 = Arc::clone(&intent);
    let i2 = Arc::clone(&intent);
    let t1 = thread::spawn(move || e1.decide_entry(&i1, &p1));
    let t2 = thread::spawn(move || e2.decide_entry(&i2, &p2));
    let r1 = t1.join().unwrap();
    let r2 = t2.join().unwrap();
    let approved_n = matches!(r1, RiskDecision::Approved(_)) as u8
        + matches!(r2, RiskDecision::Approved(_)) as u8;
    assert_eq!(approved_n, 1);
    let reserved = e.reserved_for(pos.id());
    assert!(reserved.cents() <= usd(6, 25).cents());
}

#[test]
fn entry_at_83_succeeds() {
    let snap = snapshot50();
    let e = engine(snap.clone());
    let pos = position_for(&snap);
    approved(e.decide_entry(&remainder(&pos, px(83)), &pos));
}

#[test]
fn entry_at_84_rejects() {
    let snap = snapshot50();
    let e = engine(snap.clone());
    let pos = position_for(&snap);
    assert!(matches!(
        e.decide_entry(&remainder(&pos, px(84)), &pos),
        RiskDecision::Rejected {
            reason: RiskRejectReason::EntryPriceAboveMaximum,
            ..
        }
    ));
}

#[test]
fn game_locked_rejects_all_future_entry() {
    let snap = snapshot50();
    let e = engine(snap.clone());
    let mut pos = position_for(&snap);
    let a = approved(e.decide_entry(
        &intent_at(px(80), &pos, AdditionalExposure::NotMoreThan(usd(2, 40))),
        &pos,
    ));
    apply_fill(&mut pos, a.client_order_id(), 3, px(80), usd(2, 40));
    e.on_fill(pos.fill_history().last().unwrap());
    let t = Utc
        .with_ymd_and_hms(2026, 8, 24, 19, 0, 0)
        .single()
        .unwrap();
    pos.apply_game_lock(
        momento_core::ExchangeTimestamp::from_utc(t),
        momento_core::ReceivedAt::from_utc(t),
    );
    e.lock_game(pos.game_id());
    assert!(matches!(
        e.decide_entry(&remainder(&pos, px(80)), &pos),
        RiskDecision::Rejected {
            reason: RiskRejectReason::GameLocked,
            ..
        }
    ));
    assert!(matches!(
        e.decide_entry(&remainder(&pos, px(83)), &pos),
        RiskDecision::Rejected {
            reason: RiskRejectReason::GameLocked,
            ..
        }
    ));
}

#[test]
fn game_locked_does_not_liquidate_existing_position() {
    let snap = snapshot50();
    let e = engine(snap.clone());
    let mut pos = position_for(&snap);
    let a = approved(e.decide_entry(
        &intent_at(px(80), &pos, AdditionalExposure::NotMoreThan(usd(2, 40))),
        &pos,
    ));
    apply_fill(&mut pos, a.client_order_id(), 3, px(80), usd(2, 40));
    let t = Utc
        .with_ymd_and_hms(2026, 8, 24, 19, 0, 0)
        .single()
        .unwrap();
    pos.apply_game_lock(
        momento_core::ExchangeTimestamp::from_utc(t),
        momento_core::ReceivedAt::from_utc(t),
    );
    e.lock_game(pos.game_id());
    assert_eq!(pos.actual_exposure().as_money(), usd(2, 40));
    assert_eq!(pos.lifecycle(), PositionLifecycle::OpenPartial);
    assert!(!pos.lifecycle().is_flat());
    assert_eq!(
        e.decide_entry(&remainder(&pos, px(80)), &pos)
            .clone_reason(),
        Some(RiskRejectReason::GameLocked)
    );
}

trait ReasonExt {
    fn clone_reason(&self) -> Option<RiskRejectReason>;
}

impl ReasonExt for RiskDecision {
    fn clone_reason(&self) -> Option<RiskRejectReason> {
        match self {
            RiskDecision::Rejected { reason, .. } => Some(*reason),
            RiskDecision::Approved(_) => None,
        }
    }
}

#[test]
fn price_pause_may_resume_if_not_locked() {
    let snap = snapshot50();
    let e = engine(snap.clone());
    let mut pos = position_for(&snap);
    pos.pause_entry_above_max_price();
    assert!(matches!(
        e.decide_entry(&remainder(&pos, px(80)), &pos),
        RiskDecision::Rejected {
            reason: RiskRejectReason::EntryPausedAboveMaxPrice,
            ..
        }
    ));
    pos.resume_entry_if_unlocked();
    approved(e.decide_entry(&remainder(&pos, px(81)), &pos));
}

#[test]
fn after_game_locked_price_return_still_rejected() {
    let snap = snapshot50();
    let e = engine(snap.clone());
    let mut pos = position_for(&snap);
    let t = Utc
        .with_ymd_and_hms(2026, 8, 24, 19, 0, 0)
        .single()
        .unwrap();
    pos.apply_game_lock(
        momento_core::ExchangeTimestamp::from_utc(t),
        momento_core::ReceivedAt::from_utc(t),
    );
    pos.resume_entry_if_unlocked();
    e.lock_game(pos.game_id());
    assert!(matches!(
        e.decide_entry(&remainder(&pos, px(80)), &pos),
        RiskDecision::Rejected {
            reason: RiskRejectReason::GameLocked,
            ..
        }
    ));
}

#[test]
fn kill_switch_rejects_entry() {
    let snap = snapshot50();
    let e = engine(snap.clone());
    let pos = position_for(&snap);
    e.trip_kill_switch();
    assert!(matches!(
        e.decide_entry(&remainder(&pos, px(80)), &pos),
        RiskDecision::Rejected {
            reason: RiskRejectReason::KillSwitchActive,
            ..
        }
    ));
}

#[test]
fn reconciliation_required_rejects_entry() {
    let snap = snapshot50();
    let e = engine(snap.clone());
    let pos = position_for(&snap);
    e.require_reconciliation(pos.id());
    assert!(matches!(
        e.decide_entry(&remainder(&pos, px(80)), &pos),
        RiskDecision::Rejected {
            reason: RiskRejectReason::ReconciliationRequired,
            ..
        }
    ));
}

#[test]
fn unknown_order_does_not_release_reservation() {
    let snap = snapshot50();
    let e = engine(snap.clone());
    let pos = position_for(&snap);
    let a = approved(e.decide_entry(
        &intent_at(px(80), &pos, AdditionalExposure::NotMoreThan(usd(4, 0))),
        &pos,
    ));
    let reserved_before = e.reserved_for(pos.id());
    e.mark_unknown(a.client_order_id(), pos.id());
    assert_eq!(e.reserved_for(pos.id()), reserved_before);
    assert!(matches!(
        e.decide_entry(&remainder(&pos, px(80)), &pos),
        RiskDecision::Rejected {
            reason: RiskRejectReason::ReconciliationRequired,
            ..
        }
    ));
    e.complete_reconciliation(pos.id());
    assert_eq!(e.reserved_for(pos.id()), reserved_before);
}

#[test]
fn cancelled_order_releases_unused_reservation() {
    let snap = snapshot50();
    let e = engine(snap.clone());
    let pos = position_for(&snap);
    let a = approved(e.decide_entry(&remainder(&pos, px(80)), &pos));
    assert!(e.reserved_for(pos.id()).cents() > 0);
    assert!(e.on_cancel(a.client_order_id()));
    assert_eq!(e.reserved_for(pos.id()), Money::ZERO);
}

#[test]
fn partial_fill_consumes_reservation() {
    let snap = snapshot50();
    let e = engine(snap.clone());
    let mut pos = position_for(&snap);
    let a = approved(e.decide_entry(&remainder(&pos, px(80)), &pos));
    let reserved_before = e.reserved_for(pos.id());
    apply_fill(&mut pos, a.client_order_id(), 3, px(80), usd(2, 40));
    e.on_fill(pos.fill_history().last().unwrap());
    let reserved_after = e.reserved_for(pos.id());
    assert!(reserved_after.cents() < reserved_before.cents());
}

#[test]
fn approval_contains_snapshot_and_position_ids() {
    let snap = snapshot50();
    let e = engine(snap.clone());
    let pos = position_for(&snap);
    let a = approved(e.decide_entry(&remainder(&pos, px(80)), &pos));
    assert_eq!(a.snapshot_id(), snap.snapshot_id());
    assert_eq!(a.position_id(), pos.id());
    assert_eq!(a.game_id(), pos.game_id());
}

#[test]
fn every_decision_is_audited() {
    let snap = snapshot50();
    let e = engine(snap.clone());
    let pos = position_for(&snap);
    approved(e.decide_entry(&remainder(&pos, px(80)), &pos));
    e.decide_entry(&remainder(&pos, px(84)), &pos);
    let events = e.audit_events();
    let approvals = events
        .iter()
        .filter(|e| matches!(e, AuditEvent::RiskApproval { .. }))
        .count();
    let rejections = events
        .iter()
        .filter(|e| matches!(e, AuditEvent::RiskRejection { .. }))
        .count();
    assert_eq!(approvals, 1);
    assert_eq!(rejections, 1);
}

#[test]
fn zero_fee_model_is_isolated_placeholder() {
    let id = ZeroFeeModel.model_id();
    assert_eq!(id, FeeModelId::zero_placeholder());
    assert!(id.as_str().contains("not-kalshi-economics"));
    assert_eq!(
        ZeroFeeModel
            .estimate_entry_fee(Contracts::from_u32(3), px(80))
            .unwrap(),
        Money::ZERO
    );
}

#[derive(Clone, Copy)]
struct TestPerContractFee;

impl FeeModel for TestPerContractFee {
    fn model_id(&self) -> FeeModelId {
        FeeModelId::new("test-per-contract-not-kalshi")
    }

    fn estimate_entry_fee(
        &self,
        quantity: Contracts,
        _price: Price,
    ) -> Result<Money, momento_risk::FeeEstimateError> {
        Ok(Money::from_cents(i64::from(quantity.get())))
    }

    fn estimate_liquidation_fee(
        &self,
        quantity: Contracts,
        price: Price,
    ) -> Result<Money, momento_risk::FeeEstimateError> {
        self.estimate_entry_fee(quantity, price)
    }
}

#[test]
fn fee_model_is_injectable_and_zero_is_not_assumed_permanent() {
    let snap = snapshot50();
    let e = PaperRiskEngine::new(
        snap.clone(),
        RiskConfig::mlb_paper_experimental().unwrap(),
        TestPerContractFee,
        SnapshotPaperBalance::from_bankroll(snap.bankroll()),
        momento_core::InMemoryAuditLog::default(),
    );
    let pos = position_for(&snap);
    let a = approved(e.decide_entry(&remainder(&pos, px(80)), &pos));
    assert_eq!(a.fee_model_id().as_str(), "test-per-contract-not-kalshi");
    assert!(a.fee_estimate().cents() > 0);
    assert_ne!(a.fee_model_id(), &FeeModelId::zero_placeholder());
    let _cap: &dyn AvailableCapacity = &SnapshotPaperBalance::from_bankroll(snap.bankroll());
}

#[test]
fn unknown_still_blocks_after_failed_cancel_release() {
    let snap = snapshot50();
    let e = engine(snap.clone());
    let pos = position_for(&snap);
    let a = approved(e.decide_entry(&remainder(&pos, px(80)), &pos));
    e.mark_unknown(a.client_order_id(), pos.id());
    assert!(!e.on_cancel(a.client_order_id()));
    assert!(e.reserved_for(pos.id()).cents() > 0);
    e.reconcile_order(a.client_order_id(), pos.id(), ReconcileOutcome::Found);
}

#[test]
fn week_roll_release_allows_entry_on_rebound_unfilled_position() {
    let old = snapshot50();
    let e = engine(old.clone());
    let mut pos = position_for(&old);
    let _prior = approved(e.decide_entry(&remainder(&pos, px(80)), &pos));
    assert!(e.reserved_for(pos.id()).cents() > 0);

    let new = snapshot_at(usd(50, 0));
    assert_ne!(old.snapshot_id(), new.snapshot_id());
    e.replace_weekly_snapshot(new.clone());
    assert!(pos.rebind_unfilled_weekly_snapshot(new.snapshot_id(), new.max_position_budget()));
    e.release_prior_week_unfilled_occupancy(&[pos.id()]);
    let again = approved(e.decide_entry(&remainder(&pos, px(81)), &pos));
    assert_eq!(again.snapshot_id(), new.snapshot_id());
}

#[test]
fn week_roll_does_not_release_unknown_reservation() {
    let old = snapshot50();
    let e = engine(old.clone());
    let pos = position_for(&old);
    let a = approved(e.decide_entry(&remainder(&pos, px(80)), &pos));
    e.mark_unknown(a.client_order_id(), pos.id());
    e.release_prior_week_unfilled_occupancy(&[pos.id()]);
    assert!(e.reserved_for(pos.id()).cents() > 0);
    assert!(e.has_unknown_reservations());
}

fn iti_risk() -> (WeeklyBankrollSnapshot, PaperRiskEngine, Position) {
    let snap = snapshot50();
    let mut cfg = RiskConfig::mlb_paper_experimental().unwrap();
    cfg.min_entry_price = px(20);
    cfg.max_entry_price = px(59);
    let engine = PaperRiskEngine::paper(snap.clone(), cfg);
    let pos = Position::new_for_game(
        PositionId::from_raw(1),
        GameId::from_raw(10),
        StrategyId::RESEARCH_ITI,
        snap.snapshot_id(),
        snap.max_position_budget(),
        Some(MarketId::from_raw(2)),
        Some(Side::Yes),
    );
    (snap, engine, pos)
}

fn iti_intent(pos: &Position, price: Price) -> TradeIntent {
    TradeIntent::build(BuildPositionIntent {
        strategy_id: StrategyId::RESEARCH_ITI,
        game_id: pos.game_id(),
        market_id: MarketId::from_raw(2),
        side: Side::Yes,
        position_id: pos.id(),
        limit_price: price,
        style: EntryStyle::MakerOnly,
        additional: AdditionalExposure::RemainderOfApprovedBudget,
    })
}

#[test]
fn research_iti_allocation_is_known() {
    let cfg = RiskConfig::mlb_paper_experimental().unwrap();
    assert_eq!(
        cfg.allocation_for(StrategyId::RESEARCH_ITI),
        Some(Bps::PCT_12_5)
    );
    assert_eq!(cfg.allocation_for(StrategyId::from_raw(99)), None);
}

#[test]
fn research_iti_19_is_rejected_20_and_crossing_40_are_approved() {
    let (_snap, e, pos) = iti_risk();
    match e.decide_entry(&iti_intent(&pos, px(19)), &pos) {
        RiskDecision::Rejected { reason, .. } => {
            assert_eq!(reason, RiskRejectReason::InvalidPrice);
        }
        other => panic!("19 must reject, got {other:?}"),
    }
    let at_20 = approved(e.decide_entry(&iti_intent(&pos, px(20)), &pos));
    assert_eq!(at_20.limit_price().cents(), 20);
    e.on_cancel(at_20.client_order_id());
    let at_40 = approved(e.decide_entry(&iti_intent(&pos, px(40)), &pos));
    assert_eq!(at_40.limit_price().cents(), 40);
}

#[test]
fn unknown_strategy_id_is_rejected() {
    let snap = snapshot50();
    let e = engine(snap.clone());
    let pos = position_for(&snap);
    let intent = TradeIntent::build(BuildPositionIntent {
        strategy_id: StrategyId::from_raw(99),
        game_id: pos.game_id(),
        market_id: MarketId::from_raw(2),
        side: Side::Yes,
        position_id: pos.id(),
        limit_price: px(80),
        style: EntryStyle::MakerOnly,
        additional: AdditionalExposure::RemainderOfApprovedBudget,
    });
    match e.decide_entry(&intent, &pos) {
        RiskDecision::Rejected { reason, .. } => {
            assert_eq!(reason, RiskRejectReason::UnsupportedTradeType);
        }
        other => panic!("unknown id must reject, got {other:?}"),
    }
}
