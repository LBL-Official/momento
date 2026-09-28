# Phase 0 — ROLLER data / backtest reconnaissance

Generated: 2026-09-12 (local Friday 2026-09-11 evening). Counts are from files on disk at that time. No architecture was changed to produce this report.

This is facts only. Do not treat a declared `roller.json` path as data. Do not invent NHL.

---

## Current storage formats

Canonical research warehouse is **monthly CSV** under:

`ROLLER/data/{sport}/{season_key}/canonical/`

Season keys on disk: `2025_2026` (nba, ncaab, mlb, tennis), `2025` / `2026` (wnba).

| Format | Where | Role |
| --- | --- | --- |
| Monthly CSV `month=YYYY-MM.csv` | `canonical/kalshi_candles`, `kalshi_last_trade`, `pbp`, `polymarket_candles`, `kalshi_orderbook_snapshots` | Published research observations |
| Single CSV | `canonical/games.csv`, `kalshi_markets.csv`, `polymarket_markets.csv`, tennis `crosswalk.csv` | Games / settlement / metadata |
| JSON | `canonical/dataset_version.json` (MLB, tennis only); `raw/` staging; `data/.cache/` | Coverage notes, ingest staging, query cache |
| Parquet | `derived/research_query/indexes/rq_index_v1.0.0/{LEAGUE}/{tradable\|last_trade}/` | Observation **fact** indexes (not answers) |
| Parquet (external) | Backtesting Suite warehouse / landing | Ingest **source**, not Confirm & Run primary read |
| SQLite | none in `roller/` production loaders | — |
| pickle | none in `roller/` production loaders | — |

Canonical is **not** Parquet. Query hot path already reads derived parquet indexes when present.

---

## Current loaders

Central path: [`ROLLER/roller/admin.py`](../../ROLLER/roller/admin.py) `load_dataset` → [`io_csv.concat_partition_csvs`](../../ROLLER/roller/io_csv.py) (`glob("*.csv")` + `pd.read_csv` + `pd.concat`).

[`ROLLER/roller/research_query/execute.py`](../../ROLLER/roller/research_query/execute.py) `_read_scope_tables` loads up to four datasets per scope:

- candles via `market_path.candle_dataset_name` → `kalshi_candles` / `kalshi_last_trade` / `polymarket_candles`
- `pbp`
- `kalshi_markets`
- `games`

Then `to_dict("records")` and Python loops group by ticker / game.

Index builders call the same `_load_warehouse` CSV path, then write parquet.

Frozen FIRST80: [`ROLLER/roller/research/first80.py`](../../ROLLER/roller/research/first80.py) uses `load_dataset` (CSV). Confirm & Run frozen tuple goes to `execute_research_object`, **not** the generic index.

No production `sqlite` or `pickle.load` in `roller/`.

---

## Current execution paths

```text
terminal_api / jobs.submit_execute
  → compile_draft (no I/O)
  → execute_compiled
      → plan_query
          indexed  → open_scope_index (parquet facts) → observe_entry(precomputed=)
          full_scan → _load_warehouse (CSV) → TradableIndex.build → same detectors
          unavailable → DATA_REQUIRED (fail closed; no silent partial scan)
  → operations.py / path_engine / results_math
```

| Path | When | Data |
| --- | --- | --- |
| `generic_query` indexed | Valid `rq_index_v1.0.0` for every scope | Parquet bars / pbp / settlement / universe |
| `generic_query` full_scan | Any scope missing an index | Monthly CSV concat |
| `frozen_reference` | Exact FIRST80 tuple | `execute_research_object` / `first80.py` |
| Combined leagues | All scopes indexed → union; any missing → `full_scan` reason `combined_league_union` | Tennis ATP+WTA share one CSV tree, read once |

Detectors live in [`operations.py`](../../ROLLER/roller/research_query/operations.py). Indexes store facts. They must not redefine Cross / Touch / Bounce / Recovery.

---

## Current caches

| Cache | Location | Key / notes |
| --- | --- | --- |
| In-process warehouse | `research_query/cache.py` | `(universe_hash, dataset_version)` → payloads + `TradableIndex` |
| In-process entry/path | same | entry_hash / path_hash + dataset_version |
| Optional result cache | `result_cache.py`; `ROLLER_QUERY_RESULT_CACHE=1` | question + dataset + index + code + semantics versions; skips frozen |
| Scope table cache | `execute._SCOPE_TABLES_CACHE` | last shared tennis/basketball CSV load |
| Disk job/saves | `data/.cache/research_query/`, `research_saves/` | envelopes, not warehouse |

