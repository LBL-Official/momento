# W1 ACCEPTANCE PACKAGE

**For:** CTO review  
**Bar:** [W1_ACCEPTANCE_CRITERIA.md](W1_ACCEPTANCE_CRITERIA.md)  
**Filled by:** independent auditor (not the W1 implementer, not `fill_ledger`)  
**Control-plane status until CTO signs:** AUDITED — **FAIL** (criterion 7)  
**CEO closeout (2026-08-26):** **ACCEPTED / CLOSED** — [W1_CEO_ACCEPTANCE.md](W1_CEO_ACCEPTANCE.md). Auditor FAIL body retained.  
**Audit date:** 2026-08-26  
**Scope:** current tree at `/Users/user/Desktop/Momento`; CTO-W1 only  
**Not used as proof:** W1 agent `COMPLETION_REPORT.md`, `ACCEPTANCE_CANDIDATE.md`, or `fill_ledger`

Do not copy W1 agent COMPLETE into this file as PASS.

---

```text
W1 ACCEPTANCE PACKAGE

Status: FAIL

All acceptance criteria:
[PASS] 1 Raw-data immutability
[PASS] 2 Provenance
[PASS] 3 Observability is explicit
[PASS] 4 Timestamp correctness (FLAG-003 must be resolved)
[PASS] 5 Coverage honesty (13 days / 172 games / 344 contracts; 2025, PBP, L2, market-open missing)
[PASS] 6 Step ledger integrity (PLAN vs implementation ledger; no auto-complete)
[FAIL] 7 Tests (fmt, check, test, clippy + W1 integrity tests) actually run
[PASS] 8 Documentation / reproducible package
[PASS] 9 Google reporting honesty (PENDING allowed; fake SUCCESS forbidden)
[PASS] 10 Production isolation

Evidence:
  See evidence table below (criteria 1–10). Independent checksum replay and
  manifest counts were executed by this auditor; they were not copied from
  the W1 agent 10/10 claim.

Known limitations:
  - No git metadata in this workspace; production isolation is mtime + crate
    deps + checksum replay, not `git diff`.
  - Published job `ledger.json` (run w1-d7e5d472e86268dc) still uses unprefixed
    `W1-A1-S1` IDs; current source uses `W1-LEDGER-*` (stale artifact vs code).
  - `fill_ledger` still auto-completes W1-LEDGER rows in one job. Not used as
    PLAN evidence.
  - Batch candlestick gzip line: envelope `source_timestamp` is the last
    `end_period_ts` in that payload; per-bar clocks remain in payload.
  - Envelope field `observability` is payload-presence OBSERVED for PIT books
    (FLAG-004). Game-time L2 must use `source_timestamp_kind=IngestOnly`.
  - PLAN CSV rows W1-A1…A7 remain NOT_STARTED (control-owned; not copied from
    the job ledger — correct). PLAN-W1-A8 remains DEFERRED.
  - `AcceptanceChecklist.raw_data_not_overwritten` is still hardcoded `true`
    in `build_acceptance`; independent SHA-256 replay is the evidence, not
    that boolean.

Outstanding flags:
  FLAG-001  PARTIALLY RESOLVED (source + alias table + PLAN records);
            published ledger.json still collides — ACCEPTABLE LIMITATION
  FLAG-002  PARTIALLY RESOLVED (documentation_complete is fixture-parse,
            not all_complete); fill_ledger auto-complete remains —
            ACCEPTABLE LIMITATION (not PLAN evidence)
  FLAG-003  RESOLVED in current tree (CandleEnd never lacks source_timestamp)
  FLAG-017  OPEN — agent claimed 10/10 COMPLETE; this audit Status is FAIL
            on criterion 7. Control remains VALIDATING until CTO signs.

Production impact:
  NONE (within audit limits: no git; Data-Real checksums match v1 manifests;
  production trees older than W1 foundation edits)

Auditor:
  Independent CTO W1 acceptance auditor / 2026-08-26 /
  current-tree audit only; no implementation; no Data-Real writes

CTO decision:
  PENDING at audit time (criterion 7 clippy)

CEO decision (2026-08-26, after clippy remediation):
  ACCEPTED / CLOSED
  Evidence: this audit (criteria 1–6, 8–10) + w1/CLIPPY_REMEDIATION.md (criterion 7)
  Record: W1_CEO_ACCEPTANCE.md

Auditor recommendation (not a CTO signature):
  RETURN TO W1
```

