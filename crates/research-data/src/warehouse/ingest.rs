//! Resumable raw download of events, markets, candles, and trades.

use std::fs;
use std::path::Path;

use chrono::Utc;
use flate2::Compression;
use flate2::write::GzEncoder;
use serde_json::Value;
use std::io::Write;

use crate::checksum::sha256_file;
use crate::raw::RawArchiveWriter;

use super::catalog::{cutoff_unix, market_window_ts};
use super::config::WarehouseConfig;
use super::error::WarehouseError;
use super::http::RetryingClient;
use super::paths::WarehousePaths;
use super::types::{IngestionManifest, JobStatus};

pub fn load_manifest(paths: &WarehousePaths) -> IngestionManifest {
    let p = paths.ingestion_manifest();
    match fs::read_to_string(p) {
        Ok(s) => serde_json::from_str(&s).unwrap_or_default(),
        Err(_) => IngestionManifest::default(),
    }
}

pub fn save_manifest(
    paths: &WarehousePaths,
    manifest: &IngestionManifest,
) -> Result<(), WarehouseError> {
    let bytes = serde_json::to_vec_pretty(manifest)?;
    paths.write_atomic(&paths.ingestion_manifest(), &bytes)?;
    Ok(())
}

pub fn download_cutoff(
    client: &RetryingClient,
    paths: &WarehousePaths,
) -> Result<Value, WarehouseError> {
    let body = client.get_json("/trade-api/v2/historical/cutoff")?;
    paths.write_atomic(&paths.cutoff_path(), &serde_json::to_vec_pretty(&body)?)?;
    Ok(body)
}

pub fn download_events(
    client: &RetryingClient,
    paths: &WarehousePaths,
    config: &WarehouseConfig,
) -> Result<(Vec<Value>, u32), WarehouseError> {
    let query = format!("series_ticker={}&limit=200", config.series);
    let (events, pages) = client.paginate("/trade-api/v2/events", &query, "events", 500)?;
    write_jsonl_gz(&paths.raw_events().join("events.jsonl.gz"), &events)?;
    Ok((events, pages))
}

pub fn download_markets(
    client: &RetryingClient,
    paths: &WarehousePaths,
    config: &WarehouseConfig,
) -> Result<(Vec<Value>, u32), WarehouseError> {
    let hist_q = format!("series_ticker={}&limit=1000", config.series);
    let (mut markets, hist_pages) =
        client.paginate("/trade-api/v2/historical/markets", &hist_q, "markets", 500)?;
    let live_q = format!("series_ticker={}&limit=1000", config.series);
    let (live, live_pages) = client.paginate("/trade-api/v2/markets", &live_q, "markets", 500)?;
    let mut seen = std::collections::BTreeSet::new();
    markets.retain(|m| {
        m.get("ticker")
            .and_then(|t| t.as_str())
            .is_some_and(|t| seen.insert(t.to_string()))
    });
    for m in live {
        if let Some(t) = m.get("ticker").and_then(|t| t.as_str())
            && seen.insert(t.to_string())
        {
            markets.push(m);
        }
    }
    write_jsonl_gz(&paths.raw_markets().join("markets.jsonl.gz"), &markets)?;
    Ok((markets, hist_pages + live_pages))
}

pub fn load_raw_array(path: &Path) -> Result<Vec<Value>, WarehouseError> {
    if !path.exists() {
        return Ok(Vec::new());
    }
    let file = fs::File::open(path)?;
    let reader = std::io::BufReader::new(flate2::read::GzDecoder::new(file));
    let mut out = Vec::new();
    for line in std::io::BufRead::lines(reader) {
        let line = line?;
        if line.trim().is_empty() {
            continue;
        }
        out.push(serde_json::from_str(&line)?);
    }
    Ok(out)
}

