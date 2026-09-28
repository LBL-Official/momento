//! Strict Arrow/Parquet writers for warehouse tables.

use std::fs::File;
use std::path::Path;
use std::sync::Arc;

use arrow::array::{
    ArrayRef, BooleanArray, Int64Array, StringArray, TimestampMillisecondArray, UInt32Array,
    UInt64Array,
};
use arrow::datatypes::{DataType, Field, Schema, TimeUnit};
use arrow::record_batch::RecordBatch;
use parquet::arrow::ArrowWriter;
use parquet::basic::Compression;
use parquet::file::properties::WriterProperties;

use super::error::WarehouseError;
use super::types::{
    CausalCandleFeatures, ComplementarityRow, NbaCandleRow, NbaEventRow, NbaGameRow, NbaMarketRow,
    NbaTradeRow, TradeMinuteAgg,
};

fn ts_utc(name: &str, nullable: bool) -> Field {
    Field::new(
        name,
        DataType::Timestamp(TimeUnit::Millisecond, Some("UTC".into())),
        nullable,
    )
}

fn write_batch(path: &Path, batch: RecordBatch) -> Result<u64, WarehouseError> {
    if let Some(parent) = path.parent() {
        std::fs::create_dir_all(parent)?;
    }
    let file = File::create(path)?;
    let props = WriterProperties::builder()
        .set_compression(Compression::ZSTD(Default::default()))
        .build();
    let mut writer = ArrowWriter::try_new(file, batch.schema(), Some(props))
        .map_err(|e| WarehouseError::Schema(e.to_string()))?;
    writer
        .write(&batch)
        .map_err(|e| WarehouseError::Schema(e.to_string()))?;
    writer
        .close()
        .map_err(|e| WarehouseError::Schema(e.to_string()))?;
    Ok(batch.num_rows() as u64)
}

fn opt_i64(rows: impl Iterator<Item = Option<i64>>) -> ArrayRef {
    Arc::new(Int64Array::from(rows.collect::<Vec<_>>()))
}
fn opt_str(rows: impl Iterator<Item = Option<String>>) -> ArrayRef {
    Arc::new(StringArray::from(rows.collect::<Vec<_>>()))
}

