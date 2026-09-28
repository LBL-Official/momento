# Isolated ATP / WTA ROLLER 20-phase desks

**Status:** Sequential tennis warehouse desks (not warehouse Phase 21).  
**NBA plan:** [`PLAN.md`](PLAN.md) Phases 0–20 remain **COMPLETE**. Do not reopen NBA as incomplete.  
**NCAAB plan:** [`NCAAB_PLAN.md`](NCAAB_PLAN.md) remains the NCAAB desk.  
**MLB plan:** [`MLB_PLAN.md`](MLB_PLAN.md) remains the MLB desk.  
**Recon:** [`PHASE_0_TENNIS_RECON.md`](PHASE_0_TENNIS_RECON.md).  
**Do not** start Confirm & Run cutover, W9, live FIRST01 / 80/81, or a WNBA desk.

```text
frontend → ResearchQuestion → compile → isolated ATP|WTA warehouse → ResearchContext
  → conditional backtest (reference ≡ optimized) → Results → Labs/ATP|Labs/WTA → SuperASI → ITI
```

This waterfall reuses the NBA six-entity contract. ATP and WTA are isolated like NBA vs NCAAB. Mixed ATP+WTA fail closed. Tennis with no tour fail closed.

---

## Locked tennis rules

- Default observation is **TRADABLE_YES_BID**. Last-trade is a selectable second basis. LAST TRADE ≠ YES BID.
- EV / fees only when the basis permits. Candle-path EV is not a fill.
- Identity is the Kalshi event ticker. Do not remint `TENNIS_{YYYYMMDD}_…`.
- Do not write tennis links into NBA `meta/game_market_crosswalk.parquet`.
- Read the shared canonical + Suite tree once, then split by tour.
- Physical trees: `data/atp/2025_2026/derived/warehouse/` and `data/wta/2025_2026/derived/warehouse/`.
- Player sides are p1 / p2. Complementary NO is the other YES ticker.
- Settlement is Kalshi `result` only. Scalar → INVALID. Blank → MISSING.
- MCP PBP is sequence-only. PIT / point-level TE stay `OPERATION_REQUIRED`.
- Tennis periods are S1–S5 / game windows. Q4/H1 or MLB innings → `OPERATION_REQUIRED`.
- 14 Suite candle-file gaps stay absent / `DATA_REQUIRED`.
- Confirm & Run `execute` / `compiler` / `load_dataset` stay CSV.
- Frozen locks stay FIRST80_Q3 n=290, NCAAB_FIRST80_P5 n=721, MLB 554 / 1661.
- Combined ATP+WTA warehouse union is out of scope.

---

## Phase gates

| Phase | Gate |
| --- | --- |
| 0 | Recon from today's disk. Suite complete enough; no second download. |
| 1 | Reuse sport-agnostic entities. No new money types. p1/p2 are sides. |
| 2 | Verify-only identity. Filter shared `games.csv` by league. Copy missing IDs; do not remint. |
| 3 | Isolated crosswalks. Series `KXATPMATCH` / `KXWTAMATCH`, never `KXATPGAME`. |
| 4 | Dual-basis: TRADABLE_YES_BID from Suite ∪ canonical; LAST_TRADE_PRINT from `kalshi_last_trade/`. |
| 5 | PBP via MCP MATCHED / `tennis_match_id` only. No invented point time. |
| 6 | Settlement from Suite `markets.parquet` `result` (canonical CSV same universe). |
| 7 | Historical L2 `SOURCE_UNAVAILABLE`. |
| 8 | Isolated trees under `data/atp|wta/2025_2026/derived/warehouse/`. NBA hash unchanged. |
| 9 | `get_catalog(sport="ATP"|"WTA")` READY / DATA_REQUIRED / OPERATION_REQUIRED. |
| 10 | `get_research_context` loads the parquet slice once. |
| 11 | Arbitrary valid tour spec compiles without FIRST80. |
| 12–14 | Same row contract as NBA. |
| 15 | Measure only after Phase 13 is green. No semantic change. |
| 16 | New path reads Phase 8 parquet only. Confirm & Run stays CSV. |
| 17–18 | Ingest from shared Suite + canonical once. Legacy goldens still hold. |
| 19 | Unlock ATP/WTA in the existing frontend. Mixed / no-tour fail closed. |
| 20 | Two new specs compile, execute, show W/L, R:R, coverage, row audit. Persist `ROLLER/labs/ATP/{lab_id}/` and `ROLLER/labs/WTA/{lab_id}/`. |

Phase 20 acceptance specs (never frozen locks):

```text
ATP  · Kalshi · TRADABLE_YES_BID · CROSS 65¢ · WIN REACH 85¢ · LOSS REACH 40¢
  dates: 2025-07-01 … 2025-07-31
WTA  · Kalshi · TRADABLE_YES_BID · CROSS 65¢ · WIN REACH 85¢ · LOSS REACH 40¢
  dates: 2025-07-01 … 2025-07-31
```

Universe is `("ATP",)` or `("WTA",)` — never `("NBA",)` and never `("ATP","WTA")`.

Measured 2026-09-14 after Suite locate + warehouse ingest + execute (not a frozen lock):

ATP July 2025 CROSS 65 / REACH 85/40:
- Compile **READY**, basis `TRADABLE_YES_BID`, `source=warehouse_research`
- Population **379** · W **150** · L **207** · R:R **0.8**
- EV **READY** (`ev_e4` −573.88, candle-path only — not a fill)
- Reference ≡ optimized (0 diffs)
- Lab `ROLLER/labs/ATP/e75247d5d173471d9757f4532c467c36/`
- Warehouse: 7,775,793 tradable rows / 4,628 games / 2,407,206 last-trade rows

WTA July 2025 CROSS 65 / REACH 85/40:
- Compile **READY**, basis `TRADABLE_YES_BID`, `source=warehouse_research`
- Population **326** · W **143** · L **179** · R:R **0.8**
- EV **READY** (`ev_e4` −495.40, candle-path only — not a fill)
- Reference ≡ optimized (0 diffs)
- Lab `ROLLER/labs/WTA/16eeb0e9452b4536a5911110729815c3/`
- Warehouse: 6,442,250 tradable rows / 4,470 games / 1,701,438 last-trade rows

Shared isolation:
- Tick/L2 `DATA_REQUIRED`; PBP↔candle PIT `OPERATION_REQUIRED`
- NBA crosswalk sha256 unchanged `521fa0af…`
- 14 Suite candle-file gaps stayed absent minutes

---

## Downstream (after Phase 20)

1. Labs save with persisted `question`. SuperASI A/B consume Labs CSV (no sport filter).
2. ITI uses warehouse `compile_frontend_research` / `execute_frontend_research`. Do not reuse NBA Q4 or FIRST80 as the tennis default.
3. Results “Move to SuperASI” calls `POST /superasi/library/import`.

---

## Out of scope

Warehouse Phase 21. Confirm & Run cutover. Rewriting 721 / 290 / 554 / 1661. Inventing MCP timestamps. Polymarket-as-Kalshi. Derivative series (`KXATPGAME`, set-winner, aces). Historical L2. W9. Live FIRST01 / 80/81. WNBA / NHL desks. Combined ATP+WTA warehouse union.
