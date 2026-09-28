//! Seed COMPLETE demo research partitions for control-plane e2e runs.
//!
//! Not production market data — synthetic orderbook quotes for FIRST01 signal proof.

use chrono::{Duration, NaiveDate, TimeZone, Utc};

use momento_research_data::{
    CompletenessStatus, DailyManifest, NormalizedSource, OrderbookEvent, ResearchPaths,
    ResearchSeason, ResearchSport, write_orderbook_parquet, write_trades_parquet,
};

use crate::error::{BacktestError, BacktestErrorCode};
use crate::parse::{parse_season, parse_time_frame};

pub fn seed_complete_range(
    paths: &ResearchPaths,
    season_label: &str,
    start: NaiveDate,
    end: NaiveDate,
) -> Result<u32, BacktestError> {
    let season = ResearchSeason {
        label: season_label.to_string(),
    };
    let mut days = 0u32;
    let mut d = start;
    while d <= end {
        for sport in [ResearchSport::Mlb, ResearchSport::Wnba] {
            seed_one_day(
                paths,
                &season,
                sport,
                d,
                d == start && sport == ResearchSport::Mlb,
            )?;
            days += 1;
        }
        d += Duration::days(1);
    }
    Ok(days)
}

pub fn seed_from_sheet_inputs(
    paths: &mut ResearchPaths,
    season_raw: &str,
    time_frame_raw: &str,
) -> Result<u32, BacktestError> {
    let season = parse_season(season_raw)?;
    paths.season.label = season.label.clone();
    let tf = parse_time_frame(time_frame_raw, &season)?;
    seed_complete_range(paths, &season.label, tf.start, tf.end)
}

fn seed_one_day(
    paths: &ResearchPaths,
    season: &ResearchSeason,
    sport: ResearchSport,
    date: NaiveDate,
    with_signals: bool,
) -> Result<(), BacktestError> {
    let mut manifest = DailyManifest::new(sport, season, date);
    manifest.markets_discovered = 1;
    manifest.markets_collected = 1;
    manifest.missing_markets.clear();
    manifest.invalid_records = 0;
    manifest.raw_event_count = if with_signals { 3 } else { 0 };
    manifest.normalized_event_count = manifest.raw_event_count;
    manifest.trade_count = 0;
    manifest.orderbook_event_count = if with_signals { 3 } else { 0 };
    manifest.completeness_status = CompletenessStatus::Complete;
    manifest.collection_completed_at = Some(Utc::now());
    manifest
        .notes
        .push("DEMO FIXTURE: synthetic COMPLETE partition for Sheets control-plane e2e".into());

    let trades_dir = paths.trades_day(sport, date);
    let ob_dir = paths.orderbook_day(sport, date);
    std::fs::create_dir_all(&trades_dir)?;
    std::fs::create_dir_all(&ob_dir)?;
    write_trades_parquet(&trades_dir.join("trades.parquet"), &[])
        .map_err(|e| BacktestError::coded(BacktestErrorCode::ResultWriteError, e.to_string()))?;

    let events = if with_signals {
        demo_first01_quotes(sport, date)
    } else {
        Vec::new()
    };
    write_orderbook_parquet(&ob_dir.join("orderbook.parquet"), &events)
        .map_err(|e| BacktestError::coded(BacktestErrorCode::ResultWriteError, e.to_string()))?;

    manifest
        .write_atomic(paths, sport)
        .map_err(|e| BacktestError::coded(BacktestErrorCode::ResultWriteError, e.to_string()))?;
    Ok(())
}

fn demo_first01_quotes(sport: ResearchSport, date: NaiveDate) -> Vec<OrderbookEvent> {
    let base = Utc.from_utc_datetime(&date.and_hms_opt(18, 0, 0).unwrap());
    let ticker = format!("{}-DEMO-YES", sport.series_ticker());
    let game_id = 9001u128;
    let market_id = 9002u128;
    let mk = |offset_s: i64, bid: u16, ask: u16| -> OrderbookEvent {
        let ts = base + Duration::seconds(offset_s);
        OrderbookEvent {
            exchange_timestamp_ms: Some(ts.timestamp_millis()),
            received_timestamp: ts + Duration::milliseconds(5),
            ticker: ticker.clone(),
            market_id,
            game_id,
            event_type: "demo_fixture".into(),
            source: NormalizedSource::RestSnapshot,
            sequence_number: Some(offset_s as u64),
            subscription_id: None,
            yes_bid_cents: Some(bid),
            yes_ask_cents: Some(ask),
            yes_bid_depth_hundredths: Some(1000),
            yes_ask_depth_hundredths: Some(1000),
            levels: vec![],
            sequence_gap: false,
            resync_count: 0,
            first_missing_sequence: None,
            last_valid_sequence: None,
        }
    };
    // 79 (watch) → 80 (first) → 81 with ask 82 (maker-eligible entry)
    vec![mk(0, 79, 80), mk(1, 80, 81), mk(2, 81, 82)]
}