pub fn write_events(path: &Path, rows: &[NbaEventRow]) -> Result<u64, WarehouseError> {
    let schema = Schema::new(vec![
        Field::new("event_id", DataType::Utf8, false),
        Field::new("event_ticker", DataType::Utf8, false),
        Field::new("series_ticker", DataType::Utf8, false),
        Field::new("event_title", DataType::Utf8, true),
        Field::new("event_subtitle", DataType::Utf8, true),
        Field::new("event_category", DataType::Utf8, true),
        Field::new("mutually_exclusive", DataType::Boolean, true),
        Field::new("last_updated_ts", DataType::Utf8, true),
        Field::new("sport", DataType::Utf8, false),
        Field::new("league", DataType::Utf8, false),
        Field::new("season", DataType::Utf8, false),
        Field::new("season_phase", DataType::Utf8, false),
        Field::new("phase_method", DataType::Utf8, false),
        Field::new("home_team_code", DataType::Utf8, true),
        Field::new("away_team_code", DataType::Utf8, true),
        Field::new("game_date", DataType::Utf8, true),
        Field::new("source", DataType::Utf8, false),
        ts_utc("ingested_at", false),
        Field::new("schema_version", DataType::Utf8, false),
    ]);
    let batch = RecordBatch::try_new(
        Arc::new(schema),
        vec![
            Arc::new(StringArray::from(
                rows.iter().map(|r| r.event_id.clone()).collect::<Vec<_>>(),
            )) as ArrayRef,
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
            opt_str(rows.iter().map(|r| r.event_title.clone())),
            opt_str(rows.iter().map(|r| r.event_subtitle.clone())),
            opt_str(rows.iter().map(|r| r.event_category.clone())),
            Arc::new(BooleanArray::from(
                rows.iter()
                    .map(|r| r.mutually_exclusive)
                    .collect::<Vec<_>>(),
            )),
            opt_str(rows.iter().map(|r| r.last_updated_ts.clone())),
            Arc::new(StringArray::from(
                rows.iter().map(|r| r.sport.clone()).collect::<Vec<_>>(),
            )),
            Arc::new(StringArray::from(
                rows.iter().map(|r| r.league.clone()).collect::<Vec<_>>(),
            )),
            Arc::new(StringArray::from(
                rows.iter().map(|r| r.season.clone()).collect::<Vec<_>>(),
            )),
            Arc::new(StringArray::from(
                rows.iter()
                    .map(|r| r.season_phase.clone())
                    .collect::<Vec<_>>(),
            )),
            Arc::new(StringArray::from(
                rows.iter()
                    .map(|r| r.phase_method.clone())
                    .collect::<Vec<_>>(),
            )),
            opt_str(rows.iter().map(|r| r.home_team_code.clone())),
            opt_str(rows.iter().map(|r| r.away_team_code.clone())),
            opt_str(rows.iter().map(|r| r.game_date.clone())),
            Arc::new(StringArray::from(
                rows.iter().map(|r| r.source.clone()).collect::<Vec<_>>(),
            )),
            Arc::new(
                TimestampMillisecondArray::from(
                    rows.iter()
                        .map(|r| r.ingested_at.timestamp_millis())
                        .collect::<Vec<_>>(),
                )
                .with_timezone("UTC"),
            ),
            Arc::new(StringArray::from(
                rows.iter()
                    .map(|r| r.schema_version.clone())
                    .collect::<Vec<_>>(),
            )),
        ],
    )
    .map_err(|e| WarehouseError::Schema(e.to_string()))?;
    write_batch(path, batch)
}

