//! Raw → normalized Parquet conversion.

use std::fs::File;
use std::path::Path;

use std::sync::Arc;

use arrow::array::{
    ArrayRef, BooleanArray, Int64Array, RecordBatch, StringArray, TimestampMillisecondArray,
    UInt16Array, UInt32Array, UInt64Array,
};
use arrow::datatypes::{DataType, Field, Schema, TimeUnit};
use chrono::{DateTime, Utc};
use parquet::arrow::ArrowWriter;
use parquet::basic::Compression;
use parquet::file::properties::WriterProperties;

use crate::schema::{MarketMetadata, OrderbookEvent, PublicTrade};

fn ts_field(name: &str) -> Field {
    Field::new(
        name,
        DataType::Timestamp(TimeUnit::Millisecond, Some("UTC".into())),
        false,
    )
}

pub fn write_metadata_parquet(path: &Path, rows: &[MarketMetadata]) -> std::io::Result<u64> {
    if let Some(parent) = path.parent() {
        std::fs::create_dir_all(parent)?;
    }
    let schema = Schema::new(vec![
        Field::new("game_id", DataType::Utf8, false),
        Field::new("market_id", DataType::Utf8, false),
        Field::new("ticker", DataType::Utf8, false),
        Field::new("event_ticker", DataType::Utf8, false),
        Field::new("series_ticker", DataType::Utf8, false),
        Field::new("side_label", DataType::Utf8, true),
        Field::new("status", DataType::Utf8, true),
        Field::new("open_time", DataType::Utf8, true),
        Field::new("close_time", DataType::Utf8, true),
        Field::new("settlement_ts", DataType::Utf8, true),
        Field::new("result", DataType::Utf8, true),
    ]);
    let to_s = |v: &Option<String>| v.clone().unwrap_or_default();
    let batch = RecordBatch::try_new(
        std::sync::Arc::new(schema),
        vec![
            Arc::new(StringArray::from(
                rows.iter()
                    .map(|r| r.game_id.to_string())
                    .collect::<Vec<_>>(),
            )) as ArrayRef,
            Arc::new(StringArray::from(
                rows.iter()
                    .map(|r| r.market_id.to_string())
                    .collect::<Vec<_>>(),
            )),
            Arc::new(StringArray::from(
                rows.iter().map(|r| r.ticker.clone()).collect::<Vec<_>>(),
            )),
            Arc::new(StringArray::from(
                rows.iter()
                    .map(|r| r.event_ticker.clone())
                    .collect::<Vec<_>>(),
            )),
            Arc::new(StringArray::from(
                rows.iter()
                    .map(|r| r.series_ticker.clone())
                    .collect::<Vec<_>>(),
            )),
            Arc::new(StringArray::from(
                rows.iter().map(|r| to_s(&r.side_label)).collect::<Vec<_>>(),
            )),
            Arc::new(StringArray::from(
                rows.iter().map(|r| to_s(&r.status)).collect::<Vec<_>>(),
            )),
            Arc::new(StringArray::from(
                rows.iter().map(|r| to_s(&r.open_time)).collect::<Vec<_>>(),
            )),
            Arc::new(StringArray::from(
                rows.iter().map(|r| to_s(&r.close_time)).collect::<Vec<_>>(),
            )),
            Arc::new(StringArray::from(
                rows.iter()
                    .map(|r| to_s(&r.settlement_ts))
                    .collect::<Vec<_>>(),
            )),
            Arc::new(StringArray::from(
                rows.iter().map(|r| to_s(&r.result)).collect::<Vec<_>>(),
            )),
        ],
    )
    .map_err(std::io::Error::other)?;
    write_batch(path, batch)
}