---

## Current indexes

Version: `rq_index_v1.0.0`.

Path: `data/{sport}/{season}/derived/research_query/indexes/rq_index_v1.0.0/{LEAGUE}/{tradable|last_trade}/`

Files: `bars.parquet`, `transitions.parquet`, `pbp_events.parquet`, `settlement.parquet`, `universe.parquet`, `manifest.json`.

| Leaf | Tickers | Games | Bar rows | Settlement rows | Built (UTC) |
| --- | ---: | ---: | ---: | ---: | --- |
| NBA tradable | 2704 | 1352 | 5 777 716 | 0 | 2026-09-11T22:30:49Z |
| NCAAB tradable | 1698 | 849 | 2 252 832 | 0 | 2026-09-11T22:31:46Z |
| WNBA 2025 tradable | 604 | 302 | 455 168 | 0 | 2026-09-11T22:31:58Z |
| WNBA 2026 tradable | 616 | 308 | 880 738 | 0 | 2026-09-11T22:32:15Z |
| MLB last_trade | 6862 | 3431 | 2 511 237 | 344 | 2026-09-11T22:24:22Z |
| MLB tradable | 399 | 26 | 7 408 | 344 | 2026-09-11T22:05:56Z |
| ATP tradable | 3171 | 1530 | 2 144 834 | 3074 | 2026-09-11T22:27:14Z |
| ATP last_trade | 3297 | 1651 | 766 489 | 3208 | 2026-09-11T22:32:37Z |
| WTA tradable | 3697 | 1753 | 1 948 434 | 3596 | 2026-09-11T22:28:09Z |
| WTA last_trade | 3845 | 1926 | 689 976 | 3746 | 2026-09-11T22:32:45Z |

LAST_TRADE_PRINT is never served from a tradable leaf.

---

## Current data duplication

- ATP and WTA share `data/tennis/2025_2026` physical tree. Indexes split by league leaf. Combined Confirm & Run must read the tree once (already implemented).
- Kalshi candles exist both as monthly CSV and as compact `bars.parquet` (derived, quality-filtered). Bar count ≤ CSV row count (untradable dropped from tradable index).
- External Backtesting Suite warehouse + Foundation landing hold source parquet/JSON that ingest copies into ROLLER CSV.
- Polymarket candles/markets sit beside Kalshi candles for basketball. They are a different observational type (last-trade-like). Do not flatten into yes_bid.

---

## Current repeated work

Inside `_load_warehouse` / index build (every cold full_scan):

1. `glob("*.csv")` per dataset
2. `read_csv` every month file as strings
3. `pd.concat`
4. `to_dict("records")` of the entire frame
5. Per-row Python grouping by ticker / game
6. Per-ticker sort + `quality()` / last-trade sequence
7. `dataset_version` fingerprint `rglob` over dataset files

Indexed execute skips 1–5 for bars/pbp/settlement. Detectors still scan compact bars per ticker.

---

## Current likely bottlenecks

Measured (do not invent new numbers here): see [`docs/research/research_query/QUERY_ACCELERATION.md`](../../docs/research/research_query/QUERY_ACCELERATION.md).

- Cold NBA CSV load historically ~45 s (`shared_warehouse_load_ms` 45 341).
- Cold NBA **indexed** first query ~45.8 s (index open + first scan); warm 0.8–3.2 s.
- MLB last-trade golden indexed ~37.8 s total, N=554.
- Tennis ATP+WTA candles ~5.0M CSV rows; double-load would ~2× that (fixed for shared tree).
- Combined NBA+NCAAB index union is 8.0M bar rows in memory.

---

## Current missing datasets / stale CSV

