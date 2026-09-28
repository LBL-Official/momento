//! SQLite store for canonical states and transitions.

use chrono::{DateTime, Utc};
use rusqlite::{Connection, OptionalExtension, params};
use std::path::Path;

use crate::error::W6Error;
use crate::fingerprint::{event_type_token, half_token, status_token};
use crate::schema_sql::MIGRATION_001_SQL;
use crate::types::ReconstructedGame;
use crate::versions::{ARTIFACT_VERSION, MIGRATION_001, RECONSTRUCTION_VERSION, SCHEMA_VERSION};

pub struct StateStore {
    conn: Connection,
    run_id: String,
}

impl StateStore {
    pub fn open(path: &Path, run_id: &str, generated_at: DateTime<Utc>) -> Result<Self, W6Error> {
        if let Some(parent) = path.parent() {
            std::fs::create_dir_all(parent)?;
        }
        let conn = Connection::open(path)?;
        conn.execute_batch(
            "PRAGMA foreign_keys = ON;
             PRAGMA journal_mode = WAL;
             PRAGMA synchronous = NORMAL;
             PRAGMA wal_autocheckpoint = 0;
             PRAGMA cache_size = -65536;",
        )?;
        conn.execute_batch(MIGRATION_001_SQL)?;
        Self::init_run(conn, run_id, generated_at)
    }

    pub fn open_memory(run_id: &str, generated_at: DateTime<Utc>) -> Result<Self, W6Error> {
        let conn = Connection::open_in_memory()?;
        conn.execute_batch("PRAGMA foreign_keys = ON;")?;
        conn.execute_batch(MIGRATION_001_SQL)?;
        Self::init_run(conn, run_id, generated_at)
    }

