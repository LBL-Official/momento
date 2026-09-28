//! FIRST01 deterministic tests — entry, exit, overrides, identity.

use chrono::{TimeZone, Utc};
use momento_core::{GameId, MarketId, PositionId, Side};
use momento_research_strategies::{
    EffectiveParameters, EntryEngine, EntryParameters, EntryPhase, ExitEngine, ExitParameters,
    ExperimentOverrides, FIRST01_NAME, FIRST01_VERSION, First01Model, LiquidationState,
    ResearchPosition, ResearchPositionFill, StrategyQuote, StrategyRunMetadata,
};

const GAME: u128 = 10;
const WSH: u128 = 200;
const COL: u128 = 201;

fn quote(market: u128, ticker: &str, side: Side, bid: u16, ask: u16, sec: i64) -> StrategyQuote {
    let t = Utc.with_ymd_and_hms(2026, 8, 24, 18, 0, 0).unwrap() + chrono::Duration::seconds(sec);
    StrategyQuote {
        game_id: GameId::from_raw(GAME),
        market_id: MarketId::from_raw(market),
        ticker: ticker.into(),
        side,
        yes_bid_cents: bid,
        yes_ask_cents: ask,
        exchange_timestamp_ms: t.timestamp_millis(),
        received_timestamp: t,
        sequence_gap: false,
    }
}

fn default_entry() -> EntryEngine {
    EntryEngine::new(EntryParameters::default())
}

fn default_exit() -> ExitEngine {
    ExitEngine::new(ExitParameters::default())
}

fn wsh_position(qty: u32, entry_cents: u16) -> ResearchPosition {
    ResearchPosition::new(
        PositionId::from_raw(42),
        GameId::from_raw(GAME),
        MarketId::from_raw(WSH),
        Side::Yes,
        "KXMLBGAME-TEST-WSH",
        vec![ResearchPositionFill {
            quantity_contracts: qty,
            price_cents: entry_cents,
        }],
    )
}

#[test]
fn entry_01_below_80_does_not_signal() {
    let mut e = default_entry();
    let turn = e.observe(&quote(WSH, "WSH", Side::Yes, 79, 80, 1));
    assert!(turn.signals.is_empty());
    assert_eq!(e.phase(GameId::from_raw(GAME)), EntryPhase::Watching);
}

#[test]
fn entry_02_first_80_recorded() {
    let mut e = default_entry();
    e.observe(&quote(WSH, "WSH", Side::Yes, 80, 81, 1));
    let first = e.first_observation(GameId::from_raw(GAME)).unwrap();
    assert_eq!(first.key.market_id, WSH);
    assert_eq!(first.bid_cents, 80);
}

#[test]
fn entry_03_80_then_81_confirms_and_signals_when_maker_eligible() {
    let mut e = default_entry();
    e.observe(&quote(WSH, "WSH", Side::Yes, 80, 81, 1));
    let turn = e.observe(&quote(WSH, "WSH", Side::Yes, 81, 82, 2));
    assert_eq!(turn.signals.len(), 1);
    assert_eq!(turn.signals[0].signal_price_cents, 81);
    assert!(turn.signals[0].maker_eligible);
}

#[test]
fn entry_04_80_then_89_locks_without_entry_signal() {
    let mut e = default_entry();
    e.observe(&quote(WSH, "WSH", Side::Yes, 80, 81, 1));
    let turn = e.observe(&quote(WSH, "WSH", Side::Yes, 89, 90, 2));
    assert!(turn.signals.is_empty());
    assert_eq!(e.phase(GameId::from_raw(GAME)), EntryPhase::GameLocked);
}

#[test]
fn entry_05_81_with_ask_82_is_maker_eligible() {
    let mut e = default_entry();
    e.observe(&quote(WSH, "WSH", Side::Yes, 80, 81, 1));
    let turn = e.observe(&quote(WSH, "WSH", Side::Yes, 81, 82, 2));
    assert!(turn.signals[0].maker_eligible);
}

#[test]
fn entry_06_81_with_ask_81_is_not_maker_eligible() {
    let mut e = default_entry();
    e.observe(&quote(WSH, "WSH", Side::Yes, 80, 81, 1));
    let turn = e.observe(&quote(WSH, "WSH", Side::Yes, 81, 81, 2));
    assert!(turn.signals.is_empty());
}

#[test]
fn entry_07_83_is_allowed() {
    let mut e = default_entry();
    e.observe(&quote(WSH, "WSH", Side::Yes, 80, 81, 1));
    let turn = e.observe(&quote(WSH, "WSH", Side::Yes, 83, 84, 2));
    assert_eq!(turn.signals[0].signal_price_cents, 83);
}

#[test]
fn entry_08_84_is_rejected() {
    let mut e = default_entry();
    e.observe(&quote(WSH, "WSH", Side::Yes, 80, 81, 1));
    e.observe(&quote(WSH, "WSH", Side::Yes, 81, 82, 2));
    let turn = e.observe(&quote(WSH, "WSH", Side::Yes, 84, 85, 3));
    assert!(turn.signals.is_empty());
}

