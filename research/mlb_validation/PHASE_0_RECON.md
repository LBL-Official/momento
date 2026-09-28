# PHASE 0 — MLB Validation Reconnaissance

Status: **COMPLETE** (inspect only)

This report documents the current MLB research warehouse, the frozen golden
measurement object, settlement coverage, TE/PIT implementation, tests, and
protected surfaces.

It does **not** implement settlement ingest, edge, execution realism, or
production logic. It does **not** change ROLLER semantics.

Inspected: 2026-09-11.

---

## PHASE 0 STATUS

| Gate | Status |
| --- | --- |
| Repo/data reconnaissance | **PASS** |
| Golden contract preserved | **PASS** (documented; not rewritten) |
| Dated N preserved at 554 | **PASS** |
| Last-trade identity preserved | **PASS** |
| PIT semantics documented | **PASS** |
| Settlement source identified | **PASS** (`kalshi_markets.result`) |
| FIRST80 contamination excluded | **PASS** (overlay unused; 0 MLB joins) |
| Missing 470 preserved | **PASS** |
| Scalar results identified | **PASS** (4 warehouse rows; 0 in the 554) |
| Existing tests identified | **PASS** |
| Protected systems identified | **PASS** |
| Phase 1 implementation | **NOT STARTED** |
| Phase 0 | **COMPLETE** |

---

## Golden contract (do not rewrite)

Frozen fixture: [`ROLLER/tests/fixtures/mlb_golden_ft75_lead1_dated.json`](../../ROLLER/tests/fixtures/mlb_golden_ft75_lead1_dated.json)

| Layer | Value |
| --- | --- |
| Sport / league / season | Baseball / MLB / 2025–26 |
| Date window | **2026-04-01 → 2026-09-08** |
| Market | Kalshi |
| Observation basis | **LAST_TRADE_PRINT** · `last_trade_close_cross` |
| Price field | `last_close_e4` |
| Entry | FIRST_TOUCH **7500** |
| TE | YES leading, exact lead **+1** |
| PIT | `PBP_ts <= entry_ts` |
| LOSS | REACH **4000** |
| WIN | HOLD_TO_EXPIRATION / terminal YES |
| Execution path | `generic_query` (not FIRST80, not `warehouse_frozen_v1`) |
| `question_hash` | `aaef0cbd185379f060a17077957ad50ee9cd2b4b25c339f1f3c1b25695060449` |
| `universe_hash` | `9484949819ca08afff3deb8adb171cb392812ba23412179de5b81f1023af78be` |

Do not reinterpret:

- **59** WIN_EXIT as “reached 40”
- **495** path_false as “495 losses”
- **65/84** as MLB terminal efficiency

Last trade ≠ yes bid. Candle/print path ≠ fill. Path WIN ≠ terminal YES.
Box-score win ≠ Kalshi settlement. Missing settlement ≠ YES/NO/0.

---

## Exact data sources

### Canonical warehouse

Root: [`ROLLER/data/mlb/2025_2026/canonical/`](../../ROLLER/data/mlb/2025_2026/canonical/)

From [`dataset_version.json`](../../ROLLER/data/mlb/2025_2026/canonical/dataset_version.json):

| Field | Value |
| --- | --- |
| `dataset_version` | `cb7cff4fcd52576a3b07aa4cead006032678d01a30e6a36b872085d041714ecc` |
| `pipeline_version` | `4.0.0-C` |
| `generated_at` | `2026-09-11T15:02:15Z` |
| PBP source | `mlb_statsapi` |
| Crosswalk | `Backtesting Suite/Data/MLB/2025-2026/warehouse/normalized/mlb/pbp/game_crosswalk.json` |
| Market roots | `Backtesting Suite/Data-Real/MLB/2025-2026`, `Backtesting Suite/Data/MLB/2025-2026` |

Warehouse files used by the golden path:

- `games.csv`
- `pbp/month=*.csv`
- `kalshi_markets.csv`
- `kalshi_last_trade/month=*.csv`
- `kalshi_candles/month=*.csv` (present; **not** the golden observation basis)

### Market-metadata ingest

[`ROLLER/roller/mlb/ingest.py`](../../ROLLER/roller/mlb/ingest.py) `collect_metadata` reads:

```text
Backtesting Suite/Data-Real/MLB/2025-2026/orderbook/date=*/metadata.parquet
```

`build_markets` copies Kalshi `result` / `settlement_ts` into `kalshi_markets.csv`.
Settlement is never inferred from PBP.

