//! SQLite store for synchronized observations.

use chrono::{DateTime, Utc};
use rusqlite::{Connection, params};
use std::path::Path;

use crate::error::W5Error;
use crate::schema_sql::MIGRATION_001_SQL;
use crate::types::{
    GameCoverage, GameStateSnapshot, ObservationType, SyncQuality, SyncStatus,
    SynchronizedMarketObservation, TimestampRelation,
};
use crate::versions::{ARTIFACT_VERSION, MIGRATION_001};

pub struct SyncStore {
    conn: Connection,
    run_id: String,
}

impl SyncStore {
    pub fn open(path: &Path, run_id: &str, generated_at: DateTime<Utc>) -> Result<Self, W5Error> {
        if let Some(parent) = path.parent() {
            std::fs::create_dir_all(parent)?;
        }
        let conn = Connection::open(path)?;
        // WAL autocheckpoint defaults to 1000 pages. On a multi-GB observation
        // store that copies the WAL into the main file after every game and
        // stalls the run (observed: ~40GB W5, checkpoint on every insert_batch).
        conn.execute_batch(
            "PRAGMA foreign_keys = ON;
             PRAGMA journal_mode = WAL;
             PRAGMA synchronous = NORMAL;
             PRAGMA wal_autocheckpoint = 0;
             PRAGMA cache_size = -65536;",
        )?;
        conn.execute_batch(MIGRATION_001_SQL)?;
        conn.execute(
            "INSERT OR IGNORE INTO schema_migrations(version, applied_at) VALUES (?1, ?2)",
            params![MIGRATION_001, generated_at.to_rfc3339()],
        )?;
        conn.execute(
            "INSERT OR REPLACE INTO sync_runs(run_id, dataset_version, generated_at, artifact_version)
             VALUES (?1, ?2, ?3, ?4)",
            params![
                run_id,
                crate::versions::DATASET_VERSION,
                generated_at.to_rfc3339(),
                ARTIFACT_VERSION
            ],
        )?;
        Ok(Self {
            conn,
            run_id: run_id.to_string(),
        })
    }

    pub fn checkpoint(&self) -> Result<(), W5Error> {
        self.conn
            .execute_batch("PRAGMA wal_checkpoint(TRUNCATE);")?;
        Ok(())
    }

    /// Read an existing W5 artifact. Does not write a new run.
    pub fn open_existing(path: &Path) -> Result<Self, W5Error> {
        if !path.exists() {
            return Err(W5Error::Uncommitted(format!(
                "W5 sqlite missing: {}",
                path.display()
            )));
        }
        let conn = Connection::open(path)?;
        conn.execute_batch("PRAGMA query_only = ON;")?;
        let run_id: String = conn
            .query_row(
                "SELECT run_id FROM sync_runs ORDER BY generated_at DESC LIMIT 1",
                [],
                |r| r.get(0),
            )
            .map_err(|_| {
                W5Error::Uncommitted(format!("W5 sqlite has no sync_runs: {}", path.display()))
            })?;
        Ok(Self { conn, run_id })
    }

    pub fn run_id(&self) -> &str {
        &self.run_id
    }

    pub fn dataset_version(&self) -> Result<String, W5Error> {
        Ok(self.conn.query_row(
            "SELECT dataset_version FROM sync_runs WHERE run_id = ?1",
            params![self.run_id],
            |r| r.get(0),
        )?)
    }

    pub fn artifact_version(&self) -> Result<String, W5Error> {
        Ok(self.conn.query_row(
            "SELECT artifact_version FROM sync_runs WHERE run_id = ?1",
            params![self.run_id],
            |r| r.get(0),
        )?)
    }

    /// Distinct games in the stored W5 run, ordered by GameId.
    pub fn list_games(&self) -> Result<Vec<(String, String)>, W5Error> {
        let mut stmt = self.conn.prepare(
            "SELECT game_id, game_pk FROM game_coverage WHERE run_id = ?1 ORDER BY game_id, game_pk",
        )?;
        let rows = stmt.query_map(params![self.run_id], |r| {
            Ok((r.get::<_, String>(0)?, r.get::<_, String>(1)?))
        })?;
        let mut out = Vec::new();
        for row in rows {
            out.push(row?);
        }
        Ok(out)
    }

