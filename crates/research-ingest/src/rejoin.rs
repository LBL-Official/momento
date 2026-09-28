//! Offline landing-wide identity rejoin. Does not fetch. Does not invent gamePk.

use std::collections::BTreeMap;
use std::fs;
use std::path::{Path, PathBuf};

use chrono::{NaiveDate, Utc};
use serde::{Deserialize, Serialize};

use crate::corpus::corpus_from_pairs;
use crate::error::IngestError;
use crate::join::{ObservedMlbGame, join_game_market_pairs};
use crate::kalshi::{DiscoveredMarket, completeness_from_landed_bytes};
use crate::lock::IngestLock;
use crate::paths::{IngestPaths, write_json_atomic};
use crate::types::{
    ARTIFACT_VERSION, CorpusCoverage, IdentityMapping, PLANE, SOURCE_KALSHI_DISCOVERY,
    SOURCE_STATSAPI,
};

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct LandingRejoinReport {
    pub run_id: String,
    pub plane: String,
    pub artifact_version: String,
    pub generated_at: String,
    pub pairs_path: String,
    pub pbp_envelopes_read: usize,
    pub pbp_identity_ok: usize,
    pub pbp_identity_failed: usize,
    pub kalshi_envelopes_read: usize,
    pub kalshi_markets: usize,
    pub identity_version: String,
    pub corpus: CorpusCoverage,
    pub notes: String,
}

pub fn rejoin_landing(ingest_root: &Path) -> Result<LandingRejoinReport, IngestError> {
    let paths = IngestPaths::new(ingest_root);
    let _lock = IngestLock::acquire(paths.lock_path())?;
    let generated_at = Utc::now();
    let run_id = format!("rejoin-{}", generated_at.format("%Y%m%dT%H%M%SZ"));
    let run_dir = paths.ensure_run(&run_id)?;

    let pbp_root = ingest_root.join("landing").join(SOURCE_STATSAPI);
    let kalshi_root = ingest_root.join("landing").join(SOURCE_KALSHI_DISCOVERY);

    let pbp_files = collect_files(&pbp_root, ".envelope.json")?;
    let kalshi_files = collect_files(&kalshi_root, ".envelope.json")?;

    let mut games_by_pk: BTreeMap<String, ObservedMlbGame> = BTreeMap::new();
    let mut pbp_identity_failed = 0usize;
    for path in &pbp_files {
        let bytes = fs::read(path)?;
        match momento_research_event::official_ref_from_envelope_bytes(&bytes) {
            Ok(official) => {
                games_by_pk.insert(
                    official.game_pk.clone(),
                    ObservedMlbGame::from_official(&official),
                );
            }
            Err(_) => {
                pbp_identity_failed += 1;
            }
        }
    }
    let games: Vec<ObservedMlbGame> = games_by_pk.into_values().collect();

    let mut markets_by_ticker: BTreeMap<String, DiscoveredMarket> = BTreeMap::new();
    for path in &kalshi_files {
        let bytes = fs::read(path)?;
        let Ok(v) = serde_json::from_slice::<serde_json::Value>(&bytes) else {
            continue;
        };
        let ticker = v
            .get("ticker")
            .and_then(|x| x.as_str())
            .unwrap_or("")
            .to_string();
        if ticker.is_empty() {
            continue;
        }
        let event_ticker = v
            .get("event_ticker")
            .and_then(|x| x.as_str())
            .filter(|s| !s.is_empty())
            .map(str::to_string);
        let Some(date) = date_from_landing_path(path) else {
            continue;
        };
        let completeness = completeness_from_landed_bytes(&bytes);
        markets_by_ticker.insert(
            ticker.clone(),
            DiscoveredMarket {
                date,
                ticker,
                event_ticker,
                series: v.get("series").and_then(|x| x.as_str()).map(str::to_string),
                mapping: IdentityMapping::Unmatched,
                observed_game_pk: None,
                completeness,
                notes: "rejoin from landed discovery envelope".into(),
                open_time: None,
                close_time: None,
                result: None,
                settlement_ts: None,
                settlement_value_dollars: None,
                status: None,
            },
        );
    }
    let markets: Vec<DiscoveredMarket> = markets_by_ticker.into_values().collect();

    let pairs = join_game_market_pairs(&games, &markets);
    let pairs_path = run_dir.join("game_market_pairs.json");
    write_json_atomic(&pairs_path, &pairs)?;

    let kalshi_committed = markets.len();
    let corpus = corpus_from_pairs(
        games.len(),
        games.len(),
        markets.len(),
        kalshi_committed,
        &pairs,
    );

    let report = LandingRejoinReport {
        run_id: run_id.clone(),
        plane: PLANE.into(),
        artifact_version: ARTIFACT_VERSION.into(),
        generated_at: generated_at.to_rfc3339(),
        pairs_path: pairs_path.display().to_string(),
        pbp_envelopes_read: pbp_files.len(),
        pbp_identity_ok: games.len(),
        pbp_identity_failed,
        kalshi_envelopes_read: kalshi_files.len(),
        kalshi_markets: markets.len(),
        identity_version: momento_research_event::versions::IDENTITY_VERSION.into(),
        corpus,
        notes: "offline landing rejoin; unique abbr+game_number suffix; gamePk observed from StatsAPI envelopes; no invented pk; L2 not inferred"
            .into(),
    };
    write_json_atomic(&run_dir.join("rejoin_report.json"), &report)?;
    Ok(report)
}

