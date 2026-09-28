# SuperASI v1 — Completion Report

```
LIVE EXECUTION = FALSE
CANDLE PATH ≠ ACTUAL FILL
LEDGER PRICE ≠ PROVEN FILL
FEE MODEL = ESTIMATED
MEASUREMENT ≠ EDGE
S ≠ terminal p
DO NOT CHANGE LIVE FIRST01 / 80 / 81 / 83 / 89
DO NOT START W9
```

**Verdict:** SuperASI v1 is complete as a research decomposition laboratory. ROLLER still measures. SuperASI decomposes. Neither submits orders.

## What shipped

1. **Package + validation** (`superasi_package_v1`) with checksums and fail-closed errors.
2. **Disk library** under `research/superasi/library/` (atomic write; no localStorage).
3. **Asked-six seed** reconstructed from locked CSVs (not a tape rescan).
4. **Server-authoritative import** via existing `execute_research_object` / `execute_question`. FIRST80_Q3 N = **290**, not 200.
5. **Four-cell / EV / eight mixes / fees / liquidity / adverse p / ±5 windows / decompose**.
6. **One Vite app** at `frontend/roller-terminal/src/superasi/` with nav Quick Start · Decompose · Results · Labs.
7. **Move to SuperASI** on ROLLER Results (COMPLETE or PARTIAL, count > 0). Copy: MEASUREMENT IMPORTED.

## Waterfall

Phases 0–16 executed. Phase 0 recon: `docs/research/superasi/RECON.md`. Build matrix: `reports/SUPERASI_BUILD_REPORT.md`.

## Tests

`ROLLER/tests/test_superasi_*.py` — 28 passed, including asked-six locks and frozen N=290.

Frontend: `npx tsc --noEmit` passed.

ROLLER integrity: `validate_roller.py` PASS, `leakage_audit.py` PASS.

Pre-existing `test_indexed_execute_matches_scan` failure is unchanged and out of SuperASI scope.

## Isolation

No live FIRST01 / 80 / 81 / 83 / 89 retune. W9 not started. No new credentials. No second Vite app.

## Operator note

Default chips: fill `FIRST_BARRIER_CLOSE`, fee `CURRENT`, adverse p `73%`, window `±5`. Changing fill changes headline EV and must not change S.
