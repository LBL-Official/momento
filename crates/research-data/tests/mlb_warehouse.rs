//! MLB KXMLBGAME warehouse public-API tests. No live Kalshi calls.

use momento_research_data::{
    CollectorConfig, MARKET_DATA_TYPE_CANDLE_TOB, NbaWarehouse, ResearchSport, SERIES_MLB,
    WarehouseConfig, canonicalize_season,
};

#[test]
fn mlb_is_first_class_sport() {
    assert_eq!(ResearchSport::Mlb.series_ticker(), SERIES_MLB);
    assert_eq!(ResearchSport::Mlb.dir_name(), "MLB");
    assert_eq!(ResearchSport::Mlb.warehouse_layer(), "mlb");
    assert_eq!(
        ResearchSport::from_series("KXMLBGAME"),
        Some(ResearchSport::Mlb)
    );
    assert_ne!(ResearchSport::Mlb, ResearchSport::Nba);
}

#[test]
fn season_canonicalize() {
    assert_eq!(canonicalize_season("2025-26"), "2025-2026");
    assert_eq!(canonicalize_season("2025-2026"), "2025-2026");
}

#[test]
fn historical_type_is_top_of_book_not_l2() {
    assert_eq!(MARKET_DATA_TYPE_CANDLE_TOB, "CANDLESTICK_TOP_OF_BOOK");
}

#[test]
fn mlb_paths_do_not_write_under_nba() {
    let tmp = tempfile::tempdir().unwrap();
    let data = tmp.path();
    let config = WarehouseConfig::mlb_season_2025_26();
    assert_eq!(config.series, SERIES_MLB);
    let warehouse = NbaWarehouse::open(config, Some(data.to_path_buf()));
    let root = warehouse.paths.root.to_string_lossy();
    assert!(root.contains("MLB"), "{root}");
    assert!(root.contains("2025-2026"), "{root}");
    assert!(!root.contains("/NBA/"), "{root}");
    let raw = warehouse.paths.raw_dir().to_string_lossy().into_owned();
    assert!(raw.contains("kalshi/mlb"), "{raw}");
}

#[test]
fn mlb_collector_default_still_includes_mlb() {
    let cfg = CollectorConfig::default_sports();
    assert!(cfg.sports.contains(&ResearchSport::Mlb));
}

#[test]
fn mlb_config_allows_baseball_phases() {
    let cfg = WarehouseConfig::mlb_season_2025_26();
    assert!(cfg.allows_phase("REGULAR_SEASON"));
    assert!(cfg.allows_phase("PRESEASON"));
    assert!(cfg.allows_phase("PLAYOFFS"));
    assert!(cfg.allows_phase("FINALS"));
    assert!(cfg.allows_phase("OTHER_POSTSEASON"));
    assert!(!cfg.allows_phase("PLAY_IN"));
    assert!(!cfg.allows_phase("NCAA_TOURNAMENT"));
}

#[test]
fn mlb_candles_only_skips_trades() {
    let cfg = WarehouseConfig::mlb_season_2025_26().candles_only();
    assert!(!cfg.include_trades);
    assert_eq!(cfg.series, SERIES_MLB);
}

#[test]
fn mlb_not_added_as_nba_default_warehouse() {
    let nba = WarehouseConfig::season_2025_26();
    assert_ne!(nba.series, SERIES_MLB);
}
