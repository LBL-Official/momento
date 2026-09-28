//! Read-only backtest runner: FIRST01 signals + historical execution simulation.

use chrono::{DateTime, Utc};
use momento_research_data::ReplayDataset;
use momento_research_execution::{
    DataQualityMetrics, ExecutionBacktestInput, ExecutionBacktestResult, ExecutionParameters,
    run_execution_backtest,
};
use momento_research_strategies::{EntrySignal, ExitSignal};

use crate::error::BacktestError;
use crate::overrides::ResolvedExperiment;

#[derive(Clone, Debug)]
pub struct BacktestResult {
    pub signals: SignalBacktestResult,
    pub execution: ExecutionBacktestResult,
}

#[derive(Clone, Debug, Default)]
pub struct SignalBacktestResult {
    pub entry_signals: Vec<EntrySignal>,
    pub exit_signals: Vec<ExitSignal>,
    pub events_processed: u64,
    pub quotes_observed: u64,
    pub sequence_gap_rejects: u64,
    pub first_entry_exchange_ms: Option<i64>,
    pub last_entry_exchange_ms: Option<i64>,
    pub simulated_entry_fills: u64,
    pub simulated_exit_fills: u64,
}

impl From<&ExecutionBacktestResult> for SignalBacktestResult {
    fn from(exec: &ExecutionBacktestResult) -> Self {
        Self {
            entry_signals: exec.entry_signals.clone(),
            exit_signals: exec.exit_signals.clone(),
            events_processed: exec.events_processed,
            quotes_observed: exec.quotes_observed,
            sequence_gap_rejects: exec.sequence_gap_rejects,
            first_entry_exchange_ms: exec.first_entry_exchange_ms,
            last_entry_exchange_ms: exec.last_entry_exchange_ms,
            simulated_entry_fills: exec
                .fills
                .iter()
                .filter(|f| f.purpose == momento_research_execution::order::OrderPurpose::Entry)
                .count() as u64,
            simulated_exit_fills: exec
                .fills
                .iter()
                .filter(|f| {
                    f.purpose == momento_research_execution::order::OrderPurpose::Liquidation
                })
                .count() as u64,
        }
    }
}

pub fn run_backtest(
    experiment: &ResolvedExperiment,
    datasets: &[ReplayDataset],
    data_quality: DataQualityMetrics,
) -> Result<BacktestResult, BacktestError> {
    let input = ExecutionBacktestInput {
        run_id: &experiment.run_id,
        entry_params: experiment.effective_parameters.entry,
        exit_params: experiment.effective_parameters.exit,
        execution_params: ExecutionParameters::default(),
        datasets,
        data_quality,
    };
    let execution = run_execution_backtest(&input);
    let signals = SignalBacktestResult::from(&execution);
    Ok(BacktestResult { signals, execution })
}

/// Legacy signal-only entry point (delegates to full execution runner).
pub fn run_signal_backtest(
    experiment: &ResolvedExperiment,
    datasets: &[ReplayDataset],
) -> Result<SignalBacktestResult, BacktestError> {
    Ok(run_backtest(experiment, datasets, DataQualityMetrics::default())?.signals)
}

pub fn ms_to_rfc3339(ms: i64) -> String {
    DateTime::from_timestamp_millis(ms)
        .map(|d: DateTime<Utc>| d.to_rfc3339())
        .unwrap_or_default()
}

/// Test helper: run engines over an explicit quote stream (signal-only, no book).
pub fn run_on_quotes(
    experiment: &ResolvedExperiment,
    quotes: &[momento_research_strategies::StrategyQuote],
) -> SignalBacktestResult {
    use momento_research_strategies::EntryEngine;

    let mut entry = EntryEngine::new(experiment.effective_parameters.entry);
    let mut result = SignalBacktestResult::default();
    let mut last_ms = i64::MIN;
    for quote in quotes {
        assert!(
            quote.exchange_timestamp_ms >= last_ms,
            "no-lookahead chronological order"
        );
        last_ms = quote.exchange_timestamp_ms;
        result.quotes_observed += 1;
        result.events_processed += 1;
        let turn = entry.observe(quote);
        if turn.reject == Some(momento_research_strategies::QuoteReject::SequenceGap) {
            result.sequence_gap_rejects += 1;
        }
        for sig in turn
            .intents
            .iter()
            .map(|i| momento_research_strategies::EntrySignal {
                strategy: i.strategy.clone(),
                strategy_version: i.strategy_version,
                market_id: i.market_id,
                ticker: i.ticker.clone(),
                game_id: i.game_id,
                side: i.side,
                exchange_timestamp_ms: i.exchange_timestamp_ms,
                received_timestamp: i.received_timestamp,
                signal_price_cents: i.maker_limit_cents,
                first_threshold_cents: i.first_threshold_cents,
                confirmation_threshold_cents: i.confirmation_threshold_cents,
                maximum_entry_price_cents: i.maximum_entry_price_cents,
                bid_cents: i.bid_cents,
                ask_cents: i.ask_cents,
                maker_eligible: true,
            })
        {
            if result.first_entry_exchange_ms.is_none() {
                result.first_entry_exchange_ms = Some(sig.exchange_timestamp_ms);
            }
            result.last_entry_exchange_ms = Some(sig.exchange_timestamp_ms);
            result.entry_signals.push(sig);
        }
    }
    result
}
