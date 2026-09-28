//! Daily historical collection orchestration.

use std::collections::BTreeMap;
use std::fs;
use std::path::PathBuf;

use chrono::NaiveDate;
use momento_kalshi::PublicMarketClient;
use tracing::{info, warn};

use crate::checksum::sha256_file;
use crate::discovery::{day_window, discover_markets_for_day};
use crate::identity::DiscoveredMarket;
use crate::manifest::{CompletenessStatus, DailyManifest, remove_path_if_exists};
use crate::normalize::{
    count_fp_to_hundredths, dollars_to_cents, received_now, write_metadata_parquet,
    write_orderbook_parquet, write_trades_parquet,
};
use crate::paths::ResearchPaths;
use crate::raw::{RawArchiveWriter, staging_raw_path};
use crate::schema::{NormalizedSource, OrderbookEvent, OrderbookLevel, PublicTrade};
use crate::sport::{ResearchSeason, ResearchSport};
use crate::validate::{
    no_synthetic_rows, validate_discovered_pairing, validate_metadata, validate_orderbook,
    validate_trades,
};

#[derive(Clone, Debug)]
pub struct CollectorConfig {
    pub paths: ResearchPaths,
    pub season: ResearchSeason,
    pub sports: Vec<ResearchSport>,
    pub candlestick_period_minutes: u32,
}

impl CollectorConfig {
    pub fn default_sports() -> Self {
        Self {
            paths: ResearchPaths::from_env_or_default(),
            season: ResearchSeason::current(),
            sports: vec![ResearchSport::Mlb, ResearchSport::Wnba],
            candlestick_period_minutes: 1,
        }
    }
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct CollectDayReport {
    pub sport: ResearchSport,
    pub date: NaiveDate,
    pub status: CompletenessStatus,
    pub markets_discovered: u32,
    pub markets_collected: u32,
}

pub struct Collector {
    client: PublicMarketClient,
    config: CollectorConfig,
}

impl Collector {
    pub fn new(config: CollectorConfig) -> Self {
        Self {
            client: PublicMarketClient::production(),
            config,
        }
    }

    pub fn with_client(client: PublicMarketClient, config: CollectorConfig) -> Self {
        Self { client, config }
    }

    pub fn reconcile(&self, dates: &[NaiveDate]) -> Result<Vec<CollectDayReport>, String> {
        let mut reports = Vec::new();
        for sport in &self.config.sports.clone() {
            for date in dates {
                reports.push(self.collect_day(*sport, *date)?);
            }
        }
        Ok(reports)
    }

