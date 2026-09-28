# Execution Integrity Engine — reconnaissance

Research only. **LIVE_EXECUTION_CHANGED = FALSE.**

Written before EIE code. Does not change FIRST01, Risk, Execution, A1, or V1–V5.

---

## Frozen sources (do not rescan, do not overwrite)

| Artifact | Path | Role |
|---|---|---|
| FIRST80 NBA | `Backtesting Suite/Data/NBA/2025-2026/warehouse/derived/nba/first80_execution_audit/candidates.json` | L1 universe n=1230 |
| FIRST80 NCAAB warehouse | `.../NCAAB/.../derived/ncaab/first80_execution_audit/candidates.json` | 4099 — **not working universe** |
| V3 opportunity | `.../derived/{nba,ncaab}/first80_opponent_hedge_execution_model_v3/opportunity_dataset.parquet` | L1/L2 A2 path features, H=10..60 |
| V4 ledger | `.../derived/{nba,ncaab}/first80_opponent_hedge_optimal_v4/trade_ledger.parquet` | hold / 80→40 / V1 P&L |
| A1 universe | `docs/research/A1_HYBRID_HEDGE/universe_manifest.json` | `A1_UNIVERSE_V1` hash `d7d2e9e55d9a426a` |
| A1 engine | `apps/ncaab-data/scripts/a1_hybrid_hedge/` | E1 semantics already implemented |

Working NCAAB = P5 vs P5 (721). P5 codes in `a1_hybrid_hedge/universe.py`.

---

## What EIE will **not** do

- Rescan raw 1-minute candles (V3 already applied `t > first_80_timestamp`).
- Dump every warehouse candle into a new L1 table (candles stay immutable in `normalized/*/candles_1m`).
- Overwrite A1 or V1–V5 artifacts.
- Invent L2, queue, maker fills, fees, or L4 live fills.

---

## Evidence mapping onto existing artifacts

| Level | Existing object | EIE use |
|---|---|---|
| L1 | V3 `touch_candle_*`, `jump_10c`, `persist_*`; V4 settlement / stop | Immutable observed snapshot per trade×H |
| L2 | derived from L1 | Opportunity / occupancy enums |
| L3 E1 | A1 conservative causal | Modeled hedge @ observed in-band close, else 80→40 |
| L3 E2 | A1 q / partial | Scenario, not observed |
| L3 E3/E4 | none | `NOT_AVAILABLE` |
| L4 | none in warehouse | Schema only; `NOT_AVAILABLE` |

---

## Splits (frozen)

```text
TRAIN      game_date ≤ 2025-12-31
VALIDATION game_date ≤ 2026-03-15
OOS        after
```

---

## Illegal promotion this engine exists to prevent

```text
THRESHOLD_CROSSING  ↛  FILLED_AT_THRESHOLD
GAP_THROUGH         ↛  EXACT_OBSERVATION
L3 modeled fill     ↛  L4_ACTUAL_EXECUTION
```
