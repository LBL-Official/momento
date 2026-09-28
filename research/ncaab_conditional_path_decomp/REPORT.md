# Conditional path decomposition — residual Δ (Level 2)

```
RESEARCH ONLY
Δ ≠ EDGE   Γ ≠ EDGE   VOLATILITY ≠ EDGE   RESIDUAL ≠ EDGE
SEARCH FOR STRUCTURAL REPLICATION, NOT A PROFITABLE CELL
LIVE EXECUTION = FALSE
```

State-conditioned residual, not raw vol. Not W9. Not FIRST75.
Parent H2 vol-normalization object remains **REJECTED**.

P5 games 849. MATCHED PBP 847.
In-play bars 181193. Scoring bars 82497.
TRAIN (IN_SAMPLE) scoring used to fit β: **14767**.
Global TRAIN β = 0.932 ¢/pt (r=0.445). Possession UNAVAILABLE.

## TRAIN clock β (¢/pt)

| Clock | n | β | r |
|---|---:|---:|---:|
| H1_1 | 3037 | 0.791 | 0.506 |
| H1_2 | 3879 | 0.895 | 0.527 |
| H2_OPEN | 1705 | 0.885 | 0.503 |
| H2_MID | 3830 | 0.954 | 0.450 |
| H2_LATE | 2316 | 1.297 | 0.365 |

## Level 2 — residual response surface

IN_SAMPLE residuals are in-sample to the β fit. VAL / OOS are
the confirmation windows. Do not pick a cell.

### IN_SAMPLE

| Bucket | N | Games | mean ε | R1 | R5 | R10 | MAE | MFE | P(W)% |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| ε=EXTREME_NEG | 2144 | 147 | -5.972 | 0.203 | 0.445 | 0.663 | 6.446 | 7.431 | 45.4 |
| ε=MOD_NEG | 2470 | 149 | -1.851 | 0.121 | 0.283 | 0.363 | 4.659 | 5.201 | 49.2 |
| ε=NORMAL | 5548 | 149 | -0.005 | -0.031 | -0.067 | -0.211 | 3.235 | 3.014 | 48.7 |
| ε=MOD_POS | 2484 | 149 | 1.878 | -0.174 | -0.167 | 0.050 | 5.159 | 4.907 | 51.9 |
| ε=EXTREME_POS | 2121 | 147 | 5.944 | -0.173 | -0.246 | -0.494 | 7.189 | 6.551 | 54.9 |

### VALIDATION

| Bucket | N | Games | mean ε | R1 | R5 | R10 | MAE | MFE | P(W)% |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| ε=EXTREME_NEG | 7516 | 618 | -5.770 | 0.215 | 0.390 | 0.324 | 7.220 | 7.904 | 46.0 |
| ε=MOD_NEG | 10968 | 663 | -1.842 | 0.178 | 0.257 | 0.307 | 4.621 | 5.073 | 49.4 |
| ε=NORMAL | 27943 | 664 | 0.000 | -0.013 | 0.031 | 0.038 | 2.875 | 2.901 | 49.5 |
| ε=MOD_POS | 11036 | 664 | 1.827 | -0.161 | -0.183 | -0.208 | 5.080 | 4.686 | 51.4 |
| ε=EXTREME_POS | 7419 | 617 | 5.689 | -0.100 | -0.289 | -0.301 | 7.874 | 7.260 | 54.3 |

### OOS

| Bucket | N | Games | mean ε | R1 | R5 | R10 | MAE | MFE | P(W)% |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| ε=EXTREME_NEG | 291 | 27 | -5.688 | 0.265 | -0.500 | -0.710 | 7.701 | 6.935 | 46.7 |
| ε=MOD_NEG | 526 | 29 | -1.845 | -0.084 | -0.445 | -0.411 | 5.274 | 4.760 | 46.6 |
| ε=NORMAL | 1240 | 29 | 0.009 | 0.004 | -0.081 | 0.015 | 2.866 | 2.712 | 49.8 |
| ε=MOD_POS | 483 | 29 | 1.870 | 0.145 | 0.639 | 0.398 | 4.886 | 5.563 | 54.5 |
| ε=EXTREME_POS | 308 | 26 | 5.510 | -0.256 | 0.578 | 0.651 | 6.756 | 7.575 | 52.9 |

## Clock (Level 5 descriptive)

VALIDATION only — time-state, not a selected hour.

| Bucket | N | Games | mean ε | R1 | R5 | R10 | MAE | MFE | P(W)% |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| clock=H1_1 | 13320 | 664 | -0.014 | 0.006 | 0.034 | 0.009 | 4.424 | 4.425 | 50.0 |
| clock=H1_2 | 16178 | 664 | -0.016 | 0.002 | 0.032 | 0.052 | 3.881 | 3.918 | 49.9 |
| clock=H2_OPEN | 7419 | 663 | -0.021 | 0.002 | 0.037 | 0.018 | 4.942 | 4.966 | 49.6 |
| clock=H2_MID | 16762 | 663 | -0.030 | 0.019 | 0.037 | 0.021 | 5.165 | 5.196 | 49.9 |
| clock=H2_LATE | 11203 | 660 | -0.008 | 0.022 | 0.055 | 0.101 | 4.894 | 4.949 | 50.3 |