    pub fn collect_day(
        &self,
        sport: ResearchSport,
        date: NaiveDate,
    ) -> Result<CollectDayReport, String> {
        let paths = &self.config.paths;
        let mut manifest = DailyManifest::new(sport, &self.config.season, date);
        manifest.notes.push(
            "Historical L2 orderbook is only available from prospective WebSocket capture; REST backfill stores trades, metadata, candlesticks, and point-in-time snapshots.".into(),
        );

        let cutoff = self
            .client
            .get_historical_cutoff()
            .ok()
            .and_then(|c| c.market_settled_ts);
        let discovered = discover_markets_for_day(&self.client, sport, date, cutoff)
            .map_err(|e| e.to_string())?;
        let pairing = validate_discovered_pairing(&discovered);
        manifest.invalid_records += pairing.invalid_records;
        manifest.markets_discovered = discovered.len() as u32;

        let staging_raw = paths.raw_staging_day(sport, date);
        let staging_ob = paths.orderbook_staging_day(sport, date);
        let staging_tr = paths.trades_staging_day(sport, date);
        remove_path_if_exists(&staging_raw).map_err(|e| e.to_string())?;
        remove_path_if_exists(&staging_ob).map_err(|e| e.to_string())?;
        remove_path_if_exists(&staging_tr).map_err(|e| e.to_string())?;

        let mut raw_writer =
            RawArchiveWriter::create(&staging_raw_path(paths, sport, date, "events"))
                .map_err(|e| e.to_string())?;
        let mut metadata_rows = Vec::new();
        let mut trade_rows = Vec::new();
        let mut orderbook_rows = Vec::new();
        let window = day_window(date);
        let trades_historical = cutoff.is_some_and(|c| window.end_ts < c);

        for market in &discovered {
            metadata_rows.push(market.metadata.clone());
            if let Ok(payload) = serde_json::to_value(&market.metadata) {
                let _ = raw_writer.append_payload(
                    "collector",
                    "market_metadata",
                    Some(&market.metadata.ticker),
                    payload,
                );
            }

            match self.collect_market(
                market,
                &window,
                trades_historical,
                &mut raw_writer,
                &mut trade_rows,
                &mut orderbook_rows,
            ) {
                Ok(()) => manifest.markets_collected += 1,
                Err(err) => {
                    warn!(ticker = %market.metadata.ticker, %err, "market collection failed");
                    manifest
                        .missing_markets
                        .push(market.metadata.ticker.clone());
                }
            }
        }

        let raw_summary = raw_writer.finish().map_err(|e| e.to_string())?;
        manifest.raw_event_count = raw_summary.event_count;

        let meta_report = validate_metadata(&metadata_rows);
        let trade_report = validate_trades(&trade_rows);
        let ob_report = validate_orderbook(&orderbook_rows);
        let synth_report = no_synthetic_rows(&orderbook_rows);
        manifest.invalid_records += meta_report.invalid_records
            + trade_report.invalid_records
            + ob_report.invalid_records
            + synth_report.invalid_records;
        manifest.trade_count = trade_rows.len() as u64;
        manifest.orderbook_event_count = orderbook_rows.len() as u64;
        manifest.sequence_gaps = orderbook_rows.iter().filter(|r| r.sequence_gap).count() as u32;
        manifest.normalized_event_count =
            metadata_rows.len() as u64 + trade_rows.len() as u64 + orderbook_rows.len() as u64;

        let meta_path = staging_ob.join("metadata.parquet");
        let trades_path = staging_tr.join("trades.parquet");
        let ob_path = staging_ob.join("orderbook.parquet");
        write_metadata_parquet(&meta_path, &metadata_rows).map_err(|e| e.to_string())?;
        write_trades_parquet(&trades_path, &trade_rows).map_err(|e| e.to_string())?;
        write_orderbook_parquet(&ob_path, &orderbook_rows).map_err(|e| e.to_string())?;

        let mut checksums = BTreeMap::new();
        for file in [
            raw_summary.path.clone(),
            meta_path.clone(),
            trades_path.clone(),
            ob_path.clone(),
        ] {
            if file.exists() {
                checksums.insert(
                    file.file_name()
                        .unwrap_or_default()
                        .to_string_lossy()
                        .to_string(),
                    sha256_file(&file).map_err(|e| e.to_string())?,
                );
            }
        }
        manifest.checksums = checksums;
        manifest.finalize_status();

        if manifest.completeness_status == CompletenessStatus::Invalid {
            remove_path_if_exists(&staging_raw).ok();
            remove_path_if_exists(&staging_ob).ok();
            remove_path_if_exists(&staging_tr).ok();
            manifest
                .write_atomic(paths, sport)
                .map_err(|e| e.to_string())?;
            return Ok(CollectDayReport {
                sport,
                date,
                status: manifest.completeness_status,
                markets_discovered: manifest.markets_discovered,
                markets_collected: manifest.markets_collected,
            });
        }

        publish_staging_dir(&staging_raw, &paths.raw_day(sport, date))
            .map_err(|e| e.to_string())?;
        publish_staging_dir(&staging_ob, &paths.orderbook_day(sport, date))
            .map_err(|e| e.to_string())?;
        publish_staging_dir(&staging_tr, &paths.trades_day(sport, date))
            .map_err(|e| e.to_string())?;
        manifest
            .write_atomic(paths, sport)
            .map_err(|e| e.to_string())?;

        info!(
            sport = sport.dir_name(),
            %date,
            status = ?manifest.completeness_status,
            markets = manifest.markets_collected,
            trades = manifest.trade_count,
            "collection complete"
        );

        Ok(CollectDayReport {
            sport,
            date,
            status: manifest.completeness_status,
            markets_discovered: manifest.markets_discovered,
            markets_collected: manifest.markets_collected,
        })
    }

