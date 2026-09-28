use std::collections::HashMap;
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::{Arc, Mutex};

use chrono::Utc;
use uuid::Uuid;

use momento_research_features::configured_search::{
    ConfiguredSearchSpec, estimate_hypothesis_count, run_configured_search_with_progress,
};

use crate::error::EngineError;
use crate::paths::WorkspacePaths;
use crate::store::EngineStore;
use crate::types::{ExperimentDefinition, ExperimentRecord, JobRecord};

pub struct RunExperimentRequest {
    pub definition: ExperimentDefinition,
}

pub struct JobService {
    pub store: Arc<EngineStore>,
    pub paths: WorkspacePaths,
    cancels: Mutex<HashMap<String, Arc<AtomicBool>>>,
}

impl JobService {
    pub fn new(store: Arc<EngineStore>, paths: WorkspacePaths) -> Self {
        Self {
            store,
            paths,
            cancels: Mutex::new(HashMap::new()),
        }
    }

    pub fn create_experiment(
        &self,
        def: ExperimentDefinition,
    ) -> Result<ExperimentRecord, EngineError> {
        if def.train_before >= def.val_before {
            return Err(EngineError::validation(
                "SPLIT",
                "TRAIN cut must be strictly before VAL cut. TEST is locked after VAL.",
            ));
        }
        if def.search_method == "grid" || def.search_method == "single" {
            let _ = estimate_hypothesis_count(&def.parameters);
        }
        let now = Utc::now().to_rfc3339();
        let rec = ExperimentRecord {
            id: format!("EXP_{}", Uuid::new_v4().simple()),
            status: "DRAFT".into(),
            hypothesis_count: estimate_hypothesis_count(&def.parameters) as i64,
            definition: def,
            created_at: now.clone(),
            updated_at: now,
            result_summary: None,
            artifact_dir: None,
        };
        self.store.insert_experiment(&rec)?;
        Ok(rec)
    }

    pub fn reproduce(&self, experiment_id: &str) -> Result<ExperimentRecord, EngineError> {
        let src = self.store.get_experiment(experiment_id)?;
        let mut def = src.definition;
        def.parent_experiment_id = Some(src.id);
        def.name = format!("{} (reproduce)", def.name);
        self.create_experiment(def)
    }

    pub fn queue_run(&self, experiment_id: &str) -> Result<JobRecord, EngineError> {
        let exp = self.store.get_experiment(experiment_id)?;
        if exp.status == "RUNNING" {
            return Err(EngineError::validation(
                "ALREADY_RUNNING",
                "experiment already running",
            ));
        }
        let n = estimate_hypothesis_count(&exp.definition.parameters) as i64;
        let job = JobRecord {
            id: format!("JOB_{}", Uuid::new_v4().simple()),
            experiment_id: experiment_id.into(),
            status: "QUEUED".into(),
            progress_done: 0,
            progress_total: n.max(1),
            current_hypothesis: None,
            error: None,
            started_at: None,
            finished_at: None,
            logs: vec![format!(
                "queued experiment {} hypotheses≈{}",
                experiment_id, n
            )],
        };
        self.store.upsert_job(&job)?;
        Ok(job)
    }

    pub fn request_cancel(&self, job_id: &str) -> Result<JobRecord, EngineError> {
        let mut job = self.store.get_job(job_id)?;
        if let Ok(map) = self.cancels.lock() {
            if let Some(flag) = map.get(job_id) {
                flag.store(true, Ordering::SeqCst);
            }
        }
        if job.status == "QUEUED" || job.status == "RUNNING" {
            job.status = "CANCEL_REQUESTED".into();
            job.logs.push("cancel requested".into());
            self.store.upsert_job(&job)?;
        }
        Ok(job)
    }

