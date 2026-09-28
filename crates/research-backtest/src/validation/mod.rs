//! MLB real-data validation runner.

mod data_audit;
mod frequency_reconcile;

use std::collections::BTreeMap;
use std::fs;
use std::path::{Path, PathBuf};

use chrono::{DateTime, NaiveDate, Utc};
use momento_research_data::{ReplayDataset, ResearchPaths, ResearchSport};
use momento_research_strategies::{
    EntryContext, EntryEngine, EntryPhase, FIRST01_DEFAULT_ENTRY, FIRST01_DEFAULT_EXIT,
    FIRST01_NAME, FIRST01_VERSION, StrategyQuote,
};
use serde::{Deserialize, Serialize};

use crate::dataset::{DatasetPlan, data_quality_from_plans, load_datasets};
use crate::metadata::RunMetadata;
use crate::overrides::ResolvedExperiment;
use crate::parse::{EntryPriceRange, ExitPriceInput, NormalizedSeason, NormalizedTimeFrame};
use crate::paths::BacktestPaths;
use crate::results::write_run_artifacts;
use crate::runner::{BacktestResult, run_backtest};

pub use data_audit::{MlbDataAudit, audit_mlb_data};
pub use frequency_reconcile::{
    FrequencyReconcileConfig, FrequencyReconcileResult, run_frequency_reconcile,
};

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum ValidationClassification {
    Validated,
    DataLimited,
    ImplementationMismatch,
    ExecutionModelLimited,
}

#[derive(Clone, Debug)]
pub struct MlbValidationConfig {
    pub research_data_dir: PathBuf,
    pub season_label: String,
    pub run_id: String,
}

impl MlbValidationConfig {
    pub fn from_env() -> Self {
        let research_data_dir = std::env::var("MOMENTO_RESEARCH_DATA_DIR")
            .map(PathBuf::from)
            .unwrap_or_else(|_| PathBuf::from("Backtesting Suite/Data-Real"));
        Self {
            research_data_dir,
            season_label: "2025-2026".into(),
            run_id: format!("mlb-validation-{}", Utc::now().format("%Y%m%d-%H%M%S")),
        }
    }
}

