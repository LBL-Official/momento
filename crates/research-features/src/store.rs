//! B1 feature store. Append-only research artifact.

use std::path::Path;

use chrono::{DateTime, Utc};
use rusqlite::{Connection, OptionalExtension, params};

use crate::error::B1Error;
use crate::schema_sql::MIGRATION_001_SQL;
use crate::types::B1EntrySnapshot;
use crate::versions::{
    ARTIFACT_VERSION, DATASET_VERSION, ENGINE_VERSION, FEATURE_SCHEMA_VERSION, MIGRATION_001,
    OBSERVABILITY, ORDERING_CONTRACT, SCHEMA_VERSION,
};

pub struct FeatureStore {
    conn: Connection,
    run_id: String,
}

impl FeatureStore {
    pub fn open(
        path: &Path,
        run_id: &str,
        generated_at: DateTime<Utc>,
        w6_run_id: &str,
        w7_run_id: &str,
        w8_run_id: &str,
        w5_dataset_version: Option<&str>,
    ) -> Result<Self, B1Error> {
        let conn = Connection::open(path)?;
        conn.execute_batch(
            "PRAGMA journal_mode = WAL;
             PRAGMA synchronous = NORMAL;
             PRAGMA wal_autocheckpoint = 1000;",
        )?;
        conn.execute_batch(MIGRATION_001_SQL)?;
        conn.execute(
            "INSERT OR IGNORE INTO schema_migrations(version, applied_at) VALUES (?1, ?2)",
            params![MIGRATION_001, generated_at.to_rfc3339()],
        )?;
        conn.execute(
            "INSERT INTO feature_runs(
                run_id, dataset_version, generated_at, artifact_version, schema_version,
                engine_version, feature_schema_version, w5_dataset_version, w6_run_id,
                w7_run_id, w8_run_id, observability, ordering_contract
             ) VALUES (?1,?2,?3,?4,?5,?6,?7,?8,?9,?10,?11,?12,?13)",
            params![
                run_id,
                DATASET_VERSION,
                generated_at.to_rfc3339(),
                ARTIFACT_VERSION,
                SCHEMA_VERSION,
                ENGINE_VERSION,
                FEATURE_SCHEMA_VERSION,
                w5_dataset_version,
                w6_run_id,
                w7_run_id,
                w8_run_id,
                OBSERVABILITY,
                ORDERING_CONTRACT,
            ],
        )?;
        Ok(Self {
            conn,
            run_id: run_id.to_string(),
        })
    }

    pub fn open_existing(path: &Path) -> Result<Self, B1Error> {
        let conn = Connection::open(path)?;
        conn.execute_batch("PRAGMA query_only = ON;")?;
        let run_id: String = conn.query_row(
            "SELECT run_id FROM feature_runs ORDER BY generated_at DESC LIMIT 1",
            [],
            |r| r.get(0),
        )?;
        Ok(Self { conn, run_id })
    }

    pub fn run_id(&self) -> &str {
        &self.run_id
    }

    pub fn run_meta(&self) -> Result<serde_json::Value, B1Error> {
        let row = self.conn.query_row(
            "SELECT run_id, dataset_version, generated_at, feature_schema_version,
                    engine_version, w5_dataset_version, w6_run_id, w7_run_id, w8_run_id
             FROM feature_runs WHERE run_id = ?1",
            params![self.run_id],
            |r| {
                Ok(serde_json::json!({
                    "run_id": r.get::<_, String>(0)?,
                    "dataset_version": r.get::<_, String>(1)?,
                    "generated_at": r.get::<_, String>(2)?,
                    "feature_schema_version": r.get::<_, String>(3)?,
                    "engine_version": r.get::<_, String>(4)?,
                    "w5_dataset_version": r.get::<_, Option<String>>(5)?,
                    "w6_run_id": r.get::<_, String>(6)?,
                    "w7_run_id": r.get::<_, String>(7)?,
                    "w8_run_id": r.get::<_, String>(8)?,
                }))
            },
        )?;
        Ok(row)
    }

    pub fn insert_snapshot(&self, s: &B1EntrySnapshot) -> Result<(), B1Error> {
        let payload = serde_json::to_string(s)?;
        self.conn.execute(
            "INSERT INTO entry_snapshots(
                snapshot_id, run_id, game_id, market_id, contract_side, entry_timestamp,
                entry_trade_price_cents, execution_status, w8_opportunity_id, w5_observation_id,
                official_date, split_group, settlement, bound_team_lead, inning, p_start_cents,
                start_sentiment, start_to_entry_move_cents, a1_entry_target, payload_json
             ) VALUES (?1,?2,?3,?4,?5,?6,?7,?8,?9,?10,?11,?12,?13,?14,?15,?16,?17,?18,?19,?20)",
            params![
                s.snapshot_id,
                self.run_id,
                s.game_id,
                s.market_id,
                s.contract_side,
                s.entry_timestamp.to_rfc3339(),
                s.entry_trade_price_cents,
                s.execution_status,
                s.w8_opportunity_id,
                s.w5_observation_id,
                s.official_date,
                s.split_group.as_str(),
                s.outcomes.settlement.as_str(),
                s.baseball.bound_team_lead,
                s.baseball.inning.map(i64::from),
                s.starting_market.p_start_cents,
                s.starting_market.start_sentiment.as_str(),
                s.market_history.start_to_entry_move_cents,
                s.a1_targets.entry_target.as_str(),
                payload,
            ],
        )?;
        Ok(())
    }

    pub fn load_all(&self) -> Result<Vec<B1EntrySnapshot>, B1Error> {
        let mut stmt = self
            .conn
            .prepare("SELECT payload_json FROM entry_snapshots WHERE run_id = ?1 ORDER BY entry_timestamp, snapshot_id")?;
        let rows = stmt.query_map(params![self.run_id], |r| r.get::<_, String>(0))?;
        let mut out = Vec::new();
        for row in rows {
            out.push(serde_json::from_str(&row?)?);
        }
        Ok(out)
    }

    pub fn checkpoint(&self) -> Result<(), B1Error> {
        self.conn
            .execute_batch("PRAGMA wal_checkpoint(TRUNCATE);")?;
        Ok(())
    }
}

