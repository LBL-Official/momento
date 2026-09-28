# CTO_REVIEW_FLAGS.md

**Role:** observation log. Control agent does **not** patch W1/W2 implementation.  
**Policy:** do not block W1/W2 unless correctness, data-integrity, or architectural dependency requires it.  
**As of:** 2026-08-26

Severity:

| Level | Meaning |
|-------|---------|
| **INFO** | Documented; no action required to continue |
| **REVIEW** | W1/W2 should address before claiming COMPLETE; work may continue |
| **BLOCK** | Must stop the affected step (not necessarily the whole waterfall) |

No **BLOCK** is raised against continuing W1 implementation or W2 **contract/fixture** work.

---

## FLAG-001 — Step ID collision (REVIEW)

**Class:** architectural contradiction / duplicated identity of work  
**Where:** `docs/research/BACKTEST_ENGINE_WATERFALL_REGISTRY.csv` vs `crates/research-data/src/foundation/ledger.rs`

`W1-A1-S1` means:

- PLAN: specify `lake_catalog_v1` schema (docs + fixtures)
- W1 ledger: discover lake roots

The W1 runner then `complete_step`s **every** ledger ID in one job (`fill_ledger`), including IDs that do not exist on the PLAN CSV (e.g. ledger W1-A8-S3).

**Do not block W1.** Require namespaced IDs in evidence (`PLAN-W1-…` vs `W1-LEDGER-…`). Do not copy ledger COMPLETE into the PLAN CSV.

---

## FLAG-002 — Ledger auto-complete is not evidence (REVIEW)

**Class:** invalid assumption / auditability  
**Where:** `foundation/runner.rs` `fill_ledger` + `build_acceptance`

`w1_documentation_complete: ledger.all_complete()` is circular: the same function marks all steps complete, then treats that as documentation completeness. Several acceptance booleans are hardcoded `true` (`raw_data_not_overwritten`, `no_production_code_changed`, …) without git/diff proof.

**Do not block W1.** Control plane will not mark CTO-W1 COMPLETE until independent evidence exists (checksum replay output, test list, completion records).

---

## FLAG-003 — Candle envelope drops `end_period_ts` (REVIEW)

**Class:** timestamp / synchronization  
**Where:** `foundation/envelope_v2.rs` `extract_source_clock`

```text
"candlesticks" => (None, SourceTimestampKind::CandleEnd, …)
```

Kind is `CandleEnd` but `source_timestamp` is always `None`. Payload `end_period_ts` is not copied. This is not promoting `received_at` (good) but it **fails to preserve** the candle clock that ADR-0002 requires for later sync.

**Do not block W1 catalog work.** W1 should fix this before any consumer uses v2 samples as join keys. W2/W4 must not treat missing candle source_timestamp as “ingest time.”

---

## FLAG-004 — Envelope v2 marks every lifted row OBSERVED (REVIEW)

**Class:** observability honesty  
**Where:** `envelope_from_v1` sets `observability: ObservabilityKind::Observed` for all endpoints, including `markets/orderbook` (PIT ingest).

Observability contract correctly says PIT snapshots are OBSERVED-as-of-ingest and UNAVAILABLE as game-time L2. The envelope field does not distinguish those.

**Do not block.** Consumers must use `source_timestamp_kind == IngestOnly`, not the envelope observability enum, until W1 versions the field.

---

## FLAG-005 — Numbering inversion PLAN-W3 vs CTO-W3 (INFO / permanent)

**Class:** architectural contradiction (documented, not a code bug)

PLAN-W3 = time sync. CTO-W3 = Kalshi market reconstruction.  
PLAN-W5 = PBP transitions. CTO-W5 = canonical StateTransition engine.

Agents using unprefixed `W3`/`W5` will implement the wrong layer. Crosswalk is binding.

---

## FLAG-006 — Governance docs stale vs W1 code (INFO)

**Class:** documentation lag (outside frozen W0 recon)

`BACKTEST_ENGINE_CURRENT_STATE.md` still says W1 not authorized / nothing in code.  
`WATERFALL_NEXT_STEP.md` (frozen W0-A10) says do not implement.  
W1 `foundation/` and `w1-foundation` CLI exist.

Control plane supersedes those living-doc statements for **authorization**. W0 recon files are not rewritten. Parent governance should be updated by a later authorized docs step — not by W1 inventing PLAN CSV completeness.

---

## FLAG-007 — ObservabilityKind extra variants vs ADR-0011 (REVIEW)

**Class:** contract fork

ADR-0011: OBSERVED / DERIVED / INFERRED / MODELED / LABEL_ONLY / UNAVAILABLE  
W1 enum adds `L2HistoricalUnavailable`, `OutcomeLabel` (≈ LABEL_ONLY)

Not a hallucination. Requires a versioned mapping in the contract registry before W2 stores event-state observability.

---

