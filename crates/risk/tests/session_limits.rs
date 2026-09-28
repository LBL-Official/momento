use chrono::{TimeZone, Utc};
use momento_core::{
    AdditionalExposure, Bps, BuildPositionIntent, EntryStyle, GameId, MarketId, Money, Position,
    PositionId, Price, RiskDecision, RiskRejectReason, Side, SnapshotSource, StrategyId,
    TradeIntent, WeeklyBankrollSnapshot,
};
use momento_risk::{PaperRiskEngine, RiskConfig};

fn px(c: u16) -> Price {
    Price::from_cents(c).unwrap()
}

fn snapshot_budget(bankroll: i64, budget: i64) -> WeeklyBankrollSnapshot {
    let now = Utc
        .with_ymd_and_hms(2026, 8, 24, 16, 0, 0)
        .single()
        .unwrap();
    WeeklyBankrollSnapshot::capture_with_budget(
        Money::from_cents(bankroll),
        Bps::PCT_12_5,
        Money::from_cents(budget),
        now,
        SnapshotSource::Test,
    )
    .unwrap()
}

fn snapshot50() -> WeeklyBankrollSnapshot {
    let now = Utc
        .with_ymd_and_hms(2026, 8, 24, 16, 0, 0)
        .single()
        .unwrap();
    WeeklyBankrollSnapshot::capture(
        Money::from_cents(5000),
        Bps::PCT_12_5,
        now,
        SnapshotSource::Test,
    )
    .unwrap()
}

fn position(snapshot: &WeeklyBankrollSnapshot, pid: u128, game: u128) -> Position {
    Position::new_for_game(
        PositionId::from_raw(pid),
        GameId::from_raw(game),
        StrategyId::MLB,
        snapshot.snapshot_id(),
        snapshot.max_position_budget(),
        Some(MarketId::from_raw(game)),
        Some(Side::Yes),
    )
}

fn remainder(position: &Position) -> TradeIntent {
    TradeIntent::build(BuildPositionIntent {
        strategy_id: StrategyId::MLB,
        game_id: position.game_id(),
        market_id: MarketId::from_raw(position.game_id().raw()),
        side: Side::Yes,
        position_id: position.id(),
        limit_price: px(80),
        style: EntryStyle::MakerOnly,
        additional: AdditionalExposure::RemainderOfApprovedBudget,
    })
}

fn rejected_reason(d: &RiskDecision) -> RiskRejectReason {
    match d {
        RiskDecision::Rejected { reason, .. } => *reason,
        RiskDecision::Approved(_) => panic!("expected rejection"),
    }
}

fn approved(d: RiskDecision) {
    match d {
        RiskDecision::Approved(_) => {}
        other => panic!("expected approval, got {other:?}"),
    }
}

fn engine_with(snapshot: WeeklyBankrollSnapshot, mut config: RiskConfig) -> PaperRiskEngine {
    config.max_open_positions = 8;
    let e = PaperRiskEngine::paper(snapshot, config);
    e.set_clock(
        Utc.with_ymd_and_hms(2026, 8, 24, 16, 0, 0)
            .single()
            .unwrap(),
    );
    e
}

#[test]
fn mlb_entry_uses_snapshot_budget_330_331_332() {
    for budget in [330_i64, 331, 332] {
        let snap = snapshot_budget(3931, budget);
        let e = engine_with(snap.clone(), RiskConfig::mlb_paper_experimental().unwrap());
        let pos = position(&snap, 1, 10);
        let d = e.decide_entry(&remainder(&pos), &pos);
        match d {
            RiskDecision::Approved(a) => {
                assert_eq!(a.original_budget().cents(), budget);
            }
            other => panic!("expected approval at {budget}¢, got {other:?}"),
        }
    }
}

#[test]
fn daily_entries_2_3_4_when_limit_is_3() {
    let snap = snapshot50();
    let mut config = RiskConfig::mlb_paper_experimental().unwrap();
    config.max_daily_entries = Some(3);
    let e = engine_with(snap.clone(), config);
    for (i, game) in [10_u128, 11, 12, 13].into_iter().enumerate() {
        let pos = position(&snap, (i as u128) + 1, game);
        let d = e.decide_entry(&remainder(&pos), &pos);
        if i < 3 {
            approved(d);
        } else {
            assert_eq!(rejected_reason(&d), RiskRejectReason::DailyTradeLimit);
        }
    }
    assert_eq!(e.session_ledger().entries_today, 3);
}

#[test]
fn daily_win_count_2_then_3_blocks() {
    let snap = snapshot50();
    let mut config = RiskConfig::mlb_paper_experimental().unwrap();
    config.max_daily_wins = Some(2);
    let e = engine_with(snap.clone(), config);
    e.on_realized_close(PositionId::from_raw(100), Some(Money::from_cents(50)));
    e.on_realized_close(PositionId::from_raw(101), Some(Money::from_cents(25)));
    let pos = position(&snap, 1, 10);
    assert_eq!(
        rejected_reason(&e.decide_entry(&remainder(&pos), &pos)),
        RiskRejectReason::DailyWinCountLimit
    );
}

