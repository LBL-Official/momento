//! WNBA KXWNBAGAME warehouse public-API tests. No live Kalshi calls.

use momento_research_data::{
    CollectorConfig, MARKET_DATA_TYPE_CANDLE_TOB, NbaWarehouse, ResearchSport, SERIES_WNBA,
    WarehouseConfig, canonicalize_season,
};

#[test]
fn wnba_is_first_class_sport() {
    assert_eq!(ResearchSport::Wnba.series_ticker(), SERIES_WNBA);
    assert_eq!(ResearchSport::Wnba.dir_name(), "WNBA");
    assert_eq!(ResearchSport::Wnba.warehouse_layer(), "wnba");
    assert_eq!(
        ResearchSport::from_series("KXWNBAGAME"),
        Some(ResearchSport::Wnba)
    );
    assert_ne!(ResearchSport::Wnba, ResearchSport::Nba);
}

#[test]
fn season_canonicalize() {
    assert_eq!(canonicalize_season("2025-26"), "2025-2026");
}

#[test]
fn historical_type_is_top_of_book_not_l2() {
    assert_eq!(MARKET_DATA_TYPE_CANDLE_TOB, "CANDLESTICK_TOP_OF_BOOK");
}

#[test]
fn wnba_paths_do_not_write_under_nba() {
    let tmp = tempfile::tempdir().unwrap();
    let data = tmp.path();
    let config = WarehouseConfig::wnba_season_2025_26();
    assert_eq!(config.series, SERIES_WNBA);
    let warehouse = NbaWarehouse::open(config, Some(data.to_path_buf()));
    let root = warehouse.paths.root.to_string_lossy();
    assert!(root.contains("WNBA"), "{root}");
    assert!(root.contains("2025-2026"), "{root}");
    assert!(!root.contains("/NBA/"), "{root}");
    let raw = warehouse.paths.raw_dir().to_string_lossy().into_owned();
    assert!(raw.contains("kalshi/wnba"), "{raw}");
}

#[test]
fn wnba_not_added_as_nba_default_warehouse() {
    let nba = WarehouseConfig::season_2025_26();
    assert_ne!(nba.series, SERIES_WNBA);
}

#[test]
fn wnba_config_allows_summer_phases() {
    let cfg = WarehouseConfig::wnba_season_2025_26();
    assert!(cfg.allows_phase("REGULAR_SEASON"));
    assert!(cfg.allows_phase("PLAYOFFS"));
    assert!(cfg.allows_phase("FINALS"));
    assert!(cfg.allows_phase("PRESEASON"));
    assert!(!cfg.allows_phase("PLAY_IN"));
    assert!(!cfg.allows_phase("NCAA_TOURNAMENT"));
}

#[test]
fn mlb_collector_default_still_includes_wnba_date_lake() {
    let cfg = CollectorConfig::default_sports();
    assert!(cfg.sports.contains(&ResearchSport::Wnba));
    assert!(cfg.sports.contains(&ResearchSport::Mlb));
}
