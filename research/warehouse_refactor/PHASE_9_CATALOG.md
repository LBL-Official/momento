# Phase 9 — NBA warehouse coverage catalog

Measured: **2026-09-13** via `get_catalog(RollerConfig)` against the Phase 8 tree
`ROLLER/data/nba/2025_2026/derived/warehouse/` plus Phase 7
`warehouse_v0/orderbook/capability.json`.

NBA only. Confirm & Run CSV inventory (`catalog()` / `SeasonRef`) is unchanged.
No detectors, EV, identity guessing, or backtest. Public API returns no filesystem
paths. Observation rows were counted from parquet metadata and unique-id scans,
not loaded as Python `MarketObservation` objects.

---

## 1. Objective

Answer “does this warehouse have the facts and capabilities this question needs?”
before any `ResearchContext` load or compile.

```text
ResearchQuestion / CapabilityName*
        ↓
get_catalog → WarehouseCatalog
        ↓
resolve(requirements) → CoverageResolution
        READY | DATA_REQUIRED | OPERATION_REQUIRED
```

`ZERO_RESULTS` is not a catalog status.

---

## 2. Entry points

| API | Module | Role |
| --- | --- | --- |
| `catalog()` | `roller/warehouse/catalog.py` | Existing Confirm & Run CSV path inventory. Unchanged. |
| `get_catalog` | `roller/warehouse/coverage.py` (re-exported from `catalog.py`) | Phase 9 NBA coverage. |
| `WarehouseCatalog.resolve` | coverage | Capability matrix for a requirement list. |
| `WarehouseCatalog.date_coverage` | coverage | Date-range containment from measured metadata. |

---

## 3. Re-measured coverage

| Fact | Measured |
| --- | ---: |
| Games | 1,362 |
| Game date min / max | 2025-10-10 / 2026-06-13 |
| Seasons / leagues | `2025-2026` / `NBA` |
| Markets | 2,724 |
| Tickers | 2,724 |
| Games with markets | 1,362 |
| Market source | `kalshi_rest` |
| GameMarketLink LINKED | 2,724 |
| UNLINKED / AMBIGUOUS / INVALID links | 0 / 0 / 0 |
| Games with linked markets | 1,362 |
| Observations | 6,165,183 |
| Observation basis | `TRADABLE_YES_BID` |
| Resolution | `1_MINUTE_CANDLE` |
| Games with observations | 1,352 |
| Markets with observations | 2,704 |
| `available_at` min / max | 2025-10-10T08:18:00Z / 2026-06-14T03:32:00Z |
| `event_timestamp` min / max | 2025-10-10T08:18:00Z / 2026-06-14T03:32:00Z |
| PIT available / field | true / `available_at` |
| Settlements | 2,724 |
| YES / NO / INVALID / MISSING | 1,359 / 1,359 / 6 / 0 |
| Games with settlement | 1,362 |
| Markets with settlement | 2,724 |
| PBP events | 780,137 |
| Games with PBP | 1,352 |
| Period coverage | 1, 2, 3, 4, 5, 6 |
| Clock / event_timestamp present | true / true |
| PBP PIT-aligned to candles | **false** |
| Orderbook availability | `SOURCE_UNAVAILABLE` |
| Orderbook rows / depth / TOB | 0 / `NONE` / `NONE` |
| Warehouse version (manifest `updated_at`) | 2026-09-13T06:28:48Z |
| Catalog version | 1.0.0 |
| Identity version | 1.0.0 |

INVALID is not counted as NO. Orderbook is copied from the Phase 7 capability
declaration; candles were not used to infer L2.

Ten games have settlement but no 1-minute observations and no PBP (same ten
identities). That is coverage, not `DATA_REQUIRED`.

---

## 4. Capability matrix (this version)

```text
Capability                         Status
------------------------------------------------
NBA Game                           READY
MARKET                             READY
GameMarketLink                     READY
TRADABLE_YES_BID 1-minute          READY
Candle PIT / available_at          READY
Settlement                         READY
PBP                                READY
Historical tick                    DATA_REQUIRED
Historical L2                      DATA_REQUIRED
ORDERBOOK                          DATA_REQUIRED
PBP↔candle PIT alignment           OPERATION_REQUIRED
```

`DATA_REQUIRED` wins over `OPERATION_REQUIRED` when both are requested.

Date-range helper (measured metadata, not `Path.exists`):

- `2025-10-10`–`2025-10-31` → inside warehouse
- `2019-01-01`–`2019-01-31` → outside warehouse

---

## 5. Isolation

- Does not import `execute`, `compile_question`, `official_settlement`, FIRST80.
- Does not read `kalshi_markets.csv` or monthly candle CSV.
- `test_live_execute_paths_do_not_import_entities` forbids `roller.warehouse.coverage`.

---

## 6. Tests

`ROLLER/tests/test_warehouse_catalog.py` plus the existing execute-import guard.

Phase 10 may proceed. Phase 12 is not authorized.
