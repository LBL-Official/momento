# Phase 0 — Tennis warehouse desk reconnaissance

Measured: **2026-09-14** from `/Users/user/Desktop/Momento/ROLLER/data/tennis/2025_2026/canonical/`, `ROLLER/meta/game_identity.csv`, and `Backtesting Suite/Data/TENNIS/2025-2026/warehouse/`.

Architecture stopped. This report is facts, not a warehouse. Confirm & Run tennis CSV + `rq_index_v1.0.0` were not modified. NBA / NCAAB / MLB Phase 0–20 numbers are not reused. No second `momento-tennis-data` download was started.

---

## Locked tennis rules (written here)

1. ATP is one desk. WTA is another. Mixed ATP+WTA fail closed. Tennis with no tour fail closed. Do not silently default ATP. Do not remap tennis to NBA.
2. Identity **is** the Kalshi event ticker (`KXATPMATCH-…` / `KXWTAMATCH-…`). Do not remint `TENNIS_{YYYYMMDD}_…` or `ATP_…`.
3. Do not write tennis links into NBA `meta/game_market_crosswalk.parquet` or NCAAB/MLB crosswalks.
4. Read the shared canonical + Suite tree **once**, then split by tour. Do not double-load ATP+WTA.
5. Physical isolation: `data/atp/2025_2026/derived/warehouse/` and `data/wta/2025_2026/derived/warehouse/`. Canonical CSV stays under `data/tennis/`.
6. Player sides are **p1 / p2**, not home/away. Complementary NO is the other YES ticker.
7. Default observation is **TRADABLE_YES_BID**. Last-trade exists and is a selectable second basis. Never convert prints into yes-bid. Never forward-fill empty minutes.
8. Settlement is Kalshi `result` only. Scalar → `INVALID`. Blank → `MISSING`, not `NO`. Never infer from score, MCP, or price.
9. MCP PBP is sequence-only (`pit_joinable=false`). Point-level TE / PIT snap stay `OPERATION_REQUIRED` / `NO_POINT_DATA`. Never invent point timestamps. MCP is CC BY-NC-SA research-only.
10. Tennis periods are S1–S5 / game windows. Basketball Q4/H1 or MLB innings on a tennis question → `OPERATION_REQUIRED`.
11. 14 Suite candle-file gaps stay absent minutes / `DATA_REQUIRED`, not interpolated.
12. Confirm & Run `execute` / `compiler` / `load_dataset` stay CSV. Frozen locks stay 721 / 290 / 554 / 1661.

---

## Census (today’s disk)

### Canonical ROLLER (shared tree)

Path: `ROLLER/data/tennis/2025_2026/canonical/`

| Artifact | Measured |
| --- | ---: |
| `games.csv` | **9,098** (ATP **4,628** / WTA **4,470**) |
| `internal_game_id` = `event_ticker` = `source_game_id` | all 9,098 |
| Date range | **2025-06-18 … 2026-09-12** |
| `kalshi_market_yes_p1` / `p2` nonempty | **687 / 683** (MCP-matched only) |
| `kalshi_market_yes_home` / `away` | **0 / 0** |
| `crosswalk_status` MATCHED / UNMATCHED | **688 / 8,410** |
| `tennis_match_id` nonempty | **688** |
| `kalshi_markets.csv` | **18,196** tickers / 9,098 events |
| Markets by prefix | ATP **9,256** / WTA **8,940** |
| result yes / no / blank | **8,813 / 8,827 / 556** |
| Candle rows | **13,806,248**; tickers **18,182**; games **9,091** |
| Last-trade rows | **4,108,644**; tickers **18,092** |
| PBP rows | **123,804**; matches **689**; tour M **61,444** / W **62,360** |
| `event_timestamp` on PBP | **blank** (SEQUENCE_ONLY) |
| Phase 8 `derived/warehouse/` (tennis / atp / wta) | **ABSENT** |

`sport` and `league` on `games.csv` are already ATP / WTA, not TENNIS.

Candle months (rows): 2025-06 250150, **2025-07 423981**, 2025-08 727619, 2025-09 319870, 2025-10 707153, 2025-11 226842, 2025-12 21850, then 2026-01…09.

