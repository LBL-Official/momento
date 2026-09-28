//! SQLite store for FIRST01 replay events and opportunities.

use chrono::{DateTime, Utc};
use rusqlite::{Connection, params};
use std::path::Path;

use crate::error::W8Error;
use crate::schema_sql::MIGRATION_001_SQL;
use crate::types::{First01Opportunity, ReplayEvent, ReplayEventType};
use crate::versions::{
    ARTIFACT_VERSION, ENGINE_VERSION, MIGRATION_001, OBSERVABILITY, ORDERING_CONTRACT,
};

pub struct ReplayStore {
    conn: Connection,
    run_id: String,
}

impl ReplayStore {
    pub fn open(
        path: &Path,
        run_id: &str,
        generated_at: DateTime<Utc>,
        w7_ver: &str,
        w7_run_id: &str,
    ) -> Result<Self, W8Error> {
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
            "INSERT OR REPLACE INTO replay_runs(
                run_id, dataset_version, generated_at, artifact_version, w7_dataset_version,
                w7_run_id, engine_version, strategy_name, strategy_version, observability,
                ordering_contract
             ) VALUES (?1,?2,?3,?4,?5,?6,?7,?8,?9,?10,?11)",
            params![
                run_id,
                crate::versions::DATASET_VERSION,
                generated_at.to_rfc3339(),
                ARTIFACT_VERSION,
                w7_ver,
                w7_run_id,
                ENGINE_VERSION,
                momento_research_strategies::FIRST01_NAME,
                momento_research_strategies::FIRST01_VERSION as i64,
                OBSERVABILITY,
                ORDERING_CONTRACT
            ],
        )?;
        Ok(Self {
            conn,
            run_id: run_id.to_string(),
        })
    }

    pub fn checkpoint(&self) -> Result<(), W8Error> {
        self.conn
            .execute_batch("PRAGMA wal_checkpoint(TRUNCATE);")?;
        Ok(())
    }

    pub fn open_memory(run_id: &str, generated_at: DateTime<Utc>) -> Result<Self, W8Error> {
        Self::open(Path::new(":memory:"), run_id, generated_at, "w7", "w7-run").or_else(|_| {
            let conn = Connection::open_in_memory()?;
            conn.execute_batch("PRAGMA foreign_keys = ON;")?;
            conn.execute_batch(MIGRATION_001_SQL)?;
            conn.execute(
                "INSERT INTO schema_migrations(version, applied_at) VALUES (?1, ?2)",
                params![MIGRATION_001, generated_at.to_rfc3339()],
            )?;
            conn.execute(
                "INSERT INTO replay_runs(
                        run_id, dataset_version, generated_at, artifact_version, w7_dataset_version,
                        w7_run_id, engine_version, strategy_name, strategy_version, observability,
                        ordering_contract
                     ) VALUES (?1,?2,?3,?4,'w7','w7-run',?5,'FIRST01',1,?6,?7)",
                params![
                    run_id,
                    crate::versions::DATASET_VERSION,
                    generated_at.to_rfc3339(),
                    ARTIFACT_VERSION,
                    ENGINE_VERSION,
                    OBSERVABILITY,
                    ORDERING_CONTRACT
                ],
            )?;
            Ok(Self {
                conn,
                run_id: run_id.to_string(),
            })
        })
    }

    pub fn insert_events(&mut self, events: &[ReplayEvent]) -> Result<(), W8Error> {
        let tx = self.conn.transaction()?;
        {
            let mut stmt = tx.prepare(
                "INSERT OR REPLACE INTO replay_events(
                    replay_event_id, run_id, game_id, market_id, side, observation_id,
                    market_timestamp_utc, strategy_state_before, strategy_state_after, event_type,
                    price_cents, state_id, state_seq, synchronization_class, synchronization_quality,
                    reason, observability, strategy_version, w7_dataset_version, w8_engine_version
                 ) VALUES (?1,?2,?3,?4,?5,?6,?7,?8,?9,?10,?11,?12,?13,?14,?15,?16,?17,?18,?19,?20)",
            )?;
            for e in events {
                stmt.execute(params![
                    e.replay_event_id,
                    self.run_id,
                    e.game_id,
                    e.market_id,
                    e.side,
                    e.observation_id,
                    e.market_timestamp_utc.map(|t| t.to_rfc3339()),
                    e.strategy_state_before,
                    e.strategy_state_after,
                    e.event_type.as_str(),
                    e.price_cents,
                    e.state_id,
                    e.state_seq.map(i64::from),
                    e.synchronization_class,
                    e.synchronization_quality,
                    e.reason,
                    e.observability,
                    e.strategy_version as i64,
                    e.w7_dataset_version,
                    e.w8_engine_version,
                ])?;
            }
        }
        tx.commit()?;
        Ok(())
    }

    pub fn insert_opportunities(&mut self, ops: &[First01Opportunity]) -> Result<(), W8Error> {
        let tx = self.conn.transaction()?;
        {
            let mut stmt = tx.prepare(
                "INSERT OR REPLACE INTO first01_opportunities(
                    opportunity_id, run_id, game_id, market_id, side, first80_timestamp_utc,
                    first80_observation_id, first80_price_cents, first80_state_id, first80_state_seq,
                    confirmation_timestamp_utc, confirmation_observation_id, confirmation_state_id,
                    confirmation_state_seq, entry_eligible_timestamp_utc, entry_observation_id,
                    entry_price_cents, intent_proposed, game_lock_timestamp_utc,
                    game_lock_observation_id, replay_terminal_state, first80_sync_class,
                    confirmation_sync_class, observability, strategy_version, w7_dataset_version
                 ) VALUES (?1,?2,?3,?4,?5,?6,?7,?8,?9,?10,?11,?12,?13,?14,?15,?16,?17,?18,?19,?20,?21,?22,?23,?24,?25,?26)",
            )?;
            for o in ops {
                stmt.execute(params![
                    o.opportunity_id,
                    self.run_id,
                    o.game_id,
                    o.market_id,
                    o.side,
                    o.first80_timestamp_utc.map(|t| t.to_rfc3339()),
                    o.first80_observation_id,
                    o.first80_price_cents,
                    o.first80_state_id,
                    o.first80_state_seq.map(i64::from),
                    o.confirmation_timestamp_utc.map(|t| t.to_rfc3339()),
                    o.confirmation_observation_id,
                    o.confirmation_state_id,
                    o.confirmation_state_seq.map(i64::from),
                    o.entry_eligible_timestamp_utc.map(|t| t.to_rfc3339()),
                    o.entry_observation_id,
                    o.entry_price_cents,
                    i64::from(o.intent_proposed),
                    o.game_lock_timestamp_utc.map(|t| t.to_rfc3339()),
                    o.game_lock_observation_id,
                    o.replay_terminal_state,
                    o.first80_sync_class,
                    o.confirmation_sync_class,
                    o.observability,
                    o.strategy_version as i64,
                    o.w7_dataset_version,
                ])?;
            }
        }
        tx.commit()?;
        Ok(())
    }

    pub fn events_for_game(&self, game_id: &str) -> Result<Vec<ReplayEvent>, W8Error> {
        let mut stmt = self.conn.prepare(
            "SELECT replay_event_id, game_id, market_id, side, observation_id, market_timestamp_utc,
                    strategy_state_before, strategy_state_after, event_type, price_cents, state_id,
                    state_seq, synchronization_class, synchronization_quality, reason
             FROM replay_events WHERE run_id = ?1 AND game_id = ?2
             ORDER BY market_timestamp_utc, observation_id, event_type",
        )?;
        let rows = stmt.query_map(params![self.run_id, game_id], |r| {
            Ok(ReplayEvent {
                replay_event_id: r.get(0)?,
                game_id: r.get(1)?,
                market_id: r.get(2)?,
                side: r.get(3)?,
                observation_id: r.get(4)?,
                market_timestamp_utc: parse_ts(r.get(5)?),
                strategy_state_before: r.get(6)?,
                strategy_state_after: r.get(7)?,
                event_type: parse_type(&r.get::<_, String>(8)?),
                price_cents: r.get(9)?,
                state_id: r.get(10)?,
                state_seq: r.get::<_, Option<i64>>(11)?.map(|v| v as u32),
                state_timestamp_utc: None,
                inning: None,
                half: None,
                outs: None,
                score_home: None,
                score_away: None,
                run_differential: None,
                bases: None,
                batter_id: None,
                pitcher_id: None,
                balls: None,
                strikes: None,
                game_status: None,
                synchronization_class: r.get(12)?,
                synchronization_quality: r.get(13)?,
                reason: r.get(14)?,
                observability: OBSERVABILITY.to_string(),
                previous_trade_price_cents: None,
                observed_high_cents_so_far: None,
                observed_low_cents_so_far: None,
                cumulative_trade_count: 0,
                time_since_previous_trade_ms: None,
                time_since_state_transition_ms: None,
                strategy: momento_research_strategies::FIRST01_NAME.to_string(),
                strategy_version: momento_research_strategies::FIRST01_VERSION,
                w7_dataset_version: String::new(),
                w8_engine_version: ENGINE_VERSION.to_string(),
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

fn parse_type(s: &str) -> ReplayEventType {
    match s {
        "FIRST80_OBSERVED" => ReplayEventType::First80Observed,
        "CONFIRM81_OBSERVED" => ReplayEventType::Confirm81Observed,
        "ENTRY_ELIGIBLE" => ReplayEventType::EntryEligible,
        "ENTRY_INTENT_PROPOSED" => ReplayEventType::EntryIntentProposed,
        "PRICE_PAUSED" => ReplayEventType::PricePaused,
        "GAME_LOCKED" => ReplayEventType::GameLocked,
        "AMBIGUOUS_REPLAY_ORDER" => ReplayEventType::AmbiguousReplayOrder,
        "SKIPPED_MISSING_PRICE" => ReplayEventType::SkippedMissingPrice,
        _ => ReplayEventType::SkippedMissingTimestamp,
    }
}
