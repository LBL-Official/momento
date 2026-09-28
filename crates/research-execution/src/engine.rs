//! Unified execution backtest engine: signals + fills + P&L.

use std::collections::HashMap;

use chrono::Utc;
use momento_core::{GameId, MarketId, Side};
use momento_research_data::replay::ReplayItem;
use momento_research_data::{OrderbookEvent, ReplayDataset};
use momento_research_strategies::{
    EntryContext, EntryEngine, EntryIntent, EntryOpportunity, ExitEngine, ExitSignal,
    LiquidationState, QuoteObservation, ResearchPosition, StrategyQuote,
};

use crate::book_state::MarketBookState;
use crate::entry_sim::{queue_ahead_at_submit, try_entry_fill};
use crate::exit_sim::try_liquidation_fill;
use crate::fill::SimulatedFill;
use crate::metrics::{DataQualityMetrics, RunMetrics, compute_run_metrics};
use crate::order::{OrderPurpose, SimulatedOrder};
use crate::params::ExecutionParameters;
use crate::pnl::{PortfolioPnl, compute_portfolio_pnl};
use crate::position::ExecutionPosition;
use crate::quality::{ExecutionDataQuality, aggregate_execution_quality, classify_orderbook_event};

#[derive(Clone, Debug)]
pub struct ExecutionBacktestResult {
    pub quote_observations: Vec<QuoteObservation>,
    pub entry_opportunities: Vec<EntryOpportunity>,
    pub entry_intents: Vec<EntryIntent>,
    pub entry_signals: Vec<momento_research_strategies::EntrySignal>,
    pub exit_signals: Vec<ExitSignal>,
    pub orders: Vec<SimulatedOrder>,
    pub fills: Vec<SimulatedFill>,
    pub positions: Vec<ExecutionPosition>,
    pub portfolio_pnl: PortfolioPnl,
    pub metrics: RunMetrics,
    pub events_processed: u64,
    pub quotes_observed: u64,
    pub sequence_gap_rejects: u64,
    pub first_entry_exchange_ms: Option<i64>,
    pub last_entry_exchange_ms: Option<i64>,
    pub execution_parameters: ExecutionParameters,
    pub final_marks: Vec<(u128, u16)>,
}

pub struct ExecutionBacktestInput<'a> {
    pub run_id: &'a str,
    pub entry_params: momento_research_strategies::EntryParameters,
    pub exit_params: momento_research_strategies::ExitParameters,
    pub execution_params: ExecutionParameters,
    pub datasets: &'a [ReplayDataset],
    pub data_quality: DataQualityMetrics,
}

