# Terminal Efficiency Architecture

**Package:** `apps/terminal-efficiency`  
**Writes:** `Backtesting Suite/Data/{NBA,NCAAB}/{season}/warehouse/derived/{nba|ncaab}/terminal_efficiency/`  
**Does not modify:** ROLLER five-screen, FIRST80, live trading, MLB W/A/S.

```text
BASKETBALL DATA
      ↓
POINT-IN-TIME GAME STATES
      ↓
XIB / MCD TRAINING          (2024–25; works WITHOUT candles)
      ↓
FROZEN FUNDAMENTAL PROBABILITY
      ↓
ALIGN TO KALSHI 1-MINUTE CANDLES
      ↓
F_t vs K_t  (research residual; not a trade)
```

XIB, MCD, and market K_t remain three separate objects. No automatic ensemble.

---

## Layout

```text
apps/terminal-efficiency/
  config/{nba,ncaab}.yaml
  terminal_efficiency/
    ingestion/          # wraps warehouse CLIs + ESPN; never synthesizes candles
    normalize/          # games + PBP events
    features/           # FeatureMetadata registry + pregame priors
    state/              # possessions v2.0.0, Dataset B, candle as-of join
    validation/         # leakage_audit, temporal_split
    models/             # XIB hierarchy, MCD simulator, metrics
    pipeline.py / cli.py
  tests/
```

---

## Clocks

| Clock | Authority |
|-------|-----------|
| `prediction_timestamp` | when the model is asked |
| `feature_as_of_timestamp` | latest allowed feature information |
| `game_event_timestamp` | PBP wall time (`OBSERVED` or `MODELED`) |
| `market_timestamp` | Kalshi `end_period_ts` (UTC candle end) |

As-of rule for Dataset C: latest state with `game_event_timestamp <= market_timestamp`.

---

## Datasets

| ID | Unit | Role |
|----|------|------|
| A | game @ scheduled start | pregame |
| B | possession close | **train/val grid** |
| C | aligned 1m candle | apply / coverage only |

---

## Temporal split

```text
TRAIN = 2024–25 game_date <= 2025-02-28
VAL   = 2024–25 game_date > 2025-02-28
TEST  = 2025–26 FROZEN (Phase 7 not authorized)
```

---

## Model hierarchy (walk once)

Model 0 → 1 → 2 → 3. A richer model wins only if VAL Brier improves by ≥ 0.001. Accuracy is secondary.

NBA 2024–25 VAL: **Model 1 frozen** (Model 2 ΔBrier ≈ 0.00076 < 0.001 bar). Model 3 **NOT RUN** (`libomp`). See [CURRENT_STATE.md](CURRENT_STATE.md).

---

## Isolation

No writes to `ROLLER/`. No Research Object producer. `evaluate --season 2025-2026` exits not-authorized.
