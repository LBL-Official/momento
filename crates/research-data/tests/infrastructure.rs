//! Research data infrastructure tests.

use chrono::{NaiveDate, Timelike, Utc};
use momento_kalshi::{
    ApplyResult, SeqOutcome, game_id_for_event_ticker, market_id_for_ticker, parse_orderbook_delta,
    parse_orderbook_snapshot, parse_ws_frame,
};
use momento_research_data::{
    CompletenessStatus, DailyManifest, DiscoveredMarket, MarketMetadata, NormalizedSource,
    OrderbookEvent, OrderbookLevel, OrderbookReconstructor, PublicTrade, ResearchPaths,
    ResearchSeason, ResearchSport, SCHEMA_VERSION, backfill_dates, collection_schedule,
    detect_sequence_gap, export_csv, metadata_from_kalshi, next_collection_run, no_synthetic_rows,
    same_game_different_market, validate_discovered_pairing, validate_metadata, validate_orderbook,
    validate_trades,
};
use tempfile::tempdir;

#[test]
fn market_discovery_identity_two_sided_game() {
    let sport = ResearchSport::Mlb;
    let game_event = "KXMLBGAME-25AUG25WSHCOL";
    let a = metadata_from_kalshi(
        &momento_kalshi::KalshiMarket {
            ticker: "KXMLBGAME-25AUG25WSHCOL-WSH".into(),
            event_ticker: game_event.into(),
            series_ticker: Some("KXMLBGAME".into()),
            status: Some("settled".into()),
            subtitle: Some("Washington".into()),
            open_time: None,
            close_time: None,
            yes_bid_dollars: None,
            yes_ask_dollars: None,
            last_price_dollars: None,
            yes_bid_size_fp: None,
            yes_ask_size_fp: None,
            result: None,
            settlement_value_dollars: None,
            settlement_ts: None,
            updated_time: None,
            price_level_structure: None,
            price_ranges: Vec::new(),
        },
        sport,
    );
    let b = metadata_from_kalshi(
        &momento_kalshi::KalshiMarket {
            ticker: "KXMLBGAME-25AUG25WSHCOL-COL".into(),
            event_ticker: game_event.into(),
            series_ticker: Some("KXMLBGAME".into()),
            status: Some("settled".into()),
            subtitle: Some("Colorado".into()),
            open_time: None,
            close_time: None,
            yes_bid_dollars: None,
            yes_ask_dollars: None,
            last_price_dollars: None,
            yes_bid_size_fp: None,
            yes_ask_size_fp: None,
            result: None,
            settlement_value_dollars: None,
            settlement_ts: None,
            updated_time: None,
            price_level_structure: None,
            price_ranges: Vec::new(),
        },
        sport,
    );
    assert_eq!(a.game_id, b.game_id);
    assert_ne!(a.market_id, b.market_id);
    assert!(same_game_different_market(&a, &b));
    assert_eq!(a.game_id, game_id_for_event_ticker(game_event).raw());
    assert_eq!(
        a.market_id,
        market_id_for_ticker("KXMLBGAME-25AUG25WSHCOL-WSH").raw()
    );
    assert_ne!(
        a.market_id,
        market_id_for_ticker("KXMLBGAME-25AUG25WSHCOL-COL").raw()
    );
}

#[test]
fn orderbook_snapshot_and_delta_reconstruction() {
    let mut recon = OrderbookReconstructor::new();
    let snap = parse_ws_frame(
        r#"{"type":"orderbook_snapshot","sid":2,"seq":2,"msg":{"market_ticker":"KXMLBGAME-TEST","yes_dollars_fp":[["0.8000","10.00"]],"no_dollars_fp":[["0.1900","4.00"]]}}"#,
    )
    .unwrap();
    let snap_msg = parse_orderbook_snapshot(&snap).unwrap();
    let applied = recon.apply_snapshot(2, 2, &snap_msg, false).unwrap();
    assert!(matches!(applied, ApplyResult::Updated { .. }));
    let depth = recon.depth("KXMLBGAME-TEST").expect("depth");
    assert_eq!(depth.yes_bids[0].price_cents, 80);

    let delta = parse_ws_frame(
        r#"{"type":"orderbook_delta","sid":2,"seq":3,"msg":{"market_ticker":"KXMLBGAME-TEST","price_dollars":"0.8100","delta_fp":"5.00","side":"yes","ts_ms":1715793600123}}"#,
    )
    .unwrap();
    let delta_msg = parse_orderbook_delta(&delta).unwrap();
    recon.apply_delta(2, 3, &delta_msg).unwrap();
    let depth = recon.depth("KXMLBGAME-TEST").expect("depth");
    assert_eq!(depth.yes_bids[0].price_cents, 81);
    assert_eq!(depth.ts_ms, Some(1715793600123));
}