pub fn run_execution_backtest(input: &ExecutionBacktestInput<'_>) -> ExecutionBacktestResult {
    let mut entry = EntryEngine::new(input.entry_params);
    let exit = ExitEngine::new(input.exit_params);
    let params = input.execution_params.clone();

    let mut books: HashMap<u128, MarketBookState> = HashMap::new();
    let mut orders: Vec<SimulatedOrder> = Vec::new();
    let mut fills: Vec<SimulatedFill> = Vec::new();
    let mut positions: Vec<ExecutionPosition> = Vec::new();
    let mut quote_observations: Vec<QuoteObservation> = Vec::new();
    let mut entry_opportunities: Vec<EntryOpportunity> = Vec::new();
    let mut entry_intents: Vec<EntryIntent> = Vec::new();
    let mut entry_signals: Vec<momento_research_strategies::EntrySignal> = Vec::new();
    let mut exit_signals: Vec<ExitSignal> = Vec::new();
    let mut quality_samples: Vec<ExecutionDataQuality> = Vec::new();
    let mut events_processed = 0u64;
    let mut quotes_observed = 0u64;
    let mut sequence_gap_rejects = 0u64;
    let mut first_entry_exchange_ms = None;
    let mut last_entry_exchange_ms = None;
    let mut next_order_id = 1u64;
    let mut next_fill_id = 1u64;
    let mut next_position_id = 1u128;
    let mut stop_gap_count = 0u64;
    let mut failed_exit_attempts = 0u64;
    let mut last_marks: HashMap<u128, u16> = HashMap::new();

    let events = collect_chronological_events(input.datasets);
    let mut last_ms = i64::MIN;

    for event in events {
        events_processed += 1;
        let exchange_ms = event_exchange_ms(&event);
        assert!(
            exchange_ms >= last_ms,
            "no-lookahead chronological order violated"
        );
        last_ms = exchange_ms;

        match &event {
            ChronologicalEvent::Trade(trade) => {
                process_trade_queue(&mut orders, trade);
            }
            ChronologicalEvent::Orderbook(ob) => {
                let quality = classify_orderbook_event(ob);
                quality_samples.push(quality);
                if ob.sequence_gap {
                    sequence_gap_rejects += 1;
                }

                let book = books
                    .entry(ob.market_id)
                    .or_insert_with(|| MarketBookState::new(ob.market_id, ob.ticker.clone()));
                book.apply_orderbook(ob);

                if let (Some(bid), false) = (book.best_bid, book.sequence_gap) {
                    last_marks.insert(ob.market_id, bid);
                }

                try_fill_working_orders(
                    &mut orders,
                    &mut fills,
                    &mut positions,
                    book,
                    exchange_ms,
                    &params,
                    &mut next_fill_id,
                );

                if let Some(quote) = orderbook_to_quote(ob) {
                    quotes_observed += 1;
                    process_strategy_quote(
                        quote,
                        &mut entry,
                        &exit,
                        &params,
                        input.run_id,
                        book,
                        &mut quote_observations,
                        &mut entry_opportunities,
                        &mut entry_intents,
                        &mut entry_signals,
                        &mut exit_signals,
                        &mut orders,
                        &mut positions,
                        &mut first_entry_exchange_ms,
                        &mut last_entry_exchange_ms,
                        &mut next_order_id,
                        &mut next_position_id,
                        &mut stop_gap_count,
                        &mut failed_exit_attempts,
                    );

                    try_fill_working_orders(
                        &mut orders,
                        &mut fills,
                        &mut positions,
                        book,
                        exchange_ms,
                        &params,
                        &mut next_fill_id,
                    );
                }
            }
        }
    }

    for pos in &mut positions {
        pos.mark_open_at_end();
    }

    let marks: Vec<(u128, u16)> = last_marks.into_iter().collect();
    let portfolio = compute_portfolio_pnl(&positions, &marks, params.fees_model);
    let aggregate_quality = aggregate_execution_quality(&quality_samples);
    let mut dq = input.data_quality.clone();
    dq.execution_data_quality = aggregate_quality.as_str().into();
    dq.sequence_gap_count = sequence_gap_rejects;

    let metrics = compute_run_metrics(
        quote_observations.len() as u64,
        entry_opportunities.len() as u64,
        entry_intents.len() as u64,
        entry_signals.len() as u64,
        exit_signals.len() as u64,
        &orders,
        &fills,
        &positions,
        &portfolio,
        dq,
        sequence_gap_rejects,
        stop_gap_count,
        failed_exit_attempts,
    );

    ExecutionBacktestResult {
        quote_observations,
        entry_opportunities,
        entry_intents,
        entry_signals,
        exit_signals,
        orders,
        fills,
        positions,
        portfolio_pnl: portfolio,
        metrics,
        events_processed,
        quotes_observed,
        sequence_gap_rejects,
        first_entry_exchange_ms,
        last_entry_exchange_ms,
        execution_parameters: params,
        final_marks: marks,
    }
}

enum ChronologicalEvent {
    Trade(momento_research_data::PublicTrade),
    Orderbook(OrderbookEvent),
}

fn collect_chronological_events(datasets: &[ReplayDataset]) -> Vec<ChronologicalEvent> {
    let mut events = Vec::new();
    for ds in datasets {
        for item in ds.cursor().events_chronological() {
            match item {
                ReplayItem::Trade(t) => {
                    events.push(ChronologicalEvent::Trade((*t).clone()));
                }
                ReplayItem::Orderbook(o) => {
                    events.push(ChronologicalEvent::Orderbook((*o).clone()));
                }
            }
        }
    }
    events.sort_by_key(event_exchange_ms);
    events
}

fn event_exchange_ms(event: &ChronologicalEvent) -> i64 {
    match event {
        ChronologicalEvent::Trade(t) => t
            .exchange_timestamp
            .parse::<chrono::DateTime<Utc>>()
            .map(|d| d.timestamp_millis())
            .unwrap_or_else(|_| t.received_timestamp.timestamp_millis()),
        ChronologicalEvent::Orderbook(o) => o
            .exchange_timestamp_ms
            .unwrap_or_else(|| o.received_timestamp.timestamp_millis()),
    }
}

fn process_trade_queue(orders: &mut [SimulatedOrder], trade: &momento_research_data::PublicTrade) {
    for order in orders.iter_mut() {
        if order.purpose != OrderPurpose::Entry || order.remaining_quantity == 0 {
            continue;
        }
        if order.market_id != trade.market_id {
            continue;
        }
        if trade.yes_price_cents == order.limit_price_cents {
            let consumed =
                crate::book_state::hundredths_to_contracts(Some(trade.quantity_hundredths));
            order.queue_ahead_contracts = order.queue_ahead_contracts.saturating_sub(consumed);
        }
    }
}