pub fn download_candles_for_market(
    client: &RetryingClient,
    paths: &WarehousePaths,
    config: &WarehouseConfig,
    market: &Value,
    cutoff: &Value,
    manifest: &std::sync::Mutex<IngestionManifest>,
) -> Result<u64, WarehouseError> {
    let ticker = market
        .get("ticker")
        .and_then(|t| t.as_str())
        .ok_or_else(|| WarehouseError::Schema("market missing ticker".into()))?
        .to_string();
    let event = market
        .get("event_ticker")
        .and_then(|t| t.as_str())
        .unwrap_or("")
        .to_string();
    {
        let mut man = manifest.lock().unwrap_or_else(|e| e.into_inner());
        if let Some(job) = man.job(&ticker, "candles")
            && job.status == JobStatus::Complete.as_str()
        {
            return Ok(job.row_count);
        }
        let job = man.job_mut(&ticker, "candles");
        job.event_ticker = event;
        job.status = JobStatus::Downloading.as_str().into();
        job.started_at = Some(Utc::now());
        job.attempts += 1;
    }

    let (start, end) = market_window_ts(market);
    let settled = market
        .get("settlement_ts")
        .and_then(|s| s.as_str())
        .and_then(super::types::parse_rfc3339)
        .map(|t| t.timestamp());
    let historical = cutoff_unix(cutoff).is_some_and(|c| settled.unwrap_or(end) < c);
    let period = config.candle_period_minutes;

    match fetch_candles(
        client,
        &config.series,
        &ticker,
        start,
        end,
        period,
        historical,
    ) {
        Ok(candles) => {
            let dir = paths.raw_candles(&ticker);
            fs::create_dir_all(&dir)?;
            let file = dir.join("candles.jsonl.gz");
            let mut writer = RawArchiveWriter::create(&file)?;
            writer.append_payload(
                if historical {
                    "historical_rest"
                } else {
                    "rest"
                },
                "candlesticks",
                Some(&ticker),
                serde_json::json!({ "ticker": ticker, "candlesticks": candles }),
            )?;
            let summary = writer.finish()?;
            let n = candles.as_array().map(|a| a.len() as u64).unwrap_or(0);
            let mut man = manifest.lock().unwrap_or_else(|e| e.into_inner());
            let job = man.job_mut(&ticker, "candles");
            job.status = JobStatus::Complete.as_str().into();
            job.completed_at = Some(Utc::now());
            job.row_count = n;
            job.error = None;
            job.checksum = sha256_file(&summary.path).ok();
            Ok(n)
        }
        Err(err) => {
            let mut man = manifest.lock().unwrap_or_else(|e| e.into_inner());
            let job = man.job_mut(&ticker, "candles");
            job.status = JobStatus::Failed.as_str().into();
            job.error = Some(err.to_string());
            Err(err)
        }
    }
}

/// Kalshi candlestick endpoints reject windows that would return more than
/// 5000 bars (`max candlesticks: 5000`). Split before requesting.
const MAX_CANDLES_PER_REQUEST: i64 = 4900;

pub(crate) fn candle_span_exceeds_api_limit(start: i64, end: i64, period_minutes: u32) -> bool {
    let step = i64::from(period_minutes.max(1)) * 60;
    if step <= 0 || end <= start {
        return false;
    }
    (end - start) / step > MAX_CANDLES_PER_REQUEST
}

fn fetch_candles(
    client: &RetryingClient,
    series: &str,
    ticker: &str,
    start: i64,
    end: i64,
    period: u32,
    historical: bool,
) -> Result<Value, WarehouseError> {
    if end <= start {
        return Ok(Value::Array(Vec::new()));
    }
    if candle_span_exceeds_api_limit(start, end, period) {
        let mid = start + (end - start) / 2;
        let a = fetch_candles(client, series, ticker, start, mid, period, historical)?;
        let b = fetch_candles(client, series, ticker, mid, end, period, historical)?;
        return Ok(merge_candle_arrays(a, b));
    }
    let path = if historical {
        format!(
            "/trade-api/v2/historical/markets/{ticker}/candlesticks?start_ts={start}&end_ts={end}&period_interval={period}"
        )
    } else {
        format!(
            "/trade-api/v2/series/{series}/markets/{ticker}/candlesticks?start_ts={start}&end_ts={end}&period_interval={period}"
        )
    };
    let body = match client.get_json(&path) {
        Ok(v) => v,
        Err(_) if end - start > 3_600 => {
            let mid = start + (end - start) / 2;
            let a = fetch_candles(client, series, ticker, start, mid, period, historical)?;
            let b = fetch_candles(client, series, ticker, mid, end, period, historical)?;
            return Ok(merge_candle_arrays(a, b));
        }
        Err(e) => return Err(e),
    };
    Ok(body
        .get("candlesticks")
        .cloned()
        .unwrap_or_else(|| Value::Array(Vec::new())))
}

fn merge_candle_arrays(a: Value, b: Value) -> Value {
    let mut out = Vec::new();
    if let Some(arr) = a.as_array() {
        out.extend(arr.iter().cloned());
    }
    if let Some(arr) = b.as_array() {
        out.extend(arr.iter().cloned());
    }
    Value::Array(out)
}

