//! Position-scoped stop: PositionId → MarketId → side.
//!
//! GameId is not sufficient. A COL quote must never stop a WSH position.

use chrono::{TimeZone, Utc};
use momento_core::{
    Bps, ClientOrderId, Contracts, EntryBasisCalculator, ExchangeTimestamp, Fee, FeeKind, Fill,
    FillId, GameId, KillSwitch, MarketEvent, MarketId, Money, Position, PositionId,
    PositionLifecycle, Price, ProposedVwapEntryBasis, ReceivedAt, ReconciliationState, Side,
    SnapshotSource, StrategyId, WeeklyBankrollSnapshot, half_entry_stop_from_fills,
};
use momento_positions::{InMemoryPositionTracker, PositionTracker, TrackerPersist};
use momento_strategy_mlb::{
    MLB_STRATEGY_ID, MlbContext, MlbDirective, MlbStrategy, StopExecution, ValidQuote,
    quote_is_position_stop_eligible,
};

fn usd(d: i64, c: u8) -> Money {
    Money::from_usd(d, c).unwrap()
}

fn px(c: u16) -> Price {
    Price::from_cents(c).unwrap()
}

fn ts(sec: u32) -> (ExchangeTimestamp, ReceivedAt) {
    let t = Utc
        .with_ymd_and_hms(2026, 8, 24, 20, 18, sec)
        .single()
        .unwrap();
    (ExchangeTimestamp::from_utc(t), ReceivedAt::from_utc(t))
}

const GAME: u128 = 10;
const WSH_MARKET: u128 = 200;
const COL_MARKET: u128 = 201;
const WSH_PID: u128 = 42;
const COL_PID: u128 = 43;

fn quote(market: u128, side: Side, bid: u16, ask: u16, sec: u32) -> MarketEvent {
    let (exchange_ts, received_at) = ts(sec);
    MarketEvent {
        game_id: GameId::from_raw(GAME),
        market_id: MarketId::from_raw(market),
        side: Some(side),
        exchange_ts,
        received_at,
        last: None,
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
    pid: PositionId,
) -> MlbContext<'a> {
    MlbContext {
        event,
        position,
        assigned_position_id: Some(pid),
        recon: ReconciliationState::Healthy,
        kill_switch: KillSwitch::Armed,
        data_stale: false,
        has_working_entry: false,
        unknown_entry_order: false,
        has_working_liquidation: false,
        unknown_liquidation_order: false,
    }
}

fn snap() -> WeeklyBankrollSnapshot {
    let now = Utc
        .with_ymd_and_hms(2026, 8, 24, 16, 0, 0)
        .single()
        .unwrap();
    WeeklyBankrollSnapshot::capture(usd(50, 0), Bps::PCT_12_5, now, SnapshotSource::Test).unwrap()
}

fn filled(
    strategy: StrategyId,
    pid: u128,
    market: u128,
    side: Side,
    qty: u32,
    cents: u16,
) -> Position {
    let snap = snap();
    let mut pos = Position::new_for_game(
        PositionId::from_raw(pid),
        GameId::from_raw(GAME),
        strategy,
        snap.snapshot_id(),
        snap.max_position_budget(),
        Some(MarketId::from_raw(market)),
        Some(side),
    );
    let (ex, recv) = ts(1);
    pos.apply_entry_fill(Fill::new(
        FillId::from_raw(pid),
        PositionId::from_raw(pid),
        ClientOrderId::from_raw(pid),
        None,
        Contracts::from_u32(qty),
        px(cents),
        Money::from_cents(i64::from(qty) * i64::from(cents)),
        Fee::zero(FeeKind::Entry),
        ex,
        recv,
    ))
    .unwrap();
    pos
}

fn wsh_yes_81(qty: u32) -> Position {
    filled(StrategyId::MLB, WSH_PID, WSH_MARKET, Side::Yes, qty, 81)
}

fn execute_stop(dirs: &[MlbDirective]) -> Option<StopExecution> {
    dirs.iter().find_map(|d| match d {
        MlbDirective::ExecuteStop(x) => Some(x.clone()),
        _ => None,
    })
}

