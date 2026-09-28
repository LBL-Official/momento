//! Backtest suite filesystem layout (local research store).

use std::path::{Path, PathBuf};

use chrono::{Datelike, NaiveDate, Utc};

use momento_research_data::paths::{ENV_RESEARCH_DATA_DIR, ResearchPaths};

/// Root of the Backtesting Suite (Data + Strategies + Runs + Google Sheets sync).
#[derive(Clone, Debug)]
pub struct BacktestPaths {
    pub suite_root: PathBuf,
    pub research: ResearchPaths,
}

impl BacktestPaths {
    pub fn from_env_or_default() -> Self {
        let suite_root = std::env::var("MOMENTO_BACKTEST_SUITE_DIR")
            .map(PathBuf::from)
            .unwrap_or_else(|_| PathBuf::from("Backtesting Suite"));
        let data_root = std::env::var(ENV_RESEARCH_DATA_DIR)
            .map(PathBuf::from)
            .unwrap_or_else(|_| suite_root.join("Data"));
        Self {
            suite_root,
            research: ResearchPaths {
                root: data_root,
                season: momento_research_data::ResearchSeason::current(),
            },
        }
    }

    pub fn with_roots(suite_root: PathBuf, data_root: PathBuf) -> Self {
        Self {
            suite_root,
            research: ResearchPaths {
                root: data_root,
                season: momento_research_data::ResearchSeason::current(),
            },
        }
    }

    pub fn strategies_dir(&self) -> PathBuf {
        self.suite_root.join("Strategies")
    }

    pub fn strategy_dir(&self, strategy: &str) -> PathBuf {
        self.strategies_dir().join(strategy)
    }

    pub fn runs_root(&self) -> PathBuf {
        self.suite_root.join("Runs")
    }

    pub fn sheets_sync_dir(&self) -> PathBuf {
        self.suite_root.join("Google Sheets")
    }

    pub fn input_csv(&self) -> PathBuf {
        self.sheets_sync_dir().join("Backtesting Input.csv")
    }

    pub fn results_csv(&self) -> PathBuf {
        self.sheets_sync_dir().join("Backtesting Results.csv")
    }

    /// `Runs/FIRST01/YYYY/MM/YYYY-MM-DD_<run_id>/`
    pub fn run_dir(
        &self,
        strategy: &str,
        run_id: &str,
        created_at: chrono::DateTime<Utc>,
    ) -> PathBuf {
        let date = created_at.date_naive();
        self.runs_root()
            .join(strategy)
            .join(format!("{:04}", date.year()))
            .join(format!("{:02}", date.month()))
            .join(format!("{date}_{run_id}"))
    }

    pub fn ensure_parents(&self, path: &Path) -> std::io::Result<()> {
        if let Some(parent) = path.parent() {
            std::fs::create_dir_all(parent)?;
        }
        Ok(())
    }

    pub fn with_season_label(mut self, label: String) -> Self {
        self.research.season.label = label;
        self
    }
}

/// Convenience: partition date for path formatting.
pub fn date_parts(date: NaiveDate) -> (i32, u32, u32) {
    (date.year(), date.month(), date.day())
}