Secondary root `Backtesting Suite/Data/MLB/2025-2026` has **zero**
`metadata.parquet` files.

Data-Real metadata date folders: 35 paths exist. Non-empty result rows are
only **2026-06-18 → 2026-06-30**. Earlier folders (including all 2025 dates
and 2026-06-01 → 2026-06-17) are empty.

### Dated execution artifact

[`ROLLER/data/.cache/research_query/mlb-dated-2026-04-01-2026-09-08-job.json`](../../ROLLER/data/.cache/research_query/mlb-dated-2026-04-01-2026-09-08-job.json)

- `job_id`: `2f99745805d0462f8794f8e8b7fb823c`
- `population.trades`: **554** rows
- Unique tickers: **554**
- Unique `internal_game_id`: **504** (multiple observations can share a game)

### FIRST80 official-W overlay (not used for this object)

[`ROLLER/roller/research_query/official_settlement.py`](../../ROLLER/roller/research_query/official_settlement.py)

- Overlay sports: **NBA, NCAAB, WNBA, NHL** only
- This MLB dated job: `overlay_applied=false`, `n_direct=0`, `n_complement=0`
- `terminal_source=kalshi_markets.result`

### Research object that is **not** this contract

[`research/mlb_first80_80_40_v1/`](../mlb_first80_80_40_v1/) is a different
object (yes_bid FIRST80 / close-40, N≈4303). It is **not** a settlement
source for the golden 554. Do not join its W onto this population.

---

## Row counts / game counts / ticker counts

### Warehouse (full 2025–2026)

| Object | Count | Notes |
| --- | --- | --- |
| Games | 5178 | `game_date` 2025-03-18 → 2026-09-04 |
| Dated-window games | 2050 | 2026-04-01 → 2026-09-04 (warehouse max date) |
| PBP rows | 1,757,845 | |
| PBP games | 5108 | |
| Dated PBP games | 2010 | game-day in 2026-04-01 → 2026-09-08 |
| `kalshi_markets` | 344 | 170 yes / 170 no / 4 scalar |
| Markets with game | 342 | 2 null `internal_game_id` |
| PBP-with-market | 168 | warehouse coverage note |
| Last-trade bars | 2,511,237 | |
| Last-trade tickers (all months) | 6862 | |
| Last-trade tickers in dated window | 2392 | matches golden `universe_tickers` |
| Genuine candles | 329,844 | not the golden basis |
| Trade prints read at ingest | 26,380,752 | |

Box-score columns (`final_home_score`, `final_away_score`, `home_win`,
`away_win`) are empty (`nan`). They cannot be used as settlement and must
not be filled to “help” a later gate.

### Dated golden measurement (do not promote)

| Quantity | Value | Meaning |
| --- | --- | --- |
| Universe tickers | 2392 | Dated last-trade game-day tickers |
| First Touch 75¢ | 1503 | Entry candidates |
| TE drop | 949 | Entry minus leading exact +1 |
| **N (TE-scoped)** | **554** | Golden population |
| Unique games in N | 504 | Do not treat 554 as 554 independent games |
| WIN_EXIT / path_true | 59 | Hold path; **not** “reached 40” |
| path_false | 495 | Complement of WIN_EXIT; **not** 495 losses |
| LOSS_EXIT | 159 of 218 classified | Reach 40 among classified exits |
| Unclassified | 336 | No WIN/LOSS exit class |
| Terminal YES / NO / MISSING | **65 / 19 / 470** | `65+19+470=554` |
| Joint settled | 84 / 554 = 15.16% | Local `kalshi_markets.result` overlap |
| Conditional YES | 65 / 84 = 77.38% | **Not** MLB TE for 554 |
| Overlay | 0 / 0 | FIRST80 W unused |
| 2025 tickers in dated run | 0 | Game-day filter holds |
| Scalar overlap with 554 | 0 | Warehouse scalars exist; none in this N |

Identities:

```text
59 + 495 = 554
65 + 19 + 470 + 0 INVALID (in the 554) = 554
84 ticker joins to kalshi_markets = 65 YES + 19 NO
```

---

## CURRENT N

```text
N = 554
```

Full-warehouse N (blank dates / full 2025–26 last-trade) is a **different**
population. Do not equate it with this dated N.

---

## CURRENT SETTLEMENT COVERAGE

