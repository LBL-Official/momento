# MOMENTO — Dynamic Risk Engine V3

**Program:** `MOMENTO_DYNAMIC_RISK_ENGINE_V3`
**Schema:** 1.0.0
**Date:** 2026-09-03
**Live execution changed:** FALSE

```
RESEARCH ONLY — CANDLE PATH ≠ ACTUAL FILL — THEORETICAL EXPOSURE ≠ EXECUTED EXPOSURE — MODELED STATE VALUE ≠ TRADABLE EDGE — LIVE DEPLOYMENT: NOT AUTHORIZED
```

DRE V2 showed that a linear mark-to-market objective collapses to corner solutions `h=0` or `h=1`. V3 asks whether a **nonlinear** state-conditional valuation of terminal payoff, recovery optionality, and path risk can produce **stable theoretical interior exposure** without assuming fills.

---

## 1. Scientific motivation

V2 optimized (approximately) `h × Value`. A linear objective on `[0,1]` has corner solutions except in degeneracies. That did **not** prove intermediate exposure is useless. It proved the previous math had no interior mechanism.

## 2. Scope

Offline research. Does not modify PADE V1, DRE V2, FIRST01, Risk, frozen FIRST-80, hedge engines, or fee models. All prior artifacts are read-only.

## 3. Frozen inputs

| Gate | Status |
|------|--------|
| A PADE integrity | **PASS** |
| B DRE V2 integrity | **PASS** |
| C Frozen universe 1230/910/320/0 | **PASS** |
| Market lookahead | **PASS** |
| Game lookahead | **PASS** |
| Label leakage | **PASS** |
| Split isolation | **PASS** |
| Path-bin normalization | **PASS** |

Panel: 139966 rows / 1221 trades. Path-valid to end: 138745. Invalid (typically last possession): 1221.

## 4. Accounting basis

Theoretical retained exposure `h` scales residual directional size of the original YES contract.

```
W(h) = W0 + h × X_terminal
X_terminal = +20¢ if settle YES, −80¢ if settle NO
W0 = 5000¢ ($50 experimental bankroll snapshot)
```

This does **not** assume `(1−h)` can be sold at the current bid. `h=0` is not a liquidation. `h=0.5` is not a hedge.

## 5. Path distribution

Exclusive downside-first bins on the observed candle path (5 / 10 / end). If a path both drops ≥10¢ and later recovers ≥10¢, it is classified as downside. `Σ P(bins) = 1` is gated. Jump-through remains `CANDLE_PATH_PROXY`.

## 6. Predictive information (not a policy)

OOS (selected):

| Model | n | AUC | Brier / logloss |
|-------|--:|----:|----------------:|
| p_terminal | 26948 | 0.861 | 0.157 |
| p_terminal_v3 | 27715 | 0.848 | 0.105 |
| p_rec10_end | 27478 | 0.870 | 0.147 |
| p_rec30_end | 27478 | 0.919 | 0.062 |
| p_det10_end | 27478 | 0.810 | 0.176 |
| path_end | 27478 | — | 1.221 |

Primary `p_terminal` is inherited frozen DRE V2 `p_settle_M3`. `p_terminal_v3` is a V3 as-of logit diagnostic. A good recovery model does **not** imply a good exposure policy.

Hyperparameters are selected on VALIDATION by realized CRRA γ=2 of the implied `h*`. Raw utilities are not compared across γ. Cents are not compared to utils.

## 7. Theoretical exposure policy

Hyperparameters selected on VALIDATION only.

| Family | Selection |
|--------|-----------|
| N1 EU | crra param=2.0 |
| N2 tail | kind=eu q=0.05 λ=0.0 |
| N3 recovery | λ_R=1.0 λ_D=0.0 |
| N4 asymmetric | p=2.0 a=0.01 b=0.05 |

Baselines: E0 `h=1`, E1 `h=0`, E2 frozen DRE V2 `target_delta_M3_A`, E3 VAL-selected constant `h` per 5¢ price bin.

## 8. Interior solutions

