//! NCAAB KXNCAAMBGAME warehouse public-API tests. No live Kalshi calls.

use momento_research_data::{
    CollectorConfig, MARKET_DATA_TYPE_CANDLE_TOB, NCAAB_SCHEMA_VERSION, NbaWarehouse,
    ResearchSport, SERIES_NCAAB, SeasonPhase, WarehouseConfig, canonicalize_season, dollars_to_e4,
};

#[test]
fn ncaab_is_first_class_sport() {
    assert_eq!(ResearchSport::Ncaab.series_ticker(), SERIES_NCAAB);
    assert_eq!(ResearchSport::Ncaab.dir_name(), "NCAAB");
    assert_eq!(ResearchSport::Ncaab.warehouse_layer(), "ncaab");
    assert_eq!(
        ResearchSport::from_series("KXNCAAMBGAME"),
        Some(ResearchSport::Ncaab)
    );
    assert_ne!(ResearchSport::Ncaab, ResearchSport::Nba);
}

#[test]
fn season_canonicalize() {
    assert_eq!(canonicalize_season("2025-26"), "2025-2026");
    assert_eq!(canonicalize_season("2025-2026"), "2025-2026");
}

#[test]
fn ncaab_phase_labels() {
    assert_eq!(SeasonPhase::Exhibition.as_str(), "EXHIBITION");
    assert_eq!(
        SeasonPhase::ConferenceTournament.as_str(),
        "CONFERENCE_TOURNAMENT"
    );
    assert_eq!(SeasonPhase::NcaaTournament.as_str(), "NCAA_TOURNAMENT");
    assert_eq!(SeasonPhase::OtherPostseason.as_str(), "OTHER_POSTSEASON");
    assert_eq!(
        SeasonPhase::parse("NCAA_TOURNAMENT"),
        SeasonPhase::NcaaTournament
    );
}

#[test]
fn price_e4_is_exact() {
    assert_eq!(dollars_to_e4("0.7100"), Some(7100));
    assert_eq!(dollars_to_e4("1.0000"), Some(10_000));
}

#[test]
fn historical_type_is_top_of_book_not_l2() {
    assert_eq!(MARKET_DATA_TYPE_CANDLE_TOB, "CANDLESTICK_TOP_OF_BOOK");
    assert_eq!(NCAAB_SCHEMA_VERSION, "ncaab_market_data_schema_v1");
}

#[test]
fn ncaab_paths_do_not_write_under_nba() {
    let tmp = tempfile::tempdir().unwrap();
    let data = tmp.path();
    let config = WarehouseConfig::ncaab_season_2025_26();
    assert_eq!(config.series, SERIES_NCAAB);
    assert_eq!(config.schema_version(), NCAAB_SCHEMA_VERSION);
    let warehouse = NbaWarehouse::open(config, Some(data.to_path_buf()));
    let root = warehouse.paths.root.to_string_lossy();
    assert!(root.contains("NCAAB"), "{root}");
    assert!(root.contains("2025-2026"), "{root}");
    assert!(!root.contains("/NBA/"), "{root}");
    let raw_path = warehouse.paths.raw_dir();
    let raw = raw_path.to_string_lossy();
    assert!(raw.contains("kalshi/ncaab"), "{raw}");
}

#[test]
fn ncaab_not_added_to_mlb_collector_default_sports() {
    let cfg = CollectorConfig::default_sports();
    assert!(!cfg.sports.contains(&ResearchSport::Ncaab));
    assert!(!cfg.sports.contains(&ResearchSport::Nba));
    assert!(cfg.sports.contains(&ResearchSport::Mlb));
}

#[test]
fn ncaab_config_allows_college_phases() {
    let cfg = WarehouseConfig::ncaab_season_2025_26();
    assert!(cfg.allows_phase("REGULAR_SEASON"));
    assert!(cfg.allows_phase("CONFERENCE_TOURNAMENT"));
    assert!(cfg.allows_phase("NCAA_TOURNAMENT"));
    assert!(cfg.allows_phase("EXHIBITION"));
    assert!(!cfg.allows_phase("PLAY_IN"));
    assert!(!cfg.allows_phase("FINALS"));
}
