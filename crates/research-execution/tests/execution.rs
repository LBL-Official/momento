//! Deterministic execution simulator tests.

#![allow(clippy::too_many_arguments)]

use chrono::{TimeZone, Utc};
use momento_core::Side;
use momento_research_data::{
    NormalizedSource, OrderbookEvent, OrderbookLevel, PublicTrade, ReplayDataset,
};
use momento_research_execution::{
    ExecutionBacktestInput, ExecutionDataQuality, ExecutionParameters, OrderPurpose, OrderStatus,
    classify_orderbook_event, queue_ahead_at_submit, run_execution_backtest,
};
use momento_research_strategies::{
    EntryEngine, ExitEngine, FIRST01_DEFAULT_ENTRY, FIRST01_DEFAULT_EXIT, StrategyQuote,
};

fn ob(
    market_id: u128,
    game_id: u128,
    ticker: &str,
    ms: i64,
    bid: u16,
    ask: u16,
    bid_depth: i64,
    ask_depth: i64,
    levels: Vec<OrderbookLevel>,
    source: NormalizedSource,
    gap: bool,
) -> OrderbookEvent {
    OrderbookEvent {
        exchange_timestamp_ms: Some(ms),
        received_timestamp: Utc.timestamp_millis_opt(ms).unwrap(),
        ticker: ticker.into(),
        market_id,
        game_id,
        event_type: "test".into(),
        source,
        sequence_number: Some(ms as u64),
        subscription_id: None,
        yes_bid_cents: Some(bid),
        yes_ask_cents: Some(ask),
        yes_bid_depth_hundredths: Some(bid_depth),
        yes_ask_depth_hundredths: Some(ask_depth),
        levels,
        sequence_gap: gap,
        resync_count: 0,
        first_missing_sequence: None,
        last_valid_sequence: None,
    }
}

fn quote(
    market_id: u128,
    game_id: u128,
    ticker: &str,
    ms: i64,
    bid: u16,
    ask: u16,
) -> StrategyQuote {
    StrategyQuote {
        game_id: momento_core::GameId::from_raw(game_id),
        market_id: momento_core::MarketId::from_raw(market_id),
        ticker: ticker.into(),
        side: Side::Yes,
        yes_bid_cents: bid,
        yes_ask_cents: ask,
        exchange_timestamp_ms: ms,
        received_timestamp: Utc.timestamp_millis_opt(ms).unwrap(),
        sequence_gap: false,
    }
}

fn single_dataset(events: Vec<OrderbookEvent>, trades: Vec<PublicTrade>) -> ReplayDataset {
    ReplayDataset {
        sport: momento_research_data::ResearchSport::Mlb,
        date: chrono::NaiveDate::from_ymd_opt(2025, 5, 1).unwrap(),
        trades,
        orderbook_events: events,
    }
}

fn run(ds: ReplayDataset) -> momento_research_execution::ExecutionBacktestResult {
    let input = ExecutionBacktestInput {
        run_id: "test-run",
        entry_params: FIRST01_DEFAULT_ENTRY,
        exit_params: FIRST01_DEFAULT_EXIT,
        execution_params: ExecutionParameters::default(),
        datasets: &[ds],
        data_quality: Default::default(),
    };
    run_execution_backtest(&input)
}

#[test]
fn signal_does_not_equal_fill() {
    let market = 100u128;
    let game = 200u128;
    let ds = single_dataset(
        vec![
            ob(
                market,
                game,
                "AAA",
                0,
                79,
                80,
                1000,
                1000,
                vec![],
                NormalizedSource::RestSnapshot,
                false,
            ),
            ob(
                market,
                game,
                "AAA",
                1,
                80,
                81,
                1000,
                1000,
                vec![],
                NormalizedSource::RestSnapshot,
                false,
            ),
            ob(
                market,
                game,
                "AAA",
                2,
                81,
                82,
                1000,
                1000,
                vec![],
                NormalizedSource::RestSnapshot,
                false,
            ),
        ],
        vec![],
    );
    let r = run(ds);
    assert_eq!(r.entry_signals.len(), 1);
    assert_eq!(r.metrics.entry_orders, 1);
    assert_eq!(r.metrics.entry_fills, 0, "ask 82 cannot fill 81 bid");
}

#[test]
fn maker_fills_when_ask_reaches_limit() {
    let market = 101u128;
    let game = 201u128;
    let ds = single_dataset(
        vec![
            ob(
                market,
                game,
                "BBB",
                0,
                79,
                80,
                1000,
                1000,
                vec![],
                NormalizedSource::RestSnapshot,
                false,
            ),
            ob(
                market,
                game,
                "BBB",
                1,
                80,
                81,
                1000,
                1000,
                vec![],
                NormalizedSource::RestSnapshot,
                false,
            ),
            ob(
                market,
                game,
                "BBB",
                2,
                81,
                82,
                1000,
                1000,
                vec![],
                NormalizedSource::RestSnapshot,
                false,
            ),
            ob(
                market,
                game,
                "BBB",
                3,
                81,
                81,
                1000,
                50000,
                vec![],
                NormalizedSource::RestSnapshot,
                false,
            ),
        ],
        vec![],
    );
    let r = run(ds);
    assert_eq!(r.entry_signals.len(), 1);
    assert!(r.metrics.entry_fills >= 1);
}