pub fn write_trades_parquet(path: &Path, rows: &[PublicTrade]) -> std::io::Result<u64> {
    if let Some(parent) = path.parent() {
        std::fs::create_dir_all(parent)?;
    }
    let schema = Schema::new(vec![
        Field::new("exchange_timestamp", DataType::Utf8, false),
        ts_field("received_timestamp"),
        Field::new("ticker", DataType::Utf8, false),
        Field::new("market_id", DataType::Utf8, false),
        Field::new("game_id", DataType::Utf8, false),
        Field::new("trade_id", DataType::Utf8, false),
        Field::new("yes_price_cents", DataType::UInt16, false),
        Field::new("quantity_hundredths", DataType::Int64, false),
        Field::new("taker_outcome_side", DataType::Utf8, true),
        Field::new("taker_book_side", DataType::Utf8, true),
        Field::new("is_block_trade", DataType::Boolean, false),
        Field::new("source", DataType::Utf8, false),
    ]);
    let batch = RecordBatch::try_new(
        std::sync::Arc::new(schema),
        vec![
            Arc::new(StringArray::from(
                rows.iter()
                    .map(|r| r.exchange_timestamp.clone())
                    .collect::<Vec<_>>(),
            )) as ArrayRef,
            Arc::new(
                TimestampMillisecondArray::from(
                    rows.iter()
                        .map(|r| r.received_timestamp.timestamp_millis())
                        .collect::<Vec<_>>(),
                )
                .with_timezone("UTC"),
            ),
            Arc::new(StringArray::from(
                rows.iter().map(|r| r.ticker.clone()).collect::<Vec<_>>(),
            )),
            Arc::new(StringArray::from(
                rows.iter()
                    .map(|r| r.market_id.to_string())
                    .collect::<Vec<_>>(),
            )),
            Arc::new(StringArray::from(
                rows.iter()
                    .map(|r| r.game_id.to_string())
                    .collect::<Vec<_>>(),
            )),
            Arc::new(StringArray::from(
                rows.iter().map(|r| r.trade_id.clone()).collect::<Vec<_>>(),
            )),
            Arc::new(UInt16Array::from(
                rows.iter().map(|r| r.yes_price_cents).collect::<Vec<_>>(),
            )),
            Arc::new(Int64Array::from(
                rows.iter()
                    .map(|r| r.quantity_hundredths)
                    .collect::<Vec<_>>(),
            )),
            Arc::new(StringArray::from(
                rows.iter()
                    .map(|r| r.taker_outcome_side.clone().unwrap_or_default())
                    .collect::<Vec<_>>(),
            )),
            Arc::new(StringArray::from(
                rows.iter()
                    .map(|r| r.taker_book_side.clone().unwrap_or_default())
                    .collect::<Vec<_>>(),
            )),
            Arc::new(BooleanArray::from(
                rows.iter().map(|r| r.is_block_trade).collect::<Vec<_>>(),
            )),
            Arc::new(StringArray::from(
                rows.iter().map(|r| r.source.clone()).collect::<Vec<_>>(),
            )),
        ],
    )
    .map_err(std::io::Error::other)?;
    write_batch(path, batch)
}

