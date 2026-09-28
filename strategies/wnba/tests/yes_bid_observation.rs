//! WNBA YES-bid observation. Same 80/81/89 machine as MLB. Own StrategyId.

use chrono::{TimeZone, Utc};
use momento_core::{
    AdditionalExposure, AuditEvent, Bps, ClientOrderId, Contracts, EntryStyle, ExchangeTimestamp,
    Fee, FeeKind, Fill, FillId, GameId, KillSwitch, MarketEvent, MarketId, Money, Position,
    PositionId, PositionLifecycle, Price, ReceivedAt, ReconciliationState, RiskDecision, Side,
    SnapshotSource, StrategyId, WeeklyBankrollSnapshot,
};
use momento_risk::{PaperRiskEngine, RiskConfig};
use momento_strategy_mlb::{MlbContext, MlbDirective, MlbGamePhase, MlbIssue, QuoteReject};
use momento_strategy_wnba::{WNBA_STRATEGY_ID, WnbaStrategy};

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
        WNBA_STRATEGY_ID,
        snap.snapshot_id(),
        snap.bankroll().checked_mul_bps(Bps::PCT_8_33).unwrap(),
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

fn confirm_80_81(s: &mut WnbaStrategy, assigned: PositionId) -> Vec<MlbDirective> {
    let e80 = yes_bid_event(80, 81, None, 1);
    s.observe(&ctx(&e80, None, Some(assigned)));
    let e81 = yes_bid_event(81, 82, None, 2);
    s.observe(&ctx(&e81, None, Some(assigned))).directives
}

#[test]
fn identity_is_wnba_not_mlb() {
    let s = WnbaStrategy::new();
    assert_eq!(s.strategy_id(), StrategyId::WNBA);
    assert_ne!(s.strategy_id(), StrategyId::MLB);
}

#[test]
fn a_yes_bid_79_no_signal() {
    let mut s = WnbaStrategy::new();
    let e = yes_bid_event(79, 80, None, 1);
    let turn = s.observe(&ctx(&e, None, Some(pid())));
    assert!(builds(&turn.directives).is_empty());
    assert!(s.inner().first_80(GameId::from_raw(10)).is_none());
    assert_eq!(
        s.inner().phase(GameId::from_raw(10)),
        MlbGamePhase::Watching
    );
}

#[test]
fn b_yes_bid_80_first_80() {
    let mut s = WnbaStrategy::new();
    let e = yes_bid_event(80, 81, None, 1);
    let turn = s.observe(&ctx(&e, None, Some(pid())));
    assert!(
        turn.audit
            .iter()
            .any(|a| matches!(a, AuditEvent::First80Observed { .. }))
    );
    assert_eq!(
        s.inner().first_80(GameId::from_raw(10)).unwrap().bid,
        px(80)
    );
    assert!(builds(&turn.directives).is_empty());
}

#[test]
fn c_yes_bid_80_then_81_emits_trade_intent() {
    let mut s = WnbaStrategy::new();
    let dirs = confirm_80_81(&mut s, pid());
    let intent = builds(&dirs)[0];
    assert_eq!(intent.build.strategy_id, WNBA_STRATEGY_ID);
    assert_eq!(intent.build.style, EntryStyle::MakerOnly);
    assert_eq!(intent.build.limit_price, px(81));
    assert_eq!(intent.build.side, Side::Yes);
    assert_eq!(intent.build.position_id, pid());
}

#[test]
fn h_last_price_cannot_substitute_for_yes_bid() {
    let mut s = WnbaStrategy::new();
    let e = yes_bid_event(79, 80, Some(99), 1);
    let turn = s.observe(&ctx(&e, None, Some(pid())));
    assert!(s.inner().first_80(GameId::from_raw(10)).is_none());
    assert!(builds(&turn.directives).is_empty());
}

#[test]
fn i_ask_cannot_substitute_for_yes_bid() {
    let mut s = WnbaStrategy::new();
    let e = yes_bid_event(79, 99, None, 1);
    let turn = s.observe(&ctx(&e, None, Some(pid())));
    assert!(s.inner().first_80(GameId::from_raw(10)).is_none());
    assert!(builds(&turn.directives).is_empty());
}