| Declared | On disk |
| --- | --- |
| `data/nhl/` | **ABSENT** — `UNAVAILABLE`, not `MISSING` |
| NBA / NCAAB `2026_2027` | **ABSENT** (declared in `roller.json`) |
| NBA / NCAAB / WNBA `kalshi_markets.csv` | **ABSENT** — index `settlement_rows=0` |
| NBA / NCAAB / WNBA `kalshi_last_trade/` | **ABSENT** (not used; candles are tradable yes_bid) |
| NBA / NCAAB orderbook canonical | **ABSENT** (declared) |
| MLB `kalshi_trades/` | empty directory |
| MLB `polymarket_candles/` | empty directory |
| Tennis polymarket / orderbook | **ABSENT** |
| NBA `first80_triggers.csv` | **ABSENT** (frozen path uses other bindings) |

Landing (Foundation/Ingest) at recon time: trades sidecar count **8546**, candles **5538**. Incomplete vs each other. Do not invent yes_bid from prints.

---

## Current schema inconsistencies

Observed headers (first line of files):

**Kalshi candles** (`yes_bid_*`): `internal_game_id,ticker,team_side,candle_timestamp,event_timestamp,available_at,ingested_at,yes_bid_open,yes_bid_high,yes_bid_low,yes_bid_close,yes_ask_open,yes_ask_high,yes_ask_low,yes_ask_close,volume,...`

**Kalshi last-trade** (`last_*_e4`): `internal_game_id,ticker,team_side,...,last_open_e4,last_high_e4,last_low_e4,last_close_e4,volume,print_count,is_valid,...` — **no yes_bid columns**. Do not rename `last_close_e4` to `yes_bid_close`.

**PBP basketball**: `event_timestamp,available_at,period,clock,home_score,away_score,...`

**MLB markets**: `result,settlement_value_e4,result_available_at,...`

**Orderbook snapshots**: top-of-book + depth JSON columns (`best_yes_bid_e4`, `yes_levels`, …). This is **not** reconstructed L2 history. Label remains snapshot / TOB+levels as stored.

Basketball Kalshi settlement file is missing while Polymarket markets exist with **no** yes/no `result`. Those are not interchangeable.

MLB `games.csv` box-score finals are not Kalshi settlement.

---

## Current PIT fields

`roller.json` as_of: `available_at < cutoff` (half-open). Equality excluded for basketball TE.

| Layer | Rule | File |
| --- | --- | --- |
| Constitutional I(t) | `available_at < observation_ts` | `base_terminal_efficiency/pit.py` |
| MLB snap | `event_timestamp <= snap_ts` (equality visible) | `mlb/snap.py` |
| Market bars | sort/key `available_at` (fallback candle/event ts) | `entry_engine` sequences |
| Canonical columns already present | `available_at`, `event_timestamp`, `ingested_at`, `candle_timestamp` / `captured_at` | CSV headers above |

Do not collapse these four clocks into one field.

---

## Current sport coverage

On-disk sport dirs: `mlb`, `nba`, `ncaab`, `tennis`, `wnba`.

| Sport | CODE | DATA | Notes |
| --- | --- | --- | --- |
| NBA 2025-2026 | yes | PARTIAL | Candles+PBP+games; no Kalshi settlement CSV |
| NCAAB 2025-2026 | yes | PARTIAL | Same; PBP games << Kalshi tickers |
| WNBA 2025 / 2026 | yes | PARTIAL | Same settlement gap |
| MLB 2025-2026 | yes | PARTIAL | Last-trade broad; candles thin; settlement 344 |
| ATP / WTA 2025-2026 | yes | PARTIAL | Shared tree; MCP PBP unmatched/ambiguous exist |
| NHL | overlay constant only | **UNAVAILABLE** | No `data/nhl/` |
| NFL / NCAAF | no warehouse | **UNAVAILABLE** | — |

---

## Current market coverage

Kalshi game markets are the Confirm & Run default (`markets: ["kalshi"]`).

Polymarket candles exist for NBA/NCAAB/WNBA. Compiler maps Polymarket to last-trade-like dataset `polymarket_candles`. Cross-venue joint basis is forbidden.

---

## Current PBP coverage

| Tree | Month files | Rows |
| --- | ---: | ---: |
| NBA | 9 | 780 137 |
| NCAAB | 6 | 398 585 |
| WNBA 2025 | 7 | 120 618 |
| WNBA 2026 | 4 | 132 002 |
| MLB | 17 | 1 757 845 |
| Tennis | 12 | 123 804 |