pub fn write_orderbook_parquet(path: &Path, rows: &[OrderbookEvent]) -> std::io::Result<u64> {
    if let Some(parent) = path.parent() {
        std::fs::create_dir_all(parent)?;
    }
    let schema = Schema::new(vec![
        Field::new("exchange_timestamp_ms", DataType::Int64, true),
        ts_field("received_timestamp"),
        Field::new("ticker", DataType::Utf8, false),
        Field::new("market_id", DataType::Utf8, false),
        Field::new("game_id", DataType::Utf8, false),
        Field::new("event_type", DataType::Utf8, false),
        Field::new("source", DataType::Utf8, false),
        Field::new("sequence_number", DataType::UInt64, true),
        Field::new("subscription_id", DataType::UInt64, true),
        Field::new("yes_bid_cents", DataType::UInt16, true),
        Field::new("yes_ask_cents", DataType::UInt16, true),
        Field::new("yes_bid_depth_hundredths", DataType::Int64, true),
        Field::new("yes_ask_depth_hundredths", DataType::Int64, true),
        Field::new("levels_json", DataType::Utf8, false),
        Field::new("sequence_gap", DataType::Boolean, false),
        Field::new("resync_count", DataType::UInt32, false),
        Field::new("first_missing_sequence", DataType::UInt64, true),
        Field::new("last_valid_sequence", DataType::UInt64, true),
    ]);
    let batch = RecordBatch::try_new(
        std::sync::Arc::new(schema),
        vec![
            Arc::new(Int64Array::from(
                rows.iter()
                    .map(|r| r.exchange_timestamp_ms)
                    .collect::<Vec<_>>(),
            )) as ArrayRef,
            Arc::new(
                TimestampMillisecondArray::from(
                    rows.iter()
                        .map(|r| r.received_timestamp.timestamp_millis())
                        .collect::<Vec<_>>(),
                )
                .with_timezone("UTC"),
            ),
            Arc::new(StringArray::from(
                rows.iter().map(|r| r.ticker.clone()).collect::<Vec<_>>(),
            )),
            Arc::new(StringArray::from(
                rows.iter()
                    .map(|r| r.market_id.to_string())
                    .collect::<Vec<_>>(),
            )),
            Arc::new(StringArray::from(
                rows.iter()
                    .map(|r| r.game_id.to_string())
                    .collect::<Vec<_>>(),
            )),
            Arc::new(StringArray::from(
                rows.iter()
                    .map(|r| r.event_type.clone())
                    .collect::<Vec<_>>(),
            )),
            Arc::new(StringArray::from(
                rows.iter()
                    .map(|r| format!("{:?}", r.source))
                    .collect::<Vec<_>>(),
            )),
            Arc::new(UInt64Array::from(
                rows.iter().map(|r| r.sequence_number).collect::<Vec<_>>(),
            )),
            Arc::new(UInt64Array::from(
                rows.iter().map(|r| r.subscription_id).collect::<Vec<_>>(),
            )),
            Arc::new(UInt16Array::from(
                rows.iter().map(|r| r.yes_bid_cents).collect::<Vec<_>>(),
            )),
            Arc::new(UInt16Array::from(
                rows.iter().map(|r| r.yes_ask_cents).collect::<Vec<_>>(),
            )),
            Arc::new(Int64Array::from(
                rows.iter()
                    .map(|r| r.yes_bid_depth_hundredths)
                    .collect::<Vec<_>>(),
            )),
            Arc::new(Int64Array::from(
                rows.iter()
                    .map(|r| r.yes_ask_depth_hundredths)
                    .collect::<Vec<_>>(),
            )),
            Arc::new(StringArray::from(
                rows.iter()
                    .map(|r| serde_json::to_string(&r.levels).unwrap_or_else(|_| "[]".into()))
                    .collect::<Vec<_>>(),
            )),
            Arc::new(BooleanArray::from(
                rows.iter().map(|r| r.sequence_gap).collect::<Vec<_>>(),
            )),
            Arc::new(UInt32Array::from(
                rows.iter().map(|r| r.resync_count).collect::<Vec<_>>(),
            )),
            Arc::new(UInt64Array::from(
                rows.iter()
                    .map(|r| r.first_missing_sequence)
                    .collect::<Vec<_>>(),
            )),
            Arc::new(UInt64Array::from(
                rows.iter()
                    .map(|r| r.last_valid_sequence)
                    .collect::<Vec<_>>(),
            )),
        ],
    )
    .map_err(std::io::Error::other)?;
    write_batch(path, batch)
}

fn write_batch(path: &Path, batch: RecordBatch) -> std::io::Result<u64> {
    let file = File::create(path)?;
    let props = WriterProperties::builder()
        .set_compression(Compression::ZSTD(Default::default()))
        .build();
    let mut writer =
        ArrowWriter::try_new(file, batch.schema(), Some(props)).map_err(std::io::Error::other)?;
    writer.write(&batch).map_err(std::io::Error::other)?;
    writer.close().map_err(std::io::Error::other)?;
    Ok(batch.num_rows() as u64)
}

pub fn dollars_to_cents(dollars: &str) -> Option<u16> {
    momento_kalshi::dollars_to_price_cents(dollars)
        .ok()
        .map(|p| p.cents())
}

pub fn count_fp_to_hundredths(raw: &str) -> Option<i64> {
    momento_kalshi::count_fp_to_hundredths(raw).ok()
}

pub fn received_now() -> DateTime<Utc> {
    Utc::now()
}
