//! Discovery/inventory of the committed Kalshi universe. Does not reconstruct paths.

use std::collections::{BTreeMap, BTreeSet};
use std::fs::{self, File};
use std::io::Read;
use std::path::{Path, PathBuf};

use chrono::NaiveDate;
use momento_research_data::foundation::LakeWriteGuard;
use momento_research_ingest::types::{
    GameMarketPair, IdentityMapping, MarketCompleteness as IngestCompleteness,
    SOURCE_KALSHI_DISCOVERY,
};
use serde::{Deserialize, Serialize};

use crate::error::W4Error;
use crate::reader::{latest_run_paths, load_handoff, load_identity_pairs};
use crate::versions::{ARTIFACT_VERSION, SERIES_MLB, WATERFALL};

const PEEK_BYTES: usize = 8192;

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct UniverseInventory {
    pub waterfall: String,
    pub artifact_version: String,
    pub inventory_kind: String,
    pub source_run: String,
    pub sport: String,
    pub series: String,
    pub unique_markets: usize,
    pub unique_event_tickers: usize,
    pub unique_mapped_games_game_pk: usize,
    pub date_start: Option<String>,
    pub date_end: Option<String>,
    pub partition_dates: usize,
    pub calendar_span_days: i64,
    pub seasons: BTreeMap<String, usize>,
    pub identity: BTreeMap<String, usize>,
    pub completeness_landed: BTreeMap<String, usize>,
    pub completeness_by_identity: BTreeMap<String, BTreeMap<String, usize>>,
    pub coupled_events_both_yes: usize,
    pub coupled_events_one_yes: usize,
    pub trade_files: usize,
    pub candle_observed_files: usize,
    pub l2_complete_files: usize,
    pub l2_historical_unavailable: usize,
    pub settlement_metadata_present: usize,
    pub malformed_candlestick_payloads: usize,
    pub missing_landing_files: usize,
    pub already_known_duplicates: usize,
    pub lake_mlb_complete_days: usize,
    pub lake_mlb_missing_days: usize,
    pub notes: Vec<String>,
    pub w4_gate: String,
    #[serde(default)]
    pub price_paths_reconstructed: Option<usize>,
    #[serde(default)]
    pub reconstructable_trades_only: Option<usize>,
}

