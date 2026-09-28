//! Filesystem layout for research datasets.

use std::path::{Path, PathBuf};

use chrono::NaiveDate;

use crate::sport::{ResearchSeason, ResearchSport};

pub const ENV_RESEARCH_DATA_DIR: &str = "MOMENTO_RESEARCH_DATA_DIR";

#[derive(Clone, Debug)]
pub struct ResearchPaths {
    pub root: PathBuf,
    pub season: ResearchSeason,
}

impl ResearchPaths {
    pub fn from_env_or_default() -> Self {
        let root = std::env::var(ENV_RESEARCH_DATA_DIR)
            .map(PathBuf::from)
            .unwrap_or_else(|_| PathBuf::from("Backtesting Suite/Data"));
        Self {
            root,
            season: ResearchSeason::current(),
        }
    }

    pub fn sport_root(&self, sport: ResearchSport) -> PathBuf {
        self.root.join(sport.dir_name()).join(&self.season.label)
    }

    pub fn raw_day(&self, sport: ResearchSport, date: NaiveDate) -> PathBuf {
        self.sport_root(sport)
            .join("raw")
            .join(format!("date={date}"))
    }

    pub fn raw_staging_day(&self, sport: ResearchSport, date: NaiveDate) -> PathBuf {
        self.sport_root(sport)
            .join("raw")
            .join(format!(".staging/date={date}"))
    }

    pub fn orderbook_day(&self, sport: ResearchSport, date: NaiveDate) -> PathBuf {
        self.sport_root(sport)
            .join("orderbook")
            .join(format!("date={date}"))
    }

    pub fn orderbook_staging_day(&self, sport: ResearchSport, date: NaiveDate) -> PathBuf {
        self.sport_root(sport)
            .join("orderbook")
            .join(format!(".staging/date={date}"))
    }

    pub fn trades_day(&self, sport: ResearchSport, date: NaiveDate) -> PathBuf {
        self.sport_root(sport)
            .join("trades")
            .join(format!("date={date}"))
    }

    pub fn trades_staging_day(&self, sport: ResearchSport, date: NaiveDate) -> PathBuf {
        self.sport_root(sport)
            .join("trades")
            .join(format!(".staging/date={date}"))
    }

    pub fn metadata_dir(&self, sport: ResearchSport) -> PathBuf {
        self.sport_root(sport).join("metadata")
    }

    pub fn manifests_dir(&self, sport: ResearchSport) -> PathBuf {
        self.sport_root(sport).join("manifests")
    }

    pub fn validation_dir(&self, sport: ResearchSport) -> PathBuf {
        self.sport_root(sport).join("validation")
    }

    pub fn manifest_path(&self, sport: ResearchSport, date: NaiveDate) -> PathBuf {
        self.manifests_dir(sport).join(format!("date={date}.json"))
    }

    pub fn catalog_path(&self) -> PathBuf {
        self.root.join("catalog.json")
    }

    pub fn exports_dir(&self) -> PathBuf {
        self.root.join("exports")
    }

    pub fn ensure_parents(&self, path: &Path) -> std::io::Result<()> {
        if let Some(parent) = path.parent() {
            std::fs::create_dir_all(parent)?;
        }
        Ok(())
    }
}