    fn collect_market(
        &self,
        market: &DiscoveredMarket,
        window: &crate::discovery::DayWindow,
        trades_historical: bool,
        raw: &mut RawArchiveWriter,
        trades: &mut Vec<PublicTrade>,
        orderbook: &mut Vec<OrderbookEvent>,
    ) -> Result<(), String> {
        let ticker = &market.metadata.ticker;
        let trades_payload = self
            .client
            .list_all_trades(ticker, window.start_ts, window.end_ts, trades_historical)
            .map_err(|e| e.to_string())?;
        for trade in trades_payload {
            let payload = serde_json::to_value(&trade).map_err(|e| e.to_string())?;
            raw.append_payload("rest", "markets/trades", Some(ticker), payload)
                .map_err(|e| e.to_string())?;
            let yes_cents = dollars_to_cents(&trade.yes_price_dollars)
                .ok_or_else(|| format!("invalid trade price for {ticker}"))?;
            let qty = count_fp_to_hundredths(&trade.count_fp)
                .ok_or_else(|| format!("invalid trade qty for {ticker}"))?;
            trades.push(PublicTrade {
                exchange_timestamp: trade.created_time.clone(),
                received_timestamp: received_now(),
                ticker: ticker.clone(),
                market_id: market.metadata.market_id,
                game_id: market.metadata.game_id,
                trade_id: trade.trade_id,
                yes_price_cents: yes_cents,
                quantity_hundredths: qty,
                taker_outcome_side: trade.taker_outcome_side,
                taker_book_side: trade.taker_book_side,
                is_block_trade: trade.is_block_trade,
                source: if trades_historical {
                    "historical_rest".into()
                } else {
                    "rest".into()
                },
            });
        }

        let start_ts = window.start_ts;
        let end_ts = window.end_ts;
        let series = market.sport.series_ticker();
        let candles = if trades_historical {
            self.client
                .get_historical_candlesticks(
                    ticker,
                    start_ts,
                    end_ts,
                    self.config.candlestick_period_minutes,
                )
                .map_err(|e| e.to_string())?
        } else {
            self.client
                .get_candlesticks(
                    series,
                    ticker,
                    start_ts,
                    end_ts,
                    self.config.candlestick_period_minutes,
                )
                .map_err(|e| e.to_string())?
        };
        let payload = serde_json::to_value(&candles).map_err(|e| e.to_string())?;
        raw.append_payload("rest", "candlesticks", Some(ticker), payload)
            .map_err(|e| e.to_string())?;
        for candle in candles.candlesticks {
            let yes_bid = dollars_to_cents(&candle.yes_bid.close_dollars);
            let yes_ask = dollars_to_cents(&candle.yes_ask.close_dollars);
            orderbook.push(OrderbookEvent {
                exchange_timestamp_ms: Some(candle.end_period_ts * 1000),
                received_timestamp: received_now(),
                ticker: ticker.clone(),
                market_id: market.metadata.market_id,
                game_id: market.metadata.game_id,
                event_type: "candlestick_close".into(),
                source: NormalizedSource::RestCandlestick,
                sequence_number: None,
                subscription_id: None,
                yes_bid_cents: yes_bid,
                yes_ask_cents: yes_ask,
                yes_bid_depth_hundredths: None,
                yes_ask_depth_hundredths: None,
                levels: Vec::new(),
                sequence_gap: false,
                resync_count: 0,
                first_missing_sequence: None,
                last_valid_sequence: None,
            });
        }

        if let Ok(book) = self.client.get_orderbook(ticker, Some(100)) {
            let payload = serde_json::to_value(&book).map_err(|e| e.to_string())?;
            raw.append_payload("rest", "markets/orderbook", Some(ticker), payload)
                .map_err(|e| e.to_string())?;
            let mut levels = Vec::new();
            for [price, qty] in &book.orderbook_fp.yes_dollars {
                if let (Some(cents), Some(q)) =
                    (dollars_to_cents(price), count_fp_to_hundredths(qty))
                {
                    levels.push(OrderbookLevel {
                        price_cents: cents,
                        quantity_hundredths: q,
                        book_side: "yes".into(),
                    });
                }
            }
            for [price, qty] in &book.orderbook_fp.no_dollars {
                if let (Some(cents), Some(q)) =
                    (dollars_to_cents(price), count_fp_to_hundredths(qty))
                {
                    levels.push(OrderbookLevel {
                        price_cents: cents,
                        quantity_hundredths: q,
                        book_side: "no".into(),
                    });
                }
            }
            let (yes_bid, yes_bid_depth) = best_yes_from_levels(&levels);
            let (yes_ask, yes_ask_depth) = best_yes_ask_from_no(&levels);
            orderbook.push(OrderbookEvent {
                exchange_timestamp_ms: None,
                received_timestamp: received_now(),
                ticker: ticker.clone(),
                market_id: market.metadata.market_id,
                game_id: market.metadata.game_id,
                event_type: "rest_snapshot".into(),
                source: NormalizedSource::RestSnapshot,
                sequence_number: None,
                subscription_id: None,
                yes_bid_cents: yes_bid,
                yes_ask_cents: yes_ask,
                yes_bid_depth_hundredths: yes_bid_depth,
                yes_ask_depth_hundredths: yes_ask_depth,
                levels,
                sequence_gap: false,
                resync_count: 0,
                first_missing_sequence: None,
                last_valid_sequence: None,
            });
        }

        Ok(())
    }
}

fn publish_staging_dir(staging: &PathBuf, dest: &PathBuf) -> std::io::Result<()> {
    if dest.exists() {
        remove_path_if_exists(dest)?;
    }
    if staging.exists() {
        if let Some(parent) = dest.parent() {
            fs::create_dir_all(parent)?;
        }
        fs::rename(staging, dest)?;
    }
    Ok(())
}

fn best_yes_from_levels(levels: &[OrderbookLevel]) -> (Option<u16>, Option<i64>) {
    levels
        .iter()
        .filter(|l| l.book_side == "yes")
        .max_by_key(|l| l.price_cents)
        .map(|l| (Some(l.price_cents), Some(l.quantity_hundredths)))
        .unwrap_or((None, None))
}

fn best_yes_ask_from_no(levels: &[OrderbookLevel]) -> (Option<u16>, Option<i64>) {
    levels
        .iter()
        .filter(|l| l.book_side == "no")
        .max_by_key(|l| l.price_cents)
        .map(|l| {
            (
                Some(100u16.saturating_sub(l.price_cents)),
                Some(l.quantity_hundredths),
            )
        })
        .unwrap_or((None, None))
}