July 2025 (first full month after Kalshi start; recommended Phase 20 window):

| Fact | Measured |
| --- | ---: |
| Games | ATP **308** / WTA **256** |
| Canonical candles | **423,981** rows / **1,286** tickers |
| Last-trade | **150,343** rows |

### Identity

| Fact | Measured |
| --- | ---: |
| `game_identity.csv` ATP / WTA rows | **0 / 0** |
| Identity artifact sports | NBA / NCAAB / MLB / WNBA only |

Must copy from `games.csv` without reminting. Only ~688 games carry p1/p2 tickers; markets have all 18,196 tickers with explicit `event_ticker`. Link by `event_ticker`, then fill identity home/away (p1/p2) from those market rows.

### Suite (locate — complete enough)

Path: `Backtesting Suite/Data/TENNIS/2025-2026/warehouse/`

Split trees: `normalized/{atp,wta}/` (not `normalized/tennis/`). Series **`KXATPMATCH` / `KXWTAMATCH`**. `KXATPGAME` is a derivative series, not match-winner.

| Tour | Games | Markets | `candles_1m` files | result yes / no / scalar / blank |
| --- | ---: | ---: | ---: | ---: |
| ATP | 4,628 | 9,256 | 9,244 | 4,471 / 4,479 / 292 / 14 |
| WTA | 4,470 | 8,940 | 8,938 | 4,342 / 4,348 / 248 / 2 |

**14 markets without a candle file** (12 ATP + 2 WTA):

- `KXATPMATCH-25JUN18BERKHA-{BER,KHA}`
- `KXATPMATCH-26JAN03SACKYP-{KYP,SAC}`
- `KXATPMATCH-26JAN04GARMMO-{GAR,MMO}`
- `KXATPMATCH-26JAN04KYRKOV-{KOV,KYR}`
- `KXATPMATCH-26JAN04STRPIR-{PIR,STR}`
- `KXATPMATCH-26JAN04UGOTIE-{TIE,UGO}`
- `KXWTAMATCH-25JUL23LINKAL-{KAL,LIN}`

Same 14-ticker hole as canonical (18,182 vs 18,196). **No second download.** Remaining holes are UNAVAILABLE, not a missing Kalshi client run.

Orderbook: **ABSENT**. Historical L2 stays `SOURCE_UNAVAILABLE`.

### Isolation

| Artifact | Status |
| --- | --- |
| NBA `meta/game_market_crosswalk.parquet` sha256 | `521fa0af3c674935518a42f8de499b548b94b71f6a20e45f305f2f5aaab982d8` — do not overwrite |
| `game_market_crosswalk_atp.parquet` / `_wta.parquet` | **ABSENT** (Phase 3) |
| Frozen locks | FIRST80_Q3 n=**290**, NCAAB_FIRST80_P5 n=**721**, MLB **554 / 1661** — do not rewrite |
| Confirm & Run tennis index | `rq_index_v1.0.0` present — do not rebuild unless `dataset_version` changes |

---

## Why this is a warehouse desk, not a downloader

Suite and canonical already hold the match-winner universe. Production still lists tennis as `UNAVAILABLE_SPORTS`. `DESK_SPORTS` is `{NBA, MLB, NCAAB}`. Phase 8 parquet for ATP/WTA is absent. The missing piece is the isolated warehouse desk (Phases 1–20), not a second Suite fetch.

`load_sport_games` with `warehouse_sport: TENNIS` looks for `normalized/tennis/`, which does not exist. Tennis ingest must read `normalized/{atp,wta}/` directly after one shared warehouse root resolve.

---

## What later phases must not do

- Remint event tickers into `TENNIS_…` / `ATP_…` IDs.
- Write tennis links into the NBA / NCAAB / MLB crosswalks.
- Convert last-trade prints into yes-bid or forward-fill empty minutes.
- Infer settlement from MCP score or candle price.
- Invent MCP point timestamps from match `Time` or sequence index.
- Union ATP+WTA on this desk (that stays Confirm & Run / index-only).
- Treat `KXATPGAME` as match-winner.
- Start warehouse Phase 21, W9, live 80/81, or a WNBA desk.
- Rebuild tennis `rq_index` or change Confirm & Run `execute` / `compiler` / `load_dataset`.
