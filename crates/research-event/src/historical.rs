//! Reconstruct GameState / identity / event-time from collected StatsAPI envelopes.

use std::collections::BTreeMap;
use std::fs;
use std::path::{Path, PathBuf};

use chrono::NaiveDate;
use serde::{Deserialize, Serialize};

use crate::adapter::{EventStateAdapter, MlbEventAdapter};
use crate::coverage::unique_event_tickers;
use crate::error::EventError;
use crate::identity::{
    IdentityRegistry, MappingRecord, MlbMatchStatus, OfficialMlbGameRef,
    kalshi_alias_from_event_ticker, kalshi_event_date_token, match_official_to_kalshi_tickers,
};
use crate::ingest::ingest_path;
use crate::state::replay;
use crate::versions::{IDENTITY_VERSION, STATE_MACHINE_VERSION};

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct GameReconstructionRow {
    pub game_pk: String,
    pub canonical_game_id: String,
    pub official_date: String,
    pub away_abbreviation: String,
    pub home_abbreviation: String,
    pub envelope_path: String,
    pub events: usize,
    pub ingest_malformed: usize,
    pub ingest_duplicates: usize,
    pub reconstruction: String,
    pub reconstruction_error: Option<String>,
    pub final_status: Option<String>,
    pub kalshi_match_status: String,
    pub kalshi_event_ticker: Option<String>,
    pub theta_status: String,
    pub theta_value_unavailable: bool,
    pub outs_elapsed_final: Option<u16>,
    pub regulation_outs_remaining_final: Option<u16>,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct HistoricalReconstructionReport {
    pub raw_root: String,
    pub games_attempted: usize,
    pub ingest_ok: usize,
    pub reconstruction_ok: usize,
    pub reconstruction_failed: usize,
    pub kalshi_mapped: usize,
    pub kalshi_unmatched: usize,
    pub kalshi_ambiguous: usize,
    pub machine_version: String,
    pub identity_version: String,
    pub rows: Vec<GameReconstructionRow>,
}

pub fn default_raw_root(out_dir: &Path) -> PathBuf {
    out_dir.join("raw").join("statsapi")
}

pub fn list_envelopes(raw_root: &Path) -> Vec<PathBuf> {
    let mut out = Vec::new();
    walk(raw_root, &mut out);
    out.sort();
    out
}

fn walk(dir: &Path, out: &mut Vec<PathBuf>) {
    let Ok(entries) = fs::read_dir(dir) else {
        return;
    };
    for ent in entries.flatten() {
        let p = ent.path();
        if p.is_dir() {
            walk(&p, out);
        } else if p
            .file_name()
            .and_then(|s| s.to_str())
            .is_some_and(|n| n.ends_with(".envelope.json"))
        {
            out.push(p);
        }
    }
}

fn tickers_by_date(lake_root: &Path) -> BTreeMap<String, Vec<String>> {
    let mlb = lake_root.join("MLB").join("2025-2026").join("orderbook");
    let mut map = BTreeMap::new();
    let Ok(days) = fs::read_dir(&mlb) else {
        return map;
    };
    for ent in days.flatten() {
        let name = ent.file_name().to_string_lossy().into_owned();
        let Some(date) = name.strip_prefix("date=") else {
            continue;
        };
        let tickers: Vec<String> = unique_event_tickers(&ent.path()).into_iter().collect();
        map.insert(date.to_string(), tickers);
    }
    map
}

pub fn reconstruct_envelopes(
    raw_root: &Path,
    lake_root: &Path,
) -> Result<HistoricalReconstructionReport, EventError> {
    reconstruct_paths(
        &list_envelopes(raw_root),
        lake_root,
        &raw_root.display().to_string(),
    )
}

/// Reconstruct only the given envelope paths (ingest-plane committed refs).
pub fn reconstruct_paths(
    envelopes: &[PathBuf],
    lake_root: &Path,
    raw_root_label: &str,
) -> Result<HistoricalReconstructionReport, EventError> {
    let tickers = tickers_by_date(lake_root);
    let adapter = MlbEventAdapter;
    let mut registry = IdentityRegistry::new();
    let mut rows = Vec::new();
    let mut ingest_ok = 0usize;
    let mut recon_ok = 0usize;
    let mut recon_fail = 0usize;
    let mut mapped = 0usize;
    let mut unmatched = 0usize;
    let mut ambiguous = 0usize;

    for path in envelopes {
        match ingest_path(path) {
            Ok((events, report, official)) => {
                ingest_ok += 1;
                let gid = match registry.register_official(official.clone()) {
                    Ok(id) => id,
                    Err(e) => {
                        recon_fail += 1;
                        rows.push(failed_row(
                            &official,
                            path,
                            Some(e.to_string()),
                            report.events,
                        ));
                        continue;
                    }
                };
                let date = official.official_date.to_string();
                let day_tickers = tickers.get(&date).cloned().unwrap_or_default();
                let (mst, hits) = match_official_to_kalshi_tickers(&official, &day_tickers);
                match mst {
                    MlbMatchStatus::Mapped => mapped += 1,
                    MlbMatchStatus::Unmatched => unmatched += 1,
                    MlbMatchStatus::Ambiguous => ambiguous += 1,
                    _ => {}
                }
                if mst == MlbMatchStatus::Mapped {
                    if let Some(ticker) = hits.first() {
                        let mut kalshi = kalshi_alias_from_event_ticker(ticker, ticker);
                        kalshi.mlb_game_pk = Some(official.game_pk.clone());
                        let mapping = MappingRecord {
                            from: crate::identity::SourceRef {
                                source: "kalshi_event_ticker".into(),
                                source_id: ticker.clone(),
                            },
                            to: crate::identity::SourceRef {
                                source: official.source.clone(),
                                source_id: official.game_pk.clone(),
                            },
                            status: MlbMatchStatus::Mapped,
                            provenance_note: "DERIVED unique match of observed StatsAPI \
abbreviations to observed Kalshi event_ticker suffix; gamePk copied from StatsAPI (OBSERVED)."
                                .into(),
                            identity_version: IDENTITY_VERSION.into(),
                        };
                        let _ = registry.attach_kalshi_mapping(&gid, kalshi, mapping);
                    }
                }
                let (recon, err, last_status, theta_status, theta_unavail, elapsed, remain) =
                    match replay(&events) {
                        Ok(trs) => {
                            recon_ok += 1;
                            let last = trs.last().map(|t| t.after.clone());
                            let status = last.as_ref().map(|s| format!("{:?}", s.game_status));
                            let (ts, tu, el, rem) =
                                if let (Some(st), Some(ev)) = (last.as_ref(), events.last()) {
                                    let et = adapter.event_time(st, ev);
                                    (
                                        et.event_theta.status.clone(),
                                        et.event_theta.inputs.theta_value.is_unavailable(),
                                        Some(et.outs_elapsed),
                                        Some(et.regulation_outs_remaining),
                                    )
                                } else {
                                    ("UNAVAILABLE".into(), true, None, None)
                                };
                            ("VALID".into(), None, status, ts, tu, el, rem)
                        }
                        Err(e) => {
                            recon_fail += 1;
                            (
                                "INVALID".into(),
                                Some(e.to_string()),
                                None,
                                "UNAVAILABLE".into(),
                                true,
                                None,
                                None,
                            )
                        }
                    };
                rows.push(GameReconstructionRow {
                    game_pk: official.game_pk,
                    canonical_game_id: gid.as_str().to_string(),
                    official_date: date,
                    away_abbreviation: official.away_abbreviation,
                    home_abbreviation: official.home_abbreviation,
                    envelope_path: path.display().to_string(),
                    events: events.len(),
                    ingest_malformed: report.malformed.len(),
                    ingest_duplicates: report.duplicates.len(),
                    reconstruction: recon,
                    reconstruction_error: err,
                    final_status: last_status,
                    kalshi_match_status: format!("{mst:?}"),
                    kalshi_event_ticker: hits.first().cloned(),
                    theta_status,
                    theta_value_unavailable: theta_unavail,
                    outs_elapsed_final: elapsed,
                    regulation_outs_remaining_final: remain,
                });
            }
            Err(e) => {
                recon_fail += 1;
                rows.push(GameReconstructionRow {
                    game_pk: path
                        .file_stem()
                        .map(|s| s.to_string_lossy().into_owned())
                        .unwrap_or_default(),
                    canonical_game_id: String::new(),
                    official_date: String::new(),
                    away_abbreviation: String::new(),
                    home_abbreviation: String::new(),
                    envelope_path: path.display().to_string(),
                    events: 0,
                    ingest_malformed: 0,
                    ingest_duplicates: 0,
                    reconstruction: "INGEST_FAIL".into(),
                    reconstruction_error: Some(e.to_string()),
                    final_status: None,
                    kalshi_match_status: "UNMAPPED".into(),
                    kalshi_event_ticker: None,
                    theta_status: "UNAVAILABLE".into(),
                    theta_value_unavailable: true,
                    outs_elapsed_final: None,
                    regulation_outs_remaining_final: None,
                });
            }
        }
    }

    Ok(HistoricalReconstructionReport {
        raw_root: raw_root_label.to_string(),
        games_attempted: envelopes.len(),
        ingest_ok,
        reconstruction_ok: recon_ok,
        reconstruction_failed: recon_fail,
        kalshi_mapped: mapped,
        kalshi_unmatched: unmatched,
        kalshi_ambiguous: ambiguous,
        machine_version: STATE_MACHINE_VERSION.into(),
        identity_version: IDENTITY_VERSION.into(),
        rows,
    })
}

fn failed_row(
    official: &OfficialMlbGameRef,
    path: &Path,
    err: Option<String>,
    events: usize,
) -> GameReconstructionRow {
    GameReconstructionRow {
        game_pk: official.game_pk.clone(),
        canonical_game_id: String::new(),
        official_date: official.official_date.to_string(),
        away_abbreviation: official.away_abbreviation.clone(),
        home_abbreviation: official.home_abbreviation.clone(),
        envelope_path: path.display().to_string(),
        events,
        ingest_malformed: 0,
        ingest_duplicates: 0,
        reconstruction: "IDENTITY_FAIL".into(),
        reconstruction_error: err,
        final_status: None,
        kalshi_match_status: "UNMAPPED".into(),
        kalshi_event_ticker: None,
        theta_status: "UNAVAILABLE".into(),
        theta_value_unavailable: true,
        outs_elapsed_final: None,
        regulation_outs_remaining_final: None,
    }
}

pub fn write_report(
    out_dir: &Path,
    report: &HistoricalReconstructionReport,
) -> std::io::Result<PathBuf> {
    fs::create_dir_all(out_dir)?;
    let path = out_dir.join("historical_reconstruction.json");
    fs::write(path.clone(), serde_json::to_vec_pretty(report)?)?;
    Ok(path)
}

/// Used by coverage to avoid duplicating parquet ticker extraction.
pub fn kalshi_tickers_for_date(lake_root: &Path, date: NaiveDate) -> Vec<String> {
    let p = lake_root
        .join("MLB")
        .join("2025-2026")
        .join("orderbook")
        .join(format!("date={date}"));
    unique_event_tickers(&p).into_iter().collect()
}

pub fn filter_tickers_on_date(tickers: &[String], date: NaiveDate) -> Vec<String> {
    let want = date.to_string();
    tickers
        .iter()
        .filter(|t| kalshi_event_date_token(t).as_deref() == Some(want.as_str()))
        .cloned()
        .collect()
}
