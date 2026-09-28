# SuperASI v1 — Build Report

```
LIVE EXECUTION = FALSE
CANDLE PATH ≠ ACTUAL FILL
LEDGER PRICE ≠ PROVEN FILL
FEE MODEL = ESTIMATED
MEASUREMENT ≠ EDGE
DECOMPOSITION ≠ SIGNAL
```

Date: 2026-09-10. SuperASI is a research consumer of ROLLER measurements. It does not submit orders.

## Status by surface

| Surface | Status | Notes |
|---|---|---|
| Package schema `superasi_package_v1` | IMPLEMENTED | `ROLLER/roller/superasi/package.py` |
| Disk library (atomic write) | IMPLEMENTED | `research/superasi/library/{id}/` — not localStorage |
| Four-cell 883/108/0/191 | IMPLEMENTED | S = 883/1182; p = 991/1182 |
| Eight research exit mixes | IMPLEMENTED | `EV = G·S − L_x(1−S)` |
| Path windows ±5 | IMPLEMENTED | Locked CSV 3285 rows; missing +4/+5 = UNAVAILABLE |
| Fee wrapper | IMPLEMENTED | `PublishedScheduleEstimate` only |
| Liquidity | IMPLEMENTED | FAST_GAP TAKER; bid 50 / limit 40 NOT A STOP |
| Adverse terminal | IMPLEMENTED | Layer 0 p stress; holds s_W / s_L |
| Decompose | IMPLEMENTED | Deterministic `decomp.json`; no RNG/ML |
| Terminal API | IMPLEMENTED | `/superasi/library/*`, `/superasi/seed/asked-six` |
| Move to SuperASI | IMPLEMENTED | COMPLETE or PARTIAL with count > 0 |
| SuperASI shell | IMPLEMENTED | Quick Start · Decompose · Results · Labs |
| Results chips | IMPLEMENTED | Fill / fee / adverse / ±5; mix switch changes EV, not S |
| Labs | IMPLEMENTED | Disk library UI |
| L2 / mid / OFI / queue | NOT_SUPPORTED | Not in v1 |
| Live liquidation / signals | NOT_IMPLEMENTED | Isolation rule |
| Bootstrap / clustering | NOT_IMPLEMENTED | Out of v1 |
| Client 200-row preview as N | NOT_SUPPORTED | Import refuses truncated preview |
| Last-trade stop-path / fees | DATA_REQUIRED | `LAST_TRADE_PRINT_DATA_REQUIRED` |
| Missing minute interpolation | NOT_SUPPORTED | Fail closed / UNAVAILABLE |
| Production KalshiFeeModel | NOT_SUPPORTED | Estimated schedule only |

## Asked-six locks (reproduced)

| Lock | Value |
|---|---|
| N | 1182 |
| Four-cell | 883 / 108 / 0 / 191 |
| S | 883/1182 |
| p | 991/1182 |
| Ledger EV | 5700/1182 (4.82¢) |
| T40-close EV | 4058/1182 (3.43¢) |
| Planning L | 14705/299 |
| Path losses | 299 |
| Offset 0 sum | 10318 |
| Offset −1 sum | 14663 |
| Window rows | 3285 (not 3289) |

## Phase 16 checks

| Check | Result |
|---|---|
| SuperASI pytest | 28 passed (includes FIRST80_Q3 N=290 import when warehouse present) |
| `npx tsc --noEmit` | passed |
| `scripts/validate_roller.py` | PASS |
| `scripts/leakage_audit.py` | PASS |
| Full ROLLER pytest | Not re-run to completion in Phase 16. Phase 1 baseline: 467 passed, 1 failed, 1 skipped. Pre-existing: `test_research_query_indexes.py::test_indexed_execute_matches_scan`. SuperASI did not modify that test. |
| `git diff --name-only` | Workspace has no `.git`. Isolation checked by path inventory (below). |

## Isolation inventory

This session did **not** edit:

- `ROLLER/roller/research/first80.py`
- `ROLLER/roller/timeutil.py`
- `ROLLER/roller/research_query/` (no SuperASI tokens; Results rows remain capped at 200)
- FIRST01 / Risk / Execution / W9 / `crates/research-engine`
- `apps/terminal-efficiency/`
- `research/lebronner/` (no mass-rename)

Allowed hook: `ROLLER/roller/dashboard_adapter/research_executor.py` exposes uncapped `population.trades` while `population.rows` stays preview-capped.

`research_query/execute.py` already emits full `population.trades` for generic queries. That file has a 2026-09-10 mtime from earlier ROLLER work; SuperASI v1 did not add SuperASI imports there.

## Browser verification (2026-09-10)

Against `http://127.0.0.1:5179/` + API `:8791`:

- SuperASI header switch → Quick Start caveats visible
- Asked-six seed → Results N=1182, S=883/1182 (74.70%), p=991/1182 (83.84%), four-cell 883/108/0/191
- Default mix FIRST_BARRIER_CLOSE EV 3.43¢; ledger chip → 4.82¢; S unchanged
- Offset 0 = FIRST THROUGH-CLOSE / PATH EVENT 10318/299; +5 n=297
- Labs lists `asked_six_first80_80_40`
- ROLLER Results shows **Move to SuperASI** beside Save results
- **Move to SuperASI** is on the Results toolbar. Re-execute of a drifted/incomplete snapshot question failed closed (`EMPTY_POPULATION`) and surfaced the error code — client 228-row preview was not imported as N. Asked-six seed remains the locked full-population path.