| Family | Split | n | mean h | median h | P(h=0) | P(h=1) | Interior |
|--------|-------|--:|-------:|---------:|-------:|-------:|---------:|
| N1 | TRAIN | 55381 | 0.297 | 0.000 | 0.637 | 0.285 | 0.078 |
| N1 | VALIDATION | 53599 | 0.327 | 0.000 | 0.603 | 0.314 | 0.083 |
| N1 | OOS | 26948 | 0.341 | 0.000 | 0.593 | 0.329 | 0.079 |
| N2 | TRAIN | 55381 | 0.297 | 0.000 | 0.637 | 0.285 | 0.078 |
| N2 | VALIDATION | 53599 | 0.327 | 0.000 | 0.603 | 0.314 | 0.083 |
| N2 | OOS | 26948 | 0.341 | 0.000 | 0.593 | 0.329 | 0.079 |
| N3 | TRAIN | 55381 | 0.345 | 0.000 | 0.589 | 0.331 | 0.080 |
| N3 | VALIDATION | 53599 | 0.380 | 0.000 | 0.550 | 0.365 | 0.086 |
| N3 | OOS | 26948 | 0.391 | 0.000 | 0.545 | 0.377 | 0.077 |
| N4 | TRAIN | 55381 | 0.253 | 0.000 | 0.714 | 0.225 | 0.061 |
| N4 | VALIDATION | 53599 | 0.278 | 0.000 | 0.684 | 0.246 | 0.070 |
| N4 | OOS | 26948 | 0.297 | 0.000 | 0.669 | 0.268 | 0.063 |
| N2_LINEAR | TRAIN | 55381 | 0.103 | 0.000 | 0.897 | 0.103 | 0.000 |
| N2_LINEAR | VALIDATION | 53599 | 0.107 | 0.000 | 0.893 | 0.107 | 0.000 |
| N2_LINEAR | OOS | 26948 | 0.138 | 0.000 | 0.862 | 0.138 | 0.000 |
| E2 | TRAIN | 55381 | 0.032 | 0.000 | 0.968 | 0.032 | 0.000 |
| E2 | VALIDATION | 53599 | 0.033 | 0.000 | 0.967 | 0.033 | 0.000 |
| E2 | OOS | 26948 | 0.013 | 0.000 | 0.987 | 0.013 | 0.000 |
| E3 | TRAIN | 57059 | 0.643 | 1.000 | 0.357 | 0.643 | 0.000 |
| E3 | VALIDATION | 55192 | 0.674 | 1.000 | 0.326 | 0.674 | 0.000 |
| E3 | OOS | 27715 | 0.683 | 1.000 | 0.317 | 0.683 | 0.000 |

Stability flags: N1=STABLE N2=STABLE N3=STABLE N4=STABLE

## 8b. N1 risk-aversion sensitivity (not a preference recommendation)

| kind | param | VAL interior | OOS interior | OOS mean h |
|------|------:|-------------:|-------------:|-----------:|
| crra | 0.5 | 0.003 | 0.003 | 0.329 |
| crra | 1.0 | 0.005 | 0.005 | 0.327 |
| crra | 2.0 | 0.083 | 0.079 | 0.341 |
| crra | 3.0 | — | — | — |
| crra | 5.0 | — | — | — |
| crra | 10.0 | — | — | — |
| cara | 0.005 | 0.001 | 0.001 | 0.329 |
| cara | 0.01 | 0.003 | 0.003 | 0.329 |
| cara | 0.02 | 0.005 | 0.005 | 0.327 |
| cara | 0.05 | 0.014 | 0.012 | 0.323 |

High-γ CRRA on a $50 snapshot makes the absolute utility surface extremely flat. Rows with a numerically flat objective are not counted as corner solutions.

## 9. Primary questions

| Q | Answer |
|---|--------|
| Q1 Interior exist? | **PARTIAL** |
| Q2 OOS stable? | **YES** |
| Q3 Same price, different state? | **NO** |
| Q4 Recovery optionality? | **INCONCLUSIVE** |
| Q5 Nonlinear downside? | **PARTIAL** |
| Q6 Smooth evolution? | **YES** |
| Q7 Robust across families? | **PARTIAL** |

OOS 60¢ early vs late: emp settle 0.379 vs 0.804 (n=161/102), but mean theoretical h* N1 0.000 vs 0.000. The +20/−80 entry-proxy gamble is EV-positive only for p>0.80. Predictive state asymmetry therefore need not appear as an exposure-policy asymmetry. PREDICTIVE INFORMATION ≠ THEORETICAL EXPOSURE POLICY.

## 10. Local / temporal stability

Local N1 (OOS sample): median |Δh*|=0.000 p90=0.000 flip 0↔1=0.000

Temporal N1 OOS: median |Δh*|=0.000 p90=0.000 reversals=1292

No smoothing was applied to the primary `h*` path.

## 11. Execution limitations

```
CANDLE PATH ≠ ACTUAL FILL
THEORETICAL EXPOSURE ≠ EXECUTED EXPOSURE
MODELED STATE VALUE ≠ TRADABLE EDGE
```

Utility parameters are **not** Momento's risk preferences. They are a sensitivity grid.

## 12. Verdict

| Item | Result |
|------|--------|
| ARCHITECTURE | **PASS** |
| NONLINEAR OBJECTIVES | **PARTIAL** |
| INTERIOR EXPOSURE | **PARTIAL** |
| OOS STABILITY | **PASS** |
| RECOVERY OPTIONALITY | **INCONCLUSIVE** |
| TAIL-RISK VALUE | **PARTIAL** |
| STATE ASYMMETRY | **FAIL** |
| EXECUTION EVIDENCE | **UNOBSERVED** |
| LIVE DEPLOYMENT | **NOT AUTHORIZED** |

**Headline (nonlinear-exposure hypothesis):** **PARTIAL**

## How to rerun

```
/tmp/momento-nba-venv/bin/python apps/nba-data/scripts/dre_v3.py
```

Dashboard: `frontend/dre-v3` on http://127.0.0.1:5185/

**LIVE DEPLOYMENT: NOT AUTHORIZED**