    /// Blocking run. The API layer should spawn this on a worker thread.
    pub fn execute_job(&self, job_id: &str) -> Result<JobRecord, EngineError> {
        let mut job = self.store.get_job(job_id)?;
        let mut exp = self.store.get_experiment(&job.experiment_id)?;
        let flag = Arc::new(AtomicBool::new(false));
        if let Ok(mut map) = self.cancels.lock() {
            map.insert(job_id.to_string(), flag.clone());
        }
        job.status = "RUNNING".into();
        job.started_at = Some(Utc::now().to_rfc3339());
        job.logs.push("worker started".into());
        self.store.upsert_job(&job)?;
        exp.status = "RUNNING".into();
        exp.updated_at = Utc::now().to_rfc3339();
        self.store.update_experiment(&exp)?;

        let dataset = self
            .store
            .get_dataset(&exp.definition.dataset_id, &exp.definition.dataset_version)?;
        let sqlite = dataset
            .features_sqlite
            .as_ref()
            .map(std::path::PathBuf::from)
            .filter(|p| p.exists())
            .or_else(|| {
                if self.paths.first83_sqlite.exists() {
                    Some(self.paths.first83_sqlite.clone())
                } else {
                    None
                }
            })
            .ok_or_else(|| {
                EngineError::validation(
                    "NO_SQLITE",
                    "B1 first83 features.sqlite is missing; extract it with momento-research-b1 --extract-first83",
                )
            })?;

        job.logs
            .push(format!("dataset sqlite {}", sqlite.display()));
        job.current_hypothesis = Some("preparing universe".into());
        self.store.upsert_job(&job)?;

        let spec = ConfiguredSearchSpec {
            features_sqlite: sqlite,
            train_before: exp.definition.train_before.clone(),
            val_before: exp.definition.val_before.clone(),
            parameters: exp.definition.parameters.clone(),
            include_unconditional: true,
            min_train: exp.definition.min_train,
            min_val: exp.definition.min_val,
            min_test: exp.definition.min_test,
            fdr_alpha: exp.definition.fdr_alpha,
        };

        let store = self.store.clone();
        let jid = job_id.to_string();
        let result = run_configured_search_with_progress(&spec, |done, total, label| {
            if flag.load(Ordering::SeqCst) {
                return Err(momento_research_features::B1Error::validation(
                    "CANCELLED",
                    "job cancelled",
                ));
            }
            if let Ok(mut j) = store.get_job(&jid) {
                j.progress_done = done as i64;
                j.progress_total = total.max(1) as i64;
                j.current_hypothesis = Some(label.to_string());
                if done % 5 == 0 || label == "ALL_83" {
                    j.logs.push(format!("eval {done}/{total} {label}"));
                    if j.logs.len() > 200 {
                        j.logs = j.logs.split_off(j.logs.len() - 160);
                    }
                }
                let _ = store.upsert_job(&j);
            }
            Ok(())
        });

        if let Ok(mut map) = self.cancels.lock() {
            map.remove(job_id);
        }

        match result {
            Ok(report) => {
                let art = self.paths.artifacts_dir.join(&exp.id);
                std::fs::create_dir_all(&art)?;
                std::fs::write(
                    art.join("summary.json"),
                    serde_json::to_string_pretty(&report)?,
                )?;
                std::fs::write(
                    art.join("config.json"),
                    serde_json::to_string_pretty(&exp.definition)?,
                )?;
                std::fs::write(
                    art.join("experiment.json"),
                    serde_json::to_string_pretty(&serde_json::json!({
                        "id": exp.id,
                        "definition": exp.definition,
                    }))?,
                )?;
                std::fs::write(
                    art.join("hypotheses.json"),
                    serde_json::to_string_pretty(&report.hypotheses)?,
                )?;
                std::fs::write(
                    art.join("equity_curve.json"),
                    serde_json::to_string_pretty(&report.unconditional.equity)?,
                )?;
                let hyps: Vec<(String, serde_json::Value)> = report
                    .hypotheses
                    .iter()
                    .map(|h| {
                        (
                            h.condition.clone(),
                            serde_json::to_value(h).unwrap_or_default(),
                        )
                    })
                    .collect();
                self.store.replace_hypotheses(&exp.id, &hyps)?;
                for h in &report.hypotheses {
                    if matches!(
                        h.classification.as_str(),
                        "CANDIDATE" | "ROBUST" | "CANDIDATE_THIN_VALIDATION"
                    ) {
                        self.store.upsert_candidate(
                            &format!("CAND_{}_{}", exp.id, h.condition.replace(['=', '&'], "_")),
                            &exp.id,
                            &h.condition,
                            &h.classification,
                            &serde_json::to_value(h)?,
                        )?;
                    }
                }
                let summary = serde_json::json!({
                    "imported": false,
                    "number_of_tests": report.number_of_tests,
                    "hypotheses_requested": report.hypotheses_requested,
                    "hypotheses_executed": report.hypotheses_executed,
                    "hypotheses_excluded": report.hypotheses_excluded,
                    "fdr_method": report.fdr_method,
                    "fdr_alpha": report.fdr_alpha,
                    "fill_status": report.fill_status,
                    "unconditional": report.unconditional,
                    "n_83": report.n_83,
                    "split": {
                        "train_before": report.train_before,
                        "val_before": report.val_before,
                        "test_end": report.test_end
                    },
                    "fees_cents": exp.definition.fees_cents,
                    "slippage_cents": exp.definition.slippage_cents,
                    "execution_model": exp.definition.execution_model,
                    "note": "FDR q is relative to this experiment's search space, not the imported 6,128-test exhaustive run."
                });
                exp.status = "COMPLETED".into();
                exp.updated_at = Utc::now().to_rfc3339();
                exp.hypothesis_count = report.hypotheses_executed as i64;
                exp.result_summary = Some(summary);
                exp.artifact_dir = Some(art.display().to_string());
                self.store.update_experiment(&exp)?;
                job = self.store.get_job(job_id)?;
                job.status = "COMPLETED".into();
                job.progress_done = job.progress_total;
                job.current_hypothesis = Some("done".into());
                job.finished_at = Some(Utc::now().to_rfc3339());
                job.logs.push(format!(
                    "completed n_83={} tests={}",
                    report.n_83, report.number_of_tests
                ));
            }
            Err(e) => {
                let cancelled = e.to_string().contains("CANCELLED");
                exp.status = if cancelled { "DRAFT" } else { "FAILED" }.into();
                exp.updated_at = Utc::now().to_rfc3339();
                self.store.update_experiment(&exp)?;
                job = self.store.get_job(job_id).unwrap_or(job);
                job.status = if cancelled { "CANCELLED" } else { "FAILED" }.into();
                job.error = Some(e.to_string());
                job.finished_at = Some(Utc::now().to_rfc3339());
                job.logs.push(format!("stopped: {e}"));
            }
        }
        self.store.upsert_job(&job)?;
        Ok(job)
    }
}