#[test]
fn entry_09_different_market_cannot_satisfy_sequence() {
    let mut e = default_entry();
    e.observe(&quote(WSH, "WSH", Side::Yes, 80, 81, 1));
    let turn = e.observe(&quote(COL, "COL", Side::Yes, 81, 82, 2));
    assert!(turn.signals.is_empty());
    assert_eq!(
        e.first_observation(GameId::from_raw(GAME))
            .unwrap()
            .key
            .market_id,
        WSH
    );
}

#[test]
fn entry_10_different_side_cannot_satisfy_sequence() {
    let mut e = default_entry();
    e.observe(&quote(WSH, "WSH", Side::Yes, 80, 81, 1));
    let turn = e.observe(&quote(WSH, "WSH", Side::No, 81, 82, 2));
    assert!(turn.signals.is_empty());
}

#[test]
fn entry_11_wnba_behaves_identically() {
    let mut e = default_entry();
    e.observe(&quote(WSH, "KXWNBAGAME-TEST-A", Side::Yes, 80, 81, 1));
    let turn = e.observe(&quote(WSH, "KXWNBAGAME-TEST-A", Side::Yes, 81, 82, 2));
    assert_eq!(turn.signals.len(), 1);
    assert_eq!(turn.signals[0].strategy, FIRST01_NAME);
}

#[test]
fn entry_12_parameter_override_60_63() {
    let params = EntryParameters {
        first_threshold_cents: 60,
        confirmation_threshold_cents: 61,
        maximum_entry_price_cents: 63,
        lock_threshold_cents: 89,
        require_bid_below_ask: true,
        maker_only: true,
    };
    let mut e = EntryEngine::new(params);
    e.observe(&quote(WSH, "WSH", Side::Yes, 60, 61, 1));
    let turn = e.observe(&quote(WSH, "WSH", Side::Yes, 61, 62, 2));
    assert_eq!(turn.signals.len(), 1);
    assert_eq!(turn.signals[0].strategy, FIRST01_NAME);
    assert_eq!(turn.signals[0].first_threshold_cents, 60);
}

#[test]
fn exit_13_81_entry_produces_40_5_stop() {
    let pos = wsh_position(7, 81);
    assert_eq!(
        pos.stop_threshold_hundredths(&ExitParameters::default()),
        Some(4050)
    );
}

#[test]
fn exit_14_80_bid_does_not_trigger() {
    let mut pos = wsh_position(7, 81);
    let engine = default_exit();
    let turn = engine.observe(&quote(WSH, "WSH", Side::Yes, 80, 81, 3), &mut pos);
    assert!(turn.signals.is_empty());
}

#[test]
fn exit_15_40_bid_triggers() {
    let mut pos = wsh_position(7, 81);
    let engine = default_exit();
    let turn = engine.observe(&quote(WSH, "WSH", Side::Yes, 40, 41, 3), &mut pos);
    assert_eq!(turn.signals.len(), 1);
    assert_eq!(turn.signals[0].trigger_bid_cents, 40);
}

#[test]
fn exit_16_opponent_17_cannot_trigger() {
    let mut pos = wsh_position(7, 81);
    let engine = default_exit();
    let turn = engine.observe(&quote(COL, "COL", Side::Yes, 17, 18, 3), &mut pos);
    assert!(turn.signals.is_empty());
}

#[test]
fn exit_17_opposite_side_cannot_trigger() {
    let mut pos = wsh_position(7, 81);
    let engine = default_exit();
    let turn = engine.observe(&quote(WSH, "WSH", Side::No, 10, 11, 3), &mut pos);
    assert!(turn.signals.is_empty());
}

#[test]
fn exit_18_sharp_gap_triggers_at_24() {
    let mut pos = wsh_position(7, 81);
    let engine = default_exit();
    engine.observe(&quote(WSH, "WSH", Side::Yes, 72, 73, 3), &mut pos);
    engine.observe(&quote(WSH, "WSH", Side::Yes, 55, 56, 4), &mut pos);
    let turn = engine.observe(&quote(WSH, "WSH", Side::Yes, 24, 25, 5), &mut pos);
    assert_eq!(turn.signals[0].trigger_bid_cents, 24);
}

#[test]
fn exit_19_recovery_above_stop_stays_liquidation_active() {
    let mut pos = wsh_position(7, 81);
    let engine = default_exit();
    engine.observe(&quote(WSH, "WSH", Side::Yes, 40, 41, 3), &mut pos);
    assert_eq!(pos.lifecycle, LiquidationState::LiquidationActive);
    let turn = engine.observe(&quote(WSH, "WSH", Side::Yes, 80, 81, 4), &mut pos);
    assert_eq!(turn.signals.len(), 1);
    assert!(turn.signals[0].is_continuation);
    assert_eq!(pos.lifecycle, LiquidationState::LiquidationActive);
}

#[test]
fn exit_20_partial_liquidation_preserves_remaining() {
    let mut pos = wsh_position(7, 81);
    ExitEngine::apply_liquidation_fill(&mut pos, 3);
    assert_eq!(pos.remaining_quantity, 4);
    assert_eq!(pos.lifecycle, LiquidationState::LiquidationActive);
}

