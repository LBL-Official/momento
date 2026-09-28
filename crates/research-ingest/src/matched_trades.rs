//! W4-D: historical trades for authoritative MATCHED identities only.
//!
//! Does not remap identity. Does not write Data-Real. Does not invent L2.

use std::collections::{BTreeMap, HashSet};
use std::fs;
use std::path::{Path, PathBuf};

use chrono::{DateTime, NaiveDate, Utc};
use momento_research_data::discovery::day_window;
use momento_research_data::manifest::{CompletenessStatus, DailyManifest, list_manifest_dates};
use momento_research_data::paths::ResearchPaths;
use momento_research_data::sport::{ResearchSeason, ResearchSport};
use serde::{Deserialize, Serialize};
use serde_json::{Value, json};

use crate::error::IngestError;
use crate::fence::assert_not_forbidden_write;
use crate::kalshi_live::LiveKalshiSource;
use crate::land::{LandResult, land_at_dest};
use crate::paths::{IngestPaths, sha256_bytes, write_json_atomic};
use crate::types::{GameMarketPair, IdentityMapping, SOURCE_KALSHI_MATCHED_TRADES};

pub const MATCHED_TRADES_ENVELOPE: &str = "INGEST.KALSHI.MATCHED_TRADES.1.0.0";
pub const HISTORICAL_TRADES_ENDPOINT: &str = "/trade-api/v2/historical/trades";

#[derive(Clone, Debug)]
pub struct MatchedTradeFetch {
    pub status: String,
    pub trades: Vec<Value>,
    pub notes: String,
}

pub trait MatchedTradeSource {
    fn fetch_trades(
        &self,
        ticker: &str,
        min_ts: i64,
        max_ts: i64,
    ) -> Result<MatchedTradeFetch, IngestError>;
}

#[derive(Clone, Debug, Default)]
pub struct FixtureMatchedTradeSource {
    pub by_ticker: BTreeMap<String, MatchedTradeFetch>,
}

impl MatchedTradeSource for FixtureMatchedTradeSource {
    fn fetch_trades(
        &self,
        ticker: &str,
        _min_ts: i64,
        _max_ts: i64,
    ) -> Result<MatchedTradeFetch, IngestError> {
        self.by_ticker
            .get(ticker)
            .cloned()
            .ok_or_else(|| IngestError::SourceFailure(format!("no matched-trade fixture {ticker}")))
    }
}

