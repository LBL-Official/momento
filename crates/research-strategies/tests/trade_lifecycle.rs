//! FIRST01 one-trade-per-game invariant tests.

use chrono::{TimeZone, Utc};
use momento_core::{GameId, MarketId, Side};
use momento_research_strategies::{
    EntryContext, EntryEngine, EntryParameters, EntryPhase, GameTradePhase, LifecycleAction,
};

const GAME_A: u128 = 10;
const GAME_B: u128 = 11;
const WSH: u128 = 200;
const COL: u128 = 201;

fn quote(
    game: u128,
    market: u128,
    ticker: &str,
    bid: u16,
    ask: u16,
    sec: i64,
) -> momento_research_strategies::StrategyQuote {
    let t = Utc.with_ymd_and_hms(2026, 8, 24, 18, 0, 0).unwrap() + chrono::Duration::seconds(sec);
    momento_research_strategies::StrategyQuote {
        game_id: GameId::from_raw(game),
        market_id: MarketId::from_raw(market),
        ticker: ticker.into(),
        side: Side::Yes,
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

fn observe_prices(engine: &mut EntryEngine, game: u128, market: u128, prices: &[(u16, u16)]) {
    for (i, (bid, ask)) in prices.iter().enumerate() {
        engine.observe_with_context(
            &quote(game, market, "T", *bid, *ask, i as i64 + 1),
            &EntryContext::default(),
        );
    }
}

#[test]
fn one_80_81_creates_one_opportunity() {
    let mut e = default_entry();
    e.observe_with_context(
        &quote(GAME_A, WSH, "WSH", 80, 81, 1),
        &EntryContext::default(),
    );
    let turn = e.observe_with_context(
        &quote(GAME_A, WSH, "WSH", 81, 82, 2),
        &EntryContext::default(),
    );
    assert!(turn.new_opportunity.is_some());
    assert_eq!(turn.intents.len(), 1);
    assert_eq!(
        turn.intents[0].entry_reason,
        momento_research_strategies::ENTRY_REASON_FIRST01
    );
}

#[test]
fn repeated_qualifying_quotes_create_zero_additional_opportunities() {
    let mut e = default_entry();
    observe_prices(&mut e, GAME_A, WSH, &[(80, 81), (81, 82)]);
    let mut extra_opps = 0;
    let mut extra_intents = 0;
    for (i, (bid, ask)) in [(82, 83), (83, 84), (82, 83), (81, 82)].iter().enumerate() {
        let turn = e.observe_with_context(
            &quote(GAME_A, WSH, "WSH", *bid, *ask, 10 + i as i64),
            &EntryContext {
                has_working_entry: true,
                ..Default::default()
            },
        );
        if turn.new_opportunity.is_some() {
            extra_opps += 1;
        }
        extra_intents += turn.intents.len();
        assert!(
            matches!(
                turn.quote_observation.as_ref().map(|o| o.lifecycle_action),
                Some(LifecycleAction::SuppressedByWorkingEntry)
                    | Some(LifecycleAction::SuppressedByExistingGameTrade)
            ),
            "expected suppression, got {:?}",
            turn.quote_observation.as_ref().map(|o| o.lifecycle_action)
        );
    }
    assert_eq!(extra_opps, 0);
    assert_eq!(extra_intents, 0);
}

#[test]
fn repeated_80_81_sequences_same_game_create_zero_additional_opportunities() {
    let mut e = default_entry();
    observe_prices(&mut e, GAME_A, WSH, &[(80, 81), (81, 82)]);
    // Simulate unfilled order ended — same opportunity consumed.
    let turn = e.observe_with_context(
        &quote(GAME_A, WSH, "WSH", 81, 82, 20),
        &EntryContext::default(),
    );
    assert!(turn.new_opportunity.is_none());
    assert!(turn.intents.is_empty());
    assert!(e.canonical_lifecycle_consumed(GameId::from_raw(GAME_A)));
}

#[test]
fn opponent_market_cannot_create_second_first01_trade() {
    let mut e = default_entry();
    observe_prices(&mut e, GAME_A, WSH, &[(80, 81), (81, 82)]);
    let turn = e.observe_with_context(
        &quote(GAME_A, COL, "COL", 81, 82, 5),
        &EntryContext::default(),
    );
    assert!(turn.new_opportunity.is_none());
    assert!(turn.intents.is_empty());
    assert_eq!(
        turn.quote_observation.unwrap().lifecycle_action,
        LifecycleAction::SuppressedByOpponentMarket
    );
}

#[test]
fn unfilled_order_does_not_create_second_trade() {
    let mut e = default_entry();
    observe_prices(&mut e, GAME_A, WSH, &[(80, 81), (81, 82)]);
    e.observe_with_context(
        &quote(GAME_A, WSH, "WSH", 82, 83, 5),
        &EntryContext {
            has_working_entry: true,
            ..Default::default()
        },
    );
    // Working cleared, still unfilled.
    let turn = e.observe_with_context(
        &quote(GAME_A, WSH, "WSH", 82, 83, 6),
        &EntryContext::default(),
    );
    assert!(turn.new_opportunity.is_none());
    assert_eq!(
        e.active_opportunity(GameId::from_raw(GAME_A))
            .map(|o| o.game_id),
        Some(GAME_A)
    );
}

#[test]
fn game_lock_does_not_reset_lifecycle() {
    let mut e = default_entry();
    observe_prices(&mut e, GAME_A, WSH, &[(80, 81), (81, 82)]);
    e.observe_with_context(
        &quote(GAME_A, WSH, "WSH", 89, 90, 5),
        &EntryContext {
            has_working_entry: true,
            position_filled_qty: 3,
            position_net_qty: 3,
            ..Default::default()
        },
    );
    assert_eq!(e.phase(GameId::from_raw(GAME_A)), EntryPhase::GameLocked);
    assert!(e.canonical_lifecycle_consumed(GameId::from_raw(GAME_A)));
    let later = e.observe_with_context(
        &quote(GAME_A, WSH, "WSH", 81, 82, 6),
        &EntryContext::default(),
    );
    assert!(later.new_opportunity.is_none());
    assert!(later.intents.is_empty());
}

#[test]
fn completed_trade_does_not_allow_new_opportunity() {
    let mut e = default_entry();
    observe_prices(&mut e, GAME_A, WSH, &[(80, 81), (81, 82)]);
    let had_position = EntryContext {
        position_filled_qty: 7,
        position_net_qty: 7,
        remaining_entry_qty: 0,
        position_entry_closed: false,
        ..Default::default()
    };
    e.observe_with_context(&quote(GAME_A, WSH, "WSH", 82, 83, 11), &had_position);
    let flat = EntryContext {
        position_filled_qty: 7,
        position_net_qty: 0,
        remaining_entry_qty: 0,
        position_entry_closed: true,
        ..Default::default()
    };
    let after = e.observe_with_context(&quote(GAME_A, WSH, "WSH", 83, 84, 12), &flat);
    assert!(after.new_opportunity.is_none());
    assert!(after.intents.is_empty());
    assert!(e.canonical_lifecycle_consumed(GameId::from_raw(GAME_A)));
}

#[test]
fn two_games_each_create_one_opportunity() {
    let mut e = default_entry();
    observe_prices(&mut e, GAME_A, WSH, &[(80, 81), (81, 82)]);
    observe_prices(&mut e, GAME_B, WSH, &[(80, 81), (81, 82)]);
    assert!(e.active_opportunity(GameId::from_raw(GAME_A)).is_some());
    assert!(e.active_opportunity(GameId::from_raw(GAME_B)).is_some());
    assert_ne!(
        e.active_opportunity(GameId::from_raw(GAME_A))
            .unwrap()
            .trade_id,
        e.active_opportunity(GameId::from_raw(GAME_B))
            .unwrap()
            .trade_id
    );
}

#[test]
fn quote_observations_remain_for_diagnostics() {
    let mut e = default_entry();
    let t1 = e.observe_with_context(
        &quote(GAME_A, WSH, "WSH", 80, 81, 1),
        &EntryContext::default(),
    );
    assert!(t1.quote_observation.is_some());
    let t2 = e.observe_with_context(
        &quote(GAME_A, WSH, "WSH", 81, 82, 2),
        &EntryContext::default(),
    );
    assert!(t2.quote_observation.is_some());
    assert_eq!(
        t2.quote_observation.unwrap().lifecycle_action,
        LifecycleAction::OpportunityCreated
    );
}

#[test]
fn working_entry_blocks_second_intent() {
    let mut e = default_entry();
    observe_prices(&mut e, GAME_A, WSH, &[(80, 81), (81, 82)]);
    let second = e.observe_with_context(
        &quote(GAME_A, WSH, "WSH", 82, 83, 3),
        &EntryContext {
            has_working_entry: true,
            ..Default::default()
        },
    );
    assert!(second.intents.is_empty());
}

#[test]
fn open_position_blocks_second_opportunity() {
    let mut e = default_entry();
    observe_prices(&mut e, GAME_A, WSH, &[(80, 81), (81, 82)]);
    let turn = e.observe_with_context(
        &quote(GAME_A, WSH, "WSH", 82, 83, 3),
        &EntryContext {
            position_filled_qty: 3,
            position_net_qty: 3,
            remaining_entry_qty: 0,
            ..Default::default()
        },
    );
    assert!(turn.new_opportunity.is_none());
    assert!(turn.intents.is_empty());
    assert_eq!(
        e.game_trade_phase(GameId::from_raw(GAME_A)),
        GameTradePhase::PositionOpen
    );
}

#[test]
fn liquidation_active_blocks_new_entry() {
    let mut e = default_entry();
    observe_prices(&mut e, GAME_A, WSH, &[(80, 81), (81, 82)]);
    let turn = e.observe_with_context(
        &quote(GAME_A, WSH, "WSH", 82, 83, 5),
        &EntryContext {
            position_filled_qty: 7,
            position_net_qty: 4,
            liquidation_active: true,
            ..Default::default()
        },
    );
    assert!(turn.intents.is_empty());
}
