//! W2 reconstruction job. Read-only vs the Kalshi lake.

use std::path::PathBuf;

use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};

use momento_research_data::foundation::LakeWriteGuard;

use crate::coverage::{CoverageReport, report_from_lake};
use crate::ledger::{W2Ledger, complete_ledger};
use crate::replay::validate_game;
use crate::reporting::{W2ArtifactPaths, write_artifacts};
use crate::source::{discover_local_pbp, source_contract};
use crate::state::replay;
use crate::synthetic;
use crate::versions::{ARTIFACT_VERSION, WATERFALL};

#[derive(Clone, Debug)]
pub struct W2RunConfig {
    pub lake_root: PathBuf,
    pub out_dir: PathBuf,
    pub generated_at: DateTime<Utc>,
}

impl W2RunConfig {
    pub fn defaults() -> Self {
        Self {
            lake_root: PathBuf::from("Backtesting Suite/Data-Real"),
            out_dir: PathBuf::from("Backtesting Suite/Foundation/W2"),
            generated_at: Utc::now(),
        }
    }
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct W2RunResult {
    pub waterfall: String,
    pub artifact_version: String,
    pub generated_at: DateTime<Utc>,
    pub out_dir: String,
    pub google_status: String,
    pub historical_pbp_available: bool,
    pub synthetic_validations_ok: bool,
    pub coverage_rows: usize,
    pub ledger_complete_steps: usize,
    pub ledger_blocked_steps: usize,
    pub historical_games_attempted: usize,
    pub historical_reconstruction_ok: usize,
    pub kalshi_mapped: usize,
}

pub fn run_w2_event_reconstruction(config: &W2RunConfig) -> Result<W2RunResult, String> {
    let guard = LakeWriteGuard::new(&config.lake_root);
    guard.assert_not_lake_path(&config.out_dir)?;

    let discovery = discover_local_pbp(std::slice::from_ref(&config.out_dir));
    let source = source_contract();
    let mut coverage: CoverageReport = if config.lake_root.exists() {
        report_from_lake(&config.lake_root)
    } else {
        CoverageReport {
            coverage_version: crate::versions::COVERAGE_VERSION.into(),
            generated_note: "lake_root missing".into(),
            mlb_2025: "MISSING_HISTORICAL_SOURCE".into(),
            mlb_2026: "lake not mounted".into(),
            historical_pbp_files: 0,
            rows: vec![],
        }
    };

    let raw_root = crate::historical::default_raw_root(&config.out_dir);
    let hist = if raw_root.exists() {
        crate::historical::reconstruct_envelopes(&raw_root, &config.lake_root).ok()
    } else {
        None
    };
    if let Some(h) = hist.as_ref() {
        coverage.historical_pbp_files = h.games_attempted;
        coverage.mlb_2026 = format!(
            "{} Kalshi COMPLETE days in lake; StatsAPI PBP envelopes={} reconstruction_ok={} kalshi_mapped={} (2025 PBP still MISSING_HISTORICAL_SOURCE)",
            coverage.mlb_2026.split(' ').next().unwrap_or("?"),
            h.games_attempted,
            h.reconstruction_ok,
            h.kalshi_mapped
        );
        coverage.generated_note = format!(
            "Official PBP from StatsAPI in {}. 2025 still MISSING_HISTORICAL_SOURCE. Event Theta estimator deferred (ADR-0010).",
            h.raw_root
        );
        let _ = crate::historical::write_report(&config.out_dir, h);
    }

    let catalog = synthetic::catalog_play_types_valid();
    let v_catalog = validate_game(&catalog, None);
    let (nl_events, nl_out) = synthetic::no_lookahead_game();
    let v_nl = validate_game(&nl_events, Some(&nl_out));
    let v_amend = validate_game(&synthetic::amendment_review_outs(), None);
    let validations = vec![v_catalog, v_nl, v_amend];
    let synthetic_ok = validations.iter().all(|v| v.valid) && replay(&catalog).is_ok();

    let ledger: W2Ledger = complete_ledger(config.generated_at);
    let google_status = "GOOGLE_PUBLISH_PENDING";

    let paths = W2ArtifactPaths::create(&config.out_dir).map_err(|e| e.to_string())?;
    write_artifacts(
        &paths,
        &ledger,
        &coverage,
        &source,
        &validations,
        config.generated_at,
        google_status,
    )
    .map_err(|e| e.to_string())?;

    let complete = ledger
        .steps
        .iter()
        .filter(|s| s.status == crate::ledger::StepStatus::Complete)
        .count();
    let blocked = ledger
        .steps
        .iter()
        .filter(|s| s.status == crate::ledger::StepStatus::Blocked)
        .count();

    let hist_attempted = hist.as_ref().map(|h| h.games_attempted).unwrap_or(0);
    let hist_ok = hist.as_ref().map(|h| h.reconstruction_ok).unwrap_or(0);
    let mapped = hist.as_ref().map(|h| h.kalshi_mapped).unwrap_or(0);
    let pbp_available = hist_attempted > 0 || discovery.historical_pbp_available;

    Ok(W2RunResult {
        waterfall: WATERFALL.into(),
        artifact_version: ARTIFACT_VERSION.into(),
        generated_at: config.generated_at,
        out_dir: config.out_dir.display().to_string(),
        google_status: google_status.into(),
        historical_pbp_available: pbp_available,
        synthetic_validations_ok: synthetic_ok,
        coverage_rows: coverage.rows.len(),
        ledger_complete_steps: complete,
        ledger_blocked_steps: blocked,
        historical_games_attempted: hist_attempted,
        historical_reconstruction_ok: hist_ok,
        kalshi_mapped: mapped,
    })
}
