//! Read-only integrity verification of v1 lake artifacts (W1-A3).
//! Never repairs raw files.

use std::collections::{BTreeMap, BTreeSet, HashSet};
use std::fs::File;
use std::io::{BufRead, BufReader};
use std::path::{Path, PathBuf};

use chrono::NaiveDate;
use flate2::read::GzDecoder;
use parquet::arrow::arrow_reader::ParquetRecordBatchReaderBuilder;
use serde::{Deserialize, Serialize};

use crate::checksum::sha256_file;
use crate::manifest::DailyManifest;
use crate::paths::ResearchPaths;
use crate::schema::{RawMarketEvent, SCHEMA_VERSION};
use crate::sport::ResearchSport;

use super::coverage::CoverageRecord;
use super::identity_stub::IdentityStubV1;

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum IntegritySeverity {
    Info,
    Warning,
    Error,
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct IntegrityFinding {
    pub severity: IntegritySeverity,
    pub code: String,
    pub partition_date: Option<String>,
    pub path: Option<String>,
    pub message: String,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct PartitionIntegrity {
    pub sport: String,
    pub date: NaiveDate,
    pub v1_completeness: crate::manifest::CompletenessStatus,
    pub markets_discovered: u32,
    pub markets_collected: u32,
    pub trade_count: u64,
    pub orderbook_event_count: u64,
    pub checksum_ok: bool,
    pub gzip_readable: bool,
    pub gzip_malformed_lines: u64,
    pub gzip_line_count: u64,
    pub parquet_readable: bool,
    pub unique_tickers: u32,
    pub unique_event_tickers: u32,
    pub pairing_ok: bool,
    pub unpaired_event_tickers: u32,
    pub trade_id_duplicates: u64,
    pub chronological_decreases: u64,
    pub settlement_result_rows: u32,
    pub metadata_rows: u32,
    pub identity_stubs: Vec<IdentityStubV1>,
    pub coverage: CoverageRecord,
    pub findings: Vec<IntegrityFinding>,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct IntegrityReport {
    pub schema_version_expected: String,
    pub partitions: Vec<PartitionIntegrity>,
    pub findings: Vec<IntegrityFinding>,
    pub checksum_mismatches: u32,
    pub gzip_failures: u32,
    pub parquet_failures: u32,
    pub pairing_failures: u32,
}

pub fn verify_sport(
    paths: &ResearchPaths,
    sport: ResearchSport,
) -> std::io::Result<IntegrityReport> {
    let mut report = IntegrityReport {
        schema_version_expected: SCHEMA_VERSION.to_string(),
        partitions: Vec::new(),
        findings: Vec::new(),
        checksum_mismatches: 0,
        gzip_failures: 0,
        parquet_failures: 0,
        pairing_failures: 0,
    };
    let dates = crate::manifest::list_manifest_dates(paths, sport)?;
    for date in dates {
        let part = verify_partition(paths, sport, date)?;
        if !part.checksum_ok {
            report.checksum_mismatches += 1;
        }
        if !part.gzip_readable {
            report.gzip_failures += 1;
        }
        if !part.parquet_readable {
            report.parquet_failures += 1;
        }
        if !part.pairing_ok {
            report.pairing_failures += 1;
        }
        report.findings.extend(part.findings.clone());
        report.partitions.push(part);
    }
    Ok(report)
}

fn verify_partition(
    paths: &ResearchPaths,
    sport: ResearchSport,
    date: NaiveDate,
) -> std::io::Result<PartitionIntegrity> {
    let mut findings = Vec::new();
    let manifest = DailyManifest::read(paths, sport, date)?;
    let Some(manifest) = manifest else {
        findings.push(finding(
            IntegritySeverity::Warning,
            "MANIFEST_ABSENT",
            Some(date),
            None,
            "Date directory exists without a readable v1 manifest",
        ));
        return Ok(empty_partition(sport, date, findings));
    };

    let raw_path = paths.raw_day(sport, date).join("events.jsonl.gz");
    let meta_path = paths.orderbook_day(sport, date).join("metadata.parquet");
    let ob_path = paths.orderbook_day(sport, date).join("orderbook.parquet");
    let tr_path = paths.trades_day(sport, date).join("trades.parquet");

    let mut checksum_ok = true;
    for (name, path) in [
        ("events.jsonl.gz", &raw_path),
        ("metadata.parquet", &meta_path),
        ("orderbook.parquet", &ob_path),
        ("trades.parquet", &tr_path),
    ] {
        if !path.exists() {
            if manifest.markets_discovered > 0 {
                findings.push(finding(
                    IntegritySeverity::Error,
                    "FILE_MISSING",
                    Some(date),
                    Some(path),
                    format!("expected {name} missing"),
                ));
                checksum_ok = false;
            }
            continue;
        }
        let actual = sha256_file(path)?;
        match manifest.checksums.get(name) {
            Some(expected) if expected == &actual => {}
            Some(expected) => {
                checksum_ok = false;
                findings.push(finding(
                    IntegritySeverity::Error,
                    "CHECKSUM_MISMATCH",
                    Some(date),
                    Some(path),
                    format!("manifest {expected} != actual {actual} (no repair applied)"),
                ));
            }
            None => {
                findings.push(finding(
                    IntegritySeverity::Warning,
                    "CHECKSUM_ABSENT",
                    Some(date),
                    Some(path),
                    "v1 manifest has no checksum for this file",
                ));
            }
        }
    }

    let (gzip_readable, gzip_line_count, gzip_malformed_lines, gzip_findings) =
        inspect_gzip(&raw_path, date);
    findings.extend(gzip_findings);
    if !gzip_readable {
        // Empty probes still count as readable if the decoder succeeds.
    }

    let meta = inspect_metadata_parquet(&meta_path, date);
    findings.extend(meta.findings.clone());

    let trades = inspect_trades_parquet(&tr_path, date);
    findings.extend(trades.findings.clone());

    let ob = inspect_orderbook_parquet(&ob_path, date);
    findings.extend(ob.findings.clone());

    let parquet_readable = meta.readable && trades.readable && ob.readable;
    let pairing_ok = meta.unpaired_events == 0;
    if !pairing_ok {
        findings.push(finding(
            IntegritySeverity::Error,
            "PAIRING_NOT_TWO_SIDED",
            Some(date),
            Some(&meta_path),
            format!(
                "{} event_tickers do not have exactly 2 contracts",
                meta.unpaired_events
            ),
        ));
    }

    if manifest.schema_version != SCHEMA_VERSION {
        findings.push(finding(
            IntegritySeverity::Warning,
            "SCHEMA_VERSION_MISMATCH",
            Some(date),
            None,
            format!(
                "manifest schema {} != crate {}",
                manifest.schema_version, SCHEMA_VERSION
            ),
        ));
    }

    let coverage = CoverageRecord::for_kalshi_v1_partition(
        manifest.completeness_status,
        manifest.markets_discovered,
        manifest.trade_count,
        manifest.orderbook_event_count,
        meta.settlement_result_rows,
        meta.metadata_rows,
    );

    Ok(PartitionIntegrity {
        sport: sport.dir_name().to_string(),
        date,
        v1_completeness: manifest.completeness_status,
        markets_discovered: manifest.markets_discovered,
        markets_collected: manifest.markets_collected,
        trade_count: manifest.trade_count,
        orderbook_event_count: manifest.orderbook_event_count,
        checksum_ok,
        gzip_readable,
        gzip_malformed_lines,
        gzip_line_count,
        parquet_readable,
        unique_tickers: meta.tickers.len() as u32,
        unique_event_tickers: meta.event_tickers.len() as u32,
        pairing_ok,
        unpaired_event_tickers: meta.unpaired_events,
        trade_id_duplicates: trades.duplicate_ids,
        chronological_decreases: trades.chrono_decreases,
        settlement_result_rows: meta.settlement_result_rows,
        metadata_rows: meta.metadata_rows,
        identity_stubs: meta.stubs,
        coverage,
        findings,
    })
}

fn empty_partition(
    sport: ResearchSport,
    date: NaiveDate,
    findings: Vec<IntegrityFinding>,
) -> PartitionIntegrity {
    let coverage = CoverageRecord::for_kalshi_v1_partition(
        crate::manifest::CompletenessStatus::Missing,
        0,
        0,
        0,
        0,
        0,
    );
    PartitionIntegrity {
        sport: sport.dir_name().to_string(),
        date,
        v1_completeness: crate::manifest::CompletenessStatus::Missing,
        markets_discovered: 0,
        markets_collected: 0,
        trade_count: 0,
        orderbook_event_count: 0,
        checksum_ok: false,
        gzip_readable: false,
        gzip_malformed_lines: 0,
        gzip_line_count: 0,
        parquet_readable: false,
        unique_tickers: 0,
        unique_event_tickers: 0,
        pairing_ok: true,
        unpaired_event_tickers: 0,
        trade_id_duplicates: 0,
        chronological_decreases: 0,
        settlement_result_rows: 0,
        metadata_rows: 0,
        identity_stubs: Vec::new(),
        coverage,
        findings,
    }
}

fn inspect_gzip(path: &Path, date: NaiveDate) -> (bool, u64, u64, Vec<IntegrityFinding>) {
    let mut findings = Vec::new();
    if !path.exists() {
        return (true, 0, 0, findings);
    }
    let file = match File::open(path) {
        Ok(f) => f,
        Err(e) => {
            findings.push(finding(
                IntegritySeverity::Error,
                "GZIP_OPEN_FAIL",
                Some(date),
                Some(path),
                e.to_string(),
            ));
            return (false, 0, 0, findings);
        }
    };
    let reader = BufReader::new(GzDecoder::new(file));
    let mut lines = 0u64;
    let mut malformed = 0u64;
    for line in reader.lines() {
        let Ok(line) = line else {
            malformed += 1;
            continue;
        };
        if line.trim().is_empty() {
            continue;
        }
        lines += 1;
        if serde_json::from_str::<RawMarketEvent>(&line).is_err() {
            malformed += 1;
        }
    }
    if malformed > 0 {
        findings.push(finding(
            IntegritySeverity::Error,
            "GZIP_MALFORMED_JSONL",
            Some(date),
            Some(path),
            format!("{malformed} malformed lines (left unrepaired)"),
        ));
    }
    (malformed == 0, lines, malformed, findings)
}

struct MetaInspect {
    readable: bool,
    metadata_rows: u32,
    settlement_result_rows: u32,
    tickers: BTreeSet<String>,
    event_tickers: BTreeSet<String>,
    unpaired_events: u32,
    stubs: Vec<IdentityStubV1>,
    findings: Vec<IntegrityFinding>,
}

fn inspect_metadata_parquet(path: &Path, date: NaiveDate) -> MetaInspect {
    let mut out = MetaInspect {
        readable: true,
        metadata_rows: 0,
        settlement_result_rows: 0,
        tickers: BTreeSet::new(),
        event_tickers: BTreeSet::new(),
        unpaired_events: 0,
        stubs: Vec::new(),
        findings: Vec::new(),
    };
    if !path.exists() {
        return out;
    }
    let file = match File::open(path) {
        Ok(f) => f,
        Err(e) => {
            out.readable = false;
            out.findings.push(finding(
                IntegritySeverity::Error,
                "PARQUET_OPEN_FAIL",
                Some(date),
                Some(path),
                e.to_string(),
            ));
            return out;
        }
    };
    let builder = match ParquetRecordBatchReaderBuilder::try_new(file) {
        Ok(b) => b,
        Err(e) => {
            out.readable = false;
            out.findings.push(finding(
                IntegritySeverity::Error,
                "PARQUET_SCHEMA_FAIL",
                Some(date),
                Some(path),
                e.to_string(),
            ));
            return out;
        }
    };
    let reader = match builder.build() {
        Ok(r) => r,
        Err(e) => {
            out.readable = false;
            out.findings.push(finding(
                IntegritySeverity::Error,
                "PARQUET_READER_FAIL",
                Some(date),
                Some(path),
                e.to_string(),
            ));
            return out;
        }
    };
    let mut by_event: BTreeMap<String, BTreeSet<String>> = BTreeMap::new();
    for batch in reader {
        let Ok(batch) = batch else {
            out.readable = false;
            out.findings.push(finding(
                IntegritySeverity::Error,
                "PARQUET_BATCH_FAIL",
                Some(date),
                Some(path),
                "metadata batch read failed",
            ));
            continue;
        };
        let ticker = col_str(&batch, "ticker");
        let event = col_str(&batch, "event_ticker");
        let game = col_str(&batch, "game_id");
        let market = col_str(&batch, "market_id");
        let series = col_str(&batch, "series_ticker");
        let result = col_str(&batch, "result");
        let open_time = col_str(&batch, "open_time");
        let Some(ticker) = ticker else {
            out.readable = false;
            out.findings.push(finding(
                IntegritySeverity::Error,
                "PARQUET_MISSING_COLUMN",
                Some(date),
                Some(path),
                "metadata.ticker",
            ));
            continue;
        };
        let n = batch.num_rows();
        out.metadata_rows += n as u32;
        for i in 0..n {
            let t = ticker.value(i).to_string();
            out.tickers.insert(t.clone());
            let et = event.map(|a| a.value(i).to_string()).unwrap_or_default();
            if !et.is_empty() {
                out.event_tickers.insert(et.clone());
                by_event.entry(et.clone()).or_default().insert(t.clone());
            }
            if let Some(r) = result {
                let v = r.value(i);
                if !v.is_empty() {
                    out.settlement_result_rows += 1;
                }
            }
            let mut stub = IdentityStubV1::unmapped(
                game.map(|a| a.value(i).to_string()).unwrap_or_default(),
                market.map(|a| a.value(i).to_string()).unwrap_or_default(),
                t,
                et,
                series.map(|a| a.value(i).to_string()).unwrap_or_default(),
            );
            if let Some(ot) = open_time {
                let v = ot.value(i);
                if !v.is_empty() {
                    stub.open_time = Some(v.to_string());
                }
            }
            out.stubs.push(stub);
        }
    }
    out.unpaired_events = by_event.values().filter(|set| set.len() != 2).count() as u32;
    out
}

struct TradeInspect {
    readable: bool,
    duplicate_ids: u64,
    chrono_decreases: u64,
    findings: Vec<IntegrityFinding>,
}

fn inspect_trades_parquet(path: &Path, date: NaiveDate) -> TradeInspect {
    let mut out = TradeInspect {
        readable: true,
        duplicate_ids: 0,
        chrono_decreases: 0,
        findings: Vec::new(),
    };
    if !path.exists() {
        return out;
    }
    let file = match File::open(path) {
        Ok(f) => f,
        Err(e) => {
            out.readable = false;
            out.findings.push(finding(
                IntegritySeverity::Error,
                "PARQUET_OPEN_FAIL",
                Some(date),
                Some(path),
                e.to_string(),
            ));
            return out;
        }
    };
    let builder = match ParquetRecordBatchReaderBuilder::try_new(file) {
        Ok(b) => b,
        Err(e) => {
            out.readable = false;
            out.findings.push(finding(
                IntegritySeverity::Error,
                "PARQUET_SCHEMA_FAIL",
                Some(date),
                Some(path),
                e.to_string(),
            ));
            return out;
        }
    };
    let reader = match builder.build() {
        Ok(r) => r,
        Err(e) => {
            out.readable = false;
            out.findings.push(finding(
                IntegritySeverity::Error,
                "PARQUET_READER_FAIL",
                Some(date),
                Some(path),
                e.to_string(),
            ));
            return out;
        }
    };
    let mut seen = HashSet::new();
    let mut last_ts: Option<String> = None;
    for batch in reader {
        let Ok(batch) = batch else {
            out.readable = false;
            continue;
        };
        let Some(ids) = col_str(&batch, "trade_id") else {
            out.readable = false;
            out.findings.push(finding(
                IntegritySeverity::Error,
                "PARQUET_MISSING_COLUMN",
                Some(date),
                Some(path),
                "trade_id",
            ));
            continue;
        };
        let ts = col_str(&batch, "exchange_timestamp");
        for i in 0..batch.num_rows() {
            let id = ids.value(i).to_string();
            if !seen.insert(id.clone()) {
                out.duplicate_ids += 1;
            }
            if let Some(ts) = ts {
                let cur = ts.value(i).to_string();
                if let Some(prev) = &last_ts {
                    if cur.as_str() < prev.as_str() {
                        out.chrono_decreases += 1;
                    }
                }
                last_ts = Some(cur);
            }
        }
    }
    if out.duplicate_ids > 0 {
        out.findings.push(finding(
            IntegritySeverity::Error,
            "DUPLICATE_TRADE_ID",
            Some(date),
            Some(path),
            format!(
                "{} duplicate trade_id values (unrepaired)",
                out.duplicate_ids
            ),
        ));
    }
    if out.chrono_decreases > 0 {
        out.findings.push(finding(
            IntegritySeverity::Info,
            "TRADE_NOT_SORTED",
            Some(date),
            Some(path),
            format!(
                "{} timestamp decreases vs file order (not a repair; parquet is not required to be sorted)",
                out.chrono_decreases
            ),
        ));
    }
    out
}

struct ObInspect {
    readable: bool,
    findings: Vec<IntegrityFinding>,
}

fn inspect_orderbook_parquet(path: &Path, date: NaiveDate) -> ObInspect {
    let mut out = ObInspect {
        readable: true,
        findings: Vec::new(),
    };
    if !path.exists() {
        return out;
    }
    let file = match File::open(path) {
        Ok(f) => f,
        Err(e) => {
            out.readable = false;
            out.findings.push(finding(
                IntegritySeverity::Error,
                "PARQUET_OPEN_FAIL",
                Some(date),
                Some(path),
                e.to_string(),
            ));
            return out;
        }
    };
    let builder = match ParquetRecordBatchReaderBuilder::try_new(file) {
        Ok(b) => b,
        Err(e) => {
            out.readable = false;
            out.findings.push(finding(
                IntegritySeverity::Error,
                "PARQUET_SCHEMA_FAIL",
                Some(date),
                Some(path),
                e.to_string(),
            ));
            return out;
        }
    };
    let reader = match builder.build() {
        Ok(r) => r,
        Err(e) => {
            out.readable = false;
            out.findings.push(finding(
                IntegritySeverity::Error,
                "PARQUET_READER_FAIL",
                Some(date),
                Some(path),
                e.to_string(),
            ));
            return out;
        }
    };
    let mut candle_as_l2 = 0u64;
    for batch in reader {
        let Ok(batch) = batch else {
            out.readable = false;
            continue;
        };
        let event_type = col_str(&batch, "event_type");
        let source = col_str(&batch, "source");
        if let (Some(et), Some(src)) = (event_type, source) {
            for i in 0..batch.num_rows() {
                if src.value(i).contains("RestCandlestick") && et.value(i) == "l2_snapshot" {
                    candle_as_l2 += 1;
                }
            }
        }
    }
    if candle_as_l2 > 0 {
        out.findings.push(finding(
            IntegritySeverity::Error,
            "CANDLE_LABELED_L2",
            Some(date),
            Some(path),
            format!("{candle_as_l2} candlestick rows labeled l2_snapshot"),
        ));
    }
    out
}

fn col_str<'a>(
    batch: &'a arrow::record_batch::RecordBatch,
    name: &str,
) -> Option<&'a arrow::array::StringArray> {
    use arrow::array::Array;
    batch
        .column_by_name(name)
        .and_then(|c| c.as_any().downcast_ref::<arrow::array::StringArray>())
}

fn finding(
    severity: IntegritySeverity,
    code: &str,
    date: Option<NaiveDate>,
    path: Option<&Path>,
    message: impl Into<String>,
) -> IntegrityFinding {
    IntegrityFinding {
        severity,
        code: code.to_string(),
        partition_date: date.map(|d| d.to_string()),
        path: path.map(|p| p.display().to_string()),
        message: message.into(),
    }
}

pub fn lake_content_digest(files: &[(PathBuf, String)]) -> String {
    use sha2::{Digest, Sha256};
    let mut hasher = Sha256::new();
    let mut rows: Vec<(String, String)> = files
        .iter()
        .map(|(p, h)| (p.to_string_lossy().to_string(), h.clone()))
        .collect();
    rows.sort();
    for (p, h) in rows {
        hasher.update(p.as_bytes());
        hasher.update([0]);
        hasher.update(h.as_bytes());
        hasher.update([0]);
    }
    format!("{:x}", hasher.finalize())
}
