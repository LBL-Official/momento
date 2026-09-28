//! Warehouse configuration. Seasons are labels, not hardcoded game counts.

use serde::{Deserialize, Serialize};

use crate::sport::{
    ResearchSeason, ResearchSport, SERIES_ATP, SERIES_MLB, SERIES_NBA, SERIES_NCAAB, SERIES_NHL,
    SERIES_WNBA, SERIES_WTA,
};

use super::types::{NCAAB_SCHEMA_VERSION, SCHEMA_VERSION, TENNIS_SCHEMA_VERSION};

pub const DEFAULT_SERIES: &str = SERIES_NBA;
pub const DEFAULT_MAX_WORKERS: usize = 4;
pub const DEFAULT_REQUESTS_PER_SECOND: f64 = 4.0;
pub const DEFAULT_RETRY_ATTEMPTS: u32 = 5;

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct WarehouseConfig {
    pub sport: String,
    pub series: String,
    pub season: String,
    pub include_exhibition: bool,
    pub include_preseason: bool,
    pub include_regular_season: bool,
    pub include_play_in: bool,
    pub include_playoffs: bool,
    pub include_finals: bool,
    pub include_conference_tournament: bool,
    pub include_ncaa_tournament: bool,
    pub include_other_postseason: bool,
    /// Tennis-only phase. Defaults to true so configs written before tennis
    /// existed still deserialize.
    #[serde(default = "default_include_grand_slam")]
    pub include_grand_slam: bool,
    pub max_workers: usize,
    pub requests_per_second: f64,
    pub retry_attempts: u32,
    pub candle_period_minutes: u32,
    pub event_filter: Option<String>,
    pub ticker_filter: Option<String>,
    /// When false, ticker ingest skips public trades (candles only).
    pub include_trades: bool,
}

impl WarehouseConfig {
    pub fn season_2025_26() -> Self {
        Self {
            sport: "nba".into(),
            series: DEFAULT_SERIES.into(),
            season: ResearchSeason::current().label,
            include_exhibition: true,
            include_preseason: true,
            include_regular_season: true,
            include_play_in: true,
            include_playoffs: true,
            include_finals: true,
            include_conference_tournament: true,
            include_ncaa_tournament: true,
            include_other_postseason: true,
            include_grand_slam: false,
            max_workers: DEFAULT_MAX_WORKERS,
            requests_per_second: DEFAULT_REQUESTS_PER_SECOND,
            retry_attempts: DEFAULT_RETRY_ATTEMPTS,
            candle_period_minutes: 1,
            event_filter: None,
            ticker_filter: None,
            include_trades: true,
        }
    }

    pub fn ncaab_season_2025_26() -> Self {
        Self {
            sport: "ncaab".into(),
            series: SERIES_NCAAB.into(),
            season: ResearchSeason::current().label,
            include_exhibition: true,
            include_preseason: true,
            include_regular_season: true,
            include_play_in: false,
            include_playoffs: false,
            include_finals: false,
            include_conference_tournament: true,
            include_ncaa_tournament: true,
            include_other_postseason: true,
            include_grand_slam: false,
            max_workers: DEFAULT_MAX_WORKERS,
            requests_per_second: DEFAULT_REQUESTS_PER_SECOND,
            retry_attempts: DEFAULT_RETRY_ATTEMPTS,
            candle_period_minutes: 1,
            event_filter: None,
            ticker_filter: None,
            include_trades: true,
        }
    }

    pub fn mlb_season_2025_26() -> Self {
        Self {
            sport: "mlb".into(),
            series: SERIES_MLB.into(),
            season: ResearchSeason::current().label,
            include_exhibition: true,
            include_preseason: true,
            include_regular_season: true,
            include_play_in: false,
            include_playoffs: true,
            include_finals: true,
            include_conference_tournament: false,
            include_ncaa_tournament: false,
            include_other_postseason: true,
            include_grand_slam: false,
            max_workers: DEFAULT_MAX_WORKERS,
            requests_per_second: DEFAULT_REQUESTS_PER_SECOND,
            retry_attempts: 20,
            candle_period_minutes: 1,
            event_filter: None,
            ticker_filter: None,
            include_trades: true,
        }
    }

    pub fn wnba_season_2025_26() -> Self {
        Self {
            sport: "wnba".into(),
            series: SERIES_WNBA.into(),
            season: ResearchSeason::current().label,
            include_exhibition: true,
            include_preseason: true,
            include_regular_season: true,
            include_play_in: false,
            include_playoffs: true,
            include_finals: true,
            include_conference_tournament: false,
            include_ncaa_tournament: false,
            include_other_postseason: true,
            include_grand_slam: false,
            max_workers: DEFAULT_MAX_WORKERS,
            requests_per_second: DEFAULT_REQUESTS_PER_SECOND,
            retry_attempts: DEFAULT_RETRY_ATTEMPTS,
            candle_period_minutes: 1,
            event_filter: None,
            ticker_filter: None,
            include_trades: true,
        }
    }