pub fn write_markets(path: &Path, rows: &[NbaMarketRow]) -> Result<u64, WarehouseError> {
    let schema = Schema::new(vec![
        Field::new("market_id", DataType::Utf8, false),
        Field::new("ticker", DataType::Utf8, false),
        Field::new("event_id", DataType::Utf8, false),
        Field::new("game_id", DataType::Utf8, false),
        Field::new("series_ticker", DataType::Utf8, false),
        Field::new("market_title", DataType::Utf8, true),
        Field::new("yes_subtitle", DataType::Utf8, true),
        Field::new("no_subtitle", DataType::Utf8, true),
        Field::new("team", DataType::Utf8, true),
        Field::new("opponent", DataType::Utf8, true),
        Field::new("market_status", DataType::Utf8, true),
        Field::new("result", DataType::Utf8, true),
        Field::new("settlement_value_e4", DataType::Int64, true),
        Field::new("volume_hundredths", DataType::Int64, true),
        Field::new("open_interest_hundredths", DataType::Int64, true),
        Field::new("last_price_e4", DataType::Int64, true),
        Field::new("yes_bid_e4", DataType::Int64, true),
        Field::new("yes_ask_e4", DataType::Int64, true),
        Field::new("open_time", DataType::Utf8, true),
        Field::new("close_time", DataType::Utf8, true),
        Field::new("expiration_time", DataType::Utf8, true),
        Field::new("settlement_time", DataType::Utf8, true),
        Field::new("created_time", DataType::Utf8, true),
        Field::new("updated_time", DataType::Utf8, true),
        Field::new("occurrence_datetime", DataType::Utf8, true),
        Field::new("sport", DataType::Utf8, false),
        Field::new("league", DataType::Utf8, false),
        Field::new("season", DataType::Utf8, false),
        Field::new("season_phase", DataType::Utf8, false),
        Field::new("source", DataType::Utf8, false),
        ts_utc("ingested_at", false),
        Field::new("schema_version", DataType::Utf8, false),
    ]);
    let batch = RecordBatch::try_new(
        Arc::new(schema),
        vec![
            Arc::new(StringArray::from(
                rows.iter().map(|r| r.market_id.clone()).collect::<Vec<_>>(),
            )) as ArrayRef,
            Arc::new(StringArray::from(
                rows.iter().map(|r| r.ticker.clone()).collect::<Vec<_>>(),
            )),
            Arc::new(StringArray::from(
                rows.iter().map(|r| r.event_id.clone()).collect::<Vec<_>>(),
            )),
            Arc::new(StringArray::from(
                rows.iter().map(|r| r.game_id.clone()).collect::<Vec<_>>(),
            )),
            Arc::new(StringArray::from(
                rows.iter()
                    .map(|r| r.series_ticker.clone())
                    .collect::<Vec<_>>(),
            )),
            opt_str(rows.iter().map(|r| r.market_title.clone())),
            opt_str(rows.iter().map(|r| r.yes_subtitle.clone())),
            opt_str(rows.iter().map(|r| r.no_subtitle.clone())),
            opt_str(rows.iter().map(|r| r.team.clone())),
            opt_str(rows.iter().map(|r| r.opponent.clone())),
            opt_str(rows.iter().map(|r| r.market_status.clone())),
            opt_str(rows.iter().map(|r| r.result.clone())),
            opt_i64(rows.iter().map(|r| r.settlement_value_e4)),
            opt_i64(rows.iter().map(|r| r.volume_hundredths)),
            opt_i64(rows.iter().map(|r| r.open_interest_hundredths)),
            opt_i64(rows.iter().map(|r| r.last_price_e4)),
            opt_i64(rows.iter().map(|r| r.yes_bid_e4)),
            opt_i64(rows.iter().map(|r| r.yes_ask_e4)),
            opt_str(rows.iter().map(|r| r.open_time.clone())),
            opt_str(rows.iter().map(|r| r.close_time.clone())),
            opt_str(rows.iter().map(|r| r.expiration_time.clone())),
            opt_str(rows.iter().map(|r| r.settlement_time.clone())),
            opt_str(rows.iter().map(|r| r.created_time.clone())),
            opt_str(rows.iter().map(|r| r.updated_time.clone())),
            opt_str(rows.iter().map(|r| r.occurrence_datetime.clone())),
            Arc::new(StringArray::from(
                rows.iter().map(|r| r.sport.clone()).collect::<Vec<_>>(),
            )),
            Arc::new(StringArray::from(
                rows.iter().map(|r| r.league.clone()).collect::<Vec<_>>(),
            )),
            Arc::new(StringArray::from(
                rows.iter().map(|r| r.season.clone()).collect::<Vec<_>>(),
            )),
            Arc::new(StringArray::from(
                rows.iter()
                    .map(|r| r.season_phase.clone())
                    .collect::<Vec<_>>(),
            )),
            Arc::new(StringArray::from(
                rows.iter().map(|r| r.source.clone()).collect::<Vec<_>>(),
            )),
            Arc::new(
                TimestampMillisecondArray::from(
                    rows.iter()
                        .map(|r| r.ingested_at.timestamp_millis())
                        .collect::<Vec<_>>(),
                )
                .with_timezone("UTC"),
            ),
            Arc::new(StringArray::from(
                rows.iter()
                    .map(|r| r.schema_version.clone())
                    .collect::<Vec<_>>(),
            )),
        ],
    )
    .map_err(|e| WarehouseError::Schema(e.to_string()))?;
    write_batch(path, batch)
}