pub fn parse_ts(raw: Option<String>) -> Option<DateTime<Utc>> {
    raw.and_then(|s| DateTime::parse_from_rfc3339(&s).ok())
        .map(|d| d.with_timezone(&Utc))
}

pub fn w8_run_id(path: &Path) -> Result<String, B1Error> {
    let conn = Connection::open(path)?;
    conn.execute_batch("PRAGMA query_only = ON;")?;
    conn.query_row(
        "SELECT run_id FROM replay_runs ORDER BY generated_at DESC LIMIT 1",
        [],
        |r| r.get(0),
    )
    .map_err(B1Error::from)
}

pub fn w8_entry_count(path: &Path) -> Result<i64, B1Error> {
    let conn = Connection::open(path)?;
    conn.execute_batch("PRAGMA query_only = ON;")?;
    Ok(conn.query_row(
        "SELECT COUNT(*) FROM first01_opportunities WHERE entry_price_cents IS NOT NULL
           AND entry_eligible_timestamp_utc IS NOT NULL AND entry_observation_id IS NOT NULL",
        [],
        |r| r.get(0),
    )?)
}

pub fn load_w8_entries(path: &Path) -> Result<Vec<crate::dataset::W8EntryInput>, B1Error> {
    let conn = Connection::open(path)?;
    conn.execute_batch("PRAGMA query_only = ON;")?;
    let run: String = conn.query_row(
        "SELECT run_id FROM replay_runs ORDER BY generated_at DESC LIMIT 1",
        [],
        |r| r.get(0),
    )?;
    let mut stmt = conn.prepare(
        "SELECT opportunity_id, game_id, market_id, side,
                entry_eligible_timestamp_utc, entry_observation_id, entry_price_cents,
                first80_observation_id, first80_timestamp_utc, confirmation_observation_id
         FROM first01_opportunities
         WHERE run_id = ?1
           AND entry_price_cents IS NOT NULL
           AND entry_eligible_timestamp_utc IS NOT NULL
           AND entry_observation_id IS NOT NULL
         ORDER BY game_id",
    )?;
    let rows = stmt.query_map(params![run], |r| {
        Ok((
            r.get::<_, String>(0)?,
            r.get::<_, String>(1)?,
            r.get::<_, String>(2)?,
            r.get::<_, String>(3)?,
            r.get::<_, Option<String>>(4)?,
            r.get::<_, Option<String>>(5)?,
            r.get::<_, Option<i32>>(6)?,
            r.get::<_, Option<String>>(7)?,
            r.get::<_, Option<String>>(8)?,
            r.get::<_, Option<String>>(9)?,
        ))
    })?;
    let mut out = Vec::new();
    for row in rows {
        let (oid, gid, mid, side, te, oe, pe, o80, t80, oc) = row?;
        let (Some(te), Some(oe), Some(pe)) = (te, oe, pe) else {
            continue;
        };
        let Some(ts) = parse_ts(Some(te)) else {
            continue;
        };
        out.push(crate::dataset::W8EntryInput {
            opportunity_id: oid,
            game_id: gid,
            market_id: mid,
            side,
            entry_timestamp: ts,
            entry_observation_id: oe,
            entry_price_cents: pe,
            first80_observation_id: o80,
            first80_timestamp: parse_ts(t80),
            confirm_observation_id: oc,
            official_date: None,
            game_pk: None,
            game_status: None,
        });
    }
    Ok(out)
}

pub type W6GameMeta = (Option<String>, Option<String>, Option<String>);

pub fn load_w6_game_meta(w6: &Path, game_id: &str) -> Result<W6GameMeta, B1Error> {
    let conn = Connection::open(w6)?;
    conn.execute_batch("PRAGMA query_only = ON;")?;
    let row = conn
        .query_row(
            "SELECT official_date, game_pk, status FROM games WHERE game_id = ?1 LIMIT 1",
            params![game_id],
            |r| {
                Ok((
                    r.get::<_, Option<String>>(0)?,
                    r.get::<_, Option<String>>(1)?,
                    r.get::<_, Option<String>>(2)?,
                ))
            },
        )
        .optional()?;
    Ok(row.unwrap_or((None, None, None)))
}