#[allow(clippy::ptr_arg)]
fn try_fill_working_orders(
    orders: &mut Vec<SimulatedOrder>,
    fills: &mut Vec<SimulatedFill>,
    positions: &mut Vec<ExecutionPosition>,
    book: &MarketBookState,
    exchange_ms: i64,
    params: &ExecutionParameters,
    next_fill_id: &mut u64,
) {
    for order in orders.iter_mut() {
        if order.remaining_quantity == 0 {
            continue;
        }
        if order.market_id != book.market_id {
            continue;
        }
        let fill = match order.purpose {
            OrderPurpose::Entry => try_entry_fill(order, book, exchange_ms, params, *next_fill_id),
            OrderPurpose::Liquidation => {
                try_liquidation_fill(order, book, exchange_ms, params, *next_fill_id)
            }
        };
        if let Some(f) = fill {
            *next_fill_id += 1;
            apply_fill_to_positions(positions, order, &f);
            fills.push(f);
        }
    }
}

#[allow(clippy::ptr_arg)]
fn apply_fill_to_positions(
    positions: &mut Vec<ExecutionPosition>,
    order: &SimulatedOrder,
    fill: &SimulatedFill,
) {
    match order.purpose {
        OrderPurpose::Entry => {
            if let Some(pos) = positions
                .iter_mut()
                .find(|p| p.position_id == order.position_id)
            {
                pos.apply_entry_fill(fill);
            }
        }
        OrderPurpose::Liquidation => {
            if let Some(pos) = positions
                .iter_mut()
                .find(|p| p.position_id == order.position_id)
            {
                pos.apply_exit_fill(fill, fill.exchange_timestamp_ms);
            }
        }
    }
}

fn entry_context_for_game(
    game_id: u128,
    orders: &[SimulatedOrder],
    positions: &[ExecutionPosition],
) -> EntryContext {
    let has_working_entry = orders.iter().any(|o| {
        o.purpose == OrderPurpose::Entry && o.game_id == game_id && o.remaining_quantity > 0
    });
    let game_positions: Vec<_> = positions.iter().filter(|p| p.game_id == game_id).collect();
    let position_filled_qty: u32 = game_positions.iter().map(|p| p.filled_quantity).sum();
    let position_net_qty: u32 = game_positions.iter().map(|p| p.net_contracts()).sum();
    let remaining_entry_qty: u32 = game_positions
        .iter()
        .map(|p| p.remaining_entry_quantity)
        .sum();
    let liquidation_active = game_positions.iter().any(|p| {
        p.lifecycle == LiquidationState::LiquidationActive
            || p.lifecycle == LiquidationState::StopTriggered
    });
    let position_entry_closed = game_positions.iter().any(|p| {
        let flat_after_fill = matches!(
            p.status,
            crate::position::PositionStatus::Flat | crate::position::PositionStatus::OpenAtEnd
        ) && p.filled_quantity > 0
            && p.net_contracts() == 0;
        let budget_exhausted =
            p.filled_quantity > 0 && p.remaining_entry_quantity == 0 && p.net_contracts() > 0;
        flat_after_fill || budget_exhausted
    });
    EntryContext {
        has_working_entry,
        position_filled_qty,
        position_net_qty,
        remaining_entry_qty,
        liquidation_active,
        position_entry_closed,
    }
}

