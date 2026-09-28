//! NHL KXNHLGAME warehouse public-API tests. No live Kalshi calls.

use momento_research_data::{
    CollectorConfig, MARKET_DATA_TYPE_CANDLE_TOB, NbaWarehouse, ResearchSport, SERIES_NHL,
    WarehouseConfig, canonicalize_season,
};

#[test]
fn nhl_is_first_class_sport() {
    assert_eq!(ResearchSport::Nhl.series_ticker(), SERIES_NHL);
    assert_eq!(ResearchSport::Nhl.dir_name(), "NHL");
    assert_eq!(ResearchSport::Nhl.warehouse_layer(), "nhl");
    assert_eq!(
        ResearchSport::from_series("KXNHLGAME"),
        Some(ResearchSport::Nhl)
    );
    assert_ne!(ResearchSport::Nhl, ResearchSport::Nba);
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
fn nhl_paths_do_not_write_under_nba() {
    let tmp = tempfile::tempdir().unwrap();
    let data = tmp.path();
    let config = WarehouseConfig::nhl_season_2025_26();
    assert_eq!(config.series, SERIES_NHL);
    let warehouse = NbaWarehouse::open(config, Some(data.to_path_buf()));
    let root = warehouse.paths.root.to_string_lossy();
    assert!(root.contains("NHL"), "{root}");
    assert!(root.contains("2025-2026"), "{root}");
    assert!(!root.contains("/NBA/"), "{root}");
    let raw = warehouse.paths.raw_dir().to_string_lossy().into_owned();
    assert!(raw.contains("kalshi/nhl"), "{raw}");
}

#[test]
fn nhl_not_added_to_mlb_collector_default_sports() {
    let cfg = CollectorConfig::default_sports();
    assert!(!cfg.sports.contains(&ResearchSport::Nhl));
    assert!(!cfg.sports.contains(&ResearchSport::Nba));
    assert!(cfg.sports.contains(&ResearchSport::Mlb));
}

#[test]
fn nhl_config_allows_hockey_phases() {
    let cfg = WarehouseConfig::nhl_season_2025_26();
    assert!(cfg.allows_phase("REGULAR_SEASON"));
    assert!(cfg.allows_phase("PRESEASON"));
    assert!(cfg.allows_phase("PLAYOFFS"));
    assert!(cfg.allows_phase("FINALS"));
    assert!(!cfg.allows_phase("PLAY_IN"));
    assert!(!cfg.allows_phase("NCAA_TOURNAMENT"));
}

#[test]
fn nhl_candles_only_skips_trades() {
    let cfg = WarehouseConfig::nhl_season_2025_26().candles_only();
    assert!(!cfg.include_trades);
    assert_eq!(cfg.series, SERIES_NHL);
}