pub fn run_universe_inventory(
    ingest_root: &Path,
    lake_root: &Path,
    out_dir: &Path,
    handoff: Option<&Path>,
    pairs: Option<&Path>,
) -> Result<UniverseInventory, W4Error> {
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
    let handoff = load_handoff(&handoff_path)?;
    let identity = load_identity_pairs(&pairs_path)?;

    let kalshi: Vec<_> = handoff
        .artifacts
        .iter()
        .filter(|a| a.source == SOURCE_KALSHI_DISCOVERY)
        .collect();

    let mut dates: BTreeSet<NaiveDate> = BTreeSet::new();
    let mut seasons: BTreeMap<String, usize> = BTreeMap::new();
    let mut completeness_landed: BTreeMap<String, usize> = BTreeMap::new();
    let mut missing_landing = 0usize;
    let mut l2_unavail = 0usize;
    let mut l2_complete = 0usize;
    let mut trade_files = 0usize;
    let mut candle_observed = 0usize;
    let mut settlement_present = 0usize;
    let mut malformed_candles = 0usize;
    let mut tickers: BTreeSet<String> = BTreeSet::new();
    let mut events: BTreeSet<String> = BTreeSet::new();

    for a in &kalshi {
        if let Ok(d) = NaiveDate::parse_from_str(&a.date, "%Y-%m-%d") {
            dates.insert(d);
            *seasons.entry(d.format("%Y").to_string()).or_insert(0) += 1;
        }
        tickers.insert(a.partition_id.clone());
        let path = PathBuf::from(&a.path);
        if !path.exists() {
            missing_landing += 1;
            continue;
        }
        let peek = peek_envelope_prefix(&path)?;
        *completeness_landed
            .entry(peek.completeness.clone())
            .or_insert(0) += 1;
        if peek.l2_unavailable {
            l2_unavail += 1;
        }
        if peek.completeness == "L2_COMPLETE" {
            l2_complete += 1;
        }
        if peek.trade_count > 0 || peek.completeness == "TRADES_ONLY" {
            trade_files += 1;
        }
        if peek.candle_count > 0 || peek.candles_observed {
            candle_observed += 1;
        }
        if peek.settlement {
            settlement_present += 1;
        }
        if peek.malformed_candles {
            malformed_candles += 1;
        }
        if let Some(et) = peek.event_ticker {
            events.insert(et);
        }
    }

    let mut identity_hist: BTreeMap<String, usize> = BTreeMap::new();
    let mut completeness_by_identity: BTreeMap<String, BTreeMap<String, usize>> = BTreeMap::new();
    let mut mapped_pks: BTreeSet<String> = BTreeSet::new();
    let mut by_event: BTreeMap<String, usize> = BTreeMap::new();
    for p in identity.by_ticker.values() {
        let id = match p.mapping {
            IdentityMapping::Mapped => "MATCHED",
            IdentityMapping::Ambiguous => "AMBIGUOUS",
            IdentityMapping::Unmatched | IdentityMapping::Observed => "UNMATCHED",
        };
        *identity_hist.entry(id.into()).or_insert(0) += 1;
        let comp = match p.completeness {
            Some(IngestCompleteness::TradesOnly) => "TRADES_ONLY",
            Some(IngestCompleteness::CandlesOnly) => "CANDLES_ONLY",
            Some(IngestCompleteness::MarketMetadataOnly) => "MARKET_METADATA_ONLY",
            Some(IngestCompleteness::L2Complete) => "L2_COMPLETE",
            Some(IngestCompleteness::L2Partial) => "L2_PARTIAL",
            None => "NONE",
        };
        *completeness_by_identity
            .entry(id.into())
            .or_default()
            .entry(comp.to_string())
            .or_insert(0) += 1;
        if p.mapping == IdentityMapping::Mapped {
            if let Some(pk) = &p.game_pk {
                mapped_pks.insert(pk.clone());
            }
        }
        if let Some(et) = &p.event_ticker {
            if !p.ticker.is_empty() {
                *by_event.entry(et.clone()).or_insert(0) += 1;
            }
        }
    }
    // Unmatched PBP rows live in the pairs file with empty ticker; count mapping only.
    let pairs_raw: Vec<GameMarketPair> = serde_json::from_str(&fs::read_to_string(&pairs_path)?)?;
    let unmatched_pbp = pairs_raw
        .iter()
        .filter(|p| p.mapping == IdentityMapping::Unmatched && p.ticker.is_empty())
        .count();
    if unmatched_pbp > 0 {
        *identity_hist
            .entry("UNMATCHED_PBP_NO_TICKER".into())
            .or_insert(0) += unmatched_pbp;
    }

    let coupled_both = by_event.values().filter(|n| **n >= 2).count();
    let coupled_one = by_event.values().filter(|n| **n == 1).count();

    let dup_path = handoff_path.with_file_name("duplicate_report.json");
    let already_known = if dup_path.exists() {
        let v: serde_json::Value = serde_json::from_str(&fs::read_to_string(&dup_path)?)?;
        v.as_array().map(|a| a.len()).unwrap_or(0)
    } else {
        0
    };

    let (lake_complete, lake_missing) = lake_manifest_counts(lake_root);

    let date_start = dates.first().map(|d| d.to_string());
    let date_end = dates.last().map(|d| d.to_string());
    let span = match (dates.first(), dates.last()) {
        (Some(a), Some(b)) => (*b - *a).num_days(),
        _ => 0,
    };

    let report = UniverseInventory {
        waterfall: WATERFALL.into(),
        artifact_version: ARTIFACT_VERSION.into(),
        inventory_kind: "DISCOVERY_PREFIX_SCAN".into(),
        source_run: handoff.run_id.clone(),
        sport: "MLB".into(),
        series: SERIES_MLB.into(),
        unique_markets: tickers.len(),
        unique_event_tickers: events.len().max(by_event.len()),
        unique_mapped_games_game_pk: mapped_pks.len(),
        date_start,
        date_end,
        partition_dates: dates.len(),
        calendar_span_days: span,
        seasons,
        identity: identity_hist,
        completeness_landed,
        completeness_by_identity,
        coupled_events_both_yes: coupled_both,
        coupled_events_one_yes: coupled_one,
        trade_files,
        candle_observed_files: candle_observed,
        l2_complete_files: l2_complete,
        l2_historical_unavailable: l2_unavail,
        settlement_metadata_present: settlement_present,
        malformed_candlestick_payloads: malformed_candles,
        missing_landing_files: missing_landing,
        already_known_duplicates: already_known,
        lake_mlb_complete_days: lake_complete,
        lake_mlb_missing_days: lake_missing,
        notes: vec![
            "NO L2 = DO NOT INVENT L2. TRADES_ONLY retained as valid price-path research.".into(),
            "Inventory is a prefix scan of committed envelopes; full path reconstruct was not run for 8k tickers.".into(),
            "Mapped pairs are mostly MARKET_METADATA_ONLY (trades not requested on identity pass).".into(),
            "2024 Kalshi UNAVAILABLE: catalog begins ~2025-04-16.".into(),
            "W4 GATE STILL BLOCKED: universe is not a reconstructed market engine; L2 is UNAVAILABLE; CTO has not ACCEPTED.".into(),
        ],
        w4_gate: "BLOCKED".into(),
        price_paths_reconstructed: None,
        reconstructable_trades_only: None,
    };

    fs::create_dir_all(out_dir)?;
    let body = serde_json::to_string_pretty(&report)?;
    fs::write(out_dir.join("universe_inventory.json"), body)?;
    Ok(report)
}

