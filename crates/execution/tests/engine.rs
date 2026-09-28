use chrono::{TimeZone, Utc};
use momento_core::{
    AdditionalExposure, ApprovedTradeIntent, AuditEvent, Bps, BuildPositionIntent, ClientOrderId,
    Contracts, EntryStyle, ExchangeTimestamp, FeeModelId, GameId, MarketId, Money, OrderState,
    PositionId, PositionLifecycle, Price, ReceivedAt, ReconcileOutcome, RiskDecision,
    RiskDecisionId, RiskGrant, RiskRejectReason, Side, SnapshotSource, StrategyId, TradeIntent,
    WeeklyBankrollSnapshot, contract_premium,
};
use momento_execution::{ExecutionError, PaperExecutionEngine, PaperFill};
use momento_risk::{FeeModel, RiskConfig, SnapshotPaperBalance, ZeroFeeModel};

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
    WeeklyBankrollSnapshot::capture(usd(50, 0), Bps::PCT_12_5, now, SnapshotSource::Test).unwrap()
}

fn ts() -> (ExchangeTimestamp, ReceivedAt) {
    let t = Utc
        .with_ymd_and_hms(2026, 8, 24, 18, 0, 0)
        .single()
        .unwrap();
    (ExchangeTimestamp::from_utc(t), ReceivedAt::from_utc(t))
}

fn fill_cmd(id: ClientOrderId, qty: u32, price: Price) -> PaperFill {
    let (exchange_ts, received_at) = ts();
    PaperFill {
        client_order_id: id,
        quantity: Contracts::from_u32(qty),
        price,
        fill_id: None,
        exchange_ts,
        received_at,
    }
}

fn paper() -> PaperExecutionEngine {
    PaperExecutionEngine::paper(snapshot50())
}

fn open(engine: &mut PaperExecutionEngine) -> PositionId {
    engine.open_game(
        StrategyId::from_raw(1),
        GameId::from_raw(10),
        MarketId::from_raw(2),
        Side::Yes,
    )
}

fn intent_at(position_id: PositionId, price: Price, additional: AdditionalExposure) -> TradeIntent {
    TradeIntent::build(BuildPositionIntent {
        strategy_id: StrategyId::from_raw(1),
        game_id: GameId::from_raw(10),
        market_id: MarketId::from_raw(2),
        side: Side::Yes,
        position_id,
        limit_price: price,
        style: EntryStyle::MakerOnly,
        additional,
    })
}

fn remainder(position_id: PositionId, price: Price) -> TradeIntent {
    intent_at(
        position_id,
        price,
        AdditionalExposure::RemainderOfApprovedBudget,
    )
}

fn not_more_than(position_id: PositionId, price: Price, cap: Money) -> TradeIntent {
    intent_at(position_id, price, AdditionalExposure::NotMoreThan(cap))
}

fn approve(d: RiskDecision) -> ApprovedTradeIntent {
    match d {
        RiskDecision::Approved(a) => a,
        RiskDecision::Rejected { reason, .. } => panic!("rejected: {reason:?}"),
    }
}

fn submit_remainder(engine: &mut PaperExecutionEngine, pid: PositionId) -> ClientOrderId {
    let d = engine.decide_entry(&remainder(pid, px(80)));
    engine.execute(d).unwrap()
}

#[test]
fn approved_trade_intent_is_required_for_execution() {
    let mut engine = paper();
    let pid = open(&mut engine);
    let rejected = engine.decide_entry(&remainder(pid, px(84)));
    assert!(matches!(rejected, RiskDecision::Rejected { .. }));
    assert_eq!(engine.execute(rejected), Err(ExecutionError::NotApproved));
}

#[test]
fn execution_cannot_exceed_approved_exposure() {
    let mut engine = paper();
    let pid = open(&mut engine);
    let id = submit_remainder(&mut engine, pid);
    engine.accept(id).unwrap();
    engine.fill(fill_cmd(id, 7, px(80))).unwrap();
    assert_eq!(
        engine.fill(fill_cmd(id, 1, px(80))),
        Err(ExecutionError::ExceedsApprovedExposure)
    );
    assert_eq!(
        engine.position(pid).unwrap().actual_exposure().as_money(),
        usd(5, 60)
    );
}

