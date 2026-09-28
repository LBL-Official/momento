//! Historical coverage reporting. Never claims seasons that are not on disk.

use std::collections::BTreeSet;
use std::fs::File;
use std::path::{Path, PathBuf};

use arrow::array::{Array, StringArray};
use chrono::{Datelike, NaiveDate};
use parquet::arrow::arrow_reader::ParquetRecordBatchReaderBuilder;
use serde::{Deserialize, Serialize};

use crate::identity::kalshi_event_date_token;
use crate::versions::COVERAGE_VERSION;
use momento_research_data::manifest::DailyManifest;

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum CoverageStatus {
    Available,
    Missing,
    Partial,
    Invalid,
    Unverified,
    MissingHistoricalSource,
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct GameCoverageRow {
    pub season: String,
    pub date: String,
    pub game_id: String,
    pub home_team: String,
    pub away_team: String,
    pub pbp_available: CoverageStatus,
    pub pitch_level_available: CoverageStatus,
    pub timestamps_available: CoverageStatus,
    pub score_available: CoverageStatus,
    pub runner_state_available: CoverageStatus,
    pub batter_available: CoverageStatus,
    pub pitcher_available: CoverageStatus,
    pub final_outcome_available: CoverageStatus,
    pub reconstruction_valid: CoverageStatus,
    pub reconstruction_warnings: String,
    pub notes: String,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct CoverageReport {
    pub coverage_version: String,
    pub generated_note: String,
    pub mlb_2025: String,
    pub mlb_2026: String,
    pub historical_pbp_files: usize,
    pub rows: Vec<GameCoverageRow>,
}

pub fn report_from_lake(lake_root: &Path) -> CoverageReport {
    let mlb = lake_root.join("MLB").join("2025-2026");
    let manifests = mlb.join("manifests");
    let mut rows = Vec::new();
    let mut complete_2026 = 0u32;
    let mut empty_2025 = 0u32;
    if manifests.is_dir() {
        let mut paths: Vec<PathBuf> = std::fs::read_dir(&manifests)
            .into_iter()
            .flatten()
            .flatten()
            .map(|e| e.path())
            .filter(|p| p.extension().and_then(|s| s.to_str()) == Some("json"))
            .collect();
        paths.sort();
        for p in paths {
            let Ok(text) = std::fs::read_to_string(&p) else {
                continue;
            };
            let Ok(m) = serde_json::from_str::<DailyManifest>(&text) else {
                continue;
            };
            if m.date.year() == 2025 {
                empty_2025 += 1;
                rows.push(season_missing_row(
                    "2025",
                    m.date,
                    "2025 probe: no KXMLBGAME content locally; PBP also absent",
                ));
                continue;
            }
            if m.markets_discovered == 0 {
                rows.push(date_row(
                    "2026",
                    m.date,
                    "UNAVAILABLE",
                    "Kalshi probe empty; PBP MISSING_HISTORICAL_SOURCE",
                    CoverageStatus::MissingHistoricalSource,
                ));
                continue;
            }
            complete_2026 += 1;
            let tickers =
                unique_event_tickers(&mlb.join("orderbook").join(format!("date={}", m.date)));
            if tickers.is_empty() {
                let games_est = m.markets_collected / 2;
                rows.push(date_row(
                    "2026",
                    m.date,
                    &format!("games_est={games_est}"),
                    "Kalshi COMPLETE day; metadata.parquet absent; PBP MISSING_HISTORICAL_SOURCE; GameId list not invented",
                    CoverageStatus::MissingHistoricalSource,
                ));
            } else {
                for t in tickers {
                    rows.push(kalshi_unmapped_row(m.date, &t));
                }
            }
        }
    }
    CoverageReport {
        coverage_version: COVERAGE_VERSION.into(),
        generated_note: "PBP is not present in the repository. Kalshi rows are UNMAPPED aliases, not official MLB games.".into(),
        mlb_2025: format!(
            "MISSING_HISTORICAL_SOURCE ({empty_2025} local probes, 0 PBP, 0 reconstructed games)"
        ),
        mlb_2026: format!(
            "{complete_2026} Kalshi COMPLETE PT days locally; PBP MISSING_HISTORICAL_SOURCE for all"
        ),
        historical_pbp_files: 0,
        rows,
    }
}

fn season_missing_row(season: &str, date: NaiveDate, note: &str) -> GameCoverageRow {
    date_row(
        season,
        date,
        "UNAVAILABLE",
        note,
        CoverageStatus::MissingHistoricalSource,
    )
}

fn date_row(
    season: &str,
    date: NaiveDate,
    game_id: &str,
    note: &str,
    pbp: CoverageStatus,
) -> GameCoverageRow {
    GameCoverageRow {
        season: season.into(),
        date: date.to_string(),
        game_id: game_id.into(),
        home_team: "UNAVAILABLE".into(),
        away_team: "UNAVAILABLE".into(),
        pbp_available: pbp,
        pitch_level_available: CoverageStatus::MissingHistoricalSource,
        timestamps_available: CoverageStatus::MissingHistoricalSource,
        score_available: CoverageStatus::MissingHistoricalSource,
        runner_state_available: CoverageStatus::MissingHistoricalSource,
        batter_available: CoverageStatus::MissingHistoricalSource,
        pitcher_available: CoverageStatus::MissingHistoricalSource,
        final_outcome_available: CoverageStatus::MissingHistoricalSource,
        reconstruction_valid: CoverageStatus::Missing,
        reconstruction_warnings: "no PBP to reconstruct".into(),
        notes: note.into(),
    }
}

fn kalshi_unmapped_row(date: NaiveDate, event_ticker: &str) -> GameCoverageRow {
    let ident = crate::identity::IdentityRegistry::kalshi_only_unmapped(event_ticker, event_ticker);
    let date_tok = kalshi_event_date_token(event_ticker).unwrap_or_else(|| date.to_string());
    GameCoverageRow {
        season: "2026".into(),
        date: date_tok,
        game_id: ident.canonical_game_id.0,
        home_team: "UNAVAILABLE".into(),
        away_team: "UNAVAILABLE".into(),
        pbp_available: CoverageStatus::MissingHistoricalSource,
        pitch_level_available: CoverageStatus::MissingHistoricalSource,
        timestamps_available: CoverageStatus::MissingHistoricalSource,
        score_available: CoverageStatus::MissingHistoricalSource,
        runner_state_available: CoverageStatus::MissingHistoricalSource,
        batter_available: CoverageStatus::MissingHistoricalSource,
        pitcher_available: CoverageStatus::MissingHistoricalSource,
        final_outcome_available: CoverageStatus::Unverified,
        reconstruction_valid: CoverageStatus::Missing,
        reconstruction_warnings: "Kalshi alias only; mlb_game_pk UNMAPPED; no PBP".into(),
        notes: format!("event_ticker={event_ticker}"),
    }
}

pub(crate) fn unique_event_tickers(orderbook_day: &Path) -> BTreeSet<String> {
    let path = orderbook_day.join("orderbook.parquet");
    let Ok(file) = File::open(&path) else {
        return BTreeSet::new();
    };
    let Ok(builder) = ParquetRecordBatchReaderBuilder::try_new(file) else {
        return BTreeSet::new();
    };
    let Ok(reader) = builder.build() else {
        return BTreeSet::new();
    };
    let mut out = BTreeSet::new();
    for batch in reader.flatten() {
        let Some(col) = batch.column_by_name("ticker") else {
            continue;
        };
        let Some(arr) = col.as_any().downcast_ref::<StringArray>() else {
            continue;
        };
        for i in 0..arr.len() {
            if arr.is_valid(i) {
                let t = arr.value(i);
                let event = match t.rsplit_once('-') {
                    Some((event, _)) if event.contains("KXMLBGAME") => event,
                    _ => t,
                };
                out.insert(event.to_string());
            }
        }
    }
    out
}