```text
DATED GOLDEN POPULATION
N = 554

AUTHORITATIVE KALSHI RESULT (local kalshi_markets.result)
├── YES       65
├── NO        19
├── MISSING  470
└── INVALID    0 in the 554-row current overlap

65 + 19 + 470 = 554
```

Preferred source: `kalshi_markets.result`.

Warehouse `kalshi_markets.csv` also contains **4 scalar** rows (not in the
554). Those are **not** binary settlement. Later classification must be:

```text
settlement_status = INVALID
settlement_value  = <raw result, e.g. scalar>
settlement_reason = NON_BINARY_RESULT
```

Do not convert INVALID to missing or zero.

Provenance on the dated job:

- `market_data` = `kalshi_1m_last_trade`
- `market_data_type` = `LAST_TRADE_PRINT`
- `price_basis` = `LAST_TRADE_PRINT`
- `price_rule` = `last_trade_close_cross`
- `terminal_source` = `kalshi_markets.result`

### How settlement is ingested today

- [`build_markets`](../../ROLLER/roller/mlb/ingest.py) copies metadata `result`
- [`ROLLER/roller/research_query/indexes/settlement.py`](../../ROLLER/roller/research_query/indexes/settlement.py): Kalshi result only; missing stays missing
- [`ROLLER/roller/base_terminal_efficiency/settlement.py`](../../ROLLER/roller/base_terminal_efficiency/settlement.py) parses result via `first80.settled_yes` (string parser only; **not** FIRST80 candidate overlay)
- Generic merge: existing `kalshi_markets.result` wins; overlay sports exclude MLB

Local metadata **cannot** resolve the 470. Forbidden substitutes:

- box-score winner
- MLB game result
- FIRST80 overlay / `mlb_first80_80_40_v1`
- path WIN
- inferred complement
- market price at expiration

---

## Date coverage

| Series | Coverage |
| --- | --- |
| Games | 2025-03-18 → 2026-09-04 |
| PBP months | 2025-03…11, 2026-02…09 |
| Last-trade months | 2025-04…11, 2026-03…07 |
| Last-trade 2026-07 | 30 tickers / 4655 bars (thin) |
| Last-trade Aug/Sep 2026 | **ABSENT** |
| Candle months | 2025-04, 2025-10…12, 2026-01…03, 2026-06…07 (sparse except June 2026) |
| `kalshi_markets` game-days | almost entirely **2026-06** (342 of 344 in the dated window) |
| Data-Real metadata with rows | **2026-06-18 → 2026-06-30** only |
| Golden date window | 2026-04-01 → 2026-09-08 |

The dated window is wider than last-trade (ends early July, thin July) and
much wider than settlement metadata (June only). These are **separate**
gaps. Filling settlement must not be used as a reason to switch the
observation series to candles or YES-bid.

---

## Market observation basis

Golden observation:

```text
Kalshi
LAST_TRADE_PRINT
last_trade_close_cross
last_close_e4
```

Last-trade columns include `last_open_e4` / `last_high_e4` / `last_low_e4` /
`last_close_e4`. There are **no `yes_bid_*` fields**.

Therefore:

- LAST_TRADE_PRINT ≠ YES_BID
- LAST_TRADE_PRINT ≠ YES_ASK
- LAST_TRADE_PRINT ≠ FILL

Warehouse `dataset_version.json` `observation_basis` is
`TRADABLE_YES_BID_AVAILABLE+LAST_TRADE_PRINT` (warehouse capability). The
**golden query** uses last-trade only.

Phase 1 must attach settlement to the existing 554 last-trade observations.
It must not “improve” coverage by changing the market-data basis.

---

## PBP coverage

| Metric | Count |
| --- | --- |
| PBP rows | 1,757,845 |
| PBP games | 5108 / 5178 games |
| Dated-window PBP games | 2010 / 2050 dated games |
| Games with both PBP and a `kalshi_markets` row | 168 (warehouse-wide) |

MLB PIT snap: [`ROLLER/roller/mlb/snap.py`](../../ROLLER/roller/mlb/snap.py)

- Last PBP row with `event_timestamp <= entry_ts`
- Equality is visible
- Missing / no visible row → `UNALIGNED` / `PIT_ALIGNMENT_FAILED`
- Does not run basketball clock math

Constitutional I(t) in [`ROLLER/roller/base_terminal_efficiency/pit.py`](../../ROLLER/roller/base_terminal_efficiency/pit.py)
is `available_at < observation_ts` (equality excluded). That is **not** the
MLB game-state snap rule. Do not conflate the two.

