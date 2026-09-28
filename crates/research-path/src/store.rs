//! SQLite store for EventMarketPath observations.

use chrono::{DateTime, Utc};
use rusqlite::{Connection, params};
use std::path::Path;

use crate::error::W7Error;
use crate::schema_sql::MIGRATION_001_SQL;
use crate::types::{
    EventMarketPath, GamePathCoverage, PathJoinStatus, PathObservation, StateSegment,
};
use crate::versions::{ARTIFACT_VERSION, JOIN_VERSION, MIGRATION_001};

/// Read-only W7 run provenance for W8+.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct PathRunMeta {
    pub run_id: String,
    pub dataset_version: String,
    pub artifact_version: String,
    pub w5_dataset_version: String,
    pub w6_dataset_version: String,
}

pub struct PathStore {
    conn: Connection,
    run_id: String,
}

impl PathStore {
    pub fn open(
        path: &Path,
        run_id: &str,
        generated_at: DateTime<Utc>,
        w5_ver: &str,
        w6_ver: &str,
    ) -> Result<Self, W7Error> {
        if let Some(parent) = path.parent() {
            std::fs::create_dir_all(parent)?;
        }
        let conn = Connection::open(path)?;
        conn.execute_batch(
            "PRAGMA foreign_keys = ON;
             PRAGMA journal_mode = WAL;
             PRAGMA synchronous = NORMAL;
             PRAGMA wal_autocheckpoint = 1000;
             PRAGMA cache_size = -65536;",
        )?;
        conn.execute_batch(MIGRATION_001_SQL)?;
        conn.execute(
            "INSERT OR IGNORE INTO schema_migrations(version, applied_at) VALUES (?1, ?2)",
            params![MIGRATION_001, generated_at.to_rfc3339()],
        )?;
        conn.execute(
            "INSERT OR REPLACE INTO path_runs(
                run_id, dataset_version, generated_at, artifact_version, w5_dataset_version,
                w6_dataset_version, join_version
             ) VALUES (?1,?2,?3,?4,?5,?6,?7)",
            params![
                run_id,
                crate::versions::DATASET_VERSION,
                generated_at.to_rfc3339(),
                ARTIFACT_VERSION,
                w5_ver,
                w6_ver,
                JOIN_VERSION
            ],
        )?;
        Ok(Self {
            conn,
            run_id: run_id.to_string(),
        })
    }

    pub fn checkpoint(&self) -> Result<(), W7Error> {
        self.conn
            .execute_batch("PRAGMA wal_checkpoint(TRUNCATE);")?;
        Ok(())
    }

    pub fn open_memory(run_id: &str, generated_at: DateTime<Utc>) -> Result<Self, W7Error> {
        let conn = Connection::open_in_memory()?;
        conn.execute_batch("PRAGMA foreign_keys = ON;")?;
        conn.execute_batch(MIGRATION_001_SQL)?;
        conn.execute(
            "INSERT INTO schema_migrations(version, applied_at) VALUES (?1, ?2)",
            params![MIGRATION_001, generated_at.to_rfc3339()],
        )?;
        conn.execute(
            "INSERT INTO path_runs(
                run_id, dataset_version, generated_at, artifact_version, w5_dataset_version,
                w6_dataset_version, join_version
             ) VALUES (?1,?2,?3,?4,'w5','w6',?5)",
            params![
                run_id,
                crate::versions::DATASET_VERSION,
                generated_at.to_rfc3339(),
                ARTIFACT_VERSION,
                JOIN_VERSION
            ],
        )?;
        Ok(Self {
            conn,
            run_id: run_id.to_string(),
        })
    }

    pub fn open_existing(path: &Path) -> Result<Self, W7Error> {
        if !path.exists() {
            return Err(W7Error::Uncommitted(path.display().to_string()));
        }
        let conn = Connection::open(path)?;
        conn.execute_batch("PRAGMA query_only = ON;")?;
        let run_id: String = conn.query_row(
            "SELECT run_id FROM path_runs ORDER BY generated_at DESC LIMIT 1",
            [],
            |r| r.get(0),
        )?;
        Ok(Self { conn, run_id })
    }

    pub fn run_id(&self) -> &str {
        &self.run_id
    }

    pub fn run_meta(&self) -> Result<PathRunMeta, W7Error> {
        self.conn
            .query_row(
                "SELECT dataset_version, artifact_version, w5_dataset_version, w6_dataset_version
             FROM path_runs WHERE run_id = ?1",
                params![self.run_id],
                |r| {
                    Ok(PathRunMeta {
                        run_id: self.run_id.clone(),
                        dataset_version: r.get(0)?,
                        artifact_version: r.get(1)?,
                        w5_dataset_version: r.get(2)?,
                        w6_dataset_version: r.get(3)?,
                    })
                },
            )
            .map_err(W7Error::from)
    }

    pub fn list_game_ids(&self) -> Result<Vec<String>, W7Error> {
        let mut stmt = self
            .conn
            .prepare("SELECT game_id FROM game_path_coverage WHERE run_id = ?1 ORDER BY game_id")?;
        let rows = stmt.query_map(params![self.run_id], |r| r.get::<_, String>(0))?;
        let mut out = Vec::new();
        for row in rows {
            out.push(row?);
        }
        Ok(out)
    }

    pub fn observation_count(&self) -> Result<i64, W7Error> {
        Ok(self.conn.query_row(
            "SELECT COUNT(*) FROM path_observations WHERE run_id = ?1",
            params![self.run_id],
            |r| r.get(0),
        )?)
    }

    pub fn insert_path(
        &mut self,
        path: &EventMarketPath,
        segments: &[StateSegment],
    ) -> Result<(), W7Error> {
        let synced = path
            .observations
            .iter()
            .filter(|o| o.join_status.has_applicable_state() && o.state_id.is_some())
            .count();
        let tx = self.conn.transaction()?;
        tx.execute(
            "INSERT OR REPLACE INTO event_market_paths(
                path_id, run_id, game_id, game_pk, market_id, contract_side, observations, synchronized
             ) VALUES (?1,?2,?3,?4,?5,?6,?7,?8)",
            params![
                path.path_id,
                self.run_id,
                path.game_id,
                path.game_pk,
                path.market_id,
                path.contract_side,
                path.observations.len() as i64,
                synced as i64
            ],
        )?;
        {
            let mut stmt = tx.prepare(
                "INSERT OR REPLACE INTO path_observations(
                    path_observation_id, run_id, path_id, game_id, game_pk, market_id, ticker,
                    contract_id, contract_side, observation_id, w5_synchronization_id, observation_kind,
                    market_timestamp_utc, matched_state_timestamp_utc, event_lag_ms,
                    synchronization_status, synchronization_quality, join_status, timestamp_relation,
                    trade_price_cents, trade_size_hundredths, source_observation_id, source_lineage,
                    state_id, state_seq, previous_state_id, previous_state_seq, transition_id,
                    transition_event_type, next_state_id, next_state_seq, inning, half, outs,
                    score_home, score_away, run_differential, bases_bitmask, batter_id, pitcher_id,
                    balls, strikes, game_status, chrono_index, previous_trade_price_cents,
                    price_change_cents, cumulative_trade_count, time_since_previous_trade_ms,
                    time_since_state_transition_ms, observed_high_cents_so_far, observed_low_cents_so_far,
                    distance_from_high_cents, distance_from_low_cents, prior_price_changes,
                    join_version, w5_dataset_version, w6_dataset_version, w7_version
                 ) VALUES (
                    ?1,?2,?3,?4,?5,?6,?7,?8,?9,?10,?11,?12,?13,?14,?15,?16,?17,?18,?19,?20,
                    ?21,?22,?23,?24,?25,?26,?27,?28,?29,?30,?31,?32,?33,?34,?35,?36,?37,?38,
                    ?39,?40,?41,?42,?43,?44,?45,?46,?47,?48,?49,?50,?51,?52,?53,?54,?55,?56,?57,?58
                 )",
            )?;
            for r in &path.observations {
                stmt.execute(params![
                    r.path_observation_id,
                    self.run_id,
                    r.path_id,
                    r.game_id,
                    r.game_pk,
                    r.market_id,
                    r.ticker,
                    r.contract_id,
                    r.contract_side,
                    r.observation_id,
                    r.w5_synchronization_id,
                    r.observation_kind,
                    r.market_timestamp_utc.map(|t| t.to_rfc3339()),
                    r.matched_state_timestamp_utc.map(|t| t.to_rfc3339()),
                    r.event_lag_ms,
                    r.synchronization_status,
                    r.synchronization_quality,
                    r.join_status.as_str(),
                    r.timestamp_relation,
                    r.trade_price_cents,
                    r.trade_size_hundredths,
                    r.source_observation_id,
                    r.source_lineage,
                    r.state_id,
                    r.state_seq.map(i64::from),
                    r.previous_state_id,
                    r.previous_state_seq.map(i64::from),
                    r.transition_id,
                    r.transition_event_type,
                    r.next_state_id,
                    r.next_state_seq.map(i64::from),
                    r.inning.map(i64::from),
                    r.half,
                    r.outs.map(i64::from),
                    r.score_home.map(i64::from),
                    r.score_away.map(i64::from),
                    r.run_differential,
                    r.bases_bitmask.map(i64::from),
                    r.batter_id,
                    r.pitcher_id,
                    r.balls.map(i64::from),
                    r.strikes.map(i64::from),
                    r.game_status,
                    r.chrono_index as i64,
                    r.previous_trade_price_cents,
                    r.price_change_cents,
                    r.cumulative_trade_count as i64,
                    r.time_since_previous_trade_ms,
                    r.time_since_state_transition_ms,
                    r.observed_high_cents_so_far,
                    r.observed_low_cents_so_far,
                    r.distance_from_high_cents,
                    r.distance_from_low_cents,
                    r.prior_price_changes as i64,
                    r.join_version,
                    r.w5_dataset_version,
                    r.w6_dataset_version,
                    r.w7_version,
                ])?;
            }
        }
        {
            let mut stmt = tx.prepare(
                "INSERT OR REPLACE INTO state_segments(
                    run_id, path_id, game_id, market_id, contract_side, state_id, state_seq,
                    observation_count, first_market_timestamp_utc, last_market_timestamp_utc
                 ) VALUES (?1,?2,?3,?4,?5,?6,?7,?8,?9,?10)",
            )?;
            for s in segments {
                stmt.execute(params![
                    self.run_id,
                    s.path_id,
                    s.game_id,
                    s.market_id,
                    s.contract_side,
                    s.state_id,
                    s.state_seq as i64,
                    s.observation_count as i64,
                    s.first_market_timestamp_utc.map(|t| t.to_rfc3339()),
                    s.last_market_timestamp_utc.map(|t| t.to_rfc3339()),
                ])?;
            }
        }
        tx.commit()?;
        Ok(())
    }

    pub fn insert_game_coverage(&mut self, cov: &GamePathCoverage) -> Result<(), W7Error> {
        self.conn.execute(
            "INSERT OR REPLACE INTO game_path_coverage(
                run_id, game_id, game_pk, observations, synchronized, before_first, after_last,
                at_event, with_gap, no_game_state, coverage
             ) VALUES (?1,?2,?3,?4,?5,?6,?7,?8,?9,?10,?11)",
            params![
                self.run_id,
                cov.game_id,
                cov.game_pk,
                cov.observations as i64,
                cov.synchronized as i64,
                cov.before_first as i64,
                cov.after_last as i64,
                cov.at_event as i64,
                cov.with_gap as i64,
                cov.no_game_state as i64,
                cov.coverage
            ],
        )?;
        Ok(())
    }

    pub fn path_for_game(&self, game_id: &str) -> Result<Vec<PathObservation>, W7Error> {
        self.query(
            "SELECT * FROM path_observations WHERE run_id = ?1 AND game_id = ?2
             ORDER BY market_timestamp_utc, observation_id",
            params![self.run_id, game_id],
        )
    }

    pub fn path_for_market(&self, market_id: &str) -> Result<Vec<PathObservation>, W7Error> {
        self.query(
            "SELECT * FROM path_observations WHERE run_id = ?1 AND market_id = ?2
             ORDER BY contract_side, market_timestamp_utc, observation_id",
            params![self.run_id, market_id],
        )
    }

    pub fn path_for_contract(
        &self,
        market_id: &str,
        side: &str,
    ) -> Result<Vec<PathObservation>, W7Error> {
        self.query(
            "SELECT * FROM path_observations WHERE run_id = ?1 AND market_id = ?2 AND contract_side = ?3
             ORDER BY market_timestamp_utc, observation_id",
            params![self.run_id, market_id, side],
        )
    }

    pub fn observations_at_state(
        &self,
        game_id: &str,
        state_id: &str,
    ) -> Result<Vec<PathObservation>, W7Error> {
        self.query(
            "SELECT * FROM path_observations WHERE run_id = ?1 AND game_id = ?2 AND state_id = ?3
             ORDER BY market_timestamp_utc, observation_id",
            params![self.run_id, game_id, state_id],
        )
    }

    pub fn observations_in_state_seq_range(
        &self,
        game_id: &str,
        start_seq: u32,
        end_seq: u32,
    ) -> Result<Vec<PathObservation>, W7Error> {
        self.query(
            "SELECT * FROM path_observations WHERE run_id = ?1 AND game_id = ?2
               AND state_seq IS NOT NULL AND state_seq >= ?3 AND state_seq <= ?4
             ORDER BY state_seq, market_timestamp_utc, observation_id",
            params![self.run_id, game_id, start_seq as i64, end_seq as i64],
        )
    }

    pub fn observations_at_or_before(
        &self,
        game_id: &str,
        t: DateTime<Utc>,
    ) -> Result<Vec<PathObservation>, W7Error> {
        self.query(
            "SELECT * FROM path_observations WHERE run_id = ?1 AND game_id = ?2
               AND market_timestamp_utc IS NOT NULL AND market_timestamp_utc <= ?3
             ORDER BY market_timestamp_utc, observation_id",
            params![self.run_id, game_id, t.to_rfc3339()],
        )
    }

    pub fn state_at_market_observation(
        &self,
        observation_id: &str,
    ) -> Result<Option<PathObservation>, W7Error> {
        let mut rows = self.query(
            "SELECT * FROM path_observations WHERE run_id = ?1 AND observation_id = ?2 LIMIT 1",
            params![self.run_id, observation_id],
        )?;
        Ok(rows.pop())
    }

    pub fn market_observations_before(
        &self,
        observation_id: &str,
    ) -> Result<Vec<PathObservation>, W7Error> {
        let Some(cur) = self.state_at_market_observation(observation_id)? else {
            return Ok(Vec::new());
        };
        let Some(t) = cur.market_timestamp_utc else {
            return Ok(Vec::new());
        };
        self.query(
            "SELECT * FROM path_observations WHERE run_id = ?1 AND path_id = ?2
               AND market_timestamp_utc IS NOT NULL
               AND (market_timestamp_utc < ?3 OR (market_timestamp_utc = ?3 AND observation_id < ?4))
             ORDER BY market_timestamp_utc, observation_id",
            params![self.run_id, cur.path_id, t.to_rfc3339(), observation_id],
        )
    }

    pub fn market_observations_after(
        &self,
        observation_id: &str,
    ) -> Result<Vec<PathObservation>, W7Error> {
        let Some(cur) = self.state_at_market_observation(observation_id)? else {
            return Ok(Vec::new());
        };
        let Some(t) = cur.market_timestamp_utc else {
            return Ok(Vec::new());
        };
        self.query(
            "SELECT * FROM path_observations WHERE run_id = ?1 AND path_id = ?2
               AND market_timestamp_utc IS NOT NULL
               AND (market_timestamp_utc > ?3 OR (market_timestamp_utc = ?3 AND observation_id > ?4))
             ORDER BY market_timestamp_utc, observation_id",
            params![self.run_id, cur.path_id, t.to_rfc3339(), observation_id],
        )
    }

    pub fn observations_where_price_equals(
        &self,
        cents: i32,
    ) -> Result<Vec<PathObservation>, W7Error> {
        self.query(
            "SELECT * FROM path_observations WHERE run_id = ?1 AND trade_price_cents = ?2
             ORDER BY game_id, market_timestamp_utc, observation_id",
            params![self.run_id, cents],
        )
    }

    /// Fail closed if any applicable state is in the future of its market timestamp,
    /// or if BEFORE_FIRST / AFTER_LAST rows carried an applicable W6 state.
    pub fn validate_anti_lookahead(&self) -> Result<(), W7Error> {
        let future: i64 = self.conn.query_row(
            "SELECT COUNT(*) FROM path_observations
             WHERE run_id = ?1
               AND matched_state_timestamp_utc IS NOT NULL
               AND market_timestamp_utc IS NOT NULL
               AND matched_state_timestamp_utc > market_timestamp_utc",
            params![self.run_id],
            |r| r.get(0),
        )?;
        if future != 0 {
            return Err(W7Error::validation(
                "FUTURE_STATE",
                format!("{future} observations have matched_state_timestamp > market_timestamp"),
            ));
        }
        let leaked: i64 = self.conn.query_row(
            "SELECT COUNT(*) FROM path_observations
             WHERE run_id = ?1
               AND join_status IN ('BEFORE_FIRST_EVENT', 'AFTER_LAST_EVENT')
               AND state_id IS NOT NULL",
            params![self.run_id],
            |r| r.get(0),
        )?;
        if leaked != 0 {
            return Err(W7Error::validation(
                "INAPPLICABLE_STATE",
                format!("{leaked} BEFORE_FIRST/AFTER_LAST rows have an applicable state_id"),
            ));
        }
        let missing: i64 = self.conn.query_row(
            "SELECT COUNT(*) FROM path_observations
             WHERE run_id = ?1
               AND join_status IN ('SYNCHRONIZED', 'AT_EVENT', 'SYNCHRONIZED_WITH_TIMESTAMP_GAP')
               AND state_id IS NULL",
            params![self.run_id],
            |r| r.get(0),
        )?;
        if missing != 0 {
            return Err(W7Error::validation(
                "MISSING_APPLICABLE_STATE",
                format!("{missing} success-class rows have no W6 state_id"),
            ));
        }
        Ok(())
    }

    pub fn count_join_status(&self) -> Result<Vec<(String, i64)>, W7Error> {
        let mut stmt = self.conn.prepare(
            "SELECT join_status, COUNT(*) FROM path_observations WHERE run_id = ?1
             GROUP BY join_status ORDER BY join_status",
        )?;
        let rows = stmt.query_map(params![self.run_id], |r| {
            Ok((r.get::<_, String>(0)?, r.get::<_, i64>(1)?))
        })?;
        let mut out = Vec::new();
        for row in rows {
            out.push(row?);
        }
        Ok(out)
    }

    fn query(
        &self,
        sql: &str,
        params: impl rusqlite::Params,
    ) -> Result<Vec<PathObservation>, W7Error> {
        let mut stmt = self.conn.prepare(sql)?;
        let rows = stmt.query_map(params, row_from_sqlite)?;
        let mut out = Vec::new();
        for r in rows {
            out.push(r?);
        }
        Ok(out)
    }
}