pub fn write_games(path: &Path, rows: &[NbaGameRow]) -> Result<u64, WarehouseError> {
    let schema = Schema::new(vec![
        Field::new("game_id", DataType::Utf8, false),
        Field::new("event_id", DataType::Utf8, false),
        Field::new("event_ticker", DataType::Utf8, false),
        Field::new("season", DataType::Utf8, false),
        Field::new("season_phase", DataType::Utf8, false),
        Field::new("phase_method", DataType::Utf8, false),
        Field::new("game_date", DataType::Utf8, true),
        Field::new("scheduled_start", DataType::Utf8, true),
        Field::new("home_team", DataType::Utf8, true),
        Field::new("away_team", DataType::Utf8, true),
        Field::new("home_team_code", DataType::Utf8, true),
        Field::new("away_team_code", DataType::Utf8, true),
        Field::new("home_market_ticker", DataType::Utf8, true),
        Field::new("away_market_ticker", DataType::Utf8, true),
        Field::new("market_tickers", DataType::Utf8, false),
        Field::new("market_count", DataType::UInt32, false),
        Field::new("event_status", DataType::Utf8, true),
        Field::new("settlement_status", DataType::Utf8, true),
        Field::new("event_title", DataType::Utf8, true),
        Field::new("event_subtitle", DataType::Utf8, true),
        Field::new("source", DataType::Utf8, false),
        Field::new("schema_version", DataType::Utf8, false),
    ]);
    let batch = RecordBatch::try_new(
        Arc::new(schema),
        vec![
            Arc::new(StringArray::from(
                rows.iter().map(|r| r.game_id.clone()).collect::<Vec<_>>(),
            )) as ArrayRef,
            Arc::new(StringArray::from(
                rows.iter().map(|r| r.event_id.clone()).collect::<Vec<_>>(),
            )),
            Arc::new(StringArray::from(
                rows.iter()
                    .map(|r| r.event_ticker.clone())
                    .collect::<Vec<_>>(),
            )),
            Arc::new(StringArray::from(
                rows.iter().map(|r| r.season.clone()).collect::<Vec<_>>(),
            )),
            Arc::new(StringArray::from(
                rows.iter()
                    .map(|r| r.season_phase.clone())
                    .collect::<Vec<_>>(),
            )),
            Arc::new(StringArray::from(
                rows.iter()
                    .map(|r| r.phase_method.clone())
                    .collect::<Vec<_>>(),
            )),
            opt_str(rows.iter().map(|r| r.game_date.clone())),
            opt_str(rows.iter().map(|r| r.scheduled_start.clone())),
            opt_str(rows.iter().map(|r| r.home_team.clone())),
            opt_str(rows.iter().map(|r| r.away_team.clone())),
            opt_str(rows.iter().map(|r| r.home_team_code.clone())),
            opt_str(rows.iter().map(|r| r.away_team_code.clone())),
            opt_str(rows.iter().map(|r| r.home_market_ticker.clone())),
            opt_str(rows.iter().map(|r| r.away_market_ticker.clone())),
            Arc::new(StringArray::from(
                rows.iter()
                    .map(|r| r.market_tickers.join(","))
                    .collect::<Vec<_>>(),
            )),
            Arc::new(UInt32Array::from(
                rows.iter().map(|r| r.market_count).collect::<Vec<_>>(),
            )),
            opt_str(rows.iter().map(|r| r.event_status.clone())),
            opt_str(rows.iter().map(|r| r.settlement_status.clone())),
            opt_str(rows.iter().map(|r| r.event_title.clone())),
            opt_str(rows.iter().map(|r| r.event_subtitle.clone())),
            Arc::new(StringArray::from(
                rows.iter().map(|r| r.source.clone()).collect::<Vec<_>>(),
            )),
            Arc::new(StringArray::from(
                rows.iter()
                    .map(|r| r.schema_version.clone())
                    .collect::<Vec<_>>(),
            )),
        ],
    )
    .map_err(|e| WarehouseError::Schema(e.to_string()))?;
    write_batch(path, batch)
}

