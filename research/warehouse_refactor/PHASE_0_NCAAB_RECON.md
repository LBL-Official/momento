# Phase 0 — NCAAB warehouse desk reconnaissance

Measured: **2026-09-14** from `/Users/user/Desktop/Momento/ROLLER/data/ncaab/2025_2026/canonical/`, `ROLLER/meta/game_identity.csv`, and `Backtesting Suite/Data/NCAAB/2025-2026/warehouse/`.

Architecture stopped. This report is facts, not a warehouse. Confirm & Run was not modified. NBA Phase 0–20 numbers are not reused. Phase 0 recon (`PHASE_0_RECON.md`) saying `kalshi_markets.csv` is MISSING is **stale**.

---

## Locked NCAAB rules (written here)

1. Default observation is **TRADABLE_YES_BID** (NBA-style `yes_bid_*` + `yes_ask_*`). Complementary NO is the other YES ticker. There is no separate `no_bid` stream.
2. `LAST_TRADE_PRINT` is **NOT_APPLICABLE**. Canonical has no `kalshi_last_trade/`. Do not invent a print partition.
3. Never convert prints, scores, or Polymarket into yes-bid or settlement.
4. Settlement is Kalshi `result` only. Blank → `MISSING`. `scalar` → `INVALID`. `MISSING` is not `NO`.
5. Do not remint `NCAAB_{YYYYMMDD}_{AWAY}_{HOME}`. Identity-without-source (no ESPN id) stays valid.
6. Do not write NCAAB links into `meta/game_market_crosswalk.parquet`.
7. Do not widen `MAPPING_MAPPED` inside `canonicalize_candles` / `canonicalize_markets`. Confirm & Run CSV stays the 849-game P5 subset. Warehouse reads Suite independently.
8. PBP identity ≠ PIT (`pbp_pit_aligned_to_candles=false`). Historical L2 / tick = `DATA_REQUIRED`.
9. `NCAAB_FIRST80_P5` n=721 stays a Confirm & Run frozen lock. It is not the warehouse default.
10. Basketball+NCAAB must never remap to NBA.

---

## Census (today’s disk)

### Canonical ROLLER

| Artifact | Measured |
| --- | ---: |
| `games.csv` | **5,280**; every row has `internal_game_id` and `event_ticker` |
| Games with `source_game_id` | **849** |
| Games without `source_game_id` | **4,431** |
| `kalshi_markets.csv` | **1,698** tickers / **849** games; result yes **849** / no **849** |
| Candle rows | **2,674,280**; tickers **1,698**; games **849** |
| `yes_bid` / `yes_ask` present | all 2,674,280 rows |
| volume > 0 | **933,005** |
| Games with zero canonical candles | **4,431** |
| PBP rows | **387,322**; games **847**; months 2025-11…2026-04 |
| `kalshi_last_trade/` | **ABSENT** |
| Phase 8 `derived/warehouse/` | **ABSENT** |

Candle months: 2025-10 (2,733), 2025-11 (282,530), 2025-12 (285,202), 2026-01 (1,051,569), 2026-02 (636,783), 2026-03 (413,345), 2026-04 (2,118).

### Identity

| Fact | Measured |
| --- | ---: |
| `game_identity.csv` NCAAB rows | **5,280** |
| `MAPPED` | **849** |
| `UNMAPPED` | **4,431** |
| `kalshi_market_yes_home` nonempty | **5,274** |
| `kalshi_market_yes_away` nonempty | **5,273** |
| Distinct identity tickers | **10,548** |
| Identity tickers not in canonical candles | **8,850** |
| Canonical candle tickers not in identity | **0** |

`identity_ticker_index` already indexes UNMAPPED rows that carry tickers. `mapping_status` ≠ `link_status`.

### Suite (locate — complete)

Path: `Backtesting Suite/Data/NCAAB/2025-2026/warehouse/`

| Artifact | Measured |
| --- | ---: |
| `candles_1m` parquet files | **10,560** |
| Raw candlestick sidecars | **21,120** |
| `markets.parquet` | **10,560** tickers |
| Suite result | yes **5,269** / no **5,269** / scalar **22** |
| Suite tickers minus identity | **13** |
| Identity tickers minus Suite | **1** |
| Suite tickers minus canonical candles | **8,862** |

Suite candle schema is NBA-identical E4: `yes_bid_*_e4`, `yes_ask_*_e4`, `volume_hundredths`. Series ticker is **`KXNCAAMBGAME`**.

Implementation report (2026-09-02): 13,429,581 candles; 0 games missing markets; 10,560 markets with candles. **No second `ncaab-data download-all` was started.** The hole is canonical `MAPPING_MAPPED` filter, not a missing Kalshi download.

### Isolation

| Artifact | Status |
| --- | --- |
| NBA `meta/game_market_crosswalk.parquet` sha256 | `521fa0af3c674935518a42f8de499b548b94b71f6a20e45f305f2f5aaab982d8` — do not overwrite |
| `game_market_crosswalk_ncaab.parquet` | **ABSENT** (to be written by Phase 3) |
| `NCAAB_FIRST80_P5` | frozen n=**721** — do not rewrite |

---

## Why canonical is a subset

[`canonicalize_candles`](../../ROLLER/roller/canonical/candles.py) and [`canonicalize_markets`](../../ROLLER/roller/canonical/markets.py) keep only `mapping_status == MAPPED` (849 ESPN-linked P5 games). The other 4,431 games already have identity IDs and Suite candles. Warehouse Phase 4 reads Suite ∪ canonical and does **not** rewrite Confirm & Run CSV.

---

## What later phases must not do

- Remint NCAAB identity IDs or invent ESPN `source_game_id` for the 4,431.
- Write NCAAB links into the NBA crosswalk.
- Widen the Confirm & Run canonicalize `MAPPING_MAPPED` filter.
- Infer settlement from PBP score or candle price.
- Treat last-trade as present.
- Start warehouse Phase 21, W9, or live 80/81.
- Remap basketball+NCAAB to NBA.