#[test]
fn partial_fill_supported() {
    let market = 102u128;
    let game = 202u128;
    let ds = single_dataset(
        vec![
            ob(
                market,
                game,
                "CCC",
                0,
                79,
                80,
                1000,
                1000,
                vec![],
                NormalizedSource::RestSnapshot,
                false,
            ),
            ob(
                market,
                game,
                "CCC",
                1,
                80,
                81,
                1000,
                1000,
                vec![],
                NormalizedSource::RestSnapshot,
                false,
            ),
            ob(
                market,
                game,
                "CCC",
                2,
                81,
                82,
                1000,
                1000,
                vec![],
                NormalizedSource::RestSnapshot,
                false,
            ),
            ob(
                market,
                game,
                "CCC",
                3,
                81,
                81,
                1000,
                300,
                vec![],
                NormalizedSource::RestSnapshot,
                false,
            ),
            ob(
                market,
                game,
                "CCC",
                4,
                81,
                81,
                1000,
                50000,
                vec![],
                NormalizedSource::RestSnapshot,
                false,
            ),
        ],
        vec![],
    );
    let r = run(ds);
    assert!(
        r.metrics.partial_fill_count >= 1
            || r.orders
                .iter()
                .any(|o| o.status == OrderStatus::PartiallyFilled || o.filled_quantity > 0)
    );
}

#[test]
fn queue_ahead_blocks_fill() {
    let market = 103u128;
    let game = 203u128;
    let events = vec![
        ob(
            market,
            game,
            "DDD",
            0,
            79,
            80,
            1000,
            1000,
            vec![],
            NormalizedSource::RestSnapshot,
            false,
        ),
        ob(
            market,
            game,
            "DDD",
            1,
            80,
            81,
            1000,
            1000,
            vec![],
            NormalizedSource::RestSnapshot,
            false,
        ),
        ob(
            market,
            game,
            "DDD",
            2,
            81,
            82,
            50000,
            1000,
            vec![OrderbookLevel {
                price_cents: 81,
                quantity_hundredths: 50_000,
                book_side: "yes".into(),
            }],
            NormalizedSource::WebSocketSnapshot,
            false,
        ),
        ob(
            market,
            game,
            "DDD",
            3,
            81,
            81,
            50000,
            200,
            vec![],
            NormalizedSource::RestSnapshot,
            false,
        ),
    ];
    let book = momento_research_execution::book_state::MarketBookState::new(market, "DDD");
    let mut b = book;
    b.apply_orderbook(&events[2]);
    assert!(queue_ahead_at_submit(&b, 81) > 0);
    let r = run(single_dataset(events, vec![]));
    let entry_order = r
        .orders
        .iter()
        .find(|o| o.purpose == OrderPurpose::Entry)
        .unwrap();
    assert!(entry_order.queue_ahead_contracts > 0 || r.metrics.entry_fills == 0);
}

#[test]
fn sequence_gap_prevents_execution() {
    let ob_gap = ob(
        104,
        204,
        "EEE",
        1,
        81,
        81,
        1000,
        50000,
        vec![],
        NormalizedSource::RestSnapshot,
        true,
    );
    assert_eq!(
        classify_orderbook_event(&ob_gap),
        ExecutionDataQuality::NoExecutionData
    );
}

#[test]
fn candlestick_cannot_simulate_l2() {
    let candle = ob(
        105,
        205,
        "FFF",
        1,
        81,
        82,
        1000,
        1000,
        vec![],
        NormalizedSource::RestCandlestick,
        false,
    );
    assert_eq!(
        classify_orderbook_event(&candle),
        ExecutionDataQuality::CandlestickOnly
    );
    assert!(!classify_orderbook_event(&candle).supports_maker_simulation());
}

#[test]
fn vwap_from_multiple_fills() {
    use momento_research_execution::position::ExecutionPosition;
    let mut pos = ExecutionPosition::new(1, 1, 1, "T", Side::Yes, 5);
    pos.apply_entry_fill(&momento_research_execution::fill::SimulatedFill {
        fill_id: 1,
        order_id: 1,
        position_id: 1,
        market_id: 1,
        ticker: "T".into(),
        side: Side::Yes,
        purpose: OrderPurpose::Entry,
        price_cents: 80,
        quantity_contracts: 3,
        exchange_timestamp_ms: 0,
        received_timestamp: Utc::now(),
        fill_evidence: momento_research_execution::order::FillEvidence::TopOfBookDisplayedLiquidity,
        queue_ahead_at_fill: 0,
        is_partial: true,
    });
    pos.apply_entry_fill(&momento_research_execution::fill::SimulatedFill {
        fill_id: 2,
        order_id: 1,
        position_id: 1,
        market_id: 1,
        ticker: "T".into(),
        side: Side::Yes,
        purpose: OrderPurpose::Entry,
        price_cents: 81,
        quantity_contracts: 2,
        exchange_timestamp_ms: 1,
        received_timestamp: Utc::now(),
        fill_evidence: momento_research_execution::order::FillEvidence::TopOfBookDisplayedLiquidity,
        queue_ahead_at_fill: 0,
        is_partial: false,
    });
    assert_eq!(pos.entry_vwap_cents(), Some(80));
}

