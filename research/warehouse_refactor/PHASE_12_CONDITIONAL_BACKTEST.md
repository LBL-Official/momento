# Phase 12 — NBA conditional backtest

Measured: **2026-09-13**. Observation-path classification only. No fills, EV, or FIRST80.

```text
ResearchPlan
    ↓
Universe → Game → Market (GameMarketLink)
    ↓
Entry  (operations.py / observe_entry)
    ↓
Filters (Interpretation A: game-level then period/clock snap)
    ↓
AND (sequential; B strictly after A)
    ↓
Exit  (path_engine.first_later)
    ↓
Settlement (warehouse parquet only)
    ↓
Classification
```

Module: `ROLLER/roller/warehouse/conditional_backtest.py`.

Confirm & Run still reads CSV. `pbp_pit_aligned_to_candles` remains **false**. No join table was written.

---

## Detectors called (not copied)

| Plan op | Authority |
| --- | --- |
| CROSS | `operations.first_cross` |
| TOUCH / ordinal | `entry_engine.nth_touch` / `crossings` |
| BREAK | `first_break` |
| REVERSION | `first_reversion` |
| BOUNCE | `first_bounce` |
| RECOVERY | `first_recovery` |
| ABOVE / BELOW | `first_above` / `first_below` (`>` / `<`) |
| MAXIMUM_TOUCH / MINIMUM_TOUCH | close-sequence running max/min |
| REACH / DROP / RISE / RECOVER | `path_engine` |
| Period / clock | `default_snap` + `apply_period_clock`; I(t) `available_at < t` |

CROSS equality: current `>=` / `<=` counts; already-at-P is not a new cross (`80→80` is not).

Jump-through (46→37 across 40) is a candle-path REACH/DROP, not a fill.

---

## Period / clock

Interpretation A: identify the game-level event, then filter by snap slice (`Q1`–`Q4` / `OT`).

A Q2 chip is a period filter. `PBP_MARKET_PIT_ALIGNMENT` as a requested capability still returns `OPERATION_REQUIRED` with no scan.

Unaligned / missing snap → exclusion (`period_unaligned` / `period_filter` / `clock_unaligned`), not `DATA_REQUIRED`.

---

## Classifications

`WIN` / `LOSS` = path hit. Settlement attached separately.

No path hit + `HOLD_TO_SETTLEMENT`:

- YES/NO → `HELD_TO_SETTLEMENT` + `settlement_status`
- MISSING → `MISSING_SETTLEMENT`
- INVALID → `INVALID_SETTLEMENT`

`NO_TERMINAL_RESULT` invents no winner. Same later bar WIN and LOSS → `SAME_BAR_TIE`.

`ZERO_RESULTS` = READY plan + READY context + engine ran + population 0.

---

## Measured 2025-10-10 example (not FIRST80)

```text
Q2 CROSS 63¢ · WIN REACH 87¢ · LOSS REACH 41¢ · HOLD_TO_SETTLEMENT
plan_hash 4547787d8dfdb8c40717d7321e399179e868a67f0b069cadabc3f7964f9ffa67
```

| Fact | Measured |
| --- | --- |
| Catalog / Context / Plan | READY / READY / READY |
| Engine | ran |
| Status | `ZERO_RESULTS` |
| Population N | 0 |
| Exclusions | period_filter 5, no_event 3, period_unaligned 2 |
| result_hash | `1b0ce3dc4fb863a2c9b7517669ca1e5936a02d07dab4905d896ab2dc8894a0f6` |
| BOS / TOR settlement (warehouse) | YES / NO (no qualifying entry row) |

Same date, **no period chip** (engine proof that rows classify): population **7** (WIN 1 / LOSS 6). `NBA_20251010_BOS_TOR` BOS path LOSS at `2025-10-10T23:36:00Z`, settlement YES.

Synthetic Q2 + PBP period `2` with `available_at <` candle: population 1, `entry_period=Q2`.

---

## Capability trio

- L2 / tick → `DATA_REQUIRED`, 0 rows
- `PBP_MARKET_PIT_ALIGNMENT` → `OPERATION_REQUIRED`, 0 rows
- READY + no qualifying entries → `ZERO_RESULTS`

Phase 13 may proceed.
