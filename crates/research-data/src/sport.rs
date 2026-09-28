//! Sport and series identifiers for research collection.

use serde::{Deserialize, Serialize};

pub const SERIES_MLB: &str = "KXMLBGAME";
pub const SERIES_WNBA: &str = "KXWNBAGAME";
pub const SERIES_NBA: &str = "KXNBAGAME";
pub const SERIES_NCAAB: &str = "KXNCAAMBGAME";
pub const SERIES_NHL: &str = "KXNHLGAME";
pub const SERIES_ATP: &str = "KXATPMATCH";
pub const SERIES_WTA: &str = "KXWTAMATCH";

pub const DEFAULT_SEASON: &str = "2025-2026";

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "UPPERCASE")]
pub enum ResearchSport {
    Mlb,
    Wnba,
    Nba,
    Ncaab,
    Nhl,
    /// ATP professional men's singles (`KXATPMATCH`).
    TennisAtp,
    /// WTA professional women's singles (`KXWTAMATCH`).
    TennisWta,
}

impl ResearchSport {
    pub fn series_ticker(self) -> &'static str {
        match self {
            Self::Mlb => SERIES_MLB,
            Self::Wnba => SERIES_WNBA,
            Self::Nba => SERIES_NBA,
            Self::Ncaab => SERIES_NCAAB,
            Self::Nhl => SERIES_NHL,
            Self::TennisAtp => SERIES_ATP,
            Self::TennisWta => SERIES_WTA,
        }
    }

    /// Top-level data directory. ATP and WTA deliberately share `TENNIS`;
    /// they are separated below by `warehouse_layer`.
    pub fn dir_name(self) -> &'static str {
        match self {
            Self::Mlb => "MLB",
            Self::Wnba => "WNBA",
            Self::Nba => "NBA",
            Self::Ncaab => "NCAAB",
            Self::Nhl => "NHL",
            Self::TennisAtp | Self::TennisWta => "TENNIS",
        }
    }

    /// Lowercase warehouse layer (`nba`, `ncaab`). Distinct from `dir_name`.
    pub fn warehouse_layer(self) -> &'static str {
        match self {
            Self::Mlb => "mlb",
            Self::Wnba => "wnba",
            Self::Nba => "nba",
            Self::Ncaab => "ncaab",
            Self::Nhl => "nhl",
            Self::TennisAtp => "atp",
            Self::TennisWta => "wta",
        }
    }

    pub fn league(self) -> &'static str {
        match self {
            Self::Mlb => "MLB",
            Self::Wnba => "WNBA",
            Self::Nba => "NBA",
            Self::Ncaab => "NCAAB",
            Self::Nhl => "NHL",
            Self::TennisAtp => "ATP",
            Self::TennisWta => "WTA",
        }
    }

    /// Tennis has no home/away and no preseason/playoffs; callers branch on this.
    pub fn is_tennis(self) -> bool {
        matches!(self, Self::TennisAtp | Self::TennisWta)
    }

    pub fn from_series(series: &str) -> Option<Self> {
        match series {
            SERIES_MLB => Some(Self::Mlb),
            SERIES_WNBA => Some(Self::Wnba),
            SERIES_NBA => Some(Self::Nba),
            SERIES_NCAAB => Some(Self::Ncaab),
            SERIES_NHL => Some(Self::Nhl),
            SERIES_ATP => Some(Self::TennisAtp),
            SERIES_WTA => Some(Self::TennisWta),
            _ => None,
        }
    }
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct ResearchSeason {
    pub label: String,
}

impl ResearchSeason {
    pub fn current() -> Self {
        Self {
            label: DEFAULT_SEASON.to_string(),
        }
    }
}
