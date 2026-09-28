//! W3 reconstruction job. Reuses W2 ingest_path + replay. Writes Foundation/W3.

use std::fs;
use std::path::{Path, PathBuf};

use chrono::{DateTime, NaiveDate, Utc};
use momento_research_data::foundation::LakeWriteGuard;
use momento_research_event::event::FixtureKind;
use momento_research_event::historical::reconstruct_paths;
use momento_research_event::ingest::ingest_path;
use serde::{Deserialize, Serialize};

use crate::committed::{CommittedSet, from_ingest_handoff, from_w2_collect_manifest};
use crate::coverage::{W3CoverageReport, WindowCounts, base_report, empty_window, measured_window};
use crate::error::W3Error;
use crate::ledger::{StepEvidenceStatus, W3Ledger, empty_ledger};
use crate::lifecycle::MlbGameLifecycle;
use crate::versions::{ARTIFACT_VERSION, WATERFALL};

#[derive(Clone, Debug)]
pub struct W3RunConfig {
    pub lake_root: PathBuf,
    pub out_dir: PathBuf,
    pub collect_manifest: Option<PathBuf>,
    pub ingest_handoff: Option<momento_research_ingest::W1CommitHandoff>,
    pub generated_at: DateTime<Utc>,
}

impl W3RunConfig {
    pub fn defaults() -> Self {
        Self {
            lake_root: PathBuf::from("Backtesting Suite/Data-Real"),
            out_dir: PathBuf::from("Backtesting Suite/Foundation/W3"),
            collect_manifest: Some(PathBuf::from(
                "Backtesting Suite/Foundation/W2/statsapi_collect_manifest.json",
            )),
            ingest_handoff: None,
            generated_at: Utc::now(),
        }
    }
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct ReconstructionAnomaly {
    pub game_pk: String,
    pub code: String,
    pub message: String,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct W3RunResult {
    pub waterfall: String,
    pub artifact_version: String,
    pub generated_at: DateTime<Utc>,
    pub run_id: String,
    pub source_label: String,
    pub discovered: usize,
    pub fetched: usize,
    pub committed: usize,
    pub reconstructed: usize,
    pub valid: usize,
    pub failed: usize,
    pub skipped: usize,
    pub duplicate: usize,
    pub checksum_failures: usize,
    pub pbp_events: usize,
    pub synthetic_excluded: usize,
    pub coverage: W3CoverageReport,
    pub anomalies: Vec<ReconstructionAnomaly>,
    pub out_dir: String,
}

pub fn run_w3_reconstruction(config: &W3RunConfig) -> Result<W3RunResult, W3Error> {
    let guard = LakeWriteGuard::new(&config.lake_root);
    guard
        .assert_not_lake_path(&config.out_dir)
        .map_err(W3Error::LakeWriteForbidden)?;

    let set = load_committed(config)?;
    if set
        .envelopes
        .iter()
        .any(|p| envelope_is_synthetic(p).unwrap_or(false))
    {
        return Err(W3Error::SyntheticInHistorical);
    }

    let hist = if set.envelopes.is_empty() {
        None
    } else {
        Some(
            reconstruct_paths(&set.envelopes, &config.lake_root, &set.source_label)
                .map_err(|e| W3Error::Reconstruction(e.to_string()))?,
        )
    };

    let mut pbp_events = 0usize;
    let mut valid = 0usize;
    let mut failed = 0usize;
    let mut anomalies = Vec::new();
    if let Some(h) = hist.as_ref() {
        for row in &h.rows {
            pbp_events += row.events;
            if row.reconstruction == "VALID" {
                valid += 1;
            } else {
                failed += 1;
                anomalies.push(ReconstructionAnomaly {
                    game_pk: row.game_pk.clone(),
                    code: row.reconstruction.clone(),
                    message: row.reconstruction_error.clone().unwrap_or_default(),
                });
            }
        }
        for msg in &set.checksum_failures {
            anomalies.push(ReconstructionAnomaly {
                game_pk: String::new(),
                code: "CHECKSUM".into(),
                message: msg.clone(),
            });
        }
    }

    let reconstructed = hist.as_ref().map(|h| h.games_attempted).unwrap_or(0);
    failed += set.checksum_failures.len();

    let postponed = set
        .skipped
        .iter()
        .filter(|s| s.lifecycle == MlbGameLifecycle::Postponed)
        .count();
    let cancelled = set
        .skipped
        .iter()
        .filter(|s| s.lifecycle == MlbGameLifecycle::Cancelled)
        .count();
    let suspended = set
        .skipped
        .iter()
        .filter(|s| s.lifecycle == MlbGameLifecycle::Suspended)
        .count();

    let mut coverage = base_report();
    coverage.historical_pbp_events = pbp_events;
    coverage.synthetic_events_excluded = 0;
    coverage.postponed = postponed;
    coverage.cancelled = cancelled;
    coverage.suspended = suspended;
    coverage.theta_values_calculated = 0;
    if let Some(h) = hist.as_ref() {
        coverage.identity_mapped = h.kalshi_mapped;
        coverage.identity_unmatched = h.kalshi_unmatched;
        coverage.identity_ambiguous = h.kalshi_ambiguous;
    }

    let start_2024 = NaiveDate::from_ymd_opt(2024, 3, 20).expect("d");
    let end_2024 = NaiveDate::from_ymd_opt(2024, 11, 2).expect("d");
    coverage.windows.push(empty_window(
        "2024-2025",
        start_2024,
        end_2024,
        "NO_LOCAL_COMMITTED_SOURCE — not fabricated COMPLETE",
    ));
    coverage.windows.push(empty_window(
        "2025-2026-before-observed-window",
        NaiveDate::from_ymd_opt(2025, 3, 18).expect("d"),
        NaiveDate::from_ymd_opt(2026, 6, 17).expect("d"),
        "NO_LOCAL_COMMITTED_SOURCE for this sub-window",
    ));

    let (w_start, w_end, discovered, fetched) = window_from_collect(config);
    coverage.windows.push(measured_window(
        "2026-06-18..30-observed",
        &w_start,
        &w_end,
        WindowCounts {
            discovered,
            fetched,
            committed: set.envelopes.len(),
            reconstructed,
            valid,
            failed,
            skipped: set.skipped.len(),
            duplicate: set.duplicates,
        },
    ));

    let mut ledger = empty_ledger();
    record_run_evidence(&mut ledger, &set, valid, failed, reconstructed, postponed);

    let run_id = format!("w3-{}", config.generated_at.format("%Y%m%dT%H%M%SZ"));
    let result = W3RunResult {
        waterfall: WATERFALL.into(),
        artifact_version: ARTIFACT_VERSION.into(),
        generated_at: config.generated_at,
        run_id: run_id.clone(),
        source_label: set.source_label.clone(),
        discovered,
        fetched,
        committed: set.envelopes.len(),
        reconstructed,
        valid,
        failed,
        skipped: set.skipped.len(),
        duplicate: set.duplicates,
        checksum_failures: set.checksum_failures.len(),
        pbp_events,
        synthetic_excluded: 0,
        coverage,
        anomalies,
        out_dir: config.out_dir.display().to_string(),
    };

    fs::create_dir_all(&config.out_dir)?;
    write_json(&config.out_dir.join("reconstruction_summary.json"), &result)?;
    write_json(&config.out_dir.join("coverage.json"), &result.coverage)?;
    write_json(&config.out_dir.join("anomalies.json"), &result.anomalies)?;
    write_json(&config.out_dir.join("skipped.json"), &set.skipped)?;
    write_json(&config.out_dir.join("ledger.json"), &ledger)?;
    if let Some(h) = hist.as_ref() {
        write_json(&config.out_dir.join("w2_engine_rows.json"), &h.rows)?;
    }
    fs::write(
        config.out_dir.join("schema.sql"),
        crate::schema_sql::W3_SCHEMA_SQL,
    )?;

    Ok(result)
}

fn load_committed(config: &W3RunConfig) -> Result<CommittedSet, W3Error> {
    if let Some(h) = config.ingest_handoff.as_ref() {
        return from_ingest_handoff(h);
    }
    if let Some(m) = config.collect_manifest.as_ref() {
        return from_w2_collect_manifest(m);
    }
    Err(W3Error::Uncommitted(
        "no ingest handoff and no collect manifest".into(),
    ))
}

fn window_from_collect(config: &W3RunConfig) -> (String, String, usize, usize) {
    let default = ("2026-06-18".into(), "2026-06-30".into(), 0usize, 0usize);
    let Some(path) = config.collect_manifest.as_ref() else {
        return default;
    };
    let Ok(body) = fs::read_to_string(path) else {
        return default;
    };
    let Ok(rep) = serde_json::from_str::<momento_research_event::CollectReport>(&body) else {
        return default;
    };
    (rep.start, rep.end, rep.games_listed, rep.games_collected)
}

fn envelope_is_synthetic(path: &Path) -> Result<bool, W3Error> {
    let bytes = fs::read(path)?;
    let v: serde_json::Value = serde_json::from_slice(&bytes)?;
    Ok(v.get("fixture_kind").and_then(|x| x.as_str()) == Some("SYNTHETIC_TEST_FIXTURE"))
}

fn write_json(path: &Path, value: &impl Serialize) -> Result<(), W3Error> {
    let tmp = path.with_extension("json.tmp");
    fs::write(&tmp, serde_json::to_vec_pretty(value)?)?;
    fs::rename(tmp, path)?;
    Ok(())
}

fn record_run_evidence(
    ledger: &mut W3Ledger,
    set: &CommittedSet,
    valid: usize,
    failed: usize,
    reconstructed: usize,
    postponed: usize,
) {
    ledger.record(
        "CTO-W3-A1-S2",
        StepEvidenceStatus::EvidenceRecorded,
        format!("committed envelopes={}", set.envelopes.len()),
    );
    ledger.record(
        "CTO-W3-A1-S4",
        StepEvidenceStatus::EvidenceRecorded,
        format!("checksum_failures={}", set.checksum_failures.len()),
    );
    ledger.record(
        "CTO-W3-A6-S1",
        StepEvidenceStatus::Unavailable,
        "2024-2025: no local committed StatsAPI PBP",
    );
    ledger.record(
        "CTO-W3-A6-S4",
        StepEvidenceStatus::EvidenceRecorded,
        format!(
            "reconstructed={reconstructed} valid={valid} failed={failed} postponed={postponed}"
        ),
    );
    ledger.record(
        "CTO-W3-A9-S5",
        StepEvidenceStatus::NotStarted,
        "CTO acceptance is not set by this runner",
    );
}

/// Parse one committed envelope with the W2 parser (unit-test helper).
pub fn parse_committed_envelope(
    path: &Path,
    expected_sha: &str,
) -> Result<(usize, FixtureKind), W3Error> {
    crate::gate::verify_checksum(path, expected_sha)?;
    let (events, report, _) =
        ingest_path(path).map_err(|e| W3Error::Reconstruction(e.to_string()))?;
    Ok((events.len(), report.fixture_kind))
}
