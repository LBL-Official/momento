//! First exact-83¢ TRADE per game. Not first-in-band 80–83. Research only.

use std::collections::BTreeMap;
use std::fs;

use chrono::Utc;
use momento_research_data::foundation::LakeWriteGuard;
use momento_research_path::{PathObservation, PathStore};
use momento_research_state::StateStore;
use serde::Serialize;

use crate::batch::B1RunConfig;
use crate::dataset::{W8EntryInput, extract_snapshot};
use crate::error::B1Error;
use crate::identity::load_envelope_identity;
use crate::normalization::attach_train_conditioned_z;
use crate::store::{FeatureStore, load_w6_game_meta, load_w8_entries};
use crate::types::B1EntrySnapshot;
use crate::validation::validate_snapshot;
use crate::versions::{ENGINE_VERSION, FEATURE_SCHEMA_VERSION};

const UNIVERSE: &str = "FIRST_EXACT_83_TRADE";

#[derive(Clone, Debug, Serialize)]
pub struct First83ExtractReport {
    pub universe: &'static str,
    pub definition: &'static str,
    pub w7_games: usize,
    pub w8_bound_games: usize,
    pub snapshots_written: usize,
    pub unique_games: usize,
    pub skipped_no_83: usize,
    pub skipped_bound_contract_no_83: usize,
    pub unbound_yes_or_earliest: usize,
    pub features_sqlite: String,
    pub fill_status: &'static str,
    pub feature_schema_version: &'static str,
    pub engine_version: &'static str,
    pub notes: Vec<String>,
}

fn pick_first_83<'a>(
    path: &'a [PathObservation],
    bound: Option<(&str, &str)>,
) -> Result<Option<&'a PathObservation>, &'static str> {
    let mut hits: Vec<&PathObservation> = path
        .iter()
        .filter(|o| o.trade_price_cents == Some(83) && o.market_timestamp_utc.is_some())
        .collect();
    if hits.is_empty() {
        return Ok(None);
    }
    if let Some((mid, side)) = bound {
        hits.retain(|o| o.market_id == mid && o.contract_side.eq_ignore_ascii_case(side));
        if hits.is_empty() {
            return Err("bound_no_83");
        }
    }
    hits.sort_by(|a, b| {
        a.market_timestamp_utc
            .cmp(&b.market_timestamp_utc)
            .then_with(|| a.market_id.cmp(&b.market_id))
            .then_with(|| a.contract_side.cmp(&b.contract_side))
            .then_with(|| a.observation_id.cmp(&b.observation_id))
    });
    Ok(hits.into_iter().next())
}

fn to_input(
    game_id: &str,
    obs: &PathObservation,
    w8: Option<&W8EntryInput>,
) -> Option<W8EntryInput> {
    let ts = obs.market_timestamp_utc?;
    Some(W8EntryInput {
        opportunity_id: w8
            .map(|e| e.opportunity_id.clone())
            .unwrap_or_else(|| format!("first83:{game_id}")),
        game_id: game_id.to_string(),
        market_id: obs.market_id.clone(),
        side: obs.contract_side.clone(),
        entry_timestamp: ts,
        entry_observation_id: obs.observation_id.clone(),
        entry_price_cents: 83,
        first80_observation_id: w8.and_then(|e| e.first80_observation_id.clone()),
        first80_timestamp: w8.and_then(|e| e.first80_timestamp),
        confirm_observation_id: w8.and_then(|e| e.confirm_observation_id.clone()),
        official_date: None,
        game_pk: None,
        game_status: None,
    })
}

