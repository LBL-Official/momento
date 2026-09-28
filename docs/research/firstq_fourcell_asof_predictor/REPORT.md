# As-of four-cell predictor at FIRST_q

Named archive with the four-cell, 73% counterfactual, and EV cases: `research/lebronner/REPORT.md`.

Question: given only information at the threshold timestamp, does the four-cell
distribution differ from the unconditional TRAIN rate in a way that
improves VAL and OOS log-loss?

```
LIVE EXECUTION = FALSE
CANDLE PATH ≠ ACTUAL FILL
NO FUTURE LABELS IN F_TAU
```

Locked features: quarter, score-abs bin, lead state, home.
Locked bins are the 2026-09-04 alpha-decomp matching bins.
Unaligned rows use the TRAIN unconditional. Laplace +1.
W and T40 are labels only.

Decision token: **NO_ASOF_LIFT** (FIRST80), **NO_ASOF_LIFT** (FIRST75).

VAL and OOS log-loss both beat TRAIN unconditional, and OOS paired delta CI excludes 0 on the negative side.

## FIRST80

n=1230 matchable=1158 TRAIN strata=47
Four-cell: {'WIN_SURVIVE': 910, 'WIN_T40': 109, 'LOSE_SURVIVE': 0, 'LOSE_T40': 211}

| Split | n | logloss model | logloss uncond | Δ | Δ 95% | beats? |
|---|---:|---:|---:|---:|---|---|
| TRAIN | 504 | 0.777985 | 0.772536 | +0.0054 | -0.0251–+0.0360 | no |
| VALIDATION | 483 | 0.8467 | 0.715486 | +0.1312 | +0.1024–+0.1600 | no |
| OOS | 243 | 0.835906 | 0.74032 | +0.0956 | +0.0524–+0.1388 | no |
| OOS_matchable | 230 | 0.820132 | 0.719144 | +0.1010 | +0.0554–+0.1465 | no |
| OOS_Q2Q3 | 120 | 0.829382 | 0.729852 | +0.0995 | +0.0331–+0.1660 | no |

Token: **NO_ASOF_LIFT** (established=False)

## FIRST75

n=1176 matchable=1080 TRAIN strata=47
Four-cell: {'WIN_SURVIVE': 781, 'WIN_T40': 134, 'LOSE_SURVIVE': 1, 'LOSE_T40': 260}

| Split | n | logloss model | logloss uncond | Δ | Δ 95% | beats? |
|---|---:|---:|---:|---:|---|---|
| TRAIN | 484 | 0.886616 | 0.895864 | -0.0092 | -0.0388–+0.0203 | yes |
| VALIDATION | 459 | 0.968416 | 0.838554 | +0.1299 | +0.0947–+0.1650 | no |
| OOS | 233 | 0.977531 | 0.845378 | +0.1322 | +0.0863–+0.1780 | no |
| OOS_matchable | 212 | 0.995914 | 0.850671 | +0.1452 | +0.0951–+0.1953 | no |
| OOS_Q2Q3 | 109 | 1.062156 | 0.894664 | +0.1675 | +0.0916–+0.2434 | no |

Token: **NO_ASOF_LIFT** (established=False)

## What this is not

- Not a live order, fill, or 2026–27 deployment.
- Not a claim that any stratum should be traded.
- Not a new FIRST75 / FIRST80 definition.
- Beating TRAIN in-sample is not evidence.

**LIVE DEPLOYMENT: NOT AUTHORIZED**