#[test]
fn one_position_id_survives_multiple_orders() {
    let mut engine = paper();
    let pid = open(&mut engine);
    let first = submit_remainder(&mut engine, pid);
    engine.accept(first).unwrap();
    engine.fill(fill_cmd(first, 3, px(80))).unwrap();
    engine.cancel(first).unwrap();
    let second = engine.execute(engine.decide_entry(&not_more_than(pid, px(80), usd(1, 0))));
    let second = second.unwrap();
    engine.accept(second).unwrap();
    engine.fill(fill_cmd(second, 1, px(80))).unwrap();
    assert_eq!(engine.position(pid).unwrap().id(), pid);
    assert_eq!(engine.position(pid).unwrap().fill_history().len(), 2);
    assert_ne!(first, second);
}

#[test]
fn partial_fill_does_not_complete_position() {
    let mut engine = paper();
    let pid = open(&mut engine);
    let id = submit_remainder(&mut engine, pid);
    engine.accept(id).unwrap();
    engine.fill(fill_cmd(id, 3, px(80))).unwrap();
    let pos = engine.position(pid).unwrap();
    assert_eq!(pos.actual_exposure().as_money(), usd(2, 40));
    assert_eq!(pos.remaining_economic_target().unwrap(), usd(3, 85));
    assert_eq!(pos.lifecycle(), PositionLifecycle::OpenPartial);
    assert!(!pos.lifecycle().is_complete_open());
    assert_eq!(engine.order_state(id), Some(OrderState::PartiallyFilled));
}

#[test]
fn subsequent_fill_updates_the_same_position() {
    let mut engine = paper();
    let pid = open(&mut engine);
    let id = submit_remainder(&mut engine, pid);
    engine.accept(id).unwrap();
    engine.fill(fill_cmd(id, 3, px(80))).unwrap();
    engine.fill(fill_cmd(id, 2, px(80))).unwrap();
    let pos = engine.position(pid).unwrap();
    assert_eq!(pos.id(), pid);
    assert_eq!(pos.actual_exposure().as_money(), usd(4, 00));
    assert_eq!(pos.filled_quantity(), Contracts::from_u32(5));
}

#[test]
fn submitted_quantity_is_not_filled_quantity() {
    let mut engine = paper();
    let pid = open(&mut engine);
    let id = submit_remainder(&mut engine, pid);
    engine.accept(id).unwrap();
    engine.fill(fill_cmd(id, 3, px(80))).unwrap();
    let pos = engine.position(pid).unwrap();
    assert_eq!(pos.submitted_quantity(), Contracts::from_u32(7));
    assert_eq!(pos.filled_quantity(), Contracts::from_u32(3));
    assert_ne!(pos.submitted_quantity(), pos.filled_quantity());
    let q = engine.order_quantities(id).unwrap();
    assert_eq!(q.requested, Contracts::from_u32(7));
    assert_eq!(q.filled, Contracts::from_u32(3));
}

#[test]
fn full_fill_consumes_the_approved_order_budget() {
    let mut engine = paper();
    let pid = open(&mut engine);
    let decision = engine.decide_entry(&remainder(pid, px(80)));
    let approved_economic = approve(decision.clone()).max_economic();
    let id = engine.execute(decision).unwrap();
    engine.accept(id).unwrap();
    engine.fill(fill_cmd(id, 7, px(80))).unwrap();
    assert_eq!(engine.order_state(id), Some(OrderState::Filled));
    assert_eq!(engine.reserved_for(pid), Money::ZERO);
    assert_eq!(
        engine.position(pid).unwrap().actual_exposure().as_money(),
        approved_economic
    );
    assert_eq!(approved_economic, usd(5, 60));
}

#[test]
fn cancel_releases_unused_reservation() {
    let mut engine = paper();
    let pid = open(&mut engine);
    let id = submit_remainder(&mut engine, pid);
    engine.accept(id).unwrap();
    engine.fill(fill_cmd(id, 3, px(80))).unwrap();
    assert!(engine.reserved_for(pid).cents() > 0);
    engine.cancel(id).unwrap();
    assert_eq!(engine.reserved_for(pid), Money::ZERO);
}

#[test]
fn reject_releases_unused_reservation() {
    let mut engine = paper();
    let pid = open(&mut engine);
    let id = submit_remainder(&mut engine, pid);
    engine.accept(id).unwrap();
    assert!(engine.reserved_for(pid).cents() > 0);
    engine.reject(id).unwrap();
    assert_eq!(engine.reserved_for(pid), Money::ZERO);
}

#[test]
fn expire_releases_unused_reservation() {
    let mut engine = paper();
    let pid = open(&mut engine);
    let id = submit_remainder(&mut engine, pid);
    engine.accept(id).unwrap();
    engine.fill(fill_cmd(id, 3, px(80))).unwrap();
    engine.expire(id).unwrap();
    assert_eq!(engine.reserved_for(pid), Money::ZERO);
    assert_eq!(engine.order_state(id), Some(OrderState::Expired));
}

