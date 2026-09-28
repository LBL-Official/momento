//! Tennis KXATPMATCH / KXWTAMATCH warehouse public-API tests. No live Kalshi calls.

use momento_research_data::{
    MARKET_DATA_TYPE_CANDLE_TOB, NbaWarehouse, ResearchSport, SERIES_ATP, SERIES_WTA, SeasonPhase,
    TENNIS_SCHEMA_VERSION, WarehouseConfig, classify_tennis_phase, market_tennis_competitor,
    season_for_date_tennis, tennis_competition, tennis_player_sides,
};

#[test]
fn atp_and_wta_are_first_class_sports() {
    assert_eq!(ResearchSport::TennisAtp.series_ticker(), SERIES_ATP);
    assert_eq!(ResearchSport::TennisWta.series_ticker(), SERIES_WTA);
    assert_eq!(
        ResearchSport::from_series("KXATPMATCH"),
        Some(ResearchSport::TennisAtp)
    );
    assert_eq!(
        ResearchSport::from_series("KXWTAMATCH"),
        Some(ResearchSport::TennisWta)
    );
    assert_eq!(ResearchSport::TennisAtp.league(), "ATP");
    assert_eq!(ResearchSport::TennisWta.league(), "WTA");
    assert!(ResearchSport::TennisAtp.is_tennis());
    assert!(!ResearchSport::Mlb.is_tennis());
}

#[test]
fn tours_share_one_data_dir_but_not_one_warehouse_layer() {
    assert_eq!(ResearchSport::TennisAtp.dir_name(), "TENNIS");
    assert_eq!(ResearchSport::TennisWta.dir_name(), "TENNIS");
    assert_eq!(ResearchSport::TennisAtp.warehouse_layer(), "atp");
    assert_eq!(ResearchSport::TennisWta.warehouse_layer(), "wta");
}

#[test]
fn tennis_paths_do_not_collide_with_other_sports() {
    let tmp = tempfile::tempdir().unwrap();
    let data = tmp.path();
    for (config, layer) in [
        (WarehouseConfig::tennis_atp_season_2025_26(), "kalshi/atp"),
        (WarehouseConfig::tennis_wta_season_2025_26(), "kalshi/wta"),
    ] {
        let warehouse = NbaWarehouse::open(config, Some(data.to_path_buf()));
        let root = warehouse.paths.root.to_string_lossy().into_owned();
        assert!(root.contains("TENNIS"), "{root}");
        assert!(root.contains("2025-2026"), "{root}");
        assert!(!root.contains("/NBA/"), "{root}");
        assert!(!root.contains("/MLB/"), "{root}");
        let raw = warehouse.paths.raw_dir().to_string_lossy().into_owned();
        assert!(raw.contains(layer), "{raw}");
    }
}

#[test]
fn atp_and_wta_layers_stay_separate_under_the_shared_dir() {
    let tmp = tempfile::tempdir().unwrap();
    let atp = NbaWarehouse::open(
        WarehouseConfig::tennis_atp_season_2025_26(),
        Some(tmp.path().to_path_buf()),
    );
    let wta = NbaWarehouse::open(
        WarehouseConfig::tennis_wta_season_2025_26(),
        Some(tmp.path().to_path_buf()),
    );
    assert_eq!(atp.paths.root, wta.paths.root);
    assert_ne!(atp.paths.raw_dir(), wta.paths.raw_dir());
    assert_ne!(atp.paths.normalized_dir(), wta.paths.normalized_dir());
    assert_ne!(
        atp.paths.ingestion_manifest(),
        wta.paths.ingestion_manifest()
    );
}

#[test]
fn tennis_config_has_no_basketball_or_baseball_phases() {
    for cfg in [
        WarehouseConfig::tennis_atp_season_2025_26(),
        WarehouseConfig::tennis_wta_season_2025_26(),
    ] {
        assert!(cfg.allows_phase("REGULAR_SEASON"));
        assert!(cfg.allows_phase("GRAND_SLAM"));
        assert!(cfg.allows_phase("UNKNOWN"));
        assert!(!cfg.allows_phase("PRESEASON"));
        assert!(!cfg.allows_phase("EXHIBITION"));
        assert!(!cfg.allows_phase("PLAY_IN"));
        assert!(!cfg.allows_phase("PLAYOFFS"));
        assert!(!cfg.allows_phase("FINALS"));
        assert!(!cfg.allows_phase("CONFERENCE_TOURNAMENT"));
        assert!(!cfg.allows_phase("NCAA_TOURNAMENT"));
        assert!(!cfg.allows_phase("OTHER_POSTSEASON"));
        assert_eq!(cfg.candle_period_minutes, 1);
        assert!(cfg.include_trades);
        assert_eq!(cfg.retry_attempts, 20);
        assert_eq!(cfg.schema_version(), TENNIS_SCHEMA_VERSION);
    }
}

