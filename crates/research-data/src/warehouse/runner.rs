//! Warehouse orchestration: discover → raw ingest → normalize → derive → validate.

use std::collections::{BTreeMap, BTreeSet};
use std::fs;
use std::sync::{Arc, Mutex};

use chrono::Utc;
use serde_json::Value;
use tracing::info;

use crate::checksum::sha256_file;
use crate::paths::ResearchPaths;
use crate::schema::COLLECTOR_VERSION;
use crate::sport::ResearchSeason;

use super::catalog::{
    DiscoveredUniverse, build_tennis_crosswalk, event_row, filter_universe, market_row,
};
use super::config::WarehouseConfig;
use super::derive::{causal_features, complementarity, trade_minute_agg};
use super::error::WarehouseError;
use super::http::RetryingClient;
use super::ingest::{
    download_candles_for_market, download_cutoff, download_events, download_markets,
    download_trades_for_market, load_manifest, load_raw_array, save_manifest,
};
use super::normalize::{
    load_raw_candles_for_ticker, load_raw_trades_for_ticker, month_from_rfc_date, month_from_ts,
    remove_dir_contents,
};
use super::parquet::{
    write_candles, write_causal, write_complementarity, write_events, write_games, write_markets,
    write_trade_agg, write_trades,
};
use super::paths::WarehousePaths;
use super::query::NbaQuery;
use super::types::{
    DatasetManifest, MARKET_DATA_TYPE_CANDLE_TOB, NbaCandleRow, NbaEventRow, NbaGameRow,
    NbaMarketRow, WarehouseReport,
};
use super::validate::render_report;

#[derive(Clone, Debug)]
pub struct DryRunReport {
    pub events: u64,
    pub markets: u64,
    pub games: u64,
    pub estimated_requests: u64,
    pub already_downloaded_candles: u64,
    pub already_downloaded_trades: u64,
    pub pending_candles: u64,
    pub pending_trades: u64,
}

pub struct NbaWarehouse {
    pub config: WarehouseConfig,
    pub paths: WarehousePaths,
    client: RetryingClient,
}

impl NbaWarehouse {
    pub fn open(config: WarehouseConfig, data_dir: Option<std::path::PathBuf>) -> Self {
        let season = ResearchSeason {
            label: config.season.clone(),
        };
        let sport = config.research_sport();
        let paths = match data_dir {
            Some(dir) => WarehousePaths::from_data_dir(&dir, &season.label, sport),
            None => WarehousePaths::new(&ResearchPaths::from_env_or_default(), &season, sport),
        };
        let client = RetryingClient::new(config.requests_per_second, config.retry_attempts);
        Self {
            config,
            paths,
            client,
        }
    }

    pub fn discover(&self) -> Result<DiscoveredUniverse, WarehouseError> {
        let cutoff = download_cutoff(&self.client, &self.paths)?;
        let (events, event_pages) = download_events(&self.client, &self.paths, &self.config)?;
        let (markets, market_pages) = download_markets(&self.client, &self.paths, &self.config)?;
        info!(
            events = events.len(),
            markets = markets.len(),
            event_pages,
            market_pages,
            series = self.config.series.as_str(),
            "game-market discovery complete"
        );
        Ok(DiscoveredUniverse {
            cutoff,
            events,
            markets,
            event_pages,
            market_pages,
        })
    }

    pub fn load_or_discover(&self) -> Result<DiscoveredUniverse, WarehouseError> {
        let events_path = self.paths.raw_events().join("events.jsonl.gz");
        let markets_path = self.paths.raw_markets().join("markets.jsonl.gz");
        if events_path.exists() && markets_path.exists() && self.paths.cutoff_path().exists() {
            let cutoff = serde_json::from_slice(&fs::read(self.paths.cutoff_path())?)?;
            let events = load_raw_array(&events_path)?;
            let markets = load_raw_array(&markets_path)?;
            return Ok(DiscoveredUniverse {
                cutoff,
                events,
                markets,
                event_pages: 0,
                market_pages: 0,
            });
        }
        self.discover()
    }

