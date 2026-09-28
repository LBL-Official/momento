# Performance (measured, this machine)

Do not invent timings. Semantics must match; wall-clock may change.

Query: `first_touch_80_season` via
`ROLLER/scripts/benchmark_query_engine.py --compare`.
Optimized = current `execute_compiled` / `plan_query` (`rq_index_v1.0.0`).
Reference = `execute_reference` (CSV `full_scan`, never opens `rq_index`).
NHL skipped (`SOURCE_UNAVAILABLE`).

Raw JSON: `compare_tonight.json` (NBA / ATP / WTA from first pass;
WNBA / NCAAB / MLB from the post-fix retry).

## Tonight — indexed vs reference

| League | Basis | Mode opt / ref | N opt / ref | Identities | opt wall ms | ref wall ms | opt load ms | ref load ms |
| --- | --- | --- | ---: | --- | ---: | ---: | ---: | ---: |
| NBA 2025-26 | TRADABLE_YES_BID | indexed / full_scan | 1552 / 1552 | equal | 134 365 | 260 119 | 6 | 111 718 |
| NCAAB 2025-26 | TRADABLE_YES_BID | indexed / full_scan | 908 / 908 | equal | 18 428 | 30 376 | 0 | 23 708 |
| WNBA 2025 | TRADABLE_YES_BID | indexed / full_scan | 348 / 348 | equal | 4 813 | 7 899 | 0 | 5 540 |
| MLB 2025-26 | LAST_TRADE_PRINT | indexed / full_scan | 4162 / 4162 | equal | 39 203 | 61 687 | 1 | 49 387 |
| ATP 2025-26 | TRADABLE_YES_BID | indexed / full_scan | 1596 / 1596 | equal | 22 904 | 83 895 | 1 | 70 005 |
| WTA 2025-26 | TRADABLE_YES_BID | indexed / full_scan | 1869 / 1869 | equal | 24 340 | 21 382 | 1 | 7 511 |

WTA reference was faster than WTA indexed because the shared tennis CSV
tree had just been read for ATP; OS page cache, not a process warehouse cache
(`rq_cache.clear()` ran between every pair).

NBA optimized 134 s is a cold index open on this pass (first basketball
index after WNBA/MLB unavailable rows). Later NBA queries on a warm process
were previously measured at 0.8–3.2 s — see below.

## First pass (invalid rows — recorded, not used as equality proof)

| League | What happened |
| --- | --- |
| WNBA / MLB | `optimized_mode=unavailable`. Dual-write `.parquet` siblings were inside `dataset_fingerprint`. Fail-closed. Fingerprint now ignores `.parquet` / `.manifest.json`. Retry rows above. |
| NCAAB | ~17 ms / null N. Draft still sent `dataSources: ["ncaa"]` (`NO_WAREHOUSE_PBP`). Draft fixed; retry rows above. |

WNBA first-pass reference N=348 and MLB first-pass reference N=4162 matched the
retry Ns. Those first-pass reference timings (12 001 ms / 133 302 ms) were
colder CSV loads.

## Prior measured NBA indexed sweep (2026-09-11)

From `docs/research/research_query/QUERY_ACCELERATION.md`. Not re-invented tonight.

| Query | N | total_ms |
| --- | ---: | ---: |
| first_touch_80_q3 (cold open) | 297 | 45 829 |
| later NBA indexed queries | — | ~847–3 158 |
| MLB FT75 / TE lead+1 / 2026-04-01–2026-09-08 | 554 | 37 848 |

## Isolated golden pytest (opt opens `rq_index`, then cache-cleared reference)

Command (2026-09-12T05:53Z):

```text
cd ROLLER && .venv/bin/python -m pytest \
  tests/test_reference_vs_optimized.py::test_warehouse_increment2_reference_vs_indexed \
  tests/test_reference_vs_optimized.py::test_warehouse_mlb_554_reference_vs_indexed \
  -q --tb=line
```

**5 passed in 542.15 s.** Increment 2 generic four (1087 / 271 / 1552 / 288) and
MLB FT75 / TE lead+1 dated **N=554**. Optimized `execution_mode=indexed`.
Reference `full_scan`. Identities equal. Goldens not edited.
