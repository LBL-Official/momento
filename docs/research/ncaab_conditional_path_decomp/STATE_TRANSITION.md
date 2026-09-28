# State-transition explanation — residual variance, not R5

```
EXPLANATORY IMPROVEMENT FAILED
NOT A RESCUE OF EXTREME_NEG
NOT PROFITABLE SUBSET DISCOVERY
LIVE EXECUTION = FALSE
```

Question: can \(E[\Delta P \mid M_{t-1}, M_t, P_{t-1}, \mathrm{clock}]\)
explain residual variation that Level 2 leaves unexplained?

Level 2: Ŷ = β(clock, |M|)·ΔM
State-transition: Ŷ = α(clock, trans) + β(clock, trans)·ΔM
with optional P_pre band if the cell is thick enough.

Material gate (frozen): VAL relative Var reduction ≥ 10% and OOS ≥ 5%.
VAL = -19.0% · OOS = -24.6% · **FAIL**.

Remaining-residual R5 is **not evaluated** — the gate failed.

## Residual variance by split

| Split | n | Var ΔP | Var ε global | Var ε L2 | Var ε ST | R² L2 | R² ST | ST vs L2 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| IN_SAMPLE | 14767 | 22.923 | 18.375 | 15.814 | 15.980 | 0.310 | 0.303 | -0.010 |
| VALIDATION | 64882 | 23.537 | 15.792 | 11.731 | 13.954 | 0.502 | 0.407 | -0.190 |
| OOS | 2848 | 24.161 | 16.082 | 11.696 | 14.575 | 0.516 | 0.397 | -0.246 |

## VAL Level-2 residual by signed transition

If L2 ε concentrates on LEAD_TO_TRAIL / TIE crossings, the
residual is geometry, not an anomalous market response.

| Transition | N | mean ΔM | mean ΔP | mean ε L2 | mean ε ST |
|---|---:|---:|---:|---:|---:|
| LEAD_SHRINK | 12574 | -1.963 | -1.975 | -0.566 | -0.375 |
| LEAD_EXTEND | 15054 | 2.018 | 2.620 | 0.760 | 0.600 |
| LEAD_TO_TIE | 1392 | -2.043 | -4.175 | -1.119 | -1.516 |
| LEAD_TO_TRAIL | 1564 | -2.991 | -6.105 | -1.873 | -2.125 |
| TRAIL_WIDEN | 15131 | -2.019 | -2.613 | -0.759 | -0.517 |
| TRAIL_SHRINK | 12588 | 1.959 | 1.907 | 0.499 | 0.336 |
| TRAIL_TO_TIE | 1392 | 2.044 | 4.097 | 1.038 | 1.048 |
| TRAIL_TO_LEAD | 1564 | 2.991 | 6.033 | 1.797 | 1.943 |
| TIE_TO_LEAD | 1811 | 2.112 | 3.763 | 0.969 | 1.483 |
| TIE_TO_TRAIL | 1812 | -2.111 | -3.789 | -1.003 | -1.652 |

No ST residual R5 table. Explanatory improvement was not
material. Do not inspect path statistics to rescue a cell.

## Reading

The gate is residual-variance reduction, not a mean residual
in one transition cell. VAL and OOS both fail: ST raises
Var(ε) versus Level 2. IN_SAMPLE is already slightly worse,
so this is not only a calendar shift.

LEAD_TO_TRAIL still has a more negative Level-2 mean residual
than LEAD_SHRINK or TRAIL_WIDEN. Same-size ΔM is not the same
state. That diagnostic does not authorize a richer model, a
recovery rule, or inspection of ST residual R5.

Stop this branch. Do not invent Level 6 to rescue the residual.

## What this is not

- Not a new Greek.
- Not Level 6 replication of a recovery rule.
- Not authorization to retune EXTREME_NEG.
- Not live FIRST01.

**LIVE DEPLOYMENT: NOT AUTHORIZED**

