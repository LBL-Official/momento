//! Collect official MLB StatsAPI PBP into the W2 derived tree.
//!
//! Never writes `Backtesting Suite/Data-Real/**`.
//! Authorized 2026-08-26: public StatsAPI, Kalshi-window dates only.

use std::fs;
use std::path::{Path, PathBuf};
use std::process::Command;
use std::thread;
use std::time::Duration;

use chrono::{DateTime, NaiveDate, Utc};
use serde::{Deserialize, Serialize};
use serde_json::json;

use crate::error::EventError;
use crate::ingest::sha256_bytes;

pub const STATSAPI_BASE: &str = "https://statsapi.mlb.com";
pub const COLLECT_USER_AGENT: &str = "MomentoResearch-W2/1.0 (historical PBP; not live trading)";
pub const DEFAULT_START: &str = "2026-06-18";
pub const DEFAULT_END: &str = "2026-06-30";

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct CollectedGame {
    pub official_date: String,
    pub game_pk: String,
    pub status: String,
    pub away_abbreviation: String,
    pub home_abbreviation: String,
    pub envelope_path: String,
    pub sha256: String,
    pub skipped: bool,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct CollectReport {
    pub source: String,
    pub start: String,
    pub end: String,
    pub retrieved_at: DateTime<Utc>,
    pub games_listed: usize,
    pub games_collected: usize,
    pub games_skipped_existing: usize,
    pub games_skipped_status: usize,
    pub errors: Vec<String>,
    pub games: Vec<CollectedGame>,
}

#[derive(Clone, Debug)]
pub struct CollectConfig {
    pub out_dir: PathBuf,
    pub start: NaiveDate,
    pub end: NaiveDate,
    pub sleep_ms: u64,
}

impl CollectConfig {
    pub fn kalshi_window(out_dir: impl Into<PathBuf>) -> Self {
        Self {
            out_dir: out_dir.into(),
            start: NaiveDate::from_ymd_opt(2026, 6, 18).expect("date"),
            end: NaiveDate::from_ymd_opt(2026, 6, 30).expect("date"),
            sleep_ms: 120,
        }
    }
}

fn curl_get(url: &str) -> Result<Vec<u8>, EventError> {
    let out = Command::new("curl")
        .args([
            "-sS",
            "-L",
            "--fail",
            "--max-time",
            "90",
            "-A",
            COLLECT_USER_AGENT,
            url,
        ])
        .output()
        .map_err(|e| EventError::Io(format!("curl: {e}")))?;
    if !out.status.success() {
        return Err(EventError::Io(format!(
            "curl {} exit {:?}",
            url,
            out.status.code()
        )));
    }
    Ok(out.stdout)
}

pub fn collect_statsapi_window(cfg: &CollectConfig) -> Result<CollectReport, EventError> {
    let retrieved_at = Utc::now();
    let raw_root = cfg.out_dir.join("raw").join("statsapi");
    fs::create_dir_all(&raw_root)?;
    let start = cfg.start.format("%Y-%m-%d").to_string();
    let end = cfg.end.format("%Y-%m-%d").to_string();
    let sched_url = format!(
        "{STATSAPI_BASE}/api/v1/schedule?sportId=1&startDate={start}&endDate={end}&hydrate=team"
    );
    let sched_bytes = curl_get(&sched_url)?;
    let sched: serde_json::Value = serde_json::from_slice(&sched_bytes)?;
    let mut games = Vec::new();
    let mut errors = Vec::new();
    let mut collected = 0usize;
    let mut skipped_existing = 0usize;
    let mut skipped_status = 0usize;

    for date_block in sched
        .get("dates")
        .and_then(|v| v.as_array())
        .cloned()
        .unwrap_or_default()
    {
        let date = date_block
            .get("date")
            .and_then(|v| v.as_str())
            .unwrap_or("")
            .to_string();
        for g in date_block
            .get("games")
            .and_then(|v| v.as_array())
            .cloned()
            .unwrap_or_default()
        {
            let pk = g
                .get("gamePk")
                .and_then(|v| v.as_i64())
                .map(|n| n.to_string());
            let Some(pk) = pk else {
                errors.push("schedule game missing gamePk".into());
                continue;
            };
            let status = g
                .pointer("/status/detailedState")
                .and_then(|v| v.as_str())
                .unwrap_or("Unknown")
                .to_string();
            let away = g
                .pointer("/teams/away/team/abbreviation")
                .and_then(|v| v.as_str())
                .unwrap_or("")
                .to_string();
            let home = g
                .pointer("/teams/home/team/abbreviation")
                .and_then(|v| v.as_str())
                .unwrap_or("")
                .to_string();
            if status != "Final" {
                skipped_status += 1;
                games.push(CollectedGame {
                    official_date: date.clone(),
                    game_pk: pk,
                    status,
                    away_abbreviation: away,
                    home_abbreviation: home,
                    envelope_path: String::new(),
                    sha256: String::new(),
                    skipped: true,
                });
                continue;
            }
            let day_dir = raw_root.join(format!("date={date}"));
            fs::create_dir_all(&day_dir)?;
            let env_path = day_dir.join(format!("gamePk={pk}.envelope.json"));
            if env_path.exists() {
                skipped_existing += 1;
                let bytes = fs::read(&env_path)?;
                games.push(CollectedGame {
                    official_date: date.clone(),
                    game_pk: pk,
                    status,
                    away_abbreviation: away,
                    home_abbreviation: home,
                    envelope_path: env_path.display().to_string(),
                    sha256: sha256_bytes(&bytes),
                    skipped: true,
                });
                continue;
            }
            let feed_url = format!("{STATSAPI_BASE}/api/v1.1/game/{pk}/feed/live");
            match curl_get(&feed_url) {
                Ok(feed_bytes) => match serde_json::from_slice::<serde_json::Value>(&feed_bytes) {
                    Ok(payload) => {
                        let envelope = json!({
                            "envelope_version": "W2.RAW.1.0.0",
                            "fixture_kind": "HISTORICAL_SOURCE",
                            "source": "mlb_statsapi",
                            "source_game_id": pk,
                            "retrieved_at": retrieved_at.to_rfc3339(),
                            "payload": payload,
                        });
                        let body = serde_json::to_vec(&envelope)?;
                        fs::write(&env_path, &body)?;
                        collected += 1;
                        games.push(CollectedGame {
                            official_date: date.clone(),
                            game_pk: pk,
                            status,
                            away_abbreviation: away,
                            home_abbreviation: home,
                            envelope_path: env_path.display().to_string(),
                            sha256: sha256_bytes(&body),
                            skipped: false,
                        });
                    }
                    Err(e) => errors.push(format!("game {pk} json: {e}")),
                },
                Err(e) => errors.push(format!("game {pk}: {e}")),
            }
            if cfg.sleep_ms > 0 {
                thread::sleep(Duration::from_millis(cfg.sleep_ms));
            }
        }
    }

    let report = CollectReport {
        source: format!("{STATSAPI_BASE} schedule+feed/live"),
        start,
        end,
        retrieved_at,
        games_listed: games.len(),
        games_collected: collected,
        games_skipped_existing: skipped_existing,
        games_skipped_status: skipped_status,
        errors,
        games,
    };
    let manifest_path = cfg.out_dir.join("statsapi_collect_manifest.json");
    fs::write(
        &manifest_path,
        serde_json::to_vec_pretty(&report).map_err(|e| EventError::Io(e.to_string()))?,
    )?;
    let _ = Path::new(&manifest_path);
    Ok(report)
}
