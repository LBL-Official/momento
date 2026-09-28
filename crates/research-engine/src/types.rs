use serde::{Deserialize, Serialize};

use momento_research_features::configured_search::ParameterSpec;

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum LifecycleStatus {
    Draft,
    Running,
    Completed,
    Failed,
    Hypothesis,
    Candidate,
    RobustCandidate,
    Paper,
    Shadow,
    Approved,
    Production,
    Retired,
    Rejected,
}

impl LifecycleStatus {
    pub fn as_str(self) -> &'static str {
        match self {
            Self::Draft => "DRAFT",
            Self::Running => "RUNNING",
            Self::Completed => "COMPLETED",
            Self::Failed => "FAILED",
            Self::Hypothesis => "HYPOTHESIS",
            Self::Candidate => "CANDIDATE",
            Self::RobustCandidate => "ROBUST_CANDIDATE",
            Self::Paper => "PAPER",
            Self::Shadow => "SHADOW",
            Self::Approved => "APPROVED",
            Self::Production => "PRODUCTION",
            Self::Retired => "RETIRED",
            Self::Rejected => "REJECTED",
        }
    }

    pub fn parse(s: &str) -> Option<Self> {
        Some(match s {
            "DRAFT" => Self::Draft,
            "RUNNING" => Self::Running,
            "COMPLETED" => Self::Completed,
            "FAILED" => Self::Failed,
            "HYPOTHESIS" => Self::Hypothesis,
            "CANDIDATE" => Self::Candidate,
            "ROBUST_CANDIDATE" => Self::RobustCandidate,
            "PAPER" => Self::Paper,
            "SHADOW" => Self::Shadow,
            "APPROVED" => Self::Approved,
            "PRODUCTION" => Self::Production,
            "RETIRED" => Self::Retired,
            "REJECTED" => Self::Rejected,
            _ => return None,
        })
    }
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct ExperimentDefinition {
    pub name: String,
    pub description: String,
    pub tags: Vec<String>,
    pub dataset_id: String,
    pub dataset_version: String,
    pub strategy_id: String,
    pub strategy_version: String,
    pub feature_set: String,
    pub parameters: Vec<ParameterSpec>,
    pub train_before: String,
    pub val_before: String,
    pub test_end: Option<String>,
    pub execution_model: String,
    pub fees_cents: i32,
    pub slippage_cents: i32,
    pub position_qty: Option<i32>,
    pub capital_cents: i32,
    pub search_method: String,
    pub fdr_method: String,
    pub fdr_alpha: f64,
    pub min_train: usize,
    pub min_val: usize,
    pub min_test: usize,
    pub random_seed: u64,
    pub created_by: String,
    pub parent_experiment_id: Option<String>,
}

impl Default for ExperimentDefinition {
    fn default() -> Self {
        Self {
            name: "untitled".into(),
            description: String::new(),
            tags: Vec::new(),
            dataset_id: "B1_FIRST83".into(),
            dataset_version: "v1".into(),
            strategy_id: "B1".into(),
            strategy_version: "B1.ENGINE.1.1.0".into(),
            feature_set: "B1.FEATURE.1.1.0".into(),
            parameters: Vec::new(),
            train_before: momento_research_features::TRAIN_BEFORE.into(),
            val_before: momento_research_features::VAL_BEFORE.into(),
            test_end: Some(momento_research_features::TEST_END_OBSERVED.into()),
            execution_model: "TRADE_PRINT_MODELED".into(),
            fees_cents: 0,
            slippage_cents: 0,
            position_qty: Some(7),
            capital_cents: 5000,
            search_method: "grid".into(),
            fdr_method: "benjamini_hochberg".into(),
            fdr_alpha: 0.10,
            min_train: 50,
            min_val: 10,
            min_test: 15,
            random_seed: 42,
            created_by: "local".into(),
            parent_experiment_id: None,
        }
    }
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct DatasetRecord {
    pub id: String,
    pub version: String,
    pub name: String,
    pub event_definition: String,
    pub source: String,
    pub features_sqlite: Option<String>,
    pub game_count: Option<i64>,
    pub capabilities: serde_json::Value,
    pub quality: serde_json::Value,
    pub provenance: serde_json::Value,
    pub status: String,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct StrategyRecord {
    pub id: String,
    pub version: String,
    pub name: String,
    pub description: String,
    pub research_status: String,
    pub production_status: String,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct ExperimentRecord {
    pub id: String,
    pub status: String,
    pub definition: ExperimentDefinition,
    pub created_at: String,
    pub updated_at: String,
    pub hypothesis_count: i64,
    pub result_summary: Option<serde_json::Value>,
    pub artifact_dir: Option<String>,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct JobRecord {
    pub id: String,
    pub experiment_id: String,
    pub status: String,
    pub progress_done: i64,
    pub progress_total: i64,
    pub current_hypothesis: Option<String>,
    pub error: Option<String>,
    pub started_at: Option<String>,
    pub finished_at: Option<String>,
    pub logs: Vec<String>,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct PromotionRecord {
    pub id: String,
    pub experiment_id: String,
    pub from_status: String,
    pub to_status: String,
    pub reason: String,
    pub created_at: String,
    pub created_by: String,
}