pub fn download_trades_for_market(
    client: &RetryingClient,
    paths: &WarehousePaths,
    market: &Value,
    cutoff: &Value,
    manifest: &std::sync::Mutex<IngestionManifest>,
) -> Result<u64, WarehouseError> {
    let ticker = market
        .get("ticker")
        .and_then(|t| t.as_str())
        .ok_or_else(|| WarehouseError::Schema("market missing ticker".into()))?
        .to_string();
    let event = market
        .get("event_ticker")
        .and_then(|t| t.as_str())
        .unwrap_or("")
        .to_string();
    let mut cursor = {
        let mut man = manifest.lock().unwrap_or_else(|e| e.into_inner());
        if let Some(job) = man.job(&ticker, "trades")
            && job.status == JobStatus::Complete.as_str()
        {
            return Ok(job.row_count);
        }
        let existing_cursor = man.job(&ticker, "trades").and_then(|j| j.cursor.clone());
        let job = man.job_mut(&ticker, "trades");
        job.event_ticker = event;
        job.status = JobStatus::Downloading.as_str().into();
        job.started_at = Some(Utc::now());
        job.attempts += 1;
        existing_cursor
    };

    let (start, end) = market_window_ts(market);
    let settled = market
        .get("settlement_ts")
        .and_then(|s| s.as_str())
        .and_then(super::types::parse_rfc3339)
        .map(|t| t.timestamp());
    let historical = cutoff_unix(cutoff).is_some_and(|c| settled.unwrap_or(end) < c);
    let base = if historical {
        "/trade-api/v2/historical/trades"
    } else {
        "/trade-api/v2/markets/trades"
    };

    let dir = paths.raw_trades(&ticker);
    if cursor.is_none() && dir.exists() {
        let _ = fs::remove_dir_all(&dir);
    }
    fs::create_dir_all(&dir)?;
    let mut total = if cursor.is_some() {
        manifest
            .lock()
            .unwrap_or_else(|e| e.into_inner())
            .job(&ticker, "trades")
            .map(|j| j.row_count)
            .unwrap_or(0)
    } else {
        0
    };
    let mut page_idx = if cursor.is_some() {
        count_existing_pages(&dir)
    } else {
        0
    };
    loop {
        let mut q = format!("ticker={ticker}&min_ts={start}&max_ts={end}&limit=1000");
        if let Some(c) = &cursor {
            q.push_str(&format!("&cursor={c}"));
        }
        let body = match client.get_json(&format!("{base}?{q}")) {
            Ok(v) => v,
            Err(err) => {
                let mut man = manifest.lock().unwrap_or_else(|e| e.into_inner());
                let job = man.job_mut(&ticker, "trades");
                job.status = JobStatus::Retry.as_str().into();
                job.error = Some(err.to_string());
                job.cursor = cursor;
                job.row_count = total;
                return Err(err);
            }
        };
        let trades = body
            .get("trades")
            .and_then(|t| t.as_array())
            .cloned()
            .unwrap_or_default();
        if !trades.is_empty() {
            page_idx += 1;
            let page_path = dir.join(format!("page-{page_idx:04}.jsonl.gz"));
            write_jsonl_gz(&page_path, &trades)?;
            total += trades.len() as u64;
        }
        cursor = body
            .get("cursor")
            .and_then(|c| c.as_str())
            .filter(|s| !s.is_empty())
            .map(str::to_string);
        {
            let mut man = manifest.lock().unwrap_or_else(|e| e.into_inner());
            let job = man.job_mut(&ticker, "trades");
            job.cursor = cursor.clone();
            job.row_count = total;
            if cursor.is_none() {
                job.status = JobStatus::Complete.as_str().into();
                job.completed_at = Some(Utc::now());
                job.error = None;
            }
        }
        if cursor.is_none() {
            break;
        }
    }
    Ok(total)
}

fn count_existing_pages(dir: &Path) -> u32 {
    let Ok(rd) = fs::read_dir(dir) else {
        return 0;
    };
    rd.filter_map(|e| e.ok())
        .filter(|e| e.file_name().to_string_lossy().starts_with("page-"))
        .count() as u32
}

fn write_jsonl_gz(path: &Path, rows: &[Value]) -> Result<(), WarehouseError> {
    if let Some(parent) = path.parent() {
        fs::create_dir_all(parent)?;
    }
    let file = fs::File::create(path)?;
    let mut enc = GzEncoder::new(file, Compression::default());
    for row in rows {
        writeln!(enc, "{}", serde_json::to_string(row)?)?;
    }
    enc.finish()?;
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::candle_span_exceeds_api_limit;

    #[test]
    fn splits_windows_over_5000_one_minute_bars() {
        assert!(!candle_span_exceeds_api_limit(0, 4900 * 60, 1));
        assert!(candle_span_exceeds_api_limit(0, 4901 * 60, 1));
        assert!(candle_span_exceeds_api_limit(0, 6311 * 60, 1));
        assert!(candle_span_exceeds_api_limit(0, 8730 * 60, 1));
    }
}