#[allow(clippy::too_many_arguments)]
fn process_strategy_quote(
    quote: StrategyQuote,
    entry: &mut EntryEngine,
    exit: &ExitEngine,
    params: &ExecutionParameters,
    run_id: &str,
    book: &MarketBookState,
    quote_observations: &mut Vec<QuoteObservation>,
    entry_opportunities: &mut Vec<EntryOpportunity>,
    entry_intents: &mut Vec<EntryIntent>,
    entry_signals: &mut Vec<momento_research_strategies::EntrySignal>,
    exit_signals: &mut Vec<ExitSignal>,
    orders: &mut Vec<SimulatedOrder>,
    positions: &mut Vec<ExecutionPosition>,
    first_entry_ms: &mut Option<i64>,
    last_entry_ms: &mut Option<i64>,
    next_order_id: &mut u64,
    next_position_id: &mut u128,
    stop_gap_count: &mut u64,
    failed_exit_attempts: &mut u64,
) {
    let ctx = entry_context_for_game(quote.game_id.raw(), orders, positions);
    let turn = entry.observe_with_context(&quote, &ctx);
    if turn.reject == Some(momento_research_strategies::QuoteReject::SequenceGap) {
        return;
    }
    if let Some(obs) = turn.quote_observation {
        quote_observations.push(obs);
    }
    if let Some(opp) = turn.new_opportunity {
        entry_opportunities.push(opp);
    }
    for intent in turn.intents {
        let _ = first_entry_ms.get_or_insert(intent.exchange_timestamp_ms);
        *last_entry_ms = Some(intent.exchange_timestamp_ms);
        entry_intents.push(intent.clone());
        let sig = momento_research_strategies::EntrySignal {
            strategy: intent.strategy.clone(),
            strategy_version: intent.strategy_version,
            market_id: intent.market_id,
            ticker: intent.ticker.clone(),
            game_id: intent.game_id,
            side: intent.side,
            exchange_timestamp_ms: intent.exchange_timestamp_ms,
            received_timestamp: intent.received_timestamp,
            signal_price_cents: intent.maker_limit_cents,
            first_threshold_cents: intent.first_threshold_cents,
            confirmation_threshold_cents: intent.confirmation_threshold_cents,
            maximum_entry_price_cents: intent.maximum_entry_price_cents,
            bid_cents: intent.bid_cents,
            ask_cents: intent.ask_cents,
            maker_eligible: true,
        };
        entry_signals.push(sig.clone());

        let qty = params.requested_quantity(sig.signal_price_cents);
        if qty == 0 {
            continue;
        }

        // Remainder intents attach to the existing game position (live: same PositionId).
        let pos_id = if intent.is_remainder {
            positions
                .iter()
                .find(|p| p.game_id == sig.game_id)
                .map(|p| p.position_id)
                .unwrap_or_else(|| {
                    let id = *next_position_id;
                    *next_position_id += 1;
                    positions.push(ExecutionPosition::new(
                        id,
                        sig.game_id,
                        sig.market_id,
                        sig.ticker.clone(),
                        sig.side,
                        qty,
                    ));
                    id
                })
        } else {
            let id = *next_position_id;
            *next_position_id += 1;
            positions.push(ExecutionPosition::new(
                id,
                sig.game_id,
                sig.market_id,
                sig.ticker.clone(),
                sig.side,
                qty,
            ));
            id
        };

        let queue = queue_ahead_at_submit(book, sig.signal_price_cents);
        let order = SimulatedOrder::new_entry(
            *next_order_id,
            run_id,
            pos_id,
            &sig,
            qty,
            params,
            book.last_quality,
            queue,
        );
        *next_order_id += 1;
        orders.push(order);
    }

    for pos in positions.iter_mut() {
        let Some(mut rp) = pos.to_research_position() else {
            continue;
        };
        let turn = exit.observe(&quote, &mut rp);
        pos.lifecycle = rp.lifecycle;
        if turn.reject == Some(momento_research_strategies::QuoteReject::SequenceGap) {
            continue;
        }
        for sig in turn.signals {
            let threshold = sig.stop_threshold_hundredths_of_cent;
            let trigger = sig.trigger_bid_cents;
            if u32::from(trigger).saturating_mul(100) < threshold {
                *stop_gap_count += 1;
            }
            exit_signals.push(sig.clone());

            let already = orders.iter().any(|o| {
                o.purpose == OrderPurpose::Liquidation
                    && o.position_id == sig.scope.position_id
                    && o.remaining_quantity > 0
                    && o.submitted_at_ms == sig.exchange_timestamp_ms
            });
            if already {
                continue;
            }

            let order = SimulatedOrder::new_liquidation(
                *next_order_id,
                run_id,
                sig.scope.position_id,
                &sig,
                params,
                book.last_quality,
            );
            *next_order_id += 1;
            orders.push(order);

            if !book.last_quality.supports_liquidation_simulation() {
                *failed_exit_attempts += 1;
            }
        }
    }
}

fn orderbook_to_quote(ob: &OrderbookEvent) -> Option<StrategyQuote> {
    let bid = ob.yes_bid_cents?;
    let ask = ob.yes_ask_cents?;
    let exchange_ms = ob
        .exchange_timestamp_ms
        .unwrap_or_else(|| ob.received_timestamp.timestamp_millis());
    Some(StrategyQuote {
        game_id: GameId::from_raw(ob.game_id),
        market_id: MarketId::from_raw(ob.market_id),
        ticker: ob.ticker.clone(),
        side: Side::Yes,
        yes_bid_cents: bid,
        yes_ask_cents: ask,
        exchange_timestamp_ms: exchange_ms,
        received_timestamp: ob.received_timestamp,
        sequence_gap: ob.sequence_gap,
    })
}

/// Convert execution positions to research positions for testing.
pub fn research_positions_from_execution(positions: &[ExecutionPosition]) -> Vec<ResearchPosition> {
    positions
        .iter()
        .filter_map(ExecutionPosition::to_research_position)
        .collect()
}
