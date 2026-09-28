# Phase 4 — NBA market observations

Measured: **2026-09-13T06:05:32Z**.

Projection of published Kalshi 1m candles through the Phase 3 crosswalk. Confirm & Run CSV was not rewritten.

---

## 1. Objective

```text
NBA Game → Market → MarketObservation (TRADABLE_YES_BID)
```

for every **available** NBA Kalshi 1-minute candle. Absent minutes stay absent.

---

## 2. Source inventory

| Source | Path | Measured |
| --- | --- | ---: |
| Canonical candles | `ROLLER/data/nba/2025_2026/canonical/kalshi_candles/month=*.csv` | **6,165,183** rows; 9 months |
| `kalshi_last_trade/` | NBA tree | **ABSENT** |
| `kalshi_trades/` | present | 39,799,909 prints — **not ingested** |
| Polymarket candles | present | other venue / `LAST_TRADE_PRINT` — **not ingested** |
| `rq_index` `bars.parquet` | derived, 5,777,716 quality-filtered bars | **not** the source |

Source columns include `yes_bid_*`, `yes_ask_*`, `volume`, `available_at`, `event_timestamp`, `candle_timestamp`. **No `last_*_e4` columns.**

---

## 3. Schema

Provisional parquet columns: ticker/`market_id`, `internal_game_id` (from crosswalk only), `source_internal_game_id` (CSV stamp), `game_link_status`, `basis=TRADABLE_YES_BID`, clocks, yes bid/ask OHLC, `volume`, `source`, `duplicate_key`.

Observation identity: `(ticker, available_at, basis)`.

---

## 4. Linkage methodology

```text
ticker → GameMarketLink → internal_game_id
```

If CSV stamp ≠ crosswalk: `CONFLICT` and gid left blank (0 rows).  
Unknown ticker: `UNLINKED`, gid blank.  
No interpolation, forward-fill, or synthetic minutes.  
Last-trade columns fail closed.

---

## 5. Measured row counts

| Metric | Value |
| --- | ---: |
| Observation rows | **6,165,183** |
| LINKED rows | **6,165,183** |
| UNLINKED rows | **0** |
| CONFLICT rows | **0** |
| Tickers with observations | **2,704** |
| Linked markets with zero observations | **20** (the 10 UNMAPPED games) |
| Games with observations | **1,352** |
| Games with zero observations | **10** |
| Missing `yes_bid_close` | **0** |
| Duplicate identity keys | **3 pairs / 6 rows** (exact source copies; kept) |
| Date range | 2025-10-10T08:18:00Z … 2026-06-14T03:32:00Z |

| Month | Rows |
| --- | ---: |
| 2025-10 | 541,322 |
| 2025-11 | 1,131,497 |
| 2025-12 | 923,736 |
| 2026-01 | 1,065,955 |
| 2026-02 | 669,455 |
| 2026-03 | 831,856 |
| 2026-04 | 607,878 |
| 2026-05 | 323,042 |
| 2026-06 | 70,442 |

Output: `ROLLER/data/nba/2025_2026/derived/warehouse_v0/observations/basis=tradable_yes_bid/month=YYYY-MM.parquet` (9 files, 57,098,229 bytes) + `manifest.json`.

---

## 6. Coverage

Season 2025-2026 only. All observation months match the published CSV.  
Games without observations are exactly the 10 identity games without `source_game_id` (same list as Phase 2).

Duplicate keys (kept, not dropped):

| Ticker | `available_at` | Copies |
| --- | --- | ---: |
| `KXNBAGAME-26APR24SASPOR-POR` | 2026-04-22T21:34:00Z | 2 (same `yes_bid_close=4700`) |
| `KXNBAGAME-26APR24SASPOR-SAS` | 2026-04-22T21:34:00Z | 2 (same `yes_bid_close=5200`) |
| `KXNBAGAME-26MAY24OKCSAS-OKC` | 2026-05-18T17:11:00Z | 2 (same `yes_bid_close=5300`) |

---

## 7–9. Duplicates / unresolved / quality

No silent overwrite. No last-trade→bid conversion. No filled minutes.  
3 exact-duplicate source minutes classified via `duplicate_key=1`.

---

## 10. Tests

`tests/test_warehouse_observations.py` (synthetic + live October).

---

## 11. Limitations

- Provisional layout. Not Confirm & Run.
- Does not ingest prints, Polymarket, or orderbook.
- Minute completeness vs wall-clock slots was **not** inferred (absent = absent).
- The 20 LINKED markets without candles are a coverage gap, not a zero series.

---

## 12. Status

**PHASE 4: COMPLETE**
