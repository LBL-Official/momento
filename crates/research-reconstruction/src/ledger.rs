//! CTO-W3-A#-S# ledger. Not auto-completed.

use serde::{Deserialize, Serialize};

use crate::versions::LEDGER_VERSION;

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum StepEvidenceStatus {
    NotStarted,
    EvidenceRecorded,
    Blocked,
    Unavailable,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct LedgerStep {
    pub id: String,
    pub title: String,
    pub status: StepEvidenceStatus,
    pub evidence: String,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct W3Ledger {
    pub ledger_version: String,
    pub note: String,
    pub steps: Vec<LedgerStep>,
}

pub fn empty_ledger() -> W3Ledger {
    let ids = [
        ("CTO-W3-A1-S1", "source contract (consume committed only)"),
        ("CTO-W3-A1-S2", "committed-artifact gate"),
        ("CTO-W3-A1-S3", "provenance retained on events"),
        ("CTO-W3-A1-S4", "checksum verification"),
        ("CTO-W3-A2-S1", "game identity extraction"),
        ("CTO-W3-A2-S2", "official gamePk validation"),
        ("CTO-W3-A2-S3", "unmatched handling"),
        ("CTO-W3-A2-S4", "ambiguous handling"),
        ("CTO-W3-A3-S1", "event parsing (W2 parser)"),
        ("CTO-W3-A3-S2", "event ordering"),
        ("CTO-W3-A3-S3", "timestamps (PBP official ≠ retrieved_at)"),
        ("CTO-W3-A3-S4", "event provenance"),
        ("CTO-W3-A3-S5", "malformed-event handling"),
        ("CTO-W3-A4-S1", "game metadata"),
        ("CTO-W3-A4-S2", "inning progression"),
        ("CTO-W3-A4-S3", "score"),
        ("CTO-W3-A4-S4", "outs"),
        ("CTO-W3-A4-S5", "count"),
        ("CTO-W3-A4-S6", "bases/runners"),
        ("CTO-W3-A4-S7", "batter/pitcher state"),
        ("CTO-W3-A5-S1", "replay engine (W2 state machine)"),
        ("CTO-W3-A5-S2", "state transitions"),
        ("CTO-W3-A5-S3", "no-lookahead"),
        ("CTO-W3-A5-S4", "deterministic output"),
        ("CTO-W3-A6-S1", "2024–2025 processing"),
        ("CTO-W3-A6-S2", "2025–2026 processing"),
        ("CTO-W3-A6-S3", "current/incremental processing"),
        ("CTO-W3-A6-S4", "coverage reporting"),
        ("CTO-W3-A7-S1", "idempotency"),
        ("CTO-W3-A7-S2", "duplicate handling"),
        ("CTO-W3-A7-S3", "conflict handling"),
        ("CTO-W3-A7-S4", "anomaly reporting"),
        ("CTO-W3-A8-S1", "fixtures"),
        ("CTO-W3-A8-S2", "unit tests"),
        ("CTO-W3-A8-S3", "integration tests"),
        ("CTO-W3-A8-S4", "real-data validation"),
        ("CTO-W3-A8-S5", "workspace-relevant validation"),
        ("CTO-W3-A9-S1", "evidence package"),
        ("CTO-W3-A9-S2", "coverage report"),
        ("CTO-W3-A9-S3", "limitations"),
        ("CTO-W3-A9-S4", "W4 handoff"),
        ("CTO-W3-A9-S5", "CTO acceptance package"),
    ];
    W3Ledger {
        ledger_version: LEDGER_VERSION.into(),
        note: "Statuses are evidence-only. This file is never batch-marked COMPLETE.".into(),
        steps: ids
            .iter()
            .map(|(id, title)| LedgerStep {
                id: (*id).into(),
                title: (*title).into(),
                status: StepEvidenceStatus::NotStarted,
                evidence: String::new(),
            })
            .collect(),
    }
}

impl W3Ledger {
    pub fn record(&mut self, id: &str, status: StepEvidenceStatus, evidence: impl Into<String>) {
        if let Some(step) = self.steps.iter_mut().find(|s| s.id == id) {
            step.status = status;
            step.evidence = evidence.into();
        }
    }
}
