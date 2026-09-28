# MLB ROLLER 20-phase desk

**Status:** Sequential MLB warehouse desk (not warehouse Phase 21).  
**NBA plan:** [`PLAN.md`](PLAN.md) Phases 0–20 remain **COMPLETE**. Do not reopen NBA as incomplete.  
**Do not** start Confirm & Run cutover, W9, live FIRST01 / 80/81, or a second Risk/engine.

```text
frontend → ResearchQuestion → compile → canonical MLB warehouse → ResearchContext
  → conditional backtest (reference ≡ optimized) → Results → Labs → SuperASI → ITI → Jump → Vital
```

This waterfall reuses the NBA six-entity contract. MLB gates are written here.

---

## Locked MLB rules

- `LAST_TRADE_PRINT` ≠ `TRADABLE_YES_BID`. Never convert prints into yes-bid.
- Phase 4 projects **both** bases as first-class partitions. Frontend default is **TRADABLE_YES_BID** (NBA-style). Last-trade remains selectable.
- EV / fees only when the basis permits. Last-trade must not invent fill EV.
- MLB clock is **inning / outs / score**. Basketball Q1–Q4 / MM:SS clock → `OPERATION_REQUIRED`.
- Historical L2 / tick stay `DATA_REQUIRED`. Sep live snapshots are not historical L2.
- PBP identity ≠ PIT alignment (`pbp_pit_aligned_to_candles=false`).
- Unsupported ≠ substitute. `ZERO RESULTS` ≠ `DATA_REQUIRED` ≠ `OPERATION_REQUIRED`.
- 554 / 1661 stay Confirm & Run regression fixtures. A new MLB spec must not require a frozen lock.
- Confirm & Run `execute` / `compiler` / `load_dataset` stay CSV / untouched.
- Do not remint `MLB_{YYYYMMDD}_{AWAY}_{HOME}_{game_pk}`.
- Do not invent NCAAB/tennis work. Do not block NBA.
- Jump-AE stays `mlb_factory_v1`. ITI cents do not become 80/81.

---

## Phase gates

| Phase | Gate |
| --- | --- |
| 0 | Recon from today's disk. Dual-basis and clock rules written. |
| 1 | Reuse sport-agnostic entities. No new money types. |
| 2 | Verify-only identity. Copy missing `games.csv` IDs; do not remint `game_pk`. |
| 3 | Persistent GameMarketLink. Separate MLB parquet. No ticker-body guess. |
| 4 | Dual-basis observations. Absent minutes stay absent. No forward-fill. |
| 5 | PBP inning / outs / score. No invented basketball period/clock. |
| 6 | Settlement from `kalshi_markets.result` only. Scalar → INVALID. |
| 7 | Historical L2 `SOURCE_UNAVAILABLE`. Snapshots ≠ fills. |
| 8 | Physical tree under `data/mlb/2025_2026/derived/warehouse/`. |
| 9 | `get_catalog(sport="MLB")` READY / DATA_REQUIRED / OPERATION_REQUIRED per basis. |
| 10 | `get_research_context` loads the parquet slice once. |
| 11 | Arbitrary valid MLB spec compiles without 554/1661. Q4/clock → OPERATION_REQUIRED. |
| 12–14 | Same row contract as NBA. MLB edges: doubleheaders, missing last-trade months, one-sided market, print-gap minutes, basis mismatch. |
| 15 | Measure only after Phase 13 is green. No semantic change. |
| 16 | New path reads Phase 8 parquet only. Confirm & Run stays CSV. |
| 17–18 | Ingest from existing MLB canonical + Suite landing. Legacy 554/1661 still hold. |
| 19 | Unlock MLB in the existing frontend. Default observation: TRADABLE_YES_BID. Last-trade remains selectable. |
| 20 | Brand-new spec compiles, executes, shows W/L, R:R, coverage, row audit. EV only if basis permits. Persist `ROLLER/labs/MLB/{lab_id}/` with `question`. |

Phase 20 acceptance spec (never a frozen object):

```text
MLB 2025–2026 · Kalshi · TRADABLE_YES_BID · CROSS 65¢ · WIN REACH 85¢ · LOSS REACH 40¢
  dates: 2025-04-01 … 2025-04-30
```

Measured 2026-09-14 after Suite candle gap fill (not a frozen lock):

- Compile **READY**, basis `TRADABLE_YES_BID`
- Population **239** · W **103** · L **131** · R:R **0.8**
- EV **READY** (`ev_e4` −508.37, candle-path only — not a fill)
- Reference ≡ optimized (0 diffs)
- Lab `ROLLER/labs/MLB/4e7d4763c56d4c149c3fd6ff88dbc29b/`
- Tick/L2 `DATA_REQUIRED`; Q4/clock on MLB `OPERATION_REQUIRED`

---

## Downstream (after Phase 20)

1. Labs save with persisted `question`. SuperASI A/B consume Labs CSV (no sport filter).
2. ITI uses warehouse `compile_frontend_research` / `execute_frontend_research`. Do not reuse the NBA Q4 stress fixture as the MLB default.
3. Results “Move to SuperASI” calls `POST /superasi/library/import`.
4. Jump Bot Creation + Vital register: no execution change. Committed `{name}_ITI` → `mlb-00N` stub. Factory remains `mlb_factory_v1`.

---

## Out of scope

Warehouse Phase 21. Confirm & Run cutover. W9 / Greeks / fills. Live FIRST01 / 80/81. Second engine or second Risk. Converting last-trade into yes-bid. Inventing MLB game-clock PIT. Mixing demo cents into production. Tennis / NHL desks.
