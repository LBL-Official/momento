# Phase 8 — NBA physical Parquet layout

Measured: **2026-09-13T06:28:00Z** (write) and a subsequent fresh-process query pass.

Storage only. Confirm & Run still reads published CSV. Observation workload is **TRADABLE_YES_BID 1-minute candles**. Orderbook is not a physical dataset.

```text
observation_basis: TRADABLE_YES_BID
observation_resolution: 1_MINUTE_CANDLE
tick_data_available: false
orderbook_data_available: false
candle_pit_available: true
candle_pit_field: available_at
pbp_pit_aligned_to_candles: false
```

---

## 1. Baseline physical layout (`warehouse_v0`)

Path: `ROLLER/data/nba/2025_2026/derived/warehouse_v0/`

| Entity | Files | Rows | Bytes | Compression | Row groups |
| --- | ---: | ---: | ---: | --- | --- |
| Markets | 1 | 2,724 | 202,700 | SNAPPY | 1 |
| Settlements | 1 | 2,724 | 359,810 | SNAPPY | 1 |
| Observations (`basis=tradable_yes_bid`, 9 months) | 9 | 6,165,183 | 57,098,229 | SNAPPY | 1 / file |
| PBP (9 months) | 9 | 780,137 | 28,782,623 | SNAPPY | 1 / file |
| Crosswalk (lives at `ROLLER/meta/`) | 1 | 2,724 | 82,756 | SNAPPY | 1 |
| Orderbook parquet | **0** | **0** | — | — | — |

`warehouse_v0` tree: **25** files / **86,447,469** bytes (includes README, manifests, `orderbook/capability.json`).

October observations example: 541,322 rows, 5,086,132 bytes, 1 row group, SNAPPY. Sort as written by Phase 4: `ticker`, `available_at`.

Games were not a v0 parquet (identity remains `ROLLER/meta/game_identity.csv`).

---

## 2. Candidate layouts (October sample, 541,322 candle rows)

Partition bake-off on `month=2025-10.parquet` only. Codec for this bake-off: zstd, row group 262,144.

| Candidate | Grain | Files | Bytes | Write s | Single-game read s | Single-game files | Single-game rows |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| A | sport/season (1 file) | 1 | 3,292,457 | 0.514366 | 0.011784 | 1 | 541,322 (whole file) |
| B | sport/season/date | 25 | 3,401,497 | 0.723676 | 0.056655 | 25 | 1,136 |
| C | sport/season/month | 2 | 3,232,671 | 0.666019 | 0.040835 | 2 | 1,136 |
| D | one file / game | 137 | 6,849,681 | 0.906513 | 0.000885 | 1 | 1,136 |

October has **137** games and **25** distinct `available_at` dates. Full-season game-level partitioning would be **1,352** observation files. D already doubled bytes on one month (tiny-file tax). B/D rejected.

Candidate C in the bake-off regrouped by `available_at` month and therefore split one source file into 2 (UTC spill). The **selected** write does **not** re-bucket rows; it rewrites each existing `month=YYYY-MM.parquet` in place-equivalent grain (9 files).

---

## 3. Benchmark methodology

- Engine: `ROLLER/.venv` pandas 2.3.3 + pyarrow 22.0.0.
- Observation queries read `TRADABLE_YES_BID` parquet only. No ticks, trades, L2, or inferred TOB.
- Query A–F implemented in `roller/warehouse/layout_benchmark.py`.
- Date-range query prunes month partitions by `YYYY-MM`.
- Game-context query F is a storage join (Game/Market/candles/PBP loads). Not `get_research_context`. Not PBP↔candle PIT alignment.
- Candidate bake-off used October only. Full-season timings used the live trees.
- Selected-layout query memory was re-measured in a **fresh process** so peak RSS is not the warehouse-write footprint.

---

## 4. Selected layout

```text
ROLLER/data/nba/2025_2026/derived/warehouse/
  games/games.parquet
  markets/markets.parquet
  game_market_links/links.parquet
  settlements/settlements.parquet
  observations/basis=tradable_yes_bid/month=YYYY-MM.parquet
  pbp/month=YYYY-MM.parquet
  manifest.json
  README.md
```

No `orderbook/` partition.

`warehouse_v0` is retained as the Phase 3–7 baseline.

---

## 5–8. Partition, sort, compression, row groups

**Partition:** sport/season in the path; month Hive files for observations and PBP (Candidate C). Small facts are one file each (Candidate A).

**Sort:**

| Dataset | Sort keys |
| --- | --- |
| Observations | `internal_game_id`, `market_id`, `available_at` |
| PBP | `internal_game_id`, `event_number` |
| Settlement / Market / Link | `market_id` |
| Games | `internal_game_id` |

`available_at` is the candle PIT key. It is not replaced by `event_timestamp`.

**Compression** (October, 541,322 rows, row group 262,144):