#[test]
fn unknown_retains_reservation() {
    let mut engine = paper();
    let pid = open(&mut engine);
    let id = submit_remainder(&mut engine, pid);
    engine.accept(id).unwrap();
    let reserved = engine.reserved_for(pid);
    engine.unknown(id).unwrap();
    assert_eq!(engine.reserved_for(pid), reserved);
    assert!(reserved.cents() > 0);
    assert_eq!(engine.order_state(id), Some(OrderState::Unknown));
}

#[test]
fn unknown_requires_reconciliation() {
    let mut engine = paper();
    let pid = open(&mut engine);
    let id = submit_remainder(&mut engine, pid);
    engine.unknown(id).unwrap();
    assert!(engine.recon_state().blocks_new_exposure());
    let next = engine.decide_entry(&not_more_than(pid, px(80), usd(0, 80)));
    assert!(matches!(
        next,
        RiskDecision::Rejected {
            reason: RiskRejectReason::ReconciliationRequired,
            ..
        }
    ));
    assert_eq!(engine.execute(next), Err(ExecutionError::NotApproved));
    engine.reconcile(id, ReconcileOutcome::Found).unwrap();
}

#[test]
fn game_locked_blocks_new_entry() {
    let mut engine = paper();
    let pid = open(&mut engine);
    let id = submit_remainder(&mut engine, pid);
    engine.accept(id).unwrap();
    engine.fill(fill_cmd(id, 3, px(80))).unwrap();
    let (ex, recv) = ts();
    engine.lock_game(GameId::from_raw(10), ex, recv).unwrap();
    let again = engine.decide_entry(&remainder(pid, px(80)));
    assert!(matches!(
        again,
        RiskDecision::Rejected {
            reason: RiskRejectReason::GameLocked,
            ..
        }
    ));
    let later = engine.decide_entry(&remainder(pid, px(81)));
    assert!(matches!(
        later,
        RiskDecision::Rejected {
            reason: RiskRejectReason::GameLocked,
            ..
        }
    ));
}

#[test]
fn game_locked_does_not_liquidate_existing_exposure() {
    let mut engine = paper();
    let pid = open(&mut engine);
    let id = submit_remainder(&mut engine, pid);
    engine.accept(id).unwrap();
    engine.fill(fill_cmd(id, 3, px(80))).unwrap();
    let (ex, recv) = ts();
    engine.lock_game(GameId::from_raw(10), ex, recv).unwrap();
    let pos = engine.position(pid).unwrap();
    assert_eq!(pos.actual_exposure().as_money(), usd(2, 40));
    assert_eq!(pos.filled_quantity(), Contracts::from_u32(3));
    assert!(!pos.lifecycle().is_flat());
    assert_ne!(pos.lifecycle(), PositionLifecycle::Flat);
    assert!(pos.game_lock().is_locked());
    assert_eq!(engine.order_state(id), Some(OrderState::Cancelled));
    assert_eq!(engine.reserved_for(pid), Money::ZERO);
}

#[test]
fn entry_above_83_cannot_execute() {
    let mut engine = paper();
    let pid = open(&mut engine);
    let rejected = engine.decide_entry(&remainder(pid, px(84)));
    assert!(matches!(
        rejected,
        RiskDecision::Rejected {
            reason: RiskRejectReason::EntryPriceAboveMaximum,
            ..
        }
    ));
    assert_eq!(engine.execute(rejected), Err(ExecutionError::NotApproved));

    let forged_intent = remainder(pid, px(84));
    let forged = ApprovedTradeIntent::from_risk_engine(
        RiskGrant::for_risk_engine(),
        RiskDecisionId::generate(),
        engine.snapshot().snapshot_id(),
        &forged_intent,
        ClientOrderId::from_raw(99),
        Contracts::from_u32(1),
        usd(0, 84),
        usd(0, 84),
        usd(6, 25),
        usd(5, 41),
        Money::ZERO,
        FeeModelId::zero_placeholder(),
    );
    assert_eq!(
        engine.execute_approved(forged),
        Err(ExecutionError::EntryPriceAboveMaximum)
    );
}

