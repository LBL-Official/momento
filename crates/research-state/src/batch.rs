//! Reconstruct every available StatsAPI PBP landing envelope. No Kalshi network.

use std::collections::{BTreeMap, BTreeSet, HashSet};
use std::fs;
use std::path::{Path, PathBuf};

use chrono::{DateTime, Utc};
use momento_research_data::foundation::LakeWriteGuard;
use momento_research_event::event::MlbEventType;
use momento_research_ingest::paths::IngestPaths;
use serde::{Deserialize, Serialize};

use crate::engine::reconstruct_envelope;
use crate::error::W6Error;
use crate::fingerprint::event_type_token;
use crate::schema_sql::MIGRATION_001_SQL;
use crate::store::StateStore;
use crate::types::ValidationFailure;
use crate::validate::to_failure;
use crate::versions::{
    ARTIFACT_VERSION, DATASET_VERSION, RECONSTRUCTION_VERSION, SCHEMA_VERSION, WATERFALL,
};

#[derive(Clone, Debug)]
pub struct W6RunConfig {
    pub ingest_root: PathBuf,
    pub lake_root: PathBuf,
    pub out_dir: PathBuf,
    pub pairs: PathBuf,
    pub generated_at: DateTime<Utc>,
    pub max_games: Option<usize>,
}

impl W6RunConfig {
    pub fn defaults() -> Self {
        Self {
            ingest_root: PathBuf::from("Backtesting Suite/Foundation/Ingest"),
            lake_root: PathBuf::from("Backtesting Suite/Data-Real"),
            out_dir: PathBuf::from("Backtesting Suite/Foundation/W6"),
            pairs: PathBuf::from(
                "Backtesting Suite/Foundation/Ingest/runs/ingest-20260826T095038Z-2bc3d10b5833/game_market_pairs.json",
            ),
            generated_at: Utc::now(),
            max_games: None,
        }
    }
}

#[derive(Clone, Debug, Default, Serialize, Deserialize)]
pub struct ReconstructionReport {
    pub waterfall: String,
    pub artifact_version: String,
    pub dataset_version: String,
    pub schema_version: String,
    pub reconstruction_version: String,
    pub run_id: String,
    pub generated_at: String,
    pub games_discovered: usize,
    pub games_processed: usize,
    pub games_successful: usize,
    pub games_failed: usize,
    pub w5_mapped_games_in_pairs: usize,
    pub w5_mapped_games_reconstructed: usize,
    pub events: usize,
    pub states: usize,
    pub transitions: usize,
    pub timed_events: usize,
    pub extra_innings: usize,
    pub walk_offs: usize,
    pub substitutions: usize,
    pub reviews: usize,
    pub delays: usize,
    pub amendments: usize,
    pub missing_timestamp_events: usize,
    pub missing_batter: usize,
    pub missing_pitcher: usize,
    pub missing_count: usize,
    pub missing_runner_identity_occupied: usize,
    pub validation_pass: usize,
    pub validation_fail: usize,
    pub event_types: BTreeMap<String, usize>,
    pub failures: Vec<ValidationFailure>,
    pub notes: Vec<String>,
    pub w6_gate: String,
}

