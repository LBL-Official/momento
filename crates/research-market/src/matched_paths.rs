//! W4-D: reconstruct MATCHED markets from historical-trade sidecars.
//!
//! Does not rewrite UNMATCHED `price_path_compact.jsonl`. Does not start W5.

use std::collections::BTreeMap;
use std::fs::{self, File};
use std::io::{BufWriter, Write};
use std::path::{Path, PathBuf};

use chrono::{DateTime, NaiveDate, Utc};
use momento_research_data::foundation::LakeWriteGuard;
use momento_research_data::schema::RawMarketEvent;
use momento_research_ingest::paths::IngestPaths;
use momento_research_ingest::types::{GameMarketPair, IdentityMapping};
use serde::{Deserialize, Serialize};
use serde_json::Value;

use crate::error::W4Error;
use crate::price_path::chronological_trades;
use crate::price_paths::{CompactPricePath, CompactTradePrint};
use crate::reader::{
    DiscoveryEnvelope, IdentityIndex, latest_run_paths, load_identity_pairs, read_envelope,
};
use crate::readiness::MarketReadiness;
use crate::reconstruct::reconstruct_path;
use crate::types::{MarketCompleteness, ReconstructionAnomaly};
use crate::versions::{ARTIFACT_VERSION, RECONSTRUCTION_VERSION, SERIES_MLB, WATERFALL};

const SIDECAR_ENDPOINT: &str = "matched_historical_trades";

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct MatchedTradeCoverage {
    pub waterfall: String,
    pub artifact_version: String,
    pub reconstruction_version: String,
    pub source_run: String,
    pub identity_note: String,
    pub total_matched_markets: usize,
    pub matched_with_trades: usize,
    pub matched_without_trades: usize,
    pub matched_trades_only: usize,
    pub matched_candles_only: usize,
    pub matched_l2_complete: usize,
    pub matched_l2_partial: usize,
    pub matched_metadata_only: usize,
    pub matched_with_exact_80_print: usize,
    pub matched_with_exact_81_print: usize,
    pub matched_with_exact_89_print: usize,
    pub matched_with_post_80_path: usize,
    pub matched_with_no_usable_price_observations: usize,
    pub total_matched_trade_observations: usize,
    pub existing_unmatched_trades_only_paths: Option<usize>,
    pub existing_unmatched_trade_observations: Option<usize>,
    pub combined_trade_observations: Option<usize>,
    pub min_trades_per_matched_with_trades: Option<usize>,
    pub median_trades_per_matched_with_trades: Option<usize>,
    pub max_trades_per_matched_with_trades: Option<usize>,
    pub duplicate_trade_ids: usize,
    pub malformed: usize,
    pub unmappable_sidecars: usize,
    pub reconstruct_failed: usize,
    pub by_date_with_trades: BTreeMap<String, usize>,
    pub by_season_with_trades: BTreeMap<String, usize>,
    pub notes: Vec<String>,
    pub w4_gate: String,
}

pub fn sidecar_trades_as_raw_events(sidecar: &Value) -> Result<Vec<RawMarketEvent>, W4Error> {
    let retrieval = sidecar
        .get("retrieved_at")
        .and_then(|v| v.as_str())
        .and_then(parse_rfc3339)
        .ok_or_else(|| {
            W4Error::Reconstruction("matched sidecar missing retrieved_at provenance".into())
        })?;
    let ticker = sidecar
        .get("ticker")
        .and_then(|v| v.as_str())
        .map(str::to_string);
    let trades = sidecar
        .get("trades")
        .and_then(|v| v.as_array())
        .cloned()
        .unwrap_or_default();
    Ok(trades
        .into_iter()
        .map(|payload| RawMarketEvent {
            received_at: retrieval,
            source: "historical_rest".into(),
            endpoint: SIDECAR_ENDPOINT.into(),
            ticker: ticker.clone(),
            payload,
        })
        .collect())
}