impl MatchedTradeSource for LiveKalshiSource {
    fn fetch_trades(
        &self,
        ticker: &str,
        min_ts: i64,
        max_ts: i64,
    ) -> Result<MatchedTradeFetch, IngestError> {
        let (status, trades, notes) = self.fetch_windowed_trades(ticker, min_ts, max_ts)?;
        Ok(MatchedTradeFetch {
            status,
            trades,
            notes,
        })
    }
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct SourceDiscovery {
    pub lake_complete_dates: Vec<String>,
    pub lake_matched_overlap_dates: Vec<String>,
    pub lake_matched_tickers_on_complete_days: usize,
    pub identified_trade_source: String,
    pub identified_endpoint: String,
    pub identifier: String,
    pub maps_to_matched_ticker: bool,
    pub notes: Vec<String>,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct QuarantineRecord {
    pub ticker: String,
    pub game_pk: Option<String>,
    pub code: String,
    pub message: String,
    pub source_record_id: Option<String>,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct MatchedBackfillReport {
    pub waterfall: String,
    pub artifact_version: String,
    pub run_id: String,
    pub source_discovery: SourceDiscovery,
    pub matched_attempted: usize,
    pub fetched: usize,
    pub skipped_existing: usize,
    pub fetch_failed: usize,
    pub landed_with_trades: usize,
    pub landed_empty: usize,
    pub canonical_trade_observations: usize,
    pub duplicate_source_events_dropped: usize,
    pub unmappable: usize,
    pub malformed: usize,
    pub by_season: BTreeMap<String, usize>,
    pub by_date_landed: BTreeMap<String, usize>,
    pub quarantine: Vec<QuarantineRecord>,
    pub notes: Vec<String>,
}

pub fn discover_matched_trade_sources(
    lake_root: &Path,
    pairs: &[GameMarketPair],
) -> Result<SourceDiscovery, IngestError> {
    let paths = ResearchPaths {
        root: lake_root.to_path_buf(),
        season: ResearchSeason::current(),
    };
    let mut complete = Vec::new();
    for d in list_manifest_dates(&paths, ResearchSport::Mlb).unwrap_or_default() {
        if let Ok(Some(m)) = DailyManifest::read(&paths, ResearchSport::Mlb, d) {
            if m.completeness_status == CompletenessStatus::Complete {
                complete.push(d.to_string());
            }
        }
    }
    let matched_dates: std::collections::BTreeSet<_> = pairs
        .iter()
        .filter(|p| p.mapping == IdentityMapping::Mapped && !p.ticker.is_empty())
        .map(|p| p.official_date.clone())
        .collect();
    let overlap: Vec<String> = complete
        .iter()
        .filter(|d| matched_dates.contains(*d))
        .cloned()
        .collect();
    let overlap_tickers = pairs
        .iter()
        .filter(|p| {
            p.mapping == IdentityMapping::Mapped
                && !p.ticker.is_empty()
                && overlap.iter().any(|d| d == &p.official_date)
        })
        .count();
    Ok(SourceDiscovery {
        lake_complete_dates: complete,
        lake_matched_overlap_dates: overlap,
        lake_matched_tickers_on_complete_days: overlap_tickers,
        identified_trade_source: SOURCE_KALSHI_MATCHED_TRADES.into(),
        identified_endpoint: HISTORICAL_TRADES_ENDPOINT.into(),
        identifier: "Kalshi market ticker (same string as MATCHED pair ticker)".into(),
        maps_to_matched_ticker: true,
        notes: vec![
            "Data-Real COMPLETE days are 2026-06-18..30; MATCHED catalog is 2025-04-16..2026-04-16 — no date overlap.".into(),
            "Discovery envelopes for MATCHED pairs were landed with trades_status=NOT_REQUESTED (--kalshi-metadata-only).".into(),
            "Legitimate remaining source: Kalshi GET /trade-api/v2/historical/trades keyed by ticker.".into(),
            "Pacific calendar day of official_date is the fetch window (existing day_window contract).".into(),
        ],
    })
}

pub fn matched_pairs_only(pairs: &[GameMarketPair]) -> Vec<GameMarketPair> {
    pairs
        .iter()
        .filter(|p| {
            p.mapping == IdentityMapping::Mapped
                && !p.ticker.is_empty()
                && p.game_pk.as_ref().is_some_and(|s| !s.is_empty())
        })
        .cloned()
        .collect()
}

pub fn load_game_market_pairs(path: &Path) -> Result<Vec<GameMarketPair>, IngestError> {
    Ok(serde_json::from_slice(&fs::read(path)?)?)
}

/// Exact integer cents only. Non-zero digits past two decimal places are not rounded.
pub fn dollar_string_is_exact_cents(raw: &str) -> Result<(), &'static str> {
    let s = raw.trim();
    if s.is_empty() {
        return Err("empty");
    }
    let (whole_s, frac_s) = match s.split_once('.') {
        Some((w, f)) => (w, f),
        None => (s, ""),
    };
    if whole_s.starts_with('-') || whole_s.starts_with('+') {
        return Err("signed");
    }
    if whole_s.is_empty() || !whole_s.chars().all(|c| c.is_ascii_digit()) {
        return Err("invalid");
    }
    if !frac_s.chars().all(|c| c.is_ascii_digit()) {
        return Err("invalid");
    }
    if frac_s.len() > 2 && frac_s[2..].chars().any(|c| c != '0') {
        return Err("finer_than_cents");
    }
    Ok(())
}

fn dedupe_matched_tickers(
    pairs: Vec<GameMarketPair>,
    quarantine: &mut Vec<QuarantineRecord>,
) -> Vec<GameMarketPair> {
    let mut seen: BTreeMap<String, GameMarketPair> = BTreeMap::new();
    let mut order: Vec<String> = Vec::new();
    for p in pairs {
        if let Some(existing) = seen.get(&p.ticker) {
            if existing.game_pk != p.game_pk {
                quarantine.push(QuarantineRecord {
                    ticker: p.ticker.clone(),
                    game_pk: p.game_pk.clone(),
                    code: "DUPLICATE_TICKER_IDENTITY".into(),
                    message: format!(
                        "ticker already mapped to game_pk {:?}; not remapped to {:?}",
                        existing.game_pk, p.game_pk
                    ),
                    source_record_id: None,
                });
            }
            continue;
        }
        order.push(p.ticker.clone());
        seen.insert(p.ticker.clone(), p);
    }
    order.into_iter().filter_map(|t| seen.remove(&t)).collect()
}

#[allow(clippy::too_many_arguments)]
pub fn run_matched_trade_backfill(
    ingest_root: &Path,
    lake_root: &Path,
    extra_forbidden: &[PathBuf],
    pairs: &[GameMarketPair],
    source: &dyn MatchedTradeSource,
    generated_at: DateTime<Utc>,
    skip_existing: bool,
    max_markets: Option<usize>,
) -> Result<MatchedBackfillReport, IngestError> {
    assert_not_forbidden_write(ingest_root, lake_root, extra_forbidden)?;
    let discovery = discover_matched_trade_sources(lake_root, pairs)?;
    let mut quarantine = Vec::new();
    let mut matched = dedupe_matched_tickers(matched_pairs_only(pairs), &mut quarantine);
    matched.sort_by(|a, b| a.ticker.cmp(&b.ticker));
    if let Some(n) = max_markets {
        matched.truncate(n);
    }

    let paths = IngestPaths::new(ingest_root);
    let run_id = format!("matched-trades-{}", generated_at.format("%Y%m%dT%H%M%SZ"));
    let mut fetched = 0usize;
    let mut skipped = 0usize;
    let mut failed = 0usize;
    let mut with_trades = 0usize;
    let mut empty = 0usize;
    let mut canonical = 0usize;
    let mut dup_dropped = 0usize;
    let mut unmappable = 0usize;
    let mut malformed = 0usize;
    let mut by_season: BTreeMap<String, usize> = BTreeMap::new();
    let mut by_date: BTreeMap<String, usize> = BTreeMap::new();

    for (i, pair) in matched.iter().enumerate() {
        let date = NaiveDate::parse_from_str(&pair.official_date, "%Y-%m-%d").map_err(|e| {
            IngestError::SourceFailure(format!("official_date {}: {e}", pair.official_date))
        })?;
        let dest = paths.landing_kalshi_matched_trades(date, &pair.ticker);
        if skip_existing && dest.exists() {
            skipped += 1;
            if let Ok(existing) = fs::read(&dest) {
                if let Ok(v) = serde_json::from_slice::<Value>(&existing) {
                    let n = v
                        .get("canonical_trade_count")
                        .and_then(|x| x.as_u64())
                        .unwrap_or(0) as usize;
                    if n > 0 {
                        with_trades += 1;
                        canonical += n;
                        *by_date.entry(pair.official_date.clone()).or_insert(0) += 1;
                        if let Some(y) = pair.official_date.get(..4) {
                            *by_season.entry(y.to_string()).or_insert(0) += 1;
                        }
                    } else {
                        empty += 1;
                    }
                }
            }
            continue;
        }
        let window = day_window(date);
        match source.fetch_trades(&pair.ticker, window.start_ts, window.end_ts) {
            Err(e) => {
                failed += 1;
                quarantine.push(QuarantineRecord {
                    ticker: pair.ticker.clone(),
                    game_pk: pair.game_pk.clone(),
                    code: "FETCH_FAILED".into(),
                    message: e.to_string(),
                    source_record_id: None,
                });
            }
            Ok(fetch) => {
                fetched += 1;
                let mut seen_ids = HashSet::new();
                let mut kept = Vec::new();
                for t in fetch.trades {
                    let trade_ticker = t
                        .get("ticker")
                        .and_then(|v| v.as_str())
                        .unwrap_or("")
                        .to_string();
                    let trade_id = t
                        .get("trade_id")
                        .and_then(|v| v.as_str())
                        .map(str::to_string);
                    if trade_ticker != pair.ticker {
                        unmappable += 1;
                        quarantine.push(QuarantineRecord {
                            ticker: pair.ticker.clone(),
                            game_pk: pair.game_pk.clone(),
                            code: "UNMAPPABLE_TICKER".into(),
                            message: format!(
                                "trade ticker {trade_ticker:?} != MATCHED {}",
                                pair.ticker
                            ),
                            source_record_id: trade_id,
                        });
                        continue;
                    }
                    if t.get("created_time").and_then(|v| v.as_str()).is_none() {
                        malformed += 1;
                        quarantine.push(QuarantineRecord {
                            ticker: pair.ticker.clone(),
                            game_pk: pair.game_pk.clone(),
                            code: "MALFORMED_MISSING_TIME".into(),
                            message: "created_time missing; retrieval not substituted".into(),
                            source_record_id: trade_id,
                        });
                        continue;
                    }
                    let Some(px) = t.get("yes_price_dollars").and_then(|v| v.as_str()) else {
                        malformed += 1;
                        quarantine.push(QuarantineRecord {
                            ticker: pair.ticker.clone(),
                            game_pk: pair.game_pk.clone(),
                            code: "MALFORMED_MISSING_PRICE".into(),
                            message: "yes_price_dollars missing".into(),
                            source_record_id: trade_id,
                        });
                        continue;
                    };
                    match dollar_string_is_exact_cents(px) {
                        Err("finer_than_cents") => {
                            malformed += 1;
                            quarantine.push(QuarantineRecord {
                                ticker: pair.ticker.clone(),
                                game_pk: pair.game_pk.clone(),
                                code: "PRECISION_FINER_THAN_CENTS".into(),
                                message: format!(
                                    "yes_price_dollars {px} is finer than integer cents; not rounded"
                                ),
                                source_record_id: trade_id,
                            });
                            continue;
                        }
                        Err(_) => {
                            malformed += 1;
                            quarantine.push(QuarantineRecord {
                                ticker: pair.ticker.clone(),
                                game_pk: pair.game_pk.clone(),
                                code: "MALFORMED_PRICE".into(),
                                message: format!("yes_price_dollars {px} is not a dollar string"),
                                source_record_id: trade_id,
                            });
                            continue;
                        }
                        Ok(()) => {}
                    }
                    if let Some(id) = &trade_id {
                        if !id.is_empty() && !seen_ids.insert(id.clone()) {
                            dup_dropped += 1;
                            continue;
                        }
                    }
                    kept.push(t);
                }
                let payload_bytes = serde_json::to_vec(&kept)?;
                let payload_sha = sha256_bytes(&payload_bytes);
                let envelope = json!({
                    "envelope_version": MATCHED_TRADES_ENVELOPE,
                    "fixture_kind": "HISTORICAL_SOURCE",
                    "source": SOURCE_KALSHI_MATCHED_TRADES,
                    "source_endpoint": HISTORICAL_TRADES_ENDPOINT,
                    "ticker": pair.ticker,
                    "event_ticker": pair.event_ticker,
                    "game_pk": pair.game_pk,
                    "identity_mapping": pair.mapping,
                    "official_date": pair.official_date,
                    "retrieved_at": generated_at.to_rfc3339(),
                    "window_start_ts": window.start_ts,
                    "window_end_ts": window.end_ts,
                    "trades_status": fetch.status,
                    "canonical_trade_count": kept.len(),
                    "payload_sha256": payload_sha,
                    "ingestion_run_id": run_id,
                    "notes": fetch.notes,
                    "trades": kept,
                });
                let bytes = serde_json::to_vec(&envelope)?;
                match land_at_dest(dest, &bytes, &IngestPaths::ticker_file_stem(&pair.ticker))? {
                    LandResult::Written { .. } | LandResult::AlreadyKnown { .. } => {}
                    LandResult::VersionConflict { .. } => {}
                }
                if kept.is_empty() {
                    empty += 1;
                } else {
                    with_trades += 1;
                    canonical += kept.len();
                    *by_date.entry(pair.official_date.clone()).or_insert(0) += 1;
                    if let Some(y) = pair.official_date.get(..4) {
                        *by_season.entry(y.to_string()).or_insert(0) += 1;
                    }
                }
            }
        }
        if i == 0 || (i + 1) % 25 == 0 || i + 1 == matched.len() {
            eprintln!(
                "matched-trades {}/{} {} fetched={fetched} skipped={skipped} failed={failed}",
                i + 1,
                matched.len(),
                pair.ticker
            );
        }
    }

    let report = MatchedBackfillReport {
        waterfall: "W4-D".into(),
        artifact_version: crate::types::ARTIFACT_VERSION.into(),
        run_id: run_id.clone(),
        source_discovery: discovery,
        matched_attempted: matched.len(),
        fetched,
        skipped_existing: skipped,
        fetch_failed: failed,
        landed_with_trades: with_trades,
        landed_empty: empty,
        canonical_trade_observations: canonical,
        duplicate_source_events_dropped: dup_dropped,
        unmappable,
        malformed,
        by_season,
        by_date_landed: by_date,
        quarantine: quarantine.clone(),
        notes: vec![
            "Identity mapping was not changed. Only ingest IdentityMapping::Mapped rows were attempted.".into(),
            "Retrieval time is provenance only. created_time remains the event timestamp.".into(),
            "Empty fetch is MATCHED + METADATA_ONLY, not a fabricated path.".into(),
            "W5 was not started.".into(),
        ],
    };
    let run_dir = paths.ensure_run(&run_id)?;
    write_json_atomic(&run_dir.join("matched_trade_backfill.json"), &report)?;
    write_json_atomic(&run_dir.join("matched_trade_quarantine.json"), &quarantine)?;
    Ok(report)
}

pub fn load_matched_trade_sidecar(path: &Path) -> Result<Option<Value>, IngestError> {
    if !path.exists() {
        return Ok(None);
    }
    Ok(Some(serde_json::from_slice(&fs::read(path)?)?))
}
