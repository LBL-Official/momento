use std::path::Path;
use std::sync::Mutex;

use rusqlite::{Connection, OptionalExtension, params};

use crate::error::EngineError;
use crate::types::{DatasetRecord, ExperimentRecord, JobRecord, PromotionRecord, StrategyRecord};

pub struct EngineStore {
    conn: Mutex<Connection>,
}

impl EngineStore {
    pub fn open(path: &Path) -> Result<Self, EngineError> {
        if let Some(parent) = path.parent() {
            std::fs::create_dir_all(parent)?;
        }
        let conn = Connection::open(path)?;
        conn.execute_batch(
            "PRAGMA journal_mode = WAL;
             PRAGMA foreign_keys = ON;
             CREATE TABLE IF NOT EXISTS datasets (
                id TEXT NOT NULL,
                version TEXT NOT NULL,
                name TEXT NOT NULL,
                event_definition TEXT NOT NULL,
                source TEXT NOT NULL,
                features_sqlite TEXT,
                game_count INTEGER,
                capabilities TEXT NOT NULL,
                quality TEXT NOT NULL,
                provenance TEXT NOT NULL,
                status TEXT NOT NULL,
                PRIMARY KEY (id, version)
             );
             CREATE TABLE IF NOT EXISTS strategies (
                id TEXT NOT NULL,
                version TEXT NOT NULL,
                name TEXT NOT NULL,
                description TEXT NOT NULL,
                research_status TEXT NOT NULL,
                production_status TEXT NOT NULL,
                PRIMARY KEY (id, version)
             );
             CREATE TABLE IF NOT EXISTS models (
                id TEXT PRIMARY KEY,
                strategy_id TEXT NOT NULL,
                version TEXT NOT NULL,
                dataset_id TEXT NOT NULL,
                dataset_version TEXT NOT NULL,
                parameters TEXT NOT NULL,
                health TEXT NOT NULL,
                status TEXT NOT NULL,
                calibration_at TEXT
             );
             CREATE TABLE IF NOT EXISTS experiments (
                id TEXT PRIMARY KEY,
                status TEXT NOT NULL,
                definition_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                hypothesis_count INTEGER NOT NULL DEFAULT 0,
                result_summary TEXT,
                artifact_dir TEXT
             );
             CREATE TABLE IF NOT EXISTS jobs (
                id TEXT PRIMARY KEY,
                experiment_id TEXT NOT NULL,
                status TEXT NOT NULL,
                progress_done INTEGER NOT NULL DEFAULT 0,
                progress_total INTEGER NOT NULL DEFAULT 0,
                current_hypothesis TEXT,
                error TEXT,
                started_at TEXT,
                finished_at TEXT,
                logs_json TEXT NOT NULL DEFAULT '[]'
             );
             CREATE TABLE IF NOT EXISTS hypotheses (
                experiment_id TEXT NOT NULL,
                condition TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                PRIMARY KEY (experiment_id, condition)
             );
             CREATE TABLE IF NOT EXISTS candidates (
                id TEXT PRIMARY KEY,
                experiment_id TEXT NOT NULL,
                condition TEXT NOT NULL,
                status TEXT NOT NULL,
                payload_json TEXT NOT NULL
             );
             CREATE TABLE IF NOT EXISTS promotions (
                id TEXT PRIMARY KEY,
                experiment_id TEXT NOT NULL,
                from_status TEXT NOT NULL,
                to_status TEXT NOT NULL,
                reason TEXT NOT NULL,
                created_at TEXT NOT NULL,
                created_by TEXT NOT NULL
             );
             CREATE TABLE IF NOT EXISTS job_logs (
                job_id TEXT NOT NULL,
                seq INTEGER NOT NULL,
                line TEXT NOT NULL,
                PRIMARY KEY (job_id, seq)
             );",
        )?;
        Ok(Self {
            conn: Mutex::new(conn),
        })
    }