    pub fn open_memory(run_id: &str, generated_at: DateTime<Utc>) -> Result<Self, W5Error> {
        let conn = Connection::open_in_memory()?;
        conn.execute_batch("PRAGMA foreign_keys = ON;")?;
        conn.execute_batch(MIGRATION_001_SQL)?;
        conn.execute(
            "INSERT INTO schema_migrations(version, applied_at) VALUES (?1, ?2)",
            params![MIGRATION_001, generated_at.to_rfc3339()],
        )?;
        conn.execute(
            "INSERT INTO sync_runs(run_id, dataset_version, generated_at, artifact_version)
             VALUES (?1, ?2, ?3, ?4)",
            params![
                run_id,
                crate::versions::DATASET_VERSION,
                generated_at.to_rfc3339(),
                ARTIFACT_VERSION
            ],
        )?;
        Ok(Self {
            conn,
            run_id: run_id.to_string(),
        })
    }

    pub fn insert_batch(
        &mut self,
        rows: &[SynchronizedMarketObservation],
    ) -> Result<usize, W5Error> {
        let tx = self.conn.transaction()?;
        {
            let mut stmt = tx.prepare(
                "INSERT OR REPLACE INTO synchronized_observations (
                    synchronization_id, run_id, game_id, game_pk, market_id, ticker, contract_id,
                    contract_side, observation_id, observation_type, market_timestamp_source,
                    source_timestamp_kind, market_timestamp_utc, retrieval_timestamp,
                    prior_event_id, prior_event_timestamp_utc, next_event_id,
                    next_event_timestamp_utc, timestamp_relation, event_to_market_lag_ms,
                    market_to_next_event_ms, synchronization_status, synchronization_method,
                    synchronization_quality, state_seq, inning, half, outs, score_home,
                    score_away, run_differential, balls, strikes, extra_inning, pre_state_seq,
                    pre_inning, pre_outs, pre_score_home, pre_score_away,
                    prior_market_observation_id, next_market_observation_id,
                    elapsed_from_prior_obs_ms, elapsed_to_next_obs_ms, last_trade_cents,
                    first_observed_price_cents, source_id, source_lineage, dataset_version
                ) VALUES (
                    ?1,?2,?3,?4,?5,?6,?7,?8,?9,?10,?11,?12,?13,?14,?15,?16,?17,?18,?19,?20,
                    ?21,?22,?23,?24,?25,?26,?27,?28,?29,?30,?31,?32,?33,?34,?35,?36,?37,?38,
                    ?39,?40,?41,?42,?43,?44,?45,?46,?47,?48
                )",
            )?;
            for r in rows {
                let gs = r.game_state.as_ref();
                let pre = r.pre_event_state.as_ref();
                stmt.execute(params![
                    r.synchronization_id,
                    self.run_id,
                    r.game_id,
                    r.game_pk,
                    r.market_id,
                    r.ticker,
                    r.contract_id,
                    r.contract_side,
                    r.observation_id,
                    r.observation_type.as_str(),
                    r.market_timestamp_source,
                    r.source_timestamp_kind,
                    r.market_timestamp_utc.map(|t| t.to_rfc3339()),
                    r.retrieval_timestamp.map(|t| t.to_rfc3339()),
                    r.prior_event_id,
                    r.prior_event_timestamp_utc.map(|t| t.to_rfc3339()),
                    r.next_event_id,
                    r.next_event_timestamp_utc.map(|t| t.to_rfc3339()),
                    r.timestamp_relation.as_str(),
                    r.event_to_market_lag_ms,
                    r.market_to_next_event_ms,
                    r.synchronization_status.as_str(),
                    r.synchronization_method,
                    r.synchronization_quality.as_str(),
                    gs.map(|s| s.state_seq),
                    gs.map(|s| s.inning),
                    gs.map(|s| s.half.clone()),
                    gs.map(|s| s.outs),
                    gs.map(|s| s.score_home),
                    gs.map(|s| s.score_away),
                    gs.map(|s| s.run_differential),
                    gs.map(|s| s.balls),
                    gs.map(|s| s.strikes),
                    gs.map(|s| i64::from(s.extra_inning)),
                    pre.map(|s| s.state_seq),
                    pre.map(|s| s.inning),
                    pre.map(|s| s.outs),
                    pre.map(|s| s.score_home),
                    pre.map(|s| s.score_away),
                    r.prior_market_observation_id,
                    r.next_market_observation_id,
                    r.elapsed_from_prior_obs_ms,
                    r.elapsed_to_next_obs_ms,
                    r.last_trade_cents,
                    r.first_observed_price_cents,
                    r.source_id,
                    r.source_lineage,
                    r.dataset_version,
                ])?;
            }
        }
        tx.commit()?;
        Ok(rows.len())
    }

    pub fn insert_coverage(&mut self, cov: &GameCoverage) -> Result<(), W5Error> {
        self.conn.execute(
            "INSERT OR REPLACE INTO game_coverage (
                run_id, game_id, game_pk, timed_events, observations, synchronized, at_event,
                before_first, after_last, first_pbp_utc, last_pbp_utc, first_market_utc,
                last_market_utc
            ) VALUES (?1,?2,?3,?4,?5,?6,?7,?8,?9,?10,?11,?12,?13)",
            params![
                self.run_id,
                cov.game_id,
                cov.game_pk,
                cov.timed_events as i64,
                cov.observations as i64,
                cov.synchronized as i64,
                cov.at_event as i64,
                cov.before_first as i64,
                cov.after_last as i64,
                cov.first_pbp_utc,
                cov.last_pbp_utc,
                cov.first_market_utc,
                cov.last_market_utc,
            ],
        )?;
        Ok(())
    }

    pub fn observations_for_game(
        &self,
        game_id: &str,
    ) -> Result<Vec<SynchronizedMarketObservation>, W5Error> {
        self.query(
            "SELECT * FROM synchronized_observations WHERE run_id = ?1 AND game_id = ?2
             ORDER BY market_timestamp_utc, observation_id",
            params![self.run_id, game_id],
        )
    }

    pub fn observations_for_market(
        &self,
        market_id: &str,
    ) -> Result<Vec<SynchronizedMarketObservation>, W5Error> {
        self.query(
            "SELECT * FROM synchronized_observations WHERE run_id = ?1 AND market_id = ?2
             ORDER BY market_timestamp_utc, observation_id",
            params![self.run_id, market_id],
        )
    }

    pub fn observations_for_event_interval(
        &self,
        game_id: &str,
        event_id: &str,
    ) -> Result<Vec<SynchronizedMarketObservation>, W5Error> {
        self.query(
            "SELECT * FROM synchronized_observations
             WHERE run_id = ?1 AND game_id = ?2 AND prior_event_id = ?3
             ORDER BY market_timestamp_utc, observation_id",
            params![self.run_id, game_id, event_id],
        )
    }

    fn query(
        &self,
        sql: &str,
        params: impl rusqlite::Params,
    ) -> Result<Vec<SynchronizedMarketObservation>, W5Error> {
        let mut stmt = self.conn.prepare(sql)?;
        let rows = stmt.query_map(params, row_from_sqlite)?;
        let mut out = Vec::new();
        for r in rows {
            out.push(r?);
        }
        Ok(out)
    }
}

