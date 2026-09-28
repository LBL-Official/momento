//! Event-centric warehouse layout under the existing research data root.
//!
//! Candles are never stored as `orderbook.parquet`.

use std::fs;
use std::path::{Path, PathBuf};

use crate::paths::ResearchPaths;
use crate::sport::{ResearchSeason, ResearchSport};

#[derive(Clone, Debug)]
pub struct WarehousePaths {
    pub root: PathBuf,
    pub sport: ResearchSport,
}

impl WarehousePaths {
    pub fn new(research: &ResearchPaths, season: &ResearchSeason, sport: ResearchSport) -> Self {
        let mut paths = research.clone();
        paths.season = season.clone();
        Self {
            root: paths.sport_root(sport).join("warehouse"),
            sport,
        }
    }

    pub fn from_data_dir(data_dir: &Path, season: &str, sport: ResearchSport) -> Self {
        Self {
            root: data_dir
                .join(sport.dir_name())
                .join(season)
                .join("warehouse"),
            sport,
        }
    }

    fn layer(&self) -> &'static str {
        self.sport.warehouse_layer()
    }

    pub fn raw_dir(&self) -> PathBuf {
        self.root.join("raw").join("kalshi").join(self.layer())
    }
    pub fn raw_events(&self) -> PathBuf {
        self.raw_dir().join("events")
    }
    pub fn raw_markets(&self) -> PathBuf {
        self.raw_dir().join("markets")
    }
    pub fn raw_candles(&self, ticker: &str) -> PathBuf {
        self.raw_dir()
            .join("candlesticks")
            .join(format!("ticker={ticker}"))
    }
    pub fn raw_trades(&self, ticker: &str) -> PathBuf {
        self.raw_dir()
            .join("trades")
            .join(format!("ticker={ticker}"))
    }
    pub fn cutoff_path(&self) -> PathBuf {
        self.raw_dir().join("cutoff.json")
    }

    pub fn normalized_dir(&self) -> PathBuf {
        self.root.join("normalized").join(self.layer())
    }
    pub fn events_parquet(&self) -> PathBuf {
        self.normalized_dir().join("events").join("events.parquet")
    }
    pub fn markets_parquet(&self) -> PathBuf {
        self.normalized_dir()
            .join("markets")
            .join("markets.parquet")
    }
    pub fn games_parquet(&self) -> PathBuf {
        self.normalized_dir()
            .join("games")
            .join(format!("{}_games.parquet", self.layer()))
    }
    pub fn games_json(&self) -> PathBuf {
        self.normalized_dir()
            .join("games")
            .join(format!("{}_games.json", self.layer()))
    }
    /// Tennis-only sidecar carrying `product_metadata.competition` and
    /// `custom_strike.tennis_competitor`, which have no column in the shared
    /// warehouse parquet schema.
    pub fn tennis_crosswalk_json(&self) -> PathBuf {
        self.normalized_dir()
            .join("crosswalk")
            .join(format!("{}_tennis_crosswalk.json", self.layer()))
    }
    pub fn candles_month(&self, month: &str) -> PathBuf {
        self.normalized_dir()
            .join("candles_1m")
            .join(format!("month={month}"))
    }
    pub fn trades_month(&self, month: &str) -> PathBuf {
        self.normalized_dir()
            .join("trades")
            .join(format!("month={month}"))
    }

    pub fn derived_dir(&self) -> PathBuf {
        self.root.join("derived").join(self.layer())
    }
    pub fn causal_features_month(&self, month: &str) -> PathBuf {
        self.derived_dir()
            .join("causal_features")
            .join(format!("month={month}"))
    }
    pub fn complementarity_month(&self, month: &str) -> PathBuf {
        self.derived_dir()
            .join("complementarity")
            .join(format!("month={month}"))
    }
    pub fn trade_agg_month(&self, month: &str) -> PathBuf {
        self.derived_dir()
            .join("trade_minute")
            .join(format!("month={month}"))
    }
    pub fn coverage_path(&self) -> PathBuf {
        self.derived_dir().join("coverage").join("coverage.json")
    }

    pub fn manifests_dir(&self) -> PathBuf {
        self.root.join("manifests").join(self.layer())
    }
    pub fn ingestion_manifest(&self) -> PathBuf {
        self.manifests_dir()
            .join(format!("{}_ingestion_manifest.json", self.layer()))
    }
    pub fn dataset_manifest(&self) -> PathBuf {
        self.manifests_dir().join("dataset_manifest.json")
    }
    pub fn validation_json(&self) -> PathBuf {
        self.manifests_dir().join("validation.json")
    }
    pub fn validation_txt(&self) -> PathBuf {
        self.manifests_dir().join("validation.txt")
    }

    pub fn ensure(&self, path: &Path) -> std::io::Result<()> {
        if let Some(parent) = path.parent() {
            fs::create_dir_all(parent)?;
        }
        Ok(())
    }

    pub fn write_atomic(&self, path: &Path, bytes: &[u8]) -> std::io::Result<()> {
        self.ensure(path)?;
        let tmp = path.with_extension("tmp");
        fs::write(&tmp, bytes)?;
        fs::rename(tmp, path)?;
        Ok(())
    }
}
