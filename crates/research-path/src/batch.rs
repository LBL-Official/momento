//! Batch EventMarketPath builder over the accepted W5 ∩ W6 cohort.

use std::collections::{BTreeSet, HashSet};
use std::fs;
use std::path::PathBuf;

use chrono::{DateTime, Utc};
use momento_research_data::foundation::LakeWriteGuard;
use momento_research_state::StateStore;
use momento_research_sync::SyncStore;
use serde::{Deserialize, Serialize};

use crate::causal::{assemble_paths, state_segments};
use crate::error::W7Error;
use crate::join::{W6Index, join_observation, path_id};
use crate::schema_sql::MIGRATION_001_SQL;
use crate::store::PathStore;
use crate::types::{GamePathCoverage, PathJoinStatus, PathObservation, occupancy_label};
use crate::versions::{
    ARTIFACT_VERSION, CAUSAL_VERSION, DATASET_VERSION, JOIN_VERSION, SCHEMA_VERSION, WATERFALL,
};

#[derive(Clone, Debug)]
pub struct W7RunConfig {
    pub w5_sqlite: PathBuf,
    pub w6_sqlite: PathBuf,
    pub lake_root: PathBuf,
    pub out_dir: PathBuf,
    pub generated_at: DateTime<Utc>,
    pub max_games: Option<usize>,
}

impl W7RunConfig {
    pub fn defaults() -> Self {
        Self {
            w5_sqlite: PathBuf::from("Backtesting Suite/Foundation/W5/sync.sqlite"),
            w6_sqlite: PathBuf::from("Backtesting Suite/Foundation/W6/state.sqlite"),
            lake_root: PathBuf::from("Backtesting Suite/Data-Real"),
            out_dir: PathBuf::from("Backtesting Suite/Foundation/W7"),
            generated_at: Utc::now(),
            max_games: None,
        }
    }
}

#[derive(Clone, Debug, Default, Serialize, Deserialize)]
pub struct PathReport {
    pub waterfall: String,
    pub artifact_version: String,
    pub dataset_version: String,
    pub schema_version: String,
    pub join_version: String,
    pub causal_version: String,
    pub run_id: String,
    pub generated_at: String,
    pub w5_dataset_version: String,
    pub w5_artifact_version: String,
    pub w5_run_id: String,
    pub w6_dataset_version: String,
    pub w6_reconstruction_version: String,
    pub w6_run_id: String,
    pub games_attempted: usize,
    pub games_with_w5_synchronized_observations: usize,
    pub games_with_zero_synchronized_observations: usize,
    pub games_w5_without_w6: usize,
    pub games_w6_ok_without_w5: usize,
    pub markets_attempted: usize,
    pub contract_sides_attempted: usize,
    pub contract_sides_with_synchronized_observations: usize,
    pub total_market_observations: usize,
    pub synchronized_observations: usize,
    pub observations_synchronized: usize,
    pub observations_at_event: usize,
    pub observations_synchronized_with_timestamp_gap: usize,
    pub observations_before_first_event: usize,
    pub observations_after_last_event: usize,
    pub observations_no_game_state: usize,
    pub observations_unjoinable: usize,
    pub observations_unsynchronizable: usize,
    pub observations_rejected: usize,
    pub observations_validation_failure: usize,
    pub games_with_complete_state_coverage: usize,
    pub games_with_partial_state_coverage: usize,
    pub games_with_no_usable_synchronized_path: usize,
    pub paths_written: usize,
    pub observations_price_equals_80: usize,
    pub failures: Vec<String>,
    pub representative_path_ids: Vec<String>,
    pub notes: Vec<String>,
    pub w7_gate: String,
}

#[derive(Clone, Debug, Default, Serialize, Deserialize)]
struct GameCoverageRow {
    game_id: String,
    game_pk: String,
    observations: usize,
    synchronized: usize,
    before_first: usize,
    after_last: usize,
    at_event: usize,
    with_gap: usize,
    no_game_state: usize,
    w6_timed_states: usize,
    w6_states_with_observations: usize,
    coverage: String,
}