fn row_from_sqlite(row: &rusqlite::Row<'_>) -> rusqlite::Result<SynchronizedMarketObservation> {
    let status: String = row.get("synchronization_status")?;
    let quality: String = row.get("synchronization_quality")?;
    let obs_ty: String = row.get("observation_type")?;
    let relation: String = row.get("timestamp_relation")?;
    let state_seq: Option<u32> = row.get("state_seq")?;
    let extra: Option<i64> = row.get("extra_inning")?;
    let game_state = state_seq.map(|seq| GameStateSnapshot {
        game_id: row.get("game_id").unwrap_or_default(),
        event_id: row
            .get::<_, Option<String>>("prior_event_id")
            .ok()
            .flatten()
            .unwrap_or_default(),
        state_seq: seq,
        inning: row
            .get::<_, Option<u8>>("inning")
            .ok()
            .flatten()
            .unwrap_or(0),
        half: row
            .get::<_, Option<String>>("half")
            .ok()
            .flatten()
            .unwrap_or_default(),
        outs: row.get::<_, Option<u8>>("outs").ok().flatten().unwrap_or(0),
        score_home: row
            .get::<_, Option<u16>>("score_home")
            .ok()
            .flatten()
            .unwrap_or(0),
        score_away: row
            .get::<_, Option<u16>>("score_away")
            .ok()
            .flatten()
            .unwrap_or(0),
        run_differential: row
            .get::<_, Option<i32>>("run_differential")
            .ok()
            .flatten()
            .unwrap_or(0),
        runner_first: None,
        runner_second: None,
        runner_third: None,
        batter: None,
        pitcher: None,
        balls: row
            .get::<_, Option<u8>>("balls")
            .ok()
            .flatten()
            .unwrap_or(0),
        strikes: row
            .get::<_, Option<u8>>("strikes")
            .ok()
            .flatten()
            .unwrap_or(0),
        count: format!(
            "{}-{}",
            row.get::<_, Option<u8>>("balls")
                .ok()
                .flatten()
                .unwrap_or(0),
            row.get::<_, Option<u8>>("strikes")
                .ok()
                .flatten()
                .unwrap_or(0)
        ),
        game_status: String::new(),
        extra_inning: extra.unwrap_or(0) != 0,
    });
    let pre_seq: Option<u32> = row.get("pre_state_seq")?;
    let pre_event_state = pre_seq.map(|seq| GameStateSnapshot {
        game_id: row.get("game_id").unwrap_or_default(),
        event_id: row
            .get::<_, Option<String>>("prior_event_id")
            .ok()
            .flatten()
            .unwrap_or_default(),
        state_seq: seq,
        inning: row
            .get::<_, Option<u8>>("pre_inning")
            .ok()
            .flatten()
            .unwrap_or(0),
        half: String::new(),
        outs: row
            .get::<_, Option<u8>>("pre_outs")
            .ok()
            .flatten()
            .unwrap_or(0),
        score_home: row
            .get::<_, Option<u16>>("pre_score_home")
            .ok()
            .flatten()
            .unwrap_or(0),
        score_away: row
            .get::<_, Option<u16>>("pre_score_away")
            .ok()
            .flatten()
            .unwrap_or(0),
        run_differential: 0,
        runner_first: None,
        runner_second: None,
        runner_third: None,
        batter: None,
        pitcher: None,
        balls: 0,
        strikes: 0,
        count: String::new(),
        game_status: String::new(),
        extra_inning: false,
    });
    Ok(SynchronizedMarketObservation {
        synchronization_id: row.get("synchronization_id")?,
        game_id: row.get("game_id")?,
        game_pk: row.get("game_pk")?,
        market_id: row.get("market_id")?,
        ticker: row.get("ticker")?,
        contract_id: row.get("contract_id")?,
        contract_side: row.get("contract_side")?,
        observation_id: row.get("observation_id")?,
        observation_type: parse_obs(&obs_ty),
        market_timestamp_source: row.get("market_timestamp_source")?,
        source_timestamp_kind: row.get("source_timestamp_kind")?,
        market_timestamp_utc: parse_named(row, "market_timestamp_utc")?,
        retrieval_timestamp: parse_named(row, "retrieval_timestamp")?,
        prior_event_id: row.get("prior_event_id")?,
        prior_event_timestamp_utc: parse_named(row, "prior_event_timestamp_utc")?,
        next_event_id: row.get("next_event_id")?,
        next_event_timestamp_utc: parse_named(row, "next_event_timestamp_utc")?,
        timestamp_relation: parse_relation(&relation),
        event_to_market_lag_ms: row.get("event_to_market_lag_ms")?,
        market_to_next_event_ms: row.get("market_to_next_event_ms")?,
        synchronization_status: parse_status(&status),
        synchronization_method: row.get("synchronization_method")?,
        synchronization_quality: parse_quality(&quality),
        game_state: game_state.clone(),
        pre_event_state,
        post_event_state: game_state,
        prior_market_observation_id: row.get("prior_market_observation_id")?,
        next_market_observation_id: row.get("next_market_observation_id")?,
        elapsed_from_prior_obs_ms: row.get("elapsed_from_prior_obs_ms")?,
        elapsed_to_next_obs_ms: row.get("elapsed_to_next_obs_ms")?,
        last_trade_cents: row.get("last_trade_cents")?,
        first_observed_price_cents: row.get("first_observed_price_cents")?,
        source_id: row.get("source_id")?,
        source_lineage: row.get("source_lineage")?,
        dataset_version: row.get("dataset_version")?,
    })
}

