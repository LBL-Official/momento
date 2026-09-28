# W1 Step Ledger (human)

**Namespaces (do not mix):**

- **PLAN-W1-A\*** — CEO checkpoints (`docs/research/completions/PLAN-W1-*.md`)
- **W1-LEDGER-A\*** — one job’s internal checklist (`Backtesting Suite/Foundation/W1/ledger.json`)
- Mapping: [REGISTRY_ID_MAPPING.md](REGISTRY_ID_MAPPING.md)

Machine run: `w1-d7e5d472e86268dc`  
Integrity: checksum/gzip/parquet/pairing **0 failures**  
PLAN-W1-A8 Kalshi re-query: **DEFERRED** (ledger A8 is local reporting only)

| PLAN-S | Status | Independent evidence |
|--------|--------|----------------------|
| PLAN-W1-A1-S1 | COMPLETE | `fixtures/lake_catalog_v1.example.json`; test `lake_catalog_v1_fixture_parses` |
| PLAN-W1-A1-S2 | COMPLETE | `lake_catalog.json` (350 files); real Data-Real job |
| PLAN-W1-A1-S3 | COMPLETE | `demo_catalog_slice.json` `lake_class=DEMO`; demo≠real tests |
| PLAN-W1-A1-S4 | COMPLETE | `canonical_catalog_body.json`; idempotent fixture test |
| PLAN-W1-A2-S1…S3 | COMPLETE | `coverage.rs`; `coverage_matrix.csv`; 13/172/344; 2025 probes retained |
| PLAN-W1-A3-S1…S2 | COMPLETE | integrity 0 mismatches; `overwrite_guard_blocks_lake_writes` |
| PLAN-W1-A4-S1…S3 | COMPLETE | envelope fixtures + FLAG-003 tests; observability contract |
| PLAN-W1-A5-S1…S2 | COMPLETE | identity stub fixture; live hash test; `mlb_game_pk=null` |
| PLAN-W1-A6-S1…S2 | COMPLETE | `PBP_SOURCE_MATRIX.md`; no PBP download |
| PLAN-W1-A7-S1…S2 | COMPLETE | Cargo.toml fence; `assert_lake_class_honest` |
| PLAN-W1-A8-* | **DEFERRED** | `PLAN-W1-A8-S1.md`; `launched=false` |

**Clippy remediation (2026-08-26):** criterion-7 style lints only — see [CLIPPY_REMEDIATION.md](CLIPPY_REMEDIATION.md). Independent audit package is **not** rewritten. W1 is **not** ACCEPTED / CLOSED here.

**Next:** CTO signs [`W1_ACCEPTANCE_PACKAGE.md`](../W1_ACCEPTANCE_PACKAGE.md). Do not start CTO-W3 or PLAN-W1-A8 from this file.