#[test]
fn a_wsh_yes_81_stops_at_own_yes_bid_40() {
    let mut s = MlbStrategy::new();
    let pos = wsh_yes_81(7);
    let e = quote(WSH_MARKET, Side::Yes, 40, 41, 4);
    let turn = s.observe(&ctx(&e, Some(&pos), pos.id()));
    let exec = execute_stop(&turn.directives).expect("STOP_TRIGGERED");
    assert_eq!(exec.position_id, pos.id());
    assert_eq!(exec.market_id, MarketId::from_raw(WSH_MARKET));
    assert_eq!(exec.side, Side::Yes);
    assert_eq!(exec.quantity.get(), 7);
    assert_eq!(exec.suggested_limit, px(40));
    let stop = half_entry_stop_from_fills(pos.fill_history()).unwrap();
    assert_eq!(stop.hundredths_of_cent(), 4050);
    assert_eq!(exec.threshold, stop);
}

#[test]
fn b_wsh_yes_81_stays_open_at_own_yes_bid_80() {
    let mut s = MlbStrategy::new();
    let pos = wsh_yes_81(7);
    let e = quote(WSH_MARKET, Side::Yes, 80, 81, 4);
    let turn = s.observe(&ctx(&e, Some(&pos), pos.id()));
    assert!(execute_stop(&turn.directives).is_none());
}

#[test]
fn c_incident_col_yes_17_cannot_stop_wsh_yes_81() {
    let mut s = MlbStrategy::new();
    let pos = wsh_yes_81(7);
    let col = quote(COL_MARKET, Side::Yes, 17, 18, 4);
    let wsh = quote(WSH_MARKET, Side::Yes, 80, 81, 5);
    assert!(!quote_is_position_stop_eligible(
        &pos,
        &col,
        ValidQuote {
            side: Side::Yes,
            bid: px(17),
            ask: px(18),
        }
    ));
    assert!(quote_is_position_stop_eligible(
        &pos,
        &wsh,
        ValidQuote {
            side: Side::Yes,
            bid: px(80),
            ask: px(81),
        }
    ));
    let turn_col = s.observe(&ctx(&col, Some(&pos), pos.id()));
    assert!(execute_stop(&turn_col.directives).is_none());
    let turn_wsh = s.observe(&ctx(&wsh, Some(&pos), pos.id()));
    assert!(execute_stop(&turn_wsh.directives).is_none());
}

#[test]
fn d_wsh_no_quote_cannot_stop_wsh_yes() {
    let mut s = MlbStrategy::new();
    let pos = wsh_yes_81(7);
    let e = quote(WSH_MARKET, Side::No, 10, 11, 4);
    let turn = s.observe(&ctx(&e, Some(&pos), pos.id()));
    assert!(execute_stop(&turn.directives).is_none());
}

#[test]
fn e_liquidation_identity_is_wsh_market_and_yes_side() {
    let mut s = MlbStrategy::new();
    let pos = wsh_yes_81(7);
    let e = quote(WSH_MARKET, Side::Yes, 40, 41, 4);
    let exec = execute_stop(&s.observe(&ctx(&e, Some(&pos), pos.id())).directives).unwrap();
    assert_eq!(exec.market_id, pos.market_id().unwrap());
    assert_eq!(exec.side, pos.side().unwrap());
    assert_eq!(exec.side, Side::Yes);
    assert_eq!(exec.position_id, pos.id());
}

#[test]
fn f_col_quote_never_emits_wsh_liquidation() {
    let mut s = MlbStrategy::new();
    let pos = wsh_yes_81(7);
    for (i, bid) in [8u16, 17, 18, 40, 80].into_iter().enumerate() {
        let e = quote(
            COL_MARKET,
            Side::Yes,
            bid,
            bid.saturating_add(1),
            10 + u32::try_from(i).unwrap(),
        );
        let turn = s.observe(&ctx(&e, Some(&pos), pos.id()));
        assert!(
            execute_stop(&turn.directives).is_none(),
            "COL bid {bid} must not liquidate WSH"
        );
    }
}