#[test]
fn tennis_config_maps_back_to_its_sport() {
    let atp = WarehouseConfig::tennis_atp_season_2025_26();
    assert_eq!(atp.series, SERIES_ATP);
    assert_eq!(atp.research_sport(), ResearchSport::TennisAtp);
    assert_eq!(atp.league(), "ATP");
    let wta = WarehouseConfig::tennis_wta_season_2025_26();
    assert_eq!(wta.series, SERIES_WTA);
    assert_eq!(wta.research_sport(), ResearchSport::TennisWta);
    assert_eq!(wta.league(), "WTA");
    assert!(!wta.candles_only().include_trades);
}

#[test]
fn tennis_does_not_change_existing_sport_configs() {
    for cfg in [
        WarehouseConfig::season_2025_26(),
        WarehouseConfig::ncaab_season_2025_26(),
        WarehouseConfig::mlb_season_2025_26(),
        WarehouseConfig::wnba_season_2025_26(),
        WarehouseConfig::nhl_season_2025_26(),
    ] {
        assert_ne!(cfg.series, SERIES_ATP);
        assert_ne!(cfg.series, SERIES_WTA);
        assert!(!cfg.research_sport().is_tennis());
        assert!(!cfg.allows_phase("GRAND_SLAM"));
    }
}

#[test]
fn grand_slam_phase_round_trips() {
    assert_eq!(SeasonPhase::GrandSlam.as_str(), "GRAND_SLAM");
    assert_eq!(SeasonPhase::parse("GRAND_SLAM"), SeasonPhase::GrandSlam);
}

#[test]
fn calendar_season_folds_both_tennis_years_into_one_folder() {
    use chrono::NaiveDate;
    assert_eq!(
        season_for_date_tennis(NaiveDate::from_ymd_opt(2025, 1, 12).unwrap()),
        "2025-2026"
    );
    assert_eq!(
        season_for_date_tennis(NaiveDate::from_ymd_opt(2026, 11, 20).unwrap()),
        "2025-2026"
    );
}

#[test]
fn competition_drives_phase_and_crosswalk_fields_are_readable() {
    let event = serde_json::json!({
        "event_ticker": "KXATPMATCH-26SEP11ZVEKHA",
        "series_ticker": "KXATPMATCH",
        "title": "Zverev vs Khachanov",
        "sub_title": "Zverev vs Khachanov (Sep 11)",
        "mutually_exclusive": true,
        "product_metadata": {"competition": "US Open Men Singles", "competition_scope": "Game"}
    });
    let competition = tennis_competition(&event);
    assert_eq!(competition.as_deref(), Some("US Open Men Singles"));
    assert_eq!(
        classify_tennis_phase(competition.as_deref()).phase,
        SeasonPhase::GrandSlam
    );
    let market = serde_json::json!({
        "ticker": "KXATPMATCH-26SEP09ZVEVAN-ZVE",
        "event_ticker": "KXATPMATCH-26SEP09ZVEVAN",
        "yes_sub_title": "Alexander Zverev",
        "custom_strike": {"tennis_competitor": "dc4002ad-fb32-4f36-b59f-7c7af1927c57"}
    });
    assert_eq!(
        market_tennis_competitor(&market).as_deref(),
        Some("dc4002ad-fb32-4f36-b59f-7c7af1927c57")
    );
}

#[test]
fn player_sides_never_come_from_halving_the_event_ticker() {
    let sides = tennis_player_sides(
        "KXATPMATCH-26AUG24KWONLAJ",
        &[
            "KXATPMATCH-26AUG24KWONLAJ-KWON".into(),
            "KXATPMATCH-26AUG24KWONLAJ-LAJ".into(),
        ],
    )
    .unwrap();
    assert_eq!(sides.side_a_code, "KWON");
    assert_eq!(sides.side_b_code, "LAJ");
    assert!(tennis_player_sides("KXATPMATCH-26AUG24KWONLAJ", &[]).is_none());
}

#[test]
fn historical_type_is_top_of_book_not_l2() {
    assert_eq!(MARKET_DATA_TYPE_CANDLE_TOB, "CANDLESTICK_TOP_OF_BOOK");
}
