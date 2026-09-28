//! Read-only replay interface for future backtests.

use std::fs::File;
use std::path::PathBuf;

use arrow::array::{
    Array, BooleanArray, Int64Array, StringArray, TimestampMillisecondArray, UInt16Array,
};
use chrono::{DateTime, NaiveDate, Utc};
use parquet::arrow::arrow_reader::ParquetRecordBatchReaderBuilder;

use crate::manifest::DailyManifest;
use crate::orderbook::OrderbookReconstructor;
use crate::paths::ResearchPaths;
use crate::schema::{NormalizedSource, OrderbookEvent, OrderbookLevel, PublicTrade};
use crate::sport::ResearchSport;

#[derive(Clone, Debug)]
pub struct ReplayDataset {
    pub sport: ResearchSport,
    pub date: NaiveDate,
    pub trades: Vec<PublicTrade>,
    pub orderbook_events: Vec<OrderbookEvent>,
}

impl ReplayDataset {
    pub fn load(
        paths: &ResearchPaths,
        sport: ResearchSport,
        date: NaiveDate,
    ) -> std::io::Result<Self> {
        let trades_path = paths.trades_day(sport, date).join("trades.parquet");
        let ob_path = paths.orderbook_day(sport, date).join("orderbook.parquet");
        Ok(Self {
            sport,
            date,
            trades: if trades_path.exists() {
                read_trades_parquet(&trades_path)?
            } else {
                Vec::new()
            },
            orderbook_events: if ob_path.exists() {
                read_orderbook_parquet(&ob_path)?
            } else {
                Vec::new()
            },
        })
    }

    pub fn manifest(
        paths: &ResearchPaths,
        sport: ResearchSport,
        date: NaiveDate,
    ) -> std::io::Result<Option<DailyManifest>> {
        DailyManifest::read(paths, sport, date)
    }

    pub fn cursor(&self) -> ReplayCursor<'_> {
        ReplayCursor::new(self)
    }
}

pub struct ReplayCursor<'a> {
    dataset: &'a ReplayDataset,
    index: usize,
    reconstructor: OrderbookReconstructor,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub enum ReplayItem<'a> {
    Trade(&'a PublicTrade),
    Orderbook(&'a OrderbookEvent),
}

impl<'a> ReplayCursor<'a> {
    fn new(dataset: &'a ReplayDataset) -> Self {
        Self {
            dataset,
            index: 0,
            reconstructor: OrderbookReconstructor::new(),
        }
    }

    pub fn has_gap(&self) -> bool {
        self.reconstructor.gap_state().sequence_gap
    }

    pub fn depth(&self, ticker: &str) -> Option<momento_kalshi::BookDepth> {
        self.reconstructor.depth(ticker)
    }

    pub fn events_chronological(&self) -> Vec<ReplayItem<'a>> {
        let mut items = Vec::new();
        for t in &self.dataset.trades {
            items.push(ReplayItem::Trade(t));
        }
        for o in &self.dataset.orderbook_events {
            items.push(ReplayItem::Orderbook(o));
        }
        items.sort_by_key(|a| event_time_key(a));
        items
    }
}

impl<'a> Iterator for ReplayCursor<'a> {
    type Item = ReplayItem<'a>;

    fn next(&mut self) -> Option<Self::Item> {
        let items = self.events_chronological();
        if self.index >= items.len() {
            return None;
        }
        let item = items[self.index].clone();
        self.index += 1;
        Some(item)
    }
}

fn event_time_key(item: &ReplayItem<'_>) -> i64 {
    match item {
        ReplayItem::Trade(t) => t
            .exchange_timestamp
            .parse::<DateTime<Utc>>()
            .map(|d| d.timestamp_millis())
            .unwrap_or(0),
        ReplayItem::Orderbook(o) => o
            .exchange_timestamp_ms
            .unwrap_or_else(|| o.received_timestamp.timestamp_millis()),
    }
}