pub fn write_candles(path: &Path, rows: &[NbaCandleRow]) -> Result<u64, WarehouseError> {
    let schema = Schema::new(vec![
        Field::new("ticker", DataType::Utf8, false),
        Field::new("event_id", DataType::Utf8, false),
        Field::new("market_id", DataType::Utf8, false),
        Field::new("game_id", DataType::Utf8, false),
        Field::new("end_period_ts", DataType::Int64, false),
        ts_utc("start_time", false),
        ts_utc("end_time", false),
        Field::new("yes_bid_open_e4", DataType::Int64, true),
        Field::new("yes_bid_high_e4", DataType::Int64, true),
        Field::new("yes_bid_low_e4", DataType::Int64, true),
        Field::new("yes_bid_close_e4", DataType::Int64, true),
        Field::new("yes_ask_open_e4", DataType::Int64, true),
        Field::new("yes_ask_high_e4", DataType::Int64, true),
        Field::new("yes_ask_low_e4", DataType::Int64, true),
        Field::new("yes_ask_close_e4", DataType::Int64, true),
        Field::new("price_open_e4", DataType::Int64, true),
        Field::new("price_high_e4", DataType::Int64, true),
        Field::new("price_low_e4", DataType::Int64, true),
        Field::new("price_close_e4", DataType::Int64, true),
        Field::new("price_mean_e4", DataType::Int64, true),
        Field::new("price_previous_e4", DataType::Int64, true),
        Field::new("volume_hundredths", DataType::Int64, true),
        Field::new("open_interest_hundredths", DataType::Int64, true),
        Field::new("market_data_type", DataType::Utf8, false),
        Field::new("orderbook_depth_available", DataType::Boolean, false),
        Field::new("is_valid", DataType::Boolean, false),
        Field::new("is_duplicate", DataType::Boolean, false),
        Field::new("is_pre_market", DataType::Boolean, false),
        Field::new("is_post_market", DataType::Boolean, false),
        Field::new("source", DataType::Utf8, false),
        ts_utc("ingested_at", false),
        Field::new("schema_version", DataType::Utf8, false),
    ]);
    let batch = RecordBatch::try_new(
        Arc::new(schema),
        vec![
            Arc::new(StringArray::from(
                rows.iter().map(|r| r.ticker.clone()).collect::<Vec<_>>(),
            )) as ArrayRef,
            Arc::new(StringArray::from(
                rows.iter().map(|r| r.event_id.clone()).collect::<Vec<_>>(),
            )),
            Arc::new(StringArray::from(
                rows.iter().map(|r| r.market_id.clone()).collect::<Vec<_>>(),
            )),
            Arc::new(StringArray::from(
                rows.iter().map(|r| r.game_id.clone()).collect::<Vec<_>>(),
            )),
            Arc::new(Int64Array::from(
                rows.iter().map(|r| r.end_period_ts).collect::<Vec<_>>(),
            )),
            Arc::new(
                TimestampMillisecondArray::from(
                    rows.iter()
                        .map(|r| r.start_time.timestamp_millis())
                        .collect::<Vec<_>>(),
                )
                .with_timezone("UTC"),
            ),
            Arc::new(
                TimestampMillisecondArray::from(
                    rows.iter()
                        .map(|r| r.end_time.timestamp_millis())
                        .collect::<Vec<_>>(),
                )
                .with_timezone("UTC"),
            ),
            opt_i64(rows.iter().map(|r| r.yes_bid_open_e4)),
            opt_i64(rows.iter().map(|r| r.yes_bid_high_e4)),
            opt_i64(rows.iter().map(|r| r.yes_bid_low_e4)),
            opt_i64(rows.iter().map(|r| r.yes_bid_close_e4)),
            opt_i64(rows.iter().map(|r| r.yes_ask_open_e4)),
            opt_i64(rows.iter().map(|r| r.yes_ask_high_e4)),
            opt_i64(rows.iter().map(|r| r.yes_ask_low_e4)),
            opt_i64(rows.iter().map(|r| r.yes_ask_close_e4)),
            opt_i64(rows.iter().map(|r| r.price_open_e4)),
            opt_i64(rows.iter().map(|r| r.price_high_e4)),
            opt_i64(rows.iter().map(|r| r.price_low_e4)),
            opt_i64(rows.iter().map(|r| r.price_close_e4)),
            opt_i64(rows.iter().map(|r| r.price_mean_e4)),
            opt_i64(rows.iter().map(|r| r.price_previous_e4)),
            opt_i64(rows.iter().map(|r| r.volume_hundredths)),
            opt_i64(rows.iter().map(|r| r.open_interest_hundredths)),
            Arc::new(StringArray::from(
                rows.iter()
                    .map(|r| r.market_data_type.clone())
                    .collect::<Vec<_>>(),
            )),
            Arc::new(BooleanArray::from(
                rows.iter()
                    .map(|r| r.orderbook_depth_available)
                    .collect::<Vec<_>>(),
            )),
            Arc::new(BooleanArray::from(
                rows.iter().map(|r| r.is_valid).collect::<Vec<_>>(),
            )),
            Arc::new(BooleanArray::from(
                rows.iter().map(|r| r.is_duplicate).collect::<Vec<_>>(),
            )),
            Arc::new(BooleanArray::from(
                rows.iter().map(|r| r.is_pre_market).collect::<Vec<_>>(),
            )),
            Arc::new(BooleanArray::from(
                rows.iter().map(|r| r.is_post_market).collect::<Vec<_>>(),
            )),
            Arc::new(StringArray::from(
                rows.iter().map(|r| r.source.clone()).collect::<Vec<_>>(),
            )),
            Arc::new(
                TimestampMillisecondArray::from(
                    rows.iter()
                        .map(|r| r.ingested_at.timestamp_millis())
                        .collect::<Vec<_>>(),
                )
                .with_timezone("UTC"),
            ),
            Arc::new(StringArray::from(
                rows.iter()
                    .map(|r| r.schema_version.clone())
                    .collect::<Vec<_>>(),
            )),
        ],
    )
    .map_err(|e| WarehouseError::Schema(e.to_string()))?;
    write_batch(path, batch)
}

