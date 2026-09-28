# W1 Clippy remediation (criterion 7)

**Scope:** style-lint only. No schema, Data-Real, coverage, or production change.  
**Does not:** mark W1 ACCEPTED / CLOSED (CTO decision).  
**Independent audit:** [`W1_ACCEPTANCE_PACKAGE.md`](../W1_ACCEPTANCE_PACKAGE.md) remains the audit record (criterion 7 FAIL as audited). This file is implementer evidence after the four Clippy diagnostics were fixed.

**Date:** 2026-08-26

## Exact four Clippy failures (as audited)

| Lint | Location | Diagnostic |
|------|----------|------------|
| `clippy::too_many_arguments` (9/7) | `crates/research-data/src/foundation/provenance.rs` `ProvenanceRecord::for_lake_file` | function had 9 arguments |
| `clippy::too_many_arguments` (9/7) | `crates/research-data/src/foundation/reporting.rs` `write_core_artifacts` | function had 9 arguments |
| `clippy::too_many_arguments` (8/7) | `crates/research-data/src/foundation/reporting.rs` `write_sheets_index` | function had 8 arguments |
| `clippy::type_complexity` | `crates/research-data/src/foundation/runner.rs` `collect_entries` | return type was a 3-tuple of collections |

No `#[allow(...)]` was added. Clippy deny-warnings was not weakened.

## What changed

Grouped existing arguments / return values. Serialized JSON/CSV fields, provenance `None`s at W1 catalog time, overwrite guard, and lake immutability are unchanged.

## Validation re-run (this remediation)

| Command | Exit |
|---------|------|
| `cargo fmt -p momento-research-data -- --check` | **0** |
| `cargo check -p momento-research-data --offline` | **0** |
| `cargo test -p momento-research-data --offline` | **0** (lib 5; infrastructure 13; w1_foundation 15 ok + 1 ignored) |
| `cargo clippy -p momento-research-data --all-targets --no-deps --offline -- -D warnings` | **0** |
| `cargo test -p momento-research-data --offline --test w1_foundation overwrite_guard_blocks_lake_writes -- --exact` | **0** |

CTO decision remains **PENDING**.