fn read_trades_parquet(path: &PathBuf) -> std::io::Result<Vec<PublicTrade>> {
    let file = File::open(path)?;
    let builder = ParquetRecordBatchReaderBuilder::try_new(file).map_err(std::io::Error::other)?;
    let reader = builder.build().map_err(std::io::Error::other)?;
    let mut out = Vec::new();
    for batch in reader {
        let batch = batch.map_err(std::io::Error::other)?;
        let exchange = batch
            .column_by_name("exchange_timestamp")
            .and_then(|c| c.as_any().downcast_ref::<StringArray>())
            .ok_or_else(|| std::io::Error::other("exchange_timestamp"))?;
        let received = batch
            .column_by_name("received_timestamp")
            .and_then(|c| c.as_any().downcast_ref::<TimestampMillisecondArray>())
            .ok_or_else(|| std::io::Error::other("received_timestamp"))?;
        let ticker = col_str(&batch, "ticker")?;
        let market_id = col_str(&batch, "market_id")?;
        let game_id = col_str(&batch, "game_id")?;
        let trade_id = col_str(&batch, "trade_id")?;
        let yes_price = batch
            .column_by_name("yes_price_cents")
            .and_then(|c| c.as_any().downcast_ref::<UInt16Array>())
            .ok_or_else(|| std::io::Error::other("yes_price_cents"))?;
        let qty = batch
            .column_by_name("quantity_hundredths")
            .and_then(|c| c.as_any().downcast_ref::<Int64Array>())
            .ok_or_else(|| std::io::Error::other("quantity_hundredths"))?;
        let source = col_str(&batch, "source")?;
        for i in 0..batch.num_rows() {
            out.push(PublicTrade {
                exchange_timestamp: exchange.value(i).to_string(),
                received_timestamp: DateTime::from_timestamp_millis(received.value(i))
                    .unwrap_or_else(Utc::now),
                ticker: ticker.value(i).to_string(),
                market_id: market_id.value(i).parse().unwrap_or(0),
                game_id: game_id.value(i).parse().unwrap_or(0),
                trade_id: trade_id.value(i).to_string(),
                yes_price_cents: yes_price.value(i),
                quantity_hundredths: qty.value(i),
                taker_outcome_side: None,
                taker_book_side: None,
                is_block_trade: false,
                source: source.value(i).to_string(),
            });
        }
    }
    Ok(out)
}

fn read_orderbook_parquet(path: &PathBuf) -> std::io::Result<Vec<OrderbookEvent>> {
    let file = File::open(path)?;
    let builder = ParquetRecordBatchReaderBuilder::try_new(file).map_err(std::io::Error::other)?;
    let reader = builder.build().map_err(std::io::Error::other)?;
    let mut out = Vec::new();
    for batch in reader {
        let batch = batch.map_err(std::io::Error::other)?;
        let exchange = batch
            .column_by_name("exchange_timestamp_ms")
            .and_then(|c| c.as_any().downcast_ref::<Int64Array>());
        let received = batch
            .column_by_name("received_timestamp")
            .and_then(|c| c.as_any().downcast_ref::<TimestampMillisecondArray>())
            .ok_or_else(|| std::io::Error::other("received_timestamp"))?;
        let ticker = col_str(&batch, "ticker")?;
        let market_id = col_str(&batch, "market_id")?;
        let game_id = col_str(&batch, "game_id")?;
        let event_type = col_str(&batch, "event_type")?;
        let source = col_str(&batch, "source")?;
        let levels_json = col_str(&batch, "levels_json")?;
        let sequence_gap = batch
            .column_by_name("sequence_gap")
            .and_then(|c| c.as_any().downcast_ref::<BooleanArray>());
        let yes_bid = batch
            .column_by_name("yes_bid_cents")
            .and_then(|c| c.as_any().downcast_ref::<UInt16Array>());
        let yes_ask = batch
            .column_by_name("yes_ask_cents")
            .and_then(|c| c.as_any().downcast_ref::<UInt16Array>());
        for i in 0..batch.num_rows() {
            let levels: Vec<OrderbookLevel> =
                serde_json::from_str(levels_json.value(i)).unwrap_or_default();
            out.push(OrderbookEvent {
                exchange_timestamp_ms: exchange
                    .and_then(|e| if e.is_null(i) { None } else { Some(e.value(i)) }),
                received_timestamp: DateTime::from_timestamp_millis(received.value(i))
                    .unwrap_or_else(Utc::now),
                ticker: ticker.value(i).to_string(),
                market_id: market_id.value(i).parse().unwrap_or(0),
                game_id: game_id.value(i).parse().unwrap_or(0),
                event_type: event_type.value(i).to_string(),
                source: parse_source(source.value(i)),
                sequence_number: None,
                subscription_id: None,
                yes_bid_cents: yes_bid
                    .and_then(|a| if a.is_null(i) { None } else { Some(a.value(i)) }),
                yes_ask_cents: yes_ask
                    .and_then(|a| if a.is_null(i) { None } else { Some(a.value(i)) }),
                yes_bid_depth_hundredths: None,
                yes_ask_depth_hundredths: None,
                levels,
                sequence_gap: sequence_gap.is_some_and(|a| a.value(i)),
                resync_count: 0,
                first_missing_sequence: None,
                last_valid_sequence: None,
            });
        }
    }
    Ok(out)
}

fn col_str<'a>(
    batch: &'a arrow::record_batch::RecordBatch,
    name: &str,
) -> std::io::Result<&'a StringArray> {
    batch
        .column_by_name(name)
        .and_then(|c| c.as_any().downcast_ref::<StringArray>())
        .ok_or_else(|| std::io::Error::other(name))
}

fn parse_source(raw: &str) -> NormalizedSource {
    if raw.contains("WebSocketSnapshot") {
        NormalizedSource::WebSocketSnapshot
    } else if raw.contains("WebSocketDelta") {
        NormalizedSource::WebSocketDelta
    } else if raw.contains("RestCandlestick") {
        NormalizedSource::RestCandlestick
    } else {
        NormalizedSource::RestSnapshot
    }
}