MLB `dataset_version.json`: 5 108 PBP games; 168 PBP-with-market. Tennis MCP: MATCHED / UNMATCHED / AMBIGUOUS recorded in tennis `dataset_version.json` — do not coerce UNMATCHED into a snap.

Missing PBP → UNALIGNED, not a fabricated event.

---

## Current settlement coverage

| Tree | `kalshi_markets.csv` | Settled yes/no |
| --- | ---: | --- |
| MLB | 344 | 340 (4 scalar) |
| Tennis | 18 194 | 17 640 (554 non-binary) |
| NBA / NCAAB / WNBA | **file missing** | index settlement 0 |

Polymarket markets: NBA 2 514, NCAAB 370, WNBA 182+340 — **0** binary results.

Settlement is Kalshi `result` when present. Never infer from PBP or box score. Missing ≠ NO.

---

## Current orderbook coverage

| Tree | Status |
| --- | --- |
| MLB | Live loop only. Canonical `month=2026-09.csv` **24 958** rows. Raw JSON dates 2026-09-11 and 2026-09-12. |
| NBA / NCAAB | Code + series exist; canonical dir **absent** |
| WNBA / tennis | Not in live series |

Historical L2 is **not invented**. Metadata parquet in Data-Real is market metadata, not L2.

---

## Current candle coverage

| Tree | Candle months | CSV rows | Tradable index bars |
| --- | --- | ---: | ---: |
| NBA | 2025-10 … 2026-06 | 6 165 183 | 5 777 716 |
| NCAAB | 2025-10 … 2026-04 | 2 674 280 | 2 252 832 |
| WNBA 2025 | 2025-05 … 2026-05 (gaps) | 501 214 | 455 168 |
| WNBA 2026 | 2026-05 … 2026-08 | 940 373 | 880 738 |
| MLB | 2025-04, 2025-10…2026-03, 2026-06–07 | 329 844 | 7 408 |
| Tennis | 13 months (gaps e.g. 2025-08, 2026-02, 2026-05) | 4 996 284 | ATP 2 144 834 + WTA 1 948 434 |

MLB last-trade months: 2025-04…11 and 2026-03…07 (**2 511 237** bars). That is the MLB Confirm & Run basis.

MLB candle months **absent vs last-trade**: 2025-05…09, 2026-04, 2026-05. Landing still catching up. LAST TRADE ≠ YES BID.

---

## Protected goldens (must not move)

| Object | N | Path |
| --- | ---: | --- |
| FIRST80 frozen | 290 | `frozen_reference` — not generic index |
| Increment 2 `second_touch_80` | 1087 | generic / indexed |
| Increment 2 `first_60_q2` | 271 | generic / indexed |
| Increment 2 `sequential_40_recover_80` | 1552 | generic / indexed |
| Increment 2 `layered_and` | 288 | generic / indexed |
| MLB FT75 / TE lead+1 dated | 554 | LAST_TRADE_PRINT |
| MLB 1661 | 1661 | results-layer verify-only envelope |

---

## Existing automation (do not duplicate)

- `scripts/mlb_kalshi_backfill_watchdog.sh` + `momento-research-ingest backfill`
- `scripts/mlb_canonical_catchup.sh`
- `ROLLER/scripts/ingest_orderbook_snapshots.py` (MLB live loop)
- `ROLLER/scripts/update_roller.py` (basketball offline update)
- `logs/com.momento.ncaab-ingest.plist` (NCAAB download-all)
- No `roller/auto_roller/` yet

---

## STOP / UNCLEAR (do not guess)

- Whether Kalshi will ever emit yes_bid for every MLB game in the backfill window — **UNCLEAR**. Treat remaining candle gaps as `MISSING` until landing has a sidecar, else `SOURCE_UNAVAILABLE` if Kalshi returns metadata-only.
- Basketball Kalshi settlement source for a future `kalshi_markets.csv` — **UNCLEAR**. Do not backfill from Polymarket or FIRST80 overlay into canonical markets.
- NHL warehouse — **UNAVAILABLE**. No reconstruction.

---

## Implication for later phases

Parquet-first means: one contract, eventually one published format. Tonight CSV remains what `load_dataset` reads. Derived `rq_index_v1.0.0` already is the optimized observation store. A second detector implementation would be a semantic fork — do not write one.
