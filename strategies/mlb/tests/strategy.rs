//! Milestone 6 MLB strategy tests.

use chrono::{TimeZone, Utc};
use momento_core::{
    AdditionalExposure, AuditEvent, Bps, ClientOrderId, Contracts, EntryStyle, ExchangeTimestamp,
    Fee, FeeKind, Fill, FillId, GameId, KillSwitch, MarketEvent, MarketId, Money, Position,
    PositionExitCause, PositionId, PositionLifecycle, Price, ReceivedAt, ReconciliationState, Side,
    SnapshotSource, StrategyId, WeeklyBankrollSnapshot,
};
use momento_strategy_mlb::{
    MLB_STRATEGY_ID, MlbContext, MlbDirective, MlbGamePhase, MlbStrategy, QuoteReject, StopRounding,
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

fn event(_mid: u16, bid: u16, ask: u16, side: Side, sec: u32) -> MarketEvent {
    let (exchange_ts, received_at) = ts(sec);
    MarketEvent {
        game_id: GameId::from_raw(10),
        market_id: MarketId::from_raw(2),
        side: Some(side),
        exchange_ts,
        received_at,
        last: None,
        bid: Some(px(bid)),
        ask: Some(px(ask)),
        mid: None,
        bid_depth: Some(5),
        ask_depth: Some(4),
        game_state: Some("t1-0".into()),
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

fn empty_position() -> Position {
    let snap = snapshot50();
    Position::new_for_game(
        pid(),
        GameId::from_raw(10),
        StrategyId::from_raw(1),
        snap.snapshot_id(),
        snap.max_position_budget(),
        Some(MarketId::from_raw(2)),
        Some(Side::Yes),
    )
}

fn filled_position(premium: Money, qty: u32, fill_raw: u128) -> Position {
    let mut pos = empty_position();
    let (ex, recv) = ts(1);
    pos.apply_entry_fill(Fill::new(
        FillId::from_raw(fill_raw),
        pid(),
        ClientOrderId::from_raw(fill_raw),
        None,
        Contracts::from_u32(qty),
        px(80),
        premium,
        Fee::zero(FeeKind::Entry),
        ex,
        recv,
    ))
    .unwrap();
    pos
}

fn eligible(strategy: &mut MlbStrategy, assigned: PositionId) -> Vec<MlbDirective> {
    let e80 = event(80, 80, 81, Side::Yes, 1);
    strategy.observe(&ctx(&e80, None, Some(assigned)));
    let e81 = event(81, 81, 82, Side::Yes, 2);
    strategy
        .observe(&ctx(&e81, None, Some(assigned)))
        .directives
}

fn builds(dirs: &[MlbDirective]) -> Vec<&momento_core::TradeIntent> {
    dirs.iter()
        .filter_map(|d| match d {
            MlbDirective::Build(i) => Some(i),
            _ => None,
        })
        .collect()
}

#[test]
fn no_80_no_entry() {
    let mut s = MlbStrategy::new();
    let e = event(79, 79, 80, Side::Yes, 1);
    let turn = s.observe(&ctx(&e, None, Some(pid())));
    assert!(builds(&turn.directives).is_empty());
    assert_eq!(s.phase(GameId::from_raw(10)), MlbGamePhase::Watching);
}

#[test]
fn first_80_persisted() {
    let mut s = MlbStrategy::new();
    let e = event(80, 80, 81, Side::Yes, 1);
    let turn = s.observe(&ctx(&e, None, Some(pid())));
    assert!(
        turn.audit
            .iter()
            .any(|a| matches!(a, AuditEvent::First80Observed { .. }))
    );
    let first = s.first_80(GameId::from_raw(10)).unwrap();
    assert_eq!(first.bid, px(80));
    assert_eq!(first.mid, px(80));
    assert_eq!(first.side, Side::Yes);
    assert_eq!(first.game_state.as_deref(), Some("t1-0"));
    assert!(builds(&turn.directives).is_empty());
}

#[test]
fn duplicate_80_does_not_create_new_opportunity() {
    let mut s = MlbStrategy::new();
    let e = event(80, 80, 81, Side::Yes, 1);
    s.observe(&ctx(&e, None, Some(pid())));
    let first_ts = s.first_80(GameId::from_raw(10)).unwrap().exchange_ts;
    let turn = s.observe(&ctx(&e, None, Some(pid())));
    assert!(turn.audit.is_empty());
    assert_eq!(
        s.first_80(GameId::from_raw(10)).unwrap().exchange_ts,
        first_ts
    );
}

#[test]
fn first_80_waits_for_81() {
    let mut s = MlbStrategy::new();
    let e = event(80, 80, 81, Side::Yes, 1);
    s.observe(&ctx(&e, None, Some(pid())));
    assert_eq!(
        s.phase(GameId::from_raw(10)),
        MlbGamePhase::WaitingFor81Confirmation
    );
    let again = event(80, 80, 81, Side::Yes, 3);
    assert!(builds(&s.observe(&ctx(&again, None, Some(pid()))).directives).is_empty());
}

#[test]
fn eighty_then_81_same_side_entry_eligible() {
    let mut s = MlbStrategy::new();
    let dirs = eligible(&mut s, pid());
    assert!(!builds(&dirs).is_empty());
    assert_eq!(s.phase(GameId::from_raw(10)), MlbGamePhase::EntryEligible);
}

#[test]
fn eighty_side_a_81_side_b_does_not_confirm() {
    let mut s = MlbStrategy::new();
    let e80 = event(80, 80, 81, Side::Yes, 1);
    s.observe(&ctx(&e80, None, Some(pid())));
    let mut e81 = event(81, 81, 82, Side::No, 2);
    e81.market_id = MarketId::from_raw(3);
    let turn = s.observe(&ctx(&e81, None, Some(pid())));
    assert!(builds(&turn.directives).is_empty());
    assert_eq!(s.first_80(GameId::from_raw(10)).unwrap().side, Side::Yes);
    assert_eq!(
        s.phase(GameId::from_raw(10)),
        MlbGamePhase::WaitingFor81Confirmation
    );
}

#[test]
fn entry_prices_80_to_83_accepted() {
    for (mid, bid, ask, sec) in [
        (80, 80, 81, 3),
        (81, 81, 82, 4),
        (82, 82, 83, 5),
        (83, 82, 84, 6),
    ] {
        let mut s = MlbStrategy::new();
        eligible(&mut s, pid());
        let e = event(mid, bid, ask, Side::Yes, sec);
        let dirs = s.observe(&ctx(&e, None, Some(pid()))).directives;
        let intent = builds(&dirs)[0];
        assert_eq!(intent.build.style, EntryStyle::MakerOnly);
        let limit = intent.build.limit_price.cents();
        assert!((80..=83).contains(&limit), "mid={mid} limit={limit}");
        assert!(limit < ask);
    }
}

#[test]
fn above_83_pauses_entry() {
    let mut s = MlbStrategy::new();
    eligible(&mut s, pid());
    let e = event(84, 84, 85, Side::Yes, 3);
    let turn = s.observe(&ctx(&e, None, Some(pid())));
    assert!(builds(&turn.directives).is_empty());
    assert!(
        turn.directives
            .iter()
            .any(|d| matches!(d, MlbDirective::PauseEntry { .. }))
    );
    assert!(s.paused_above_max(GameId::from_raw(10)));
}

#[test]
fn above_83_does_not_lock_game() {
    let mut s = MlbStrategy::new();
    eligible(&mut s, pid());
    let e = event(84, 84, 85, Side::Yes, 3);
    s.observe(&ctx(&e, None, Some(pid())));
    assert_ne!(s.phase(GameId::from_raw(10)), MlbGamePhase::GameLocked);
    assert!(s.first_89(GameId::from_raw(10)).is_none());
}

#[test]
fn return_to_band_resumes_before_89() {
    let mut s = MlbStrategy::new();
    eligible(&mut s, pid());
    let high = event(84, 84, 85, Side::Yes, 3);
    s.observe(&ctx(&high, None, Some(pid())));
    let back = event(82, 82, 83, Side::Yes, 4);
    let turn = s.observe(&ctx(&back, None, Some(pid())));
    assert!(!builds(&turn.directives).is_empty());
    assert!(!s.paused_above_max(GameId::from_raw(10)));
}

#[test]
fn partial_fill_does_not_complete_entry() {
    let mut s = MlbStrategy::new();
    eligible(&mut s, pid());
    let pos = filled_position(usd(2, 40), 3, 1);
    let e = event(81, 81, 82, Side::Yes, 3);
    s.observe(&ctx(&e, Some(&pos), Some(pid())));
    assert_eq!(
        s.phase(GameId::from_raw(10)),
        MlbGamePhase::PositionBuilding
    );
    assert_ne!(pos.lifecycle(), PositionLifecycle::OpenComplete);
}

#[test]
fn partial_fill_preserves_same_position_id() {
    let mut s = MlbStrategy::new();
    eligible(&mut s, pid());
    let pos = filled_position(usd(2, 40), 3, 1);
    let e = event(81, 81, 82, Side::Yes, 3);
    let dirs = s.observe(&ctx(&e, Some(&pos), Some(pid()))).directives;
    assert_eq!(builds(&dirs)[0].build.position_id, pid());
    assert_eq!(pos.id(), pid());
}

#[test]
fn remaining_target_uses_actual_filled_state() {
    let mut s = MlbStrategy::new();
    eligible(&mut s, pid());
    let pos = filled_position(usd(2, 40), 3, 1);
    assert_eq!(pos.remaining_economic_target().unwrap(), usd(3, 85));
    let e = event(81, 81, 82, Side::Yes, 3);
    let turn = s.observe(&ctx(&e, Some(&pos), Some(pid())));
    let intent = builds(&turn.directives)[0];
    assert!(matches!(
        intent.build.additional,
        AdditionalExposure::RemainderOfApprovedBudget
    ));
}

#[test]
fn multiple_fills_one_position_id() {
    let mut pos = filled_position(usd(2, 40), 3, 1);
    let (ex, recv) = ts(2);
    pos.apply_entry_fill(Fill::new(
        FillId::from_raw(2),
        pid(),
        ClientOrderId::from_raw(2),
        None,
        Contracts::from_u32(1),
        px(80),
        usd(0, 80),
        Fee::zero(FeeKind::Entry),
        ex,
        recv,
    ))
    .unwrap();
    let mut s = MlbStrategy::new();
    eligible(&mut s, pid());
    let e = event(81, 81, 82, Side::Yes, 4);
    let turn = s.observe(&ctx(&e, Some(&pos), Some(pid())));
    let intent = builds(&turn.directives)[0];
    assert_eq!(intent.build.position_id, pid());
    assert_eq!(pos.fill_history().len(), 2);
}

#[test]
fn multiple_client_order_ids_one_position_id() {
    let mut s = MlbStrategy::new();
    let first = eligible(&mut s, pid());
    let pos = filled_position(usd(2, 40), 3, 1);
    let e = event(82, 82, 83, Side::Yes, 5);
    let second = s.observe(&ctx(&e, Some(&pos), Some(pid()))).directives;
    assert_eq!(builds(&first)[0].build.position_id, pid());
    assert_eq!(builds(&second)[0].build.position_id, pid());
}

#[test]
fn eighty_nine_cancels_entry_management() {
    let mut s = MlbStrategy::new();
    eligible(&mut s, pid());
    let e = event(89, 89, 90, Side::Yes, 3);
    let mut c = ctx(&e, None, Some(pid()));
    c.has_working_entry = true;
    let turn = s.observe(&c);
    assert!(
        turn.directives
            .iter()
            .any(|d| matches!(d, MlbDirective::CancelRemainingEntries { .. }))
    );
}

#[test]
fn eighty_nine_permanently_game_locks() {
    let mut s = MlbStrategy::new();
    eligible(&mut s, pid());
    let e = event(89, 89, 90, Side::Yes, 3);
    s.observe(&ctx(&e, None, Some(pid())));
    assert_eq!(s.phase(GameId::from_raw(10)), MlbGamePhase::GameLocked);
    assert!(s.first_89(GameId::from_raw(10)).is_some());
}

#[test]
fn eighty_nine_zero_position_prevents_future_entry() {
    let mut s = MlbStrategy::new();
    let e = event(89, 89, 90, Side::Yes, 1);
    let turn = s.observe(&ctx(&e, None, None));
    assert!(builds(&turn.directives).is_empty());
    assert_eq!(s.phase(GameId::from_raw(10)), MlbGamePhase::GameLocked);
    let later = event(81, 81, 82, Side::Yes, 2);
    assert!(builds(&s.observe(&ctx(&later, None, Some(pid()))).directives).is_empty());
}

#[test]
fn eighty_nine_partial_preserves_existing_position() {
    let mut s = MlbStrategy::new();
    eligible(&mut s, pid());
    let pos = filled_position(usd(2, 40), 3, 1);
    let e = event(89, 89, 90, Side::Yes, 3);
    s.observe(&ctx(&e, Some(&pos), Some(pid())));
    assert_eq!(pos.id(), pid());
    assert_eq!(pos.actual_exposure().as_money(), usd(2, 40));
    assert_eq!(s.phase(GameId::from_raw(10)), MlbGamePhase::GameLocked);
}

#[test]
fn eighty_nine_does_not_liquidate() {
    let mut s = MlbStrategy::new();
    eligible(&mut s, pid());
    let pos = filled_position(usd(2, 40), 3, 1);
    let e = event(89, 89, 90, Side::Yes, 3);
    let turn = s.observe(&ctx(&e, Some(&pos), Some(pid())));
    assert!(builds(&turn.directives).is_empty());
    assert_ne!(pos.lifecycle(), PositionLifecycle::LiquidationActive);
    assert_ne!(pos.lifecycle(), PositionLifecycle::Flat);
}

#[test]
fn return_to_band_after_89_does_not_resume() {
    let mut s = MlbStrategy::new();
    eligible(&mut s, pid());
    s.observe(&ctx(&event(89, 89, 90, Side::Yes, 3), None, Some(pid())));
    let turn = s.observe(&ctx(&event(81, 81, 82, Side::Yes, 4), None, Some(pid())));
    assert!(builds(&turn.directives).is_empty());
}

#[test]
fn working_entry_at_89_is_cancelled_through_architecture() {
    let mut s = MlbStrategy::new();
    eligible(&mut s, pid());
    let e = event(89, 89, 90, Side::Yes, 3);
    let mut c = ctx(&e, None, Some(pid()));
    c.has_working_entry = true;
    let turn = s.observe(&c);
    match &turn.directives[0] {
        MlbDirective::CancelRemainingEntries {
            game_id,
            position_id,
        } => {
            assert_eq!(*game_id, GameId::from_raw(10));
            assert_eq!(*position_id, Some(pid()));
        }
        other => panic!("expected cancel, got {other:?}"),
    }
}

#[test]
fn cancellation_unknown_does_not_permit_replacement_entry() {
    let mut s = MlbStrategy::new();
    eligible(&mut s, pid());
    let e89 = event(89, 89, 90, Side::Yes, 3);
    let mut c = ctx(&e89, None, Some(pid()));
    c.unknown_entry_order = true;
    c.has_working_entry = true;
    s.observe(&c);
    let e82 = event(82, 82, 83, Side::Yes, 4);
    let mut c2 = ctx(&e82, None, Some(pid()));
    c2.unknown_entry_order = true;
    assert!(builds(&s.observe(&c2).directives).is_empty());
}

#[test]
fn genuine_fill_around_cancellation_remains_authoritative() {
    let mut s = MlbStrategy::new();
    eligible(&mut s, pid());
    let pos = filled_position(usd(2, 40), 3, 1);
    let e = event(89, 89, 90, Side::Yes, 3);
    s.observe(&ctx(&e, Some(&pos), Some(pid())));
    assert_eq!(pos.fill_history().len(), 1);
    assert_eq!(pos.actual_exposure().as_money(), usd(2, 40));
}

#[test]
fn stale_data_cannot_trigger_entry() {
    let mut s = MlbStrategy::new();
    let e = event(80, 80, 81, Side::Yes, 1);
    let mut c = ctx(&e, None, Some(pid()));
    c.data_stale = true;
    let turn = s.observe(&c);
    assert!(s.first_80(GameId::from_raw(10)).is_none());
    assert!(matches!(
        turn.issue,
        Some(momento_strategy_mlb::MlbIssue::InsufficientQuote(
            QuoteReject::Stale
        ))
    ));
}

#[test]
fn invalid_bid_ask_cannot_trigger_entry() {
    let mut s = MlbStrategy::new();
    let mut e = event(80, 82, 81, Side::Yes, 1);
    let turn = s.observe(&ctx(&e, None, Some(pid())));
    assert!(s.first_80(GameId::from_raw(10)).is_none());
    assert!(matches!(
        turn.issue,
        Some(momento_strategy_mlb::MlbIssue::InsufficientQuote(
            QuoteReject::BidAskInverted
        ))
    ));
    e.bid = None;
    let turn = s.observe(&ctx(&e, None, Some(pid())));
    assert!(matches!(
        turn.issue,
        Some(momento_strategy_mlb::MlbIssue::InsufficientQuote(
            QuoteReject::MissingBid
        ))
    ));
}

#[test]
fn duplicate_market_events_are_idempotent() {
    let mut s = MlbStrategy::new();
    let dirs = eligible(&mut s, pid());
    let n = dirs.len();
    let e81 = event(81, 81, 82, Side::Yes, 2);
    let again = s.observe(&ctx(&e81, None, Some(pid())));
    assert!(again.directives.is_empty());
    assert_eq!(n, 1);
}

#[test]
fn restart_replay_preserves_first_80() {
    let mut s = MlbStrategy::new();
    let e = event(80, 80, 81, Side::Yes, 1);
    s.observe(&ctx(&e, None, Some(pid())));
    let mut restored = MlbStrategy::restore(s.snapshot());
    restored.observe(&ctx(&e, None, Some(pid())));
    let first = restored.first_80(GameId::from_raw(10)).unwrap();
    assert_eq!(first.bid, px(80));
    assert_eq!(first.mid, px(80));
    assert_eq!(
        restored.phase(GameId::from_raw(10)),
        MlbGamePhase::WaitingFor81Confirmation
    );
}

#[test]
fn restart_replay_preserves_game_locked() {
    let mut s = MlbStrategy::new();
    s.observe(&ctx(&event(89, 89, 90, Side::Yes, 1), None, None));
    let mut restored = MlbStrategy::restore(s.snapshot());
    assert_eq!(
        restored.phase(GameId::from_raw(10)),
        MlbGamePhase::GameLocked
    );
    assert!(
        builds(
            &restored
                .observe(&ctx(&event(81, 81, 82, Side::Yes, 2), None, Some(pid())))
                .directives
        )
        .is_empty()
    );
}

#[test]
fn crate_does_not_depend_on_kalshi_or_execution() {
    let manifest = include_str!("../Cargo.toml");
    assert!(!manifest.contains("momento-kalshi"));
    assert!(!manifest.contains("momento-execution"));
}

#[test]
fn risk_rejection_prevents_execution() {
    let mut s = MlbStrategy::new();
    let dirs = eligible(&mut s, pid());
    let intent = builds(&dirs)[0];
    let snap = snapshot50();
    let pos = Position::new_for_game(
        pid(),
        GameId::from_raw(10),
        StrategyId::from_raw(1),
        snap.snapshot_id(),
        snap.max_position_budget(),
        Some(MarketId::from_raw(2)),
        Some(Side::Yes),
    );
    let risk = momento_risk::PaperRiskEngine::paper(
        snap,
        momento_risk::RiskConfig::mlb_paper_experimental().unwrap(),
    );
    risk.trip_kill_switch();
    let decision = risk.decide_entry(intent, &pos);
    assert!(matches!(
        decision,
        momento_core::RiskDecision::Rejected { .. }
    ));
}

#[test]
fn reconciliation_unhealthy_prevents_new_entry() {
    let mut s = MlbStrategy::new();
    eligible(&mut s, pid());
    let e = event(81, 81, 82, Side::Yes, 3);
    let mut c = ctx(&e, None, Some(pid()));
    c.recon = ReconciliationState::Required;
    assert!(builds(&s.observe(&c).directives).is_empty());
}

#[test]
fn kill_switch_prevents_new_entry() {
    let mut s = MlbStrategy::new();
    eligible(&mut s, pid());
    let e = event(81, 81, 82, Side::Yes, 3);
    let mut c = ctx(&e, None, Some(pid()));
    c.kill_switch = KillSwitch::Tripped;
    assert!(builds(&s.observe(&c).directives).is_empty());
}

#[test]
fn no_take_profit_intent_exists() {
    fn classify(d: &MlbDirective) -> &'static str {
        match d {
            MlbDirective::Build(_) => "build",
            MlbDirective::CancelRemainingEntries { .. } => "cancel",
            MlbDirective::PauseEntry { .. } => "pause",
            MlbDirective::StopWatch(_) => "stop_watch",
            MlbDirective::ExecuteStop(_) => "execute_stop",
        }
    }
    assert_eq!(
        classify(&MlbDirective::PauseEntry {
            game_id: GameId::from_raw(1)
        }),
        "pause"
    );
}

#[test]
fn no_discretionary_exit_exists() {
    match PositionExitCause::StopLoss {
        PositionExitCause::StopLoss => {}
        PositionExitCause::Settlement => panic!("expected stop"),
    }
}

#[test]
fn stop_signal_is_distinct_from_liquidation() {
    let mut s = MlbStrategy::new();
    eligible(&mut s, pid());
    let pos = filled_position(usd(2, 40), 3, 1);
    let e = event(81, 81, 82, Side::Yes, 3);
    let turn = s.observe(&ctx(&e, Some(&pos), Some(pid())));
    let stop = turn
        .directives
        .iter()
        .find_map(|d| match d {
            MlbDirective::StopWatch(sig) => Some(sig),
            _ => None,
        })
        .expect("stop watch");
    assert_eq!(stop.rounding, StopRounding::HalfOfVwapHundredths);
    assert!(stop.proposed_basis.is_some());
}

#[test]
fn settlement_path_remains_separate() {
    let mut s = MlbStrategy::new();
    eligible(&mut s, pid());
    let mut pos = filled_position(usd(2, 40), 3, 1);
    pos.apply_settlement(usd(3, 0)).unwrap();
    let e = event(81, 81, 82, Side::Yes, 3);
    let turn = s.observe(&ctx(&e, Some(&pos), Some(pid())));
    assert!(builds(&turn.directives).is_empty());
    assert_eq!(pos.lifecycle(), PositionLifecycle::Settled);
}

#[test]
fn no_second_position_id_to_finish_remainder() {
    let mut index = momento_positions::GamePositionIndex::new();
    let a = index.id_for(MLB_STRATEGY_ID, GameId::from_raw(10));
    let mut s = MlbStrategy::new();
    eligible(&mut s, a);
    let e = event(81, 81, 82, Side::Yes, 3);
    let other = PositionId::from_raw(999);
    s.observe(&ctx(&e, None, Some(other)));
    assert_eq!(s.phase(GameId::from_raw(10)), MlbGamePhase::NotEligible);
    assert_eq!(index.id_for(MLB_STRATEGY_ID, GameId::from_raw(10)), a);
}

#[test]
fn cumulative_exposure_cannot_exceed_risk_approval() {
    let snap = snapshot50();
    let mut pos = Position::new_for_game(
        pid(),
        GameId::from_raw(10),
        StrategyId::from_raw(1),
        snap.snapshot_id(),
        snap.max_position_budget(),
        Some(MarketId::from_raw(2)),
        Some(Side::Yes),
    );
    let (ex, recv) = ts(1);
    pos.apply_entry_fill(Fill::new(
        FillId::from_raw(1),
        pid(),
        ClientOrderId::from_raw(1),
        None,
        Contracts::from_u32(7),
        px(80),
        usd(5, 60),
        Fee::zero(FeeKind::Entry),
        ex,
        recv,
    ))
    .unwrap();
    pos.apply_entry_fill(Fill::new(
        FillId::from_raw(2),
        pid(),
        ClientOrderId::from_raw(2),
        None,
        Contracts::from_u32(1),
        px(65),
        usd(0, 65),
        Fee::zero(FeeKind::Entry),
        ex,
        recv,
    ))
    .ok();
    let mut s = MlbStrategy::new();
    eligible(&mut s, pid());
    let e = event(81, 81, 82, Side::Yes, 3);
    let dirs = s.observe(&ctx(&e, Some(&pos), Some(pid()))).directives;
    if let Some(intent) = builds(&dirs).first() {
        let risk = momento_risk::PaperRiskEngine::paper(
            snap,
            momento_risk::RiskConfig::mlb_paper_experimental().unwrap(),
        );
        match risk.decide_entry(intent, &pos) {
            momento_core::RiskDecision::Rejected { .. } => {}
            momento_core::RiskDecision::Approved(a) => {
                let used = pos
                    .actual_exposure()
                    .as_money()
                    .checked_add(a.max_economic())
                    .unwrap();
                assert!(used.cents() <= pos.approved_economic_budget().cents());
            }
        }
    } else {
        assert!(pos.actionable_remaining_entry().unwrap().cents() <= 0);
    }
}

#[test]
fn missing_venue_mid_uses_yes_bid_and_does_not_invent_average() {
    let mut s = MlbStrategy::new();
    let mut e = event(80, 80, 82, Side::Yes, 1);
    e.mid = None;
    e.last = Some(px(99));
    let turn = s.observe(&ctx(&e, None, Some(pid())));
    let first = s.first_80(GameId::from_raw(10)).unwrap();
    assert_eq!(first.bid, px(80));
    assert_ne!(first.bid, px(81));
    assert!(turn.audit.iter().any(
        |a| matches!(a, AuditEvent::First80Observed { mid: None, bid: Some(b), .. } if *b == px(80))
    ));
}
