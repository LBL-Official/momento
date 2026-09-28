# Phase 7 — NBA historical orderbook data-contract boundary

Measured: **2026-09-13T06:25:02Z**.

This phase establishes the **absence** of historical NBA L2 / tick / orderbook data. It does not build an orderbook warehouse.

---

## 1. Data-contract boundary

This ROLLER version contains exactly one historical market-observation basis:

```text
TRADABLE_YES_BID = 1-minute Kalshi candle data.
```

```text
A 1-minute candle is not a tick.
A 1-minute candle is not an orderbook snapshot.
A candle yes_bid is not L2.
Volume is not depth.
A candle path is not an execution tape.
```

PIT **is** available for those 1-minute candles via `available_at`.  
What is unavailable: higher-resolution market data, and PBP-to-candle PIT alignment.

---

## 2. Source inventory

| Path | Measured |
| --- | --- |
| `ROLLER/data/nba/2025_2026/canonical/kalshi_orderbook_snapshots/month=empty.csv` | **0** data rows (header only) |
| `ROLLER/data/nba/2025_2026/raw/kalshi/orderbook/` | **0** files |
| Suite `warehouse/raw/kalshi/NBA/` | `candlesticks`, `cutoff.json`, `events`, `markets`, `trades` — **no `orderbook`** |
| Suite `warehouse/manifests/NBA/dataset_manifest.json` | `orderbook_depth_available: false`; `market_data_type: CANDLESTICK_TOP_OF_BOOK` |

MLB live snapshots exist under `ROLLER/data/mlb/…` and were **not** inspected as NBA sources and were **not** copied.

Phase 4 candles were **not** read.

---

## 3. Capability status

```text
ORDERBOOK SOURCE: UNAVAILABLE
ORDERBOOK ROWS: 0
ORDERBOOK DEPTH: NONE
ORDERBOOK TOP_OF_BOOK: NONE
market_data_basis: ONE_MINUTE_CANDLE
parquet_emitted: false
```

Artifact (declaration of absence, not a dataset):

```text
ROLLER/data/nba/2025_2026/derived/warehouse_v0/orderbook/capability.json
```

1,424 bytes. No `*.parquet` in that directory.

---

## 4. What was not created

- Synthetic orderbook rows
- Empty bid/ask levels
- Zero-row `OrderbookSnapshot` parquet
- Orderbook fields on `MarketObservation`
- Tick-level NBA observations

A fixture-only validator (`reject_hypothetical_l2`) exists solely to prove candle columns (`yes_bid_*`, `volume`) are rejected as L2. It is not connected to NBA warehouse construction.

---

## 5. Tests

`tests/test_warehouse_orderbook.py`: candle rejection, malformed/negative hypothetical L2, no parquet emit, MLB path exclusion, live `SOURCE_UNAVAILABLE`.

---

## 6. Limitations

- NBA only. MLB orderbook is a different sport and a different contract.
- This version will not grow an NBA L2 ingest path from this module.
- Confirm & Run is unchanged.

---

## 7. Status

**PHASE 7: COMPLETE**