---

## Evidence table (criteria 1–10)

| # | Result | Independent evidence |
|---|--------|----------------------|
| **1 Immutability** | **PASS** | Auditor SHA-256 replay of all **52** checksummed files on MLB COMPLETE days 2026-06-18…30 vs v1 manifests: **0 mismatches, 0 missing files**. Data-Real latest file mtime **2026-08-25T11:05:01**; Foundation/W1 latest **2026-08-26T01:06:39**. Outputs only under `Backtesting Suite/Foundation/W1/` (resolved path outside Data-Real). Guard: `LakeWriteGuard::assert_not_lake_path` + `resolve_path` existing-prefix canonicalize in `crates/research-data/src/foundation/guard.rs`. **Historical** `overwrite_guard_blocks_lake_writes` FAIL (2026-08-26T07:35:35Z, missing child path) is **not** current: auditor re-ran `cargo test -p momento-research-data --offline --test w1_foundation overwrite_guard_blocks_lake_writes -- --exact` as part of full suite — **ok**. Job `integrity_report.json`: checksum/gzip/parquet/pairing all **0**. 25 findings INFO `TRADE_NOT_SORTED` only — not repairs. |
| **2 Provenance** | **PASS** | Types: `ProvenanceRecord`, `TimestampRole`, `SourceTimestampKind` in `foundation/provenance.rs`. Artifacts: `provenance_index.json`, `source_inventory.json`, `raw_v2_sample.jsonl`. Envelope: `ingestion_timestamp` = v1 `received_at`; exchange clocks from payload only (`envelope_from_v1`). Tests: `received_at_is_not_copied_to_source_timestamp_for_orderbook`, `envelope_v2_round_trip_does_not_use_received_at_as_exchange`, `trade_uses_created_time`. |
| **3 Observability** | **PASS** | `ObservabilityKind` + `OBSERVABILITY_CONTRACT` in `observability.rs`. Artifact `observability_contract.json`: `l2_orderbook` / `kalshi_orderbook` = `L2_HISTORICAL_UNAVAILABLE`; `candlestick_1m_close` = `OBSERVED`; `pbp` = `UNAVAILABLE`. Tests: `observability_never_upgrades_l2_or_pbp`; LEGACY `no_synthetic_l2_from_candlesticks` (candlestick source + `l2_snapshot` event_type is invalid). Coverage records set `l2=UNAVAILABLE` even when v1 COMPLETE (`complete_v1_is_not_lifetime_complete`). FLAG-004 remains a **limitation**, not a candle-as-L2 upgrade. |
| **4 Timestamps / FLAG-003** | **PASS** | Current `candle_source_clock` in `envelope_v2.rs`: `CandleEnd` only when an `end_period_ts` is converted to RFC3339; empty payload uses `Unknown`, not `CandleEnd`. Tests **run this audit**: `single_candlestick_copies_end_period_ts`, `candlestick_batch_preserves_last_end_period_ts_as_envelope_clock`, `candle_end_never_pairs_with_empty_source_timestamp` — all **ok**. PIT orderbook: `IngestOnly`, `received_at` not copied to `source_timestamp`. Closeout fail-if (“`source_timestamp` empty while kind is `CandleEnd`”) does **not** hold on current code. |
| **5 Coverage honesty** | **PASS** | **Auditor count from Data-Real MLB manifests**, not from the agent report: COMPLETE dates exactly `2026-06-18`…`2026-06-30` (**13**). MISSING/probes: 5×2025 + 17×2026-06-01…17 (probes retained, not deleted). **2025 COMPLETE = 0**. Catalog `market_evidence` MLB: **172** `event_ticker`, **344** tickers, date range 2026-06-18…30. `coverage_matrix.csv` MLB `PARTITION_COMPLETE_V1` = 13 same dates. PBP-like paths under Data-Real: **0**. `starting_price_evidence.json`: 410 rows, class `STARTING_PRICE_UNVERIFIED`, `market_open_price_cents` non-null = **0**. Test `starting_price_is_unverified_not_market_open`. `PBP_SOURCE_MATRIX.md` catalogs sources; download forbidden. |
| **6 Ledger integrity** | **PASS** | PLAN evidence is `docs/research/completions/PLAN-W1-A1-S1.md` … `PLAN-W1-A7-S2.md` plus `PLAN-W1-A8-S1.md` **DEFERRED** — not `fill_ledger`. Alias table `w1/REGISTRY_ID_MAPPING.md`. Current `W1_STEPS` IDs are `W1-LEDGER-*`; test `w1_ledger_ids_are_namespaced_not_plan_ids` **ok**. `build_acceptance.w1_documentation_complete` = fixture JSON parse (`catalog_fixture_parses` / `envelope_fixture_parses`), **not** `ledger.all_complete()`. `fill_ledger` still exists and still marks every W1-LEDGER step complete in one call — **not accepted as PLAN proof**. Published `Foundation/W1/ledger.json` still has unprefixed `W1-A1-S1` (stale run). PLAN CSV still `NOT_STARTED` / A8 `DEFERRED` — not polluted by auto-complete. |
| **7 Tests** | **FAIL** | See command table. `fmt --check`, `cargo check`, `cargo test` **exit 0**. Mandated `cargo clippy -p momento-research-data --all-targets --no-deps -- -D warnings` **exit 101** (4 lints: `too_many_arguments` ×3, `type_complexity` ×1). W1 integrity tests in the green `cargo test` run: overwrite guard, checksum-related job artifacts independently replayed, `no_synthetic_l2_from_candlesticks`, demo≠real, timestamp kinds. Production tests were not deleted (infrastructure 13 ok). Bar §7 fail-if is “not run”; tests **were** run. This **FAIL** is the auditor-mandated deny-warnings clippy command, which did not succeed. |
| **8 Documentation** | **PASS** | Paths exist: `docs/research/backtesting_rebuild/w1/` (ARCHITECTURE, COVERAGE, PROVENANCE, OBSERVABILITY, DATA_DICTIONARY, PBP_SOURCE_MATRIX, REGISTRY_ID_MAPPING, LEDGER, VALIDATION_REPORT, REPRODUCE via Foundation). Fixtures: `crates/research-data/src/foundation/fixtures/lake_catalog_v1.example.json`, `raw_envelope_v2.example.json`, `identity_stub_v1.example.json`. Derived package files listed below all exist. `REPRODUCE.md` documents the collector command and digest stability. Local ≠ Google: `google_publish.json` PENDING. |
| **9 Google honesty** | **PASS** | Local CSVs/JSON under Foundation/W1 exist (`sheets_w1_index.csv`, `coverage_matrix.csv`, etc.). `google_publish.json` status **`GOOGLE_PUBLISH_PENDING`**. No `SUCCESS` claim. Note admits Sheets MCP `needsAuth` and that a Drive folder id is not a complete published archive. Bar allows PENDING. |
| **10 Production isolation** | **PASS** | **No git repo** (`git status` → NO_GIT) — cannot prove a commit diff. Observed: `momento-research-data` Cargo.toml has **no** `momento-risk` / `momento-execution` / `momento-strategy-mlb`; test `production_fence_research_data_toml` **ok**. Production path latest mtimes are **2026-08-24…08-25**; W1 `foundation/` latest **2026-08-26T01:04:48**. Data-Real latest **2026-08-25** with checksum match. Auditor did not modify production or Data-Real. |

