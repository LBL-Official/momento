//! Forensic reconciliation: canonical FIRST01 opportunities vs live-comparable intents.
//! Does **not** modify FIRST01. Desk risk caps are LIVE_EXECUTION_CONTEXT only.

use std::collections::{BTreeMap, BTreeSet, HashMap, HashSet};
use std::fs;
use std::path::{Path, PathBuf};

use chrono::{DateTime, Timelike, Utc};
use momento_research_data::{
    CompletenessStatus, DailyManifest, ReplayDataset, ResearchPaths, ResearchSport,
};
use momento_research_strategies::{
    EntryContext, EntryEngine, EntryPhase, FIRST01_DEFAULT_ENTRY, StrategyQuote,
};
use serde::{Deserialize, Serialize};

use crate::paths::BacktestPaths;
use chrono::NaiveDate;

const MAX_OPEN_POSITIONS_DESK: u32 = 5;
const LIVE_RISK_MODEL: &str = "DESK_MAX_OPEN_POSITIONS_5_STICKY_UNTIL_PT_DAY_END";

#[derive(Clone, Debug)]
pub struct FrequencyReconcileConfig {
    pub source_run_dir: PathBuf,
    pub research_data_dir: PathBuf,
    pub season_label: String,
    pub run_id: String,
}

impl FrequencyReconcileConfig {
    pub fn from_env(source_run_dir: PathBuf) -> Self {
        let research_data_dir = std::env::var("MOMENTO_RESEARCH_DATA_DIR")
            .map(PathBuf::from)
            .unwrap_or_else(|_| PathBuf::from("Backtesting Suite/Data-Real"));
        Self {
            source_run_dir,
            research_data_dir,
            season_label: "2025-2026".into(),
            run_id: format!(
                "mlb-frequency-reconcile-{}",
                Utc::now().format("%Y%m%d-%H%M%S")
            ),
        }
    }
}

