//! Landing and run directories. Never under Data-Real.

use std::fs;
use std::path::{Path, PathBuf};

use chrono::NaiveDate;
use serde::Serialize;

use crate::error::IngestError;
use crate::types::SOURCE_STATSAPI;

#[derive(Clone, Debug)]
pub struct IngestPaths {
    pub root: PathBuf,
}

impl IngestPaths {
    pub fn new(root: impl Into<PathBuf>) -> Self {
        Self { root: root.into() }
    }

    pub fn lock_path(&self) -> PathBuf {
        self.root.join("locks").join("ingest.lock")
    }

    pub fn landing_game(&self, date: NaiveDate, game_pk: &str) -> PathBuf {
        self.root
            .join("landing")
            .join(SOURCE_STATSAPI)
            .join(format!("date={date}"))
            .join(format!("gamePk={game_pk}.envelope.json"))
    }

    pub fn ticker_file_stem(ticker: &str) -> String {
        ticker
            .chars()
            .map(|c| {
                if c.is_ascii_alphanumeric() || c == '-' {
                    c
                } else {
                    '_'
                }
            })
            .collect()
    }

    pub fn landing_kalshi_discovery(&self, date: NaiveDate, ticker: &str) -> PathBuf {
        let safe = Self::ticker_file_stem(ticker);
        self.root
            .join("landing")
            .join(crate::types::SOURCE_KALSHI_DISCOVERY)
            .join(format!("date={date}"))
            .join(format!("ticker={safe}.envelope.json"))
    }

    pub fn landing_kalshi_matched_trades(&self, date: NaiveDate, ticker: &str) -> PathBuf {
        let safe = Self::ticker_file_stem(ticker);
        self.root
            .join("landing")
            .join(crate::types::SOURCE_KALSHI_MATCHED_TRADES)
            .join(format!("date={date}"))
            .join(format!("ticker={safe}.trades.json"))
    }

    pub fn landing_kalshi_candles(&self, date: NaiveDate, ticker: &str) -> PathBuf {
        let safe = Self::ticker_file_stem(ticker);
        self.root
            .join("landing")
            .join(crate::types::SOURCE_KALSHI_HISTORICAL_CANDLES)
            .join(format!("date={date}"))
            .join(format!("ticker={safe}.candles.json"))
    }

    pub fn landing_kalshi_settlement(&self, date: NaiveDate, ticker: &str) -> PathBuf {
        let safe = Self::ticker_file_stem(ticker);
        self.root
            .join("landing")
            .join(crate::types::SOURCE_KALSHI_SETTLEMENT)
            .join(format!("date={date}"))
            .join(format!("ticker={safe}.json"))
    }

    pub fn watermark_path(&self) -> PathBuf {
        self.root.join("state").join("watermarks.json")
    }

    pub fn run_dir(&self, run_id: &str) -> PathBuf {
        self.root.join("runs").join(run_id)
    }

    pub fn ensure_run(&self, run_id: &str) -> Result<PathBuf, IngestError> {
        let dir = self.run_dir(run_id);
        fs::create_dir_all(&dir)?;
        fs::create_dir_all(self.root.join("locks"))?;
        Ok(dir)
    }
}

pub fn write_json_atomic(
    path: &Path,
    value: &(impl Serialize + ?Sized),
) -> Result<(), IngestError> {
    if let Some(parent) = path.parent() {
        fs::create_dir_all(parent)?;
    }
    let tmp = path.with_extension("json.tmp");
    fs::write(&tmp, serde_json::to_vec_pretty(value)?)?;
    fs::rename(tmp, path)?;
    Ok(())
}

pub fn sha256_bytes(bytes: &[u8]) -> String {
    use sha2::{Digest, Sha256};
    format!("{:x}", Sha256::digest(bytes))
}

pub fn sha256_file(path: &Path) -> Result<String, IngestError> {
    let bytes = fs::read(path)?;
    Ok(sha256_bytes(&bytes))
}
