# MOMENTO — Dynamic Risk Engine V4

**Program:** `MOMENTO_DYNAMIC_RISK_ENGINE_V4`
**Schema:** 1.0.0
**Date:** 2026-09-03
**Live execution changed:** FALSE

```
RESEARCH ONLY — CANDLE PATH ≠ ACTUAL FILL — FORWARD DISTRIBUTION ≠ TRADABLE EDGE — PREDICTIVE STATE ≠ EXECUTION SIGNAL — LIVE DEPLOYMENT: NOT AUTHORIZED
```

DRE V3 showed that forcing predictive state through a theoretical utility function does not produce a meaningful exposure surface. V4 therefore **does not optimize `h*`**. It estimates **forward conditional distributions**.

```
PREDICTIVE STATE INFORMATION ≠ THEORETICAL EXPOSURE POLICY ≠ EXECUTABLE TRADING POLICY
```

## 1. Motivation

Hypothesis: current price does not completely characterize the forward distribution of candle-path movement and terminal outcomes.

## 2. Scope

Offline research. No sell/stop/hedge/fill/exposure recommendation. Does not modify PADE, DRE V2, DRE V3, FIRST01, Risk, frozen FIRST-80, hedges, or fee models.

## 3. Frozen inputs

| Gate | Status |
|------|--------|
| A Frozen FIRST-80 | **PASS** |
| B PADE integrity | **PASS** |
| C DRE V2 integrity | **PASS** |
| D DRE V3 integrity | **PASS** |
| E/F/G Leakage | **PASS** |
| H Split isolation | **PASS** |
| I Path normalization | **PASS** |
| J No OOS tuning | **PASS** |

## 4. Universe accounting

Universe **1230**. Panel-eligible **1221**. Unresolved **9** (preserved). Panel rows **139966**. Path-label-eligible (end) **138745**.

UNRESOLVED ≠ MODEL-ELIGIBLE. Universe is not redefined to 1221.

## 5. State and three clocks

One row = FIRST-80 trade × HIGH/MEDIUM PADE possession. Wall clock = `market_observation_timestamp` / `position_age_wall_s`. Game clock = `game_clock` / remaining / elapsed. Possession clock = `possession_index`. They are not collapsed.

Clock-horizon labels use **elapsed game seconds** because remaining clock increases in 58/1221 trades.

## 6. Forward labels

Possession horizons 1/3/5/10/end: ΔP, min, max, DD, UE, recover ≥5/10/20, deteriorate ≥5/10/20, exclusive path class, first 10¢ order (UP_FIRST / DOWN_FIRST / NEITHER / AMBIGUOUS / INSUFFICIENT). Missing hits are censored, not zero. Jump-through remains `CANDLE_PATH_PROXY`.

## 7. Matched-price experiment (pre-registered)

Primary: 5¢ bins, band `[60,65)`, early vs late, 5-possession horizon. Minimum 50 rows and 15 trades. Robustness: 2¢, 10¢, NN ±1¢.

OOS primary early vs late: n=203/114 trades=25/38 P(settle) 0.433 vs 0.781 P(rec≥10) 0.064 vs 0.438 P(det≥10) 0.020 vs 0.393 median DD 0.000 vs 0.000 Wasserstein DD 8.800. material=True adequate=True.

RESEARCH DISTRIBUTION — NOT A TRADING INSTRUCTION.

## 8. Nested models

B0 price-only → B1 market quality → B2 game state → M3 multi-clock → M4 path state → M5 dynamics. TRAIN fit. C=1.0 pre-registered. Incremental OOS vs B0 is reported but is **not** the discovery bar.

OOS ΔAUC M3 settle=0.005 rec10_5=0.010 det10_5=0.050 min≤40 k5 (control)=0.005.

## 9. Questions

| Q | Answer |
|---|--------|
| Q1 Same-price different distributions? | **YES** |
| Q2 Survives OOS? | **YES** |
| Q3 Which objects? | **terminal,recovery,deterioration,drawdown_distribution** |
| Q4 Possession beyond clock/score? | **FAIL** |
| Q5 Staleness? | **FAIL** |
| Q6 Robust to bin width? | **YES** |
| Q7 Concentrated in few games? | **NO** |
| Q8 Price dominates some objects? | **YES** |
| Q9 Dist. difference without execution assumption? | **YES** |
| Q10 Justify a trading experiment? | **NO** |

## 10. Limitations

One-minute candles. Repeated candles are observed outcomes, not independent updates. First-hit order is AMBIGUOUS when both thresholds occur on the same possession. Clock horizons use elapsed time. Rows within a trade are clustered; bootstrap is game-level. No L2. No fills.

## 11. Verdict

| Item | Result |
|------|--------|
| ARCHITECTURE | **PASS** |
| FROZEN INPUT INTEGRITY | **PASS** |
| TIME ALIGNMENT | **PARTIAL** |
| LEAKAGE AUDIT | **PASS** |
| PRICE-MATCHED STATE ASYMMETRY | **PARTIAL** |
| FORWARD DISTRIBUTION VALUE | **PARTIAL** |
| POSSESSION INCREMENTAL VALUE | **FAIL** |
| MARKET-AGE VALUE | **FAIL** |
| TRANSITION STRUCTURE | **PARTIAL** |
| EXECUTION EVIDENCE | **UNOBSERVED** |
| LIVE DEPLOYMENT | **NOT AUTHORIZED** |

**Headline:** **PARTIAL**

## How to rerun

```
/tmp/momento-nba-venv/bin/python apps/nba-data/scripts/dre_v4.py
```

Dashboard: `frontend/dre-v4` on http://127.0.0.1:5186/

**LIVE DEPLOYMENT: NOT AUTHORIZED**
