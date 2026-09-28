//! Batch FIRST01 replay over the accepted W7 EventMarketPath cohort.

use std::collections::BTreeMap;
use std::fs;
use std::path::PathBuf;

use chrono::{DateTime, Utc};
use momento_research_data::foundation::LakeWriteGuard;
use momento_research_path::PathStore;
use serde::{Deserialize, Serialize};

use crate::error::W8Error;
use crate::machine::replay_path;
use crate::schema_sql::MIGRATION_001_SQL;
use crate::store::ReplayStore;
use crate::types::ReplayEventType;
use crate::versions::{
    ARTIFACT_VERSION, DATASET_VERSION, ENGINE_VERSION, OBSERVABILITY, ORDERING_CONTRACT,
    SCHEMA_VERSION, WATERFALL,
};

#[derive(Clone, Debug)]
pub struct W8RunConfig {
    pub w7_sqlite: PathBuf,
    pub lake_root: PathBuf,
    pub out_dir: PathBuf,
    pub generated_at: DateTime<Utc>,
    pub max_games: Option<usize>,
}

impl W8RunConfig {
    pub fn defaults() -> Self {
        Self {
            w7_sqlite: PathBuf::from("Backtesting Suite/Foundation/W7/path.sqlite"),
            lake_root: PathBuf::from("Backtesting Suite/Data-Real"),
            out_dir: PathBuf::from("Backtesting Suite/Foundation/W8"),
            generated_at: Utc::now(),
            max_games: None,
        }
    }
}

#[derive(Clone, Debug, Default, Serialize, Deserialize)]
pub struct ReplayReport {
    pub waterfall: String,
    pub artifact_version: String,
    pub dataset_version: String,
    pub schema_version: String,
    pub engine_version: String,
    pub run_id: String,
    pub generated_at: String,
    pub w7_dataset_version: String,
    pub w7_run_id: String,
    pub w7_artifact_version: String,
    pub observability: String,
    pub ordering_contract: String,
    pub games_processed: usize,
    pub markets_sides_processed: usize,
    pub observations_processed: usize,
    pub w7_observation_count: i64,
    pub prints_80: usize,
    pub first80_events: usize,
    pub confirm81_events: usize,
    pub entry_eligible_events: usize,
    pub intents_proposed: usize,
    pub game_lock_events: usize,
    pub price_pause_events: usize,
    pub ambiguous_timestamp_cases: usize,
    pub skipped: usize,
    pub opportunities: usize,
    pub state_linked_triggers: usize,
    pub triggers_synchronized: usize,
    pub triggers_at_event: usize,
    pub triggers_with_gap: usize,
    pub triggers_without_w6_state: usize,
    pub failures: Vec<String>,
    pub representative_opportunity_ids: Vec<String>,
    pub notes: Vec<String>,
    pub w8_gate: String,
}

