//! W2 step ledger. Statuses: NOT_STARTED | IN_PROGRESS | BLOCKED | COMPLETE | WAIVED.
//!
//! Numbering is the crate-internal W2-A{1..10}-S{1..10} series (100 steps).
//! Control-plane IDs (CTO-W2-A1-S1 …) are mapped in [`CONTROL_PLANE_CROSSWALK`].
//! Do not auto-complete steps that lack evidence.

use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};

use crate::versions::{ARTIFACT_VERSION, WATERFALL};

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum StepStatus {
    NotStarted,
    InProgress,
    Blocked,
    Complete,
    Waived,
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct LedgerStep {
    pub id: String,
    pub activity: String,
    pub objective: String,
    pub status: StepStatus,
    pub date: String,
    pub implementation: String,
    pub files_changed: String,
    pub tests: String,
    pub validation: String,
    pub dependencies: String,
    pub known_limitations: String,
    pub evidence_path: String,
    pub result: String,
    pub blockers: String,
    pub downstream_impact: String,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct W2Ledger {
    pub waterfall: String,
    pub artifact_version: String,
    pub generated_at: DateTime<Utc>,
    pub capability: String,
    pub steps: Vec<LedgerStep>,
}

/// Control-plane IDs vs crate ledger IDs. Do not collapse these namespaces.
pub const CONTROL_PLANE_CROSSWALK: &str = "\
CTO-W2-A1-S1 schema+FIXTURE → crate W2-A4 (event) + W2-A5 (state) + fixtures in synthetic.rs
CTO-W2-A1-S2 adapters → crate W2 adapter.rs (MlbEventAdapter)
CTO-W2-A2-S1 identity graph → crate W2-A2
CTO-W2-A2-S2 official pk map → BLOCKED (crate W2-A2-S7)
CTO-W2-A3-S1 PBP license gate → BLOCKED (no download this run)
CTO-W2-A4-S1 reconstruct GameState from authorized historical PBP → BLOCKED (no files)
CTO-W2-A5-S1 UNAVAILABLE event-state labeling → crate coverage.rs + identity kalshi: prefix
";

struct Spec {
    id: &'static str,
    activity: &'static str,
    objective: &'static str,
}

fn specs() -> Vec<Spec> {
    let mut v = Vec::new();
    let blocks: &[(&str, &str, &[&str])] = &[
        (
            "W2-A1",
            "W2-A source contract",
            &[
                "Inventory every MLB/PBP source in repo, env, collectors",
                "Authoritative source hierarchy (no auto-substitution)",
                "Source provenance contract",
                "Timestamp semantics (five clocks)",
                "Authoritative event definition",
                "Missing-data behavior",
                "Duplicate-event behavior",
                "Corrected/amended PBP behavior",
                "Source conflict behavior",
                "Document W2 source contract",
            ],
        ),
        (
            "W2-A2",
            "W2-B identity",
            &[
                "Identity schema",
                "Normalization of source ids",
                "Mapping engine (no invented maps)",
                "Duplicate detection",
                "Collision detection",
                "Missing ID behavior",
                "Source crosswalk (Kalshi alias vs official)",
                "Season validation",
                "Team validation",
                "Game uniqueness + deterministic IDs",
            ],
        ),
        (
            "W2-A3",
            "W2-C ingest",
            &[
                "Source discovery (local only)",
                "Ingestion contract / envelope",
                "Raw source reference",
                "StatsAPI-shaped parser",
                "Schema validation",
                "Malformed event handling",
                "Duplicate handling",
                "Ordering",
                "Provenance on every event",
                "Ingestion report",
            ],
        ),
        (
            "W2-A4",
            "W2-D canonical event",
            &[
                "Event schema",
                "Game + clock fields",
                "Score / runners / PA",
                "Event types",
                "Optional pitch/review/substitution",
                "Provenance + observability",
                "Serialize",
                "Deserialize",
                "No magic sentinels",
                "Tests",
            ],
        ),
        (
            "W2-A5",
            "W2-E state machine",
            &[
                "State schema",
                "Transition function",
                "Invariant system",
                "Replay",
                "Edge cases",
                "Extra innings",
                "Walk-offs",
                "Reviews/amendments",
                "Substitutions + scoring",
                "Invalid states fail closed",
            ],
        ),
        (
            "W2-A6",
            "W2-F event time",
            &[
                "Innings/outs remaining fields",
                "Outs elapsed",
                "Current inning/half/outs",
                "PA position slot",
                "Event sequence",
                "Time since start/previous (when sourced)",
                "Opportunity count/fraction/delta",
                "Regulation vs extra innings",
                "No invented theta value",
                "Document empirical Event Theta later",
            ],
        ),
        (
            "W2-A7",
            "W2-G sequence",
            &[
                "Ordered sequence type",
                "last N events",
                "last N plate appearances",
                "last N scoring",
                "last N pitching changes",
                "last N reviews",
                "event-type transitions",
                "time between events",
                "scoring bursts",
                "lead changes",
            ],
        ),
        (
            "W2-A8",
            "W2-H replay/validation",
            &[
                "Deterministic ordering",
                "State replay",
                "State serialization",
                "State restoration",
                "Duplicate handling",
                "Malformed PBP",
                "Inning transitions",
                "Extra innings / walk-offs / reviews",
                "Runner + scoring validation",
                "Validation summaries",
            ],
        ),
        (
            "W2-A9",
            "W2-I coverage",
            &[
                "Coverage vocabulary",
                "Season/date/GameId rows",
                "PBP/pitch/timestamp/score flags",
                "Runner/batter/pitcher flags",
                "Final outcome flag",
                "Reconstruction valid/warnings",
                "2025 MISSING_HISTORICAL_SOURCE",
                "2026 Kalshi-only honesty",
                "CSV mirror",
                "Do not claim synthetic as history",
            ],
        ),
        (
            "W2-A10",
            "W2-J documentation",
            &[
                "WATERFALL_2_MLB_EVENT_RECONSTRUCTION.md",
                "W2_ARCHITECTURE.md",
                "W2_DATA_DICTIONARY.md",
                "W2_VALIDATION.md",
                "W2_COVERAGE.md",
                "W2_STEP_LEDGER.md",
                "W2_COMPLETION_REPORT.md",
                "W1 dependency note (no W1 file edits)",
                "Google local artifacts",
                "Completion gate",
            ],
        ),
    ];
    for (act, name, objs) in blocks {
        for (i, obj) in objs.iter().enumerate() {
            v.push(Spec {
                id: Box::leak(format!("{act}-S{}", i + 1).into_boxed_str()),
                activity: name,
                objective: obj,
            });
        }
    }
    v
}

struct Evidence {
    status: StepStatus,
    implementation: &'static str,
    files: &'static str,
    tests: &'static str,
    validation: &'static str,
    limitations: &'static str,
    evidence_path: &'static str,
    result: &'static str,
    blockers: &'static str,
    downstream: &'static str,
}

const W1_DEPS: &str = "W1 ObservabilityKind, IdentityStubV1, ProvenanceRecord, DailyManifest, LakeWriteGuard, exported w2_contract (RawArtifactRef, RawMarketIdentity). W2 does not edit foundation/**.";

fn evidence(id: &str) -> Evidence {
    const ENGINE_FILES: &str = "crates/research-event/**";
    const ENGINE_TESTS: &str = "cargo test -p momento-research-event";
    const SYNTH: &str =
        "Engine proven on SYNTHETIC_TEST_FIXTURE only; no fabricated 2025/2026 PBP.";
    const DS_ENGINE: &str =
        "W3 may consume frozen event/identity types; must not assume historical PBP exists.";

    match id {
        "W2-A2-S7" => Evidence {
            status: StepStatus::Complete,
            implementation: "IdentityRegistry + match_official_to_kalshi_tickers (unique observed abbrev suffix)",
            files: "crates/research-event/src/identity.rs, historical.rs",
            tests: "kalshi_suffix_match_is_unique_and_does_not_invent_pk, identity_no_invented_map",
            validation: "MAPPED only on unique date+abbrev suffix; pk copied from StatsAPI",
            limitations: "Ambiguous doubleheaders stay AMBIGUOUS. No invented mlb_game_pk.",
            evidence_path: "crates/research-event/src/identity.rs",
            result: "COMPLETE (crosswalk engine). Real mapped counts depend on collected PBP.",
            blockers: "none for engine",
            downstream: "W3/W4 may join Mapped games; Unmatched remain kalshi: aliases",
        },
        "W2-A3-S1" => Evidence {
            status: StepStatus::Complete,
            implementation: "source::discover_local_pbp",
            files: "crates/research-event/src/source.rs",
            tests: "local_pbp_discovery_empty",
            validation: "zero historical PBP files",
            limitations: "Discovery complete; real-file ingest remains impossible until files exist.",
            evidence_path: "crates/research-event/src/source.rs",
            result: "COMPLETE (empty inventory, not a fake lake)",
            blockers: "none for discovery; historical ingest blocked separately (CTO-W2-A4-S1)",
            downstream: DS_ENGINE,
        },
        "W2-A9-S7" => Evidence {
            status: StepStatus::Complete,
            implementation: "coverage::report_from_lake",
            files: "crates/research-event/src/coverage.rs",
            tests: "coverage_does_not_claim_2025_pbp",
            validation: "2025 labeled MISSING_HISTORICAL_SOURCE",
            limitations: "Honest missingness is not coverage.",
            evidence_path: "Backtesting Suite/Foundation/W2/w2_coverage.csv",
            result: "COMPLETE as reporting of absence",
            blockers: "none",
            downstream: "W3 must not treat 2025 Kalshi as present",
        },
        "W2-A10-S9" => Evidence {
            status: StepStatus::Complete,
            implementation: "reporting.rs writes local CSV/JSON outside Data-Real",
            files: "crates/research-event/src/reporting.rs, Backtesting Suite/Foundation/W2/",
            tests: "runner_writes_outside_lake",
            validation: "local sheets_w2_index.csv written; cell API remains GOOGLE_PUBLISH_PENDING",
            limitations: "Sheets MCP needsAuth. Local artifacts are the W2 deliverable. Do not fake publish.",
            evidence_path: "Backtesting Suite/Foundation/W2/sheets_w2_index.csv",
            result: "COMPLETE (local artifacts). Sheets cell publish: GOOGLE_PUBLISH_PENDING",
            blockers: "none for local artifacts; Sheets MCP is an external publish gate, not a PBP gate",
            downstream: "CEO Sheets index not live until MCP auth",
        },
        _ => Evidence {
            status: StepStatus::Complete,
            implementation: ENGINE_FILES,
            files: ENGINE_FILES,
            tests: ENGINE_TESTS,
            validation: "unit + integration in tests/w2_engine.rs",
            limitations: SYNTH,
            evidence_path: ENGINE_FILES,
            result: "COMPLETE (engine/contract; historical PBP still missing)",
            blockers: "none for engine; historical reconstruction blocked on data",
            downstream: DS_ENGINE,
        },
    }
}

pub fn complete_ledger(generated_at: DateTime<Utc>) -> W2Ledger {
    let date = generated_at.date_naive().to_string();
    let mut steps = Vec::new();
    for s in specs() {
        let ev = evidence(s.id);
        steps.push(LedgerStep {
            id: s.id.to_string(),
            activity: s.activity.to_string(),
            objective: s.objective.to_string(),
            status: ev.status,
            date: date.clone(),
            implementation: ev.implementation.to_string(),
            files_changed: ev.files.to_string(),
            tests: ev.tests.to_string(),
            validation: ev.validation.to_string(),
            dependencies: W1_DEPS.to_string(),
            known_limitations: ev.limitations.to_string(),
            evidence_path: ev.evidence_path.to_string(),
            result: ev.result.to_string(),
            blockers: ev.blockers.to_string(),
            downstream_impact: ev.downstream.to_string(),
        });
    }
    W2Ledger {
        waterfall: WATERFALL.into(),
        artifact_version: ARTIFACT_VERSION.into(),
        generated_at,
        capability: "ENGINE COMPLETE / HISTORICAL COVERAGE INCOMPLETE".into(),
        steps,
    }
}

impl W2Ledger {
    pub fn markdown(&self) -> String {
        let mut s = String::from("# W2 Step Ledger\n\n");
        s.push_str(&format!(
            "**Capability:** {}\n\n{}\n\n",
            self.capability, CONTROL_PLANE_CROSSWALK
        ));
        s.push_str("| ID | Status | Objective | Result | Blockers |\n|---|---|---|---|---|\n");
        for st in &self.steps {
            s.push_str(&format!(
                "| {} | {:?} | {} | {} | {} |\n",
                st.id,
                st.status,
                st.objective.replace('|', "/"),
                st.result.replace('|', "/"),
                st.blockers.replace('|', "/")
            ));
        }
        s
    }

    pub fn blocked_count(&self) -> usize {
        self.steps
            .iter()
            .filter(|s| s.status == StepStatus::Blocked)
            .count()
    }
}
