//! Research clocks. Manual only in v1. Never auto-trades.

use serde::Serialize;

#[derive(Clone, Debug, Serialize)]
pub struct ResearchClock {
    pub id: &'static str,
    pub cadence: &'static str,
    pub enabled: bool,
    pub note: &'static str,
}

pub fn research_clocks() -> Vec<ResearchClock> {
    vec![
        ResearchClock {
            id: "MARKET_STATE",
            cadence: "continuous",
            enabled: false,
            note: "Live feed is not wired into the research engine.",
        },
        ResearchClock {
            id: "FEATURE_UPDATE",
            cadence: "continuous",
            enabled: false,
            note: "B1 snapshots are versioned extracts, not a live feature stream.",
        },
        ResearchClock {
            id: "PARAMETER_RECALIBRATION",
            cadence: "periodic",
            enabled: false,
            note: "Create a new experiment. Do not overwrite a completed one.",
        },
        ResearchClock {
            id: "MODEL_HEALTH",
            cadence: "periodic",
            enabled: false,
            note: "Health states exist; B1 formulas are not invented.",
        },
        ResearchClock {
            id: "RESEARCH_SWEEP",
            cadence: "manual",
            enabled: false,
            note: "Trigger with POST /api/experiments/{id}/run or momento-research-b1 --run-experiment.",
        },
    ]
}

pub fn orchestration_snapshot() -> serde_json::Value {
    serde_json::json!({
        "auto_trade": false,
        "auto_promote": false,
        "live_execution": false,
        "clocks": research_clocks()
    })
}