| Codec | Bytes | Write s | Read s |
| --- | ---: | ---: | ---: |
| none | 7,852,549 | 0.498299 | 0.012538 |
| snappy | 5,053,487 | 0.495722 | 0.012341 |
| zstd | 3,292,457 | 0.501362 | 0.012251 |
| gzip | 3,267,560 | 0.998445 | 0.013469 |

zstd chosen: nearly gzip size, gzip write time is **1.99×** zstd, read times are within 1 ms.

**Row groups** (October, zstd):

| row_group_size | Bytes | Row groups | Avg rows / group | Write s | Read s |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 0 (pandas default) | 3,426,858 | 1 | 541,322 | 0.484565 | 0.017094 |
| 65,536 | 3,674,130 | 9 | 60,146 | 0.508982 | 0.015120 |
| 262,144 | 3,292,457 | 3 | 180,440 | 0.619273 | 0.016548 |
| 524,288 | 3,417,695 | 2 | 270,661 | 0.638258 | 0.017825 |

262,144 chosen: smallest bytes, useful predicate groups without 9-way split overhead.

---

## 9–10. Selected file counts and bytes

| Entity | Files | Rows | Bytes | Compression | Row groups |
| --- | ---: | ---: | ---: | --- | --- |
| Games | 1 | 1,362 | 61,781 | ZSTD | 1 |
| Markets | 1 | 2,724 | 135,189 | ZSTD | 1 |
| GameMarketLink | 1 | 2,724 | 63,316 | ZSTD | 1 |
| Settlements | 1 | 2,724 | 225,760 | ZSTD | 1 |
| Observations | 9 | 6,165,183 | 38,465,715 | ZSTD | 3 on Oct (180,440 avg) |
| PBP | 9 | 780,137 | 22,039,155 | ZSTD | month files |

Selected tree: **24** files / **60,992,850** bytes. No orderbook parquet.

Observation bytes vs baseline: 57,098,229 → 38,465,715.

---

## 11–12. Read benchmarks and memory

Fresh-process selected timings. Baseline timings from the pre-write process.

| Query | Meaning | Baseline rows / files / s / RSS MB | Selected rows / files / s / RSS MB |
| --- | --- | --- | --- |
| A | 1-minute candles for `NBA_20251010_BOS_TOR` | 1,136 / 9 / 0.300747 / 236.875 | 1,136 / 9 / 0.275313 / 230.500 |
| B | 1-minute candles for `KXNBAGAME-25OCT10BOSTOR-BOS` | 653 / 9 / 0.272647 / 256.062 | 653 / 9 / 0.336977 / 240.781 |
| C | candles `2025-10-10` … `2025-10-31` | 481,593 / 1 / 0.036550 / 256.062 | 481,593 / 1 / 0.034870 / 243.547 |
| D | season candle row-count (metadata) | 6,165,183 / 9 / 0.001137 / 256.062 | 6,165,183 / 9 / 0.001251 / 243.547 |
| E | PBP for `NBA_20251010_BOS_TOR` | 613 / 9 / 0.039829 / 256.062 | 613 / 9 / 0.042937 / 243.547 |
| F | storage join candles+PBP for that game | 1,136 + 613 / 18 / 0.303938 / 256.062 | 1,136 + 613 / 18 / 0.269448 / 243.547 |

Query times are comparable. This phase is not a latency claim. The gain that is measured is **lossless zstd layout + explicit contract + smaller bytes**.

---

## 13. Integrity / fingerprints

Payload fingerprints of baseline `warehouse_v0` vs selected `warehouse/`:

| Dataset | Rows | SHA-256 |
| --- | ---: | --- |
| Observations (incl. `available_at`) | 6,165,183 | `2ef7766470c6eec2549e35e3b02b4cf6057eba3f934e55a0533cde768f6e9eff` |
| PBP | 780,137 | `81153aa19d104bcd581ed5ff78e70659da66dcb703d1ccea371965778ee215aa` |
| Settlements | 2,724 | `d296295757fb88bd10b1440745aefc6d02b21473616a7798c8fb1d718c7a6b26` |

Match: **yes**. `available_at` multiset checked per month during write; drift would have aborted.

Games parquet is a physical projection of Phase 2 identity (1,362 NBA rows). IDs unchanged. `home_win` is not copied.

---

## 14. Rationale

- Keep month grain: 9 observation files is enough to prune a date window (Query C touched 1 file) without 1,352 game files or 25+ daily files per month.
- Keep `observations/basis=tradable_yes_bid/` so the directory cannot be read as a generic tick/L2 bucket.
- zstd at 262,144-row groups: measured smallest October size among the useful group sizes, without gzip’s write penalty.
- Sort by `internal_game_id`, `market_id`, `available_at` matches later game/market/PIT access without changing PIT values.
- Do not materialize orderbook. Phase 7 already declared `SOURCE_UNAVAILABLE` / 0 rows.

Confirm & Run was not pointed at this tree.

---

## 15. Tests

`tests/test_warehouse_layout.py` (fingerprint/`available_at`, basis path, no L2 partition, games projection without `home_win`, execute/CSV isolation, live contract).

---

## 16. Status

**PHASE 8: COMPLETE**