pub fn run_matched_trade_reconstruction(
    ingest_root: &Path,
    lake_root: &Path,
    out_dir: &Path,
    handoff: Option<&Path>,
    pairs: Option<&Path>,
) -> Result<MatchedTradeCoverage, W4Error> {
    let guard = LakeWriteGuard::new(lake_root);
    guard
        .assert_not_lake_path(out_dir)
        .map_err(W4Error::LakeWriteForbidden)?;

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
    let identity = if pairs_path.exists() {
        load_identity_pairs(&pairs_path)?
    } else {
        IdentityIndex::empty()
    };
    let source_run = handoff_path
        .parent()
        .and_then(|p| p.file_name())
        .map(|s| s.to_string_lossy().into_owned())
        .unwrap_or_else(|| "unknown".into());

    let mut matched: Vec<GameMarketPair> = identity
        .by_ticker
        .values()
        .filter(|p| {
            p.mapping == IdentityMapping::Mapped
                && !p.ticker.is_empty()
                && p.game_pk.as_ref().is_some_and(|s| !s.is_empty())
        })
        .cloned()
        .collect();
    matched.sort_by(|a, b| a.ticker.cmp(&b.ticker));

    fs::create_dir_all(out_dir)?;
    let jsonl = out_dir.join("matched_price_path_compact.jsonl");
    let mut compact_w = BufWriter::new(File::create(&jsonl)?);
    let ingest_paths = IngestPaths::new(ingest_root);

    let mut rows: Vec<MarketReadiness> = Vec::new();
    let mut anomalies: Vec<ReconstructionAnomaly> = Vec::new();
    let mut with_trades = 0usize;
    let mut trades_only = 0usize;
    let mut candles_only = 0usize;
    let mut l2_complete = 0usize;
    let mut l2_partial = 0usize;
    let mut metadata_only = 0usize;
    let mut exact_80 = 0usize;
    let mut exact_81 = 0usize;
    let mut exact_89 = 0usize;
    let mut post_80 = 0usize;
    let mut no_usable = 0usize;
    let mut total_trades = 0usize;
    let mut trade_counts: Vec<usize> = Vec::new();
    let mut dup_ids = 0usize;
    let mut malformed = 0usize;
    let mut unmappable = 0usize;
    let mut failed = 0usize;
    let mut by_date: BTreeMap<String, usize> = BTreeMap::new();
    let mut by_season: BTreeMap<String, usize> = BTreeMap::new();

    for pair in &matched {
        let date = match NaiveDate::parse_from_str(&pair.official_date, "%Y-%m-%d") {
            Ok(d) => d,
            Err(e) => {
                failed += 1;
                anomalies.push(ReconstructionAnomaly {
                    ticker: pair.ticker.clone(),
                    code: "MALFORMED_OFFICIAL_DATE".into(),
                    message: e.to_string(),
                });
                continue;
            }
        };
        let env = load_or_synthesize_envelope(&ingest_paths, date, pair)?;
        if env.ticker != pair.ticker {
            unmappable += 1;
            anomalies.push(ReconstructionAnomaly {
                ticker: pair.ticker.clone(),
                code: "IDENTITY_TICKER_MISMATCH".into(),
                message: format!(
                    "envelope ticker {} != authoritative MATCHED {}",
                    env.ticker, pair.ticker
                ),
            });
            continue;
        }

        let sidecar_path = ingest_paths.landing_kalshi_matched_trades(date, &pair.ticker);
        let mut raw_rows = Vec::new();
        if sidecar_path.exists() {
            match fs::read(&sidecar_path) {
                Ok(bytes) => match serde_json::from_slice::<Value>(&bytes) {
                    Ok(sidecar) => {
                        let side_ticker =
                            sidecar.get("ticker").and_then(|v| v.as_str()).unwrap_or("");
                        if !side_ticker.is_empty() && side_ticker != pair.ticker {
                            unmappable += 1;
                            anomalies.push(ReconstructionAnomaly {
                                ticker: pair.ticker.clone(),
                                code: "UNMAPPABLE_SIDECAR_TICKER".into(),
                                message: format!(
                                    "sidecar ticker {side_ticker} != MATCHED {}",
                                    pair.ticker
                                ),
                            });
                        } else {
                            match sidecar_trades_as_raw_events(&sidecar) {
                                Ok(rows_raw) => raw_rows = rows_raw,
                                Err(e) => {
                                    malformed += 1;
                                    anomalies.push(ReconstructionAnomaly {
                                        ticker: pair.ticker.clone(),
                                        code: "SIDECAR_PROVENANCE".into(),
                                        message: e.to_string(),
                                    });
                                }
                            }
                        }
                    }
                    Err(e) => {
                        malformed += 1;
                        anomalies.push(ReconstructionAnomaly {
                            ticker: pair.ticker.clone(),
                            code: "SIDECAR_PARSE".into(),
                            message: e.to_string(),
                        });
                    }
                },
                Err(e) => {
                    malformed += 1;
                    anomalies.push(ReconstructionAnomaly {
                        ticker: pair.ticker.clone(),
                        code: "SIDECAR_IO".into(),
                        message: e.to_string(),
                    });
                }
            }
        }

        match reconstruct_path(&env, &identity, &raw_rows) {
            Ok((path_obj, mut a)) => {
                anomalies.append(&mut a);
                let ready = MarketReadiness::measure(&path_obj, &anomalies);
                dup_ids += ready.duplicate_trade_ids;
                malformed += ready.malformed;
                match path_obj.completeness {
                    MarketCompleteness::TradesOnly => trades_only += 1,
                    MarketCompleteness::CandlesOnly => candles_only += 1,
                    MarketCompleteness::L2Complete => l2_complete += 1,
                    MarketCompleteness::L2Partial => l2_partial += 1,
                    MarketCompleteness::MarketMetadataOnly | MarketCompleteness::Unobserved => {
                        metadata_only += 1;
                    }
                }
                if let Ok(trades) = chronological_trades(&path_obj) {
                    if trades.is_empty() {
                        no_usable += 1;
                    } else {
                        with_trades += 1;
                        total_trades += trades.len();
                        trade_counts.push(trades.len());
                        *by_date.entry(pair.official_date.clone()).or_insert(0) += 1;
                        if let Some(y) = pair.official_date.get(..4) {
                            *by_season.entry(y.to_string()).or_insert(0) += 1;
                        }
                        let has_80 = trades.iter().any(|t| t.price_cents == 80);
                        let has_81 = trades.iter().any(|t| t.price_cents == 81);
                        let has_89 = trades.iter().any(|t| t.price_cents == 89);
                        if has_80 {
                            exact_80 += 1;
                        }
                        if has_81 {
                            exact_81 += 1;
                        }
                        if has_89 {
                            exact_89 += 1;
                        }
                        if trades
                            .iter()
                            .position(|t| t.price_cents == 80)
                            .is_some_and(|i| trades.len() > i + 1)
                        {
                            post_80 += 1;
                        }
                        if path_obj.completeness == MarketCompleteness::TradesOnly {
                            let compact = CompactPricePath {
                                ticker: path_obj.ticker.clone(),
                                event_ticker: path_obj.event_ticker.clone(),
                                market_id: path_obj.market_id.clone(),
                                completeness: path_obj.completeness,
                                identity_status: path_obj
                                    .capability
                                    .market_identity_status
                                    .as_str()
                                    .into(),
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
                            };
                            serde_json::to_writer(&mut compact_w, &compact)?;
                            compact_w.write_all(b"\n")?;
                        }
                    }
                } else {
                    no_usable += 1;
                }
                drop(path_obj);
                rows.push(ready);
            }
            Err(e) => {
                failed += 1;
                anomalies.push(ReconstructionAnomaly {
                    ticker: pair.ticker.clone(),
                    code: "RECONSTRUCT".into(),
                    message: e.to_string(),
                });
            }
        }
    }
    compact_w.flush()?;
    rows.sort_by(|a, b| a.ticker.cmp(&b.ticker));

    trade_counts.sort_unstable();
    let (min_t, med_t, max_t) = extrema_median(&trade_counts);

    let unmatched_paths = read_existing_unmatched_path_count(out_dir);
    let unmatched_obs = read_existing_unmatched_trade_observations(out_dir);
    let combined = unmatched_obs.map(|u| u + total_trades);

    let coverage = MatchedTradeCoverage {
        waterfall: "W4-D".into(),
        artifact_version: ARTIFACT_VERSION.into(),
        reconstruction_version: RECONSTRUCTION_VERSION.into(),
        source_run,
        identity_note: "MATCHED identity is the existing GameId/ticker mapping. It is not evidence of historical trades.".into(),
        total_matched_markets: matched.len(),
        matched_with_trades: with_trades,
        matched_without_trades: matched.len().saturating_sub(with_trades),
        matched_trades_only: trades_only,
        matched_candles_only: candles_only,
        matched_l2_complete: l2_complete,
        matched_l2_partial: l2_partial,
        matched_metadata_only: metadata_only,
        matched_with_exact_80_print: exact_80,
        matched_with_exact_81_print: exact_81,
        matched_with_exact_89_print: exact_89,
        matched_with_post_80_path: post_80,
        matched_with_no_usable_price_observations: no_usable,
        total_matched_trade_observations: total_trades,
        existing_unmatched_trades_only_paths: unmatched_paths,
        existing_unmatched_trade_observations: unmatched_obs,
        combined_trade_observations: combined,
        min_trades_per_matched_with_trades: min_t,
        median_trades_per_matched_with_trades: med_t,
        max_trades_per_matched_with_trades: max_t,
        duplicate_trade_ids: dup_ids,
        malformed,
        unmappable_sidecars: unmappable,
        reconstruct_failed: failed,
        by_date_with_trades: by_date,
        by_season_with_trades: by_season,
        notes: vec![
            "MATCHED identity ≠ observed historical market data.".into(),
            "MATCHED + TRADES_ONLY = GameId-linked price-path research when raw trades exist.".into(),
            "MATCHED + METADATA_ONLY = retained identity, not price-path usable.".into(),
            "80/81/89 counts are exact integer-cent trade prints (observability). Not FIRST01 triggers.".into(),
            "UNMATCHED price_path_compact.jsonl was not rewritten.".into(),
            "No synthetic bid/ask. No synthetic L2. W5 was not started.".into(),
            WATERFALL.into(),
        ],
        w4_gate: "W4-D".into(),
    };

    write_pretty(out_dir.join("matched_trade_coverage.json"), &coverage)?;
    write_pretty(out_dir.join("matched_price_path_market_rows.json"), &rows)?;
    write_pretty(
        out_dir.join("matched_price_path_anomalies.json"),
        &anomalies,
    )?;
    Ok(coverage)
}