#[test]
fn j_missing_yes_bid_fails_closed() {
    let mut s = WnbaStrategy::new();
    let mut e = yes_bid_event(80, 81, None, 1);
    e.bid = None;
    let turn = s.observe(&ctx(&e, None, Some(pid())));
    assert!(s.inner().first_80(GameId::from_raw(10)).is_none());
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

#[test]
fn e_yes_bid_89_permanently_game_locks() {
    let mut s = WnbaStrategy::new();
    let e = yes_bid_event(89, 90, None, 1);
    s.observe(&ctx(&e, None, None));
    assert_eq!(
        s.inner().phase(GameId::from_raw(10)),
        MlbGamePhase::GameLocked
    );
    assert!(s.inner().first_89(GameId::from_raw(10)).is_some());
}

#[test]
fn f_game_lock_does_not_liquidate() {
    let mut s = WnbaStrategy::new();
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
}

#[test]
fn g_price_returning_below_89_does_not_resume_entry() {
    let mut s = WnbaStrategy::new();
    s.observe(&ctx(&yes_bid_event(89, 90, None, 1), None, None));
    let turn = s.observe(&ctx(&yes_bid_event(82, 83, None, 2), None, Some(pid())));
    assert!(builds(&turn.directives).is_empty());
    assert_eq!(
        s.inner().phase(GameId::from_raw(10)),
        MlbGamePhase::GameLocked
    );
}

#[test]
fn partial_fill_keeps_the_same_position_id() {
    let pos = filled_partial();
    assert_eq!(pos.id(), pid());
    assert_eq!(pos.strategy_id(), WNBA_STRATEGY_ID);
    assert!(pos.filled_quantity().get() > 0);
}

fn remainder(pos: &Position) -> momento_core::TradeIntent {
    momento_core::TradeIntent::build(momento_core::BuildPositionIntent {
        strategy_id: WNBA_STRATEGY_ID,
        game_id: pos.game_id(),
        market_id: MarketId::from_raw(2),
        side: Side::Yes,
        position_id: pos.id(),
        limit_price: px(81),
        style: EntryStyle::MakerOnly,
        additional: AdditionalExposure::RemainderOfApprovedBudget,
    })
}

#[test]
fn wnba_uses_8_33_percent_allocation_416_cents() {
    let snap = snapshot50();
    assert_eq!(snap.bankroll(), usd(50, 0));
    assert_eq!(snap.max_position_budget(), usd(6, 25));
    let e = PaperRiskEngine::paper(snap.clone(), RiskConfig::mlb_paper_experimental().unwrap());
    let pos = empty_position_for(&snap, pid(), GameId::from_raw(10));
    match e.decide_entry(&remainder(&pos), &pos) {
        RiskDecision::Approved(a) => {
            assert_eq!(a.original_budget(), usd(4, 16));
            assert!(a.original_budget().cents() < 417);
        }
        other => panic!("expected WNBA approval, got {other:?}"),
    }
}

#[test]
fn wnba_allocation_does_not_change_mlb_12_5_percent() {
    let snap = snapshot50();
    let e = PaperRiskEngine::paper(snap.clone(), RiskConfig::mlb_paper_experimental().unwrap());
    let mlb = Position::new_for_game(
        PositionId::from_raw(7),
        GameId::from_raw(70),
        StrategyId::MLB,
        snap.snapshot_id(),
        snap.max_position_budget(),
        Some(MarketId::from_raw(2)),
        Some(Side::Yes),
    );
    let intent = momento_core::TradeIntent::build(momento_core::BuildPositionIntent {
        strategy_id: StrategyId::MLB,
        game_id: mlb.game_id(),
        market_id: MarketId::from_raw(2),
        side: Side::Yes,
        position_id: mlb.id(),
        limit_price: px(81),
        style: EntryStyle::MakerOnly,
        additional: AdditionalExposure::RemainderOfApprovedBudget,
    });
    match e.decide_entry(&intent, &mlb) {
        RiskDecision::Approved(a) => assert_eq!(a.original_budget(), usd(6, 25)),
        other => panic!("expected MLB $6.25, got {other:?}"),
    }
}

#[test]
fn k_wnba_position_identity_is_position_market_side() {
    let pos = filled_partial();
    assert_eq!(pos.strategy_id(), WNBA_STRATEGY_ID);
    assert_eq!(pos.market_id(), Some(MarketId::from_raw(2)));
    assert_eq!(pos.side(), Some(Side::Yes));
}

#[test]
fn wnba_other_market_quote_cannot_stop_position() {
    let mut s = WnbaStrategy::new();
    let pos = filled_partial();
    // Includes same-game opposite ticker (e.g. GS vs CONN).
    let (exchange_ts, received_at) = ts(4);
    let other = MarketEvent {
        game_id: GameId::from_raw(10),
        market_id: MarketId::from_raw(201),
        side: Some(Side::Yes),
        exchange_ts,
        received_at,
        last: None,
        bid: Some(px(17)),
        ask: Some(px(18)),
        mid: None,
        bid_depth: Some(5),
        ask_depth: Some(4),
        game_state: None,
    };
    let turn = s.observe(&ctx(&other, Some(&pos), Some(pid())));
    assert!(
        !turn
            .directives
            .iter()
            .any(|d| matches!(d, MlbDirective::ExecuteStop(_)))
    );
}

#[test]
fn wnba_own_yes_bid_40_stops_and_carries_market_side() {
    let mut s = WnbaStrategy::new();
    let pos = filled_partial();
    let e = yes_bid_event(40, 41, None, 4);
    let exec = s
        .observe(&ctx(&e, Some(&pos), Some(pid())))
        .directives
        .into_iter()
        .find_map(|d| match d {
            MlbDirective::ExecuteStop(x) => Some(x),
            _ => None,
        })
        .expect("WNBA STOP_TRIGGERED");
    assert_eq!(exec.market_id, MarketId::from_raw(2));
    assert_eq!(exec.side, Side::Yes);
    assert_eq!(exec.quantity.get(), 3);
}

#[test]
fn wnba_two_sided_game_cannot_cross_stop() {
    let snap = snapshot50();
    let mut pos = Position::new_for_game(
        pid(),
        GameId::from_raw(10),
        WNBA_STRATEGY_ID,
        snap.snapshot_id(),
        snap.bankroll().checked_mul_bps(Bps::PCT_8_33).unwrap(),
        Some(MarketId::from_raw(5001)),
        Some(Side::Yes),
    );
    let (ex, recv) = ts(1);
    pos.apply_entry_fill(Fill::new(
        FillId::from_raw(1),
        pid(),
        ClientOrderId::from_raw(1),
        None,
        Contracts::from_u32(5),
        px(81),
        Money::from_cents(405),
        Fee::zero(FeeKind::Entry),
        ex,
        recv,
    ))
    .unwrap();
    let mut s = WnbaStrategy::new();
    let (exchange_ts, received_at) = ts(4);
    let conn = MarketEvent {
        game_id: GameId::from_raw(10),
        market_id: MarketId::from_raw(5002),
        side: Some(Side::Yes),
        exchange_ts,
        received_at,
        last: None,
        bid: Some(px(17)),
        ask: Some(px(18)),
        mid: None,
        bid_depth: Some(5),
        ask_depth: Some(4),
        game_state: None,
    };
    assert!(
        !s.observe(&ctx(&conn, Some(&pos), Some(pid())))
            .directives
            .iter()
            .any(|d| matches!(d, MlbDirective::ExecuteStop(_))),
        "CONN quote must not stop GS YES"
    );
}

#[test]
fn wnba_sharp_drop_and_continue_after_stop_trigger() {
    let mut pos = filled_partial();
    let mut s = WnbaStrategy::new();
    assert!(
        !s.observe(&ctx(
            &yes_bid_event(72, 73, None, 4),
            Some(&pos),
            Some(pid())
        ))
        .directives
        .iter()
        .any(|d| matches!(d, MlbDirective::ExecuteStop(_)))
    );
    let exec = s
        .observe(&ctx(
            &yes_bid_event(24, 25, None, 5),
            Some(&pos),
            Some(pid()),
        ))
        .directives
        .into_iter()
        .find_map(|d| match d {
            MlbDirective::ExecuteStop(x) => Some(x),
            _ => None,
        })
        .expect("WNBA gap through stop must reduce at 24");
    assert_eq!(exec.suggested_limit, px(24));
    assert_eq!(exec.market_id, MarketId::from_raw(2));
    assert_eq!(exec.side, Side::Yes);

    pos.trigger_stop();
    pos.begin_liquidation();
    let mut s2 = WnbaStrategy::new();
    let cont = s2
        .observe(&ctx(
            &yes_bid_event(24, 25, None, 6),
            Some(&pos),
            Some(pid()),
        ))
        .directives
        .into_iter()
        .find_map(|d| match d {
            MlbDirective::ExecuteStop(x) => Some(x),
            _ => None,
        })
        .expect("WNBA LIQUIDATION_ACTIVE must continue");
    assert_eq!(cont.suggested_limit, px(24));
    assert_eq!(pos.lifecycle(), PositionLifecycle::LiquidationActive);
}

#[test]
fn wnba_game_lock_does_not_disable_stop() {
    let pos = filled_partial();
    let mut s = WnbaStrategy::new();
    confirm_80_81(&mut s, pid());
    let locked = s.observe(&ctx(
        &yes_bid_event(89, 90, None, 3),
        Some(&pos),
        Some(pid()),
    ));
    assert!(
        !locked
            .directives
            .iter()
            .any(|d| matches!(d, MlbDirective::ExecuteStop(_)))
    );
    let exec = s
        .observe(&ctx(
            &yes_bid_event(24, 25, None, 4),
            Some(&pos),
            Some(pid()),
        ))
        .directives
        .into_iter()
        .find_map(|d| match d {
            MlbDirective::ExecuteStop(x) => Some(x),
            _ => None,
        })
        .expect("WNBA GAME_LOCKED still monitors 50% stop");
    assert_eq!(exec.suggested_limit, px(24));
}
