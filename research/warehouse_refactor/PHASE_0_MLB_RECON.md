# Phase 0 — MLB warehouse desk reconnaissance

Measured: **2026-09-14** from `/Users/user/Desktop/Momento/ROLLER/data/mlb/2025_2026/canonical/` and `ROLLER/meta/game_identity.csv`.

Architecture stopped. This report is facts, not a warehouse. Confirm & Run was not modified. NBA Phase 0–20 numbers are not reused.

`dataset_version.json` (`generated_at` 2026-09-13T12:41:10Z) already states: last trade ≠ yes bid; candle/print ≠ fill; settlement is Kalshi result, never inferred from PBP; `candles_quality_ready: true`; `candle_volume_present: true`.

---

## Dual-basis and clock rules (locked here)

1. `LAST_TRADE_PRINT` and `TRADABLE_YES_BID` are first-class observation partitions. Prints are never rewritten as yes-bid.
2. Frontend default for MLB is **TRADABLE_YES_BID** (same as NBA). Last-trade remains a selectable second basis. Prints are never rewritten as yes-bid.
3. Candles are READY only when quality/coverage actually permit. On this disk, `candles_quality_ready` is true.
4. EV / fees only when the basis permits. Last-trade path must not invent fill EV.
5. MLB clock is inning / outs / score. Basketball Q1–Q4 and MM:SS game-clock path horizons are `OPERATION_REQUIRED`.
6. PBP identity ≠ PIT alignment.
7. Historical L2 / tick = `DATA_REQUIRED`. Live 2026-09 orderbook snapshots may be catalogued as snapshots with blank `internal_game_id` left `UNLINKED` — not historical L2.

---

## Census (today’s disk)

| Artifact | Measured |
| --- | ---: |
| `games.csv` | **5,208** rows; every row has `internal_game_id` |
| `meta/game_identity.csv` MLB rows | **5,178** |
| Identity gap | **30** `games.csv` rows not in the identity artifact (dates **2026-09-05** and **2026-09-06**). IDs already minted `MLB_{YYYYMMDD}_{AWAY}_{HOME}_{game_pk}` — copy, do not remint. |
| `kalshi_markets.csv` | **8,880**; 8,690 with gid; results yes **4,426** / no **4,434** / scalar **20** |
| Games with exactly 2 markets | 4,345 |
| Games with 1 market | 0 in this census |
| Last-trade bars | **2,540,194**; months 2025-04…11 and 2026-03…07; **missing 2025-12, 2026-01, 2026-02** vs candles |
| Candles | **7,681,992**; 16 months 2025-04…2026-07 |
| PBP | **1,773,247**; includes 2025-03, 2026-08, 2026-09; missing 2025-12, 2026-01 vs candles |
| Orderbook snapshots | `kalshi_orderbook_snapshots/month=2026-09.csv` **54,430** rows; all `internal_game_id` blank |
| Phase 8 warehouse | **ABSENT** (`derived/warehouse/` does not exist) |
| NBA crosswalk | `meta/game_market_crosswalk.parquet` exists — **do not overwrite** |
| `rq_index` last_trade | bar_rows 2,540,194; game_count 3,475; ticker_count 6,990 (legacy planner facts, not `get_research_context`) |
| `rq_index` tradable | bar_rows 7,334,490; game_count 3,641; ticker_count 7,332 |

Confirm & Run last-trade goldens **554** / **1661** remain fixtures. They are not the warehouse desk.

`ROLLER/labs/MLB/` objects: **zero** at recon time.

---

## What later phases must not do

- Remint the 30 September identity rows.
- Write MLB links into `meta/game_market_crosswalk.parquet`.
- Force CSV `full_scan` on the warehouse path.
- Route FIRST80 through this desk.
- Treat last-trade months that are missing vs the candle span as present.
- Infer settlement from final score or PBP.
- Start warehouse Phase 21.

---

## Candle-gap census (2026-09-14, candle-desk pass)

Measured again before download/locate. Do not invent. Authorized Kalshi backfill
(`momento-research-ingest` + `scripts/mlb_kalshi_backfill_watchdog.sh`) was already
running (window `2025-03-18:2026-09-11`). A second ingest was not started
(`ConcurrentWriter`). Landing candle sidecar count was still **7,336** vs
**8,870** trade sidecars after two completed watchdog passes (exit 0) that did
not raise the candle count. The live process was 429-backoff on historical
candlesticks.

### Canonical vs games

