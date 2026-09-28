# Phase 15 — Performance

Measured on this machine: **2026-09-13**. Numbers below are from
`ROLLER/scripts/benchmark_conditional_backtest.py`. They are not invented.

Semantics-invisible pass. Detectors stay in `operations.py` / `path_engine` /
`observe_entry`. Phase 8 layout unchanged. Adjacent-month UTC spill in
`_months_for_dates` kept. Confirm & Run still reads CSV.

```text
REFERENCE = OPTIMIZED
DIFFERENCES = 0
```

---

## Methodology

- Engine: `ROLLER/.venv` (pandas + pyarrow).
- Warehouse: `ROLLER/data/nba/2025_2026/derived/warehouse/`
  `updated_at` **2026-09-13T06:28:48Z**.
- Clocks split: catalog, compile, context, reference, optimized, peak RSS,
  parquet files opened, month files, observation/PBP rows, population.
- `clear_context_cache()` before each measured query.
- Baseline recorded **before** context changes (`/tmp/p15_baseline_a.json`,
  `/tmp/p15_baseline_bde.json`).
- After numbers: B–E `/tmp/p15_after3_bde.json`; A context+optimized
  `/tmp/p15_after_a2.json` (`--skip-reference`; A reference was 542.698s at
  baseline and was not re-run — Reference remains the nested-loop oracle).

Queries (warehouse-backed, not FIRST80):

| ID | Spec |
| --- | --- |
| A | 2025-10-10–2026-06-13 CROSS 63 / REACH 87 / REACH 41 |
| B | 2025-10-10 only |
| C | B + Q2 + PBP (`plan_hash` `4547787d…`) |
| D | B + sequential AND ABOVE 70 |
| E | same chips as C (valid ZERO_RESULTS) |

---

## Baseline (before optimization)

Catalog cold: **2.087s** (A process) / **2.139s** (B–E process).

| Query | Context s | Ref s | Opt s | Pop | Obs | PBP | Months | Peak RSS MB | diffs |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| A | 91.680 | 542.698 | 41.160 | 1908 | 6,165,183 | 0 | 9 | 4210 | 0 |
| B | 0.082 | 0.008 | 0.007 | 7 | 5,125 | 0 | 2 | 313 | 0 |
| C | 0.120 | 0.015 | 0.013 | 0 | 5,125 | 3,176 | 2 | 345 | 0 |
| D | 0.080 | 0.007 | 0.008 | 7 | 5,125 | 0 | 2 | 359 | 0 |
| E | 0.116 | 0.012 | 0.013 | 0 | 5,125 | 3,176 | 2 | 376 | 0 |

A classifications: WIN 1046 / LOSS 846 / SAME_BAR_TIE 3 / HELD_TO_SETTLEMENT 13.

Full hashes (from the JSON artifacts):

```text
A plan_hash    854de7c3d9f9c6f32dcfaeef79ead71d96fafb1d43aa72b35c4589526ffaca5c
A result_hash  bcfe1a20f9b2ee599a89cbcf6e28bcb8832f9e9c8899fa6287904263c5f6d87a
B plan_hash    d8c10b912b20a45b0f9909cb759f2dee8a23298cd55df21ab94feb9e2432a35a
B result_hash  3ff90cf3b331db7909790f3180d5b54e1d3df6027d8dcfe277c3928397d02382
C/E plan_hash  4547787d8dfdb8c40717d7321e399179e868a67f0b069cadabc3f7964f9ffa67
C/E result_hash 1b0ce3dc4fb863a2c9b7517669ca1e5936a02d07dab4905d896ab2dc8894a0f6
D plan_hash    a22a381d5bdbc89dfffdd14c4af3af8df97e90ac8fbab0e314167af85389a0d3
D result_hash  e4e00ef8cd1b7dd24114b3b647862d174c1a870842360401be77309c7e9b9cad
```

Raw script output (not invented):

```text
research/warehouse_refactor/phase15_measurements/p15_baseline_a.json
research/warehouse_refactor/phase15_measurements/p15_baseline_bde.json
research/warehouse_refactor/phase15_measurements/p15_after_a2.json
research/warehouse_refactor/phase15_measurements/p15_after3_bde.json
```

E (October Q2) opened `month=2025-10` and adjacent `2025-11` only. It did
**not** open `2026-06`.

A reference cost is O(markets × season observations). Left as the oracle.

---

## After (projection, plan-driven materialization, cache, default optimized)

What changed (no detector math, no parquet semantic change):

- Column projection on parquet reads (entity constructor fields only).
  `basis` is **not** projected on observations — pyarrow
  `string` vs `dictionary` merge is `ArrowTypeError`.
- Date / id predicates applied in pandas after read (same reason: no
  warehouse `filters=` on those files).
- `ResearchPlan.context_requirements` drives obs/PBP load. Plain CROSS
  does not open PBP. Q2 does (3,176 events on 2025-10-10).
- Deterministic context cache: `plan_hash` + warehouse/catalog/identity
  versions + manifest mtime/size + dates + basis + PIT + requirements.
  No `current_time`. `clear_context_cache()` invalidates.
- `_records()` instead of `to_dict("records")`.
- `run_conditional_backtest(..., engine_id=optimized)` is the default.
  Reference is unchanged nested-loop.

| Query | Context s | Ref s | Opt s | Pop | Obs | PBP | diffs | result_hash |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| A | **67.242** | (not re-run; baseline 542.698) | **29.302** | 1908 | 6,165,183 | 0 | n/a (skip-ref) | `bcfe1a20…` (same) |
| B | 0.551 | 0.010 | 0.009 | 7 | 5,125 | 0 | 0 | `3ff90cf3…` |
| C | 0.565 | 0.018 | 0.014 | 0 | 5,125 | 3,176 | 0 | `1b0ce3dc…` |
| D | 0.451 | 0.007 | 0.009 | 7 | 5,125 | 0 | 0 | `e4e00ef…` |
| E | 0.528 | 0.015 | 0.016 | 0 | 5,125 | 3,176 | 0 | `1b0ce3dc…` |

A after peak RSS **4607 MB**. A classifications unchanged
(1046 / 846 / 3 / 13). Same plan hashes as baseline.

### Honest deltas

- **A context:** 91.680s → 67.242s.
- **A optimized:** 41.160s → 29.302s.
- **B–E context:** slower in this process (~0.08–0.12s → ~0.45–0.56s).
  Not claimed as a speedup. Date pruning, PBP skip, and cache still hold.
- Adjacent-month spill remains (Oct query still opens Nov).

---

## Tests

`ROLLER/tests/test_warehouse_performance.py` (6):

- Date query does not open 2026-06 / 2026-03; Oct + Nov spill allowed.
- Plain query PBP rows 0; Q2 loads 3,176.
- Projection: no `last_close_e4` on constructed observations.
- Cache hit / `clear_context_cache`.
- Repeated Q2 hashes (`4547787d…`).
- Live 2025-10-10 Reference ≡ Optimized, population 7, diffs = 0.

Re-run: `test_conditional_backtest_equivalence.py`,
`test_conditional_backtest_edge_cases.py` — green.

Phase 15 complete. Next authorized phase is **16**. Do not start it from this report.