fn parse_named(row: &rusqlite::Row<'_>, col: &str) -> rusqlite::Result<Option<DateTime<Utc>>> {
    let s: Option<String> = row.get(col)?;
    Ok(s.and_then(|x| DateTime::parse_from_rfc3339(&x).ok())
        .map(|d| d.with_timezone(&Utc)))
}

fn parse_status(s: &str) -> SyncStatus {
    match s {
        "SYNCHRONIZED" => SyncStatus::Synchronized,
        "AT_EVENT" => SyncStatus::AtEvent,
        "SYNCHRONIZED_WITH_TIMESTAMP_GAP" => SyncStatus::SynchronizedWithTimestampGap,
        "BEFORE_FIRST_EVENT" | "UNSYNCHRONIZED_NO_PRIOR_EVENT" => SyncStatus::BeforeFirstEvent,
        "AFTER_LAST_EVENT" | "OUTSIDE_GAME_WINDOW" => SyncStatus::AfterLastEvent,
        "AMBIGUOUS_TIMESTAMP" => SyncStatus::AmbiguousTimestamp,
        "MISSING_TIMESTAMP" | "INVALID_TIMESTAMP" => SyncStatus::MissingTimestamp,
        "IDENTITY_UNMATCHED" => SyncStatus::IdentityUnmatched,
        "IDENTITY_AMBIGUOUS" => SyncStatus::IdentityAmbiguous,
        _ => SyncStatus::SourceDataInvalid,
    }
}