## Level 3 — price acceleration Γ = ΔP_t − ΔP_{t−1} (VAL)

| Bucket | N | Games | mean ε | R1 | R5 | R10 | MAE | MFE | P(W)% |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Γ=HIGH_NEG_G | 14626 | 645 | -2.696 | -0.230 | -0.207 | -0.228 | 6.869 | 6.347 | 48.1 |
| Γ=OTHER_G | 50256 | 664 | 0.761 | 0.081 | 0.111 | 0.117 | 3.966 | 4.156 | 50.5 |

## Level 4 — H1-vol tertiles (TRAIN cuts, VAL rows)

| Bucket | N | Games | mean ε | R1 | R5 | R10 | MAE | MFE | P(W)% |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| V_H1=LOW | 14264 | 302 | -0.002 | 0.004 | 0.044 | 0.080 | 2.836 | 2.913 | 50.2 |
| V_H1=MID | 12767 | 259 | -0.042 | 0.019 | 0.052 | 0.042 | 6.334 | 6.362 | 50.1 |
| V_H1=HIGH | 8353 | 161 | -0.021 | 0.034 | 0.026 | -0.032 | 6.792 | 6.774 | 49.4 |

EXTREME_NEG residual × H1-vol tertile (VAL):

| Bucket | N | Games | mean ε | R1 | R5 | R10 | MAE | MFE | P(W)% |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| εEXT×V_H1=LOW | 875 | 153 | -6.088 | 0.119 | 0.597 | 0.666 | 7.768 | 8.553 | 51.9 |
| εEXT×V_H1=MID | 2045 | 232 | -6.573 | 0.221 | 0.551 | 0.822 | 8.951 | 10.228 | 44.5 |
| εEXT×V_H1=HIGH | 1484 | 150 | -6.654 | 0.235 | 0.447 | -0.204 | 9.279 | 9.714 | 42.5 |

VAL vol expanding n=26158 R5=0.049 mean ε=0.000.
VAL vol contracting n=37895 R5=0.031 mean ε=-0.029.

## Theta-like (ΔM = 0) — VAL mean ΔP by clock

| Clock | N | mean ΔP |
|---|---:|---:|
| H1_1 | 15389 | 0.006 |
| H1_2 | 18841 | 0.010 |
| H2_OPEN | 9589 | 0.008 |
| H2_MID | 20329 | 0.021 |
| H2_LATE | 13266 | 0.008 |

## Replication gate (frozen; not a strategy)

Same sign of mean R5 on VAL and OOS, |R5| ≥ 1.0¢, OOS n ≥ 30.

| ε bucket | VAL R5 | VAL n | OOS R5 | OOS n | gate |
|---|---:|---:|---:|---:|---|
| EXTREME_NEG | 0.390 | 7516 | -0.500 | 291 | FAIL |
| MOD_NEG | 0.257 | 10968 | -0.445 | 526 | FAIL |
| NORMAL | 0.031 | 27943 | -0.081 | 1240 | FAIL |
| MOD_POS | -0.183 | 11036 | 0.639 | 483 | FAIL |
| EXTREME_POS | -0.289 | 7419 | 0.578 | 308 | FAIL |

FAIL on every bucket means Level 2 has not produced a
replicated residual-recovery phenomenon. That is a result.
Do not retune the cents cuts to manufacture a PASS.

## Reading (descriptive)

Excess movement **exists**: TRAIN clock β rises from 0.79 ¢/pt
in H1_1 to 1.30 in H2_LATE, and EXTREME residual buckets have
|mean ε| ≈ 5.7–6.0¢. A global 0.93 ¢/pt does not absorb the
state. That answers “does excess exist?” with yes, as variation.

It does **not** answer “does excess reverse?” with a replicated
yes. VAL EXTREME_NEG R5 is +0.39¢ after a −5.8¢ residual
(same economic class as the rejected +0.14¢ raw-shock bounce).
EXTREME_POS is the mirror (−0.29¢). OOS flips both signs.
Median R is 0 wherever we stored it. Γ HIGH_NEG continues down
(VAL R5 −0.21¢): acceleration looks like information, not
overshoot. H1-vol tertiles do not move mean ε or R5.

Do not promote εEXT × V_H1. VAL R5 is +0.45 to +0.60 across
all three tertiles; that is still sub-cent, and OOS cells are
thin. Expanding vs contracting vol is a wash.

Theta (ΔM=0) mean ΔP is ~0 at every clock bin. Time alone is
not a drift we can see at one-minute resolution on this tape.

Level 2 status: **excess exists; replicated recovery does not.**
The parent vol-norm object stays rejected. No cell is authorized.

Signed M(t-1) → M(t) transitions were measured next.
They do not reduce residual variance versus Level 2.
See `STATUS.md` and `STATE_TRANSITION.md`. Stop this branch.

## What this is not

- Not an entry, fade, or normalization-buy rule.
- Not a promotion of the best residual cell.
- Not W9 / option greeks / L2 / fills.
- Not a reopening of the rejected H2 vol-norm object.
- Not MLB FIRST01.

**LIVE DEPLOYMENT: NOT AUTHORIZED**

