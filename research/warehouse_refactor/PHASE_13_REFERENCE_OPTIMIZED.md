# Phase 13 — Reference ≡ Optimized

Measured: **2026-09-13**. Correctness only. Not a performance project.

```text
same ResearchPlan
+
same ResearchContext
+
independent traversal (nested loop vs in-memory index)
=
identical BacktestRow set
```

Module: `ROLLER/roller/warehouse/conditional_backtest.py`.

- **Reference** (`engine_id=reference`): `for game / market / ordered bars` → `evaluate_market`.
- **Optimized** (`engine_id=optimized`): group/index bars by `(internal_game_id, ticker)`, prune markets with no observations, then the **same** `evaluate_market`.
- Detectors stay in `operations.py` / `path_engine` / `observe_entry`. Optimized does not redefine inequalities.
- `compare_backtest_rows` is identity-keyed (`internal_game_id`, `market_id`, `entry_timestamp`, `entry_operation`). Any field difference is a failure. No “99.9%” pass.
- `result_hash` hashes `to_dict()` without `engine_id` so equal rows produce equal hashes.

Confirm & Run still reads CSV. No parquet layout change. No EV/CI.

---

## Invariant

```text
REFERENCE = OPTIMIZED
DIFFERENCES = 0
```

---

## Live NBA warehouse (2025-10-10)

### Required Q2 spec (not FIRST80)

```text
Q2 CROSS 63¢ · WIN REACH 87¢ · LOSS REACH 41¢ · HOLD_TO_SETTLEMENT
plan_hash 4547787d8dfdb8c40717d7321e399179e868a67f0b069cadabc3f7964f9ffa67
warehouse_version 2026-09-13T06:28:48Z
```

| Field | Reference | Optimized |
| --- | --- | --- |
| Status | `ZERO_RESULTS` | `ZERO_RESULTS` |
| Population | 0 | 0 |
| result_hash | `1b0ce3dc4fb863a2c9b7517669ca1e5936a02d07dab4905d896ab2dc8894a0f6` | same |
| Difference count | **0** | **0** |
| Difference rows | none | none |

Exclusions (both engines): `period_filter` 5, `no_event` 3, `period_unaligned` 2.

Catalog / Context / Plan: READY / READY / READY. Engine ran.

### Same date, no period chip (row-level proof)

| Field | Reference | Optimized |
| --- | --- | --- |
| Status | `READY` | `READY` |
| Population | 7 | 7 |
| Classifications | WIN 1 / LOSS 6 | WIN 1 / LOSS 6 |
| result_hash | `3ff90cf3b331db7909790f3180d5b54e1d3df6027d8dcfe277c3928397d02382` | same |
| Difference count | **0** | **0** |

`NBA_20251010_BOS_TOR` BOS: LOSS at `2025-10-10T23:36:00Z`, entry_value 7000, settlement YES (path classification; not a fill).

---

## Synthetic matrix

CROSS, TOUCH, ordinal TOUCH, all entry ops, Q2 period, clock window, sequential AND, WIN-only / LOSS-only / both, HOLD / MISSING / INVALID settlement, jump-through, OT ≠ Q4, duplicate game records → one row, repeated-run hashes.

Every case: `compare_backtest_rows` empty; `result_hash` equal.

---

## Completion

```text
REFERENCE = OPTIMIZED
DIFFERENCES = 0
PHASE 13 = COMPLETE
```
