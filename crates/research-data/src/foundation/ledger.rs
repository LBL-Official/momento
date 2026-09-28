//! Machine-readable W1 progress ledger (W1-A* / S*).

use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};

use super::{ARTIFACT_VERSION, WATERFALL};

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum StepStatus {
    NotStarted,
    InProgress,
    Complete,
    Blocked,
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct StepSpec {
    pub id: &'static str,
    pub activity: &'static str,
    pub objective: &'static str,
}

pub const W1_STEPS: &[StepSpec] = &[
    StepSpec {
        id: "W1-LEDGER-A1-S1",
        activity: "W1-A1",
        objective: "Discover lake roots (Data-Real, Data demo, repo placeholders)",
    },
    StepSpec {
        id: "W1-LEDGER-A1-S2",
        activity: "W1-A1",
        objective: "Classify file types (raw gzip, parquet, manifests, sheets, runs)",
    },
    StepSpec {
        id: "W1-LEDGER-A1-S3",
        activity: "W1-A1",
        objective: "Count files / bytes / partition dates without modifying them",
    },
    StepSpec {
        id: "W1-LEDGER-A1-S4",
        activity: "W1-A1",
        objective: "Emit source inventory rows",
    },
    StepSpec {
        id: "W1-LEDGER-A2-S1",
        activity: "W1-A2",
        objective: "Define timestamp roles (ingestion vs exchange vs candle end)",
    },
    StepSpec {
        id: "W1-LEDGER-A2-S2",
        activity: "W1-A2",
        objective: "Define provenance record contract",
    },
    StepSpec {
        id: "W1-LEDGER-A2-S3",
        activity: "W1-A2",
        objective: "Map v1 RawMarketEvent fields into provenance + envelope v2",
    },
    StepSpec {
        id: "W1-LEDGER-A3-S1",
        activity: "W1-A3",
        objective: "SHA-256 verify files against v1 manifests",
    },
    StepSpec {
        id: "W1-LEDGER-A3-S2",
        activity: "W1-A3",
        objective: "Gzip decompress + JSONL parse (malformed detection)",
    },
    StepSpec {
        id: "W1-LEDGER-A3-S3",
        activity: "W1-A3",
        objective: "Parquet readability + schema consistency",
    },
    StepSpec {
        id: "W1-LEDGER-A3-S4",
        activity: "W1-A3",
        objective: "Ticker / game-market pairing integrity",
    },
    StepSpec {
        id: "W1-LEDGER-A3-S5",
        activity: "W1-A3",
        objective: "Chronological sanity (no silent reorder)",
    },
    StepSpec {
        id: "W1-LEDGER-A3-S6",
        activity: "W1-A3",
        objective: "Emit anomaly report (no raw repairs)",
    },
    StepSpec {
        id: "W1-LEDGER-A4-S1",
        activity: "W1-A4",
        objective: "Install coverage vocabulary (do not redefine v1 COMPLETE)",
    },
    StepSpec {
        id: "W1-LEDGER-A4-S2",
        activity: "W1-A4",
        objective: "Apply dimension coverage (L2/PBP/lifetime/starting price)",
    },
    StepSpec {
        id: "W1-LEDGER-A4-S3",
        activity: "W1-A4",
        objective: "Write coverage matrix",
    },
    StepSpec {
        id: "W1-LEDGER-A5-S1",
        activity: "W1-A5",
        objective: "Quantify 2025 MLB local availability",
    },
    StepSpec {
        id: "W1-LEDGER-A5-S2",
        activity: "W1-A5",
        objective: "Quantify 2026 MLB local availability",
    },
    StepSpec {
        id: "W1-LEDGER-A5-S3",
        activity: "W1-A5",
        objective: "Layer matrix (metadata/trades/candles/L2/settlement/open)",
    },
    StepSpec {
        id: "W1-LEDGER-A5-S4",
        activity: "W1-A5",
        objective: "Document recovery queries without launching collection",
    },
    StepSpec {
        id: "W1-LEDGER-A6-S1",
        activity: "W1-A6",
        objective: "Canonical lake catalog schema",
    },
    StepSpec {
        id: "W1-LEDGER-A6-S2",
        activity: "W1-A6",
        objective: "Per GameId/MarketId evidence index",
    },
    StepSpec {
        id: "W1-LEDGER-A6-S3",
        activity: "W1-A6",
        objective: "Write versioned canonical manifest",
    },
    StepSpec {
        id: "W1-LEDGER-A7-S1",
        activity: "W1-A7",
        objective: "Observability enum + field contract",
    },
    StepSpec {
        id: "W1-LEDGER-A7-S2",
        activity: "W1-A7",
        objective: "Attach observability to catalog/coverage rows",
    },
    StepSpec {
        id: "W1-LEDGER-A8-S1",
        activity: "W1-A8",
        objective: "Local W1 artifact package (Drive is archive, not DB)",
    },
    StepSpec {
        id: "W1-LEDGER-A8-S2",
        activity: "W1-A8",
        objective: "Sheets index CSV with required header fields",
    },
    StepSpec {
        id: "W1-LEDGER-A8-S3",
        activity: "W1-A8",
        objective: "Google publish status (PENDING if not uploaded)",
    },
    StepSpec {
        id: "W1-LEDGER-A9-S1",
        activity: "W1-A9",
        objective: "Lake content digest + idempotent derived outputs",
    },
    StepSpec {
        id: "W1-LEDGER-A9-S2",
        activity: "W1-A9",
        objective: "Overwrite guard against the immutable lake",
    },
    StepSpec {
        id: "W1-LEDGER-A10-S1",
        activity: "W1-A10",
        objective: "Automated acceptance checklist",
    },
    StepSpec {
        id: "W1-LEDGER-A10-S2",
        activity: "W1-A10",
        objective: "Production fence (no risk/execution/strategy deps)",
    },
];

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct LedgerStep {
    pub id: String,
    pub activity: String,
    pub objective: String,
    pub status: StepStatus,
    pub evidence: String,
    pub next_step: String,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct WaterfallLedger {
    pub waterfall: String,
    pub artifact_version: String,
    pub generated_at: DateTime<Utc>,
    pub run_id: String,
    pub status: StepStatus,
    pub steps: Vec<LedgerStep>,
}

impl WaterfallLedger {
    pub fn new(run_id: String, generated_at: DateTime<Utc>) -> Self {
        let steps: Vec<LedgerStep> = W1_STEPS
            .iter()
            .enumerate()
            .map(|(i, spec)| {
                let next = W1_STEPS
                    .get(i + 1)
                    .map(|s| s.id)
                    .unwrap_or("STOP — do not begin W2");
                LedgerStep {
                    id: spec.id.to_string(),
                    activity: spec.activity.to_string(),
                    objective: spec.objective.to_string(),
                    status: StepStatus::NotStarted,
                    evidence: String::new(),
                    next_step: next.to_string(),
                }
            })
            .collect();
        Self {
            waterfall: WATERFALL.to_string(),
            artifact_version: ARTIFACT_VERSION.to_string(),
            generated_at,
            run_id,
            status: StepStatus::InProgress,
            steps,
        }
    }

    pub fn complete_step(&mut self, id: &str, evidence: impl Into<String>) {
        if let Some(step) = self.steps.iter_mut().find(|s| s.id == id) {
            step.status = StepStatus::Complete;
            step.evidence = evidence.into();
        }
    }

    pub fn all_complete(&self) -> bool {
        self.steps.iter().all(|s| s.status == StepStatus::Complete)
    }
}
