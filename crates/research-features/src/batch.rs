//! Batch B1 extraction over accepted W8 entries.

use std::collections::BTreeMap;
use std::fs;
use std::path::PathBuf;

use chrono::{DateTime, Utc};
use momento_research_data::foundation::LakeWriteGuard;
use momento_research_path::PathStore;
use momento_research_state::StateStore;
use serde::{Deserialize, Serialize};

use crate::analysis::{a1_bucket_matrix, condition_report, settlement_return_cents};
use crate::dataset::extract_snapshot;
use crate::dictionary::feature_dictionary;
use crate::error::B1Error;
use crate::identity::load_envelope_identity;
use crate::normalization::attach_train_conditioned_z;
use crate::schema_sql::MIGRATION_001_SQL;
use crate::store::{FeatureStore, load_w6_game_meta, load_w8_entries, w8_entry_count, w8_run_id};
use crate::types::B1EntrySnapshot;
use crate::validation::validate_batch;
use crate::versions::{
    ARTIFACT_VERSION, DATASET_VERSION, ENGINE_VERSION, FEATURE_SCHEMA_VERSION, OBSERVABILITY,
    SCHEMA_VERSION, WATERFALL,
};

#[derive(Clone, Debug)]
pub struct B1RunConfig {
    pub w8_sqlite: PathBuf,
    pub w7_sqlite: PathBuf,
    pub w6_sqlite: PathBuf,
    pub lake_root: PathBuf,
    pub identity_landing: PathBuf,
    pub out_dir: PathBuf,
    pub generated_at: DateTime<Utc>,
    pub max_entries: Option<usize>,
}

impl B1RunConfig {
    pub fn defaults() -> Self {
        Self {
            w8_sqlite: PathBuf::from("Backtesting Suite/Foundation/W8/replay.sqlite"),
            w7_sqlite: PathBuf::from("Backtesting Suite/Foundation/W7/path.sqlite"),
            w6_sqlite: PathBuf::from("Backtesting Suite/Foundation/W6/state.sqlite"),
            lake_root: PathBuf::from("Backtesting Suite/Data-Real"),
            identity_landing: PathBuf::from(
                "Backtesting Suite/Foundation/Ingest/landing/mlb_statsapi",
            ),
            out_dir: PathBuf::from("Backtesting Suite/Foundation/B1"),
            generated_at: Utc::now(),
            max_entries: None,
        }
    }
}

#[derive(Clone, Debug, Default, Serialize, Deserialize)]
pub struct FeatureReport {
    pub waterfall: String,
    pub artifact_version: String,
    pub dataset_version: String,
    pub schema_version: String,
    pub engine_version: String,
    pub feature_schema_version: String,
    pub run_id: String,
    pub generated_at: String,
    pub w6_run_id: String,
    pub w7_run_id: String,
    pub w8_run_id: String,
    pub observability: String,
    pub w8_entries: usize,
    pub snapshots_written: usize,
    pub unique_games: usize,
    pub notes: Vec<String>,
    pub b1_gate: String,
}