#[test]
fn g_partial_fill_liquidates_only_actual_filled_quantity() {
    let mut s = MlbStrategy::new();
    let pos = wsh_yes_81(3);
    assert_eq!(pos.filled_quantity().get(), 3);
    let e = quote(WSH_MARKET, Side::Yes, 40, 41, 4);
    let turn = s.observe(&ctx(&e, Some(&pos), pos.id()));
    let exec = execute_stop(&turn.directives).unwrap();
    assert_eq!(exec.quantity.get(), 3);
}

#[test]
fn h_two_markets_under_one_game_have_independent_stops() {
    let pos_wsh = wsh_yes_81(7);
    let pos_col = filled(StrategyId::MLB, COL_PID, COL_MARKET, Side::Yes, 7, 81);
    assert_eq!(pos_wsh.game_id(), pos_col.game_id());
    assert_ne!(pos_wsh.market_id(), pos_col.market_id());
    assert_ne!(pos_wsh.id(), pos_col.id());

    let col_17 = quote(COL_MARKET, Side::Yes, 17, 18, 4);
    let wsh_80 = quote(WSH_MARKET, Side::Yes, 80, 81, 5);

    let mut s_wsh = MlbStrategy::new();
    assert!(
        execute_stop(
            &s_wsh
                .observe(&ctx(&col_17, Some(&pos_wsh), pos_wsh.id()))
                .directives
        )
        .is_none()
    );
    assert!(
        execute_stop(
            &s_wsh
                .observe(&ctx(&wsh_80, Some(&pos_wsh), pos_wsh.id()))
                .directives
        )
        .is_none()
    );

    let mut s_col = MlbStrategy::new();
    let col_turn = s_col.observe(&ctx(&col_17, Some(&pos_col), pos_col.id()));
    let col_stop =
        execute_stop(&col_turn.directives).expect("COL own bid 17 must stop COL 81 entry");
    assert_eq!(col_stop.market_id, MarketId::from_raw(COL_MARKET));
    assert_eq!(col_stop.position_id, pos_col.id());
}

#[test]
fn i_yes_and_no_stops_are_independent() {
    let yes = wsh_yes_81(7);
    let no = filled(StrategyId::MLB, 99, WSH_MARKET, Side::No, 7, 81);
    let no_quote = quote(WSH_MARKET, Side::No, 10, 11, 4);
    let yes_quote = quote(WSH_MARKET, Side::Yes, 80, 81, 5);
    let mut s = MlbStrategy::new();
    assert!(execute_stop(&s.observe(&ctx(&no_quote, Some(&yes), yes.id())).directives).is_none());
    assert!(execute_stop(&s.observe(&ctx(&yes_quote, Some(&no), no.id())).directives).is_none());
}

#[test]
fn j_mlb_position_identity_is_position_market_side() {
    let pos = wsh_yes_81(7);
    assert_eq!(pos.strategy_id(), StrategyId::MLB);
    assert_eq!(pos.strategy_id(), MLB_STRATEGY_ID);
    assert_eq!(pos.market_id(), Some(MarketId::from_raw(WSH_MARKET)));
    assert_eq!(pos.side(), Some(Side::Yes));
    assert_eq!(pos.id(), PositionId::from_raw(WSH_PID));
}

