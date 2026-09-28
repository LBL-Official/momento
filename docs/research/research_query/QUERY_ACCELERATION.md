# Query acceleration

Generic candle queries only. Frozen FIRST80 is unchanged.

## 1. Baseline (Increment 2, already measured)

Do not invent timings. Source: `ROLLER/docs/research_query/INCREMENT2_DESIGN.md` and Increment 1 goldens.

| Stage | Reality |
| --- | --- |
| Canonical CSV load | 45 341 ms pandas concat of the NBA season |
| Generic entry scan | 10–23 s over 2704 tickers |
| Generic path | 3–14 s |
| Cold interactive RUN | ~60–75 s |
| Frozen FIRST80 | 109 ms, N=290 |

`facts.py` `TradableIndex` and Increment 2 caches are in-process only. Cold start rereads monthly CSV.

## 2. Problem

The generic engine answers new operations by scanning tradable closes. The warehouse load, not the detector, dominates latency. An index that stored **answers** would freeze rates. The index must store **facts**.

## 3. Representation bake-off (measured)

Script: `ROLLER/scripts/benchmark_query_engine.py --bakeoff`

Series: `79,80,80,80,79,80` (one-touch test: two upward crossings of 80).

| Representation | Rows / cells | Build ms (this machine) |
| --- | --- | --- |
| A transitions `(prior_e4, current_e4, ts)` | 5 | 0.018 |
| B 91-cent crossing grid | 91 prices, 2 cells | 0.053 |
| C compact tradable bars | 6 | 0.017 |

One-touch test **passed** (`crossings_80 == 2`). Recommendation: **A + compact bars**. B explodes storage. C still requires a per-query scan. A answers any P exactly: up-cross `prior < P ≤ current`; down-cross `prior > P ≥ current`; break is strict beyond.

## 4. Index design

Package: `ROLLER/roller/research_query/indexes/`

Version: `rq_index_v1.0.0`

Path: `ROLLER/data/{sport}/{season}/derived/research_query/indexes/{index_version}/{LEAGUE}/{tradable|last_trade}/`

ATP and WTA share `data/tennis/2025_2026` and write separate league leaves. LAST_TRADE_PRINT is never served from a tradable leaf.

| File | Fact |
| --- | --- |
| `transitions.parquet` | consecutive tradable `(prior_e4, current_e4, ts, ticker, game)` |
| `bars.parquet` | compact series (`team_side` when the source row has it) |
| `pbp_events.parquet` | source PBP fields with `event_time` for as-of snap (score/inning/period; never future-looking) |
| `settlement.parquet` | Kalshi `result` only; empty if markets CSV is empty |
| `universe.parquet` | ticker/game partition |
| `manifest.json` | versions, checksums, coverage |

Builders call the same `_load_warehouse` sources. Detectors stay in `operations.py`.

```text
python -m roller.research_query.indexes build --league NBA --season 2025-2026
python -m roller.research_query.indexes build --league MLB --season 2025-2026 --basis LAST_TRADE_PRINT
python -m roller.research_query.indexes build-all
```

## 5. Planner

`plan_query` runs only on `GENERIC_QUERY`.

- Index absent → `full_scan`
- Index present and valid → `indexed` (same Phase 1 detectors on compact bars)
- Index present but stale/corrupt/out of coverage → `DATA_REQUIRED` (fail closed)

Envelope additions only: `performance.execution_mode`, `performance.index_version`, `performance.rows_scanned`.

## 6. Result cache

Optional. Key:

`question_hash + dataset_version + index_version + code_version + operation_semantics_version`

Never `cache["FIRST80"]`. Increment 2 in-process caches remain the warm-process layer. Enable with `ROLLER_QUERY_RESULT_CACHE=1`. Disk dir: `ROLLER_QUERY_RESULT_CACHE_DIR`.

## 7. Semantics unchanged

Phase 1 detectors are the reference. Indexed execute feeds `observe_entry(..., precomputed=bars)`. Sequential REACH→RECOVER stays an ordered state machine. Period/clock still apply after the game-level event + snap.

## 8. Fail-closed

| Condition | Behavior |
| --- | --- |
| No index directory | full scan |
| Checksum mismatch | DATA_REQUIRED |
| `dataset_version` ≠ current fingerprint | DATA_REQUIRED |
| Query dates outside declared coverage | DATA_REQUIRED |
| Empty Kalshi markets | `terminal_missing`; no box-score fill |

## 9. Indexed vs scan (fixture)

`tests/test_research_query_indexes.py` rebuilds a two-ticker index and asserts the same qualifying tickers and `population_n` as the full-scan path.

A full-season index build is I/O bound by the same CSV load. After that, Confirm & Run reads parquet facts.

### Index build (this machine, 2026-09-11)

`python -m roller.research_query.indexes build-all`. Do not treat these as query latencies.