    pub fn catalog(
        &self,
        universe: &DiscoveredUniverse,
    ) -> (Vec<NbaEventRow>, Vec<NbaMarketRow>, Vec<NbaGameRow>) {
        let now = Utc::now();
        let mut events: Vec<NbaEventRow> = universe
            .events
            .iter()
            .filter_map(|e| event_row(e, now, &self.config))
            .collect();
        let mut seen: BTreeSet<String> = events.iter().map(|e| e.event_id.clone()).collect();
        for m in &universe.markets {
            let et = m
                .get("event_ticker")
                .and_then(|t| t.as_str())
                .unwrap_or("")
                .to_string();
            if et.is_empty() || seen.contains(&et) {
                continue;
            }
            let syn = serde_json::json!({
                "event_ticker": et,
                "series_ticker": m.get("series_ticker").cloned().unwrap_or(Value::String(self.config.series.clone())),
                "title": m.get("title").cloned().unwrap_or(Value::Null),
                "sub_title": m.get("yes_sub_title").cloned().unwrap_or(Value::Null),
                "category": m.get("category").cloned().unwrap_or(Value::Null),
                "mutually_exclusive": true,
            });
            if let Some(row) = event_row(&syn, now, &self.config) {
                seen.insert(row.event_id.clone());
                events.push(row);
            }
        }
        let by_event: BTreeMap<String, &NbaEventRow> =
            events.iter().map(|e| (e.event_id.clone(), e)).collect();
        let markets: Vec<NbaMarketRow> = universe
            .markets
            .iter()
            .filter_map(|m| {
                let et = m.get("event_ticker").and_then(|t| t.as_str()).unwrap_or("");
                market_row(m, by_event.get(et).copied(), now, &self.config)
            })
            .collect();
        filter_universe(&self.config, events, markets)
    }

    pub fn dry_run(&self) -> Result<DryRunReport, WarehouseError> {
        let universe = self.load_or_discover()?;
        let (events, markets, games) = self.catalog(&universe);
        let manifest = load_manifest(&self.paths);
        let mut already_c = 0u64;
        let mut already_t = 0u64;
        for m in &markets {
            if manifest
                .job(&m.ticker, "candles")
                .is_some_and(|j| j.status == "COMPLETE")
            {
                already_c += 1;
            }
            if manifest
                .job(&m.ticker, "trades")
                .is_some_and(|j| j.status == "COMPLETE")
            {
                already_t += 1;
            }
        }
        let pending_c = markets.len() as u64 - already_c;
        let pending_t = if self.config.include_trades {
            markets.len() as u64 - already_t
        } else {
            0
        };
        Ok(DryRunReport {
            events: events.len() as u64,
            markets: markets.len() as u64,
            games: games.len() as u64,
            estimated_requests: pending_c + pending_t + 3,
            already_downloaded_candles: already_c,
            already_downloaded_trades: already_t,
            pending_candles: pending_c,
            pending_trades: pending_t,
        })
    }

    pub fn download_all(&self) -> Result<WarehouseReport, WarehouseError> {
        let universe = self.load_or_discover()?;
        self.download_timeseries(&universe)?;
        self.rebuild_all(&universe)
    }

    pub fn download_timeseries(&self, universe: &DiscoveredUniverse) -> Result<(), WarehouseError> {
        let (_events, markets, _games) = self.catalog(universe);
        let by_ticker: BTreeMap<String, Value> = universe
            .markets
            .iter()
            .filter_map(|m| {
                m.get("ticker")
                    .and_then(|t| t.as_str())
                    .map(|t| (t.to_string(), m.clone()))
            })
            .collect();
        let manifest = Arc::new(Mutex::new(load_manifest(&self.paths)));
        let failed = Arc::new(Mutex::new(0u64));
        let work: Vec<Value> = markets
            .iter()
            .filter_map(|m| by_ticker.get(&m.ticker).cloned())
            .collect();

        let done = Arc::new(std::sync::atomic::AtomicU64::new(0));
        let total = work.len() as u64;
        let chunk = work.len().div_ceil(self.config.max_workers.max(1)).max(1);
        std::thread::scope(|scope| {
            for piece in work.chunks(chunk) {
                let manifest = Arc::clone(&manifest);
                let failed = Arc::clone(&failed);
                let done = Arc::clone(&done);
                let cutoff = universe.cutoff.clone();
                scope.spawn(move || {
                    for market in piece {
                        self.download_one(market, &cutoff, &manifest, &failed, &done, total);
                        let _ = save_manifest(
                            &self.paths,
                            &manifest.lock().unwrap_or_else(|e| e.into_inner()),
                        );
                    }
                });
            }
        });
        save_manifest(
            &self.paths,
            &manifest.lock().unwrap_or_else(|e| e.into_inner()),
        )?;
        Ok(())
    }