#[test]
fn l_restart_preserves_market_side_fills_and_stop_basis() {
    let original = wsh_yes_81(7);
    let basis = ProposedVwapEntryBasis
        .basis(original.fill_history())
        .unwrap();
    let json = serde_json::to_string(&original).unwrap();
    let restored: Position = serde_json::from_str(&json).unwrap();
    assert_eq!(restored.id(), original.id());
    assert_eq!(restored.market_id(), original.market_id());
    assert_eq!(restored.side(), original.side());
    assert_eq!(restored.filled_quantity(), original.filled_quantity());
    assert_eq!(
        ProposedVwapEntryBasis
            .basis(restored.fill_history())
            .unwrap(),
        basis
    );

    let persist = TrackerPersist {
        positions: vec![restored.clone()],
        orders: vec![],
        unknown: vec![],
        recon: ReconciliationState::Healthy,
        index: vec![(
            StrategyId::MLB.raw(),
            restored.game_id().raw(),
            restored.id().raw(),
        )],
        event_keys: vec![],
    };
    let loaded = InMemoryPositionTracker::restore_persist(persist);
    let pos = loaded.get(original.id()).unwrap();
    let mut s = MlbStrategy::new();
    let open = quote(WSH_MARKET, Side::Yes, 80, 81, 6);
    assert!(execute_stop(&s.observe(&ctx(&open, Some(pos), pos.id())).directives).is_none());
    let stop_q = quote(WSH_MARKET, Side::Yes, 40, 41, 7);
    assert!(execute_stop(&s.observe(&ctx(&stop_q, Some(pos), pos.id())).directives).is_some());
    let col = quote(COL_MARKET, Side::Yes, 17, 18, 8);
    assert!(execute_stop(&s.observe(&ctx(&col, Some(pos), pos.id())).directives).is_none());
}

#[test]
fn m_unknown_liquidation_does_not_emit_execute_stop() {
    let mut s = MlbStrategy::new();
    let pos = wsh_yes_81(7);
    let e = quote(WSH_MARKET, Side::Yes, 40, 41, 4);
    let mut c = ctx(&e, Some(&pos), pos.id());
    c.unknown_liquidation_order = true;
    assert!(execute_stop(&s.observe(&c).directives).is_none());
}

#[test]
fn n_working_liquidation_does_not_emit_duplicate_execute_stop() {
    let mut s = MlbStrategy::new();
    let pos = wsh_yes_81(7);
    let e = quote(WSH_MARKET, Side::Yes, 40, 41, 4);
    let mut c = ctx(&e, Some(&pos), pos.id());
    c.has_working_liquidation = true;
    assert!(execute_stop(&s.observe(&c).directives).is_none());
}

#[test]
fn missing_position_identity_fails_closed() {
    let snap = snap();
    let mut pos = Position::new_for_game(
        PositionId::from_raw(WSH_PID),
        GameId::from_raw(GAME),
        StrategyId::MLB,
        snap.snapshot_id(),
        snap.max_position_budget(),
        None,
        None,
    );
    let (ex, recv) = ts(1);
    pos.apply_entry_fill(Fill::new(
        FillId::from_raw(1),
        PositionId::from_raw(WSH_PID),
        ClientOrderId::from_raw(1),
        None,
        Contracts::from_u32(7),
        px(81),
        Money::from_cents(567),
        Fee::zero(FeeKind::Entry),
        ex,
        recv,
    ))
    .unwrap();
    let mut s = MlbStrategy::new();
    let e = quote(WSH_MARKET, Side::Yes, 40, 41, 4);
    assert!(execute_stop(&s.observe(&ctx(&e, Some(&pos), pos.id())).directives).is_none());
}

#[test]
fn every_two_sided_mlb_game_scopes_stop_to_held_market() {
    // Same defect as COL/WSH: one GameId, two YES markets. Not a named-matchup special case.
    let matchups = [
        ("CHC vs AZ", 1101, 1102),
        ("CLE vs LAA", 1201, 1202),
        ("TEX vs CWS", 1301, 1302),
        ("COL vs WSH", WSH_MARKET, COL_MARKET),
    ];
    for (label, held, opponent) in matchups {
        let pos = filled(StrategyId::MLB, WSH_PID, held, Side::Yes, 7, 81);
        let mut s = MlbStrategy::new();
        let opp_17 = quote(opponent, Side::Yes, 17, 18, 4);
        let held_80 = quote(held, Side::Yes, 80, 81, 5);
        let held_40 = quote(held, Side::Yes, 40, 41, 6);
        assert!(
            execute_stop(&s.observe(&ctx(&opp_17, Some(&pos), pos.id())).directives).is_none(),
            "{label}: opponent 17¢ must not stop held YES @ 81"
        );
        assert!(
            execute_stop(&s.observe(&ctx(&held_80, Some(&pos), pos.id())).directives).is_none(),
            "{label}: own 80¢ must remain OPEN"
        );
        let exec = execute_stop(&s.observe(&ctx(&held_40, Some(&pos), pos.id())).directives)
            .unwrap_or_else(|| panic!("{label}: own 40¢ must STOP_TRIGGERED"));
        assert_eq!(exec.market_id, MarketId::from_raw(held), "{label}");
        assert_eq!(exec.side, Side::Yes, "{label}");
        assert_eq!(exec.quantity.get(), 7, "{label}");
    }
}

