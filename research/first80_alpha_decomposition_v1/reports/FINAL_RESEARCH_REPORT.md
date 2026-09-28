# FIRST80 alpha decomposition v1 — final research report

**Program:** `FIRST80_ALPHA_DECOMPOSITION_V1`  
**Date:** 2026-09-04  
**Live execution changed:** FALSE

```
RESEARCH ONLY — OBSERVED CALIBRATION DEVIATION ≠ PROVEN MARKET INEFFICIENCY — TERMINAL ALPHA ≠ PATH ALPHA — PATH SURVIVAL ≠ INDEPENDENT EDGE — CONDITIONAL INFORMATION ≠ EXECUTABLE PROFIT — HISTORICAL CANDLE PATH ≠ ACTUAL FILL — HEDGE OPPORTUNITY ≠ LOCKED-IN ALPHA — LIVE EXECUTION = FALSE
```

## Definitions (not changed)

First tradable yes_bid_close >= 80¢ after a prior tradable close < 80¢, two-sided uncrossed spread <= 10¢, inside the game-day window. One observation per event: earliest timestamp; same-minute ties excluded. Source: apps/nba-data/scripts/nba_80_40_execution_audit.py. DO NOT REDEFINE.

Primary T_40 = first subsequent completed candle AFTER the first-80 candle with tradable yes_bid_close <= 40¢ (stop_close_triggered / Y_40_CLOSE). Wick (yes_bid_low) is secondary and is not the primary research object.

## Question 1 — Is P(W|FIRST80) distinguishable from 80%?

Estimate 0.8285. Wilson 95% [0.8064, 0.8485]. Exact one-sided p=0.0062. TRAIN 0.8075 (one-sided p=0.3603 — does not reject 80%). OOS 0.8601 n=243.

Game-cluster bootstrap mean 0.8288 p05 0.8168 p95 0.8424.

This is not a claim that 82.85% is the true fair value. TRAIN does not reject the 80% null; FULL and OOS do. Game-cluster bootstrap p05 still sits above 80% on the pooled sample.

FirstReach(q) calibration deviation is a **broad positive bias** (~2–3pp on FULL at 70–95¢), not a unique 80¢ anomaly.

## Question 2 — Path survival after conditioning on W?

P(¬T40|W,FIRST80)=0.8930 (910/1019) vs FIRST75 0.8536 (n_wins=915; settled first-to-75 n=1176). Shared event+ticker 1084/1230 of FIRST80 units were also first-to-75 on the same ticker.

OOS difference 0.0397 approx 95% [-0.0289, 0.1083].

NON_FIRST80 0.9479 among winners; n_units=247 (n_wins=211). Comeback-selected — higher survival here is not FIRST80 path evidence.

Matched OOS adequate strata = 4 (too thin to carry the claim).

Path token: `NO_OOS_CI_SEPARATION`. Independent path-survival is established only if that token is `OOS_DIFFERENCE_CI_EXCLUDES_ZERO`.

## Question 3 — Mechanical decomposition

P(W ∩ ¬T40) = P(W) × P(¬T40|W) = 0.8285 × 0.8930 = 0.7398.

Algebraic share of the 74% statistic from P(W) above 80% ≈ 0.0343. Most of the joint is 0.80 × P(¬T40|W), not the extra 2.85pp of win rate.

phi=0.7674. OR undefined (zero cell). P(W|¬T40)=1.0000 on this candle sample. LOSS ∧ ¬T40 = 0 (measurement on minute closes, not a continuity proof).

## Question 4 — Sensitivity if P(W)=80%

Holding P(¬T40|W) at 0.8930: joint becomes 0.7144 (delta -0.0254). **Not a forecast.**

## Question 5 — Theoretical hedge states

P(quoted opponent bid_close ≤ 20¢ | FIRST80)=0.9854. Median delay minutes=1.0000. Mean measured complement at that candle ≈ 0.9874. A 20¢ opponent print at FIRST80 is mostly contemporaneous complementarity, not a later lock-in window.

Cheaper opponent prints (≤5¢ / ≤10¢) occur later and almost only on eventual winners. Still quoted states, not fills.

Not an executable hedge. Fees/spread/queue omitted.

## Question 6 — Persistent conditional alpha?

PADE coverage 1221/1230 (dropped 9). OOS trade-balanced mean α̂=-0.0062 (VAL -0.0038).

α̂ = F̂(S) − K(S) with F̂ from TRAIN buckets only. F is not observed. Walk-forward α̂ is slightly **negative** on VAL/OOS and does not support persistent conditional alpha.

## Final classification

**A_TERMINAL_CALIBRATION_ONLY**

RESULT A — TERMINAL CALIBRATION ONLY. The apparent First80 advantage is primarily terminal calibration. No independent path-survival evidence was established.

Locked rule: terminal distinguishable on FULL p<0.05 and OOS point estimate >0.80. Independent path requires an OOS interval on FIRST80−FIRST75 that excludes 0. This run's OOS difference interval includes 0.

```
LIVE DEPLOYMENT RECOMMENDATION:
NOT AUTHORIZED
```