fn row_from_sqlite(row: &rusqlite::Row<'_>) -> rusqlite::Result<PathObservation> {
    Ok(PathObservation {
        path_observation_id: row.get("path_observation_id")?,
        path_id: row.get("path_id")?,
        game_id: row.get("game_id")?,
        game_pk: row.get("game_pk")?,
        market_id: row.get("market_id")?,
        ticker: row.get("ticker")?,
        contract_id: row.get("contract_id")?,
        contract_side: row.get("contract_side")?,
        observation_id: row.get("observation_id")?,
        w5_synchronization_id: row.get("w5_synchronization_id")?,
        observation_kind: row.get("observation_kind")?,
        market_timestamp_utc: parse_ts(row, "market_timestamp_utc")?,
        matched_state_timestamp_utc: parse_ts(row, "matched_state_timestamp_utc")?,
        event_lag_ms: row.get("event_lag_ms")?,
        synchronization_status: row.get("synchronization_status")?,
        synchronization_quality: row.get("synchronization_quality")?,
        join_status: parse_join(&row.get::<_, String>("join_status")?),
        timestamp_relation: row.get("timestamp_relation")?,
        trade_price_cents: row.get("trade_price_cents")?,
        trade_size_hundredths: row.get("trade_size_hundredths")?,
        source_observation_id: row.get("source_observation_id")?,
        source_lineage: row.get("source_lineage")?,
        state_id: row.get("state_id")?,
        state_seq: opt_u32(row, "state_seq")?,
        previous_state_id: row.get("previous_state_id")?,
        previous_state_seq: opt_u32(row, "previous_state_seq")?,
        transition_id: row.get("transition_id")?,
        transition_event_type: row.get("transition_event_type")?,
        next_state_id: row.get("next_state_id")?,
        next_state_seq: opt_u32(row, "next_state_seq")?,
        inning: opt_u8(row, "inning")?,
        half: row.get("half")?,
        outs: opt_u8(row, "outs")?,
        score_home: opt_u16(row, "score_home")?,
        score_away: opt_u16(row, "score_away")?,
        run_differential: row.get("run_differential")?,
        bases_bitmask: opt_u8(row, "bases_bitmask")?,
        batter_id: row.get("batter_id")?,
        pitcher_id: row.get("pitcher_id")?,
        balls: opt_u8(row, "balls")?,
        strikes: opt_u8(row, "strikes")?,
        game_status: row.get("game_status")?,
        chrono_index: row.get::<_, i64>("chrono_index")? as u32,
        previous_trade_price_cents: row.get("previous_trade_price_cents")?,
        price_change_cents: row.get("price_change_cents")?,
        cumulative_trade_count: row.get::<_, i64>("cumulative_trade_count")? as u32,
        time_since_previous_trade_ms: row.get("time_since_previous_trade_ms")?,
        time_since_state_transition_ms: row.get("time_since_state_transition_ms")?,
        observed_high_cents_so_far: row.get("observed_high_cents_so_far")?,
        observed_low_cents_so_far: row.get("observed_low_cents_so_far")?,
        distance_from_high_cents: row.get("distance_from_high_cents")?,
        distance_from_low_cents: row.get("distance_from_low_cents")?,
        prior_price_changes: row.get::<_, i64>("prior_price_changes")? as u32,
        causal_version: crate::versions::CAUSAL_VERSION.to_string(),
        join_version: row.get("join_version")?,
        w5_dataset_version: row.get("w5_dataset_version")?,
        w6_dataset_version: row.get("w6_dataset_version")?,
        w7_version: row.get("w7_version")?,
    })
}