pub fn run_w6_batch(cfg: &W6RunConfig) -> Result<ReconstructionReport, W6Error> {
    let guard = LakeWriteGuard::new(&cfg.lake_root);
    guard
        .assert_not_lake_path(&cfg.out_dir)
        .map_err(W6Error::LakeWriteForbidden)?;

    let ingest = IngestPaths::new(&cfg.ingest_root);
    let landing = ingest.root.join("landing").join("mlb_statsapi");
    let mut envelopes = list_envelopes(&landing);
    envelopes.sort();
    if let Some(n) = cfg.max_games {
        envelopes.truncate(n);
    }

    let mapped_pks = load_mapped_pks(&cfg.pairs);

    fs::create_dir_all(&cfg.out_dir)?;
    for sub in [
        "game_states",
        "state_transitions",
        "validation",
        "manifests",
    ] {
        fs::create_dir_all(cfg.out_dir.join(sub))?;
    }
    fs::write(cfg.out_dir.join("schema.sql"), MIGRATION_001_SQL)?;
    fs::write(
        cfg.out_dir.join("game_states").join("README.md"),
        "Canonical game states live in ../state.sqlite (gitignored). This directory holds schema and indexes only.\n",
    )?;
    fs::write(
        cfg.out_dir.join("state_transitions").join("README.md"),
        "Canonical transitions live in ../state.sqlite (gitignored). Do not attach market prices here.\n",
    )?;

    let run_id = format!("w6-{}", cfg.generated_at.format("%Y%m%dT%H%M%SZ"));
    for extra in ["state.sqlite", "state.sqlite-wal", "state.sqlite-shm"] {
        let p = cfg.out_dir.join(extra);
        if p.exists() {
            let _ = fs::remove_file(&p);
        }
    }
    let mut store = StateStore::open(&cfg.out_dir.join("state.sqlite"), &run_id, cfg.generated_at)?;

    let mut report = ReconstructionReport {
        waterfall: WATERFALL.into(),
        artifact_version: ARTIFACT_VERSION.into(),
        dataset_version: DATASET_VERSION.into(),
        schema_version: SCHEMA_VERSION.into(),
        reconstruction_version: RECONSTRUCTION_VERSION.into(),
        run_id: run_id.clone(),
        generated_at: cfg.generated_at.to_rfc3339(),
        games_discovered: envelopes.len(),
        notes: vec![
            "Play-level StatsAPI PBP: pitch-level count transitions are UNAVAILABLE unless a pitch event exists.".into(),
            "Handedness and batting-order slot are UNAVAILABLE in this source.".into(),
            "Game remaining time is UNAVAILABLE (would require lookahead).".into(),
            "W6 does not attach Kalshi prices. Join keys are GameId + timestamp + state_seq + state_id.".into(),
        ],
        ..ReconstructionReport::default()
    };
    report.waterfall = WATERFALL.into();
    report.artifact_version = ARTIFACT_VERSION.into();
    report.dataset_version = DATASET_VERSION.into();
    report.schema_version = SCHEMA_VERSION.into();
    report.reconstruction_version = RECONSTRUCTION_VERSION.into();
    report.run_id = run_id;
    report.generated_at = cfg.generated_at.to_rfc3339();
    report.games_discovered = envelopes.len();
    report.w5_mapped_games_in_pairs = mapped_pks.len();

    let mut seen_ids = HashSet::new();
    let mut index = Vec::new();
    let mut sample: Option<serde_json::Value> = None;

    for path in &envelopes {
        report.games_processed += 1;
        let pk = game_pk_from_path(path).unwrap_or_default();
        if report.games_processed == 1 || report.games_processed % 25 == 0 {
            eprintln!(
                "w6-reconstruct {}/{} gamePk={}",
                report.games_processed,
                envelopes.len(),
                pk
            );
        }
        match reconstruct_envelope(path) {
            Ok(game) => {
                if !seen_ids.insert(game.game_id.clone()) {
                    let err = format!("duplicate GameId {}", game.game_id);
                    report.games_failed += 1;
                    report.validation_fail += 1;
                    report.failures.push(ValidationFailure {
                        game_id: game.game_id.clone(),
                        event_id: String::new(),
                        sequence: 0,
                        state_before_id: None,
                        event_type: String::new(),
                        attempted_state_id: None,
                        code: "GAME_ID_UNIQUENESS".into(),
                        reason: err.clone(),
                    });
                    store.insert_failure(&game.game_id, &pk, &err)?;
                    continue;
                }
                store.insert_game(&game, "OK", None)?;
                report.games_successful += 1;
                report.validation_pass += 1;
                report.events += game.events_total;
                report.states += game.states.len();
                report.transitions += game.transitions.len();
                report.timed_events += game.timed_events;
                report.extra_innings += usize::from(game.extra_inning);
                report.walk_offs += usize::from(game.walk_off);
                if mapped_pks.contains(&game.game_pk) {
                    report.w5_mapped_games_reconstructed += 1;
                }
                for t in &game.transitions {
                    *report
                        .event_types
                        .entry(event_type_token(t.event_type).to_string())
                        .or_default() += 1;
                    report.substitutions += usize::from(t.substitution);
                    report.reviews += usize::from(t.review);
                    report.delays += usize::from(t.delay);
                    report.amendments += usize::from(t.amendment);
                    if matches!(
                        t.event_type,
                        MlbEventType::PitchingChange
                            | MlbEventType::BattingChange
                            | MlbEventType::Substitution
                    ) {
                        // already counted via substitution flag
                    }
                }
                for s in &game.states {
                    let playable = s.state_seq > 0
                        && s.event_type.is_some_and(|t| t != MlbEventType::GameStart);
                    if playable && s.canonical_timestamp.is_unavailable() {
                        report.missing_timestamp_events += 1;
                    }
                    if playable && s.batter_id.is_unavailable() {
                        report.missing_batter += 1;
                    }
                    if playable && s.pitcher_id.is_unavailable() {
                        report.missing_pitcher += 1;
                    }
                    if playable && (s.balls.is_unavailable() || s.strikes.is_unavailable()) {
                        report.missing_count += 1;
                    }
                    for slot in [&s.runner_first, &s.runner_second, &s.runner_third] {
                        if let Some(Some(id)) = slot.as_value() {
                            if id.is_empty() {
                                report.missing_runner_identity_occupied += 1;
                            }
                        }
                    }
                }
                index.push(serde_json::json!({
                    "game_id": game.game_id,
                    "game_pk": game.game_pk,
                    "events": game.events_total,
                    "states": game.states.len(),
                    "transitions": game.transitions.len(),
                    "final_fingerprint": game.states.last().map(|s| s.fingerprint.clone()),
                    "extra_inning": game.extra_inning,
                    "walk_off": game.walk_off,
                    "terminal": game.terminal,
                }));
                if sample.is_none() {
                    if let Some(last) = game.states.last() {
                        sample = Some(serde_json::to_value(last)?);
                    }
                }
            }
            Err(e) => {
                report.games_failed += 1;
                report.validation_fail += 1;
                let fail = to_failure(&e, None, None);
                let mut fail = fail;
                if fail.game_id.is_empty() {
                    fail.game_id = pk.clone();
                }
                report.failures.push(fail);
                store.insert_failure(&pk, &pk, &e.to_string())?;
            }
        }
    }

    report.w6_gate = if report.games_successful > 0 && report.games_failed == 0 {
        "COMPLETE".into()
    } else if report.games_successful > 0 {
        "COMPLETE_WITH_FAILURES".into()
    } else if report.games_discovered == 0 {
        "COMPLETE_NO_PBP_LANDING".into()
    } else {
        "FAILED".into()
    };

    let index_path = cfg.out_dir.join("game_states").join("game_index.jsonl");
    let mut body = String::new();
    for row in &index {
        body.push_str(&serde_json::to_string(row)?);
        body.push('\n');
    }
    fs::write(index_path, body)?;
    if let Some(s) = sample {
        fs::write(
            cfg.out_dir.join("game_states").join("sample_state.json"),
            serde_json::to_vec_pretty(&s)?,
        )?;
    }
    fs::write(
        cfg.out_dir
            .join("validation")
            .join("w6_validation_report.json"),
        serde_json::to_vec_pretty(&report)?,
    )?;
    let manifest = serde_json::json!({
        "waterfall": WATERFALL,
        "source_dataset": "mlb_statsapi landing envelopes",
        "source_version": "W3 ingest / PARSER_VERSION on events",
        "games_discovered": report.games_discovered,
        "games_successful": report.games_successful,
        "games_failed": report.games_failed,
        "events": report.events,
        "states": report.states,
        "transitions": report.transitions,
        "validation_pass": report.validation_pass,
        "validation_fail": report.validation_fail,
        "reconstruction_version": RECONSTRUCTION_VERSION,
        "schema_version": SCHEMA_VERSION,
        "generation_timestamp": report.generated_at,
        "generation_timestamp_note": "manifest only; never part of state identity",
        "w6_gate": report.w6_gate,
    });
    fs::write(
        cfg.out_dir.join("manifests").join("w6_manifest.json"),
        serde_json::to_vec_pretty(&manifest)?,
    )?;
    fs::write(
        cfg.out_dir.join("reconstruction_report.json"),
        serde_json::to_vec_pretty(&report)?,
    )?;
    store.checkpoint()?;
    Ok(report)
}