/// Extract one first exact-83¢ TRADE snapshot per W7 game. Does not overwrite
/// the first-in-band `features.sqlite`.
pub fn run_first83_extract(cfg: &B1RunConfig) -> Result<First83ExtractReport, B1Error> {
    let guard = LakeWriteGuard::new(&cfg.lake_root);
    let out_dir = cfg.out_dir.join("first83");
    guard
        .assert_not_lake_path(&out_dir)
        .map_err(B1Error::LakeWriteForbidden)?;

    let w7 = PathStore::open_existing(&cfg.w7_sqlite)?;
    let w6 = StateStore::open_existing(&cfg.w6_sqlite)?;
    let w7_meta = w7.run_meta()?;
    let games = w7.list_game_ids()?;
    let w8_entries = load_w8_entries(&cfg.w8_sqlite).unwrap_or_default();
    let mut w8_by_game: BTreeMap<String, W8EntryInput> = BTreeMap::new();
    for e in w8_entries {
        w8_by_game.entry(e.game_id.clone()).or_insert(e);
    }

    fs::create_dir_all(&out_dir)?;
    let db = out_dir.join("features.sqlite");
    for extra in [
        "features.sqlite",
        "features.sqlite-wal",
        "features.sqlite-shm",
    ] {
        let p = out_dir.join(extra);
        if p.exists() {
            let _ = fs::remove_file(&p);
        }
    }

    let generated_at = Utc::now();
    let run_id = format!("b1-first83-{}", generated_at.format("%Y%m%dT%H%M%SZ"));
    let store = FeatureStore::open(
        &db,
        &run_id,
        generated_at,
        w6.run_id(),
        &w7_meta.run_id,
        "FIRST_EXACT_83",
        Some(&w7_meta.w5_dataset_version),
    )?;
    let identity = load_envelope_identity(&cfg.identity_landing);

    let mut snapshots: Vec<B1EntrySnapshot> = Vec::new();
    let mut skipped_no_83 = 0usize;
    let mut skipped_bound = 0usize;
    let mut unbound = 0usize;
    let n_games = games.len();

    for (i, gid) in games.iter().enumerate() {
        let path = w7.path_for_game(gid)?;
        let w8 = w8_by_game.get(gid);
        let bound = w8.map(|e| (e.market_id.as_str(), e.side.as_str()));
        match pick_first_83(&path, bound) {
            Ok(None) => skipped_no_83 += 1,
            Err("bound_no_83") => skipped_bound += 1,
            Ok(Some(obs)) => {
                if w8.is_none() {
                    unbound += 1;
                }
                let Some(mut entry) = to_input(gid, obs, w8) else {
                    skipped_no_83 += 1;
                    continue;
                };
                let (date, pk, status) = load_w6_game_meta(&cfg.w6_sqlite, gid)?;
                entry.official_date = date;
                entry.game_pk = pk.clone();
                entry.game_status = status;
                let states = w6.load_states(gid)?;
                let transitions = w6.load_transitions(gid)?;
                let ident = pk.as_ref().and_then(|p| identity.get(p));
                snapshots.push(extract_snapshot(
                    &entry,
                    &path,
                    &states,
                    &transitions,
                    ident,
                ));
            }
            Err(_) => skipped_no_83 += 1,
        }
        if (i + 1) % 50 == 0 || i + 1 == n_games {
            eprintln!(
                "first83 extract {}/{} games; kept {}",
                i + 1,
                n_games,
                snapshots.len()
            );
        }
    }

    attach_train_conditioned_z(&mut snapshots);
    for (i, snap) in snapshots.iter().enumerate() {
        if snap.entry_trade_price_cents != 83 {
            return Err(B1Error::validation(
                "NOT_83",
                format!("extracted non-83 entry for {}", snap.game_id),
            ));
        }
        validate_snapshot(snap)?;
        store.insert_snapshot(snap)?;
        if (i + 1) % 50 == 0 {
            store.checkpoint()?;
        }
    }
    store.checkpoint()?;

    let unique = {
        let s: std::collections::BTreeSet<&str> =
            snapshots.iter().map(|x| x.game_id.as_str()).collect();
        s.len()
    };
    if unique != snapshots.len() {
        return Err(B1Error::validation(
            "DUP_GAME",
            format!(
                "duplicate games in first-83 extract: {unique} vs {}",
                snapshots.len()
            ),
        ));
    }

    let report = First83ExtractReport {
        universe: UNIVERSE,
        definition: "First W7 TRADE print at exactly 83¢ per game. Bound to the W8 market/side when that opportunity exists; otherwise the earliest 83¢ TRADE (timestamp, market_id, side, observation_id). One snapshot per game. Features use only path/state at or before that timestamp. Not first-in-band 80–83. TRADE print ≠ fill.",
        w7_games: n_games,
        w8_bound_games: w8_by_game.len(),
        snapshots_written: snapshots.len(),
        unique_games: unique,
        skipped_no_83,
        skipped_bound_contract_no_83: skipped_bound,
        unbound_yes_or_earliest: unbound,
        features_sqlite: db.display().to_string(),
        fill_status: "TRADE_PRINT_MODELED",
        feature_schema_version: FEATURE_SCHEMA_VERSION,
        engine_version: ENGINE_VERSION,
        notes: vec![
            "Does not overwrite B1/features.sqlite (first-in-band 80–83).".into(),
            "Games that never print 83¢ are not 83¢ observations.".into(),
            "No L2 invented. No live FIRST01 change.".into(),
        ],
    };
    fs::write(
        out_dir.join("b1_83_universe.json"),
        serde_json::to_string_pretty(&report)?,
    )?;
    Ok(report)
}

