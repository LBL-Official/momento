//! Deterministic YES-bid observation tests (strategy spec 2026-08-24).
//!
//! Qualifying price is Kalshi `yes_bid_dollars` → `MarketEvent.bid`.
//! These tests never set a venue mid, never treat last as the signal, and
//! never treat ask as the 80/81/89 observation.

use std::sync::Arc;
use std::thread;

use chrono::{TimeZone, Utc};
use momento_core::{
    AdditionalExposure, AuditEvent, Bps, ClientOrderId, Contracts, EntryStyle, ExchangeTimestamp,
    Fee, FeeKind, Fill, FillId, GameId, KillSwitch, MarketEvent, MarketId, Money, Position,
    PositionId, Price, ReceivedAt, ReconciliationState, RiskDecision, RiskRejectReason, Side,
    SnapshotSource, StrategyId, WeeklyBankrollSnapshot,
};
use momento_risk::{PaperRiskEngine, RiskConfig};
use momento_strategy_mlb::{
    MlbContext, MlbDirective, MlbGamePhase, MlbIssue, MlbStrategy, QuoteReject,
};

fn usd(d: i64, c: u8) -> Money {
    Money::from_usd(d, c).unwrap()
}

fn px(c: u16) -> Price {
    Price::from_cents(c).unwrap()
}

fn ts(sec: u32) -> (ExchangeTimestamp, ReceivedAt) {
    let t = Utc
        .with_ymd_and_hms(2026, 8, 24, 18, 0, sec)
        .single()
        .unwrap();
    (ExchangeTimestamp::from_utc(t), ReceivedAt::from_utc(t))
}

fn yes_bid_event(bid: u16, ask: u16, last: Option<u16>, sec: u32) -> MarketEvent {
    let (exchange_ts, received_at) = ts(sec);
    MarketEvent {
        game_id: GameId::from_raw(10),
        market_id: MarketId::from_raw(2),
        side: Some(Side::Yes),
        exchange_ts,
        received_at,
        last: last.map(px),
        bid: Some(px(bid)),
        ask: Some(px(ask)),
        mid: None,
        bid_depth: Some(5),
        ask_depth: Some(4),
        game_state: None,
    }
}

fn ctx<'a>(
    event: &'a MarketEvent,
    position: Option<&'a Position>,
    pid: Option<PositionId>,
) -> MlbContext<'a> {
    MlbContext {
        event,
        position,
        assigned_position_id: pid,
        recon: ReconciliationState::Healthy,
        kill_switch: KillSwitch::Armed,
        data_stale: false,
        has_working_entry: false,
        unknown_entry_order: false,
        has_working_liquidation: false,
        unknown_liquidation_order: false,
    }
}

fn pid() -> PositionId {
    PositionId::from_raw(42)
}

fn snapshot50() -> WeeklyBankrollSnapshot {
    let now = Utc
        .with_ymd_and_hms(2026, 8, 24, 16, 0, 0)
        .single()
        .unwrap();
    WeeklyBankrollSnapshot::capture(usd(50, 0), Bps::PCT_12_5, now, SnapshotSource::Test).unwrap()
}

fn empty_position_for(snap: &WeeklyBankrollSnapshot, id: PositionId, game: GameId) -> Position {
    Position::new_for_game(
        id,
        game,
        StrategyId::from_raw(1),
        snap.snapshot_id(),
        snap.max_position_budget(),
        Some(MarketId::from_raw(2)),
        Some(Side::Yes),
    )
}

fn filled_partial() -> Position {
    let snap = snapshot50();
    let mut pos = empty_position_for(&snap, pid(), GameId::from_raw(10));
    let (ex, recv) = ts(1);
    pos.apply_entry_fill(Fill::new(
        FillId::from_raw(1),
        pid(),
        ClientOrderId::from_raw(1),
        None,
        Contracts::from_u32(3),
        px(80),
        usd(2, 40),
        Fee::zero(FeeKind::Entry),
        ex,
        recv,
    ))
    .unwrap();
    pos
}

fn builds(dirs: &[MlbDirective]) -> Vec<&momento_core::TradeIntent> {
    dirs.iter()
        .filter_map(|d| match d {
            MlbDirective::Build(i) => Some(i),
            _ => None,
        })
        .collect()
}

fn confirm_80_81(s: &mut MlbStrategy, assigned: PositionId) -> Vec<MlbDirective> {
    let e80 = yes_bid_event(80, 81, None, 1);
    s.observe(&ctx(&e80, None, Some(assigned)));
    let e81 = yes_bid_event(81, 82, None, 2);
    s.observe(&ctx(&e81, None, Some(assigned))).directives
}