    fn download_one(
        &self,
        market: &Value,
        cutoff: &Value,
        manifest: &Arc<Mutex<IngestionManifestLock>>,
        failed: &Arc<Mutex<u64>>,
        done: &Arc<std::sync::atomic::AtomicU64>,
        total: u64,
    ) {
        let ticker = market
            .get("ticker")
            .and_then(|t| t.as_str())
            .unwrap_or("?")
            .to_string();
        if let Err(err) = download_candles_for_market(
            &self.client,
            &self.paths,
            &self.config,
            market,
            cutoff,
            manifest,
        ) {
            *failed.lock().unwrap_or_else(|e| e.into_inner()) += 1;
            tracing::warn!(ticker = ticker.as_str(), error = %err, "candle download failed");
        }
        if self.config.include_trades
            && let Err(err) =
                download_trades_for_market(&self.client, &self.paths, market, cutoff, manifest)
        {
            *failed.lock().unwrap_or_else(|e| e.into_inner()) += 1;
            tracing::warn!(ticker = ticker.as_str(), error = %err, "trade download failed");
        }
        let n = done.fetch_add(1, std::sync::atomic::Ordering::Relaxed) + 1;
        if n == 1 || n % 25 == 0 || n == total {
            info!(
                done = n,
                total,
                ticker,
                series = self.config.series.as_str(),
                "game-market ticker ingest progress"
            );
        }
    }