#[test]
fn daily_loss_cents_330_331_332() {
    let snap = snapshot50();
    let mut config = RiskConfig::mlb_paper_experimental().unwrap();
    config.max_daily_loss_cents = Some(Money::from_cents(331));
    let e = engine_with(snap.clone(), config);

    e.on_realized_close(PositionId::from_raw(1), Some(Money::from_cents(-330)));
    approved(e.decide_entry(
        &remainder(&position(&snap, 10, 20)),
        &position(&snap, 10, 20),
    ));

    e.on_realized_close(PositionId::from_raw(2), Some(Money::from_cents(-1)));
    assert_eq!(e.session_ledger().realized_pnl_cents, -331);
    assert_eq!(
        rejected_reason(&e.decide_entry(
            &remainder(&position(&snap, 11, 21)),
            &position(&snap, 11, 21)
        )),
        RiskRejectReason::DailyLossCentsLimit
    );

    e.on_realized_close(PositionId::from_raw(3), Some(Money::from_cents(-1)));
    assert_eq!(
        rejected_reason(&e.decide_entry(
            &remainder(&position(&snap, 12, 22)),
            &position(&snap, 12, 22)
        )),
        RiskRejectReason::DailyLossCentsLimit
    );
}

#[test]
fn unread_session_pnl_fails_closed_when_win_limit_set() {
    let snap = snapshot50();
    let mut config = RiskConfig::mlb_paper_experimental().unwrap();
    config.max_daily_wins = Some(3);
    let e = engine_with(snap.clone(), config);
    e.on_realized_close(PositionId::from_raw(1), None);
    assert!(!e.session_ledger().pnl_available);
    assert_eq!(
        rejected_reason(
            &e.decide_entry(&remainder(&position(&snap, 2, 30)), &position(&snap, 2, 30))
        ),
        RiskRejectReason::SessionPnlUnavailable
    );
}

#[test]
fn liquidation_still_works_when_entry_limit_hit() {
    let snap = snapshot50();
    let mut config = RiskConfig::mlb_paper_experimental().unwrap();
    config.max_daily_entries = Some(1);
    let e = engine_with(snap.clone(), config);
    let first = position(&snap, 1, 10);
    approved(e.decide_entry(&remainder(&first), &first));
    let second = position(&snap, 2, 11);
    assert_eq!(
        rejected_reason(&e.decide_entry(&remainder(&second), &second)),
        RiskRejectReason::DailyTradeLimit
    );
    // Liquidation path does not consult session limits. An unfilled position is
    // InvalidQuantity; the gate under test is that approve_liquidation is not
    // DailyTradeLimit.
    let err = e.approve_liquidation(&first).err();
    assert_ne!(err, Some(RiskRejectReason::DailyTradeLimit));
}

#[test]
fn one_per_game_still_rejects_independently() {
    let snap = snapshot50();
    let mut config = RiskConfig::mlb_paper_experimental().unwrap();
    config.max_daily_entries = Some(5);
    let e = engine_with(snap.clone(), config);
    let first = position(&snap, 1, 10);
    approved(e.decide_entry(&remainder(&first), &first));
    let duplicate = position(&snap, 2, 10);
    assert_eq!(
        rejected_reason(&e.decide_entry(&remainder(&duplicate), &duplicate)),
        RiskRejectReason::DuplicateGamePosition
    );
}

#[test]
fn pacific_midnight_resets_entry_count() {
    let snap = snapshot50();
    let mut config = RiskConfig::mlb_paper_experimental().unwrap();
    config.max_daily_entries = Some(1);
    let e = engine_with(snap.clone(), config);
    let first = position(&snap, 1, 10);
    approved(e.decide_entry(&remainder(&first), &first));
    assert_eq!(e.session_ledger().entries_today, 1);

    // 2026-08-25 07:00 UTC = 2026-08-25 00:00 PDT.
    e.set_clock(Utc.with_ymd_and_hms(2026, 8, 25, 7, 0, 0).single().unwrap());
    assert_eq!(e.session_ledger().entries_today, 0);
    let next = position(&snap, 2, 11);
    approved(e.decide_entry(&remainder(&next), &next));
    assert_eq!(e.session_ledger().entries_today, 1);
}

#[test]
fn flat_close_is_neither_win_nor_loss() {
    let snap = snapshot50();
    let mut config = RiskConfig::mlb_paper_experimental().unwrap();
    config.max_daily_wins = Some(1);
    config.max_daily_losses = Some(1);
    let e = engine_with(snap.clone(), config);
    e.on_realized_close(PositionId::from_raw(1), Some(Money::from_cents(0)));
    assert_eq!(e.session_ledger().wins, 0);
    assert_eq!(e.session_ledger().losses, 0);
    approved(e.decide_entry(&remainder(&position(&snap, 2, 40)), &position(&snap, 2, 40)));
}

#[test]
fn persist_restores_session_counters() {
    let snap = snapshot50();
    let mut config = RiskConfig::mlb_paper_experimental().unwrap();
    config.max_daily_entries = Some(3);
    let e = engine_with(snap.clone(), config.clone());
    approved(e.decide_entry(&remainder(&position(&snap, 1, 10)), &position(&snap, 1, 10)));
    let persist = e.persist_state().unwrap();
    assert_eq!(persist.session.entries_today, 1);
    let restored = PaperRiskEngine::restore(persist, config);
    restored.set_clock(
        Utc.with_ymd_and_hms(2026, 8, 24, 16, 0, 0)
            .single()
            .unwrap(),
    );
    assert_eq!(restored.session_ledger().entries_today, 1);
}
