//! NBA KXNBAGAME warehouse public-API tests. No live Kalshi calls.

use chrono::{TimeZone, Utc};
use momento_research_data::{
    MARKET_DATA_TYPE_CANDLE_TOB, ResearchSport, SERIES_NBA, SeasonPhase, canonicalize_season,
    dollars_to_e4,
};

#[test]
fn nba_is_first_class_sport() {
    assert_eq!(ResearchSport::Nba.series_ticker(), SERIES_NBA);
    assert_eq!(ResearchSport::Nba.dir_name(), "NBA");
    assert_eq!(
        ResearchSport::from_series("KXNBAGAME"),
        Some(ResearchSport::Nba)
    );
    assert_ne!(ResearchSport::Nba, ResearchSport::Mlb);
}

#[test]
fn price_e4_is_exact() {
    assert_eq!(dollars_to_e4("0.7100"), Some(7100));
    assert_eq!(dollars_to_e4("1.0000"), Some(10_000));
    assert_eq!(dollars_to_e4("0.7246"), Some(7246));
    assert_eq!(dollars_to_e4(""), None);
}

#[test]
fn season_canonicalize() {
    assert_eq!(canonicalize_season("2025-26"), "2025-2026");
    assert_eq!(canonicalize_season("2025-2026"), "2025-2026");
}

#[test]
fn phase_enum_labels() {
    assert_eq!(SeasonPhase::PlayIn.as_str(), "PLAY_IN");
    assert_eq!(SeasonPhase::parse("FINALS"), SeasonPhase::Finals);
}

#[test]
fn historical_type_is_top_of_book_not_l2() {
    assert_eq!(MARKET_DATA_TYPE_CANDLE_TOB, "CANDLESTICK_TOP_OF_BOOK");
}

#[test]
fn timestamps_are_utc() {
    let ts = Utc.timestamp_opt(1_700_000_000, 0).unwrap();
    assert_eq!(ts.timezone(), Utc);
}