pub fn run_b1_batch(cfg: &B1RunConfig) -> Result<FeatureReport, B1Error> {
    let guard = LakeWriteGuard::new(&cfg.lake_root);
    guard
        .assert_not_lake_path(&cfg.out_dir)
        .map_err(B1Error::LakeWriteForbidden)?;

    let w7 = PathStore::open_existing(&cfg.w7_sqlite)?;
    let w6 = StateStore::open_existing(&cfg.w6_sqlite)?;
    let w7_meta = w7.run_meta()?;
    let w8_id = w8_run_id(&cfg.w8_sqlite)?;
    let mut entries = load_w8_entries(&cfg.w8_sqlite)?;
    let w8_n = w8_entry_count(&cfg.w8_sqlite)? as usize;
    if let Some(n) = cfg.max_entries {
        entries.truncate(n);
    }

    fs::create_dir_all(&cfg.out_dir)?;
    for extra in [
        "features.sqlite",
        "features.sqlite-wal",
        "features.sqlite-shm",
    ] {
        let p = cfg.out_dir.join(extra);
        if p.exists() {
            let _ = fs::remove_file(&p);
        }
    }
    fs::write(cfg.out_dir.join("schema.sql"), MIGRATION_001_SQL)?;

    let run_id = format!("b1-{}", cfg.generated_at.format("%Y%m%dT%H%M%SZ"));
    let store = FeatureStore::open(
        &cfg.out_dir.join("features.sqlite"),
        &run_id,
        cfg.generated_at,
        w6.run_id(),
        &w7_meta.run_id,
        &w8_id,
        Some(&w7_meta.w5_dataset_version),
    )?;

    let identity = load_envelope_identity(&cfg.identity_landing);
    let mut snapshots = Vec::new();
    let n_planned = entries.len();
    for (i, mut entry) in entries.into_iter().enumerate() {
        let (date, pk, status) = load_w6_game_meta(&cfg.w6_sqlite, &entry.game_id)?;
        entry.official_date = date;
        entry.game_pk = pk.clone();
        entry.game_status = status;
        let path = w7.path_for_game(&entry.game_id)?;
        let states = w6.load_states(&entry.game_id)?;
        let transitions = w6.load_transitions(&entry.game_id)?;
        let ident = pk.as_ref().and_then(|p| identity.get(p));
        snapshots.push(extract_snapshot(
            &entry,
            &path,
            &states,
            &transitions,
            ident,
        ));
        if (i + 1) % 25 == 0 || i + 1 == n_planned {
            eprintln!("b1 extract {}/{} games", i + 1, n_planned);
        }
    }
    attach_train_conditioned_z(&mut snapshots);
    for (i, snap) in snapshots.iter().enumerate() {
        crate::validation::validate_snapshot(snap)?;
        store.insert_snapshot(snap)?;
        if (i + 1) % 25 == 0 {
            store.checkpoint()?;
        }
    }
    store.checkpoint()?;

    let validation = validate_batch(&snapshots, w8_n)?;
    write_artifacts(
        cfg,
        &run_id,
        &snapshots,
        &validation,
        w6.run_id(),
        &w7_meta.run_id,
        &w8_id,
    )?;

    Ok(FeatureReport {
        waterfall: WATERFALL.into(),
        artifact_version: ARTIFACT_VERSION.into(),
        dataset_version: DATASET_VERSION.into(),
        schema_version: SCHEMA_VERSION.into(),
        engine_version: ENGINE_VERSION.into(),
        feature_schema_version: FEATURE_SCHEMA_VERSION.into(),
        run_id,
        generated_at: cfg.generated_at.to_rfc3339(),
        w6_run_id: w6.run_id().to_string(),
        w7_run_id: w7_meta.run_id,
        w8_run_id: w8_id,
        observability: OBSERVABILITY.into(),
        w8_entries: w8_n,
        snapshots_written: snapshots.len(),
        unique_games: validation.unique_games,
        notes: vec![
            "Observational TRADE entry. Not a demonstrated maker fill.".into(),
            "Historical L2 UNAVAILABLE. Bid/ask/OBI/OFI/depth not invented.".into(),
            "A1 entry/exit buckets are research targets, not live parameter changes.".into(),
            "One primary W8 entry per game.".into(),
            "Settlement is W6. Fair value reserved (no label leak).".into(),
            "W9 / live 80/81/83/89 / 50% stop unchanged.".into(),
        ],
        b1_gate: validation.gate,
    })
}