pub fn first83_out_dir(cfg: &B1RunConfig) -> std::path::PathBuf {
    cfg.out_dir.join("first83")
}

pub fn first83_features_sqlite(cfg: &B1RunConfig) -> std::path::PathBuf {
    first83_out_dir(cfg).join("features.sqlite")
}

/// Extract first-exact-83 snapshots for a caller-supplied game set into a
/// dedicated sqlite. Refuses to write the locked `first83/features.sqlite`.
pub fn run_first83_extract_subset(
    cfg: &B1RunConfig,
    game_ids: &[String],
    out_sqlite: &std::path::Path,
    min_official_date_exclusive: &str,
) -> Result<First83ExtractReport, B1Error> {
    if out_sqlite
        .parent()
        .and_then(|p| p.file_name())
        .is_some_and(|n| n == "first83")
    {
        return Err(B1Error::validation(
            "LOCKED_FIRST83",
            "refusing to write prospective extract into locked first83/",
        ));
    }
    let guard = LakeWriteGuard::new(&cfg.lake_root);
    if let Some(parent) = out_sqlite.parent() {
        guard
            .assert_not_lake_path(parent)
            .map_err(B1Error::LakeWriteForbidden)?;
        fs::create_dir_all(parent)?;
    }
    let w7 = PathStore::open_existing(&cfg.w7_sqlite)?;
    let w6 = StateStore::open_existing(&cfg.w6_sqlite)?;
    let w7_meta = w7.run_meta()?;
    let w8_entries = load_w8_entries(&cfg.w8_sqlite).unwrap_or_default();
    let mut w8_by_game: BTreeMap<String, W8EntryInput> = BTreeMap::new();
    for e in w8_entries {
        w8_by_game.entry(e.game_id.clone()).or_insert(e);
    }
    for extra in [
        "features.sqlite",
        "features.sqlite-wal",
        "features.sqlite-shm",
    ] {
        if let Some(parent) = out_sqlite.parent() {
            let p = parent.join(extra);
            if p.exists() {
                let _ = fs::remove_file(&p);
            }
        }
    }
    if out_sqlite.exists() {
        let _ = fs::remove_file(out_sqlite);
    }
    let generated_at = Utc::now();
    let run_id = format!(
        "b1-first83-prospective-{}",
        generated_at.format("%Y%m%dT%H%M%SZ")
    );
    let store = FeatureStore::open(
        out_sqlite,
        &run_id,
        generated_at,
        w6.run_id(),
        &w7_meta.run_id,
        "FIRST_EXACT_83_PROSPECTIVE",
        Some(&w7_meta.w5_dataset_version),
    )?;
    let identity = load_envelope_identity(&cfg.identity_landing);
    let mut snapshots: Vec<B1EntrySnapshot> = Vec::new();
    let mut skipped_no_83 = 0usize;
    let mut skipped_bound = 0usize;
    let mut unbound = 0usize;
    let mut seen = BTreeMap::new();
    for gid in game_ids {
        let path = w7.path_for_game(gid)?;
        let w8 = w8_by_game.get(gid);
        let bound = w8.map(|e| (e.market_id.as_str(), e.side.as_str()));
        match pick_first_83(&path, bound) {
            Ok(None) => skipped_no_83 += 1,
            Err("bound_no_83") => skipped_bound += 1,
            Ok(Some(obs)) => {
                if w8.is_none() {
                    unbound += 1;
                }
                let Some(mut entry) = to_input(gid, obs, w8) else {
                    skipped_no_83 += 1;
                    continue;
                };
                let (date, pk, status) = load_w6_game_meta(&cfg.w6_sqlite, gid)?;
                if let Some(d) = date.as_deref() {
                    if d <= min_official_date_exclusive {
                        return Err(B1Error::validation(
                            "LEAK_CUTOFF",
                            format!("prospective extract included {gid} on {d}"),
                        ));
                    }
                } else {
                    return Err(B1Error::validation(
                        "NO_DATE",
                        format!("prospective game {gid} has no official_date"),
                    ));
                }
                entry.official_date = date;
                entry.game_pk = pk.clone();
                entry.game_status = status;
                let states = w6.load_states(gid)?;
                let transitions = w6.load_transitions(gid)?;
                let ident = pk.as_ref().and_then(|p| identity.get(p));
                let snap = extract_snapshot(&entry, &path, &states, &transitions, ident);
                if seen.insert(gid.clone(), snap.entry_timestamp).is_some() {
                    return Err(B1Error::validation(
                        "DUP_GAME",
                        format!("duplicate first-83 snapshot for {gid}"),
                    ));
                }
                snapshots.push(snap);
            }
            Err(_) => skipped_no_83 += 1,
        }
    }
    // Prospective-only rows are all post-cutoff. Do not refit TRAIN z on them.
    for snap in &mut snapshots {
        if snap.entry_trade_price_cents != 83 {
            return Err(B1Error::validation(
                "NOT_83",
                format!("extracted non-83 entry for {}", snap.game_id),
            ));
        }
        validate_snapshot(snap)?;
        store.insert_snapshot(snap)?;
    }
    store.checkpoint()?;
    let unique = snapshots.len();
    Ok(First83ExtractReport {
        universe: UNIVERSE,
        definition: "Prospective first exact 83¢ TRADE. Same definition as locked first83. Does not overwrite locked extract.",
        w7_games: game_ids.len(),
        w8_bound_games: w8_by_game.len(),
        snapshots_written: unique,
        unique_games: unique,
        skipped_no_83,
        skipped_bound_contract_no_83: skipped_bound,
        unbound_yes_or_earliest: unbound,
        features_sqlite: out_sqlite.display().to_string(),
        fill_status: "TRADE_PRINT_MODELED",
        feature_schema_version: FEATURE_SCHEMA_VERSION,
        engine_version: ENGINE_VERSION,
        notes: vec![
            "Does not overwrite B1/first83/features.sqlite.".into(),
            "TRAIN z / tertiles must be applied from the locked first83 extract.".into(),
        ],
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    use chrono::TimeZone;

    fn obs(ts: i64, mid: &str, side: &str, px: i32, id: &str) -> PathObservation {
        PathObservation {
            path_observation_id: id.into(),
            path_id: "p".into(),
            game_id: "g".into(),
            game_pk: "1".into(),
            market_id: mid.into(),
            ticker: "t".into(),
            contract_id: "c".into(),
            contract_side: side.into(),
            observation_id: id.into(),
            w5_synchronization_id: "w5".into(),
            observation_kind: "TRADE".into(),
            market_timestamp_utc: Some(Utc.timestamp_opt(ts, 0).unwrap()),
            matched_state_timestamp_utc: None,
            event_lag_ms: None,
            synchronization_status: "OK".into(),
            synchronization_quality: "OK".into(),
            join_status: momento_research_path::PathJoinStatus::Synchronized,
            timestamp_relation: "AT".into(),
            trade_price_cents: Some(px),
            trade_size_hundredths: None,
            source_observation_id: None,
            source_lineage: "test".into(),
            state_id: None,
            state_seq: None,
            previous_state_id: None,
            previous_state_seq: None,
            transition_id: None,
            transition_event_type: None,
            next_state_id: None,
            next_state_seq: None,
            inning: None,
            half: None,
            outs: None,
            score_home: None,
            score_away: None,
            run_differential: None,
            bases_bitmask: None,
            batter_id: None,
            pitcher_id: None,
            balls: None,
            strikes: None,
            game_status: None,
            chrono_index: 0,
            previous_trade_price_cents: None,
            price_change_cents: None,
            cumulative_trade_count: 0,
            time_since_previous_trade_ms: None,
            time_since_state_transition_ms: None,
            observed_high_cents_so_far: Some(px),
            observed_low_cents_so_far: Some(px),
            distance_from_high_cents: Some(0),
            distance_from_low_cents: Some(0),
            prior_price_changes: 0,
            causal_version: "t".into(),
            join_version: "t".into(),
            w5_dataset_version: "t".into(),
            w6_dataset_version: "t".into(),
            w7_version: "t".into(),
        }
    }

    #[test]
    fn first_83_is_earliest_on_bound_contract() {
        let path = vec![
            obs(10, "m", "LAD", 81, "a"),
            obs(20, "m", "LAD", 83, "b"),
            obs(15, "m", "SF", 83, "c"),
            obs(30, "m", "LAD", 83, "d"),
        ];
        let hit = pick_first_83(&path, Some(("m", "LAD"))).unwrap().unwrap();
        assert_eq!(hit.observation_id, "b");
    }

    #[test]
    fn unbound_takes_earliest_83() {
        let path = vec![obs(10, "m", "SF", 83, "n"), obs(20, "m", "LAD", 83, "y")];
        let hit = pick_first_83(&path, None).unwrap().unwrap();
        assert_eq!(hit.observation_id, "n");
    }
}