pub fn write_trades(path: &Path, rows: &[NbaTradeRow]) -> Result<u64, WarehouseError> {
    let schema = Schema::new(vec![
        Field::new("trade_id", DataType::Utf8, false),
        Field::new("ticker", DataType::Utf8, false),
        Field::new("event_id", DataType::Utf8, false),
        Field::new("market_id", DataType::Utf8, false),
        Field::new("game_id", DataType::Utf8, false),
        ts_utc("timestamp", false),
        Field::new("yes_price_e4", DataType::Int64, true),
        Field::new("no_price_e4", DataType::Int64, true),
        Field::new("quantity_hundredths", DataType::Int64, true),
        Field::new("taker_outcome_side", DataType::Utf8, true),
        Field::new("taker_book_side", DataType::Utf8, true),
        Field::new("taker_side", DataType::Utf8, true),
        Field::new("side_classification", DataType::Utf8, false),
        Field::new("is_block_trade", DataType::Boolean, false),
        Field::new("is_duplicate", DataType::Boolean, false),
        Field::new("source", DataType::Utf8, false),
        ts_utc("ingested_at", false),
        Field::new("schema_version", DataType::Utf8, false),
    ]);
    let batch = RecordBatch::try_new(
        Arc::new(schema),
        vec![
            Arc::new(StringArray::from(
                rows.iter().map(|r| r.trade_id.clone()).collect::<Vec<_>>(),
            )) as ArrayRef,
            Arc::new(StringArray::from(
                rows.iter().map(|r| r.ticker.clone()).collect::<Vec<_>>(),
            )),
            Arc::new(StringArray::from(
                rows.iter().map(|r| r.event_id.clone()).collect::<Vec<_>>(),
            )),
            Arc::new(StringArray::from(
                rows.iter().map(|r| r.market_id.clone()).collect::<Vec<_>>(),
            )),
            Arc::new(StringArray::from(
                rows.iter().map(|r| r.game_id.clone()).collect::<Vec<_>>(),
            )),
            Arc::new(
                TimestampMillisecondArray::from(
                    rows.iter()
                        .map(|r| r.timestamp.timestamp_millis())
                        .collect::<Vec<_>>(),
                )
                .with_timezone("UTC"),
            ),
            opt_i64(rows.iter().map(|r| r.yes_price_e4)),
            opt_i64(rows.iter().map(|r| r.no_price_e4)),
            opt_i64(rows.iter().map(|r| r.quantity_hundredths)),
            opt_str(rows.iter().map(|r| r.taker_outcome_side.clone())),
            opt_str(rows.iter().map(|r| r.taker_book_side.clone())),
            opt_str(rows.iter().map(|r| r.taker_side.clone())),
            Arc::new(StringArray::from(
                rows.iter()
                    .map(|r| r.side_classification.clone())
                    .collect::<Vec<_>>(),
            )),
            Arc::new(BooleanArray::from(
                rows.iter().map(|r| r.is_block_trade).collect::<Vec<_>>(),
            )),
            Arc::new(BooleanArray::from(
                rows.iter().map(|r| r.is_duplicate).collect::<Vec<_>>(),
            )),
            Arc::new(StringArray::from(
                rows.iter().map(|r| r.source.clone()).collect::<Vec<_>>(),
            )),
            Arc::new(
                TimestampMillisecondArray::from(
                    rows.iter()
                        .map(|r| r.ingested_at.timestamp_millis())
                        .collect::<Vec<_>>(),
                )
                .with_timezone("UTC"),
            ),
            Arc::new(StringArray::from(
                rows.iter()
                    .map(|r| r.schema_version.clone())
                    .collect::<Vec<_>>(),
            )),
        ],
    )
    .map_err(|e| WarehouseError::Schema(e.to_string()))?;
    write_batch(path, batch)
}

