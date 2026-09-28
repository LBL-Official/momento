//! W4 reconstruction job. Writes Foundation/W4. Never writes Data-Real.

use std::fs;
use std::path::PathBuf;

use chrono::{DateTime, NaiveDate, Utc};
use momento_research_data::foundation::LakeWriteGuard;
use serde::{Deserialize, Serialize};

use crate::couple::couple_paths;
use crate::coverage::{coupled_counts, has_l2_complete_claim, measure};
use crate::error::W4Error;
use crate::lake::{lake_note_anomalies, load_complete_raw_day};
use crate::reader::{
    IdentityIndex, committed_envelopes_for_date, latest_run_paths, load_handoff,
    load_identity_pairs, read_envelope,
};
use crate::reconstruct::reconstruct_path;
use crate::types::{MarketPath, ObservationBlocker, ReconstructionAnomaly};
use crate::versions::{ARTIFACT_VERSION, WATERFALL};

#[derive(Clone, Debug)]
pub struct W4RunConfig {
    pub lake_root: PathBuf,
    pub out_dir: PathBuf,
    pub ingest_root: PathBuf,
    pub handoff: Option<PathBuf>,
    pub pairs: Option<PathBuf>,
    pub date: NaiveDate,
    pub include_lake_raw: bool,
    pub generated_at: DateTime<Utc>,
}