| League | Season | Basis | Tickers | Bar rows | Elapsed s |
| --- | --- | --- | ---: | ---: | ---: |
| ATP | 2025-2026 | TRADABLE_YES_BID | 3171 | 2 144 834 | 112.970 |
| WTA | 2025-2026 | TRADABLE_YES_BID | 3697 | 1 948 434 | 52.686 |
| NBA | 2025-2026 | TRADABLE_YES_BID | 2704 | 5 777 716 | 222.125 |
| NCAAB | 2025-2026 | TRADABLE_YES_BID | 1698 | 2 252 832 | 93.344 |
| MLB | 2025-2026 | LAST_TRADE_PRINT | 6862 | 2 511 237 | 162.526 |
| MLB | 2025-2026 | TRADABLE_YES_BID | 399 | 7 408 | 54.255 |
| WNBA | 2025 | TRADABLE_YES_BID | 604 | 455 168 | 15.129 |
| WNBA | 2026 | TRADABLE_YES_BID | 616 | 880 738 | 21.776 |
| ATP | 2025-2026 | LAST_TRADE_PRINT | 3297 | 766 489 | 38.581 |
| WTA | 2025-2026 | LAST_TRADE_PRINT | 3845 | 689 976 | 12.529 |

MLB tradable bar_rows=7408 is the landed yes_bid set at that ingest, not last-trade coverage. LAST TRADE ≠ YES BID.

### Indexed query (this machine, 2026-09-11)

Planner: every listed warehouse opened `execution_mode=indexed`. ATP+WTA union 6 548 tickers / 4 093 268 rows. NBA+NCAAB union 4 402 tickers / 8 030 548 rows.

| Query | Mode | N | dataset_load_ms | total_ms |
| --- | --- | ---: | ---: | ---: |
| MLB FT75 / TE lead+1 / 2026-04-01–2026-09-08 | indexed | 554 | 1 655 | 37 848 |
| Increment 2 generic matrix (NBA) | indexed | 1087 / 271 / 1552 / 288 | — | same N after snap rebuild (27-test pytest 170.88 s including index + MLB golden) |
| Frozen FIRST80 | frozen_reference | 290 | — | not routed through the generic index |

`pytest tests/test_mlb_golden_fixture.py::test_golden_warehouse_identity` passed on the last-trade index after PBP score + `team_side` facts were stored. Increment 2 N unchanged after the snap/`team_side` rebuild.

### Warehouse NBA sweep (this machine, 2026-09-11)

Command:

```text
cd ROLLER && .venv/bin/python scripts/benchmark_query_engine.py --warehouse --leagues NBA
```

Raw: `/tmp/roller-warehouse-bench-nba.json`. Every row `execution_mode=indexed`, `index_version=rq_index_v1.0.0`, 2 704 tickers / 5 777 716 rows. First query pays the cold index open (~45 s). Later queries hit the in-process warehouse cache.

| Query | N | total_ms | dataset_load_ms |
| --- | ---: | ---: | ---: |
| first_touch_80_q3 | 297 | 45 829 | 2 |
| second_touch_80_q3 | 209 | 847 | 0 |
| first_touch_60_q2 | 271 | 1 030 | 0 |
| first_60_and_80 | 1 242 | 2 885 | 0 |
| first_80_reach_40 | 1 552 | 2 939 | 0 |
| first_80_reach_40_recover_80 | 1 552 | 2 473 | 0 |
| first_touch_80_season | 1 552 | 2 416 | 0 |
| price_sweep_55 | 1 577 | 2 881 | 0 |
| price_sweep_60 | 1 593 | 2 832 | 1 |
| price_sweep_65 | 1 602 | 2 964 | 0 |
| price_sweep_70 | 1 595 | 3 158 | 0 |
| price_sweep_75 | 1 576 | 3 117 | 0 |
| price_sweep_80 | 1 552 | 2 | 0 |
| period_sweep_Q1 | 236 | 1 110 | — |
| period_sweep_Q2 | 281 | 1 243 | — |
| period_sweep_Q3 | 297 | 1 | — |
| period_sweep_Q4 | 399 | 1 671 | — |
| reach_35 | 1 552 | 2 553 | — |
| reach_40 | 1 552 | 2 | — |
| reach_45 | 1 552 | 2 878 | — |

`first_touch_60_q2` N=271 and `first_80_reach_40_recover_80` N=1552 match Increment 2 goldens. Sub-3 ms rows are in-process result-cache hits, not a faster detector.

## 10. FIRST80 isolation

Exact FIRST80 tuple still calls `execute_research_object`. Generic never claims `warehouse_frozen_v1`. Tagged WIN/LOSS drafts are generic. `first80.py` was not edited.

## 11. Non-goals

Exit-path bounce/revert/maximum_move/minimum_move/never_reach. Box-score settlement. Precomputed win-rate parquets. Loading the warehouse into RAM as the optimization. High/low, ticks, L2, fees, Sharpe, XIB/MCD. Routing FIRST80 through the generic index.

## 12. How to run

```text
cd ROLLER
.venv/bin/python scripts/benchmark_query_engine.py --bakeoff
.venv/bin/python -m roller.research_query.indexes build --league NBA --season 2025-2026
.venv/bin/python -m pytest tests/test_research_query_operations.py tests/test_research_query_indexes.py -q
```
