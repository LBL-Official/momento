# Phase 10 — NBA ResearchContext

Measured: **2026-09-13** against the Phase 8 warehouse. No backtest.

```text
ResearchQuestion
        ↓
Catalog.resolve (Phase 9)
        ↓
Capability decision
        ↓
Canonical warehouse loading (filtered parquet)
        ↓
ResearchContext
```

The bag in `query_context.ResearchContext` remains constructible without the
loader. `get_research_context` now exists and is unused by Confirm & Run
`execute.py` / `compiler.py` / `load_dataset`.

---

## 1. API

```text
get_research_context(question, cfg) → ContextResult
    status: READY | DATA_REQUIRED | OPERATION_REQUIRED
    context: ResearchContext | None
    coverage, missing_data, missing_operations
```

Public objects carry no filesystem paths. Identity is only

```text
market_id → GameMarketLink → internal_game_id
```

Observations stay `TRADABLE_YES_BID`. PIT field is `available_at` (never
substituted). Settlements come from warehouse parquet. INVALID stays INVALID.
PBP is identity-linked and is not time-aligned to candles.

L2 / tick / trade-tape / orderbook → `DATA_REQUIRED`, `context is None`.
PBP↔candle PIT alignment → `OPERATION_REQUIRED`, no join implemented.

A dated question month-prunes observation and PBP files. A full-season
question without dates does not materialize 6.1M observation entities.

---

## 2. Measured NBA example (not FIRST80)

```text
NBA 2025-2026 · Kalshi · TRADABLE_YES_BID · 1-minute · PIT available_at
date 2025-10-10
Q2 CROSS 63¢ · WIN REACH 87¢ · LOSS REACH 41¢ · HOLD_TO_SETTLEMENT
```

| Slice fact | Measured |
| --- | ---: |
| Context status | READY |
| Games on 2025-10-10 | 5 |
| Markets / links | 10 / 10 |
| Observations (day) | 5,125 |
| `NBA_20251010_BOS_TOR` observations | 1,136 |
| PBP events (day) | 3,176 |
| `NBA_20251010_BOS_TOR` PBP | 613 |
| BOS / TOR settlement | YES / NO |
| Observation basis / PIT | `TRADABLE_YES_BID` / `available_at` |
| Warehouse version | 2026-09-13T06:28:48Z |

`NBA_20260108_MIA_CHI` (same day as other games that do have candles): 0
observations, 0 PBP, both markets `INVALID` (source `scalar`). Not rewritten
as NO.

---

## 3. Isolation

No CSV Confirm & Run read. No `official_settlement`. No FIRST80. No ticker
parsing. Context is frozen after construction.

Phase 11 may proceed. Phase 12 is not authorized.
