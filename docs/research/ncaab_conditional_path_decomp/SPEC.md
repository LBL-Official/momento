# CONDITIONAL PATH DECOMPOSITION — Level 2 residual Δ

```
RESEARCH ONLY
Δ ≠ EDGE
Γ ≠ EDGE
VOLATILITY ≠ EDGE
RESIDUAL ≠ EDGE
A GREEK-LIKE STATE VARIABLE IS NOT AN AUTHORIZATION TO TRADE
SEARCH FOR STRUCTURAL REPLICATION, NOT A PROFITABLE CELL
LIVE EXECUTION = FALSE
```

Not W9. Not option greeks. Not FIRST75. Not the rejected H2
vol-normalization entry object.

## Frozen status

```
LEVEL 2: MEASUREMENT SUCCESSFUL; RECOVERY HYPOTHESIS FAILED
LEVEL 3: MEASUREMENT STORED; REVERSAL HYPOTHESIS NOT SUPPORTED
LEVELS 4–5: NO MATERIAL STRUCTURE OBSERVED
STATE TRANSITION: EXPLANATORY IMPROVEMENT FAILED
NEXT OBJECTIVE: STOP THIS BRANCH
NOT: PROFITABLE SUBSET DISCOVERY
```

## Hierarchy

1. Raw price move — **REJECTED** as a recovery signal
   (`ncaab_h2_opening_vol_shock`, RESULT NEGATIVE).
2. State-adjusted residual Δ — measurement successful; recovery failed.
3. Gamma / acceleration — stored; reversal not supported.
4. Volatility interaction — no material structure.
5. Time-state / theta — no material structure.
6. Signed M(t-1) → M(t) transitions — measured; residual-variance
   reduction **failed**. Remaining-residual R5 was not evaluated.

## Residual

ε_t = ΔP_t − β(clock, |M|) · ΔM_t

β is fit on **IN_SAMPLE scoring minutes only**, then applied forward.
Cell β (clock × margin band) if n ≥ 40, else clock β, else global β.
Global β is stored only as a baseline, not the primary expected move.

## Causal F_τ

- clock_bin, P_pre, M_pre, ΔM, sign(ΔM)
- V_recent = σ of prior ≤8 signed ΔP (strictly before t)
- V_h1 = H1 σ only after H1 completes (period 2). UNAVAILABLE in H1.
- possession: **UNAVAILABLE** (not invented)

## Frozen residual buckets (cents, not fit to R5)

EXTREME_NEG ε≤−3 · MOD_NEG (−3,−1] · NORMAL (−1,1)
MOD_POS [1,3) · EXTREME_POS ≥3

Do not promote the bucket with the largest R5.

## Replication gate (not a strategy)

A residual bucket is *structurally interesting* only if VAL and OOS
mean R5 have the same sign, |R5| ≥ 1.0¢, and OOS n ≥ 30.
Failing the gate is a result. Do not retune buckets to pass it.

## State-transition model (explanatory)

Ŷ = α(clock, trans) + β(clock, trans)·ΔM
trans ∈ LEAD_SHRINK / LEAD_TO_TRAIL / TRAIL_WIDEN / …

Fit on IN_SAMPLE only. Shrink to trans-only, then to Level-2 Ŷ.
Optional richer cell adds P_pre band if n≥40.

Primary outcome: 1 − Var(ε_ST)/Var(ε_L2) on VAL and OOS.
Material if VAL ≥ 10% and OOS ≥ 5%. Remaining residual R5 is
**not evaluated** unless that gate passes. This is not a rescue of
EXTREME_NEG.