fn load_or_synthesize_envelope(
    ingest_paths: &IngestPaths,
    date: NaiveDate,
    pair: &GameMarketPair,
) -> Result<DiscoveryEnvelope, W4Error> {
    let discovery = ingest_paths.landing_kalshi_discovery(date, &pair.ticker);
    if discovery.exists() {
        return read_envelope(&discovery);
    }
    Ok(DiscoveryEnvelope {
        ticker: pair.ticker.clone(),
        event_ticker: pair.event_ticker.clone(),
        identity_mapping: Some(pair.mapping),
        observed_game_pk: pair.game_pk.clone(),
        series: Some(SERIES_MLB.into()),
        retrieved_at: None,
        payload: serde_json::json!({
            "completeness": "MARKET_METADATA_ONLY",
            "trades_status": "NOT_IN_DISCOVERY_LANDING",
            "trades": [],
            "candlesticks": {"unavailable": true}
        }),
    })
}

fn extrema_median(sorted: &[usize]) -> (Option<usize>, Option<usize>, Option<usize>) {
    if sorted.is_empty() {
        return (None, None, None);
    }
    let min = sorted[0];
    let max = sorted[sorted.len() - 1];
    let med = sorted[(sorted.len() - 1) / 2];
    (Some(min), Some(med), Some(max))
}

fn read_existing_unmatched_path_count(out_dir: &Path) -> Option<usize> {
    let p = out_dir.join("price_path_readiness.json");
    let v: Value = serde_json::from_slice(&fs::read(p).ok()?).ok()?;
    v.get("reconstructable_trades_only")
        .and_then(|x| x.as_u64())
        .map(|n| n as usize)
}

fn read_existing_unmatched_trade_observations(out_dir: &Path) -> Option<usize> {
    let p = out_dir.join("price_path_market_rows.json");
    let rows: Vec<Value> = serde_json::from_slice(&fs::read(p).ok()?).ok()?;
    Some(
        rows.iter()
            .map(|r| r.get("trade_count").and_then(|x| x.as_u64()).unwrap_or(0) as usize)
            .sum(),
    )
}

fn parse_rfc3339(raw: &str) -> Option<DateTime<Utc>> {
    DateTime::parse_from_rfc3339(raw)
        .ok()
        .map(|d| d.with_timezone(&Utc))
}

fn write_pretty<T: Serialize>(path: PathBuf, value: &T) -> Result<(), W4Error> {
    fs::write(path, serde_json::to_string_pretty(value)?)?;
    Ok(())
}