fn write_artifacts(
    cfg: &B1RunConfig,
    run_id: &str,
    snapshots: &[B1EntrySnapshot],
    validation: &crate::validation::ValidationReport,
    w6: &str,
    w7: &str,
    w8: &str,
) -> Result<(), B1Error> {
    fs::write(
        cfg.out_dir.join("validation_report.json"),
        serde_json::to_string_pretty(validation)?,
    )?;
    fs::write(
        cfg.out_dir.join("feature_dictionary.json"),
        serde_json::to_string_pretty(&feature_dictionary())?,
    )?;
    let baseline = condition_report(
        snapshots,
        "ALL_PRIMARY_80_83",
        |_| true,
        settlement_return_cents,
    );
    let late_lead = condition_report(
        snapshots,
        "LATE_INN_6_9_LEAD_GE2",
        |s| {
            s.baseball.inning.is_some_and(|i| (6..=9).contains(&i))
                && s.baseball.bound_team_lead.is_some_and(|l| l >= 2)
        },
        settlement_return_cents,
    );
    let a1 = a1_bucket_matrix(snapshots);
    fs::write(
        cfg.out_dir.join("coverage_report.json"),
        serde_json::to_string_pretty(&serde_json::json!({
            "run_id": run_id,
            "n_entries": snapshots.len(),
            "n_unique_games": validation.unique_games,
            "baseline": baseline,
            "late_lead_ge2": late_lead,
            "note": "Conditional means are descriptive. Not a trading rule. Report N_games."
        }))?,
    )?;
    fs::write(
        cfg.out_dir.join("a1_bucket_report.json"),
        serde_json::to_string_pretty(&serde_json::json!({
            "run_id": run_id,
            "entry_band": crate::versions::A1_DEFAULT_ENTRY_BAND,
            "independence_unit": "GAME",
            "observability": "TRADE_PRINT_NOT_FILL",
            "cells": a1,
            "note": "A1 entry × A1 exit × coarse feature condition. Positive EV is not a trading rule."
        }))?,
    )?;
    let mut examples = BTreeMap::new();
    if let Some(a) = snapshots.iter().find(|s| {
        s.starting_market
            .p_start_cents
            .is_some_and(|p| (50..=60).contains(&p))
            && s.entry_trade_price_cents >= 80
    }) {
        examples.insert("smooth_start_near_50", example_view(a));
    }
    if let Some(b) = snapshots.iter().find(|s| {
        s.starting_market.p_start_cents.is_some_and(|p| p < 50)
            && s.market_history.reversal_count.is_some_and(|r| r >= 3)
    }) {
        examples.insert("volatile_underdog_path", example_view(b));
    }
    if examples.is_empty() {
        if let Some(s) = snapshots.first() {
            examples.insert("first_snapshot", example_view(s));
        }
    }
    fs::write(
        cfg.out_dir.join("representative_examples.json"),
        serde_json::to_string_pretty(&examples)?,
    )?;
    fs::write(
        cfg.out_dir.join("manifest.json"),
        serde_json::to_string_pretty(&serde_json::json!({
            "run_id": run_id,
            "dataset_version": DATASET_VERSION,
            "w6_run_id": w6,
            "w7_run_id": w7,
            "w8_run_id": w8,
            "feature_schema_version": FEATURE_SCHEMA_VERSION,
            "engine_version": ENGINE_VERSION,
            "generated_at": cfg.generated_at.to_rfc3339(),
            "observability": OBSERVABILITY,
            "note": "generated_at is manifest-only and never used for ordering"
        }))?,
    )?;
    fs::write(
        cfg.out_dir.join("README.md"),
        "B1 observational feature store. features.sqlite is gitignored. TRADE != fill. L2 = UNAVAILABLE.\n",
    )?;
    Ok(())
}

fn example_view(s: &B1EntrySnapshot) -> serde_json::Value {
    serde_json::json!({
        "snapshot_id": s.snapshot_id,
        "game_id": s.game_id,
        "side": s.contract_side,
        "inning": s.baseball.inning,
        "bound_team_lead": s.baseball.bound_team_lead,
        "regime": s.baseball.regime.as_str(),
        "p_start": s.starting_market.p_start_cents,
        "start_sentiment": s.starting_market.start_sentiment.as_str(),
        "p_entry": s.entry_trade_price_cents,
        "a1_entry_target": s.a1_targets.entry_target.as_str(),
        "d80_trade_cents": s.current_market.d80_trade_cents,
        "start_to_entry_move": s.market_history.start_to_entry_move_cents,
        "path_distance": s.market_history.path_distance_cents,
        "path_efficiency_bps": s.market_history.path_efficiency_bps,
        "reversal_count": s.market_history.reversal_count,
        "volatility_5m": s.market_history.volatility_5m_cents,
        "settlement": s.outcomes.settlement.as_str(),
        "future_return_5m": s.outcomes.future_5m.return_cents,
        "L2": "UNAVAILABLE"
    })
}