pub fn write_causal(path: &Path, rows: &[CausalCandleFeatures]) -> Result<u64, WarehouseError> {
    let schema = Schema::new(vec![
        Field::new("ticker", DataType::Utf8, false),
        Field::new("end_period_ts", DataType::Int64, false),
        Field::new("mid_close_e4", DataType::Int64, true),
        Field::new("spread_e4", DataType::Int64, true),
        Field::new("spread_bps", DataType::Int64, true),
        Field::new("return_1m_e4", DataType::Int64, true),
        Field::new("return_5m_e4", DataType::Int64, true),
        Field::new("return_15m_e4", DataType::Int64, true),
        Field::new("look_ahead", DataType::Boolean, false),
    ]);
    let batch = RecordBatch::try_new(
        Arc::new(schema),
        vec![
            Arc::new(StringArray::from(
                rows.iter().map(|r| r.ticker.clone()).collect::<Vec<_>>(),
            )) as ArrayRef,
            Arc::new(Int64Array::from(
                rows.iter().map(|r| r.end_period_ts).collect::<Vec<_>>(),
            )),
            opt_i64(rows.iter().map(|r| r.mid_close_e4)),
            opt_i64(rows.iter().map(|r| r.spread_e4)),
            opt_i64(rows.iter().map(|r| r.spread_bps)),
            opt_i64(rows.iter().map(|r| r.return_1m_e4)),
            opt_i64(rows.iter().map(|r| r.return_5m_e4)),
            opt_i64(rows.iter().map(|r| r.return_15m_e4)),
            Arc::new(BooleanArray::from(
                rows.iter().map(|r| r.look_ahead).collect::<Vec<_>>(),
            )),
        ],
    )
    .map_err(|e| WarehouseError::Schema(e.to_string()))?;
    write_batch(path, batch)
}