#[test]
fn sequence_gap_detection_and_no_quote_after_gap() {
    assert_eq!(detect_sequence_gap(Some(2), 3), SeqOutcome::Apply);
    assert_eq!(detect_sequence_gap(Some(2), 4), SeqOutcome::Gap);

    let mut recon = OrderbookReconstructor::new();
    let snap = parse_ws_frame(
        r#"{"type":"orderbook_snapshot","sid":2,"seq":2,"msg":{"market_ticker":"KXMLBGAME-TEST","yes_dollars_fp":[["0.8000","10.00"]],"no_dollars_fp":[["0.1900","4.00"]]}}"#,
    )
    .unwrap();
    recon
        .apply_snapshot(2, 2, &parse_orderbook_snapshot(&snap).unwrap(), false)
        .unwrap();
    let delta = parse_ws_frame(
        r#"{"type":"orderbook_delta","sid":2,"seq":4,"msg":{"market_ticker":"KXMLBGAME-TEST","price_dollars":"0.8100","delta_fp":"5.00","side":"yes"}}"#,
    )
    .unwrap();
    let applied = recon
        .apply_delta(2, 4, &parse_orderbook_delta(&delta).unwrap())
        .unwrap();
    assert_eq!(applied, ApplyResult::Gap);
    assert!(recon.gap_state().sequence_gap);
    assert!(recon.depth("KXMLBGAME-TEST").is_none());
}

#[test]
fn resync_after_gap() {
    let mut recon = OrderbookReconstructor::new();
    let snap = |seq: u64| {
        parse_ws_frame(&format!(
            r#"{{"type":"orderbook_snapshot","sid":2,"seq":{seq},"msg":{{"market_ticker":"KXMLBGAME-TEST","yes_dollars_fp":[["0.8000","10.00"]],"no_dollars_fp":[["0.1900","4.00"]]}}}}"#
        ))
        .unwrap()
    };
    recon
        .apply_snapshot(2, 2, &parse_orderbook_snapshot(&snap(2)).unwrap(), false)
        .unwrap();
    let delta = parse_ws_frame(
        r#"{"type":"orderbook_delta","sid":2,"seq":4,"msg":{"market_ticker":"KXMLBGAME-TEST","price_dollars":"0.8100","delta_fp":"5.00","side":"yes"}}"#,
    )
    .unwrap();
    recon
        .apply_delta(2, 4, &parse_orderbook_delta(&delta).unwrap())
        .unwrap();
    recon
        .apply_snapshot(2, 5, &parse_orderbook_snapshot(&snap(5)).unwrap(), true)
        .unwrap();
    assert_eq!(recon.gap_state().resync_count, 1);
    assert!(recon.depth("KXMLBGAME-TEST").is_some());
}

#[test]
fn timestamp_and_depth_preservation_in_schema() {
    let event = OrderbookEvent {
        exchange_timestamp_ms: Some(1_234),
        received_timestamp: Utc::now(),
        ticker: "T".into(),
        market_id: 1,
        game_id: 2,
        event_type: "rest_snapshot".into(),
        source: NormalizedSource::RestSnapshot,
        sequence_number: Some(9),
        subscription_id: Some(2),
        yes_bid_cents: Some(80),
        yes_ask_cents: Some(81),
        yes_bid_depth_hundredths: Some(1000),
        yes_ask_depth_hundredths: Some(400),
        levels: vec![OrderbookLevel {
            price_cents: 80,
            quantity_hundredths: 1000,
            book_side: "yes".into(),
        }],
        sequence_gap: false,
        resync_count: 0,
        first_missing_sequence: None,
        last_valid_sequence: Some(9),
    };
    assert_eq!(event.exchange_timestamp_ms, Some(1_234));
    assert_eq!(event.levels[0].quantity_hundredths, 1000);
    assert!(validate_orderbook(&[event]).is_valid());
}

#[test]
fn trade_preservation_and_invalid_price_rejection() {
    let good = PublicTrade {
        exchange_timestamp: "2025-08-01T12:00:00Z".into(),
        received_timestamp: Utc::now(),
        ticker: "KXMLBGAME-X".into(),
        market_id: 10,
        game_id: 20,
        trade_id: "t1".into(),
        yes_price_cents: 81,
        quantity_hundredths: 500,
        taker_outcome_side: Some("yes".into()),
        taker_book_side: Some("bid".into()),
        is_block_trade: false,
        source: "rest".into(),
    };
    assert!(validate_trades(&[good]).is_valid());

    let bad = PublicTrade {
        yes_price_cents: 0,
        ..PublicTrade {
            exchange_timestamp: "2025-08-01T12:00:00Z".into(),
            received_timestamp: Utc::now(),
            ticker: "KXMLBGAME-X".into(),
            market_id: 10,
            game_id: 20,
            trade_id: "t2".into(),
            yes_price_cents: 0,
            quantity_hundredths: 500,
            taker_outcome_side: None,
            taker_book_side: None,
            is_block_trade: false,
            source: "rest".into(),
        }
    };
    assert!(!validate_trades(&[bad]).is_valid());
}

