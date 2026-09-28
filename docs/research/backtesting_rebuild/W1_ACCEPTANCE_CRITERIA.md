# W1 CLOSEOUT BAR (binding)

**Authority:** CTO. Not the W1 implementation agent. Not `fill_ledger`. Not “tests passed.”  
**Status of W1 itself:** VALIDATING until a filled [W1_ACCEPTANCE_PACKAGE.md](W1_ACCEPTANCE_PACKAGE.md) is **ACCEPTED / CLOSED** by the CTO.  
**Auditor:** independent of the W1 implementer (dedicated acceptance/audit prompt).  
**Control agent:** owns this bar; does **not** mark PASS/FAIL here.

Closing W1 requires **all** of:

```text
code correctness
+ data integrity
+ provenance
+ observability honesty
+ timestamp correctness
+ coverage honesty
+ ledger integrity (evidence-based, not auto-complete)
+ architectural compliance
+ reproducibility
+ production isolation
```

Passing `cargo test` proves the code behaves as written. It does **not** prove historical assumptions are correct.

---

## 1. Raw-data immutability

| Must prove | Fail if |
|------------|---------|
| `Backtesting Suite/Data-Real` untouched | Any overwrite, delete, or silent repair of raw gzip/parquet/manifests |
| Raw gzip byte-preserved | Hash of `events.jsonl.gz` (and published v1 parquet/manifests) differs from v1 manifests without a documented **new** derived tree |
| Checksums/manifests valid | Checksum mismatch ignored or “fixed” in place |

Evidence: SHA-256 replay vs v1 manifests; LakeWriteGuard; catalog generated **outside** the lake (`Foundation/W1`).

---

## 2. Provenance

Every ingested artifact must answer:

- Where did this come from?
- When was it obtained?
- What exactly is it?
- What can / cannot we observe from it?

Fail if provenance is missing, or if collector clock is used as if it were venue time.

---

## 3. Observability is explicit

The engine must not infer that candles are L2.

Required field states (ADR-0011):

```text
OBSERVED | DERIVED | INFERRED | MODELED | UNAVAILABLE
```

(`LABEL_ONLY` / `L2_HISTORICAL_UNAVAILABLE` are allowed as **named** extensions, mapped in the contract registry — they must not silently upgrade UNAVAILABLE.)

Fail if `orderbook.parquet` / candle close is treated as historical L2 or as game-time REST book.

---

## 4. Timestamp correctness (FLAG-003 is a closeout gate)

| Must prove | Fail if |
|------------|---------|
| `CandleEnd` preserves the candle period-end source timestamp (`end_period_ts` or documented equivalent) | `source_timestamp` empty while kind is `CandleEnd` |
| `received_at` is ingestion only | `received_at` represented as exchange time |

This flag must be **resolved** before W1 acceptance. It is not optional polish.

---

## 5. Coverage honesty

Must report, as facts about **this lake**, without fabricated completeness:

| Present (v1 PARTITION_COMPLETE window) | Missing / UNAVAILABLE |
|----------------------------------------|------------------------|
| MLB Kalshi **2026-06-18 → 2026-06-30** | **2025** MLB Kalshi (empty probes ≠ games) |
| **13** COMPLETE_V1 days | Historical **PBP** |
| **172** games (event-tickers) | Historical **L2** |
| **344** contracts | **Proven market-open price** |

v1 `COMPLETE` means close/settled PT-day collect. It does **not** mean lifetime, L2, PBP, or market-open.

Fail if 2025 is invented, if empty probes are deleted, or if first settlement-day candle is labeled `MARKET_OPEN_PRICE`.

---

## 6. Step ledger integrity

PLAN-W1-Ax-Sy and the implementation ledger must not collide as if they were one namespace.

Required: **one unambiguous completion record** per accepted step (PLAN-namespaced or an explicit alias table).

Fail if completeness is:

```text
function says COMPLETE  →  therefore COMPLETE
```

(`fill_ledger` auto-complete is not evidence.)

---

## 7. Tests

Must actually be run and reported (command, package, pass/fail):

- `cargo fmt` (or documented equivalent check)
- `cargo check`
- `cargo test` (W1 crate(s) at minimum)
- `cargo clippy`

Plus W1-specific integrity / immutability / provenance tests (checksum replay, no_synthetic_rows, demo≠real, non-overwrite, timestamp kinds).

Fail if tests were not run, or if production tests were deleted to make W1 pass.

---

## 8. Documentation (reproducible package)

Must explain:

- WHAT was ingested
- WHERE it came from
- HOW it was verified
- WHAT is observable
- WHAT is unavailable
- WHAT transformations occurred (v1 wrap vs v2 additive; no raw rewrite)
- WHAT tests prove correctness

Derived package location: `Backtesting Suite/Foundation/W1/` plus `docs/research/backtesting_rebuild/w1/`.

---

## 9. Google reporting

Local research artifacts must exist.

Anything publishable to Drive/Sheets must be reported **honestly**.

`GOOGLE_PUBLISH_PENDING` is acceptable if authentication is genuinely unavailable.

Fail if publication is faked as success.

---

## 10. Production isolation

Absolutely no changes to:

- live host / live trading paths
- risk engine
- execution
- production strategy (`strategies/mlb`, FIRST01 live)
- live configuration
- trading transport (Kalshi order/auth/ws production)
- Data-Real raw data

Production impact of an accepted W1 must be **NONE**.

---

## After CTO accepts W1

```text
W1 → ACCEPTED / CLOSED
```

Then the CTO may authorize:

```text
CTO-W3 — Kalshi Market Reconstruction
```

That authorization is **not** automatic from a green test suite.

| Still true after W1 close | |
|---------------------------|--|
| CTO-W2 contract/fixture work | May continue (PBP still UNAVAILABLE) |
| CTO-W2 real PBP ingest | Still BLOCKED on license + source |
| CTO-W3 implementation | **Only after** this CTO accept + explicit W3 auth |
| PLAN-W1-A8 Kalshi re-query | Still DEFERRED unless separately authorized |

---

## Auditor output (required shape)

Fill [W1_ACCEPTANCE_PACKAGE.md](W1_ACCEPTANCE_PACKAGE.md):

```text
Status: PASS / FAIL

All acceptance criteria:
[PASS|FAIL] 1 Immutability
[PASS|FAIL] 2 Provenance
[PASS|FAIL] 3 Observability
[PASS|FAIL] 4 Timestamps (FLAG-003)
[PASS|FAIL] 5 Coverage honesty
[PASS|FAIL] 6 Ledger integrity
[PASS|FAIL] 7 Tests actually run
[PASS|FAIL] 8 Documentation package
[PASS|FAIL] 9 Google reporting honesty
[PASS|FAIL] 10 Production isolation

Evidence: …
Known limitations: …
Outstanding flags: …
Production impact: NONE | <describe>
```

Any FAIL ⇒ W1 stays open. The CTO makes the final call.