#[derive(Clone, Debug, Default, Serialize, Deserialize)]
struct MarketCoverageRow {
    game_id: String,
    market_id: String,
    contract_side: String,
    observations: usize,
    synchronized: usize,
    before_first: usize,
    after_last: usize,
    at_event: usize,
    with_gap: usize,
}

pub fn run_w7_batch(cfg: &W7RunConfig) -> Result<PathReport, W7Error> {
    let guard = LakeWriteGuard::new(&cfg.lake_root);
    guard
        .assert_not_lake_path(&cfg.out_dir)
        .map_err(W7Error::LakeWriteForbidden)?;

    let w5 = SyncStore::open_existing(&cfg.w5_sqlite)?;
    let w6 = StateStore::open_existing(&cfg.w6_sqlite)?;
    let w5_ver = w5.dataset_version()?;
    let w6_ver = w6.dataset_version()?;
    let w5_art = w5.artifact_version()?;
    let w6_recon = w6.reconstruction_version()?;

    fs::create_dir_all(&cfg.out_dir)?;
    for sub in ["paths", "coverage", "validation", "manifests", "examples"] {
        fs::create_dir_all(cfg.out_dir.join(sub))?;
    }
    fs::write(cfg.out_dir.join("schema.sql"), MIGRATION_001_SQL)?;
    fs::write(
        cfg.out_dir.join("paths").join("README.md"),
        "EventMarketPath rows live in ../path.sqlite (gitignored). TRADE observations remain TRADE.\n",
    )?;

    let mut w5_games = w5.list_games()?;
    w5_games.sort();
    w5_games.dedup();
    let w6_ok: HashSet<String> = w6.list_ok_game_ids()?.into_iter().collect();
    let w5_ids: HashSet<String> = w5_games.iter().map(|(g, _)| g.clone()).collect();

    let mut overlap: Vec<(String, String)> = w5_games
        .iter()
        .filter(|(gid, _)| w6_ok.contains(gid))
        .cloned()
        .collect();
    overlap.sort();
    if let Some(n) = cfg.max_games {
        overlap.truncate(n);
    }

    let run_id = format!("w7-{}", cfg.generated_at.format("%Y%m%dT%H%M%SZ"));
    for extra in ["path.sqlite", "path.sqlite-wal", "path.sqlite-shm"] {
        let p = cfg.out_dir.join(extra);
        if p.exists() {
            let _ = fs::remove_file(&p);
        }
    }
    let mut store = PathStore::open(
        &cfg.out_dir.join("path.sqlite"),
        &run_id,
        cfg.generated_at,
        &w5_ver,
        &w6_ver,
    )?;

    let mut report = PathReport {
        waterfall: WATERFALL.into(),
        artifact_version: ARTIFACT_VERSION.into(),
        dataset_version: DATASET_VERSION.into(),
        schema_version: SCHEMA_VERSION.into(),
        join_version: JOIN_VERSION.into(),
        causal_version: CAUSAL_VERSION.into(),
        run_id: run_id.clone(),
        generated_at: cfg.generated_at.to_rfc3339(),
        w5_dataset_version: w5_ver.clone(),
        w5_artifact_version: w5_art,
        w5_run_id: w5.run_id().to_string(),
        w6_dataset_version: w6_ver.clone(),
        w6_reconstruction_version: w6_recon,
        w6_run_id: w6.run_id().to_string(),
        games_w5_without_w6: w5_ids.difference(&w6_ok).count(),
        games_w6_ok_without_w5: w6_ok.difference(&w5_ids).count(),
        notes: vec![
            "W5 remains authoritative for AS-OF classification.".into(),
            "W6 remains authoritative for canonical MLB state.".into(),
            "TRADE observations remain TRADE. No bid/ask/mid/open/close is inferred.".into(),
            "Trade size is UNAVAILABLE because W5 sqlite did not persist quantity.".into(),
            "Causal descriptors use only observations at or before T on the same contract side."
                .into(),
            "BEFORE_FIRST_EVENT and AFTER_LAST_EVENT are retained without an applicable W6 state."
                .into(),
            "80-cent query is observational print matching, not FIRST01 replay.".into(),
            "W8 was not started.".into(),
        ],
        ..PathReport::default()
    };

    let mut examples = ExampleSet::default();
    let mut game_cov_out = Vec::new();
    let mut market_cov_out = Vec::new();
    let mut path_ids = Vec::new();

    for (game_id, game_pk) in &overlap {
        report.games_attempted += 1;
        if report.games_attempted == 1 || report.games_attempted % 25 == 0 {
            eprintln!(
                "W7 progress games={} synced={} before_first={} after_last={}",
                report.games_attempted,
                report.observations_synchronized
                    + report.observations_at_event
                    + report.observations_synchronized_with_timestamp_gap,
                report.observations_before_first_event,
                report.observations_after_last_event
            );
        }
        let states = w6.load_states(game_id)?;
        let transitions = w6.load_transitions(game_id)?;
        let timed_state_ids: BTreeSet<String> = states
            .iter()
            .filter(|s| s.event_id.is_some())
            .map(|s| s.state_id.clone())
            .collect();
        let idx = W6Index::from_rows(game_id, states, transitions);
        let w5_rows = w5.observations_for_game(game_id)?;
        let mut joined = Vec::with_capacity(w5_rows.len());
        for obs in &w5_rows {
            let pid = path_id(
                &obs.game_id,
                &obs.market_id,
                &obs.contract_side,
                &w5_ver,
                &w6_ver,
            );
            match join_observation(obs, Some(&idx), &pid, &w5_ver, &w6_ver) {
                Ok(row) => joined.push(row),
                Err(e) => {
                    report
                        .failures
                        .push(format!("{game_id} {}: {e}", obs.observation_id));
                    report.observations_validation_failure += 1;
                }
            }
        }

        let paths = assemble_paths(joined);
        let mut game_obs = Vec::new();
        let mut covered_states: HashSet<String> = HashSet::new();
        for path in &paths {
            let segs = state_segments(&path.path_id, &path.observations);
            store.insert_path(path, &segs)?;
            path_ids.push(path.path_id.clone());
            report.contract_sides_attempted += 1;
            let mut mc = MarketCoverageRow {
                game_id: path.game_id.clone(),
                market_id: path.market_id.clone(),
                contract_side: path.contract_side.clone(),
                observations: path.observations.len(),
                ..MarketCoverageRow::default()
            };
            let mut synced_side = 0usize;
            for o in &path.observations {
                tally(&mut report, o);
                match o.join_status {
                    PathJoinStatus::Synchronized => {}
                    PathJoinStatus::AtEvent => mc.at_event += 1,
                    PathJoinStatus::SynchronizedWithTimestampGap => mc.with_gap += 1,
                    PathJoinStatus::BeforeFirstEvent => mc.before_first += 1,
                    PathJoinStatus::AfterLastEvent => mc.after_last += 1,
                    _ => {}
                }
                if o.join_status.has_applicable_state() && o.state_id.is_some() {
                    synced_side += 1;
                    mc.synchronized += 1;
                    if let Some(sid) = &o.state_id {
                        covered_states.insert(sid.clone());
                    }
                }
                examples.consider(o);
                game_obs.push(o);
            }
            if synced_side > 0 {
                report.contract_sides_with_synchronized_observations += 1;
            }
            market_cov_out.push(mc);
        }

        let mut gc = GameCoverageRow {
            game_id: game_id.clone(),
            game_pk: game_pk.clone(),
            observations: game_obs.len(),
            w6_timed_states: timed_state_ids.len(),
            w6_states_with_observations: timed_state_ids
                .iter()
                .filter(|s| covered_states.contains(*s))
                .count(),
            ..GameCoverageRow::default()
        };
        for o in &game_obs {
            if o.join_status.has_applicable_state() && o.state_id.is_some() {
                gc.synchronized += 1;
            }
            match o.join_status {
                PathJoinStatus::BeforeFirstEvent => gc.before_first += 1,
                PathJoinStatus::AfterLastEvent => gc.after_last += 1,
                PathJoinStatus::AtEvent => gc.at_event += 1,
                PathJoinStatus::SynchronizedWithTimestampGap => gc.with_gap += 1,
                PathJoinStatus::NoGameState => gc.no_game_state += 1,
                _ => {}
            }
        }
        gc.coverage = if gc.synchronized == 0 {
            report.games_with_no_usable_synchronized_path += 1;
            report.games_with_zero_synchronized_observations += 1;
            "NONE".into()
        } else if gc.w6_timed_states > 0 && gc.w6_states_with_observations == gc.w6_timed_states {
            report.games_with_complete_state_coverage += 1;
            report.games_with_w5_synchronized_observations += 1;
            "COMPLETE".into()
        } else {
            report.games_with_partial_state_coverage += 1;
            report.games_with_w5_synchronized_observations += 1;
            "PARTIAL".into()
        };
        store.insert_game_coverage(&GamePathCoverage {
            game_id: gc.game_id.clone(),
            game_pk: gc.game_pk.clone(),
            observations: gc.observations,
            synchronized: gc.synchronized,
            before_first: gc.before_first,
            after_last: gc.after_last,
            at_event: gc.at_event,
            with_gap: gc.with_gap,
            no_game_state: gc.no_game_state,
            coverage: gc.coverage.clone(),
        })?;
        game_cov_out.push(gc);
        if report.games_attempted % 25 == 0 {
            store.checkpoint()?;
        }
    }

    store.validate_anti_lookahead()?;

    // Unique markets (not sides).
    report.markets_attempted = market_cov_out
        .iter()
        .map(|m| m.market_id.clone())
        .collect::<BTreeSet<_>>()
        .len();
    report.total_market_observations = report.observations_synchronized
        + report.observations_at_event
        + report.observations_synchronized_with_timestamp_gap
        + report.observations_before_first_event
        + report.observations_after_last_event
        + report.observations_no_game_state
        + report.observations_unjoinable
        + report.observations_unsynchronizable
        + report.observations_rejected
        + report.observations_validation_failure;
    report.synchronized_observations = report.observations_synchronized
        + report.observations_at_event
        + report.observations_synchronized_with_timestamp_gap;
    report.observations_price_equals_80 = store.observations_where_price_equals(80)?.len();
    report.paths_written = path_ids.len();
    report.representative_path_ids = examples.path_ids();
    report.w7_gate = if report.failures.is_empty() {
        "COMPLETE".into()
    } else {
        "COMPLETE_WITH_CLASSIFIED_FAILURES".into()
    };

    let example_json = examples.to_json();
    fs::write(
        cfg.out_dir
            .join("examples")
            .join("representative_event_market_paths.json"),
        serde_json::to_string_pretty(&example_json)?,
    )?;
    fs::write(
        cfg.out_dir.join("coverage").join("game_coverage.json"),
        serde_json::to_string_pretty(&game_cov_out)?,
    )?;
    fs::write(
        cfg.out_dir
            .join("coverage")
            .join("market_side_coverage.json"),
        serde_json::to_string_pretty(&market_cov_out)?,
    )?;
    fs::write(
        cfg.out_dir.join("path_report.json"),
        serde_json::to_string_pretty(&report)?,
    )?;
    fs::write(
        cfg.out_dir.join("coverage_report.json"),
        serde_json::to_string_pretty(&report)?,
    )?;

    let validation = serde_json::json!({
        "anti_lookahead": "PASS",
        "matched_state_timestamp_lte_market_timestamp": true,
        "before_first_and_after_last_have_no_applicable_state": true,
        "success_rows_have_w6_state": true,
        "trade_kind": "TRADE",
        "synthetic_l2": false,
        "first01": false,
        "w8_started": false,
        "join_status_counts": store.count_join_status()?,
    });
    fs::write(
        cfg.out_dir
            .join("validation")
            .join("w7_validation_report.json"),
        serde_json::to_string_pretty(&validation)?,
    )?;

    let manifest = serde_json::json!({
        "waterfall": WATERFALL,
        "artifact_version": ARTIFACT_VERSION,
        "dataset_version": DATASET_VERSION,
        "schema_version": SCHEMA_VERSION,
        "join_version": JOIN_VERSION,
        "causal_version": CAUSAL_VERSION,
        "run_id": run_id,
        "generated_at": cfg.generated_at.to_rfc3339(),
        "w5_dataset_version": w5_ver,
        "w5_run_id": w5.run_id(),
        "w6_dataset_version": w6_ver,
        "w6_run_id": w6.run_id(),
        "w7_generation_version": ARTIFACT_VERSION,
        "sqlite": "path.sqlite",
        "note": "generated_at is manifest-only and does not order historical observations",
    });
    fs::write(
        cfg.out_dir.join("manifests").join("w7_manifest.json"),
        serde_json::to_string_pretty(&manifest)?,
    )?;
    store.checkpoint()?;
    Ok(report)
}