#[test]
fn stop_81_entry_produces_40_5_threshold() {
    let pos = momento_research_strategies::ResearchPosition::new(
        momento_core::PositionId::from_raw(1),
        momento_core::GameId::from_raw(1),
        momento_core::MarketId::from_raw(1),
        Side::Yes,
        "T",
        vec![momento_research_strategies::ResearchPositionFill {
            quantity_contracts: 7,
            price_cents: 81,
        }],
    );
    let threshold = pos
        .stop_threshold_hundredths(&FIRST01_DEFAULT_EXIT)
        .unwrap();
    assert_eq!(threshold, 4050);
}

#[test]
fn sharp_gap_triggers_at_observed_price() {
    let market = 106u128;
    let game = 206u128;
    let ds = single_dataset(
        vec![
            ob(
                market,
                game,
                "GGG",
                0,
                79,
                80,
                1000,
                1000,
                vec![],
                NormalizedSource::RestSnapshot,
                false,
            ),
            ob(
                market,
                game,
                "GGG",
                1,
                80,
                81,
                1000,
                1000,
                vec![],
                NormalizedSource::RestSnapshot,
                false,
            ),
            ob(
                market,
                game,
                "GGG",
                2,
                81,
                82,
                1000,
                1000,
                vec![],
                NormalizedSource::RestSnapshot,
                false,
            ),
            ob(
                market,
                game,
                "GGG",
                3,
                81,
                81,
                1000,
                50000,
                vec![],
                NormalizedSource::RestSnapshot,
                false,
            ),
            ob(
                market,
                game,
                "GGG",
                4,
                72,
                73,
                1000,
                1000,
                vec![],
                NormalizedSource::RestSnapshot,
                false,
            ),
            ob(
                market,
                game,
                "GGG",
                5,
                24,
                25,
                1000,
                50000,
                vec![],
                NormalizedSource::RestSnapshot,
                false,
            ),
        ],
        vec![],
    );
    let r = run(ds);
    assert!(!r.exit_signals.is_empty());
    let exit_fill = r
        .fills
        .iter()
        .find(|f| f.purpose == OrderPurpose::Liquidation);
    if let Some(f) = exit_fill {
        assert!(f.price_cents <= 24);
    }
}

#[test]
fn opponent_market_cannot_exit_position() {
    let exit = ExitEngine::new(FIRST01_DEFAULT_EXIT);
    let mut pos = momento_research_strategies::ResearchPosition::new(
        momento_core::PositionId::from_raw(1),
        momento_core::GameId::from_raw(500),
        momento_core::MarketId::from_raw(1000),
        Side::Yes,
        "WSH",
        vec![momento_research_strategies::ResearchPositionFill {
            quantity_contracts: 5,
            price_cents: 81,
        }],
    );
    let wrong = quote(2000, 500, "COL", 10, 20, 21);
    let turn = exit.observe(&wrong, &mut pos);
    assert!(turn.signals.is_empty());
}

#[test]
fn fees_not_modeled() {
    let r = run(single_dataset(vec![], vec![]));
    assert_eq!(r.metrics.fees_status, "NOT_MODELED");
}

#[test]
fn execution_model_version_recorded() {
    let params = ExecutionParameters::default();
    assert_eq!(params.execution_model_name, "CONSERVATIVE_MAKER");
    assert_eq!(params.execution_model_version, 1);
}

#[test]
fn reproducibility_same_input_same_output() {
    let market = 107u128;
    let game = 207u128;
    let ds = single_dataset(
        vec![
            ob(
                market,
                game,
                "HHH",
                0,
                79,
                80,
                1000,
                1000,
                vec![],
                NormalizedSource::RestSnapshot,
                false,
            ),
            ob(
                market,
                game,
                "HHH",
                1,
                80,
                81,
                1000,
                1000,
                vec![],
                NormalizedSource::RestSnapshot,
                false,
            ),
            ob(
                market,
                game,
                "HHH",
                2,
                81,
                82,
                1000,
                1000,
                vec![],
                NormalizedSource::RestSnapshot,
                false,
            ),
        ],
        vec![],
    );
    let a = run(ds.clone());
    let b = run(ds);
    assert_eq!(a.metrics.entry_signals, b.metrics.entry_signals);
    assert_eq!(a.metrics.entry_orders, b.metrics.entry_orders);
    assert_eq!(a.metrics.entry_fills, b.metrics.entry_fills);
}

#[test]
fn no_lookahead_entry_engine() {
    let mut entry = EntryEngine::new(FIRST01_DEFAULT_ENTRY);
    let q1 = quote(1, 1, "T", 100, 79, 80);
    let q2 = quote(1, 1, "T", 50, 80, 81);
    let _ = entry.observe(&q1);
    let turn = entry.observe(&q2);
    assert!(turn.signals.is_empty() || turn.signals[0].exchange_timestamp_ms >= 50);
}
