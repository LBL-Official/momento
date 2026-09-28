//! Momento Research Engine — datasets, experiments, jobs.
//!
//! Wraps `momento-research-features`. Does not submit live orders.

#![forbid(unsafe_code)]

pub mod catalog;
pub mod error;
pub mod import;
pub mod interfaces;
pub mod jobs;
pub mod orchestration;
pub mod paths;
pub mod promote;
pub mod quality;
pub mod store;
pub mod strategy;
pub mod types;

pub use error::EngineError;
pub use jobs::{JobService, RunExperimentRequest};
pub use paths::WorkspacePaths;
pub use store::EngineStore;
pub use types::{
    DatasetRecord, ExperimentDefinition, ExperimentRecord, JobRecord, LifecycleStatus,
    PromotionRecord, StrategyRecord,
};

/// Open (or create) the engine store and seed catalogs + imported B1 artifacts.
pub fn open_engine(root: impl AsRef<std::path::Path>) -> Result<EngineStore, EngineError> {
    let paths = WorkspacePaths::new(root);
    std::fs::create_dir_all(&paths.engine_dir)?;
    let store = EngineStore::open(&paths.engine_sqlite)?;
    catalog::seed(&store, &paths)?;
    import::import_first83_if_present(&store, &paths)?;
    Ok(store)
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::promote::allowed_transition;

    #[test]
    fn seed_registers_b1_and_imports_exhaustive() {
        let tmp = tempfile::tempdir().unwrap();
        let root = tmp.path();
        let src = WorkspacePaths::detect();
        let dest83 = root.join("Backtesting Suite/Foundation/B1/first83");
        std::fs::create_dir_all(&dest83).unwrap();
        for name in [
            "b1_83_universe.json",
            "b1_83_exhaustive_rankings.csv",
            "b1_83_search_summary.json",
        ] {
            let from = src.first83_dir.join(name);
            if from.exists() {
                std::fs::copy(&from, dest83.join(name)).unwrap();
            }
        }
        let store = open_engine(root).unwrap();
        let ds = store.get_dataset("B1_FIRST83", "v1").unwrap();
        assert_eq!(ds.game_count, Some(2906));
        let holdout = store.get_dataset("B1_FIRST83_PROSPECTIVE", "v1").unwrap();
        assert_eq!(holdout.version, "v1");
        assert_eq!(holdout.capabilities["l2"], false);
        assert_eq!(ds.capabilities["l2"], false);
        let strats = store.list_strategies().unwrap();
        assert!(
            strats
                .iter()
                .any(|s| s.id == "B1" && s.production_status == "NONE")
        );
        if src.first83_rankings.exists() {
            let exp = store
                .get_experiment("EXP_B1_FIRST83_EXHAUSTIVE_v1")
                .unwrap();
            assert_eq!(exp.status, "COMPLETED");
            let bench = &exp.result_summary.unwrap()["benchmark_40_49"];
            assert_eq!(bench["classification"], "CANDIDATE");
            assert!((bench["q_value"].as_f64().unwrap() - 0.1731).abs() < 0.001);
            let cands = store.list_candidates().unwrap();
            assert!(
                cands
                    .iter()
                    .any(|c| c["condition"] == "start_price_band=40_49")
            );
            assert!(
                cands
                    .iter()
                    .any(|c| c["condition"] == "inning_grp=7&p_max_vs_83=PEAK_AT")
            );
        }
    }

    #[test]
    fn promotion_gate() {
        assert!(!allowed_transition(
            LifecycleStatus::Candidate,
            LifecycleStatus::Production
        ));
    }

    #[test]
    fn quality_marks_l2_unavailable() {
        let q =
            crate::quality::first83_quality_from_sqlite(std::path::Path::new("/no/such.sqlite"));
        assert!(q.is_err());
    }

    #[test]
    fn custom_grid_and_reproduce_use_same_job_service() {
        let src = WorkspacePaths::detect();
        if !src.first83_sqlite.exists() {
            eprintln!("skip: first83 features.sqlite not present");
            return;
        }
        let tmp = tempfile::tempdir().unwrap();
        let dest83 = tmp.path().join("Backtesting Suite/Foundation/B1/first83");
        std::fs::create_dir_all(&dest83).unwrap();
        for name in [
            "b1_83_universe.json",
            "b1_83_exhaustive_rankings.csv",
            "b1_83_search_summary.json",
        ] {
            let from = src.first83_dir.join(name);
            if from.exists() {
                std::fs::copy(&from, dest83.join(name)).unwrap();
            }
        }
        let store = std::sync::Arc::new(open_engine(tmp.path()).unwrap());
        let mut ds = store.get_dataset("B1_FIRST83", "v1").unwrap();
        ds.features_sqlite = Some(src.first83_sqlite.display().to_string());
        store.upsert_dataset(&ds).unwrap();
        let jobs = JobService::new(store.clone(), WorkspacePaths::new(tmp.path()));
        let def = ExperimentDefinition {
            name: "acceptance custom grid".into(),
            parameters: vec![
                momento_research_features::ParameterSpec::list(
                    "start_price_band",
                    vec!["40_49".into()],
                ),
                momento_research_features::ParameterSpec::list("inning_grp", vec!["7".into()]),
                momento_research_features::ParameterSpec::list(
                    "p_max_vs_83",
                    vec!["PEAK_AT".into()],
                ),
                momento_research_features::ParameterSpec::list(
                    "vol_1m_tertile",
                    vec!["LOW".into()],
                ),
                momento_research_features::ParameterSpec::list(
                    "vol_15m_tertile",
                    vec!["LOW".into()],
                ),
            ],
            ..ExperimentDefinition::default()
        };
        let exp = jobs.create_experiment(def).unwrap();
        let copy = jobs.reproduce(&exp.id).unwrap();
        assert_eq!(
            copy.definition.parent_experiment_id.as_deref(),
            Some(exp.id.as_str())
        );
        assert_eq!(copy.definition.parameters.len(), 5);
        let job = jobs.queue_run(&exp.id).unwrap();
        let done = jobs.execute_job(&job.id).unwrap();
        assert_eq!(done.status, "COMPLETED");
        let finished = store.get_experiment(&exp.id).unwrap();
        assert_eq!(finished.status, "COMPLETED");
        let summary = finished.result_summary.unwrap();
        assert_eq!(summary["unconditional"]["train"]["n"], 1699);
        assert_eq!(summary["n_83"], 2906);
        assert_eq!(summary["fill_status"], "TRADE_PRINT_MODELED");
        assert_eq!(summary["hypotheses_requested"], 2);
        assert!(summary["hypotheses_executed"].as_u64().unwrap() >= 1);
        assert!(summary["number_of_tests"].as_u64().unwrap() < 20);
        let art = std::path::Path::new(finished.artifact_dir.as_ref().unwrap());
        assert!(art.join("summary.json").exists());
        assert!(art.join("config.json").exists());
        assert!(art.join("hypotheses.json").exists());
    }

    #[test]
    fn create_rejects_leaking_split() {
        let tmp = tempfile::tempdir().unwrap();
        let store = open_engine(tmp.path()).unwrap();
        let jobs = JobService::new(std::sync::Arc::new(store), WorkspacePaths::new(tmp.path()));
        let def = ExperimentDefinition {
            train_before: "2026-05-03".into(),
            val_before: "2025-10-07".into(),
            ..ExperimentDefinition::default()
        };
        let err = jobs.create_experiment(def).unwrap_err();
        assert!(err.to_string().contains("TRAIN"));
    }
}