#[test]
fn a_yes_bid_79_no_signal() {
    let mut s = MlbStrategy::new();
    let e = yes_bid_event(79, 80, None, 1);
    let turn = s.observe(&ctx(&e, None, Some(pid())));
    assert!(builds(&turn.directives).is_empty());
    assert!(s.first_80(GameId::from_raw(10)).is_none());
    assert_eq!(s.phase(GameId::from_raw(10)), MlbGamePhase::Watching);
}

#[test]
fn b_yes_bid_80_first_80() {
    let mut s = MlbStrategy::new();
    let e = yes_bid_event(80, 81, None, 1);
    let turn = s.observe(&ctx(&e, None, Some(pid())));
    assert!(
        turn.audit
            .iter()
            .any(|a| matches!(a, AuditEvent::First80Observed { .. }))
    );
    assert_eq!(s.first_80(GameId::from_raw(10)).unwrap().bid, px(80));
    assert!(builds(&turn.directives).is_empty());
    assert_eq!(
        s.phase(GameId::from_raw(10)),
        MlbGamePhase::WaitingFor81Confirmation
    );
}

#[test]
fn c_yes_bid_80_then_81_entry_eligible_trade_intent() {
    let mut s = MlbStrategy::new();
    let dirs = confirm_80_81(&mut s, pid());
    let intent = builds(&dirs)[0];
    assert_eq!(s.phase(GameId::from_raw(10)), MlbGamePhase::EntryEligible);
    assert_eq!(intent.build.style, EntryStyle::MakerOnly);
    assert_eq!(intent.build.limit_price, px(81));
    assert_eq!(intent.build.side, Side::Yes);
    assert_eq!(intent.build.position_id, pid());
}

#[test]
fn d_yes_bid_80_81_82_trade_intent_stays_within_80_83() {
    let mut s = MlbStrategy::new();
    confirm_80_81(&mut s, pid());
    let e82 = yes_bid_event(82, 83, None, 3);
    let dirs = s.observe(&ctx(&e82, None, Some(pid()))).directives;
    let intent = builds(&dirs)[0];
    let limit = intent.build.limit_price.cents();
    assert!((80..=83).contains(&limit));
    assert!(limit < 83);
    assert_eq!(intent.build.style, EntryStyle::MakerOnly);
}

#[test]
fn e_yes_bid_89_permanent_game_locked() {
    let mut s = MlbStrategy::new();
    let e = yes_bid_event(89, 90, None, 1);
    s.observe(&ctx(&e, None, None));
    assert_eq!(s.phase(GameId::from_raw(10)), MlbGamePhase::GameLocked);
    assert!(s.first_89(GameId::from_raw(10)).is_some());
}

#[test]
fn f_yes_bid_89_does_not_liquidate_partial_position() {
    let mut s = MlbStrategy::new();
    confirm_80_81(&mut s, pid());
    let pos = filled_partial();
    let e = yes_bid_event(89, 90, None, 3);
    let turn = s.observe(&ctx(&e, Some(&pos), Some(pid())));
    assert!(builds(&turn.directives).is_empty());
    assert!(
        !turn
            .directives
            .iter()
            .any(|d| matches!(d, MlbDirective::ExecuteStop(_)))
    );
    assert_eq!(pos.id(), pid());
    assert_eq!(pos.actual_exposure().as_money(), usd(2, 40));
    assert_eq!(pos.filled_quantity().get(), 3);
    assert_eq!(s.phase(GameId::from_raw(10)), MlbGamePhase::GameLocked);
}

#[test]
fn g_yes_bid_89_then_82_does_not_resume_entry() {
    let mut s = MlbStrategy::new();
    s.observe(&ctx(&yes_bid_event(89, 90, None, 1), None, None));
    let turn = s.observe(&ctx(&yes_bid_event(82, 83, None, 2), None, Some(pid())));
    assert!(builds(&turn.directives).is_empty());
    assert_eq!(s.phase(GameId::from_raw(10)), MlbGamePhase::GameLocked);
}

#[test]
fn h_last_price_99_with_yes_bid_79_does_not_trigger() {
    let mut s = MlbStrategy::new();
    let e = yes_bid_event(79, 80, Some(99), 1);
    let turn = s.observe(&ctx(&e, None, Some(pid())));
    assert!(s.first_80(GameId::from_raw(10)).is_none());
    assert!(s.first_89(GameId::from_raw(10)).is_none());
    assert!(builds(&turn.directives).is_empty());
    assert_eq!(s.phase(GameId::from_raw(10)), MlbGamePhase::Watching);
}