fn parse_ts(row: &rusqlite::Row<'_>, col: &str) -> rusqlite::Result<Option<DateTime<Utc>>> {
    let s: Option<String> = row.get(col)?;
    Ok(s.and_then(|x| DateTime::parse_from_rfc3339(&x).ok())
        .map(|d| d.with_timezone(&Utc)))
}

fn opt_u32(row: &rusqlite::Row<'_>, col: &str) -> rusqlite::Result<Option<u32>> {
    Ok(row.get::<_, Option<i64>>(col)?.map(|v| v as u32))
}

fn opt_u8(row: &rusqlite::Row<'_>, col: &str) -> rusqlite::Result<Option<u8>> {
    Ok(row.get::<_, Option<i64>>(col)?.map(|v| v as u8))
}

fn opt_u16(row: &rusqlite::Row<'_>, col: &str) -> rusqlite::Result<Option<u16>> {
    Ok(row.get::<_, Option<i64>>(col)?.map(|v| v as u16))
}

fn parse_join(s: &str) -> PathJoinStatus {
    match s {
        "SYNCHRONIZED" => PathJoinStatus::Synchronized,
        "AT_EVENT" => PathJoinStatus::AtEvent,
        "SYNCHRONIZED_WITH_TIMESTAMP_GAP" => PathJoinStatus::SynchronizedWithTimestampGap,
        "BEFORE_FIRST_EVENT" => PathJoinStatus::BeforeFirstEvent,
        "AFTER_LAST_EVENT" => PathJoinStatus::AfterLastEvent,
        "NO_GAME_STATE" => PathJoinStatus::NoGameState,
        "UNSYNCHRONIZABLE" => PathJoinStatus::Unsynchronizable,
        "UNJOINABLE" => PathJoinStatus::Unjoinable,
        "VALIDATION_FAILURE" => PathJoinStatus::ValidationFailure,
        _ => PathJoinStatus::Rejected,
    }
}