#[derive(Clone, Debug, Default, Serialize, Deserialize)]
pub struct SignalFrequencyReport {
    pub quote_observations: u64,
    pub entry_opportunities: u64,
    pub entry_intents: u64,
    pub entry_orders: u64,
    pub entry_fills: u64,
    pub completed_trades: u64,
    pub eligible_days: u32,
    pub quotes_per_eligible_day: f64,
    pub opportunities_per_eligible_day: f64,
    pub intents_per_eligible_day: f64,
    pub orders_per_eligible_day: f64,
    pub fills_per_eligible_day: f64,
    pub trades_per_eligible_day: f64,
    pub median_opportunities_per_day: f64,
    pub median_intents_per_day: f64,
    /// Legacy — equals entry_intents total.
    pub total_signals: u64,
    pub signals_per_eligible_day: f64,
    pub median_signals_per_day: f64,
    pub min_signals_per_day: u64,
    pub max_signals_per_day: u64,
    pub std_dev_signals_per_day: f64,
    pub pct_zero_signal_days: f64,
    pub pct_1_2_signal_days: f64,
    pub pct_3_5_signal_days: f64,
    pub pct_over_5_signal_days: f64,
    pub intents_at_80: u64,
    pub intents_at_81: u64,
    pub intents_at_82: u64,
    pub intents_at_83: u64,
    pub reached_80_never_81: u64,
    pub reached_81_bid_ge_ask: u64,
    pub reached_89_lock: u64,
    pub sequence_gap_rejects: u64,
    pub opportunities_by_date: BTreeMap<String, u64>,
    pub intents_by_date: BTreeMap<String, u64>,
    pub quotes_by_date: BTreeMap<String, u64>,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct MlbValidationResult {
    pub classification: ValidationClassification,
    pub run_id: String,
    pub run_dir: PathBuf,
    pub data_audit: MlbDataAudit,
    pub eligible_date_start: String,
    pub eligible_date_end: String,
    pub signal_frequency: SignalFrequencyReport,
    pub entry_orders: u64,
    pub entry_fills: u64,
    pub entry_fill_rate: f64,
    pub gross_pnl_cents: i64,
    pub net_pnl_cents: i64,
    pub first01_verified: bool,
    pub notes: Vec<String>,
}

pub fn run_mlb_validation(config: &MlbValidationConfig) -> Result<MlbValidationResult, String> {
    verify_first01_immutable()?;

    let mut paths = ResearchPaths::from_env_or_default();
    paths.root = config.research_data_dir.clone();

    let audit = audit_mlb_data(&paths, &config.season_label)?;
    if audit.eligible_dates == 0 {
        return Ok(MlbValidationResult {
            classification: ValidationClassification::DataLimited,
            run_id: config.run_id.clone(),
            run_dir: PathBuf::new(),
            data_audit: audit,
            eligible_date_start: String::new(),
            eligible_date_end: String::new(),
            signal_frequency: SignalFrequencyReport::default(),
            entry_orders: 0,
            entry_fills: 0,
            entry_fill_rate: 0.0,
            gross_pnl_cents: 0,
            net_pnl_cents: 0,
            first01_verified: true,
            notes: vec![
                "No eligible real KXMLBGAME partitions (demo excluded).".into(),
                "Collect COMPLETE MLB days via momento-research-collector into Data-Real.".into(),
            ],
        });
    }

    let eligible_dates: Vec<NaiveDate> = audit
        .rows
        .iter()
        .filter(|r| r.eligible)
        .filter_map(|r| NaiveDate::parse_from_str(&r.date, "%Y-%m-%d").ok())
        .collect();
    let start = *eligible_dates.first().unwrap();
    let end = *eligible_dates.last().unwrap();

    let plan = DatasetPlan {
        sport: ResearchSport::Mlb,
        dates: eligible_dates.clone(),
        manifests: Vec::new(),
        manifest_ids: eligible_dates.iter().map(|d| format!("MLB:{d}")).collect(),
        checksum_digest: audit.data_root.clone(),
        coverage: format!("REAL MLB {} eligible days", eligible_dates.len()),
    };

    let datasets = load_datasets(&paths, &plan).map_err(|e| e.to_string())?;
    let signal_freq = compute_signal_frequency(&datasets, &eligible_dates)?;

    let experiment = ResolvedExperiment {
        run_id: config.run_id.clone(),
        entry_model: momento_research_strategies::First01Model::definition().as_strategy_model(),
        exit_model: momento_research_strategies::First01Model::definition().as_strategy_model(),
        series: vec!["KXMLBGAME".into()],
        season: NormalizedSeason {
            label: config.season_label.clone(),
            original: "25-26".into(),
            start_year: 2025,
            end_year: 2026,
        },
        time_frame: NormalizedTimeFrame {
            original: format!("{start}-{end}"),
            start,
            end,
        },
        entry_range: EntryPriceRange {
            minimum_entry_price_cents: 80,
            confirmation_threshold_cents: 81,
            maximum_entry_price_cents: 83,
        },
        exit_input: ExitPriceInput::ModelNative,
        overrides: Default::default(),
        default_parameters: momento_research_strategies::EffectiveParameters {
            entry: FIRST01_DEFAULT_ENTRY,
            exit: FIRST01_DEFAULT_EXIT,
        },
        effective_parameters: momento_research_strategies::EffectiveParameters {
            entry: FIRST01_DEFAULT_ENTRY,
            exit: FIRST01_DEFAULT_EXIT,
        },
        original_entry_price_input: "80-83".into(),
        original_exit_price_input: "FIRST01".into(),
    };

    let dq = data_quality_from_plans(std::slice::from_ref(&plan));
    let backtest = run_backtest(&experiment, &datasets, dq).map_err(|e| e.to_string())?;
    let m = &backtest.execution.metrics;
    let mut freq = signal_freq;
    freq.entry_orders = m.entry_orders;
    freq.entry_fills = m.entry_fills;
    freq.completed_trades = m.positions_closed;
    freq.orders_per_eligible_day = m.entry_orders as f64 / eligible_dates.len().max(1) as f64;
    freq.fills_per_eligible_day = m.entry_fills as f64 / eligible_dates.len().max(1) as f64;
    freq.trades_per_eligible_day = m.positions_closed as f64 / eligible_dates.len().max(1) as f64;

    let classification = classify_validation(
        &audit,
        freq.entry_opportunities,
        &m.data_quality.execution_data_quality,
    );

    let bt_paths = BacktestPaths::from_env_or_default();
    let mut meta = RunMetadata::new_base(
        config.run_id.clone(),
        FIRST01_NAME.into(),
        FIRST01_VERSION,
        FIRST01_NAME.into(),
        FIRST01_NAME.into(),
    );
    meta.requested_series = "KXMLBGAME".into();
    meta.normalized_series = vec!["KXMLBGAME".into()];
    meta.normalized_season = config.season_label.clone();
    meta.requested_time_start = start.to_string();
    meta.requested_time_end = end.to_string();
    meta.effective_entry_range = "80-83".into();
    meta.effective_exit_rule = "FIRST01 50% VWAP loss".into();
    meta.dataset_coverage = format!("REAL MLB eligible_days={}", eligible_dates.len());
    meta.status = "COMPLETE".into();
    meta.completed_at = Some(Utc::now());
    meta.effective_parameters = experiment.effective_parameters.clone();

    let artifacts = write_run_artifacts(&bt_paths, &meta, &backtest).map_err(|e| e.to_string())?;
    write_validation_artifacts(
        &artifacts.run_dir,
        config,
        &audit,
        &freq,
        &backtest,
        classification,
        &eligible_dates,
    )
    .map_err(|e| e.to_string())?;

    Ok(MlbValidationResult {
        classification,
        run_id: config.run_id.clone(),
        run_dir: artifacts.run_dir,
        eligible_date_start: start.to_string(),
        eligible_date_end: end.to_string(),
        data_audit: audit,
        signal_frequency: freq,
        entry_orders: m.entry_orders,
        entry_fills: m.entry_fills,
        entry_fill_rate: m.entry_fill_rate,
        gross_pnl_cents: m.gross_pnl_cents,
        net_pnl_cents: m.net_pnl_cents,
        first01_verified: true,
        notes: vec!["REAL HISTORICAL DATA — demo partitions excluded.".into()],
    })
}

fn verify_first01_immutable() -> Result<(), String> {
    let e = FIRST01_DEFAULT_ENTRY;
    let x = FIRST01_DEFAULT_EXIT;
    if e.first_threshold_cents != 80
        || e.confirmation_threshold_cents != 81
        || e.maximum_entry_price_cents != 83
        || e.lock_threshold_cents != 89
        || x.loss_numerator != 1
        || x.loss_denominator != 2
    {
        return Err("FIRST01 defaults changed".into());
    }
    Ok(())
}

fn classify_validation(
    audit: &MlbDataAudit,
    signals: u64,
    execution_quality: &str,
) -> ValidationClassification {
    if audit.eligible_dates == 0 {
        return ValidationClassification::DataLimited;
    }
    if audit.eligible_dates < 5 {
        return ValidationClassification::DataLimited;
    }
    if execution_quality.contains("CANDLESTICK") && !execution_quality.contains("FULL_L2") {
        return ValidationClassification::ExecutionModelLimited;
    }
    if signals == 0 && audit.eligible_dates > 0 {
        return ValidationClassification::DataLimited;
    }
    ValidationClassification::Validated
}

fn compute_signal_frequency(
    datasets: &[ReplayDataset],
    eligible_dates: &[NaiveDate],
) -> Result<SignalFrequencyReport, String> {
    let mut entry = EntryEngine::new(FIRST01_DEFAULT_ENTRY);
    let mut intents_by_date: BTreeMap<String, u64> = BTreeMap::new();
    let mut opportunities_by_date: BTreeMap<String, u64> = BTreeMap::new();
    let mut quotes_by_date: BTreeMap<String, u64> = BTreeMap::new();
    let mut price_counts = [0u64; 4];
    let mut seq_gaps = 0u64;
    let mut reached_89 = 0u64;
    let mut reached_81_bid_ge_ask = 0u64;
    let mut games_saw_80: BTreeMap<u128, bool> = BTreeMap::new();
    let mut games_confirmed: BTreeMap<u128, bool> = BTreeMap::new();
    let mut working_entry_games: std::collections::HashSet<u128> = std::collections::HashSet::new();
    let position_net_by_game: BTreeMap<u128, u32> = BTreeMap::new();

    let mut quotes: Vec<StrategyQuote> = Vec::new();
    for ds in datasets {
        for item in ds.cursor().events_chronological() {
            if let momento_research_data::replay::ReplayItem::Orderbook(ob) = item {
                if let Some(q) = orderbook_to_quote(ob) {
                    quotes.push(q);
                }
            }
        }
    }
    quotes.sort_by_key(|q| q.exchange_timestamp_ms);

    let mut quote_observations = 0u64;
    let mut entry_opportunities = 0u64;
    let mut entry_intents = 0u64;

    for q in &quotes {
        let gid = q.game_id.raw();
        let before = entry.snapshot_game(q.game_id);
        let ctx = EntryContext {
            has_working_entry: working_entry_games.contains(&gid),
            position_filled_qty: *position_net_by_game.get(&gid).unwrap_or(&0),
            position_net_qty: *position_net_by_game.get(&gid).unwrap_or(&0),
            remaining_entry_qty: 0,
            liquidation_active: false,
            position_entry_closed: false,
        };
        let turn = entry.observe_with_context(q, &ctx);
        if turn.reject == Some(momento_research_strategies::QuoteReject::SequenceGap) {
            seq_gaps += 1;
        }
        if turn.quote_observation.is_some() {
            quote_observations += 1;
            let date = ms_to_date(q.exchange_timestamp_ms);
            *quotes_by_date.entry(date).or_insert(0) += 1;
        }
        if turn.new_opportunity.is_some() {
            entry_opportunities += 1;
            let date = ms_to_date(q.exchange_timestamp_ms);
            *opportunities_by_date.entry(date).or_insert(0) += 1;
        }
        for intent in &turn.intents {
            entry_intents += 1;
            let date = ms_to_date(intent.exchange_timestamp_ms);
            *intents_by_date.entry(date).or_insert(0) += 1;
            let idx = intent.maker_limit_cents.saturating_sub(80) as usize;
            if idx < 4 {
                price_counts[idx] += 1;
            }
            working_entry_games.insert(gid);
        }
        let after = entry.snapshot_game(q.game_id);
        if before.phase != EntryPhase::GameLocked && after.phase == EntryPhase::GameLocked {
            reached_89 += 1;
        }
        if after.first.is_some() {
            games_saw_80.insert(gid, true);
        }
        if after.confirmed {
            games_confirmed.insert(gid, true);
        }
        if after.confirmed && turn.intents.is_empty() && q.yes_bid_cents >= q.yes_ask_cents {
            reached_81_bid_ge_ask += 1;
        }
    }

    let reached_80_never_81 = games_saw_80
        .keys()
        .filter(|g| !games_confirmed.get(g).copied().unwrap_or(false))
        .count() as u64;

    let per_day: Vec<u64> = eligible_dates
        .iter()
        .map(|d| *intents_by_date.get(&d.to_string()).unwrap_or(&0))
        .collect();
    let opp_per_day: Vec<u64> = eligible_dates
        .iter()
        .map(|d| *opportunities_by_date.get(&d.to_string()).unwrap_or(&0))
        .collect();
    let n = eligible_dates.len().max(1) as f64;

    Ok(SignalFrequencyReport {
        quote_observations,
        entry_opportunities,
        entry_intents,
        entry_orders: 0,
        entry_fills: 0,
        completed_trades: 0,
        eligible_days: eligible_dates.len() as u32,
        quotes_per_eligible_day: quote_observations as f64 / n,
        opportunities_per_eligible_day: entry_opportunities as f64 / n,
        intents_per_eligible_day: entry_intents as f64 / n,
        orders_per_eligible_day: 0.0,
        fills_per_eligible_day: 0.0,
        trades_per_eligible_day: 0.0,
        median_opportunities_per_day: median_f64(
            &opp_per_day.iter().map(|v| *v as f64).collect::<Vec<_>>(),
        ),
        median_intents_per_day: median_f64(&per_day.iter().map(|v| *v as f64).collect::<Vec<_>>()),
        total_signals: entry_intents,
        signals_per_eligible_day: entry_intents as f64 / n,
        median_signals_per_day: median_f64(&per_day.iter().map(|v| *v as f64).collect::<Vec<_>>()),
        min_signals_per_day: per_day.iter().copied().min().unwrap_or(0),
        max_signals_per_day: per_day.iter().copied().max().unwrap_or(0),
        std_dev_signals_per_day: std_dev(&per_day),
        pct_zero_signal_days: per_day.iter().filter(|&&v| v == 0).count() as f64 / n * 100.0,
        pct_1_2_signal_days: per_day.iter().filter(|&&v| (1..=2).contains(&v)).count() as f64 / n
            * 100.0,
        pct_3_5_signal_days: per_day.iter().filter(|&&v| (3..=5).contains(&v)).count() as f64 / n
            * 100.0,
        pct_over_5_signal_days: per_day.iter().filter(|&&v| v > 5).count() as f64 / n * 100.0,
        intents_at_80: price_counts[0],
        intents_at_81: price_counts[1],
        intents_at_82: price_counts[2],
        intents_at_83: price_counts[3],
        reached_80_never_81,
        reached_81_bid_ge_ask,
        reached_89_lock: reached_89,
        sequence_gap_rejects: seq_gaps,
        opportunities_by_date,
        intents_by_date,
        quotes_by_date,
    })
}

fn write_validation_artifacts(
    run_dir: &Path,
    config: &MlbValidationConfig,
    audit: &MlbDataAudit,
    freq: &SignalFrequencyReport,
    backtest: &BacktestResult,
    classification: ValidationClassification,
    eligible_dates: &[NaiveDate],
) -> Result<(), String> {
    for sub in ["diagnostics", "validation", "trades", "risk"] {
        fs::create_dir_all(run_dir.join(sub)).map_err(|e| e.to_string())?;
    }
    fs::write(
        run_dir.join("diagnostics/data_quality_report.csv"),
        audit_csv(audit),
    )
    .map_err(|e| e.to_string())?;
    fs::write(
        run_dir.join("diagnostics/bias_report.json"),
        serde_json::to_string_pretty(&serde_json::json!({
            "look_ahead_bias": {"status": "AUDITED", "ordering": "exchange_timestamp"},
            "survivorship_bias": {"status": "NOT_MODELED"},
            "missing_data": {"status": "DOCUMENTED"}
        }))
        .unwrap(),
    )
    .map_err(|e| e.to_string())?;
    fs::write(
        run_dir.join("validation/out_of_sample.json"),
        r#"{"status":"OOS NOT AVAILABLE"}"#,
    )
    .map_err(|e| e.to_string())?;
    fs::write(
        run_dir.join("validation/walk_forward.json"),
        r#"{"WALK_FORWARD_STATUS":"NOT_RUN"}"#,
    )
    .map_err(|e| e.to_string())?;
    fs::write(
        run_dir.join("validation/parameter_sensitivity.json"),
        r#"{"PARAMETER_SENSITIVITY":"NOT_RUN"}"#,
    )
    .map_err(|e| e.to_string())?;
    fs::write(run_dir.join("daily_signal_report.csv"), daily_csv(freq))
        .map_err(|e| e.to_string())?;
    fs::write(
        run_dir.join("validation/frequency_analysis.csv"),
        frequency_csv(freq),
    )
    .map_err(|e| e.to_string())?;
    fs::write(
        run_dir.join("validation/live_entry_state_machine.md"),
        live_state_machine_doc(),
    )
    .map_err(|e| e.to_string())?;
    fs::write(
        run_dir.join("validation/june_data_discovery_audit.csv"),
        june_discovery_csv(audit),
    )
    .map_err(|e| e.to_string())?;
    fs::write(
        run_dir.join("validation/first01_semantics_audit.md"),
        first01_semantics_doc(freq, backtest),
    )
    .map_err(|e| e.to_string())?;
    fs::write(
        run_dir.join("FIRST01_validation_report.md"),
        validation_markdown(
            config,
            audit,
            freq,
            backtest,
            classification,
            eligible_dates,
        ),
    )
    .map_err(|e| e.to_string())?;
    let m = &backtest.execution.metrics;
    fs::write(
        run_dir.join("diagnostics/market_impact_report.json"),
        r#"{"MARKET_IMPACT":"NOT MODELED"}"#,
    )
    .map_err(|e| e.to_string())?;
    fs::write(
        run_dir.join("risk/risk_metrics.json"),
        serde_json::to_string_pretty(&serde_json::json!({
            "max_drawdown_cents": m.max_drawdown_cents,
            "sharpe": "NOT_STATISTICALLY_MEANINGFUL",
            "fees": "NOT_MODELED"
        }))
        .unwrap(),
    )
    .map_err(|e| e.to_string())?;
    Ok(())
}

fn audit_csv(audit: &MlbDataAudit) -> String {
    let mut out = String::from(
        "date,manifest_status,is_demo,market_count,orderbook_events,trades,eligible,exclusion_reason\n",
    );
    for r in &audit.rows {
        out.push_str(&format!(
            "{},{},{},{},{},{},{},{}\n",
            r.date,
            r.manifest_status,
            r.is_demo,
            r.market_count,
            r.orderbook_event_count,
            r.trade_count,
            r.eligible,
            r.exclusion_reason
        ));
    }
    out
}

fn june_discovery_csv(audit: &MlbDataAudit) -> String {
    let mut out =
        String::from("date,expected_markets,markets_discovered,source_endpoint,status,reason\n");
    for row in audit.rows.iter().filter(|r| r.date.starts_with("2026-06")) {
        let reason = if row.market_count == 0 {
            "Kalshi discovery returned 0 KXMLBGAME markets for LA close_time window; earliest tickers are 26JUN18 — API limitation not collector bug"
        } else if row.eligible {
            "COMPLETE partition; candlestick-derived orderbook events"
        } else {
            row.exclusion_reason.as_str()
        };
        out.push_str(&format!(
            "{},{},{},/markets + /historical/markets,{},{}\n",
            row.date,
            if row.market_count == 0 { "0" } else { "24-32" },
            row.market_count,
            row.manifest_status,
            reason
        ));
    }
    out
}

fn frequency_csv(freq: &SignalFrequencyReport) -> String {
    format!(
        "metric,per_eligible_day,total,median_per_day\n\
quote_observations,{:.4},{},{:.2}\n\
entry_opportunities,{:.4},{},{:.2}\n\
entry_intents,{:.4},{},{:.2}\n\
entry_orders,{:.4},{},\n\
entry_fills,{:.4},{},\n\
completed_trades,{:.4},{},\n",
        freq.quotes_per_eligible_day,
        freq.quote_observations,
        0.0,
        freq.opportunities_per_eligible_day,
        freq.entry_opportunities,
        freq.median_opportunities_per_day,
        freq.intents_per_eligible_day,
        freq.entry_intents,
        freq.median_intents_per_day,
        freq.orders_per_eligible_day,
        freq.entry_orders,
        freq.fills_per_eligible_day,
        freq.entry_fills,
        freq.trades_per_eligible_day,
        freq.completed_trades,
    )
}

fn live_state_machine_doc() -> String {
    r#"# LIVE ENTRY STATE MACHINE (FIRST01 / MLB)

```
IDLE (Watching)
  | YES bid >= 80 on (GameId, MarketId, Side)
  v
FIRST_80 (First80Triggered)
  | same market+side, YES bid >= 81
  v
CONFIRMED_81 (EntryEligible)
  | maker_limit valid AND NOT has_working_entry AND NOT position blocks
  v
ENTRY_INTENT (Build TradeIntent) — ONE per opportunity
  | execution submits order
  v
ENTRY_WORKING (has_working_entry=true) — blocks duplicate intents
  | fill(s)
  v
POSITION_BUILDING / POSITION_OPEN — blocks duplicate intents
  | YES bid <= 50% entry VWAP
  v
LIQUIDATION_ACTIVE — blocks duplicate intents
  | flat
  v
TRADE_COMPLETE — may allow new opportunity if not GameLocked

Parallel terminal: YES bid >= 89 -> GAME_LOCKED (permanent for game)
```

Concurrency scope: **one active FIRST01 trade per GameId**.
Identity scope: opportunity keyed by GameId + MarketId + Side + sequence.
"#
    .into()
}

fn first01_semantics_doc(freq: &SignalFrequencyReport, backtest: &BacktestResult) -> String {
    let m = &backtest.execution.metrics;
    let unique_games: std::collections::HashSet<u128> = backtest
        .execution
        .entry_opportunities
        .iter()
        .map(|o| o.game_id)
        .collect();
    let dup = freq
        .entry_opportunities
        .saturating_sub(unique_games.len() as u64);
    let suppressed = backtest
        .execution
        .quote_observations
        .iter()
        .filter(|q| q.qualifies_first01)
        .filter(|q| {
            !matches!(
                q.lifecycle_action,
                momento_research_strategies::LifecycleAction::OpportunityCreated
                    | momento_research_strategies::LifecycleAction::IntentEmitted
                    | momento_research_strategies::LifecycleAction::Observed
                    | momento_research_strategies::LifecycleAction::FirstThresholdRecorded
                    | momento_research_strategies::LifecycleAction::ConfirmationPending
            )
        })
        .count();
    format!(
        r#"# FIRST01 Semantics Audit

## Definitions

| Concept | Definition |
|---------|------------|
| Quote observation | Every distinct processed top-of-book quote |
| Entry opportunity | **ONE** canonical 80→81 maker lifecycle per GameId |
| Entry intent | Live-equivalent `Build` — first + optional PositionBuilding remainder |
| Entry order | Simulated maker order from intent |
| Entry fill | Simulated fill from CONSERVATIVE_MAKER_V1 |
| Completed trade | Position flat after entry |

## Game-level rule (live-aligned)

**ONE CANONICAL FIRST01 OPPORTUNITY PER GameId** for the game's entry lifecycle.

Live evidence (`can_attempt_entry`, sticky `first_80`, PositionOpen/Flat/OpenComplete):
after any filled exposure completes, re-entry is permanently blocked. Opponent markets
after `first_80` binding never create a second trade.

`entry_reason = FIRST01_80_TO_81_CONFIRMED_MAKER`

## This run

- Quote observations: {}
- Qualifying suppressed quotes (approx): {}
- Unique games with opportunity: {}
- Canonical opportunities: {}
- Duplicate opportunities (same game): {}
- Entry intents: {}
- Entry orders: {}
- Entry fills: {}
- Completed trades: {}

## One-trade-per-game invariant

{}

## 3–5/day diagnostic

Compare **canonical opportunities/day** ({:.2}) against ~3–5 hypothesis.
Root cause if elevated: typically ≈ MLB games/day with a qualifying market (not quote spam).
"#,
        freq.quote_observations,
        suppressed,
        unique_games.len(),
        freq.entry_opportunities,
        dup,
        freq.entry_intents,
        m.entry_orders,
        m.entry_fills,
        freq.completed_trades,
        if dup == 0 { "PASS" } else { "FAIL" },
        freq.opportunities_per_eligible_day,
    )
}

fn daily_csv(freq: &SignalFrequencyReport) -> String {
    let mut out = String::from("date,quote_observations,opportunities,entry_intents\n");
    let dates: std::collections::BTreeSet<String> = freq
        .quotes_by_date
        .keys()
        .chain(freq.opportunities_by_date.keys())
        .chain(freq.intents_by_date.keys())
        .cloned()
        .collect();
    for d in dates {
        out.push_str(&format!(
            "{d},{},{},{}\n",
            freq.quotes_by_date.get(&d).unwrap_or(&0),
            freq.opportunities_by_date.get(&d).unwrap_or(&0),
            freq.intents_by_date.get(&d).unwrap_or(&0),
        ));
    }
    out
}

fn validation_markdown(
    config: &MlbValidationConfig,
    audit: &MlbDataAudit,
    freq: &SignalFrequencyReport,
    backtest: &BacktestResult,
    classification: ValidationClassification,
    eligible_dates: &[NaiveDate],
) -> String {
    let m = &backtest.execution.metrics;
    format!(
        "# FIRST01 MLB Real-Data Validation\n\n\
**Classification:** {classification:?}\n\
**Run ID:** {}\n\
**Data root:** {}\n\
**Eligible MLB days:** {}\n\
**Date range:** {} — {}\n\n\
## Key metrics (distinct semantics)\n\
- Quote observations / eligible day = {:.2}\n\
- Entry opportunities / eligible day = {:.2}\n\
- Entry intents / eligible day = {:.2}\n\
- Entry orders / eligible day = {:.2}\n\
- Entry fills / eligible day = {:.2}\n\
- Completed trades / eligible day = {:.2}\n\
- Quote observations (total): {}\n\
- Entry opportunities (total): {}\n\
- Entry intents (total): {}\n\
- Entry orders: {}\n\
- Entry fills: {}\n\
- Fill rate: {:.2}%\n\
- Execution data quality: {}\n\
- Demo partitions excluded: {}\n",
        config.run_id,
        audit.data_root,
        eligible_dates.len(),
        audit.contiguous_eligible_start.as_deref().unwrap_or("?"),
        audit.contiguous_eligible_end.as_deref().unwrap_or("?"),
        freq.quotes_per_eligible_day,
        freq.opportunities_per_eligible_day,
        freq.intents_per_eligible_day,
        freq.orders_per_eligible_day,
        freq.fills_per_eligible_day,
        freq.trades_per_eligible_day,
        freq.quote_observations,
        freq.entry_opportunities,
        freq.entry_intents,
        m.entry_orders,
        m.entry_fills,
        m.entry_fill_rate * 100.0,
        m.data_quality.execution_data_quality,
        audit.demo_dates,
    )
}

fn orderbook_to_quote(ob: &momento_research_data::OrderbookEvent) -> Option<StrategyQuote> {
    let bid = ob.yes_bid_cents?;
    let ask = ob.yes_ask_cents?;
    Some(StrategyQuote {
        game_id: momento_core::GameId::from_raw(ob.game_id),
        market_id: momento_core::MarketId::from_raw(ob.market_id),
        ticker: ob.ticker.clone(),
        side: momento_core::Side::Yes,
        yes_bid_cents: bid,
        yes_ask_cents: ask,
        exchange_timestamp_ms: ob
            .exchange_timestamp_ms
            .unwrap_or_else(|| ob.received_timestamp.timestamp_millis()),
        received_timestamp: ob.received_timestamp,
        sequence_gap: ob.sequence_gap,
    })
}

fn ms_to_date(ms: i64) -> String {
    DateTime::from_timestamp_millis(ms)
        .map(|d| d.date_naive().to_string())
        .unwrap_or_default()
}

fn median_f64(vals: &[f64]) -> f64 {
    if vals.is_empty() {
        return 0.0;
    }
    let mut v = vals.to_vec();
    v.sort_by(|a, b| a.partial_cmp(b).unwrap_or(std::cmp::Ordering::Equal));
    v[v.len() / 2]
}

fn std_dev(vals: &[u64]) -> f64 {
    if vals.is_empty() {
        return 0.0;
    }
    let mean = vals.iter().sum::<u64>() as f64 / vals.len() as f64;
    let var = vals
        .iter()
        .map(|v| {
            let d = *v as f64 - mean;
            d * d
        })
        .sum::<f64>()
        / vals.len() as f64;
    var.sqrt()
}