    pub fn rebuild_all(
        &self,
        universe: &DiscoveredUniverse,
    ) -> Result<WarehouseReport, WarehouseError> {
        let (events, markets, games) = self.catalog(universe);
        write_events(&self.paths.events_parquet(), &events)?;
        write_markets(&self.paths.markets_parquet(), &markets)?;
        write_games(&self.paths.games_parquet(), &games)?;
        self.paths.write_atomic(
            &self.paths.games_json(),
            &serde_json::to_vec_pretty(&games)?,
        )?;
        if self.config.research_sport().is_tennis() {
            self.paths.write_atomic(
                &self.paths.tennis_crosswalk_json(),
                &serde_json::to_vec_pretty(&build_tennis_crosswalk(universe, &events))?,
            )?;
        }

        remove_dir_contents(&self.paths.normalized_dir().join("candles_1m"))?;
        remove_dir_contents(&self.paths.normalized_dir().join("trades"))?;
        remove_dir_contents(&self.paths.derived_dir().join("causal_features"))?;
        remove_dir_contents(&self.paths.derived_dir().join("complementarity"))?;
        remove_dir_contents(&self.paths.derived_dir().join("trade_minute"))?;

        let mut candle_count = 0u64;
        let mut trade_count = 0u64;
        let mut dup_candles = 0u64;
        let mut dup_trades = 0u64;
        let mut with_c = BTreeSet::new();
        let mut with_t = BTreeSet::new();
        let mut earliest = None;
        let mut latest = None;
        let mut coverage_acc = Vec::new();
        let mut extra_anomalies = Vec::new();

        if self.config.research_sport().is_tennis() {
            // Fail closed: sides are never guessed from the event ticker blob,
            // so an unresolved event must be visible in the report.
            for event in &events {
                if event.home_team_code.is_none() || event.away_team_code.is_none() {
                    extra_anomalies.push(format!(
                        "tennis event {} has no market-derived player sides",
                        event.event_ticker
                    ));
                }
            }
        }

        for market in &markets {
            let candles = load_raw_candles_for_ticker(&self.paths, market)?;
            let trades = load_raw_trades_for_ticker(&self.paths, market)?;
            if !candles.is_empty() {
                with_c.insert(market.ticker.clone());
                candle_count += candles.len() as u64;
                dup_candles += candles.iter().filter(|c| c.is_duplicate).count() as u64;
                if let (Some(min_ts), Some(max_ts)) = (
                    candles.iter().map(|c| c.end_period_ts).min(),
                    candles.iter().map(|c| c.end_period_ts).max(),
                ) {
                    let expected = ((max_ts - min_ts) / 60 + 1).max(1);
                    coverage_acc.push(candles.len() as f64 / expected as f64);
                }
                for c in &candles {
                    earliest = Some(
                        earliest.map_or(c.end_time, |e: chrono::DateTime<Utc>| e.min(c.end_time)),
                    );
                    latest = Some(
                        latest.map_or(c.end_time, |e: chrono::DateTime<Utc>| e.max(c.end_time)),
                    );
                }
                let month = ticker_month(market, candles.first().map(|c| c.end_period_ts));
                write_candles(
                    &self
                        .paths
                        .candles_month(&month)
                        .join(format!("{}.parquet", sanitize(&market.ticker))),
                    &candles,
                )?;
                write_causal(
                    &self
                        .paths
                        .causal_features_month(&month)
                        .join(format!("{}.parquet", sanitize(&market.ticker))),
                    &causal_features(&candles),
                )?;
            }
            if !trades.is_empty() {
                with_t.insert(market.ticker.clone());
                trade_count += trades.len() as u64;
                dup_trades += trades.iter().filter(|t| t.is_duplicate).count() as u64;
                let month = ticker_month(market, trades.first().map(|t| t.timestamp.timestamp()));
                write_trades(
                    &self
                        .paths
                        .trades_month(&month)
                        .join(format!("{}.parquet", sanitize(&market.ticker))),
                    &trades,
                )?;
                write_trade_agg(
                    &self
                        .paths
                        .trade_agg_month(&month)
                        .join(format!("{}.parquet", sanitize(&market.ticker))),
                    &trade_minute_agg(&trades),
                )?;
            }
        }

        for game in &games {
            if game.market_tickers.len() != 2 {
                continue;
            }
            let mut pair_candles = Vec::new();
            for ticker in &game.market_tickers {
                if let Some(m) = markets.iter().find(|m| m.ticker == *ticker) {
                    pair_candles.extend(load_raw_candles_for_ticker(&self.paths, m)?);
                }
            }
            let comps = complementarity(std::slice::from_ref(game), &pair_candles);
            if comps.is_empty() {
                extra_anomalies.push(format!(
                    "no aligned complementarity for {}",
                    game.event_ticker
                ));
                continue;
            }
            let month = month_from_ts(comps[0].end_period_ts);
            write_complementarity(
                &self
                    .paths
                    .complementarity_month(&month)
                    .join(format!("{}.parquet", sanitize(&game.event_ticker))),
                &comps,
            )?;
        }

        let manifest = load_manifest(&self.paths);
        let failed = manifest
            .jobs
            .iter()
            .filter(|j| j.status == "FAILED")
            .count() as u64;
        let coverage = if coverage_acc.is_empty() {
            None
        } else {
            Some(format!(
                "{:.4}",
                coverage_acc.iter().sum::<f64>() / coverage_acc.len() as f64
            ))
        };
        let report = super::validate::validate_counts(
            &self.config.sport,
            &self.config.series,
            &self.config.season,
            &events,
            &markets,
            &games,
            candle_count,
            trade_count,
            with_c.len() as u64,
            with_t.len() as u64,
            dup_candles,
            dup_trades,
            earliest.map(|t| t.to_rfc3339()),
            latest.map(|t| t.to_rfc3339()),
            coverage,
            failed,
            extra_anomalies,
        );
        self.persist_report(&report, &universe.cutoff, events.len(), markets.len())?;
        Ok(report)
    }