### Foundation artifacts confirmed present

`Backtesting Suite/Foundation/W1/`: `lake_catalog.json`, `canonical_catalog_body.json`, `integrity_report.json`, `coverage_matrix.csv`, `availability_audit.json`, `provenance_index.json`, `source_inventory.json`, `observability_contract.json`, `starting_price_evidence.json`, `raw_artifact_refs.json`, `raw_v2_sample.jsonl`, `ledger.json`, `acceptance.json`, `anomalies.csv`, `missing_data.csv`, `sheets_w1_index.csv`, `demo_catalog_slice.json`, `google_publish.json`, `REPRODUCE.md`.

---

## Outstanding flags

| Flag | Classification | Notes |
|------|----------------|-------|
| **FLAG-001** step IDs | **PARTIALLY RESOLVED** / published artifact **ACCEPTABLE LIMITATION** | Current `ledger.rs` uses `W1-LEDGER-*`; mapping doc + PLAN-W1 completion records + namespaced-ID test. Frozen `ledger.json` still `W1-A1-S1`. Auditor did not re-run the Data-Real job. PLAN CSV not overwritten. |
| **FLAG-002** auto-complete | **PARTIALLY RESOLVED** / `fill_ledger` **ACCEPTABLE LIMITATION** | `w1_documentation_complete` is no longer `ledger.all_complete()`. `fill_ledger` still completes all internal steps in one function — **not** treated as PLAN completeness. Hardcoded `raw_data_not_overwritten: true` is **not** criterion-1 evidence (checksum replay is). |
| **FLAG-003** candle `source_timestamp` | **RESOLVED** | Current-tree tests prove `CandleEnd` carries `end_period_ts`. Historical empty-`CandleEnd` behavior is not present. Batch last-bar envelope clock is a documented limitation, not the closeout fail-if. |
| **FLAG-017** agent COMPLETE vs control VALIDATING | **OPEN** | Agent 10/10 claim is **not** adopted. This package **Status: FAIL** (criterion 7). Control stays VALIDATING until the human CTO signs. |
| FLAG-004 PIT `observability=OBSERVED` | **ACCEPTABLE LIMITATION** | Not a closeout gate. Consumers must use `IngestOnly`. |