fn tally(report: &mut PathReport, o: &PathObservation) {
    match o.join_status {
        PathJoinStatus::Synchronized => report.observations_synchronized += 1,
        PathJoinStatus::AtEvent => report.observations_at_event += 1,
        PathJoinStatus::SynchronizedWithTimestampGap => {
            report.observations_synchronized_with_timestamp_gap += 1;
        }
        PathJoinStatus::BeforeFirstEvent => report.observations_before_first_event += 1,
        PathJoinStatus::AfterLastEvent => report.observations_after_last_event += 1,
        PathJoinStatus::NoGameState => report.observations_no_game_state += 1,
        PathJoinStatus::Unjoinable => report.observations_unjoinable += 1,
        PathJoinStatus::Unsynchronizable => report.observations_unsynchronizable += 1,
        PathJoinStatus::Rejected => report.observations_rejected += 1,
        PathJoinStatus::ValidationFailure => report.observations_validation_failure += 1,
    }
}

#[derive(Default)]
struct ExampleSet {
    early: Option<serde_json::Value>,
    mid: Option<serde_json::Value>,
    late: Option<serde_json::Value>,
    extra_innings: Option<serde_json::Value>,
    yes_side: Option<serde_json::Value>,
    no_side: Option<serde_json::Value>,
    synchronized: Option<serde_json::Value>,
    at_event: Option<serde_json::Value>,
    with_gap: Option<serde_json::Value>,
    before_first: Option<serde_json::Value>,
    after_last: Option<serde_json::Value>,
    score_change: Option<serde_json::Value>,
    runners: Option<serde_json::Value>,
    count: Option<serde_json::Value>,
}