impl W4RunConfig {
    pub fn defaults() -> Self {
        Self {
            lake_root: PathBuf::from("Backtesting Suite/Data-Real"),
            out_dir: PathBuf::from("Backtesting Suite/Foundation/W4"),
            ingest_root: PathBuf::from("Backtesting Suite/Foundation/Ingest"),
            handoff: None,
            pairs: None,
            date: NaiveDate::from_ymd_opt(2026, 6, 18).expect("date"),
            include_lake_raw: true,
            generated_at: Utc::now(),
        }
    }
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct W4RunResult {
    pub waterfall: String,
    pub artifact_version: String,
    pub generated_at: DateTime<Utc>,
    pub run_id: String,
    pub date: String,
    pub committed_envelopes: usize,
    pub reconstructed: usize,
    pub failed: usize,
    pub coupled_episodes: usize,
    pub completeness_claimed: bool,
    pub coverage: crate::coverage::W4CoverageReport,
    pub anomalies: Vec<ReconstructionAnomaly>,
    pub blockers: Vec<ObservationBlocker>,
    pub out_dir: String,
}

pub fn run_w4_reconstruction(config: &W4RunConfig) -> Result<W4RunResult, W4Error> {
    let guard = LakeWriteGuard::new(&config.lake_root);
    guard
        .assert_not_lake_path(&config.out_dir)
        .map_err(W4Error::LakeWriteForbidden)?;

    let (handoff_path, pairs_default) = match &config.handoff {
        Some(h) => {
            let pairs = config
                .pairs
                .clone()
                .unwrap_or_else(|| h.with_file_name("game_market_pairs.json"));
            (h.clone(), pairs)
        }
        None => latest_run_paths(&config.ingest_root)?,
    };
    let pairs_path = config.pairs.clone().unwrap_or(pairs_default);
    let handoff = load_handoff(&handoff_path)?;
    let identity = if pairs_path.exists() {
        load_identity_pairs(&pairs_path)?
    } else {
        IdentityIndex::empty()
    };

    let envelopes = committed_envelopes_for_date(&handoff, config.date)?;
    let lake = if config.include_lake_raw {
        load_complete_raw_day(&config.lake_root, config.date)?
    } else {
        Default::default()
    };

    let mut paths: Vec<MarketPath> = Vec::new();
    let mut anomalies = lake_note_anomalies(&lake);
    let mut failed = 0usize;

    for env_ref in &envelopes {
        let env = match read_envelope(&env_ref.path) {
            Ok(e) => e,
            Err(e) => {
                failed += 1;
                anomalies.push(ReconstructionAnomaly {
                    ticker: env_ref.artifact.partition_id.clone(),
                    code: "ENVELOPE_PARSE".into(),
                    message: e.to_string(),
                });
                continue;
            }
        };
        let lake_rows = lake.by_ticker.get(&env.ticker).cloned().unwrap_or_default();
        match reconstruct_path(&env, &identity, &lake_rows) {
            Ok((path, mut a)) => {
                anomalies.append(&mut a);
                paths.push(path);
            }
            Err(e) => {
                failed += 1;
                anomalies.push(ReconstructionAnomaly {
                    ticker: env.ticker,
                    code: "RECONSTRUCT".into(),
                    message: e.to_string(),
                });
            }
        }
    }

    paths.sort_by(|a, b| a.ticker.cmp(&b.ticker));
    let (episodes, mut couple_anom) = couple_paths(&paths);
    anomalies.append(&mut couple_anom);
    let (both, missing) = coupled_counts(&episodes);

    let blockers: Vec<ObservationBlocker> = paths
        .iter()
        .filter(|p| p.blocked_on_ingest_observations)
        .map(|p| ObservationBlocker {
            ticker: p.ticker.clone(),
            identity: p.identity,
            completeness: p.completeness,
            reason: "BLOCKED_ON_INGEST_OBSERVATIONS".into(),
        })
        .collect();

    let claimed = failed == 0 && !has_l2_complete_claim(&paths);
    let mut notes = lake.notes.clone();
    notes.push("W5 handoff: market path exists; event↔market sync is not done".into());
    notes.push("FULL_L2 not claimed. 2024 Kalshi not claimed.".into());
    if let Some(p) = identity.path.as_ref() {
        notes.push(format!(
            "identity consumed from {} ({} tickers indexed)",
            p.display(),
            identity.by_ticker.len()
        ));
    }
    let coverage = measure(
        config.date,
        &paths,
        both,
        missing,
        episodes.len(),
        claimed,
        notes,
    );

    let run_id = format!("w4-{}", config.generated_at.format("%Y%m%dT%H%M%SZ"));
    let result = W4RunResult {
        waterfall: WATERFALL.into(),
        artifact_version: ARTIFACT_VERSION.into(),
        generated_at: config.generated_at,
        run_id: run_id.clone(),
        date: config.date.to_string(),
        committed_envelopes: envelopes.len(),
        reconstructed: paths.len(),
        failed,
        coupled_episodes: episodes.len(),
        completeness_claimed: claimed,
        coverage: coverage.clone(),
        anomalies: anomalies.clone(),
        blockers: blockers.clone(),
        out_dir: config.out_dir.display().to_string(),
    };

    fs::create_dir_all(&config.out_dir)?;
    write_json(&config.out_dir.join("reconstruction_summary.json"), &result)?;
    write_json(&config.out_dir.join("coverage.json"), &coverage)?;
    write_json(&config.out_dir.join("anomalies.json"), &anomalies)?;
    write_json(&config.out_dir.join("blockers.json"), &blockers)?;
    write_json(
        &config.out_dir.join("completeness_histogram.json"),
        &coverage.paths_by_completeness,
    )?;
    let identity_hist = serde_json::json!({
        "mapped": coverage.identity_mapped,
        "unmatched": coverage.identity_unmatched,
        "ambiguous": coverage.identity_ambiguous,
    });
    write_json(
        &config.out_dir.join("identity_join_consumed.json"),
        &identity_hist,
    )?;
    let lifetime_hist = serde_json::json!({
        "OPEN_TO_SETTLEMENT": coverage.lifetime_open_to_settlement,
        "SETTLEMENT_DAY_ONLY": coverage.lifetime_settlement_day_only,
        "UNKNOWN": coverage.lifetime_unknown,
    });
    write_json(
        &config.out_dir.join("lifetime_coverage.json"),
        &lifetime_hist,
    )?;

    let summaries: Vec<_> = paths
        .iter()
        .map(|p| {
            serde_json::json!({
                "ticker": p.ticker,
                "event_ticker": p.event_ticker,
                "identity": p.identity,
                "game_pk": p.game_pk,
                "completeness": p.completeness,
                "point_count": p.points.len(),
                "trade_points": p.points.iter().filter(|x| x.kind.as_str() == "TRADE").count(),
                "candle_points": p.points.iter().filter(|x| x.kind.as_str() == "CANDLE_1M").count(),
                "ingest_only_pit_count": p.ingest_only_pit_count,
                "starting_price_class": p.starting_price_class,
                "lifetime_coverage": p.lifetime_coverage,
                "blocked_on_ingest_observations": p.blocked_on_ingest_observations,
                "identity_status": p.capability.market_identity_status,
                "price_path_research": p.capability.price_path_research,
                "orderbook_microstructure": p.capability.orderbook_microstructure,
                "maker_fill_simulation": p.capability.maker_fill_simulation,
                "game_id_linked_research": p.capability.game_id_linked_research,
            })
        })
        .collect();
    write_json(&config.out_dir.join("path_summaries.json"), &summaries)?;

    let coupled_sum: Vec<_> = episodes
        .iter()
        .map(|e| {
            serde_json::json!({
                "event_ticker": e.event_ticker,
                "team_a_ticker": e.team_a_yes.as_ref().map(|p| p.ticker.clone()),
                "team_b_ticker": e.team_b_yes.as_ref().map(|p| p.ticker.clone()),
                "missing_side": e.missing_side,
            })
        })
        .collect();
    write_json(&config.out_dir.join("coupled_episodes.json"), &coupled_sum)?;

    let paths_dir = config.out_dir.join("paths");
    fs::create_dir_all(&paths_dir)?;
    for p in &paths {
        write_json_compact(&paths_dir.join(format!("{}.json", p.ticker)), p)?;
    }

    fs::write(
        config.out_dir.join("w5_handoff.md"),
        "# W4 → W5 handoff\n\nHere is a market path; event↔market sync is **not** done.\nW5 must not treat these paths as SynchronizedState.\n",
    )?;

    Ok(result)
}

fn write_json<T: Serialize>(path: &std::path::Path, value: &T) -> Result<(), W4Error> {
    let body = serde_json::to_string_pretty(value)?;
    fs::write(path, body)?;
    Ok(())
}

fn write_json_compact<T: Serialize>(path: &std::path::Path, value: &T) -> Result<(), W4Error> {
    let body = serde_json::to_vec(value)?;
    fs::write(path, body)?;
    Ok(())
}
