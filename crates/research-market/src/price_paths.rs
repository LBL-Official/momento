//! Bounded price-path reconstruction for TRADES_ONLY (and other observation-bearing) markets.
//! Does not reconstruct metadata-only catalogs into giant path files.

use std::collections::BTreeMap;
use std::fs::{self, File};
use std::io::{BufWriter, Write};
use std::path::{Path, PathBuf};

use momento_research_data::foundation::LakeWriteGuard;
use serde::{Deserialize, Serialize};

use crate::error::W4Error;
use crate::gate::{artifact_is_committed_discovery, verify_checksum};
use crate::inventory::{peek_envelope_prefix, run_universe_inventory};
use crate::price_path::chronological_trades;
use crate::reader::{
    IdentityIndex, latest_run_paths, load_handoff, load_identity_pairs, read_envelope,
};
use crate::readiness::{FunnelCounts, MarketReadiness, coupled_readiness};
use crate::reconstruct::reconstruct_path;
use crate::types::{MarketCompleteness, MarketPath, ReconstructionAnomaly};
use crate::versions::{ARTIFACT_VERSION, RECONSTRUCTION_VERSION, WATERFALL};

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct CompactTradePrint {
    pub ts: String,
    pub cents: i32,
    pub qty_hundredths: Option<i64>,
    pub trade_id: Option<String>,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct CompactPricePath {
    pub ticker: String,
    pub event_ticker: String,
    pub market_id: String,
    pub completeness: MarketCompleteness,
    pub identity_status: String,
    pub game_pk: Option<String>,
    pub reconstruction_version: String,
    pub trades: Vec<CompactTradePrint>,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct PricePathRunReport {
    pub waterfall: String,
    pub artifact_version: String,
    pub reconstruction_version: String,
    pub source_run: String,
    pub inventory_kind: String,
    pub unique_markets_inventoried: usize,
    pub reconstructed: usize,
    pub failed: usize,
    pub skipped_metadata_only: usize,
    pub skipped_unobserved: usize,
    pub skipped_other: usize,
    pub by_completeness: BTreeMap<String, usize>,
    pub by_identity: BTreeMap<String, usize>,
    pub reconstructable_trades_only: usize,
    pub l2_paths: usize,
    pub candles_only_paths: usize,
    pub excluded_from_price_path: usize,
    pub exclusion_reasons: BTreeMap<String, usize>,
    pub funnel_reconstructed_markets: FunnelCounts,
    pub funnel_matched_only: FunnelCounts,
    pub coupled_events: usize,
    pub coupled_both_yes: usize,
    pub coupled_missing_side: usize,
    pub coupled_either_eighty: usize,
    pub unique_matched_games_in_reconstructed: usize,
    pub matched_games_eighty_observable: usize,
    pub notes: Vec<String>,
    pub w4_gate: String,
}

pub fn run_price_path_reconstruction(
    ingest_root: &Path,
    lake_root: &Path,
    out_dir: &Path,
    handoff: Option<&Path>,
    pairs: Option<&Path>,
) -> Result<PricePathRunReport, W4Error> {
    let guard = LakeWriteGuard::new(lake_root);
    guard
        .assert_not_lake_path(out_dir)
        .map_err(W4Error::LakeWriteForbidden)?;

    let inventory = run_universe_inventory(ingest_root, lake_root, out_dir, handoff, pairs)?;

    let (handoff_path, pairs_default) = match handoff {
        Some(h) => (
            h.to_path_buf(),
            pairs
                .map(Path::to_path_buf)
                .unwrap_or_else(|| h.with_file_name("game_market_pairs.json")),
        ),
        None => latest_run_paths(ingest_root)?,
    };
    let pairs_path = pairs.map(Path::to_path_buf).unwrap_or(pairs_default);
    let handoff_doc = load_handoff(&handoff_path)?;
    let identity = if pairs_path.exists() {
        load_identity_pairs(&pairs_path)?
    } else {
        IdentityIndex::empty()
    };

    let mut reconstructed_paths: Vec<MarketPath> = Vec::new();
    let mut rows: Vec<MarketReadiness> = Vec::new();
    let mut anomalies: Vec<ReconstructionAnomaly> = Vec::new();
    let mut compact: Vec<CompactPricePath> = Vec::new();
    let mut failed = 0usize;
    let mut skipped_metadata = 0usize;
    let mut skipped_unobserved = 0usize;
    let mut skipped_other = 0usize;
    let mut by_completeness: BTreeMap<String, usize> = BTreeMap::new();
    let mut exclusion_reasons: BTreeMap<String, usize> = BTreeMap::new();

    let mut sha_by_path: BTreeMap<PathBuf, String> = BTreeMap::new();
    let mut candidates: Vec<PathBuf> = Vec::new();
    for a in &handoff_doc.artifacts {
        if !artifact_is_committed_discovery(&a.source, a.commit_status) {
            continue;
        }
        let path = PathBuf::from(&a.path);
        sha_by_path.insert(path.clone(), a.sha256.clone());
        if !path.exists() {
            skipped_other += 1;
            *exclusion_reasons
                .entry("MISSING_LANDING".into())
                .or_insert(0) += 1;
            continue;
        }
        let peek = peek_envelope_prefix(&path)?;
        *by_completeness
            .entry(peek.completeness().to_string())
            .or_insert(0) += 1;
        if peek.is_price_path_candidate() {
            candidates.push(path);
        } else if peek.completeness() == "MARKET_METADATA_ONLY" {
            skipped_metadata += 1;
            *exclusion_reasons
                .entry("METADATA_ONLY_NO_PRICE_PATH".into())
                .or_insert(0) += 1;
        } else if peek.completeness() == "UNOBSERVED" {
            skipped_unobserved += 1;
            *exclusion_reasons.entry("UNOBSERVED".into()).or_insert(0) += 1;
        } else {
            skipped_other += 1;
            *exclusion_reasons
                .entry(format!("SKIP_{}", peek.completeness()))
                .or_insert(0) += 1;
        }
    }
    candidates.sort();

    for path in &candidates {
        let expected = sha_by_path.get(path).map(String::as_str).unwrap_or("");
        if !expected.is_empty() {
            if let Err(e) = verify_checksum(path, expected) {
                failed += 1;
                anomalies.push(ReconstructionAnomaly {
                    ticker: path.display().to_string(),
                    code: "CHECKSUM".into(),
                    message: e.to_string(),
                });
                continue;
            }
        }
        let env = match read_envelope(path) {
            Ok(e) => e,
            Err(e) => {
                failed += 1;
                anomalies.push(ReconstructionAnomaly {
                    ticker: path.display().to_string(),
                    code: "ENVELOPE_PARSE".into(),
                    message: e.to_string(),
                });
                continue;
            }
        };
        match reconstruct_path(&env, &identity, &[]) {
            Ok((path_obj, mut a)) => {
                anomalies.append(&mut a);
                let row = MarketReadiness::measure(&path_obj, &anomalies);
                if let Ok(trades) = chronological_trades(&path_obj) {
                    compact.push(CompactPricePath {
                        ticker: path_obj.ticker.clone(),
                        event_ticker: path_obj.event_ticker.clone(),
                        market_id: path_obj.market_id.clone(),
                        completeness: path_obj.completeness,
                        identity_status: path_obj.capability.market_identity_status.as_str().into(),
                        game_pk: path_obj.game_pk.clone(),
                        reconstruction_version: path_obj.reconstruction_version.clone(),
                        trades: trades
                            .into_iter()
                            .map(|t| CompactTradePrint {
                                ts: t.exchange_timestamp.to_rfc3339(),
                                cents: t.price_cents,
                                qty_hundredths: t.quantity_hundredths,
                                trade_id: t.trade_id,
                            })
                            .collect(),
                    });
                }
                rows.push(row);
                reconstructed_paths.push(path_obj);
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

    rows.sort_by(|a, b| a.ticker.cmp(&b.ticker));
    compact.sort_by(|a, b| a.ticker.cmp(&b.ticker));
    reconstructed_paths.sort_by(|a, b| a.ticker.cmp(&b.ticker));

    let mut by_identity: BTreeMap<String, usize> = BTreeMap::new();
    let mut trades_only = 0usize;
    let mut l2_paths = 0usize;
    let mut candles_only = 0usize;
    for r in &rows {
        *by_identity
            .entry(r.identity_status.as_str().into())
            .or_insert(0) += 1;
        match r.completeness {
            MarketCompleteness::TradesOnly => trades_only += 1,
            MarketCompleteness::L2Complete | MarketCompleteness::L2Partial => l2_paths += 1,
            MarketCompleteness::CandlesOnly => candles_only += 1,
            _ => {}
        }
    }

    let coupled = coupled_readiness(&reconstructed_paths, &rows);
    let coupled_both = coupled.iter().filter(|c| c.both_yes).count();
    let coupled_missing = coupled.iter().filter(|c| !c.both_yes).count();
    let coupled_eighty = coupled
        .iter()
        .filter(|c| c.either_eighty_observable)
        .count();

    let matched_rows: Vec<_> = rows
        .iter()
        .filter(|r| r.funnel_matched_identity)
        .cloned()
        .collect();
    let mut matched_games = std::collections::BTreeSet::new();
    let mut matched_games_eighty = std::collections::BTreeSet::new();
    for r in &matched_rows {
        if let Some(pk) = &r.game_pk {
            matched_games.insert(pk.clone());
            if r.funnel_eighty_observable {
                matched_games_eighty.insert(pk.clone());
            }
        }
    }

    let excluded_price_path = skipped_metadata + skipped_unobserved + skipped_other;
    let funnel_all = FunnelCounts::from_rows(&rows);
    let funnel_matched = FunnelCounts::from_rows(&matched_rows);

    let notes = vec![
        "TRADES_ONLY is not a failed dataset. It is a valid price-path research universe.".into(),
        "NO L2 = DO NOT INVENT L2. Compact trade files are prints, not bid/ask.".into(),
        "Metadata-only markets were inventoried and excluded from path reconstruct (not discarded from identity).".into(),
        "80/81 flags are observability of trade prints vs frozen FIRST01 thresholds; this is not strategy replay.".into(),
        "W5 (event↔market sync) is not implemented.".into(),
        format!(
            "GameId-linked 80% denominator uses MATCHED reconstructed paths ({}/{} unique matched games in this reconstruct).",
            matched_games_eighty.len(),
            inventory.unique_mapped_games_game_pk
        ),
    ];

    let report = PricePathRunReport {
        waterfall: WATERFALL.into(),
        artifact_version: ARTIFACT_VERSION.into(),
        reconstruction_version: RECONSTRUCTION_VERSION.into(),
        source_run: inventory.source_run.clone(),
        inventory_kind: "PRICE_PATH_RECONSTRUCT_TRADES_ONLY".into(),
        unique_markets_inventoried: inventory.unique_markets,
        reconstructed: reconstructed_paths.len(),
        failed,
        skipped_metadata_only: skipped_metadata,
        skipped_unobserved,
        skipped_other,
        by_completeness,
        by_identity,
        reconstructable_trades_only: trades_only,
        l2_paths,
        candles_only_paths: candles_only,
        excluded_from_price_path: excluded_price_path,
        exclusion_reasons,
        funnel_reconstructed_markets: funnel_all,
        funnel_matched_only: funnel_matched,
        coupled_events: coupled.len(),
        coupled_both_yes: coupled_both,
        coupled_missing_side: coupled_missing,
        coupled_either_eighty: coupled_eighty,
        unique_matched_games_in_reconstructed: matched_games.len(),
        matched_games_eighty_observable: matched_games_eighty.len(),
        notes,
        w4_gate: "COMPLETE".into(),
    };

    fs::create_dir_all(out_dir)?;
    write_pretty(out_dir.join("price_path_readiness.json"), &report)?;
    write_pretty(out_dir.join("price_path_market_rows.json"), &rows)?;
    write_pretty(out_dir.join("price_path_coupled.json"), &coupled)?;
    write_pretty(out_dir.join("price_path_anomalies.json"), &anomalies)?;

    let jsonl = out_dir.join("price_path_compact.jsonl");
    let mut w = BufWriter::new(File::create(&jsonl)?);
    for row in &compact {
        serde_json::to_writer(&mut w, row)?;
        w.write_all(b"\n")?;
    }
    w.flush()?;

    let mut inventory_out = inventory;
    inventory_out.w4_gate = "COMPLETE".into();
    inventory_out.price_paths_reconstructed = Some(reconstructed_paths.len());
    inventory_out.reconstructable_trades_only = Some(trades_only);
    inventory_out.notes = vec![
        "NO L2 = DO NOT INVENT L2. TRADES_ONLY is a valid price-path research universe.".into(),
        "Price-path reconstruct covers observation-bearing markets only; metadata-only excluded from paths, not discarded from identity.".into(),
        "Mapped pairs remain MARKET_METADATA_ONLY until DATA-INGEST lands trades for MATCHED tickers.".into(),
        "2024 Kalshi UNAVAILABLE: catalog begins ~2025-04-16.".into(),
        "W4 price-path foundation COMPLETE. W5 (event↔market sync) is not started.".into(),
    ];
    write_pretty(out_dir.join("universe_inventory.json"), &inventory_out)?;

    Ok(report)
}

fn write_pretty<T: Serialize>(path: PathBuf, value: &T) -> Result<(), W4Error> {
    fs::write(path, serde_json::to_string_pretty(value)?)?;
    Ok(())
}