## FLAG-008 — PLAN-W1-A8 vs ledger W1-A8 (REVIEW)

**Class:** duplicated ownership of the ID “W1-A8”

PLAN-W1-A8 = optional Kalshi re-query (**DEFERRED**, separate CEO auth).  
W1 ledger W1-A8 = local Drive/Sheets artifact package.

W1 must **not** launch historical re-query because it named a step A8. Re-query remains unauthorized.

---

## FLAG-009 — W2 implementation not present; W1 already published W2 handoff types (INFO)

**Class:** parallel-work observation

W2 crate/files do not exist. W1 owns `w2_contract.rs` (`RawArtifactRef`, `RawMarketIdentity`). That is legitimate **if** W2 does not edit it.

W1 `SportCode` was removed from an earlier draft of `w2_contract.rs` (now `sport: String`). Fine. W2 must not invent official MLB ids in `mlb_game_pk`.

---

## FLAG-010 — `LakeLayer::Orderbook` provenance tagged CandlePeriodEnd (REVIEW)

**Class:** timestamp

`write_provenance_index` maps entire orderbook parquet to `TimestampRole::CandlePeriodEnd`. That parquet also contains PIT `RestSnapshot` rows (ingest clock). Mixing clocks in one file-level provenance row is honest-as-approximation only.

W3/W4 must join at **row** observability, not file-level role.

---

## FLAG-011 — Production fence is Cargo.toml string search (INFO)

**Class:** safety (weak but present)

`w1_foundation.rs` asserts `research-data/Cargo.toml` does not contain `momento-risk` / `momento-execution` / `momento-strategy-mlb`. Good intent. Does not prove `apps/research-collector` or future W2 crates stay fenced.

---

## FLAG-012 — Shared-file bottlenecks (INFO, protocol assigned)

`lib.rs` and `apps/research-collector/src/main.rs` cannot be owned by two active implementers. Protocol: W2 new crate + no collector edits. See FILE_OWNERSHIP OWN-001/002.

---

## FLAG-013 — Historical-data hallucination risks (standing)

Not observed as committed fabricated days. Standing watch items:

- demo `Data/` COMPLETE flags
- `orderbook.parquet` name
- first candle on close-day = open
- 2025 probe dates as reconstructed games
- `received_at` as exchange time
- W1 job status `"COMPLETE"` when acceptance is self-attested

W1 source inventory correctly lists PBP and L2 as ABSENT. Keep that.

---

## FLAG-014 — Immutable raw (no violation observed)

W1 `LakeWriteGuard` refuses writes under `lake_root`. Default out dir `Backtesting Suite/Foundation/W1` is outside Data-Real. **No BLOCK.** Continue.

If a future change writes `events.jsonl.gz` in place: **BLOCK** immediately.

---

## FLAG-015 — Production contamination (no violation observed)

No edits observed to strategy/risk/execution/live config in this control-plane pass. **No BLOCK.**

---

## FLAG-016 — `W1/` vs `w1/` case collision (REVIEW)

**Class:** duplicated ownership / shared-file

Darwin case-insensitive FS: control-plane package `W1/` and W1 agent directory `w1/` are one inode. Control-plane README/SPEC/… were written into the W1 agent doc tree. W1 agent files (`ARCHITECTURE.md`, `LEDGER.md`, `W2_HANDOFF.md`, …) were **not** deleted.

**Do not block.** Future control stubs for W1 must not invent a second folder. Combined index is `w1/README.md`. Exclusive *implementation* ownership remains `foundation/**`.

---

## FLAG-017 — W1 agent COMPLETE vs control plane not COMPLETE (REVIEW)

**Class:** invalid assumption (completeness)

W1 `COMPLETION_REPORT.md` / `LEDGER.md` mark the waterfall COMPLETE (run `w1-d7e5d472e86268dc`, 0 checksum mismatches, tests claimed). Control plane status remains **VALIDATING**, not COMPLETE, until PLAN-namespaced completion records exist and FLAG-001/002/003 are addressed.

Observed **positive** evidence (do not ignore): Foundation artifacts exist; validation report matches W0 inventory counts (13 days / 172 games / 344 markets); starting prices unverified; PBP/L2 UNAVAILABLE; recovery queries not launched.

---

## FLAG-018 — W1 “do not begin W2” vs CTO parallel W2 (INFO)

**Class:** authorization contradiction (process, not data)

W1 `LEDGER.md` / `COMPLETION_REPORT.md` tell the W1 agent to STOP and not start W2. That is correct **for the W1 agent**. CTO authorization allows a **different** W2 agent to do contract/fixture work in parallel. W2 must not treat W1’s STOP as a ban on W2 contracts.

---

## What is NOT blocking parallel W1 / W2

W2 contract design, adapter traits, and synthetic FIXTURE PBP **may proceed**.  
W2 must not parse a non-existent PBP lake or fill `mlb_game_pk` from ticker folklore.