impl ExampleSet {
    fn consider(&mut self, o: &PathObservation) {
        let v = example_value(o);
        if self.early.is_none() && o.inning == Some(1) && o.state_id.is_some() {
            self.early = Some(v.clone());
        }
        if self.mid.is_none()
            && o.inning.is_some_and(|i| (5..=6).contains(&i))
            && o.state_id.is_some()
        {
            self.mid = Some(v.clone());
        }
        if self.late.is_none()
            && o.inning.is_some_and(|i| (8..=9).contains(&i))
            && o.state_id.is_some()
        {
            self.late = Some(v.clone());
        }
        if self.extra_innings.is_none() && o.inning.is_some_and(|i| i > 9) && o.state_id.is_some() {
            self.extra_innings = Some(v.clone());
        }
        if o.join_status.has_applicable_state() {
            if self.yes_side.is_none() {
                self.yes_side = Some(v.clone());
            } else if self.no_side.is_none()
                && self
                    .yes_side
                    .as_ref()
                    .is_some_and(|y| y["contract_side"] != o.contract_side)
            {
                self.no_side = Some(v.clone());
            }
        }
        match o.join_status {
            PathJoinStatus::Synchronized if self.synchronized.is_none() => {
                self.synchronized = Some(v.clone());
            }
            PathJoinStatus::AtEvent if self.at_event.is_none() => self.at_event = Some(v.clone()),
            PathJoinStatus::SynchronizedWithTimestampGap if self.with_gap.is_none() => {
                self.with_gap = Some(v.clone());
            }
            PathJoinStatus::BeforeFirstEvent if self.before_first.is_none() => {
                self.before_first = Some(v.clone());
            }
            PathJoinStatus::AfterLastEvent if self.after_last.is_none() => {
                self.after_last = Some(v.clone());
            }
            _ => {}
        }
        if self.score_change.is_none()
            && o.run_differential.is_some_and(|d| d != 0)
            && o.state_id.is_some()
        {
            self.score_change = Some(v.clone());
        }
        if self.runners.is_none() && o.bases_bitmask.is_some_and(|b| b != 0) && o.state_id.is_some()
        {
            self.runners = Some(v.clone());
        }
        if self.count.is_none()
            && (o.balls.is_some() || o.strikes.is_some())
            && o.state_id.is_some()
        {
            self.count = Some(v);
        }
    }