    fn init_run(
        conn: Connection,
        run_id: &str,
        generated_at: DateTime<Utc>,
    ) -> Result<Self, W6Error> {
        conn.execute(
            "INSERT OR IGNORE INTO schema_migrations(version, applied_at) VALUES (?1, ?2)",
            params![MIGRATION_001, generated_at.to_rfc3339()],
        )?;
        conn.execute(
            "INSERT OR REPLACE INTO reconstruction_runs(
                run_id, dataset_version, generated_at, artifact_version, schema_version, reconstruction_version
             ) VALUES (?1, ?2, ?3, ?4, ?5, ?6)",
            params![
                run_id,
                crate::versions::DATASET_VERSION,
                generated_at.to_rfc3339(),
                ARTIFACT_VERSION,
                SCHEMA_VERSION,
                RECONSTRUCTION_VERSION
            ],
        )?;
        Ok(Self {
            conn,
            run_id: run_id.to_string(),
        })
    }

    pub fn checkpoint(&self) -> Result<(), W6Error> {
        self.conn
            .execute_batch("PRAGMA wal_checkpoint(TRUNCATE);")?;
        Ok(())
    }

    pub fn insert_game(
        &mut self,
        game: &ReconstructedGame,
        status: &str,
        error: Option<&str>,
    ) -> Result<(), W6Error> {
        let tx = self.conn.transaction()?;
        tx.execute(
            "INSERT OR REPLACE INTO games(
                run_id, game_id, game_pk, official_date, events, states, transitions, timed_events,
                extra_inning, walk_off, terminal, status, error
             ) VALUES (?1,?2,?3,?4,?5,?6,?7,?8,?9,?10,?11,?12,?13)",
            params![
                self.run_id,
                game.game_id,
                game.game_pk,
                game.official_date.map(|d| d.to_string()),
                game.events_total as i64,
                game.states.len() as i64,
                game.transitions.len() as i64,
                game.timed_events as i64,
                i64::from(game.extra_inning),
                i64::from(game.walk_off),
                i64::from(game.terminal),
                status,
                error,
            ],
        )?;
        {
            let mut stmt = tx.prepare(
                "INSERT OR REPLACE INTO game_states(
                    state_id, run_id, game_id, game_pk, fingerprint, state_seq, event_id, event_sequence,
                    source_event_id, canonical_timestamp, source_timestamp, inning, half, outs,
                    score_home, score_away, run_differential, bases_bitmask, batter_id, pitcher_id,
                    balls, strikes, pa_seq, pa_phase, event_type, event_kind, extra_inning, walk_off,
                    game_status, source_dataset, source_version, reconstruction_version
                 ) VALUES (
                    ?1,?2,?3,?4,?5,?6,?7,?8,?9,?10,?11,?12,?13,?14,?15,?16,?17,?18,?19,?20,
                    ?21,?22,?23,?24,?25,?26,?27,?28,?29,?30,?31,?32
                 )",
            )?;
            for s in &game.states {
                stmt.execute(params![
                    s.state_id,
                    self.run_id,
                    s.game_id,
                    s.game_pk,
                    s.fingerprint,
                    s.state_seq as i64,
                    s.event_id,
                    s.event_sequence as i64,
                    s.source_event_id.as_value().cloned(),
                    s.canonical_timestamp.as_value().map(|t| t.to_rfc3339()),
                    s.source_timestamp.as_value().map(|t| t.to_rfc3339()),
                    s.inning as i64,
                    half_token(s.half),
                    s.outs as i64,
                    s.score_home as i64,
                    s.score_away as i64,
                    s.run_differential,
                    s.bases_bitmask as i64,
                    s.batter_id.as_value().cloned(),
                    s.pitcher_id.as_value().cloned(),
                    s.balls.as_value().map(|v| i64::from(*v)),
                    s.strikes.as_value().map(|v| i64::from(*v)),
                    s.pa_seq.as_value().map(|v| i64::from(*v)),
                    s.pa_phase.as_str(),
                    s.event_type.map(event_type_token),
                    s.event_kind.as_str(),
                    i64::from(s.extra_inning),
                    i64::from(s.walk_off),
                    status_token(s.game_status),
                    s.source_dataset,
                    s.source_version,
                    s.reconstruction_version,
                ])?;
            }
        }
        {
            let mut stmt = tx.prepare(
                "INSERT OR REPLACE INTO state_transitions(
                    transition_id, run_id, game_id, fingerprint, sequence, event_id, source_event_id,
                    previous_state_id, resulting_state_id, event_timestamp, event_type, event_kind,
                    score_delta_home, score_delta_away, out_delta, bases_before, bases_after,
                    batter_changed, pitcher_changed, inning_changed, half_changed, substitution,
                    review, amendment, delay, walk_off, reconstruction_version
                 ) VALUES (
                    ?1,?2,?3,?4,?5,?6,?7,?8,?9,?10,?11,?12,?13,?14,?15,?16,?17,?18,?19,?20,
                    ?21,?22,?23,?24,?25,?26,?27
                 )",
            )?;
            for t in &game.transitions {
                stmt.execute(params![
                    t.transition_id,
                    self.run_id,
                    t.game_id,
                    t.fingerprint,
                    t.sequence as i64,
                    t.event_id,
                    t.source_event_id,
                    t.previous_state_id,
                    t.resulting_state_id,
                    t.event_timestamp.as_value().map(|x| x.to_rfc3339()),
                    event_type_token(t.event_type),
                    t.event_kind.as_str(),
                    t.score_delta_home,
                    t.score_delta_away,
                    t.out_delta,
                    t.bases_before as i64,
                    t.bases_after as i64,
                    i64::from(t.batter_changed),
                    i64::from(t.pitcher_changed),
                    i64::from(t.inning_changed),
                    i64::from(t.half_changed),
                    i64::from(t.substitution),
                    i64::from(t.review),
                    i64::from(t.amendment),
                    i64::from(t.delay),
                    i64::from(t.walk_off),
                    t.reconstruction_version,
                ])?;
            }
        }
        tx.commit()?;
        Ok(())
    }

    pub fn insert_failure(
        &mut self,
        game_id: &str,
        game_pk: &str,
        error: &str,
    ) -> Result<(), W6Error> {
        self.conn.execute(
            "INSERT OR REPLACE INTO games(
                run_id, game_id, game_pk, official_date, events, states, transitions, timed_events,
                extra_inning, walk_off, terminal, status, error
             ) VALUES (?1,?2,?3,NULL,0,0,0,0,0,0,0,'FAILED',?4)",
            params![self.run_id, game_id, game_pk, error],
        )?;
        Ok(())
    }

    pub fn game_exists(&self, game_id: &str) -> Result<bool, W6Error> {
        let n: i64 = self.conn.query_row(
            "SELECT COUNT(*) FROM games WHERE run_id = ?1 AND game_id = ?2",
            params![self.run_id, game_id],
            |r| r.get(0),
        )?;
        Ok(n > 0)
    }

    pub fn state_id_at_or_before(
        &self,
        game_id: &str,
        t: DateTime<Utc>,
    ) -> Result<Option<String>, W6Error> {
        let ts = t.to_rfc3339();
        let id: Option<String> = self
            .conn
            .query_row(
                "SELECT state_id FROM game_states
                 WHERE run_id = ?1 AND game_id = ?2 AND canonical_timestamp IS NOT NULL
                   AND canonical_timestamp <= ?3
                 ORDER BY canonical_timestamp DESC, event_sequence DESC
                 LIMIT 1",
                params![self.run_id, game_id, ts],
                |r| r.get(0),
            )
            .optional()?;
        Ok(id)
    }

    /// Read an existing W6 artifact. Does not write a new run.
    pub fn open_existing(path: &Path) -> Result<Self, W6Error> {
        if !path.exists() {
            return Err(W6Error::Uncommitted(format!(
                "W6 sqlite missing: {}",
                path.display()
            )));
        }
        let conn = Connection::open(path)?;
        conn.execute_batch("PRAGMA query_only = ON;")?;
        let run_id: String = conn
            .query_row(
                "SELECT run_id FROM reconstruction_runs ORDER BY generated_at DESC LIMIT 1",
                [],
                |r| r.get(0),
            )
            .map_err(|_| {
                W6Error::Uncommitted(format!(
                    "W6 sqlite has no reconstruction_runs: {}",
                    path.display()
                ))
            })?;
        Ok(Self { conn, run_id })
    }

    pub fn run_id(&self) -> &str {
        &self.run_id
    }

    pub fn dataset_version(&self) -> Result<String, W6Error> {
        Ok(self.conn.query_row(
            "SELECT dataset_version FROM reconstruction_runs WHERE run_id = ?1",
            params![self.run_id],
            |r| r.get(0),
        )?)
    }

    pub fn reconstruction_version(&self) -> Result<String, W6Error> {
        Ok(self.conn.query_row(
            "SELECT reconstruction_version FROM reconstruction_runs WHERE run_id = ?1",
            params![self.run_id],
            |r| r.get(0),
        )?)
    }

    pub fn list_ok_game_ids(&self) -> Result<Vec<String>, W6Error> {
        let mut stmt = self.conn.prepare(
            "SELECT game_id FROM games WHERE run_id = ?1 AND status = 'OK' ORDER BY game_id",
        )?;
        let rows = stmt.query_map(params![self.run_id], |r| r.get::<_, String>(0))?;
        let mut out = Vec::new();
        for row in rows {
            out.push(row?);
        }
        Ok(out)
    }

    pub fn load_states(&self, game_id: &str) -> Result<Vec<StoredState>, W6Error> {
        let mut stmt = self.conn.prepare(
            "SELECT state_id, game_id, game_pk, state_seq, event_id, event_sequence,
                    canonical_timestamp, inning, half, outs, score_home, score_away,
                    run_differential, bases_bitmask, batter_id, pitcher_id, balls, strikes,
                    game_status, extra_inning, event_type
             FROM game_states
             WHERE run_id = ?1 AND game_id = ?2
             ORDER BY state_seq",
        )?;
        let rows = stmt.query_map(params![self.run_id, game_id], |r| {
            Ok(StoredState {
                state_id: r.get(0)?,
                game_id: r.get(1)?,
                game_pk: r.get(2)?,
                state_seq: r.get::<_, i64>(3)? as u32,
                event_id: r.get(4)?,
                event_sequence: r.get::<_, i64>(5)? as u32,
                canonical_timestamp: parse_ts(r.get(6)?),
                inning: r.get::<_, i64>(7)? as u8,
                half: r.get(8)?,
                outs: r.get::<_, i64>(9)? as u8,
                score_home: r.get::<_, i64>(10)? as u16,
                score_away: r.get::<_, i64>(11)? as u16,
                run_differential: r.get(12)?,
                bases_bitmask: r.get::<_, i64>(13)? as u8,
                batter_id: r.get(14)?,
                pitcher_id: r.get(15)?,
                balls: r.get::<_, Option<i64>>(16)?.map(|v| v as u8),
                strikes: r.get::<_, Option<i64>>(17)?.map(|v| v as u8),
                game_status: r.get(18)?,
                extra_inning: r.get::<_, i64>(19)? != 0,
                event_type: r.get(20)?,
            })
        })?;
        let mut out = Vec::new();
        for row in rows {
            out.push(row?);
        }
        Ok(out)
    }

    pub fn load_transitions(&self, game_id: &str) -> Result<Vec<StoredTransition>, W6Error> {
        let mut stmt = self.conn.prepare(
            "SELECT transition_id, sequence, event_id, previous_state_id, resulting_state_id,
                    event_timestamp, event_type
             FROM state_transitions
             WHERE run_id = ?1 AND game_id = ?2
             ORDER BY sequence",
        )?;
        let rows = stmt.query_map(params![self.run_id, game_id], |r| {
            Ok(StoredTransition {
                transition_id: r.get(0)?,
                sequence: r.get::<_, i64>(1)? as u32,
                event_id: r.get(2)?,
                previous_state_id: r.get(3)?,
                resulting_state_id: r.get(4)?,
                event_timestamp: parse_ts(r.get(5)?),
                event_type: r.get(6)?,
            })
        })?;
        let mut out = Vec::new();
        for row in rows {
            out.push(row?);
        }
        Ok(out)
    }
}

fn parse_ts(raw: Option<String>) -> Option<DateTime<Utc>> {
    raw.and_then(|s| DateTime::parse_from_rfc3339(&s).ok())
        .map(|d| d.with_timezone(&Utc))
}

/// Compact W6 state row for W7 join. Not a second game-state authority.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct StoredState {
    pub state_id: String,
    pub game_id: String,
    pub game_pk: String,
    pub state_seq: u32,
    pub event_id: Option<String>,
    pub event_sequence: u32,
    pub canonical_timestamp: Option<DateTime<Utc>>,
    pub inning: u8,
    pub half: String,
    pub outs: u8,
    pub score_home: u16,
    pub score_away: u16,
    pub run_differential: i32,
    pub bases_bitmask: u8,
    pub batter_id: Option<String>,
    pub pitcher_id: Option<String>,
    pub balls: Option<u8>,
    pub strikes: Option<u8>,
    pub game_status: String,
    pub extra_inning: bool,
    pub event_type: Option<String>,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct StoredTransition {
    pub transition_id: String,
    pub sequence: u32,
    pub event_id: String,
    pub previous_state_id: String,
    pub resulting_state_id: String,
    pub event_timestamp: Option<DateTime<Utc>>,
    pub event_type: String,
}