#[test]
fn exit_21_zero_fill_remains_active() {
    let mut pos = wsh_position(7, 81);
    let engine = default_exit();
    engine.observe(&quote(WSH, "WSH", Side::Yes, 40, 41, 3), &mut pos);
    ExitEngine::apply_liquidation_fill(&mut pos, 0);
    assert_eq!(pos.remaining_quantity, 7);
    assert_eq!(pos.lifecycle, LiquidationState::LiquidationActive);
}

#[test]
fn exit_22_subsequent_lower_bid_available() {
    let mut pos = wsh_position(7, 81);
    let engine = default_exit();
    engine.observe(&quote(WSH, "WSH", Side::Yes, 40, 41, 3), &mut pos);
    ExitEngine::apply_liquidation_fill(&mut pos, 0);
    let turn = engine.observe(&quote(WSH, "WSH", Side::Yes, 24, 25, 4), &mut pos);
    assert_eq!(turn.signals[0].trigger_bid_cents, 24);
}

#[test]
fn exit_23_different_game_market_cannot_affect_position() {
    let mut pos = wsh_position(7, 81);
    let engine = default_exit();
    let other = StrategyQuote {
        game_id: GameId::from_raw(99),
        market_id: MarketId::from_raw(999),
        ticker: "OTHER".into(),
        side: Side::Yes,
        yes_bid_cents: 10,
        yes_ask_cents: 11,
        exchange_timestamp_ms: quote(WSH, "WSH", Side::Yes, 10, 11, 5).exchange_timestamp_ms,
        received_timestamp: quote(WSH, "WSH", Side::Yes, 10, 11, 5).received_timestamp,
        sequence_gap: false,
    };
    assert!(engine.observe(&other, &mut pos).signals.is_empty());
}

#[test]
fn exit_24_wnba_opponent_market_cannot_trigger() {
    let mut pos = ResearchPosition::new(
        PositionId::from_raw(50),
        GameId::from_raw(GAME),
        MarketId::from_raw(WSH),
        Side::Yes,
        "KXWNBAGAME-A",
        vec![ResearchPositionFill {
            quantity_contracts: 5,
            price_cents: 81,
        }],
    );
    let engine = default_exit();
    assert!(
        engine
            .observe(&quote(COL, "KXWNBAGAME-B", Side::Yes, 17, 18, 3), &mut pos)
            .signals
            .is_empty()
    );
}

#[test]
fn exit_25_restart_preserves_market_and_side() {
    let mut e = default_entry();
    e.observe(&quote(WSH, "WSH", Side::Yes, 80, 81, 1));
    let snap = e.snapshot_game(GameId::from_raw(GAME));
    let mut e2 = default_entry();
    e2.restore_game(snap);
    let first = e2.first_observation(GameId::from_raw(GAME)).unwrap();
    assert_eq!(first.key.market_id, WSH);
    assert_eq!(first.key.side, Side::Yes);
}

#[test]
fn exit_26_no_lookahead_on_entry() {
    let mut e = default_entry();
    e.observe(&quote(WSH, "WSH", Side::Yes, 80, 81, 1));
    let early = e.observe(&quote(WSH, "WSH", Side::Yes, 79, 80, 2));
    assert!(early.signals.is_empty());
}

#[test]
fn override_entry_60_63_preserves_strategy_name() {
    let overrides = ExperimentOverrides {
        entry: Some(EntryParameters {
            first_threshold_cents: 60,
            confirmation_threshold_cents: 61,
            maximum_entry_price_cents: 63,
            ..EntryParameters::default()
        }),
        ..ExperimentOverrides::default()
    };
    let meta = StrategyRunMetadata::for_first01(&overrides);
    assert_eq!(meta.strategy_name, FIRST01_NAME);
    assert_eq!(meta.parameter_set.entry.first_threshold_cents, 60);
    let model = First01Model::definition();
    assert_eq!(model.default_entry.first_threshold_cents, 80);
}

#[test]
fn override_exit_40_percent_without_changing_first01_defaults() {
    let overrides = ExperimentOverrides {
        exit: Some(ExitParameters {
            loss_numerator: 2,
            loss_denominator: 5,
        }),
        ..ExperimentOverrides::default()
    };
    let effective = EffectiveParameters::resolve(&overrides);
    assert_eq!(effective.exit.loss_numerator, 2);
    assert_eq!(First01Model::definition().default_exit.loss_denominator, 2);
    let pos = wsh_position(7, 81);
    let stop = pos.stop_threshold_hundredths(&effective.exit).unwrap();
    assert_eq!(stop, 3240);
}

#[test]
fn first01_version_is_stable() {
    let model = First01Model::definition();
    assert_eq!(model.name, FIRST01_NAME);
    assert_eq!(model.version, FIRST01_VERSION);
}

#[test]
fn sequence_gap_rejects_quote() {
    let mut q = quote(WSH, "WSH", Side::Yes, 80, 81, 1);
    q.sequence_gap = true;
    let mut e = default_entry();
    let turn = e.observe(&q);
    assert!(turn.signals.is_empty());
    assert!(turn.reject.is_some());
}