#[test]
fn i_yes_ask_99_with_yes_bid_79_does_not_trigger() {
    let mut s = MlbStrategy::new();
    let e = yes_bid_event(79, 99, None, 1);
    let turn = s.observe(&ctx(&e, None, Some(pid())));
    assert!(s.first_80(GameId::from_raw(10)).is_none());
    assert!(s.first_89(GameId::from_raw(10)).is_none());
    assert!(builds(&turn.directives).is_empty());
}

#[test]
fn j_missing_yes_bid_fails_closed() {
    let mut s = MlbStrategy::new();
    let mut e = yes_bid_event(80, 81, None, 1);
    e.bid = None;
    let turn = s.observe(&ctx(&e, None, Some(pid())));
    assert!(s.first_80(GameId::from_raw(10)).is_none());
    assert!(builds(&turn.directives).is_empty());
    assert!(matches!(
        turn.issue,
        Some(MlbIssue::InsufficientQuote(QuoteReject::MissingBid))
    ));
}

#[test]
fn k_sub_cent_domain_price_cannot_enter_observation() {
    assert!(Price::from_cents(101).is_err());
    assert_eq!(Price::from_cents(80).unwrap().cents(), 80);
}

fn remainder(pos: &Position) -> momento_core::TradeIntent {
    momento_core::TradeIntent::build(momento_core::BuildPositionIntent {
        strategy_id: StrategyId::from_raw(1),
        game_id: pos.game_id(),
        market_id: MarketId::from_raw(2),
        side: Side::Yes,
        position_id: pos.id(),
        limit_price: px(81),
        style: EntryStyle::MakerOnly,
        additional: AdditionalExposure::RemainderOfApprovedBudget,
    })
}

fn apply_entry_fill(pos: &mut Position, order: ClientOrderId) {
    let (ex, recv) = ts(1);
    pos.apply_entry_fill(Fill::new(
        FillId::generate(),
        pos.id(),
        order,
        None,
        Contracts::from_u32(3),
        px(80),
        usd(2, 40),
        Fee::zero(FeeKind::Entry),
        ex,
        recv,
    ))
    .unwrap();
}

fn open_five(e: &PaperRiskEngine, snap: &WeeklyBankrollSnapshot) {
    for n in 1..=5 {
        let mut pos = empty_position_for(snap, PositionId::from_raw(n), GameId::from_raw(100 + n));
        let decision = e.decide_entry(&remainder(&pos), &pos);
        let approved = match decision {
            RiskDecision::Approved(a) => a,
            other => panic!("expected approval for slot {n}, got {other:?}"),
        };
        apply_entry_fill(&mut pos, approved.client_order_id());
        e.on_fill(pos.fill_history().last().unwrap());
        e.on_cancel(approved.client_order_id());
        assert_eq!(snap.max_position_budget(), usd(6, 25));
    }
    assert_eq!(e.open_slot_count(), 5);
    assert_eq!(e.max_open_positions(), 5);
}

#[test]
fn l_sixth_simultaneous_mlb_position_id_is_rejected_by_risk() {
    let snap = snapshot50();
    let e = PaperRiskEngine::paper(snap.clone(), RiskConfig::mlb_paper_experimental().unwrap());
    open_five(&e, &snap);
    let mut strategy = MlbStrategy::new();
    let sixth_game = GameId::from_raw(106);
    let sixth_pid = PositionId::from_raw(6);
    let mut e80 = yes_bid_event(80, 81, None, 1);
    e80.game_id = sixth_game;
    strategy.observe(&ctx(&e80, None, Some(sixth_pid)));
    let mut e81 = yes_bid_event(81, 82, None, 2);
    e81.game_id = sixth_game;
    let dirs = strategy
        .observe(&ctx(&e81, None, Some(sixth_pid)))
        .directives;
    let intent = builds(&dirs)[0];
    let sixth_pos = empty_position_for(&snap, sixth_pid, sixth_game);
    match e.decide_entry(intent, &sixth_pos) {
        RiskDecision::Rejected {
            reason: RiskRejectReason::PositionLimitExceeded,
            ..
        } => {}
        other => panic!("expected PositionLimitExceeded, got {other:?}"),
    }
    assert_eq!(e.open_slot_count(), 5);
}