---

## Exact commands / results (this audit)

Workspace: `/Users/user/Desktop/Momento`  
Date: 2026-08-26

| Command | Exit | Result |
|---------|------|--------|
| `cargo fmt -p momento-research-data -- --check` | **0** | PASS (no fmt diffs) |
| `cargo check -p momento-research-data --offline` | **0** | PASS |
| `cargo test -p momento-research-data --offline` | **0** | PASS: lib **5** ok; infrastructure **13** ok; w1_foundation **15** ok, **1** ignored (`write_workspace_demo_catalog_slice`) |
| `cargo clippy -p momento-research-data --all-targets --no-deps --offline -- -D warnings` | **101** | **FAIL**: `clippy::too_many_arguments` at `provenance.rs:61`, `reporting.rs:42`, `reporting.rs:137`; `clippy::type_complexity` at `runner.rs:255` |

W1 integrity tests included in the passing `cargo test` run (not re-listed as separate processes):  
`overwrite_guard_blocks_lake_writes`, `w1_job_is_idempotent_on_fixture_lake`, `observability_never_upgrades_l2_or_pbp`, `complete_v1_is_not_lifetime_complete`, `empty_probe_is_not_fabricated_2025`, `demo_data_path_cannot_be_labeled_real`, `data_real_path_cannot_be_labeled_demo`, `no_synthetic_l2_from_candlesticks`, envelope timestamp tests including `candle_end_never_pairs_with_empty_source_timestamp`.

Independent non-cargo checks: Python SHA-256 replay of 52 MLB COMPLETE files (**0 mismatches**); MLB manifest COMPLETE/MISSING census; Data-Real PBP glob (**0**); starting-price class census; production vs W1 mtimes; `git status` → **NO_GIT**.

---

## Recommendation

**RETURN TO W1**

Reason: criterion **7 FAIL** — required `clippy … -D warnings` did not succeed. This is **style-lint only**, not an integrity, provenance, coverage, or production defect.

Narrow return scope (if the CTO sends it back): allow or refactor the four clippy lints so `cargo clippy -p momento-research-data --all-targets --no-deps -- -D warnings` exits 0. Do **not** re-open FLAG-003, Data-Real, or PLAN-W1-A8.

If the CTO treats deny-warnings clippy as **outside** the closeout bar (the bar’s §7 fail-if is “tests were not run,” and tests did run green), the CTO may still **ACCEPT / CLOSED** despite this FAIL. That waiver is a CTO act, not this auditor’s.

**This auditor does not write ACCEPTED / CLOSED.**

---

After **ACCEPTED / CLOSED**, next implementation authorization (CTO):

**CTO-W3 — Kalshi Market Reconstruction**  
(not automatic; not W2 PBP ingest)