    fn path_ids(&self) -> Vec<String> {
        let slots = [
            &self.early,
            &self.mid,
            &self.late,
            &self.extra_innings,
            &self.yes_side,
            &self.no_side,
            &self.synchronized,
            &self.at_event,
            &self.with_gap,
            &self.before_first,
            &self.after_last,
        ];
        let mut ids = Vec::new();
        for v in slots.into_iter().flatten() {
            if let Some(id) = v.get("path_id").and_then(|x| x.as_str()) {
                if !ids.iter().any(|e| e == id) {
                    ids.push(id.to_string());
                }
            }
        }
        ids
    }

    fn to_json(&self) -> serde_json::Value {
        serde_json::json!({
            "early_game": self.early,
            "mid_game": self.mid,
            "late_game": self.late,
            "extra_innings": self.extra_innings,
            "contract_side_a": self.yes_side,
            "contract_side_b": self.no_side,
            "synchronized": self.synchronized,
            "at_event": self.at_event,
            "timestamp_gap": self.with_gap,
            "pregame_before_first_event": self.before_first,
            "after_last_event": self.after_last,
            "score_change": self.score_change,
            "runner_state": self.runners,
            "count": self.count,
        })
    }
}

fn example_value(o: &PathObservation) -> serde_json::Value {
    serde_json::json!({
        "path_id": o.path_id,
        "path_observation_id": o.path_observation_id,
        "market_timestamp_utc": o.market_timestamp_utc.map(|t| t.to_rfc3339()),
        "trade_price_cents": o.trade_price_cents,
        "observation_kind": o.observation_kind,
        "game_id": o.game_id,
        "market_id": o.market_id,
        "side": o.contract_side,
        "state_id": o.state_id,
        "state_seq": o.state_seq,
        "state_timestamp_utc": o.matched_state_timestamp_utc.map(|t| t.to_rfc3339()),
        "event_lag_ms": o.event_lag_ms,
        "synchronization_class": o.join_status.as_str(),
        "synchronization_quality": o.synchronization_quality,
        "inning": o.inning,
        "half": o.half,
        "outs": o.outs,
        "score_home": o.score_home,
        "score_away": o.score_away,
        "run_differential": o.run_differential,
        "bases": o.bases_bitmask.map(occupancy_label),
        "count": match (o.balls, o.strikes) {
            (Some(b), Some(s)) => Some(format!("{b}-{s}")),
            _ => None,
        },
        "batter_id": o.batter_id,
        "pitcher_id": o.pitcher_id,
        "game_status": o.game_status,
    })
}