| Fact | Measured |
| --- | ---: |
| `games.csv` | **5,208** |
| Games with ≥1 candle | **3,643** |
| Games with zero candles | **1,565** |
| Games with a Kalshi market row | **4,345** |
| Games with market and no candle | **702** |
| Games with no market row (cannot download) | **863** |
| Candle rows | **7,681,992** |
| Candle tickers | **7,332** |
| Market tickers | **8,880** |
| Market tickers missing candles | **1,548** |
| `yes_bid_close` present | **7,681,992** |
| `yes_ask_close` present | **7,681,992** |
| Volume `> 0` | **3,360,134** |
| Volume `= 0` | **4,321,366** |
| Volume blank | **492** |
| Last-trade rows / games | **2,540,194** / **3,474** |

Candle CSV months: 2025-04 … 2026-07 (including 2025-12, 2026-01, 2026-02).
PBP months **not** in candles: **2025-03**, **2026-08**, **2026-09**.
Last-trade months still missing vs candles: **2025-12**, **2026-01**, **2026-02**.

Games with zero candles by `game_date` month:

| Month | Games |
| --- | ---: |
| 2025-03 | 174 |
| 2025-04 | 203 |
| 2025-05 | 1 |
| 2025-07 | 1 |
| 2025-10 | 6 |
| 2025-11 | 1 |
| 2026-02 | 130 |
| 2026-03 | 340 |
| 2026-05 | 3 |
| 2026-06 | 2 |
| 2026-07 | 208 |
| 2026-08 | 412 |
| 2026-09 | 84 |

### Landing sidecars

| Fact | Measured |
| --- | ---: |
| `*.candles.json` tickers | **7,336** |
| `*.trades.json` tickers | **8,870** |
| Trades without candles | **1,544** (2026-07: 418, 2026-08: 834, 2026-09: 292) |
| Candles without trades | **10** |
| Market tickers in neither landing | **0** |
| Discovery envelopes for the 1,544 | `candles_status=NOT_REQUESTED` **1,122**; `UNAVAILABLE` **422** (all `MARKET_METADATA_ONLY`) |

Data-Real `orderbook/` days: **35** (ends 2026-06-30). No Jul–Sep 2026 parquet there.

### Located (not downloaded): Suite `candles_1m`

`Backtesting Suite/Data/MLB/2025-2026/warehouse/normalized/mlb/candles_1m/`

| Fact | Measured |
| --- | ---: |
| Parquet files / tickers | **8,754** |
| Overlap with landing candles | **7,332** |
| Suite tickers not in landing | **1,422** (2026-07: 390, 2026-08: 838, 2026-09: 194) |
| Landing tickers not in Suite | **4** |

Schema is the NBA 1-minute contract: `yes_bid_*_e4`, `yes_ask_*_e4`,
`volume_hundredths`, `market_data_type=CANDLESTICK_TOP_OF_BOOK`,
`source=historical_rest`. There is no separate `no_bid` column. Complementary
NO is the other YES ticker. Months include **2026-08** and **2026-09**.

MLB `roller.mlb.ingest` did **not** read this tree (only landing JSON +
Data-Real `candlestick_close`). NBA canonicalize already does
(`roller/canonical/candles.py` + `roller/ingest/kalshi.py`).

Remaining after locate: games with no Kalshi market (**863**) stay
`DATA_REQUIRED` for candle-only questions. Tickers Kalshi listed
`UNAVAILABLE` stay missing. Do not convert last-trade into yes-bid.

### After Suite `candles_1m` gap fill (measured 2026-09-14T23:30:01Z)

`python -m roller.mlb.ingest --candles-only` added **2,654,875** Suite rows.
Did not remint games. Did not rewrite last-trade or PBP.

| Fact | Measured |
| --- | ---: |
| `genuine_candles` | **10,336,867** |
| `suite_candles_added` | **2,654,875** |
| Candle tickers | **8,754** |
| Games with ≥1 candle | **4,345** |
| Games with market and no candle | **0** |
| Games with no market (still no candle) | **863** |
| `yes_bid_close` / `yes_ask_close` present | **10,336,867** / **10,336,867** |
| Volume `> 0` | **4,521,267** |
| New candle months | **2026-08** (1,507,034), **2026-09** (147,591) |
| 2026-07 after fill | **1,636,482** |
| PBP months still not in candles | **2025-03** only |
| NBA crosswalk sha256 | **521fa0af3c674935518a42f8de499b548b94b71f6a20e45f305f2f5aaab982d8** (unchanged) |

Landing sidecars remain 7,336 vs 8,870. Authorized backfill is still running
(429 backoff). Every game that has a Kalshi market now has 1-minute yes_bid
+ yes_ask from Suite parquet or landing. Remaining games without candles
have no market row — `UNAVAILABLE`, not substituted from last-trade.
