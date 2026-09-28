# NCAAB ROLLER 20-phase desk

**Status:** Sequential NCAAB warehouse desk (not warehouse Phase 21).  
**NBA plan:** [`PLAN.md`](PLAN.md) Phases 0–20 remain **COMPLETE**. Do not reopen NBA as incomplete.  
**MLB plan:** [`MLB_PLAN.md`](MLB_PLAN.md) remains the MLB desk.  
**Recon:** [`PHASE_0_NCAAB_RECON.md`](PHASE_0_NCAAB_RECON.md).  
**Do not** start Confirm & Run cutover, W9, live FIRST01 / 80/81, or a second Risk/engine.

```text
frontend → ResearchQuestion → compile → canonical NCAAB warehouse → ResearchContext
  → conditional backtest (reference ≡ optimized) → Results → Labs → SuperASI → ITI
```

This waterfall reuses the NBA six-entity contract. NCAAB gates are written here.

---

## Locked NCAAB rules

- Default observation is **TRADABLE_YES_BID**. `LAST_TRADE_PRINT` is NOT_APPLICABLE.
- EV / fees only when the basis permits. Candle-path EV is not a fill.
- NCAAB clock is basketball H1/H2 / P5. Do not invent NBA Q4 as the NCAAB default.
- Historical L2 / tick stay `DATA_REQUIRED`.
- PBP identity ≠ PIT alignment (`pbp_pit_aligned_to_candles=false`).
- Unsupported ≠ substitute. `ZERO RESULTS` ≠ `DATA_REQUIRED` ≠ `OPERATION_REQUIRED`.
- `NCAAB_FIRST80_P5` n=721 stays a Confirm & Run fixture. A new NCAAB spec must not require that lock.
- Confirm & Run `execute` / `compiler` / `load_dataset` stay CSV / untouched.
- Do not remint `NCAAB_{YYYYMMDD}_{AWAY}_{HOME}`.
- Do not write NCAAB links into NBA `meta/game_market_crosswalk.parquet`.
- Do not widen canonicalize `MAPPING_MAPPED`. Warehouse reads Suite independently.
- Basketball+NCAAB must never remap to NBA.

---

## Phase gates

| Phase | Gate |
| --- | --- |
| 0 | Recon from today's disk. Suite complete; no second download. |
| 1 | Reuse sport-agnostic entities. No new money types. |
| 2 | Verify-only identity. Copy missing IDs; do not remint. |
| 3 | Persistent GameMarketLink. Separate NCAAB parquet. Identity tickers including UNMAPPED. Series `KXNCAAMBGAME`. |
| 4 | TRADABLE_YES_BID from Suite `candles_1m` ∪ canonical CSV. Absent minutes stay absent. |
| 5 | PBP via ESPN source id. Candle-only games stay unlinked. No invented period. |
| 6 | Settlement from Suite `markets.parquet` `result` only. Scalar → INVALID. |
| 7 | Historical L2 `SOURCE_UNAVAILABLE`. |
| 8 | Physical tree under `data/ncaab/2025_2026/derived/warehouse/`. NBA crosswalk hash unchanged. |
| 9 | `get_catalog(sport="NCAAB")` READY / DATA_REQUIRED / OPERATION_REQUIRED. |
| 10 | `get_research_context` loads the parquet slice once. |
| 11 | Arbitrary valid NCAAB spec compiles without FIRST80 P5. |
| 12–14 | Same row contract as NBA. |
| 15 | Measure only after Phase 13 is green. No semantic change. |
| 16 | New path reads Phase 8 parquet only. Confirm & Run stays CSV. |
| 17–18 | Ingest from Suite + canonical. Legacy 721 still holds. |
| 19 | Unlock NCAAB in the existing frontend. Default observation: TRADABLE_YES_BID. |
| 20 | Brand-new spec compiles, executes, shows W/L, R:R, coverage, row audit. EV only if basis permits. Persist `ROLLER/labs/NCAAB/{lab_id}/` with `question`. |

Phase 20 acceptance spec (never a frozen object):

```text
NCAAB 2025–2026 · Kalshi · TRADABLE_YES_BID · CROSS 65¢ · WIN REACH 85¢ · LOSS REACH 40¢
  dates: 2025-11-03 … 2025-11-30
```

Measured 2026-09-14 after Suite locate + warehouse ingest (not a frozen lock):

- Compile **READY**, basis `TRADABLE_YES_BID`, `source=warehouse_research`
- Population **926** · W **479** · L **253** · R:R **0.8**
- EV **READY** (`ev_e4` 351.51, candle-path only — not a fill)
- Reference ≡ optimized (0 diffs)
- Lab `ROLLER/labs/NCAAB/d41764fd0fa74ad78d3efc3da82e8648/`
- Tick/L2 `DATA_REQUIRED`; PBP↔candle PIT `OPERATION_REQUIRED`
- Warehouse: 13,429,581 tradable rows / 5,280 games; NBA crosswalk sha256 unchanged `521fa0af…`

---

## Downstream (after Phase 20)

1. Labs save with persisted `question`. SuperASI A/B consume Labs CSV (no sport filter).
2. ITI uses warehouse `compile_frontend_research` / `execute_frontend_research`. Do not reuse the NBA Q4 stress fixture or FIRST80 P5 as the NCAAB default.
3. Results “Move to SuperASI” calls `POST /superasi/library/import`.

---

## Out of scope

Warehouse Phase 21. Confirm & Run cutover. W9 / Greeks / fills. Live FIRST01 / 80/81. Second engine or second Risk. Inventing ESPN ids. Polymarket-as-Kalshi. Tennis / WNBA / NHL desks.