fn collect_files(root: &Path, suffix: &str) -> Result<Vec<PathBuf>, IngestError> {
    let mut out = Vec::new();
    if !root.exists() {
        return Ok(out);
    }
    walk_files(root, suffix, &mut out)?;
    out.sort();
    Ok(out)
}

fn walk_files(dir: &Path, suffix: &str, out: &mut Vec<PathBuf>) -> Result<(), IngestError> {
    for entry in fs::read_dir(dir)? {
        let entry = entry?;
        let path = entry.path();
        if path.is_dir() {
            walk_files(&path, suffix, out)?;
        } else if path
            .file_name()
            .and_then(|n| n.to_str())
            .is_some_and(|n| n.ends_with(suffix))
        {
            out.push(path);
        }
    }
    Ok(())
}

fn date_from_landing_path(path: &Path) -> Option<NaiveDate> {
    path.iter().filter_map(|c| c.to_str()).find_map(|s| {
        s.strip_prefix("date=")
            .and_then(|d| NaiveDate::parse_from_str(d, "%Y-%m-%d").ok())
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    #[test]
    fn landing_rejoin_maps_numbered_doubleheader() {
        let tmp = tempfile::TempDir::new().unwrap();
        let ingest = tmp.path().join("ingest");
        let date = "2025-04-18";
        let pbp_dir = ingest
            .join("landing")
            .join(SOURCE_STATSAPI)
            .join(format!("date={date}"));
        let k_dir = ingest
            .join("landing")
            .join(SOURCE_KALSHI_DISCOVERY)
            .join(format!("date={date}"));
        fs::create_dir_all(&pbp_dir).unwrap();
        fs::create_dir_all(&k_dir).unwrap();

        write_pbp(
            &pbp_dir.join("gamePk=1.envelope.json"),
            "1",
            "ATH",
            "MIL",
            1,
        );
        write_pbp(
            &pbp_dir.join("gamePk=2.envelope.json"),
            "2",
            "ATH",
            "MIL",
            2,
        );
        write_kalshi(
            &k_dir.join("ticker=KXMLBGAME-25APR18ATHMIL-ATH.envelope.json"),
            "KXMLBGAME-25APR18ATHMIL-ATH",
            "KXMLBGAME-25APR18ATHMIL",
        );
        write_kalshi(
            &k_dir.join("ticker=KXMLBGAME-25APR18ATHMIL2-ATH.envelope.json"),
            "KXMLBGAME-25APR18ATHMIL2-ATH",
            "KXMLBGAME-25APR18ATHMIL2",
        );

        let report = rejoin_landing(&ingest).unwrap();
        assert_eq!(report.pbp_identity_ok, 2);
        assert_eq!(report.pbp_identity_failed, 0);
        assert_eq!(report.corpus.games_mapped, 2);
        assert_eq!(report.corpus.pairs_mapped, 2);
        assert_eq!(report.corpus.pairs_ambiguous, 0);
    }

    fn write_pbp(path: &Path, pk: &str, away: &str, home: &str, game_number: u8) {
        let pk_n: i64 = pk.parse().unwrap();
        let env = json!({
            "envelope_version": "W2.RAW.1.0.0",
            "fixture_kind": "HISTORICAL_SOURCE",
            "source": "mlb_statsapi",
            "source_game_id": pk,
            "payload": {
                "gameData": {
                    "game": {"pk": pk_n, "gameNumber": game_number},
                    "datetime": {"officialDate": "2025-04-18"},
                    "teams": {
                        "home": {"id": 1, "abbreviation": home},
                        "away": {"id": 2, "abbreviation": away}
                    },
                    "status": {"detailedState": "Final", "abstractGameState": "Final"}
                },
                "liveData": {"plays": {"allPlays": []}}
            }
        });
        fs::write(path, serde_json::to_vec(&env).unwrap()).unwrap();
    }

    fn write_kalshi(path: &Path, ticker: &str, event: &str) {
        let env = json!({
            "envelope_version": "INGEST.KALSHI.DISCOVERY.1.0.0",
            "fixture_kind": "HISTORICAL_SOURCE",
            "source": "kalshi_discovery",
            "ticker": ticker,
            "event_ticker": event,
            "series": "KXMLBGAME",
            "payload": {"completeness": "MARKET_METADATA_ONLY"}
        });
        fs::write(path, serde_json::to_vec(&env).unwrap()).unwrap();
    }
}