    fn lock(&self) -> Result<std::sync::MutexGuard<'_, Connection>, EngineError> {
        self.conn
            .lock()
            .map_err(|_| EngineError::Store("mutex poisoned".into()))
    }

    pub fn upsert_dataset(&self, d: &DatasetRecord) -> Result<(), EngineError> {
        let conn = self.lock()?;
        conn.execute(
            "INSERT OR REPLACE INTO datasets
             (id, version, name, event_definition, source, features_sqlite, game_count,
              capabilities, quality, provenance, status)
             VALUES (?1,?2,?3,?4,?5,?6,?7,?8,?9,?10,?11)",
            params![
                d.id,
                d.version,
                d.name,
                d.event_definition,
                d.source,
                d.features_sqlite,
                d.game_count,
                d.capabilities.to_string(),
                d.quality.to_string(),
                d.provenance.to_string(),
                d.status
            ],
        )?;
        Ok(())
    }

    pub fn list_datasets(&self) -> Result<Vec<DatasetRecord>, EngineError> {
        let conn = self.lock()?;
        let mut stmt = conn.prepare(
            "SELECT id, version, name, event_definition, source, features_sqlite, game_count,
                    capabilities, quality, provenance, status FROM datasets ORDER BY id, version",
        )?;
        let rows = stmt.query_map([], |r| {
            Ok(DatasetRecord {
                id: r.get(0)?,
                version: r.get(1)?,
                name: r.get(2)?,
                event_definition: r.get(3)?,
                source: r.get(4)?,
                features_sqlite: r.get(5)?,
                game_count: r.get(6)?,
                capabilities: serde_json::from_str(&r.get::<_, String>(7)?).unwrap_or_default(),
                quality: serde_json::from_str(&r.get::<_, String>(8)?).unwrap_or_default(),
                provenance: serde_json::from_str(&r.get::<_, String>(9)?).unwrap_or_default(),
                status: r.get(10)?,
            })
        })?;
        Ok(rows.filter_map(|x| x.ok()).collect())
    }

    pub fn get_dataset(&self, id: &str, version: &str) -> Result<DatasetRecord, EngineError> {
        self.list_datasets()?
            .into_iter()
            .find(|d| d.id == id && d.version == version)
            .ok_or_else(|| EngineError::NotFound(format!("dataset {id}/{version}")))
    }

    pub fn upsert_strategy(&self, s: &StrategyRecord) -> Result<(), EngineError> {
        let conn = self.lock()?;
        conn.execute(
            "INSERT OR REPLACE INTO strategies
             (id, version, name, description, research_status, production_status)
             VALUES (?1,?2,?3,?4,?5,?6)",
            params![
                s.id,
                s.version,
                s.name,
                s.description,
                s.research_status,
                s.production_status
            ],
        )?;
        Ok(())
    }

    pub fn list_strategies(&self) -> Result<Vec<StrategyRecord>, EngineError> {
        let conn = self.lock()?;
        let mut stmt = conn.prepare(
            "SELECT id, version, name, description, research_status, production_status
             FROM strategies ORDER BY id",
        )?;
        let rows = stmt.query_map([], |r| {
            Ok(StrategyRecord {
                id: r.get(0)?,
                version: r.get(1)?,
                name: r.get(2)?,
                description: r.get(3)?,
                research_status: r.get(4)?,
                production_status: r.get(5)?,
            })
        })?;
        Ok(rows.filter_map(|x| x.ok()).collect())
    }

    pub fn insert_experiment(&self, rec: &ExperimentRecord) -> Result<(), EngineError> {
        let conn = self.lock()?;
        conn.execute(
            "INSERT INTO experiments
             (id, status, definition_json, created_at, updated_at, hypothesis_count,
              result_summary, artifact_dir)
             VALUES (?1,?2,?3,?4,?5,?6,?7,?8)",
            params![
                rec.id,
                rec.status,
                serde_json::to_string(&rec.definition)?,
                rec.created_at,
                rec.updated_at,
                rec.hypothesis_count,
                rec.result_summary.as_ref().map(ToString::to_string),
                rec.artifact_dir
            ],
        )?;
        Ok(())
    }

    pub fn update_experiment(&self, rec: &ExperimentRecord) -> Result<(), EngineError> {
        let conn = self.lock()?;
        conn.execute(
            "UPDATE experiments SET status=?2, definition_json=?3, updated_at=?4,
                hypothesis_count=?5, result_summary=?6, artifact_dir=?7
             WHERE id=?1",
            params![
                rec.id,
                rec.status,
                serde_json::to_string(&rec.definition)?,
                rec.updated_at,
                rec.hypothesis_count,
                rec.result_summary.as_ref().map(ToString::to_string),
                rec.artifact_dir
            ],
        )?;
        Ok(())
    }

    pub fn get_experiment(&self, id: &str) -> Result<ExperimentRecord, EngineError> {
        let conn = self.lock()?;
        conn.query_row(
            "SELECT id, status, definition_json, created_at, updated_at, hypothesis_count,
                    result_summary, artifact_dir FROM experiments WHERE id=?1",
            params![id],
            |r| {
                let def: String = r.get(2)?;
                let summary: Option<String> = r.get(6)?;
                Ok(ExperimentRecord {
                    id: r.get(0)?,
                    status: r.get(1)?,
                    definition: serde_json::from_str(&def).unwrap_or_default(),
                    created_at: r.get(3)?,
                    updated_at: r.get(4)?,
                    hypothesis_count: r.get(5)?,
                    result_summary: summary.and_then(|s| serde_json::from_str(&s).ok()),
                    artifact_dir: r.get(7)?,
                })
            },
        )
        .optional()?
        .ok_or_else(|| EngineError::NotFound(format!("experiment {id}")))
    }

    pub fn list_experiments(&self) -> Result<Vec<ExperimentRecord>, EngineError> {
        let conn = self.lock()?;
        let mut stmt = conn.prepare("SELECT id FROM experiments ORDER BY created_at DESC")?;
        let ids: Vec<String> = stmt
            .query_map([], |r| r.get(0))?
            .filter_map(|x| x.ok())
            .collect();
        drop(stmt);
        drop(conn);
        ids.into_iter().map(|id| self.get_experiment(&id)).collect()
    }

    pub fn upsert_job(&self, j: &JobRecord) -> Result<(), EngineError> {
        let conn = self.lock()?;
        conn.execute(
            "INSERT OR REPLACE INTO jobs
             (id, experiment_id, status, progress_done, progress_total, current_hypothesis,
              error, started_at, finished_at, logs_json)
             VALUES (?1,?2,?3,?4,?5,?6,?7,?8,?9,?10)",
            params![
                j.id,
                j.experiment_id,
                j.status,
                j.progress_done,
                j.progress_total,
                j.current_hypothesis,
                j.error,
                j.started_at,
                j.finished_at,
                serde_json::to_string(&j.logs)?
            ],
        )?;
        Ok(())
    }

    pub fn get_job(&self, id: &str) -> Result<JobRecord, EngineError> {
        let conn = self.lock()?;
        conn.query_row(
            "SELECT id, experiment_id, status, progress_done, progress_total, current_hypothesis,
                    error, started_at, finished_at, logs_json FROM jobs WHERE id=?1",
            params![id],
            |r| {
                let logs: String = r.get(9)?;
                Ok(JobRecord {
                    id: r.get(0)?,
                    experiment_id: r.get(1)?,
                    status: r.get(2)?,
                    progress_done: r.get(3)?,
                    progress_total: r.get(4)?,
                    current_hypothesis: r.get(5)?,
                    error: r.get(6)?,
                    started_at: r.get(7)?,
                    finished_at: r.get(8)?,
                    logs: serde_json::from_str(&logs).unwrap_or_default(),
                })
            },
        )
        .optional()?
        .ok_or_else(|| EngineError::NotFound(format!("job {id}")))
    }

    pub fn list_jobs(&self) -> Result<Vec<JobRecord>, EngineError> {
        let conn = self.lock()?;
        let mut stmt = conn.prepare("SELECT id FROM jobs ORDER BY id DESC")?;
        let ids: Vec<String> = stmt
            .query_map([], |r| r.get(0))?
            .filter_map(|x| x.ok())
            .collect();
        drop(stmt);
        drop(conn);
        ids.into_iter().map(|id| self.get_job(&id)).collect()
    }

    pub fn replace_hypotheses(
        &self,
        experiment_id: &str,
        rows: &[(String, serde_json::Value)],
    ) -> Result<(), EngineError> {
        let conn = self.lock()?;
        conn.execute(
            "DELETE FROM hypotheses WHERE experiment_id=?1",
            params![experiment_id],
        )?;
        for (cond, payload) in rows {
            conn.execute(
                "INSERT INTO hypotheses (experiment_id, condition, payload_json) VALUES (?1,?2,?3)",
                params![experiment_id, cond, payload.to_string()],
            )?;
        }
        Ok(())
    }

    pub fn list_hypotheses(
        &self,
        experiment_id: &str,
    ) -> Result<Vec<serde_json::Value>, EngineError> {
        let conn = self.lock()?;
        let mut stmt = conn.prepare(
            "SELECT payload_json FROM hypotheses WHERE experiment_id=?1 ORDER BY condition",
        )?;
        let rows = stmt.query_map(params![experiment_id], |r| r.get::<_, String>(0))?;
        let mut rows: Vec<serde_json::Value> = rows
            .filter_map(|x| x.ok())
            .filter_map(|s| serde_json::from_str(&s).ok())
            .collect();
        rows.sort_by_key(|v| v.get("rank").and_then(|r| r.as_u64()).unwrap_or(9_999));
        Ok(rows)
    }

    pub fn list_promotions_for(
        &self,
        experiment_id: &str,
    ) -> Result<Vec<PromotionRecord>, EngineError> {
        Ok(self
            .list_promotions()?
            .into_iter()
            .filter(|p| p.experiment_id == experiment_id)
            .collect())
    }

    pub fn upsert_candidate(
        &self,
        id: &str,
        experiment_id: &str,
        condition: &str,
        status: &str,
        payload: &serde_json::Value,
    ) -> Result<(), EngineError> {
        let conn = self.lock()?;
        conn.execute(
            "INSERT OR REPLACE INTO candidates (id, experiment_id, condition, status, payload_json)
             VALUES (?1,?2,?3,?4,?5)",
            params![id, experiment_id, condition, status, payload.to_string()],
        )?;
        Ok(())
    }

    pub fn list_candidates(&self) -> Result<Vec<serde_json::Value>, EngineError> {
        let conn = self.lock()?;
        let mut stmt = conn.prepare(
            "SELECT id, experiment_id, condition, status, payload_json FROM candidates ORDER BY id",
        )?;
        let rows = stmt.query_map([], |r| {
            Ok(serde_json::json!({
                "id": r.get::<_, String>(0)?,
                "experiment_id": r.get::<_, String>(1)?,
                "condition": r.get::<_, String>(2)?,
                "status": r.get::<_, String>(3)?,
                "payload": serde_json::from_str::<serde_json::Value>(&r.get::<_, String>(4)?)
                    .unwrap_or_default()
            }))
        })?;
        Ok(rows.filter_map(|x| x.ok()).collect())
    }

    pub fn insert_promotion(&self, p: &PromotionRecord) -> Result<(), EngineError> {
        let conn = self.lock()?;
        conn.execute(
            "INSERT INTO promotions
             (id, experiment_id, from_status, to_status, reason, created_at, created_by)
             VALUES (?1,?2,?3,?4,?5,?6,?7)",
            params![
                p.id,
                p.experiment_id,
                p.from_status,
                p.to_status,
                p.reason,
                p.created_at,
                p.created_by
            ],
        )?;
        Ok(())
    }

    pub fn list_promotions(&self) -> Result<Vec<PromotionRecord>, EngineError> {
        let conn = self.lock()?;
        let mut stmt = conn.prepare(
            "SELECT id, experiment_id, from_status, to_status, reason, created_at, created_by
             FROM promotions ORDER BY created_at DESC",
        )?;
        let rows = stmt.query_map([], |r| {
            Ok(PromotionRecord {
                id: r.get(0)?,
                experiment_id: r.get(1)?,
                from_status: r.get(2)?,
                to_status: r.get(3)?,
                reason: r.get(4)?,
                created_at: r.get(5)?,
                created_by: r.get(6)?,
            })
        })?;
        Ok(rows.filter_map(|x| x.ok()).collect())
    }

    pub fn upsert_model(&self, row: &serde_json::Value) -> Result<(), EngineError> {
        let conn = self.lock()?;
        conn.execute(
            "INSERT OR REPLACE INTO models
             (id, strategy_id, version, dataset_id, dataset_version, parameters, health, status, calibration_at)
             VALUES (?1,?2,?3,?4,?5,?6,?7,?8,?9)",
            params![
                row["id"].as_str().unwrap_or(""),
                row["strategy_id"].as_str().unwrap_or(""),
                row["version"].as_str().unwrap_or(""),
                row["dataset_id"].as_str().unwrap_or(""),
                row["dataset_version"].as_str().unwrap_or(""),
                row["parameters"].to_string(),
                row["health"].as_str().unwrap_or("UNKNOWN"),
                row["status"].as_str().unwrap_or("HYPOTHESIS"),
                row["calibration_at"].as_str()
            ],
        )?;
        Ok(())
    }

    pub fn list_models(&self) -> Result<Vec<serde_json::Value>, EngineError> {
        let conn = self.lock()?;
        let mut stmt = conn.prepare(
            "SELECT id, strategy_id, version, dataset_id, dataset_version, parameters, health, status, calibration_at
             FROM models ORDER BY id",
        )?;
        let rows = stmt.query_map([], |r| {
            Ok(serde_json::json!({
                "id": r.get::<_, String>(0)?,
                "strategy_id": r.get::<_, String>(1)?,
                "version": r.get::<_, String>(2)?,
                "dataset_id": r.get::<_, String>(3)?,
                "dataset_version": r.get::<_, String>(4)?,
                "parameters": serde_json::from_str::<serde_json::Value>(&r.get::<_, String>(5)?)
                    .unwrap_or_default(),
                "health": r.get::<_, String>(6)?,
                "status": r.get::<_, String>(7)?,
                "calibration_at": r.get::<_, Option<String>>(8)?,
            }))
        })?;
        Ok(rows.filter_map(|x| x.ok()).collect())
    }
}
