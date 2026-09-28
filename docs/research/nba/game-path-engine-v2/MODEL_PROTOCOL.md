# Model protocol

Complexity does not win by default:

```text
INTERPRETABLE BUCKET  >  SMALL LOGISTIC  >  REGULARIZED NONLINEAR  >  COMPLEX
```

unless a more complex model shows **meaningful, robust, out-of-sample
economic** improvement.

## Models

| ID | Form | Notes |
| --- | --- | --- |
| 0 | Unconditional q̂ = 26.02% | Baseline |
| 1 | Univariate buckets | Primary interpretability |
| 2 | Pre-specified two-way interactions | I1–I6 only |
| 3 | Regularized logistic (L2, L1, elastic net) | CV inside TRAIN |
| 4 | Shallow GBM (depth-1 trees, numpy) | Only if 1–3 fail to capture nonlinearity; depth/leaf constrained |
| 5 | Depth-2 CART discovery | min_leaf=40; freeze then forward-test |

No sklearn. Random seed **42**.

## Splits

See [SPLITS.md](SPLITS.md). Platt calibration, if used, is TRAIN-CV only.

## Metrics (reported)

AUC, PR-AUC, Brier, log loss, ECE, calibration, risk-bucket separation,
EV, acceptance. **Primary promotion criterion is OOS economic usefulness.**

## Risk buckets for q̂

```text
0–10%, 10–15%, 15–20%, 20–25%, 25–30%, 30–33.33%, 33.33–40%, 40%+
```

Merge below n=30. Report n, predicted q, actual q, Wilson CI, survival,
EV, ΔEV vs baseline, acceptance.

## Economics

```text
EV = (1 − q)(+1) + q(−2) = 1 − 3q
breakeven q = 1/3
```

A candidate must beat the **unconditional** EV by a pre-registered margin
of **0.03 R** on VALIDATION (≈1pp of q), not merely stay below 33.33%.

## Production utility (all required for a candidate)

```text
ProductionUtility = f(Edge, Robustness, Calibration, AcceptanceRate,
                      Capacity, Drawdown, RegimeStability)
```

A. `EV_filtered > EV_unconditional + 0.03 R` on VAL, then confirmed OOS  
B. Wilson interval must not make the lift pure noise (OOS CI on q not
   covering a worse EV than baseline as the only plausible value — reported,
   not p-hacked)  
C. Acceptance ≥ **50%** of primary first-80 for production; ≥ **20%** may
   be labeled RESEARCH-ONLY  
D. Direction persists TRAIN, VAL, OOS and early / mid / late TRAIN+VAL
   season slices where n allows  
E. Portfolio: Sharpe/Sortino/drawdown vs unfiltered (research parameters)

## Multiple testing

Family-wise exploratory univariate tests report raw p (two-sided proportion
vs TRAIN complement) and Benjamini–Hochberg FDR at q=0.10. Significance
without effect size, n, CI, and validation is not a promotion.

## Execution stress

Every candidate is shown on close-path (primary) and wick (stress), and
on HIGH maker-fill vs all observations.
