//! Batch synchronizer for the PBP + MATCHED-trades cohort. Streams per game.

use std::collections::BTreeMap;
use std::fs;
use std::path::{Path, PathBuf};

use chrono::{DateTime, Utc};
use momento_research_data::foundation::LakeWriteGuard;
use momento_research_ingest::paths::IngestPaths;
use momento_research_ingest::types::{GameMarketPair, IdentityMapping};
use serde::{Deserialize, Serialize};

use crate::apply::synchronize_market;
use crate::as_of::as_of;
use crate::error::W5Error;
use crate::market::load_matched_trade_sidecar;
use crate::store::SyncStore;
use crate::timeline::load_pbp_timeline;
use crate::types::{
    GameCoverage, GameStateSnapshot, IdentityStatus, SyncParams, SyncStatus, TimedEvent,
};
use crate::versions::{ARTIFACT_VERSION, DATASET_VERSION, WATERFALL};

#[derive(Clone, Debug)]
pub struct W5RunConfig {
    pub ingest_root: PathBuf,
    pub lake_root: PathBuf,
    pub out_dir: PathBuf,
    pub pairs: PathBuf,
    pub generated_at: DateTime<Utc>,
    pub max_games: Option<usize>,
    pub game_filter: Option<Vec<String>>,
    pub market_filter: Option<Vec<String>>,
}

impl W5RunConfig {
    pub fn defaults() -> Self {
        Self {
            ingest_root: PathBuf::from("Backtesting Suite/Foundation/Ingest"),
            lake_root: PathBuf::from("Backtesting Suite/Data-Real"),
            out_dir: PathBuf::from("Backtesting Suite/Foundation/W5"),
            pairs: PathBuf::from(
                "Backtesting Suite/Foundation/Ingest/runs/ingest-20260826T095038Z-2bc3d10b5833/game_market_pairs.json",
            ),
            generated_at: Utc::now(),
            max_games: None,
            game_filter: None,
            market_filter: None,
        }
    }
}