---

## TE coverage

Package: [`ROLLER/roller/base_terminal_efficiency/`](../../ROLLER/roller/base_terminal_efficiency/)

Golden TE chips: `score_side=leading`, `exact_diffs=[1]`.

Dated job TE funnel:

| Step | N |
| --- | --- |
| Entry (First Touch 75¢) | 1503 |
| TE-scoped | 554 |
| Dropped | 949 |

Attach path: [`execute.py`](../../ROLLER/roller/research_query/execute.py) →
`attach_to_row` / `row_matches_te_filters`. Missing score fails closed.

65/84 is **conditional terminal YES among settled rows**. It is not TE for
the 554 and is not an edge claim.

---

## Known missingness

| Gap | State |
| --- | --- |
| 470/554 have no `kalshi_markets.result` | **MISSING** (not zero, not NO) |
| Settlement metadata only June 2026 | source coverage hole |
| Last-trade absent Aug/Sep 2026; July thin | observation-series hole (already baked into N=554) |
| No `yes_bid_*` on last-trade bars | quotes/fills **DATA_REQUIRED** for later execution gate |
| Box scores empty | cannot substitute; must stay empty |
| 4 warehouse scalar results | **INVALID** if ever joined; none in current 554 |
| FIRST80 W has 0 MLB tickers | overlay must stay unused |
| Full-warehouse N ≠ dated N | different populations |

Honest gate preview (not Phase 2–7 work):

| Gate | Status |
| --- | --- |
| Data integrity (this recon) | PASS as documentation |
| Settlement completeness | **BLOCKED** (MISSING=470) |
| Terminal efficiency validated | **NOT STARTED** |
| OOS edge | **NOT STARTED** |
| Execution realism | preview **DATA_REQUIRED** (last trade ≠ fill) |
| Production engineering | **NOT STARTED** |
| Complete settlement backtest | **BLOCKED** (MISSING>0) |
| Strategy validated | **BLOCKED** |

---

## Current reproducibility state

Dated job hashes:

| Hash | Value |
| --- | --- |
| `question_hash` | `aaef0cbd185379f060a17077957ad50ee9cd2b4b25c339f1f3c1b25695060449` |
| `universe_hash` | `9484949819ca08afff3deb8adb171cb392812ba23412179de5b81f1023af78be` |
| `entry_hash` | `3d0924fc33f906a1d0084ef0403d8bb4f769d678ebe9f772ec056c6ddec5228e` |
| `state_hash` | `97ed03dbda8960400a5bef68a916d546a2e4d02c0bae83e8b55eaca2aa16e228` |
| `path_hash` | `c9e4efc6be94a1f8770e9d53812953abbbd3a7a92010881386e1a6487787480e` |
| `measurement_hash` | `a368dd6fd3245f934b2c050d3c20f507177e024a4ff69dddffa3f951ae8d516e` |
| `code_version` | `research_query_v1.2_ops` |
| `operation_semantics_version` | `1.0.0` |
| Warehouse `dataset_version` | `cb7cff4fcd52576a3b07aa4cead006032678d01a30e6a36b872085d041714ecc` |

If warehouse last-trade coverage **inside the dated window** changes, the
golden test **must fail**. Do not bump N to make it pass.

---

## Existing tests

Contract / window / settlement / PIT:

- [`ROLLER/tests/test_mlb_golden_fixture.py`](../../ROLLER/tests/test_mlb_golden_fixture.py)
- [`ROLLER/tests/mlb_golden.py`](../../ROLLER/tests/mlb_golden.py)
- [`ROLLER/tests/test_mlb_backtest_invariants.py`](../../ROLLER/tests/test_mlb_backtest_invariants.py)
- [`ROLLER/tests/test_mlb_population_window.py`](../../ROLLER/tests/test_mlb_population_window.py)
- [`ROLLER/tests/test_official_settlement.py`](../../ROLLER/tests/test_official_settlement.py)
- [`ROLLER/tests/test_mlb_snap.py`](../../ROLLER/tests/test_mlb_snap.py)
- [`ROLLER/tests/test_mlb_te_hash.py`](../../ROLLER/tests/test_mlb_te_hash.py)
- [`ROLLER/tests/test_terminal_efficiency_pit.py`](../../ROLLER/tests/test_terminal_efficiency_pit.py)
- [`ROLLER/tests/test_mlb_execute.py`](../../ROLLER/tests/test_mlb_execute.py)