#[test]
fn manifest_partial_and_complete() {
    let mut complete = DailyManifest::new(
        ResearchSport::Mlb,
        &ResearchSeason::current(),
        NaiveDate::from_ymd_opt(2025, 8, 1).unwrap(),
    );
    complete.markets_discovered = 2;
    complete.markets_collected = 2;
    complete.finalize_status();
    assert_eq!(complete.completeness_status, CompletenessStatus::Complete);

    let mut partial = DailyManifest::new(
        ResearchSport::Mlb,
        &ResearchSeason::current(),
        NaiveDate::from_ymd_opt(2025, 8, 2).unwrap(),
    );
    partial.markets_discovered = 2;
    partial.markets_collected = 1;
    partial.missing_markets.push("KXMLBGAME-TEST-A".into());
    partial.finalize_status();
    assert_eq!(partial.completeness_status, CompletenessStatus::Partial);
}

#[test]
fn manifest_atomic_write_and_idempotent_rerun() {
    let dir = tempdir().unwrap();
    let mut paths = ResearchPaths::from_env_or_default();
    paths.root = dir.path().join("data");
    let sport = ResearchSport::Wnba;
    let date = NaiveDate::from_ymd_opt(2025, 7, 1).unwrap();
    let mut manifest = DailyManifest::new(sport, &ResearchSeason::current(), date);
    manifest.markets_discovered = 1;
    manifest.markets_collected = 1;
    manifest.finalize_status();
    manifest.write_atomic(&paths, sport).unwrap();
    let again = DailyManifest::read(&paths, sport, date).unwrap().unwrap();
    assert_eq!(again.completeness_status, CompletenessStatus::Complete);
    assert_eq!(again.schema_version, SCHEMA_VERSION);
}

#[test]
fn timezone_correct_schedule() {
    let schedule = collection_schedule();
    assert_eq!(schedule.timezone, "America/Los_Angeles");
    assert_eq!(schedule.hour_local, 3);
    let next = next_collection_run(Utc::now());
    let local = next.with_timezone(&chrono_tz::America::Los_Angeles);
    assert_eq!(local.hour(), 3);
    assert_eq!(local.minute(), 0);
}

#[test]
fn backfill_identifies_missing_dates() {
    let dir = tempdir().unwrap();
    let mut paths = ResearchPaths::from_env_or_default();
    paths.root = dir.path().join("data");
    let season = ResearchSeason::current();
    let now = chrono::DateTime::parse_from_rfc3339("2025-08-25T12:00:00-07:00")
        .unwrap()
        .with_timezone(&Utc);
    let missing = backfill_dates(&paths, ResearchSport::Mlb, &season, now).unwrap();
    assert!(!missing.is_empty());
}

#[test]
fn no_synthetic_l2_from_candlesticks() {
    let row = OrderbookEvent {
        exchange_timestamp_ms: Some(1),
        received_timestamp: Utc::now(),
        ticker: "T".into(),
        market_id: 1,
        game_id: 1,
        event_type: "l2_snapshot".into(),
        source: NormalizedSource::RestCandlestick,
        sequence_number: None,
        subscription_id: None,
        yes_bid_cents: Some(80),
        yes_ask_cents: Some(81),
        yes_bid_depth_hundredths: None,
        yes_ask_depth_hundredths: None,
        levels: Vec::new(),
        sequence_gap: false,
        resync_count: 0,
        first_missing_sequence: None,
        last_valid_sequence: None,
    };
    assert!(!no_synthetic_rows(&[row]).is_valid());
}

#[test]
fn discovered_markets_do_not_cross_contaminate_ids() {
    let sport = ResearchSport::Wnba;
    let discovered = vec![
        DiscoveredMarket {
            metadata: MarketMetadata {
                game_id: 100,
                market_id: 1,
                ticker: "KXWNBAGAME-A".into(),
                event_ticker: "KXWNBAGAME-E".into(),
                series_ticker: "KXWNBAGAME".into(),
                side_label: Some("A".into()),
                status: None,
                open_time: None,
                close_time: None,
                settlement_ts: None,
                result: None,
            },
            sport,
        },
        DiscoveredMarket {
            metadata: MarketMetadata {
                game_id: 100,
                market_id: 2,
                ticker: "KXWNBAGAME-B".into(),
                event_ticker: "KXWNBAGAME-E".into(),
                series_ticker: "KXWNBAGAME".into(),
                side_label: Some("B".into()),
                status: None,
                open_time: None,
                close_time: None,
                settlement_ts: None,
                result: None,
            },
            sport,
        },
    ];
    assert!(validate_discovered_pairing(&discovered).is_valid());
    assert!(
        validate_metadata(
            &discovered
                .iter()
                .map(|d| d.metadata.clone())
                .collect::<Vec<_>>()
        )
        .is_valid()
    );
}

#[test]
fn csv_export_writes_small_table() {
    let dir = tempdir().unwrap();
    let path = dir.path().join("out.csv");
    let trades = vec![PublicTrade {
        exchange_timestamp: "2025-08-01T12:00:00Z".into(),
        received_timestamp: Utc::now(),
        ticker: "T".into(),
        market_id: 1,
        game_id: 2,
        trade_id: "x".into(),
        yes_price_cents: 80,
        quantity_hundredths: 100,
        taker_outcome_side: None,
        taker_book_side: None,
        is_block_trade: false,
        source: "rest".into(),
    }];
    export_csv(&path, &trades, &[]).unwrap();
    let body = std::fs::read_to_string(path).unwrap();
    assert!(body.contains("trade,"));
}