#[test]
fn m_concurrent_approvals_cannot_create_a_sixth_position() {
    let snap = snapshot50();
    let e = Arc::new(PaperRiskEngine::paper(
        snap.clone(),
        RiskConfig::mlb_paper_experimental().unwrap(),
    ));
    open_five(&e, &snap);
    let p6 = Arc::new(empty_position_for(
        &snap,
        PositionId::from_raw(6),
        GameId::from_raw(106),
    ));
    let p7 = Arc::new(empty_position_for(
        &snap,
        PositionId::from_raw(7),
        GameId::from_raw(107),
    ));
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
fn n_existing_five_position_limit_remains_enforced() {
    let snap = snapshot50();
    let e = PaperRiskEngine::paper(snap.clone(), RiskConfig::mlb_paper_experimental().unwrap());
    assert_eq!(e.max_open_positions(), 5);
    open_five(&e, &snap);
    for n in 6..=8 {
        let pos = empty_position_for(&snap, PositionId::from_raw(n), GameId::from_raw(100 + n));
        match e.decide_entry(&remainder(&pos), &pos) {
            RiskDecision::Rejected {
                reason: RiskRejectReason::PositionLimitExceeded,
                ..
            } => {}
            other => panic!("slot {n} should be capped, got {other:?}"),
        }
    }
    assert_eq!(e.open_slot_count(), 5);
    assert_eq!(snap.bankroll(), usd(50, 0));
    assert_eq!(snap.max_position_budget(), usd(6, 25));
}

#[test]
fn yes_bid_40_triggers_execute_stop_from_actual_entry_vwap() {
    let mut s = MlbStrategy::new();
    confirm_80_81(&mut s, pid());
    let pos = filled_partial();
    let e = yes_bid_event(40, 41, Some(80), 4);
    let turn = s.observe(&ctx(&e, Some(&pos), Some(pid())));
    let exec = turn
        .directives
        .iter()
        .find_map(|d| match d {
            MlbDirective::ExecuteStop(x) => Some(x),
            _ => None,
        })
        .expect("ExecuteStop");
    assert_eq!(exec.quantity.get(), 3);
    assert_eq!(exec.suggested_limit, px(40));
    assert_eq!(exec.position_id, pid());
    assert_eq!(exec.market_id, MarketId::from_raw(2));
    assert_eq!(exec.side, Side::Yes);
}

#[test]
fn yes_bid_41_does_not_trigger_50_percent_stop() {
    let mut s = MlbStrategy::new();
    confirm_80_81(&mut s, pid());
    let pos = filled_partial();
    let e = yes_bid_event(41, 42, Some(80), 4);
    let turn = s.observe(&ctx(&e, Some(&pos), Some(pid())));
    assert!(
        !turn
            .directives
            .iter()
            .any(|d| matches!(d, MlbDirective::ExecuteStop(_)))
    );
}

#[test]
fn last_and_ask_cannot_trigger_stop_when_yes_bid_is_above_threshold() {
    let mut s = MlbStrategy::new();
    confirm_80_81(&mut s, pid());
    let pos = filled_partial();
    let last_not_bid = yes_bid_event(81, 82, Some(40), 4);
    let turn = s.observe(&ctx(&last_not_bid, Some(&pos), Some(pid())));
    assert!(
        !turn
            .directives
            .iter()
            .any(|d| matches!(d, MlbDirective::ExecuteStop(_)))
    );
}

#[test]
fn unknown_liquidation_does_not_resubmit_execute_stop() {
    let mut s = MlbStrategy::new();
    confirm_80_81(&mut s, pid());
    let pos = filled_partial();
    let e = yes_bid_event(40, 41, None, 4);
    let mut c = ctx(&e, Some(&pos), Some(pid()));
    c.unknown_liquidation_order = true;
    let turn = s.observe(&c);
    assert!(
        !turn
            .directives
            .iter()
            .any(|d| matches!(d, MlbDirective::ExecuteStop(_)))
    );
}

#[test]
fn working_liquidation_does_not_duplicate_execute_stop() {
    let mut s = MlbStrategy::new();
    confirm_80_81(&mut s, pid());
    let pos = filled_partial();
    let e = yes_bid_event(40, 41, None, 4);
    let mut c = ctx(&e, Some(&pos), Some(pid()));
    c.has_working_liquidation = true;
    let turn = s.observe(&c);
    assert!(
        !turn
            .directives
            .iter()
            .any(|d| matches!(d, MlbDirective::ExecuteStop(_)))
    );
}