Related MLB suite (warehouse / ingest / isolation; not a strategy-validation
claim):

- `test_mlb_warehouse_compat.py`
- `test_mlb_landing_ingest.py`
- `test_mlb_last_print.py`
- `test_mlb_candle_volume.py`
- `test_mlb_integrity.py`
- `test_mlb_isolation.py`
- `test_mlb_generic_query_is_tennis_import.py`
- `test_mlb_benchmark.py`
- `test_mlb_gate17.py`
- `test_terminal_efficiency_settlement.py`
- `test_orderbook_and_settlement.py`

These tests lock measurement semantics. They do **not** mean the strategy
is validated.

---

## DATA GAPS

1. **Settlement:** 470/554 have no authoritative Kalshi `result`. Local
   metadata is June 2026 only. Complete-settlement gate = **BLOCKED**.
2. **Observation vs settlement are separate.** Last-trade exists for Apr–early
   Jul 2026 (2392 dated tickers). Settlement metadata covers a June slice
   (344 warehouse markets, 84 overlap with N).
3. **Quotes/fills:** last-trade bars have no `yes_bid_*`. Execution realism
   will be **DATA_REQUIRED** / **BLOCKED_BY_EXECUTION_DATA** unless a later
   authorized quote source appears. Do not synthesize fills from last trade.
4. **Last-trade calendar:** no Aug/Sep 2026 files; July 2026 is 30 tickers.
   This already limits which games can enter N. Do not expand the date
   window to chase settlement.
5. **Box scores:** empty. Must remain unused.
6. **Scalar warehouse results:** 4 tickers, none in N. Future ingest must
   mark non-binary results INVALID (`NON_BINARY_RESULT`), not YES/NO/missing.
7. **Cluster structure:** 554 observations / 504 games. Later inference
   must not treat rows as 554 independent games.

---

## FILES TO MODIFY

Phase 0 creates only this report:

- [`research/mlb_validation/PHASE_0_RECON.md`](PHASE_0_RECON.md)

No ROLLER packages, frontend, warehouse CSVs, or golden expected counts
are modified in Phase 0.

Later phases (not authorized here) may add an isolated package
`ROLLER/roller/mlb_validation/` without touching protected files.

---

## FILES PROTECTED

Do not modify:

- [`ROLLER/roller/research/first80.py`](../../ROLLER/roller/research/first80.py) and frozen FIRST80 tests
- Live FIRST01 / 80/81/83/89
- Risk Decision Engine
- Live Kalshi order submission
- Generic Cross / First Touch / Reach / Terminal / PIT / LAST TRADE / YES BID semantics
- Generic research-query result semantics
- Golden expected counts (`N=554`, hashes) unless an explicit versioned research change is approved
- Frontend
- Data-Real / Foundation / production warehouse writes
- W9 / invented L2 / invented fee or mid semantics

Do not treat [`research/mlb_first80_80_40_v1/`](../mlb_first80_80_40_v1/) as
this object’s settlement layer.

---

## NEXT AUTHORIZED PHASE

**Phase 1 — complete settlement coverage**, only after this report is
accepted, and only against the **existing 554** golden observations.

Phase 1 must:

- keep N = 554
- keep LAST_TRADE_PRINT
- use authoritative Kalshi `result` (`kalshi_markets.result` preferred)
- leave missing as missing
- class non-binary results as INVALID / `NON_BINARY_RESULT`

Phase 1 must not:

- rebuild the 554 or rerun entry to change N
- switch to YES-bid or candles
- use FIRST80 W, box scores, path WIN, complement inference, or expiration price
- modify generic research-query semantics, FIRST80, frontend, Risk, or live execution
- implement TE models, edge, execution realism, or production logic

Phase 1 is **not** started by this report.

---

## End-of-phase report

| Item | Value |
| --- | --- |
| PHASE 0 STATUS | **COMPLETE** |
| CURRENT SETTLEMENT COVERAGE | YES 65 / NO 19 / MISSING 470 / INVALID 0 in N |
| CURRENT N | **554** |
| DATA GAPS | June-only Kalshi result; 470 missing; no quotes/fills; thin/absent late-2026 last-trade |
| FILES TO MODIFY | this report only |
| FILES PROTECTED | FIRST80, live FIRST01/80/81/83/89, Risk, generic RQ semantics, golden N, frontend |
| NEXT AUTHORIZED PHASE | **Phase 1 — complete settlement coverage** (not started) |