    pub fn nhl_season_2025_26() -> Self {
        Self {
            sport: "nhl".into(),
            series: SERIES_NHL.into(),
            season: ResearchSeason::current().label,
            include_exhibition: true,
            include_preseason: true,
            include_regular_season: true,
            include_play_in: false,
            include_playoffs: true,
            include_finals: true,
            include_conference_tournament: false,
            include_ncaa_tournament: false,
            include_other_postseason: true,
            include_grand_slam: false,
            max_workers: DEFAULT_MAX_WORKERS,
            requests_per_second: DEFAULT_REQUESTS_PER_SECOND,
            retry_attempts: DEFAULT_RETRY_ATTEMPTS,
            candle_period_minutes: 1,
            event_filter: None,
            ticker_filter: None,
            include_trades: true,
        }
    }

    /// ATP professional singles (`KXATPMATCH`). Research only.
    ///
    /// Tennis has no exhibition, preseason, play-in, playoff, conference, or
    /// NCAA phase, so those gates are off. `retry_attempts` matches MLB because
    /// a tennis tour season has a comparable number of markets.
    pub fn tennis_atp_season_2025_26() -> Self {
        Self::tennis_season_2025_26("tennis_atp", SERIES_ATP)
    }

    /// WTA professional singles (`KXWTAMATCH`). Research only.
    pub fn tennis_wta_season_2025_26() -> Self {
        Self::tennis_season_2025_26("tennis_wta", SERIES_WTA)
    }

    fn tennis_season_2025_26(sport: &str, series: &str) -> Self {
        Self {
            sport: sport.into(),
            series: series.into(),
            season: ResearchSeason::current().label,
            include_exhibition: false,
            include_preseason: false,
            include_regular_season: true,
            include_play_in: false,
            include_playoffs: false,
            include_finals: false,
            include_conference_tournament: false,
            include_ncaa_tournament: false,
            include_other_postseason: false,
            include_grand_slam: true,
            max_workers: DEFAULT_MAX_WORKERS,
            requests_per_second: DEFAULT_REQUESTS_PER_SECOND,
            retry_attempts: 20,
            candle_period_minutes: 1,
            event_filter: None,
            ticker_filter: None,
            include_trades: true,
        }
    }

    pub fn with_season(mut self, season: impl Into<String>) -> Self {
        self.season = canonicalize_season(&season.into());
        self
    }

    pub fn candles_only(mut self) -> Self {
        self.include_trades = false;
        self
    }

    pub fn research_sport(&self) -> ResearchSport {
        match self.sport.to_ascii_lowercase().as_str() {
            "ncaab" => ResearchSport::Ncaab,
            "mlb" => ResearchSport::Mlb,
            "wnba" => ResearchSport::Wnba,
            "nhl" => ResearchSport::Nhl,
            "tennis_atp" => ResearchSport::TennisAtp,
            "tennis_wta" => ResearchSport::TennisWta,
            _ => ResearchSport::Nba,
        }
    }

    pub fn schema_version(&self) -> &'static str {
        match self.research_sport() {
            ResearchSport::Ncaab => NCAAB_SCHEMA_VERSION,
            ResearchSport::TennisAtp | ResearchSport::TennisWta => TENNIS_SCHEMA_VERSION,
            _ => SCHEMA_VERSION,
        }
    }

    pub fn league(&self) -> &'static str {
        self.research_sport().league()
    }

    pub fn allows_phase(&self, phase: &str) -> bool {
        match phase {
            "EXHIBITION" => self.include_exhibition,
            "PRESEASON" => self.include_preseason,
            "REGULAR_SEASON" => self.include_regular_season,
            "PLAY_IN" => self.include_play_in,
            "PLAYOFFS" => self.include_playoffs,
            "FINALS" => self.include_finals,
            "CONFERENCE_TOURNAMENT" => self.include_conference_tournament,
            "NCAA_TOURNAMENT" => self.include_ncaa_tournament,
            "OTHER_POSTSEASON" => self.include_other_postseason,
            "GRAND_SLAM" => self.include_grand_slam,
            "UNKNOWN" => true,
            _ => true,
        }
    }
}

fn default_include_grand_slam() -> bool {
    true
}

/// Accept `2025-26` and `2025-2026`.
pub fn canonicalize_season(raw: &str) -> String {
    let t = raw.trim();
    if t.len() == 7 && t.as_bytes().get(4) == Some(&b'-') {
        if let (Ok(a), Ok(b)) = (t[..4].parse::<i32>(), t[5..].parse::<i32>()) {
            if b < 100 {
                return format!("{a}-{}", a / 100 * 100 + b);
            }
        }
    }
    t.to_string()
}