pub(crate) struct PrefixPeek {
    completeness: String,
    l2_unavailable: bool,
    trade_count: u64,
    candle_count: u64,
    candles_observed: bool,
    settlement: bool,
    malformed_candles: bool,
    event_ticker: Option<String>,
}

impl PrefixPeek {
    pub(crate) fn completeness(&self) -> &str {
        &self.completeness
    }

    pub(crate) fn is_price_path_candidate(&self) -> bool {
        matches!(
            self.completeness.as_str(),
            "TRADES_ONLY" | "CANDLES_ONLY" | "L2_PARTIAL" | "L2_COMPLETE"
        )
    }
}

pub(crate) fn peek_envelope_prefix(path: &Path) -> Result<PrefixPeek, W4Error> {
    let mut f = File::open(path)?;
    let mut buf = vec![0u8; PEEK_BYTES];
    let n = f.read(&mut buf)?;
    let s = String::from_utf8_lossy(&buf[..n]);
    Ok(PrefixPeek {
        completeness: extract_string(&s, "\"completeness\":\"")
            .unwrap_or("UNKNOWN")
            .to_string(),
        l2_unavailable: s.contains("HISTORICAL_L2_UNAVAILABLE"),
        trade_count: extract_u64(&s, "\"trade_count\":").unwrap_or(0),
        candle_count: extract_u64(&s, "\"candle_count\":").unwrap_or(0),
        candles_observed: s.contains("\"candles_status\":\"OBSERVED")
            || s.contains("\"candles_status\":\"OBSERVED_HISTORICAL"),
        settlement: s.contains("\"settlement_ts\"") || s.contains("\"result\""),
        malformed_candles: s.contains("malformed venue response"),
        event_ticker: extract_string(&s, "\"event_ticker\":\"").map(str::to_string),
    })
}

fn extract_string<'a>(s: &'a str, key: &str) -> Option<&'a str> {
    let i = s.find(key)?;
    let rest = &s[i + key.len()..];
    rest.split('"').next().filter(|v| !v.is_empty())
}

fn extract_u64(s: &str, key: &str) -> Option<u64> {
    let i = s.find(key)?;
    let rest = &s[i + key.len()..];
    let num: String = rest.chars().take_while(|c| c.is_ascii_digit()).collect();
    num.parse().ok()
}

fn lake_manifest_counts(lake_root: &Path) -> (usize, usize) {
    let dir = lake_root.join("MLB/2025-2026/manifests");
    let Ok(rd) = fs::read_dir(dir) else {
        return (0, 0);
    };
    let mut complete = 0usize;
    let mut missing = 0usize;
    for e in rd.flatten() {
        let p = e.path();
        if p.extension().and_then(|s| s.to_str()) != Some("json") {
            continue;
        }
        let Ok(body) = fs::read_to_string(&p) else {
            continue;
        };
        if body.contains("\"completeness_status\": \"COMPLETE\"")
            || body.contains("\"completeness_status\":\"COMPLETE\"")
        {
            complete += 1;
        } else if body.contains("MISSING") {
            missing += 1;
        }
    }
    (complete, missing)
}