#[test]
fn o_exact_stop_and_below_stop_trigger() {
    let pos = wsh_yes_81(7);
    let mut s = MlbStrategy::new();
    let exact = execute_stop(
        &s.observe(&ctx(
            &quote(WSH_MARKET, Side::Yes, 40, 41, 4),
            Some(&pos),
            pos.id(),
        ))
        .directives,
    )
    .expect("40¢ is STOP_TRIGGERED");
    assert_eq!(exact.suggested_limit, px(40));
    let mut s2 = MlbStrategy::new();
    let below = execute_stop(
        &s2.observe(&ctx(
            &quote(WSH_MARKET, Side::Yes, 39, 40, 4),
            Some(&pos),
            pos.id(),
        ))
        .directives,
    )
    .expect("39¢ is STOP_TRIGGERED");
    assert_eq!(below.suggested_limit, px(39));
}

#[test]
fn p_sharp_drop_72_to_24_triggers_at_24_not_waiting_for_40() {
    let pos = wsh_yes_81(7);
    let mut s = MlbStrategy::new();
    let at_72 = s.observe(&ctx(
        &quote(WSH_MARKET, Side::Yes, 72, 73, 4),
        Some(&pos),
        pos.id(),
    ));
    assert!(execute_stop(&at_72.directives).is_none());
    let at_24 = s.observe(&ctx(
        &quote(WSH_MARKET, Side::Yes, 24, 25, 5),
        Some(&pos),
        pos.id(),
    ));
    let exec = execute_stop(&at_24.directives).expect("gap through 40 must STOP_TRIGGERED at 24");
    assert_eq!(exec.suggested_limit, px(24));
    assert_eq!(exec.market_id, MarketId::from_raw(WSH_MARKET));
    assert_eq!(exec.quantity.get(), 7);
    assert_ne!(exec.suggested_limit, px(40));
}

#[test]
fn q_stop_price_gone_stays_liquidation_active_and_follows_24() {
    let mut pos = wsh_yes_81(7);
    pos.trigger_stop();
    pos.begin_liquidation();
    assert_eq!(pos.lifecycle(), PositionLifecycle::LiquidationActive);
    let mut s = MlbStrategy::new();
    assert!(
        execute_stop(
            &s.observe(&ctx(
                &quote(COL_MARKET, Side::Yes, 17, 18, 4),
                Some(&pos),
                pos.id(),
            ))
            .directives
        )
        .is_none(),
        "COL cannot continue WSH liquidation"
    );
    let exec = execute_stop(
        &s.observe(&ctx(
            &quote(WSH_MARKET, Side::Yes, 24, 25, 5),
            Some(&pos),
            pos.id(),
        ))
        .directives,
    )
    .expect("LIQUIDATION_ACTIVE must continue at 24, not wait for 40");
    assert_eq!(exec.suggested_limit, px(24));
    assert_eq!(pos.lifecycle(), PositionLifecycle::LiquidationActive);
}

#[test]
fn r_liquidation_active_does_not_return_to_open_when_bid_recovers() {
    let mut pos = wsh_yes_81(7);
    pos.trigger_stop();
    pos.begin_liquidation();
    let mut s = MlbStrategy::new();
    let exec = execute_stop(
        &s.observe(&ctx(
            &quote(WSH_MARKET, Side::Yes, 80, 81, 6),
            Some(&pos),
            pos.id(),
        ))
        .directives,
    )
    .expect("once triggered, keep reducing at the current executable bid");
    assert_eq!(exec.suggested_limit, px(80));
    assert_eq!(pos.lifecycle(), PositionLifecycle::LiquidationActive);
}