#[derive(Clone, Debug, Default, Serialize, Deserialize)]
pub struct SyncReport {
    pub waterfall: String,
    pub artifact_version: String,
    pub dataset_version: String,
    pub run_id: String,
    pub expected_games_note: String,
    pub games_attempted: usize,
    pub games_successfully_synchronized: usize,
    pub games_partially_synchronized: usize,
    pub games_failed: usize,
    pub games_with_complete_pbp: usize,
    pub games_with_market_observations: usize,
    pub games_with_both: usize,
    pub games_with_timestamp_gaps: usize,
    pub contract_sides_attempted: usize,
    pub contract_sides_synchronized: usize,
    pub observations_attempted: usize,
    pub observations_synchronized: usize,
    pub observations_at_event: usize,
    pub observations_synchronized_with_gap: usize,
    pub observations_before_first_event: usize,
    pub observations_after_last_event: usize,
    pub observations_ambiguous_timestamp: usize,
    pub observations_missing_timestamp: usize,
    pub observations_rejected: usize,
    pub identity_failures: usize,
    pub timestamp_failures: usize,
    pub source_invalid: usize,
    pub duplicate_market_observations_dropped: usize,
    pub malformed_market_records: usize,
    pub l2_observations: usize,
    pub quote_observations: usize,
    pub candle_observations: usize,
    pub trade_observations: usize,
    pub pbp_timestamp_precision: String,
    pub kalshi_timestamp_precision: String,
    pub market_ts_frac_0: usize,
    pub market_ts_frac_1_to_3: usize,
    pub market_ts_frac_4_plus: usize,
    pub lag_min_ms: Option<i64>,
    pub lag_median_ms: Option<i64>,
    pub lag_p95_ms: Option<i64>,
    pub lag_max_ms: Option<i64>,
    pub quality: BTreeMap<String, usize>,
    pub status: BTreeMap<String, usize>,
    pub timestamp_relation: BTreeMap<String, usize>,
    pub notes: Vec<String>,
    pub w5_gate: String,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct TimestampQualityReport {
    pub pbp_timestamp_precision: String,
    pub kalshi_timestamp_precision: String,
    pub market_ts_frac_0: usize,
    pub market_ts_frac_1_to_3: usize,
    pub market_ts_frac_4_plus: usize,
    pub lag_min_ms: Option<i64>,
    pub lag_median_ms: Option<i64>,
    pub lag_p95_ms: Option<i64>,
    pub lag_max_ms: Option<i64>,
    pub quality: BTreeMap<String, usize>,
    pub clock_correction_applied: bool,
}

pub fn run_w5_batch(cfg: &W5RunConfig) -> Result<SyncReport, W5Error> {
    let guard = LakeWriteGuard::new(&cfg.lake_root);
    guard
        .assert_not_lake_path(&cfg.out_dir)
        .map_err(W5Error::LakeWriteForbidden)?;

    let pairs: Vec<GameMarketPair> = serde_json::from_slice(&fs::read(&cfg.pairs)?)?;
    let mut by_game: BTreeMap<String, Vec<GameMarketPair>> = BTreeMap::new();
    for p in pairs {
        if p.mapping != IdentityMapping::Mapped {
            continue;
        }
        let Some(pk) = p.game_pk.clone().filter(|s| !s.is_empty()) else {
            continue;
        };
        if p.ticker.is_empty() {
            continue;
        }
        if let Some(gf) = cfg.game_filter.as_ref() {
            if !gf.is_empty() && !gf.contains(&pk) {
                continue;
            }
        }
        if let Some(mf) = cfg.market_filter.as_ref() {
            if !mf.is_empty() && !mf.contains(&p.ticker) {
                continue;
            }
        }
        by_game.entry(pk).or_default().push(p);
    }

    let ingest = IngestPaths::new(&cfg.ingest_root);
    let mut cohort: Vec<(String, Vec<GameMarketPair>)> = Vec::new();
    for (pk, sides) in &by_game {
        let date = sides
            .first()
            .map(|s| s.official_date.as_str())
            .unwrap_or("");
        let Ok(d) = chrono::NaiveDate::parse_from_str(date, "%Y-%m-%d") else {
            continue;
        };
        let pbp = ingest.landing_game(d, pk);
        if !pbp.exists() {
            continue;
        }
        let mut has_trades = false;
        for s in sides {
            let tap = ingest.landing_kalshi_matched_trades(d, &s.ticker);
            if tap.exists() {
                if let Ok(body) = fs::read(&tap) {
                    if let Ok(v) = serde_json::from_slice::<serde_json::Value>(&body) {
                        let n = v
                            .get("canonical_trade_count")
                            .and_then(|x| x.as_u64())
                            .unwrap_or(0);
                        if n > 0 {
                            has_trades = true;
                            break;
                        }
                    }
                }
            }
        }
        if has_trades {
            cohort.push((pk.clone(), sides.clone()));
        }
    }
    cohort.sort_by(|a, b| a.0.cmp(&b.0));
    if let Some(n) = cfg.max_games {
        cohort.truncate(n);
    }

    fs::create_dir_all(&cfg.out_dir)?;
    let run_id = format!("w5-{}", cfg.generated_at.format("%Y%m%dT%H%M%SZ"));
    let db_path = cfg.out_dir.join("sync.sqlite");
    for extra in ["sync.sqlite", "sync.sqlite-wal", "sync.sqlite-shm"] {
        let p = cfg.out_dir.join(extra);
        if p.exists() {
            let _ = fs::remove_file(&p);
        }
    }
    let mut store = SyncStore::open(&db_path, &run_id, cfg.generated_at)?;

    let mut report = SyncReport {
        waterfall: WATERFALL.into(),
        artifact_version: ARTIFACT_VERSION.into(),
        dataset_version: DATASET_VERSION.into(),
        run_id: run_id.clone(),
        expected_games_note:
            "User brief expected 1684 games / 3368 sides. Actual cohort is PBP ∩ MATCHED trades on disk."
                .into(),
        ..SyncReport::default()
    };
    report.waterfall = WATERFALL.into();
    report.artifact_version = ARTIFACT_VERSION.into();
    report.dataset_version = DATASET_VERSION.into();
    report.run_id = run_id.clone();
    report.pbp_timestamp_precision =
        "RFC3339 UTC from StatsAPI play startTime (seconds typical; source digits preserved)"
            .into();
    report.kalshi_timestamp_precision =
        "RFC3339 created_time; fractional digits preserved in source string; not upgraded".into();

    let mut lags: Vec<i64> = Vec::new();
    let mut coverage: Vec<GameCoverage> = Vec::new();
    let mut examples: Vec<serde_json::Value> = Vec::new();
    report.games_attempted = cohort.len();

    for (i, (pk, sides)) in cohort.iter().enumerate() {
        let date = sides[0].official_date.as_str();
        let Ok(d) = chrono::NaiveDate::parse_from_str(date, "%Y-%m-%d") else {
            report.games_failed += 1;
            continue;
        };
        let pbp_path = ingest.landing_game(d, pk);
        let timeline = match load_pbp_timeline(&pbp_path) {
            Ok(t) => t,
            Err(_) => {
                report.games_failed += 1;
                continue;
            }
        };
        if !timeline.timed.is_empty() {
            report.games_with_complete_pbp += 1;
        }
        let ambiguous_clock = timeline.ambiguous_clock();
        let game_id = timeline.game_id.clone();
        let mut game_success = 0usize;
        let mut game_obs = 0usize;
        let mut sides_ok = 0usize;
        let mut cov = GameCoverage {
            game_id: game_id.clone(),
            game_pk: pk.clone(),
            timed_events: timeline.timed.len(),
            observations: 0,
            synchronized: 0,
            at_event: 0,
            before_first: 0,
            after_last: 0,
            first_pbp_utc: timeline
                .timed
                .first()
                .map(|e| e.normalized_event_time.to_rfc3339()),
            last_pbp_utc: timeline
                .timed
                .last()
                .map(|e| e.normalized_event_time.to_rfc3339()),
            first_market_utc: None,
            last_market_utc: None,
        };

        let mut saw_gap = false;
        report.contract_sides_attempted += sides.len();
        for side in sides {
            let tape = match load_matched_trade_sidecar(
                &cfg.ingest_root,
                &side.official_date,
                &side.ticker,
                pk,
            ) {
                Ok(Some(t)) => t,
                Ok(None) => continue,
                Err(_) => {
                    report.identity_failures += 1;
                    continue;
                }
            };
            report.malformed_market_records += tape.malformed;
            report.duplicate_market_observations_dropped += tape.duplicates_dropped;
            report.trade_observations += tape.observations.len();
            report.observations_attempted += tape.observations.len();
            game_obs += tape.observations.len();
            cov.observations += tape.observations.len();
            for o in &tape.observations {
                if let Some(raw) = o
                    .source_market_time
                    .split_once('.')
                    .map(|(_, rest)| rest.chars().take_while(|c| c.is_ascii_digit()).count())
                {
                    match raw {
                        0 => report.market_ts_frac_0 += 1,
                        1..=3 => report.market_ts_frac_1_to_3 += 1,
                        _ => report.market_ts_frac_4_plus += 1,
                    }
                } else if o.normalized_market_time.is_some() {
                    report.market_ts_frac_0 += 1;
                }
                if let Some(t) = o.normalized_market_time {
                    let s = t.to_rfc3339();
                    match cov.first_market_utc.as_ref() {
                        None => cov.first_market_utc = Some(s.clone()),
                        Some(cur) if s.as_str() < cur.as_str() => {
                            cov.first_market_utc = Some(s.clone());
                        }
                        _ => {}
                    }
                    match cov.last_market_utc.as_ref() {
                        None => cov.last_market_utc = Some(s),
                        Some(cur) if s.as_str() > cur.as_str() => {
                            cov.last_market_utc = Some(s);
                        }
                        _ => {}
                    }
                }
            }
            let suffix = side.ticker.rsplit('-').next().unwrap_or("").to_string();
            let rows = synchronize_market(
                SyncParams {
                    game_id: &game_id,
                    game_pk: pk,
                    identity: IdentityStatus::Matched,
                    events: &timeline.timed,
                    contract_side: &suffix,
                    first_observed_price_cents: tape.first_observed_price_cents,
                    ambiguous_clock,
                },
                &tape.observations,
            );
            for r in &rows {
                *report
                    .status
                    .entry(r.synchronization_status.as_str().into())
                    .or_insert(0) += 1;
                *report
                    .quality
                    .entry(r.synchronization_quality.as_str().into())
                    .or_insert(0) += 1;
                *report
                    .timestamp_relation
                    .entry(r.timestamp_relation.as_str().into())
                    .or_insert(0) += 1;
                match r.synchronization_status {
                    SyncStatus::Synchronized => {
                        report.observations_synchronized += 1;
                        game_success += 1;
                        cov.synchronized += 1;
                    }
                    SyncStatus::AtEvent => {
                        report.observations_at_event += 1;
                        game_success += 1;
                        cov.at_event += 1;
                    }
                    SyncStatus::SynchronizedWithTimestampGap => {
                        report.observations_synchronized_with_gap += 1;
                        game_success += 1;
                        cov.synchronized += 1;
                        saw_gap = true;
                    }
                    SyncStatus::BeforeFirstEvent => {
                        report.observations_before_first_event += 1;
                        report.observations_rejected += 1;
                        cov.before_first += 1;
                    }
                    SyncStatus::AfterLastEvent => {
                        report.observations_after_last_event += 1;
                        report.observations_rejected += 1;
                        cov.after_last += 1;
                    }
                    SyncStatus::AmbiguousTimestamp => {
                        report.observations_ambiguous_timestamp += 1;
                        report.observations_rejected += 1;
                    }
                    SyncStatus::MissingTimestamp => {
                        report.observations_missing_timestamp += 1;
                        report.timestamp_failures += 1;
                        report.observations_rejected += 1;
                    }
                    SyncStatus::IdentityUnmatched | SyncStatus::IdentityAmbiguous => {
                        report.identity_failures += 1;
                        report.observations_rejected += 1;
                    }
                    SyncStatus::SourceDataInvalid => {
                        report.source_invalid += 1;
                        report.observations_rejected += 1;
                    }
                }
                if let Some(lag) = r.event_to_market_lag_ms {
                    if r.synchronization_status.is_success() {
                        lags.push(lag);
                    }
                }
            }
            if rows.iter().any(|r| r.synchronization_status.is_success()) {
                sides_ok += 1;
                report.contract_sides_synchronized += 1;
            }
            if examples.len() < 25 {
                for r in rows
                    .iter()
                    .filter(|r| r.synchronization_status.is_success())
                    .take(8)
                {
                    if examples.len() < 25 {
                        if let Ok(v) = serde_json::to_value(r) {
                            examples.push(v);
                        }
                    }
                }
            }
            store.insert_batch(&rows)?;
        }

        if game_obs == 0 {
            report.games_failed += 1;
        } else {
            report.games_with_market_observations += 1;
            if !timeline.timed.is_empty() {
                report.games_with_both += 1;
            }
            if game_success == game_obs {
                report.games_successfully_synchronized += 1;
            } else if game_success > 0 {
                report.games_partially_synchronized += 1;
            } else {
                report.games_failed += 1;
            }
            if saw_gap {
                report.games_with_timestamp_gaps += 1;
            }
        }
        store.insert_coverage(&cov)?;
        coverage.push(cov);

        if i == 0 || (i + 1) % 10 == 0 || i + 1 == cohort.len() {
            eprintln!(
                "w5-sync {}/{} gamePk={} sides={} timed_events={}",
                i + 1,
                cohort.len(),
                pk,
                sides_ok,
                timeline.timed.len()
            );
        }
    }

    lags.sort_unstable();
    report.lag_min_ms = lags.first().copied();
    report.lag_max_ms = lags.last().copied();
    report.lag_median_ms = median_i64(&lags);
    report.lag_p95_ms = percentile_i64(&lags, 95);
    report.l2_observations = 0;
    report.quote_observations = 0;
    report.candle_observations = 0;
    report.notes = vec![
        "Cohort is PBP + MATCHED Kalshi TRADES. Historical L2/order-book is UNAVAILABLE; none invented.".into(),
        "AS-OF: latest W3 event with effective time <= market created_time.".into(),
        "Exact timestamp equality is AT_EVENT. Applicable state is W3 after-state; pre_event_state is also stored.".into(),
        "Observations after the last PBP event are AFTER_LAST_EVENT and do not snap to the last state.".into(),
        "next_event_time is diagnostic only and is not used to construct state.".into(),
        "Retrieval/ingest time is provenance only and never orders observations.".into(),
        "first_observed_price_cents is not market_open_price / starting_price.".into(),
        "Unmatched Kalshi catalog rows remain in ingest identity artifacts; they are not this cohort.".into(),
        "W6 was not started.".into(),
    ];
    report.w5_gate = "RUN_COMPLETE".into();

    let quality = TimestampQualityReport {
        pbp_timestamp_precision: report.pbp_timestamp_precision.clone(),
        kalshi_timestamp_precision: report.kalshi_timestamp_precision.clone(),
        market_ts_frac_0: report.market_ts_frac_0,
        market_ts_frac_1_to_3: report.market_ts_frac_1_to_3,
        market_ts_frac_4_plus: report.market_ts_frac_4_plus,
        lag_min_ms: report.lag_min_ms,
        lag_median_ms: report.lag_median_ms,
        lag_p95_ms: report.lag_p95_ms,
        lag_max_ms: report.lag_max_ms,
        quality: report.quality.clone(),
        clock_correction_applied: false,
    };

    write_json(&cfg.out_dir.join("synchronization_report.json"), &report)?;
    write_json(&cfg.out_dir.join("coverage_report.json"), &coverage)?;
    write_json(&cfg.out_dir.join("timestamp_quality_report.json"), &quality)?;
    write_json(
        &cfg.out_dir
            .join("representative_synchronized_examples.json"),
        &examples,
    )?;
    fs::write(
        cfg.out_dir.join("schema.sql"),
        crate::schema_sql::MIGRATION_001_SQL,
    )?;
    store.checkpoint()?;
    Ok(report)
}

pub fn game_state_at_market_time(
    events: &[TimedEvent],
    t: DateTime<Utc>,
) -> Result<GameStateSnapshot, W5Error> {
    let window = crate::as_of::game_window(events);
    match as_of(events, t, window.as_ref()) {
        Ok(hit) => Ok(hit.matched.state_after),
        Err(crate::as_of::AsOfReject::NoPriorEvent { .. }) => {
            Err(W5Error::Timeline("BEFORE_FIRST_EVENT".into()))
        }
        Err(crate::as_of::AsOfReject::OutsideWindow { .. }) => {
            Err(W5Error::Timeline("AFTER_LAST_EVENT".into()))
        }
    }
}

fn median_i64(sorted: &[i64]) -> Option<i64> {
    if sorted.is_empty() {
        return None;
    }
    Some(sorted[(sorted.len() - 1) / 2])
}

fn percentile_i64(sorted: &[i64], p: usize) -> Option<i64> {
    if sorted.is_empty() {
        return None;
    }
    let idx = ((sorted.len() - 1) * p) / 100;
    Some(sorted[idx])
}

fn write_json(path: &Path, v: &impl Serialize) -> Result<(), W5Error> {
    fs::write(path, serde_json::to_vec_pretty(v)?)?;
    Ok(())
}