pub fn write_complementarity(
    path: &Path,
    rows: &[ComplementarityRow],
) -> Result<u64, WarehouseError> {
    let schema = Schema::new(vec![
        Field::new("event_id", DataType::Utf8, false),
        Field::new("end_period_ts", DataType::Int64, false),
        Field::new("a_ticker", DataType::Utf8, false),
        Field::new("b_ticker", DataType::Utf8, false),
        Field::new("a_mid_e4", DataType::Int64, true),
        Field::new("b_mid_e4", DataType::Int64, true),
        Field::new("combined_mid_e4", DataType::Int64, true),
        Field::new("complementarity_error_e4", DataType::Int64, true),
    ]);
    let batch = RecordBatch::try_new(
        Arc::new(schema),
        vec![
            Arc::new(StringArray::from(
                rows.iter().map(|r| r.event_id.clone()).collect::<Vec<_>>(),
            )) as ArrayRef,
            Arc::new(Int64Array::from(
                rows.iter().map(|r| r.end_period_ts).collect::<Vec<_>>(),
            )),
            Arc::new(StringArray::from(
                rows.iter().map(|r| r.a_ticker.clone()).collect::<Vec<_>>(),
            )),
            Arc::new(StringArray::from(
                rows.iter().map(|r| r.b_ticker.clone()).collect::<Vec<_>>(),
            )),
            opt_i64(rows.iter().map(|r| r.a_mid_e4)),
            opt_i64(rows.iter().map(|r| r.b_mid_e4)),
            opt_i64(rows.iter().map(|r| r.combined_mid_e4)),
            opt_i64(rows.iter().map(|r| r.complementarity_error_e4)),
        ],
    )
    .map_err(|e| WarehouseError::Schema(e.to_string()))?;
    write_batch(path, batch)
}

pub fn write_trade_agg(path: &Path, rows: &[TradeMinuteAgg]) -> Result<u64, WarehouseError> {
    let schema = Schema::new(vec![
        Field::new("ticker", DataType::Utf8, false),
        Field::new("minute_ts", DataType::Int64, false),
        Field::new("trade_count", DataType::UInt64, false),
        Field::new("trade_volume_hundredths", DataType::Int64, false),
        Field::new("average_trade_size_hundredths", DataType::Int64, true),
        Field::new("median_trade_size_hundredths", DataType::Int64, true),
        Field::new("max_trade_size_hundredths", DataType::Int64, true),
        Field::new("buy_volume_hundredths", DataType::Int64, false),
        Field::new("sell_volume_hundredths", DataType::Int64, false),
        Field::new("unknown_side_volume_hundredths", DataType::Int64, false),
    ]);
    let batch = RecordBatch::try_new(
        Arc::new(schema),
        vec![
            Arc::new(StringArray::from(
                rows.iter().map(|r| r.ticker.clone()).collect::<Vec<_>>(),
            )) as ArrayRef,
            Arc::new(Int64Array::from(
                rows.iter().map(|r| r.minute_ts).collect::<Vec<_>>(),
            )),
            Arc::new(UInt64Array::from(
                rows.iter().map(|r| r.trade_count).collect::<Vec<_>>(),
            )),
            Arc::new(Int64Array::from(
                rows.iter()
                    .map(|r| r.trade_volume_hundredths)
                    .collect::<Vec<_>>(),
            )),
            opt_i64(rows.iter().map(|r| r.average_trade_size_hundredths)),
            opt_i64(rows.iter().map(|r| r.median_trade_size_hundredths)),
            opt_i64(rows.iter().map(|r| r.max_trade_size_hundredths)),
            Arc::new(Int64Array::from(
                rows.iter()
                    .map(|r| r.buy_volume_hundredths)
                    .collect::<Vec<_>>(),
            )),
            Arc::new(Int64Array::from(
                rows.iter()
                    .map(|r| r.sell_volume_hundredths)
                    .collect::<Vec<_>>(),
            )),
            Arc::new(Int64Array::from(
                rows.iter()
                    .map(|r| r.unknown_side_volume_hundredths)
                    .collect::<Vec<_>>(),
            )),
        ],
    )
    .map_err(|e| WarehouseError::Schema(e.to_string()))?;
    write_batch(path, batch)
}