#[test]
fn s_partial_liquidation_remaining_quantity_only() {
    let mut pos = wsh_yes_81(7);
    let (ex, recv) = ts(2);
    pos.apply_liquidation_fill(Fill::new(
        FillId::from_raw(900),
        pos.id(),
        ClientOrderId::from_raw(900),
        None,
        Contracts::from_u32(3),
        px(24),
        Money::from_cents(72),
        Fee::zero(FeeKind::Liquidation),
        ex,
        recv,
    ))
    .unwrap();
    assert_eq!(pos.filled_quantity().get(), 4);
    assert_eq!(pos.lifecycle(), PositionLifecycle::LiquidationActive);
    let mut s = MlbStrategy::new();
    let exec = execute_stop(
        &s.observe(&ctx(
            &quote(WSH_MARKET, Side::Yes, 24, 25, 7),
            Some(&pos),
            pos.id(),
        ))
        .directives,
    )
    .unwrap();
    assert_eq!(exec.quantity.get(), 4);
}

#[test]
fn t_complete_liquidation_is_flat_and_emits_no_stop() {
    let mut pos = wsh_yes_81(7);
    let (ex, recv) = ts(2);
    pos.apply_liquidation_fill(Fill::new(
        FillId::from_raw(901),
        pos.id(),
        ClientOrderId::from_raw(901),
        None,
        Contracts::from_u32(7),
        px(24),
        Money::from_cents(168),
        Fee::zero(FeeKind::Liquidation),
        ex,
        recv,
    ))
    .unwrap();
    assert_eq!(pos.filled_quantity().get(), 0);
    assert_eq!(pos.lifecycle(), PositionLifecycle::Flat);
    let mut s = MlbStrategy::new();
    assert!(
        execute_stop(
            &s.observe(&ctx(
                &quote(WSH_MARKET, Side::Yes, 24, 25, 8),
                Some(&pos),
                pos.id(),
            ))
            .directives
        )
        .is_none()
    );
}

#[test]
fn u_game_lock_does_not_disable_position_stop() {
    let pos = wsh_yes_81(7);
    let mut s = MlbStrategy::new();
    let locked = s.observe(&ctx(
        &quote(WSH_MARKET, Side::Yes, 89, 90, 4),
        Some(&pos),
        pos.id(),
    ));
    assert!(execute_stop(&locked.directives).is_none());
    let exec = execute_stop(
        &s.observe(&ctx(
            &quote(WSH_MARKET, Side::Yes, 24, 25, 5),
            Some(&pos),
            pos.id(),
        ))
        .directives,
    )
    .expect("GAME_LOCKED must still monitor the 50% stop");
    assert_eq!(exec.suggested_limit, px(24));
    assert_eq!(exec.market_id, MarketId::from_raw(WSH_MARKET));
}

#[test]
fn v_restart_preserves_liquidation_active_and_keeps_reducing() {
    let mut original = wsh_yes_81(7);
    original.trigger_stop();
    original.begin_liquidation();
    let json = serde_json::to_string(&original).unwrap();
    let restored: Position = serde_json::from_str(&json).unwrap();
    assert_eq!(restored.lifecycle(), PositionLifecycle::LiquidationActive);
    assert_eq!(restored.market_id(), original.market_id());
    assert_eq!(restored.side(), original.side());
    assert_eq!(restored.filled_quantity().get(), 7);
    let persist = TrackerPersist {
        positions: vec![restored.clone()],
        orders: vec![],
        unknown: vec![],
        recon: ReconciliationState::Healthy,
        index: vec![(
            StrategyId::MLB.raw(),
            restored.game_id().raw(),
            restored.id().raw(),
        )],
        event_keys: vec![],
    };
    let loaded = InMemoryPositionTracker::restore_persist(persist);
    let pos = loaded.get(original.id()).unwrap();
    let mut s = MlbStrategy::new();
    let exec = execute_stop(
        &s.observe(&ctx(
            &quote(WSH_MARKET, Side::Yes, 24, 25, 9),
            Some(pos),
            pos.id(),
        ))
        .directives,
    )
    .expect("restart must not lose stop protection");
    assert_eq!(exec.suggested_limit, px(24));
}