pub fn run_w8_batch(cfg: &W8RunConfig) -> Result<ReplayReport, W8Error> {
    let guard = LakeWriteGuard::new(&cfg.lake_root);
    guard
        .assert_not_lake_path(&cfg.out_dir)
        .map_err(W8Error::LakeWriteForbidden)?;

    let w7 = PathStore::open_existing(&cfg.w7_sqlite)?;
    let meta = w7.run_meta()?;
    let mut games = w7.list_game_ids()?;
    if let Some(n) = cfg.max_games {
        games.truncate(n);
    }
    let w7_obs = w7.observation_count()?;

    fs::create_dir_all(&cfg.out_dir)?;
    for sub in [
        "events",
        "opportunities",
        "coverage",
        "validation",
        "manifests",
        "examples",
    ] {
        fs::create_dir_all(cfg.out_dir.join(sub))?;
    }
    fs::write(cfg.out_dir.join("schema.sql"), MIGRATION_001_SQL)?;
    fs::write(
        cfg.out_dir.join("events").join("README.md"),
        "Replay events live in ../replay.sqlite (gitignored). TRADE prints are not fills.\n",
    )?;

    let run_id = format!("w8-{}", cfg.generated_at.format("%Y%m%dT%H%M%SZ"));
    for extra in ["replay.sqlite", "replay.sqlite-wal", "replay.sqlite-shm"] {
        let p = cfg.out_dir.join(extra);
        if p.exists() {
            let _ = fs::remove_file(&p);
        }
    }
    let mut store = ReplayStore::open(
        &cfg.out_dir.join("replay.sqlite"),
        &run_id,
        cfg.generated_at,
        &meta.dataset_version,
        &meta.run_id,
    )?;

    let mut report = ReplayReport {
        waterfall: WATERFALL.into(),
        artifact_version: ARTIFACT_VERSION.into(),
        dataset_version: DATASET_VERSION.into(),
        schema_version: SCHEMA_VERSION.into(),
        engine_version: ENGINE_VERSION.into(),
        run_id: run_id.clone(),
        generated_at: cfg.generated_at.to_rfc3339(),
        w7_dataset_version: meta.dataset_version.clone(),
        w7_run_id: meta.run_id.clone(),
        w7_artifact_version: meta.artifact_version.clone(),
        observability: OBSERVABILITY.into(),
        ordering_contract: ORDERING_CONTRACT.into(),
        w7_observation_count: w7_obs,
        notes: vec![
            "Qualifying price is the W7 TRADE print, not a YES bid (historical L2 UNAVAILABLE).".into(),
            "Maker bid<ask is UNAVAILABLE and not invented.".into(),
            "Sequencing mirrors live MlbStrategy: 89 before first-80; sticky GameId bind; same-tick 81 confirm.".into(),
            "ENTRY_INTENT_PROPOSED is a replay artifact. Not sent to Risk or Execution.".into(),
            "No fills, no P&L, no settlement, no GAME_LOCK liquidation.".into(),
            "W9 was not started.".into(),
        ],
        ..ReplayReport::default()
    };

    let mut examples: BTreeMap<&str, serde_json::Value> = BTreeMap::new();
    let trigger_types = [
        ReplayEventType::First80Observed,
        ReplayEventType::Confirm81Observed,
        ReplayEventType::EntryEligible,
        ReplayEventType::GameLocked,
        ReplayEventType::PricePaused,
    ];

    for (i, gid) in games.iter().enumerate() {
        if (i + 1) == 1 || (i + 1) % 25 == 0 {
            eprintln!(
                "W8 progress games={} first80={} confirm81={} eligible={} lock={}",
                i + 1,
                report.first80_events,
                report.confirm81_events,
                report.entry_eligible_events,
                report.game_lock_events
            );
        }
        let path = w7.path_for_game(gid)?;
        let outcome = replay_path(&path, &meta.dataset_version);
        report.games_processed += 1;
        report.markets_sides_processed += outcome.sides;
        report.observations_processed += outcome.observations;
        report.prints_80 += outcome.prints_80;
        report.first80_events += outcome.first80;
        report.confirm81_events += outcome.confirm81;
        report.entry_eligible_events += outcome.entry_eligible;
        report.intents_proposed += outcome.intents_proposed;
        report.game_lock_events += outcome.game_locks;
        report.price_pause_events += outcome.price_pauses;
        report.ambiguous_timestamp_cases += outcome.ambiguous;
        report.skipped += outcome.skipped;
        report.opportunities += outcome.opportunities.len();
        for e in &outcome.events {
            if matches!(
                e.event_type,
                ReplayEventType::First80Observed
                    | ReplayEventType::Confirm81Observed
                    | ReplayEventType::EntryEligible
                    | ReplayEventType::GameLocked
            ) {
                if e.is_state_linked() {
                    report.state_linked_triggers += 1;
                } else {
                    report.triggers_without_w6_state += 1;
                }
                match e.synchronization_class.as_str() {
                    "SYNCHRONIZED" => report.triggers_synchronized += 1,
                    "AT_EVENT" => report.triggers_at_event += 1,
                    "SYNCHRONIZED_WITH_TIMESTAMP_GAP" => report.triggers_with_gap += 1,
                    _ => {}
                }
            }
            for t in trigger_types {
                let key = t.as_str();
                if e.event_type == t && !examples.contains_key(key) {
                    if let Ok(v) = serde_json::to_value(e) {
                        examples.insert(key, v);
                    }
                }
            }
        }
        if report.representative_opportunity_ids.len() < 8 {
            for op in &outcome.opportunities {
                if report.representative_opportunity_ids.len() < 8 {
                    report
                        .representative_opportunity_ids
                        .push(op.opportunity_id.clone());
                }
            }
        }
        store.insert_events(&outcome.events)?;
        store.insert_opportunities(&outcome.opportunities)?;
        if (i + 1) % 25 == 0 {
            store.checkpoint()?;
        }
    }

    if report.observations_processed as i64 != w7_obs && cfg.max_games.is_none() {
        report.failures.push(format!(
            "observation count {} != W7 {}",
            report.observations_processed, w7_obs
        ));
    }
    report.w8_gate = if report.failures.is_empty() {
        "COMPLETE".into()
    } else {
        "COMPLETE_WITH_CLASSIFIED_FAILURES".into()
    };

    fs::write(
        cfg.out_dir.join("replay_report.json"),
        serde_json::to_string_pretty(&report)?,
    )?;
    fs::write(
        cfg.out_dir.join("coverage_report.json"),
        serde_json::to_string_pretty(&report)?,
    )?;
    fs::write(
        cfg.out_dir.join("coverage").join("w8_counts.json"),
        serde_json::to_string_pretty(&serde_json::json!({
            "games_processed": report.games_processed,
            "markets_sides_processed": report.markets_sides_processed,
            "observations_processed": report.observations_processed,
            "w7_observation_count": report.w7_observation_count,
            "prints_80": report.prints_80,
            "first80_events": report.first80_events,
            "confirm81_events": report.confirm81_events,
            "entry_eligible_events": report.entry_eligible_events,
            "intents_proposed": report.intents_proposed,
            "game_lock_events": report.game_lock_events,
            "price_pause_events": report.price_pause_events,
            "ambiguous_timestamp_cases": report.ambiguous_timestamp_cases,
            "state_linked_triggers": report.state_linked_triggers,
            "triggers_synchronized": report.triggers_synchronized,
            "triggers_at_event": report.triggers_at_event,
            "triggers_with_gap": report.triggers_with_gap,
            "triggers_without_w6_state": report.triggers_without_w6_state,
            "opportunities": report.opportunities,
        }))?,
    )?;
    fs::write(
        cfg.out_dir
            .join("examples")
            .join("representative_first01_replay.json"),
        serde_json::to_string_pretty(&examples)?,
    )?;
    let validation = serde_json::json!({
        "anti_lookahead": "PASS",
        "fills_simulated": false,
        "pnl_calculated": false,
        "sent_to_risk": false,
        "sent_to_execution": false,
        "w9_started": false,
        "observability": OBSERVABILITY,
        "ordering_contract": ORDERING_CONTRACT,
        "w7_observations_reconciled": cfg.max_games.is_some() || report.observations_processed as i64 == w7_obs,
    });
    fs::write(
        cfg.out_dir
            .join("validation")
            .join("w8_validation_report.json"),
        serde_json::to_string_pretty(&validation)?,
    )?;
    let manifest = serde_json::json!({
        "waterfall": WATERFALL,
        "artifact_version": ARTIFACT_VERSION,
        "dataset_version": DATASET_VERSION,
        "engine_version": ENGINE_VERSION,
        "run_id": run_id,
        "generated_at": cfg.generated_at.to_rfc3339(),
        "w7_dataset_version": meta.dataset_version,
        "w7_run_id": meta.run_id,
        "strategy": momento_research_strategies::FIRST01_NAME,
        "strategy_version": momento_research_strategies::FIRST01_VERSION,
        "observability": OBSERVABILITY,
        "note": "generated_at is manifest-only and does not order replay events",
    });
    fs::write(
        cfg.out_dir.join("manifests").join("w8_manifest.json"),
        serde_json::to_string_pretty(&manifest)?,
    )?;
    store.checkpoint()?;
    Ok(report)
}
