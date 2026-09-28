# Waterfall Step Completion Record

STEP ID: INGEST-A1-S1  
TITLE: Continuous historical + forward ingestion control plane  
OBJECTIVE: Idempotent orchestrator independent of W1/W2 implementation, contractually downstream of W1/W2.

SCOPE: Landing, checksums, provenance, watermarks, coverage, failure states, W1 commit gate, W2 consume gate, Sunday 00:00 PT schedule, Kalshi catalog-only. No W3. No Data-Real writes. No live PBP download in this step.

INPUTS: W1 types (`LakeWriteGuard`, `ProvenanceRecord`), W2 `reconstruct_paths`, W1 CEO closeout.

OUTPUTS: `momento-research-ingest`, CLI, ingest docs, ADR-0021.

CODE CHANGES: new crate/app; additive `reconstruct_paths` in research-event; workspace members; gitignore for Ingest landing.

DATA CHANGES: none (tests use tempdirs). Data-Real untouched.

SCHEMA CHANGES: ingest handoff/manifest JSON (new plane, not a W1 schema mutation).

TESTS: `crates/research-ingest/tests/ingest_plane.rs`

VALIDATION: cargo fmt/check/test/clippy on ingest + research-data + research-event as applicable.

ARTIFACTS: `docs/research/backtesting_rebuild/ingest/`

GOOGLE DRIVE OUTPUT: none  
GOOGLE SHEETS OUTPUT: none  

PERFORMANCE: n/a (fixture orchestrator)

KNOWN LIMITATIONS: Live StatsAPI backfill not executed; CLI refuses `--network`. Full 2024–2026 PBP is **not** claimed present. PLAN-W1-A8 still deferred.

LOOKAHEAD / DATA LEAKAGE REVIEW: no plugin features; no future labels.

REPRODUCIBILITY: fixture tests.

DEPENDENCIES CREATED: DATA-INGEST plane  
DEPENDENCIES RESOLVED: W1 ACCEPTED/CLOSED  

NEXT STEP: CTO-authorized live StatsAPI window (optional) or W3 (separate). Do not start W3 from this record.

FINAL STATUS: COMPLETE (infrastructure). Historical network backfill NOT COMPLETE.