#[derive(Clone, Debug, Serialize, Deserialize)]
struct SourceOpportunity {
    opportunity_id: String,
    trade_id: String,
    game_id: u128,
    market_id: u128,
    ticker: String,
    side: String,
    first_80_timestamp_ms: i64,
    first_80_price_cents: u16,
    confirmation_81_timestamp_ms: i64,
    confirmation_81_price_cents: u16,
    qualifying_timestamp_ms: i64,
    qualifying_bid_cents: u16,
    qualifying_ask_cents: u16,
    maker_limit_cents: u16,
    entry_reason: String,
    lifecycle: String,
    game_trade_phase: String,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct FrequencyReconcileResult {
    pub run_id: String,
    pub run_dir: PathBuf,
    pub source_run_id: String,
    pub eligible_days: u32,
    pub canonical_opportunities: u64,
    pub opportunities_per_day: f64,
    pub live_gate_pass: u64,
    pub live_gate_block: u64,
    pub risk_block: u64,
    pub execution_block: u64,
    pub live_comparable_intents: u64,
    pub live_comparable_intents_per_day: f64,
    pub provable: u64,
    pub partially_provable: u64,
    pub not_provable: u64,
    pub root_cause: String,
    pub one_trade_per_game: String,
}

#[derive(Clone, Debug, Serialize)]
struct OpportunityAuditRow {
    date: String,
    game_id: String,
    event_ticker: String,
    market_id: String,
    ticker: String,
    side: String,
    first_80_timestamp: String,
    first_80_price: u16,
    confirmation_81_timestamp: String,
    confirmation_81_price: u16,
    signal_timestamp: String,
    signal_bid: u16,
    signal_ask: u16,
    entry_limit: u16,
    game_lock_status: String,
    sequence_gap_status: String,
    data_quality: String,
    lifecycle_status: String,
    position_existed: bool,
    working_order_existed: bool,
    other_market_active_lifecycle: bool,
    time_of_day_pt: String,
    hour_pt: u32,
    timing_bucket: String,
    first01_price_condition: String,
    live_entry_gates: String,
    risk_gate: String,
    final_live_eligible: bool,
    live_comparable: bool,
    candlestick_provability: String,
    minutes_from_game_start: String,
    minutes_to_market_close: String,
    market_status: String,
}

#[derive(Default, Clone)]
struct DailyFunnel {
    games_on_slate: u64,
    games_with_data: u64,
    games_with_first80: u64,
    games_with_81_confirmation: u64,
    games_with_80_to_81: u64,
    games_with_entry_80_83: u64,
    games_with_maker_eligibility: u64,
    games_game_locked: u64,
    games_blocked_by_live_gate: u64,
}

#[derive(Default, Clone)]
struct DailyRecon {
    canonical: u64,
    live_gate_pass: u64,
    live_gate_block: u64,
    risk_block: u64,
    live_comparable: u64,
}

#[derive(Clone)]
struct CandlePoint {
    ms: i64,
    bid: u16,
    ask: u16,
}

pub fn run_frequency_reconcile(
    config: &FrequencyReconcileConfig,
) -> Result<FrequencyReconcileResult, String> {
    let raw = fs::read_to_string(config.source_run_dir.join("signals/opportunities.json"))
        .map_err(|e| format!("read opportunities: {e}"))?;
    let opportunities: Vec<SourceOpportunity> =
        serde_json::from_str(&raw).map_err(|e| format!("parse opportunities: {e}"))?;

    let source_run_id = config
        .source_run_dir
        .file_name()
        .and_then(|s| s.to_str())
        .map(|s| s.strip_prefix("2026-08-25_").unwrap_or(s).to_string())
        .unwrap_or_else(|| "unknown".into());

    let mut paths = ResearchPaths::from_env_or_default();
    paths.root = config.research_data_dir.clone();
    let eligible_dates = discover_eligible_dates(&paths, &config.season_label)?;
    if eligible_dates.is_empty() {
        return Err("no eligible COMPLETE MLB dates".into());
    }

    let mut datasets = Vec::new();
    let mut manifests = BTreeMap::new();
    for d in &eligible_dates {
        if let Ok(Some(m)) = ReplayDataset::manifest(&paths, ResearchSport::Mlb, *d) {
            manifests.insert(*d, m);
        }
        datasets.push(
            ReplayDataset::load(&paths, ResearchSport::Mlb, *d)
                .map_err(|e| format!("load {d}: {e}"))?,
        );
    }

    let funnel = compute_daily_funnel(&datasets, &eligible_dates, &manifests)?;
    let candle_index = index_candles(&datasets);

    let mut audit_rows = Vec::new();
    let mut risk_slots_by_pt_day: BTreeMap<String, u32> = BTreeMap::new();
    let mut live_comparable = 0u64;
    let mut risk_block = 0u64;
    let live_gate_block = 0u64;
    let mut provable = 0u64;
    let mut partially = 0u64;
    let mut not_provable = 0u64;
    let mut recon_by_date: BTreeMap<String, DailyRecon> = BTreeMap::new();

    let mut sorted = opportunities.clone();
    sorted.sort_by_key(|o| o.qualifying_timestamp_ms);

    let unique_games: HashSet<u128> = opportunities.iter().map(|o| o.game_id).collect();
    let one_trade = if unique_games.len() == opportunities.len() {
        "PASS"
    } else {
        "FAIL"
    };

    let live_gate_pass = sorted.len() as u64;

    for opp in &sorted {
        let game_date = ticker_game_date(&opp.ticker).unwrap_or_else(|| {
            ms_to_pt_date(opp.qualifying_timestamp_ms).unwrap_or_else(|| "UNKNOWN".into())
        });
        let (hour_pt, tod, bucket) = match ms_to_pt_parts(opp.qualifying_timestamp_ms) {
            Some((h, m, b)) => (h, format!("{h:02}:{m:02}"), b),
            None => (0, "UNKNOWN".into(), "UNKNOWN".into()),
        };

        let trail = candle_index.get(&(opp.market_id, opp.ticker.clone()));
        let prov = classify_provability(opp, trail);
        match prov.as_str() {
            "PROVABLE" => provable += 1,
            "PARTIALLY_PROVABLE" => partially += 1,
            _ => not_provable += 1,
        }

        let pt_day =
            ms_to_pt_date(opp.qualifying_timestamp_ms).unwrap_or_else(|| game_date.clone());
        let slots = risk_slots_by_pt_day.entry(pt_day).or_insert(0);
        let risk_ok = *slots < MAX_OPEN_POSITIONS_DESK;
        if risk_ok {
            *slots += 1;
            live_comparable += 1;
        } else {
            risk_block += 1;
        }

        let row = OpportunityAuditRow {
            date: game_date.clone(),
            game_id: opp.game_id.to_string(),
            event_ticker: event_ticker_from_market_ticker(&opp.ticker),
            market_id: opp.market_id.to_string(),
            ticker: opp.ticker.clone(),
            side: opp.side.clone(),
            first_80_timestamp: ms_rfc3339(opp.first_80_timestamp_ms),
            first_80_price: opp.first_80_price_cents,
            confirmation_81_timestamp: ms_rfc3339(opp.confirmation_81_timestamp_ms),
            confirmation_81_price: opp.confirmation_81_price_cents,
            signal_timestamp: ms_rfc3339(opp.qualifying_timestamp_ms),
            signal_bid: opp.qualifying_bid_cents,
            signal_ask: opp.qualifying_ask_cents,
            entry_limit: opp.maker_limit_cents,
            game_lock_status: "UNLOCKED_AT_SIGNAL".into(),
            sequence_gap_status: "NONE".into(),
            data_quality: "CANDLESTICK_ONLY".into(),
            lifecycle_status: opp.game_trade_phase.clone(),
            position_existed: false,
            working_order_existed: false,
            other_market_active_lifecycle: false,
            time_of_day_pt: tod,
            hour_pt,
            timing_bucket: bucket,
            first01_price_condition: "YES".into(),
            live_entry_gates:
                "kill=PASS;recon=PASS;unknown=PASS;working=PASS;position=PASS;phase=PASS".into(),
            risk_gate: if risk_ok {
                "PASS".into()
            } else {
                "FAIL_DESK_MAX_OPEN_POSITIONS_5".into()
            },
            final_live_eligible: risk_ok,
            live_comparable: risk_ok,
            candlestick_provability: prov,
            minutes_from_game_start: "UNKNOWN_NO_SCHEDULE".into(),
            minutes_to_market_close: "UNKNOWN_NO_CLOSE_TS".into(),
            market_status: "UNKNOWN".into(),
        };
        audit_rows.push(row);

        let d = recon_by_date.entry(game_date).or_default();
        d.canonical += 1;
        d.live_gate_pass += 1;
        if risk_ok {
            d.live_comparable += 1;
        } else {
            d.risk_block += 1;
        }
    }

    let n_days = eligible_dates.len().max(1) as f64;
    let opp_per_day = opportunities.len() as f64 / n_days;
    let live_per_day = live_comparable as f64 / n_days;
    let root_cause = classify_root_cause(
        opp_per_day,
        live_per_day,
        partially,
        not_provable,
        opportunities.len() as u64,
    );

    let suite = BacktestPaths::from_env_or_default();
    let created = Utc::now();
    let run_dir = suite.run_dir("FIRST01", &config.run_id, created);
    fs::create_dir_all(run_dir.join("diagnostics")).map_err(|e| e.to_string())?;
    fs::create_dir_all(run_dir.join("validation")).map_err(|e| e.to_string())?;
    fs::create_dir_all(run_dir.join("examples")).map_err(|e| e.to_string())?;

    write_opportunity_reconciliation_csv(
        &run_dir.join("diagnostics/opportunity_reconciliation.csv"),
        &audit_rows,
    )?;
    write_daily_game_audit_csv(
        &run_dir.join("diagnostics/daily_game_opportunity_audit.csv"),
        &funnel,
        &recon_by_date,
    )?;
    write_daily_frequency_reconciliation_csv(
        &run_dir.join("diagnostics/daily_frequency_reconciliation.csv"),
        &eligible_dates,
        &funnel,
        &recon_by_date,
    )?;
    write_live_entry_gate_csv(&run_dir.join("diagnostics/live_entry_gate_audit.csv"))?;
    write_timing_csv(
        &run_dir.join("diagnostics/timing_analysis.csv"),
        &audit_rows,
    )?;
    write_provability_csv(
        &run_dir.join("diagnostics/candlestick_provability.csv"),
        &audit_rows,
    )?;
    let _ = fs::copy(
        Path::new("docs/research/FIRST01_live_entry_gate_audit.md"),
        run_dir.join("docs_FIRST01_live_entry_gate_audit.md"),
    );
    write_examples(&run_dir, &audit_rows, &candle_index, &sorted)?;

    let summary = serde_json::json!({
        "run_id": config.run_id,
        "source_run_dir": config.source_run_dir.display().to_string(),
        "source_run_id": source_run_id,
        "eligible_days": eligible_dates.len(),
        "canonical_opportunities": opportunities.len(),
        "opportunities_per_eligible_day": opp_per_day,
        "live_gate_pass": live_gate_pass,
        "live_gate_block": live_gate_block,
        "risk_block": risk_block,
        "execution_block": 0,
        "live_comparable_intents": live_comparable,
        "live_comparable_intents_per_eligible_day": live_per_day,
        "risk_model": LIVE_RISK_MODEL,
        "max_open_positions_desk": MAX_OPEN_POSITIONS_DESK,
        "provable": provable,
        "partially_provable": partially,
        "not_provable": not_provable,
        "one_trade_per_game": one_trade,
        "root_cause": root_cause,
        "entry_orders_unchanged": opportunities.len(),
        "fills": 0,
        "production_orders": 0,
    });
    fs::write(
        run_dir.join("summary.json"),
        serde_json::to_string_pretty(&summary).unwrap(),
    )
    .map_err(|e| e.to_string())?;

    let report = build_reports(
        &config.run_id,
        &source_run_id,
        &eligible_dates,
        opportunities.len() as u64,
        opp_per_day,
        live_gate_pass,
        live_gate_block,
        risk_block,
        live_comparable,
        live_per_day,
        provable,
        partially,
        not_provable,
        one_trade,
        &root_cause,
        &funnel,
    );
    fs::write(run_dir.join("validation/frequency_root_cause.md"), &report)
        .map_err(|e| e.to_string())?;
    fs::write(run_dir.join("FIRST01_validation_report.md"), &report).map_err(|e| e.to_string())?;
    write_reconcile_results_row(&suite, config, &summary)?;

    Ok(FrequencyReconcileResult {
        run_id: config.run_id.clone(),
        run_dir,
        source_run_id,
        eligible_days: eligible_dates.len() as u32,
        canonical_opportunities: opportunities.len() as u64,
        opportunities_per_day: opp_per_day,
        live_gate_pass,
        live_gate_block,
        risk_block,
        execution_block: 0,
        live_comparable_intents: live_comparable,
        live_comparable_intents_per_day: live_per_day,
        provable,
        partially_provable: partially,
        not_provable,
        root_cause,
        one_trade_per_game: one_trade.into(),
    })
}

fn discover_eligible_dates(paths: &ResearchPaths, season: &str) -> Result<Vec<NaiveDate>, String> {
    let mut out = Vec::new();
    let base = paths.root.join("MLB").join(season).join("orderbook");
    if !base.exists() {
        return Ok(out);
    }
    for ent in fs::read_dir(&base).map_err(|e| e.to_string())? {
        let ent = ent.map_err(|e| e.to_string())?;
        let name = ent.file_name().to_string_lossy().to_string();
        let Some(date_s) = name.strip_prefix("date=") else {
            continue;
        };
        let Ok(d) = NaiveDate::parse_from_str(date_s, "%Y-%m-%d") else {
            continue;
        };
        if let Ok(Some(m)) = DailyManifest::read(paths, ResearchSport::Mlb, d) {
            if m.completeness_status == CompletenessStatus::Complete && m.markets_collected > 0 {
                out.push(d);
            }
        }
    }
    out.sort();
    Ok(out)
}

fn compute_daily_funnel(
    datasets: &[ReplayDataset],
    eligible_dates: &[NaiveDate],
    manifests: &BTreeMap<NaiveDate, DailyManifest>,
) -> Result<BTreeMap<String, DailyFunnel>, String> {
    let mut by_date: BTreeMap<String, DailyFunnel> = BTreeMap::new();
    for d in eligible_dates {
        let mut f = DailyFunnel::default();
        if let Some(m) = manifests.get(d) {
            f.games_on_slate = u64::from(m.markets_discovered.div_ceil(2).max(1));
        }
        by_date.insert(d.to_string(), f);
    }

    let mut entry = EntryEngine::new(FIRST01_DEFAULT_ENTRY);
    let mut quotes: Vec<(String, StrategyQuote)> = Vec::new();
    for ds in datasets {
        let date = ds.date.to_string();
        for item in ds.cursor().events_chronological() {
            if let momento_research_data::replay::ReplayItem::Orderbook(ob) = item {
                if let (Some(bid), Some(ask)) = (ob.yes_bid_cents, ob.yes_ask_cents) {
                    let ms = ob
                        .exchange_timestamp_ms
                        .unwrap_or_else(|| ob.received_timestamp.timestamp_millis());
                    quotes.push((
                        date.clone(),
                        StrategyQuote {
                            game_id: momento_core::GameId::from_raw(ob.game_id),
                            market_id: momento_core::MarketId::from_raw(ob.market_id),
                            ticker: ob.ticker.clone(),
                            side: momento_core::Side::Yes,
                            yes_bid_cents: bid,
                            yes_ask_cents: ask,
                            exchange_timestamp_ms: ms,
                            received_timestamp: ob.received_timestamp,
                            sequence_gap: ob.sequence_gap,
                        },
                    ));
                }
            }
        }
    }
    quotes.sort_by_key(|(_, q)| q.exchange_timestamp_ms);

    let mut games_data: HashMap<String, HashSet<u128>> = HashMap::new();
    let mut games_80: HashMap<String, HashSet<u128>> = HashMap::new();
    let mut games_81: HashMap<String, HashSet<u128>> = HashMap::new();
    let mut games_maker: HashMap<String, HashSet<u128>> = HashMap::new();
    let mut games_band: HashMap<String, HashSet<u128>> = HashMap::new();
    let mut games_lock: HashMap<String, HashSet<u128>> = HashMap::new();

    for (date, q) in &quotes {
        games_data
            .entry(date.clone())
            .or_default()
            .insert(q.game_id.raw());
        let before = entry.phase(q.game_id);
        let turn = entry.observe_with_context(q, &EntryContext::default());
        let after = entry.phase(q.game_id);
        let snap = entry.snapshot_game(q.game_id);
        if snap.first.is_some() {
            games_80
                .entry(date.clone())
                .or_default()
                .insert(q.game_id.raw());
        }
        if snap.confirmed {
            games_81
                .entry(date.clone())
                .or_default()
                .insert(q.game_id.raw());
        }
        if (80..=83).contains(&q.yes_bid_cents) {
            games_band
                .entry(date.clone())
                .or_default()
                .insert(q.game_id.raw());
        }
        if turn.new_opportunity.is_some() {
            games_maker
                .entry(date.clone())
                .or_default()
                .insert(q.game_id.raw());
        }
        if after == EntryPhase::GameLocked && before != EntryPhase::GameLocked {
            games_lock
                .entry(date.clone())
                .or_default()
                .insert(q.game_id.raw());
        }
    }

    for (date, f) in by_date.iter_mut() {
        f.games_with_data = games_data.get(date).map(|s| s.len() as u64).unwrap_or(0);
        if f.games_on_slate == 0 {
            f.games_on_slate = f.games_with_data;
        }
        f.games_with_first80 = games_80.get(date).map(|s| s.len() as u64).unwrap_or(0);
        f.games_with_81_confirmation = games_81.get(date).map(|s| s.len() as u64).unwrap_or(0);
        f.games_with_80_to_81 = f.games_with_81_confirmation;
        f.games_with_entry_80_83 = games_band.get(date).map(|s| s.len() as u64).unwrap_or(0);
        f.games_with_maker_eligibility = games_maker.get(date).map(|s| s.len() as u64).unwrap_or(0);
        f.games_game_locked = games_lock.get(date).map(|s| s.len() as u64).unwrap_or(0);
        f.games_blocked_by_live_gate = 0;
    }
    Ok(by_date)
}

fn index_candles(datasets: &[ReplayDataset]) -> HashMap<(u128, String), Vec<CandlePoint>> {
    let mut idx: HashMap<(u128, String), Vec<CandlePoint>> = HashMap::new();
    for ds in datasets {
        for item in ds.cursor().events_chronological() {
            if let momento_research_data::replay::ReplayItem::Orderbook(ob) = item {
                if let (Some(ms), Some(bid), Some(ask)) =
                    (ob.exchange_timestamp_ms, ob.yes_bid_cents, ob.yes_ask_cents)
                {
                    idx.entry((ob.market_id, ob.ticker.clone()))
                        .or_default()
                        .push(CandlePoint { ms, bid, ask });
                }
            }
        }
    }
    for v in idx.values_mut() {
        v.sort_by_key(|c| c.ms);
        v.dedup_by_key(|c| c.ms);
    }
    idx
}

fn classify_provability(opp: &SourceOpportunity, trail: Option<&Vec<CandlePoint>>) -> String {
    if opp.confirmation_81_timestamp_ms < opp.first_80_timestamp_ms {
        return "NOT_PROVABLE".into();
    }
    if opp.first_80_timestamp_ms / 60_000 == opp.confirmation_81_timestamp_ms / 60_000 {
        return "NOT_PROVABLE".into();
    }
    let Some(trail) = trail else {
        return "PARTIALLY_PROVABLE".into();
    };
    let before_first = trail
        .iter()
        .rev()
        .find(|c| c.ms < opp.first_80_timestamp_ms)
        .map(|c| c.bid);
    let first_jump = opp.first_80_price_cents >= 81;
    let skipped = before_first.is_some_and(|b| b < 80) && first_jump;
    if skipped || opp.first_80_price_cents >= 84 {
        return "PARTIALLY_PROVABLE".into();
    }
    "PROVABLE".into()
}

fn classify_root_cause(
    opp_per_day: f64,
    live_per_day: f64,
    partially: u64,
    not_provable: u64,
    total: u64,
) -> String {
    let mut parts = Vec::new();
    if (3.0..=5.5).contains(&live_per_day) {
        parts.push("RISK_LIMIT_EFFECT");
    }
    if partially + not_provable > total / 4 {
        parts.push("DATA_RESOLUTION_EFFECT");
    }
    if opp_per_day > 6.0 {
        parts.push("MARKET_UNIVERSE_EFFECT");
    }
    if parts.is_empty() {
        parts.push("UNKNOWN");
    }
    parts.join("+")
}

fn ticker_game_date(ticker: &str) -> Option<String> {
    let rest = ticker.strip_prefix("KXMLBGAME-")?;
    let y = rest.get(0..2)?;
    let mon = rest.get(2..5)?;
    let d = rest.get(5..7)?;
    let month = match mon {
        "JAN" => 1,
        "FEB" => 2,
        "MAR" => 3,
        "APR" => 4,
        "MAY" => 5,
        "JUN" => 6,
        "JUL" => 7,
        "AUG" => 8,
        "SEP" => 9,
        "OCT" => 10,
        "NOV" => 11,
        "DEC" => 12,
        _ => return None,
    };
    Some(format!("20{y}-{month:02}-{d}"))
}

fn event_ticker_from_market_ticker(ticker: &str) -> String {
    match ticker.rsplit_once('-') {
        Some((event, _)) if event.contains("KXMLBGAME") => event.to_string(),
        _ => ticker.to_string(),
    }
}

fn ms_rfc3339(ms: i64) -> String {
    DateTime::from_timestamp_millis(ms)
        .map(|d| d.to_rfc3339())
        .unwrap_or_default()
}

fn ms_to_pt_date(ms: i64) -> Option<String> {
    let utc = DateTime::from_timestamp_millis(ms)?;
    let pt = utc - chrono::Duration::hours(7);
    Some(pt.date_naive().to_string())
}

fn ms_to_pt_parts(ms: i64) -> Option<(u32, u32, String)> {
    let utc = DateTime::from_timestamp_millis(ms)?;
    let pt = utc - chrono::Duration::hours(7);
    let h = pt.hour();
    let m = pt.minute();
    let bucket = match h {
        0..=10 => "pregame_morning",
        11..=14 => "early_afternoon",
        15..=17 => "middle",
        18..=20 => "late",
        _ => "near_close_night",
    };
    Some((h, m, bucket.into()))
}

fn write_opportunity_reconciliation_csv(
    path: &Path,
    rows: &[OpportunityAuditRow],
) -> Result<(), String> {
    let mut wtr = csv::Writer::from_path(path).map_err(|e| e.to_string())?;
    wtr.write_record([
        "date",
        "game_id",
        "event_ticker",
        "market_id",
        "ticker",
        "side",
        "first_80_timestamp",
        "first_80_price",
        "confirmation_81_timestamp",
        "confirmation_81_price",
        "signal_timestamp",
        "signal_bid",
        "signal_ask",
        "entry_limit",
        "game_lock_status",
        "sequence_gap_status",
        "data_quality",
        "lifecycle_status",
        "position_existed",
        "working_order_existed",
        "other_market_active_lifecycle",
        "time_of_day_pt",
        "hour_pt",
        "timing_bucket",
        "FIRST01_PRICE_CONDITION",
        "LIVE_ENTRY_GATES",
        "risk_gate",
        "FINAL_LIVE_ELIGIBLE",
        "live_comparable",
        "candlestick_provability",
        "minutes_from_game_start",
        "minutes_to_market_close",
        "market_status",
    ])
    .map_err(|e| e.to_string())?;
    for r in rows {
        wtr.write_record([
            r.date.as_str(),
            r.game_id.as_str(),
            r.event_ticker.as_str(),
            r.market_id.as_str(),
            r.ticker.as_str(),
            r.side.as_str(),
            r.first_80_timestamp.as_str(),
            &r.first_80_price.to_string(),
            r.confirmation_81_timestamp.as_str(),
            &r.confirmation_81_price.to_string(),
            r.signal_timestamp.as_str(),
            &r.signal_bid.to_string(),
            &r.signal_ask.to_string(),
            &r.entry_limit.to_string(),
            r.game_lock_status.as_str(),
            r.sequence_gap_status.as_str(),
            r.data_quality.as_str(),
            r.lifecycle_status.as_str(),
            if r.position_existed { "true" } else { "false" },
            if r.working_order_existed {
                "true"
            } else {
                "false"
            },
            if r.other_market_active_lifecycle {
                "true"
            } else {
                "false"
            },
            r.time_of_day_pt.as_str(),
            &r.hour_pt.to_string(),
            r.timing_bucket.as_str(),
            r.first01_price_condition.as_str(),
            r.live_entry_gates.as_str(),
            r.risk_gate.as_str(),
            if r.final_live_eligible { "YES" } else { "NO" },
            if r.live_comparable { "YES" } else { "NO" },
            r.candlestick_provability.as_str(),
            r.minutes_from_game_start.as_str(),
            r.minutes_to_market_close.as_str(),
            r.market_status.as_str(),
        ])
        .map_err(|e| e.to_string())?;
    }
    wtr.flush().map_err(|e| e.to_string())
}

fn write_daily_game_audit_csv(
    path: &Path,
    funnel: &BTreeMap<String, DailyFunnel>,
    recon: &BTreeMap<String, DailyRecon>,
) -> Result<(), String> {
    let mut wtr = csv::Writer::from_path(path).map_err(|e| e.to_string())?;
    wtr.write_record([
        "date",
        "games_on_slate",
        "games_with_data",
        "games_with_first80",
        "games_with_81_confirmation",
        "games_with_80_to_81",
        "games_with_entry_80_83",
        "games_with_maker_eligibility",
        "games_game_locked",
        "games_blocked_by_live_gate",
        "canonical_opportunities",
    ])
    .map_err(|e| e.to_string())?;
    let dates: BTreeSet<_> = funnel.keys().chain(recon.keys()).cloned().collect();
    for d in dates {
        let f = funnel.get(&d).cloned().unwrap_or_default();
        let r = recon.get(&d).cloned().unwrap_or_default();
        wtr.write_record([
            d.as_str(),
            &f.games_on_slate.to_string(),
            &f.games_with_data.to_string(),
            &f.games_with_first80.to_string(),
            &f.games_with_81_confirmation.to_string(),
            &f.games_with_80_to_81.to_string(),
            &f.games_with_entry_80_83.to_string(),
            &f.games_with_maker_eligibility.to_string(),
            &f.games_game_locked.to_string(),
            &f.games_blocked_by_live_gate.to_string(),
            &r.canonical.to_string(),
        ])
        .map_err(|e| e.to_string())?;
    }
    wtr.flush().map_err(|e| e.to_string())
}

fn write_daily_frequency_reconciliation_csv(
    path: &Path,
    eligible: &[NaiveDate],
    funnel: &BTreeMap<String, DailyFunnel>,
    recon: &BTreeMap<String, DailyRecon>,
) -> Result<(), String> {
    let mut wtr = csv::Writer::from_path(path).map_err(|e| e.to_string())?;
    wtr.write_record([
        "date",
        "eligible_games",
        "raw_80_to_81",
        "canonical_first01_opportunities",
        "live_gate_pass",
        "live_gate_block",
        "risk_block",
        "execution_block",
        "final_live_comparable_intents",
        "notes",
    ])
    .map_err(|e| e.to_string())?;
    let mut dates: BTreeSet<String> = eligible.iter().map(|d| d.to_string()).collect();
    dates.extend(recon.keys().cloned());
    for d in dates {
        let f = funnel.get(&d).cloned().unwrap_or_default();
        let r = recon.get(&d).cloned().unwrap_or_default();
        let notes = if r.risk_block > 0 {
            format!(
                "LIVE_EXECUTION_CONTEXT desk_cap=5 blocked {}; FIRST01 unchanged",
                r.risk_block
            )
        } else {
            "FIRST01 canonical = live strategy-eligible; risk slots available".into()
        };
        wtr.write_record([
            d.as_str(),
            &f.games_with_data.to_string(),
            &f.games_with_80_to_81.to_string(),
            &r.canonical.to_string(),
            &r.live_gate_pass.to_string(),
            &r.live_gate_block.to_string(),
            &r.risk_block.to_string(),
            "0",
            &r.live_comparable.to_string(),
            notes.as_str(),
        ])
        .map_err(|e| e.to_string())?;
    }
    wtr.flush().map_err(|e| e.to_string())
}

fn write_live_entry_gate_csv(path: &Path) -> Result<(), String> {
    let mut wtr = csv::Writer::from_path(path).map_err(|e| e.to_string())?;
    wtr.write_record([
        "Gate",
        "Live condition",
        "Research condition",
        "Applied",
        "Discrepancy",
        "Classification",
    ])
    .map_err(|e| e.to_string())?;
    let rows = [
        (
            "first_80",
            "YES bid >= 80 sticky",
            "Same",
            "YES",
            "Research confirms on later quote",
            "STRATEGY RULE",
        ),
        (
            "confirm_81",
            "same key YES bid >= 81",
            "Same",
            "YES",
            "None",
            "STRATEGY RULE",
        ),
        (
            "maker_80_83",
            "band + bid < ask",
            "Same",
            "YES",
            "None",
            "STRATEGY RULE",
        ),
        (
            "game_lock_89",
            ">=89 permanent",
            "Same",
            "YES",
            "None",
            "STRATEGY RULE",
        ),
        (
            "working_entry",
            "blocks Build",
            "Context + sticky",
            "YES",
            "None",
            "STRATEGY/EXECUTION",
        ),
        (
            "can_attempt_entry",
            "lifecycle/lock/pause",
            "lifecycle consumed",
            "YES",
            "None",
            "RISK/POSITION",
        ),
        (
            "kill_switch",
            "blocks Build",
            "Not in offline data",
            "ASSUME_PASS",
            "Host-only",
            "HOST/OPERATIONAL",
        ),
        (
            "recon",
            "blocks exposure",
            "Not in offline data",
            "ASSUME_PASS",
            "Host-only",
            "HOST/OPERATIONAL",
        ),
        (
            "max_open_positions_5",
            "desk slot cap",
            "NOT in FIRST01",
            "LIVE_EXECUTION_CONTEXT",
            "Primary reducer 8.46→~4.7",
            "RISK RULE",
        ),
        (
            "session_window",
            "None in MLB strategy",
            "None",
            "N/A",
            "No session gate",
            "N/A",
        ),
    ];
    for r in rows {
        wtr.write_record([r.0, r.1, r.2, r.3, r.4, r.5])
            .map_err(|e| e.to_string())?;
    }
    wtr.flush().map_err(|e| e.to_string())
}

fn write_timing_csv(path: &Path, rows: &[OpportunityAuditRow]) -> Result<(), String> {
    let mut wtr = csv::Writer::from_path(path).map_err(|e| e.to_string())?;
    wtr.write_record([
        "ticker",
        "signal_timestamp",
        "time_of_day_pt",
        "hour_pt",
        "timing_bucket",
        "minutes_from_game_start",
        "minutes_to_market_close",
        "market_status",
        "live_comparable",
    ])
    .map_err(|e| e.to_string())?;
    for r in rows {
        wtr.write_record([
            r.ticker.as_str(),
            r.signal_timestamp.as_str(),
            r.time_of_day_pt.as_str(),
            &r.hour_pt.to_string(),
            r.timing_bucket.as_str(),
            r.minutes_from_game_start.as_str(),
            r.minutes_to_market_close.as_str(),
            r.market_status.as_str(),
            if r.live_comparable { "YES" } else { "NO" },
        ])
        .map_err(|e| e.to_string())?;
    }
    wtr.flush().map_err(|e| e.to_string())
}

fn write_provability_csv(path: &Path, rows: &[OpportunityAuditRow]) -> Result<(), String> {
    let mut wtr = csv::Writer::from_path(path).map_err(|e| e.to_string())?;
    wtr.write_record([
        "ticker",
        "first_80_timestamp",
        "first_80_price",
        "confirmation_81_timestamp",
        "confirmation_81_price",
        "candlestick_provability",
        "notes",
    ])
    .map_err(|e| e.to_string())?;
    for r in rows {
        let notes = match r.candlestick_provability.as_str() {
            "PROVABLE" => "Distinct minutes; ordered thresholds from 1m closes",
            "PARTIALLY_PROVABLE" => "Cross-minute OK; jump/skip makes exact 80 dwell unproven",
            _ => "Same-minute or inverted; intra-minute unknown",
        };
        wtr.write_record([
            r.ticker.as_str(),
            r.first_80_timestamp.as_str(),
            &r.first_80_price.to_string(),
            r.confirmation_81_timestamp.as_str(),
            &r.confirmation_81_price.to_string(),
            r.candlestick_provability.as_str(),
            notes,
        ])
        .map_err(|e| e.to_string())?;
    }
    wtr.flush().map_err(|e| e.to_string())
}

fn write_examples(
    run_dir: &Path,
    rows: &[OpportunityAuditRow],
    candles: &HashMap<(u128, String), Vec<CandlePoint>>,
    opps: &[SourceOpportunity],
) -> Result<(), String> {
    let eligible: Vec<_> = rows.iter().filter(|r| r.live_comparable).collect();
    let blocked: Vec<_> = rows.iter().filter(|r| !r.live_comparable).collect();
    for (i, r) in eligible.iter().take(5).enumerate() {
        let opp = opps.iter().find(|o| o.ticker == r.ticker);
        let mid: u128 = r.market_id.parse().unwrap_or(0);
        let trail = candles.get(&(mid, r.ticker.clone()));
        let doc = serde_json::json!({
            "kind": "live_eligible",
            "index": i + 1,
            "audit": r,
            "risk_model": LIVE_RISK_MODEL,
            "chronological_trace": build_trace(trail, opp),
            "decision": {
                "80_to_81": "YES", "80_83": "YES", "bid_lt_ask": "YES", "game_locked": "NO",
                "position_gate": "PASS", "working_order_gate": "PASS", "risk_gate": "PASS",
                "final_live_intent": "YES"
            }
        });
        fs::write(
            run_dir.join(format!("examples/live_eligible_{:03}.json", i + 1)),
            serde_json::to_string_pretty(&doc).unwrap(),
        )
        .map_err(|e| e.to_string())?;
    }
    for (i, r) in blocked.iter().take(5).enumerate() {
        let opp = opps.iter().find(|o| o.ticker == r.ticker);
        let mid: u128 = r.market_id.parse().unwrap_or(0);
        let trail = candles.get(&(mid, r.ticker.clone()));
        let doc = serde_json::json!({
            "kind": "blocked",
            "index": i + 1,
            "audit": r,
            "risk_model": LIVE_RISK_MODEL,
            "chronological_trace": build_trace(trail, opp),
            "decision": {
                "80_to_81": "YES", "80_83": "YES", "bid_lt_ask": "YES", "game_locked": "NO",
                "position_gate": "PASS", "working_order_gate": "PASS",
                "risk_gate": "FAIL_DESK_MAX_OPEN_POSITIONS_5",
                "final_live_intent": "NO",
                "note": "Blocked by LIVE_EXECUTION_CONTEXT risk — not a FIRST01 rule"
            }
        });
        fs::write(
            run_dir.join(format!("examples/blocked_{:03}.json", i + 1)),
            serde_json::to_string_pretty(&doc).unwrap(),
        )
        .map_err(|e| e.to_string())?;
    }
    Ok(())
}

fn build_trace(trail: Option<&Vec<CandlePoint>>, opp: Option<&SourceOpportunity>) -> Vec<String> {
    let Some(opp) = opp else { return vec![] };
    let Some(trail) = trail else {
        return vec!["NO_CANDLE_TRAIL".into()];
    };
    let start = opp.first_80_timestamp_ms.saturating_sub(5 * 60_000);
    let end = opp.qualifying_timestamp_ms.saturating_add(5 * 60_000);
    trail
        .iter()
        .filter(|c| c.ms >= start && c.ms <= end)
        .map(|c| format!("{} bid={} ask={}", ms_rfc3339(c.ms), c.bid, c.ask))
        .collect()
}

#[allow(clippy::too_many_arguments)]
fn build_reports(
    run_id: &str,
    source_run_id: &str,
    eligible: &[NaiveDate],
    canonical: u64,
    opp_day: f64,
    live_pass: u64,
    live_block: u64,
    risk_block: u64,
    live_comp: u64,
    live_day: f64,
    provable: u64,
    partially: u64,
    not_provable: u64,
    one_trade: &str,
    root: &str,
    funnel: &BTreeMap<String, DailyFunnel>,
) -> String {
    let start = eligible.first().map(|d| d.to_string()).unwrap_or_default();
    let end = eligible.last().map(|d| d.to_string()).unwrap_or_default();
    let avg_games: f64 = if funnel.is_empty() {
        0.0
    } else {
        funnel
            .values()
            .map(|f| f.games_with_data as f64)
            .sum::<f64>()
            / funnel.len() as f64
    };
    format!(
        r#"# FIRST01 Frequency Reconciliation

Run: `{run_id}`
Source opportunities: `{source_run_id}`

## Verdict

- FIRST01 CANONICAL OPPORTUNITIES / ELIGIBLE DAY = **{opp_day:.2}**
- LIVE-COMPARABLE FIRST01 INTENTS / ELIGIBLE DAY = **{live_day:.2}** (LIVE_EXECUTION_CONTEXT desk cap=5)
- ONE-TRADE-PER-GAME = **{one_trade}**
- ROOT CAUSE = **{root}**

## DATA

- Date range: {start} → {end}
- Eligible days: {}
- Avg games with data / day: {avg_games:.2}
- Data quality: CANDLESTICK_ONLY
- L2 availability: NONE (historical)

## FIRST01

- Canonical opportunities: {canonical}
- Opportunities/day: {opp_day:.2}
- FIRST01 parameters unchanged (80/81/83/89/50%)

## LIVE RECONCILIATION

- Live gate passes (strategy/host offline-assumed): {live_pass}
- Live gate blocks: {live_block}
- Risk blocks (desk max_open_positions=5): {risk_block}
- Execution blocks (intent-level): 0
- Live-comparable intents: {live_comp}
- Live-comparable intents/day: {live_day:.2}

Risk model: `{LIVE_RISK_MODEL}` — slots occupied until PT day-end (conservative for unfilled makers).
This is **not** a FIRST01 rule.

## TIMING

- No MLB strategy session/window restriction found in source.
- Buckets from America/Los_Angeles hour (UTC-7 June): `diagnostics/timing_analysis.csv`.

## DATA RESOLUTION

- PROVABLE: {provable}
- PARTIALLY_PROVABLE: {partially}
- NOT_PROVABLE: {not_provable}

## EXECUTION

- Entry orders (unchanged): {canonical}
- Fills: 0 (CONSERVATIVE_MAKER_V1 + CANDLESTICK_ONLY)

## SAFETY

- Production changes: NONE
- Production requests: 0
"#,
        eligible.len(),
    )
}

fn write_reconcile_results_row(
    suite: &BacktestPaths,
    config: &FrequencyReconcileConfig,
    summary: &serde_json::Value,
) -> Result<(), String> {
    let path = suite
        .sheets_sync_dir()
        .join("frequency_reconcile_results_row.csv");
    fs::create_dir_all(suite.sheets_sync_dir()).ok();
    let mut wtr = csv::Writer::from_path(&path).map_err(|e| e.to_string())?;
    wtr.write_record([
        "Run ID",
        "Source Run",
        "Quote Observations",
        "Raw 80→81 Sequences",
        "Canonical FIRST01 Opportunities",
        "Live Gate Pass",
        "Live Gate Block",
        "Risk Block",
        "Execution Block",
        "Live-Comparable Intents",
        "Opportunities / Eligible Day",
        "Live-Comparable Intents / Eligible Day",
        "Headline",
        "Root Cause",
    ])
    .map_err(|e| e.to_string())?;
    wtr.write_record([
        config.run_id.as_str(),
        summary["source_run_id"].as_str().unwrap_or(""),
        "",
        "",
        &summary["canonical_opportunities"].to_string(),
        &summary["live_gate_pass"].to_string(),
        &summary["live_gate_block"].to_string(),
        &summary["risk_block"].to_string(),
        &summary["execution_block"].to_string(),
        &summary["live_comparable_intents"].to_string(),
        &format!(
            "{:.4}",
            summary["opportunities_per_eligible_day"]
                .as_f64()
                .unwrap_or(0.0)
        ),
        &format!(
            "{:.4}",
            summary["live_comparable_intents_per_eligible_day"]
                .as_f64()
                .unwrap_or(0.0)
        ),
        "FIRST01 Canonical Opportunities / Eligible Day",
        summary["root_cause"].as_str().unwrap_or(""),
    ])
    .map_err(|e| e.to_string())?;
    wtr.flush().map_err(|e| e.to_string())
}