fn parse_quality(s: &str) -> SyncQuality {
    match s {
        "EXACT" => SyncQuality::Exact,
        "WITHIN_1S" => SyncQuality::Within1s,
        "WITHIN_3S" => SyncQuality::Within3s,
        "WITHIN_5S" => SyncQuality::Within5s,
        "WITHIN_INNING" => SyncQuality::WithinInning,
        "AMBIGUOUS" => SyncQuality::Ambiguous,
        "UNMATCHED" => SyncQuality::Unmatched,
        _ => SyncQuality::Unavailable,
    }
}

fn parse_relation(s: &str) -> TimestampRelation {
    match s {
        "BEFORE_EVENT" => TimestampRelation::BeforeEvent,
        "AT_EVENT" => TimestampRelation::AtEvent,
        "AFTER_EVENT" => TimestampRelation::AfterEvent,
        "AMBIGUOUS_TIMESTAMP" => TimestampRelation::AmbiguousTimestamp,
        _ => TimestampRelation::NotApplicable,
    }
}

fn parse_obs(s: &str) -> ObservationType {
    match s {
        "QUOTE" => ObservationType::Quote,
        "CANDLE" => ObservationType::Candle,
        "L2_SNAPSHOT" | "ORDERBOOK_SNAPSHOT" => ObservationType::L2Snapshot,
        "L2_DELTA" | "ORDERBOOK_DELTA" => ObservationType::L2Delta,
        _ => ObservationType::Trade,
    }
}