fn load_mapped_pks(pairs: &Path) -> BTreeSet<String> {
    let Ok(bytes) = fs::read(pairs) else {
        return BTreeSet::new();
    };
    let Ok(v) = serde_json::from_slice::<Vec<serde_json::Value>>(&bytes) else {
        return BTreeSet::new();
    };
    let mut out = BTreeSet::new();
    for p in v {
        let mapping = p.get("mapping").and_then(|x| x.as_str()).unwrap_or("");
        if mapping != "MAPPED" && mapping != "Mapped" {
            continue;
        }
        if let Some(pk) = p.get("game_pk").and_then(|x| x.as_str()) {
            if !pk.is_empty() {
                out.insert(pk.to_string());
            }
        }
    }
    out
}

fn list_envelopes(root: &Path) -> Vec<PathBuf> {
    let mut out = Vec::new();
    walk(root, &mut out);
    out
}

fn walk(dir: &Path, out: &mut Vec<PathBuf>) {
    let Ok(entries) = fs::read_dir(dir) else {
        return;
    };
    for ent in entries.flatten() {
        let p = ent.path();
        if p.is_dir() {
            walk(&p, out);
        } else if p
            .file_name()
            .and_then(|n| n.to_str())
            .is_some_and(|n| n.ends_with(".envelope.json"))
        {
            out.push(p);
        }
    }
}

fn game_pk_from_path(path: &Path) -> Option<String> {
    let name = path.file_name()?.to_str()?;
    let rest = name
        .strip_prefix("gamePk=")?
        .strip_suffix(".envelope.json")?;
    Some(rest.to_string())
}