#[test]
fn fee_model_remains_injected_and_zero_is_placeholder() {
    let engine = paper();
    assert_eq!(engine.fee_model_id(), FeeModelId::zero_placeholder());
    assert!(
        engine
            .fee_model_id()
            .as_str()
            .contains("not-kalshi-economics")
    );
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
fn zero_fee_model_is_only_the_paper_default() {
    let snap = snapshot50();
    let mut engine = PaperExecutionEngine::new(
        snap.clone(),
        RiskConfig::mlb_paper_experimental().unwrap(),
        TestPerContractFee,
    );
    let pid = engine.open_game(
        StrategyId::from_raw(1),
        GameId::from_raw(10),
        MarketId::from_raw(2),
        Side::Yes,
    );
    assert_ne!(engine.fee_model_id(), FeeModelId::zero_placeholder());
    let d = engine.decide_entry(&remainder(pid, px(80)));
    let approved = approve(d.clone());
    assert!(approved.fee_estimate().cents() > 0);
    let id = engine.execute(d).unwrap();
    engine.accept(id).unwrap();
    let fill = engine.fill(fill_cmd(id, 1, px(80))).unwrap();
    assert!(fill.fee().amount().cents() > 0);
    assert_eq!(
        fill.premium(),
        contract_premium(Contracts::from_u32(1), px(80)).unwrap()
    );
    let _cap: &dyn momento_risk::AvailableCapacity =
        &SnapshotPaperBalance::from_bankroll(snap.bankroll());
}

#[test]
fn partial_then_another_approved_order_is_one_position() {
    let mut engine = paper();
    let pid = open(&mut engine);
    let first = submit_remainder(&mut engine, pid);
    engine.accept(first).unwrap();
    engine.fill(fill_cmd(first, 3, px(80))).unwrap();
    engine.cancel(first).unwrap();
    assert_eq!(
        engine
            .position(pid)
            .unwrap()
            .remaining_economic_target()
            .unwrap(),
        usd(3, 85)
    );
    let d = engine.decide_entry(&not_more_than(pid, px(80), usd(1, 0)));
    let second = engine.execute(d).unwrap();
    engine.accept(second).unwrap();
    engine.fill(fill_cmd(second, 1, px(80))).unwrap();
    let d = engine.decide_entry(&remainder(pid, px(80)));
    let third = engine.execute(d).unwrap();
    engine.accept(third).unwrap();
    engine.fill(fill_cmd(third, 3, px(80))).unwrap();
    let pos = engine.position(pid).unwrap();
    assert_eq!(pos.id(), pid);
    assert_eq!(pos.fill_history().len(), 3);
    assert_eq!(pos.actual_exposure().as_money(), usd(5, 60));
    assert!(pos.actual_exposure().as_money().cents() <= usd(6, 25).cents());
}

#[test]
fn cumulative_fills_cannot_exceed_original_budget() {
    let mut engine = paper();
    let pid = open(&mut engine);
    let id = submit_remainder(&mut engine, pid);
    engine.accept(id).unwrap();
    engine.fill(fill_cmd(id, 7, px(80))).unwrap();
    assert!(
        engine
            .position(pid)
            .unwrap()
            .actual_exposure()
            .as_money()
            .cents()
            <= usd(6, 25).cents()
    );
    let again = engine.decide_entry(&remainder(pid, px(80)));
    match again {
        RiskDecision::Rejected { .. } => {}
        RiskDecision::Approved(a) => {
            assert!(a.max_economic().cents() <= 0 || a.max_contracts().get() == 0);
        }
    }
}

#[test]
fn audit_events_reconstruct_order_fill_lifecycle() {
    let mut engine = paper();
    let pid = open(&mut engine);
    let id = submit_remainder(&mut engine, pid);
    engine.accept(id).unwrap();
    engine.fill(fill_cmd(id, 3, px(80))).unwrap();
    engine.cancel(id).unwrap();
    let events = engine.audit_events();
    assert!(
        events
            .iter()
            .any(|e| matches!(e, AuditEvent::RiskApproval { .. }))
    );
    assert!(
        events
            .iter()
            .any(|e| matches!(e, AuditEvent::OrderSubmitted { .. }))
    );
    assert!(
        events
            .iter()
            .any(|e| matches!(e, AuditEvent::OrderWorking { .. }))
    );
    assert!(
        events
            .iter()
            .any(|e| matches!(e, AuditEvent::OrderPartiallyFilled { .. }))
    );
    assert!(
        events
            .iter()
            .any(|e| matches!(e, AuditEvent::OrderCancelled { .. }))
    );
    assert!(
        events
            .iter()
            .any(|e| matches!(e, AuditEvent::PositionUpdated { .. }))
    );
}