    fn persist_report(
        &self,
        report: &WarehouseReport,
        cutoff: &Value,
        events: usize,
        markets: usize,
    ) -> Result<(), WarehouseError> {
        self.paths.write_atomic(
            &self.paths.validation_json(),
            &serde_json::to_vec_pretty(report)?,
        )?;
        self.paths.write_atomic(
            &self.paths.validation_txt(),
            render_report(report).as_bytes(),
        )?;
        let checksum = match (
            sha256_file(&self.paths.events_parquet()),
            sha256_file(&self.paths.markets_parquet()),
        ) {
            (Ok(a), Ok(b)) => format!("{a}:{b}"),
            _ => String::new(),
        };
        let dataset = DatasetManifest {
            dataset_name: format!("kalshi_{}", self.config.series.to_ascii_lowercase()),
            sport: self.config.sport.clone(),
            series: self.config.series.clone(),
            season: self.config.season.clone(),
            generation_timestamp: Utc::now(),
            api_base: "https://external-api.kalshi.com/trade-api/v2".into(),
            historical_cutoff: Some(cutoff.clone()),
            events_count: events as u64,
            markets_count: markets as u64,
            games_count: report.games,
            candles_count: report.candles,
            trades_count: report.trades,
            date_min: report.earliest_candle.clone(),
            date_max: report.latest_candle.clone(),
            schema_version: self.config.schema_version().into(),
            code_version: COLLECTOR_VERSION.into(),
            checksum,
            market_data_type: MARKET_DATA_TYPE_CANDLE_TOB.into(),
            orderbook_depth_available: false,
        };
        self.paths.write_atomic(
            &self.paths.dataset_manifest(),
            &serde_json::to_vec_pretty(&dataset)?,
        )?;
        self.paths.write_atomic(
            &self.paths.coverage_path(),
            &serde_json::to_vec_pretty(&serde_json::json!({
                "coverage_ratio": report.coverage_ratio,
                "markets_with_candles": report.markets_with_candles,
                "markets_with_trades": report.markets_with_trades,
                "orderbook_depth_available": false,
                "market_data_type": MARKET_DATA_TYPE_CANDLE_TOB,
            }))?,
        )?;
        Ok(())
    }

    pub fn validate(&self) -> Result<WarehouseReport, WarehouseError> {
        let universe = self.load_or_discover()?;
        self.rebuild_all(&universe)
    }

    pub fn query(&self) -> Result<NbaQuery, WarehouseError> {
        let universe = self.load_or_discover()?;
        let (events, markets, games) = self.catalog(&universe);
        let mut candles = Vec::new();
        let mut trades = Vec::new();
        for market in &markets {
            candles.extend(load_raw_candles_for_ticker(&self.paths, market)?);
            trades.extend(load_raw_trades_for_ticker(&self.paths, market)?);
        }
        let causal = {
            let mut out = Vec::new();
            let mut by_t: BTreeMap<String, Vec<NbaCandleRow>> = BTreeMap::new();
            for c in &candles {
                by_t.entry(c.ticker.clone()).or_default().push(c.clone());
            }
            for rows in by_t.into_values() {
                out.extend(causal_features(&rows));
            }
            out
        };
        let complementarity = complementarity(&games, &candles);
        let _ = events;
        Ok(NbaQuery {
            games,
            markets,
            candles,
            trades,
            causal,
            complementarity,
        })
    }
}

type IngestionManifestLock = super::types::IngestionManifest;

fn sanitize(ticker: &str) -> String {
    ticker.replace('/', "_")
}

fn ticker_month(market: &NbaMarketRow, fallback_ts: Option<i64>) -> String {
    let from_occ = month_from_rfc_date(market.occurrence_datetime.as_deref());
    if from_occ.len() == 7 && from_occ != "unknown" {
        return from_occ;
    }
    fallback_ts
        .map(month_from_ts)
        .unwrap_or_else(|| "unknown".into())
}
