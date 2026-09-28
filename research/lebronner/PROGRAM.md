# Lebronner program — conditional selection

How to try to raise Lebronner from the adverse −0.37¢ baseline without
building the strategy on terminal miscalibration. Spec only.

```
LIVE EXECUTION = FALSE
CANDLE PATH ≠ ACTUAL FILL
OBSERVED CALIBRATION DEVIATION ≠ PROVEN MARKET INEFFICIENCY
NO FUTURE LABELS IN F_τ
SPEC_ONLY — IMPLEMENTATION NOT AUTHORIZED
```

Does not change live FIRST01 / 80/81/83/89. Does not retune FIRST75,
FIRST80, or T40. Does not reopen the failed scoreboard as-of test.
Does not fit ITI weights to historical P&L.

Counts and the named −0.37¢: `research/lebronner/REPORT.md`.
Successor name SuperASI (ROLLER +EV / in-production EV stop-path):
`research/superasi/README.md`.

## Objective

Convert an uncertain, marginal unconditional edge into a
**conditional selection problem**.

```
historical universe
  → conditional state filters
  → better entry price
  → higher conditional survival probability
  → positive EV
```

Every additional filter can overfit. The system is designed around
**prospective falsification**, not historical P&L search.

**Status:** `SPEC_ONLY`. Implementation authorized:
False. Live authorized: False.

## Layer 0 — Conservative baseline (the control universe)

Deliberately adverse counterfactual, path conditionals held:

- P(W | FIRST75) = **73%** (not the historical 77.35%)
- S = P(¬T40 | FIRST75) = **62.96%** (exact 0.629647)
- Lebronner payoffs: +20¢ / −35¢, s_L = 0
- **EV = 55S − 35 = -0.37¢**
- Breakeven S = **63.64%**
- Gap to breakeven = **0.68 pp**

### The new distribution at a 73% terminal rate

Holding the conditional path terms fixed (historical s_W and s_L).
**Not a forecast.** This is the mathematically consistent counterfactual.

| | ¬T40 | T40 | Terminal |
|---|---:|---:|---:|
| **W** | **62.8588%** | 10.1412% | **73.0000%** |
| **L** | 0.1059% | 26.8941% | 27.0000% |
| | **62.9647%** | 37.0353% | 100% |

W∩¬T40 = p · s_W = 0.73 × s_W. S = p s_W + (1−p) s_L = **62.9647%**.
That 62.96% is this S(0.73), not a new measurement on the tape.

This is valuable because it is a **conservative control**.
The question is not “the historical sample made money.” The question is:

> Suppose terminal conditions deteriorate. Can information available
> **before entry** improve the conditional path distribution enough
> to overcome this adverse baseline?

Terminal calibration residual is **Layer 5 upside**, not a requirement.

## Layer 1 — Path phenomenon

The unconditional entry-time object remains:

`S = P(¬T40 | FIRST75)`

That is already measured on the locked six-row universe (66.70%
historical; 62.96% in this 73% world). Filters must beat **this**
baseline, not a new in-sample EV.

## Layer 2 — Conditional state selection

Let X_τ be information observable at the potential entry time.
The research object is

`S(X) = P(¬T40 | FIRST75, X_τ)`

not historical P&L. A filter is useful only if it produces a robust

`ΔS(X) = S(X) − S(FIRST75)`

evaluated **out of sample**.

Do not search hundreds of indicators for the highest historical EV.
Each filter needs a hypothesis about **why the future path distribution
changes**.

Candidate observables (hypothesis class, not a fitted model):

- Δ_market (empirical market sensitivity)
- β (response to game-state / underlying changes)
- σ (local price volatility)
- game state, clock, score differential (already failed as an as-of
  four-cell table: `NO_ASOF_LIFT` — do not reopen those bins)
- price trajectory / reversion state
- phenomenon entries (volatility and delta market dynamics)
- ITI (Ian Tali Index)

The failed scoreboard as-of test used quarter, |score|, lead/trail/tie,
home. Adding more of those bins after OOS miss is fishing. This program
is a **different feature class** and requires a new locked protocol
before any implementation.

## Layer 3 — Price optimization (Mechanism A vs B)

Wait for a roughly 3¢ reversion. If it does not revert toward 77, do
not enter. Two mechanisms must be separated.

### Mechanism A — mechanical price improvement

Observe a qualifying state near K = 80¢. Require a pullback and enter
at K_e = **77¢**. With a 40¢ exit: winner **+23¢**,
stop **-37¢**.

Breakeven S = 37 / 60 = **61.67%**.
Lebronner +20/−35 breakeven is 35/55 = **63.64%**.
The better price alone lowers required survival by **1.97 pp**.

That is mechanical. It is not predictive alpha. At the unchanged
62.96% S, this payoff is **+0.78¢**
(still s_L = 0, still not a fill).

### Mechanism B — selection effect of the pullback

Requiring 80→77 trades a different population:

`P(¬T40 | FIRST75, pullback to 77)`

That rate can be higher, lower, or the same. A pullback can be
deteriorating game information. **Do not assume reversion improves S
because it improves the price.** Measure the selection effect
separately from Mechanism A.

## Layer 4 — Execution model

Any claimed EV must later subtract realistic fees, spread, fill
probability, queue loss, partial fills, and adverse selection.
A 1 pp historical improvement is not sufficient once those are in.
Candle path ≠ fill. FIRST80 asked-six stop-path / in-production EV
haircuts are archived under SuperASI, not as a Lebronner filter
and not as a live liquidation rule:
`research/superasi/EV_DECOMPOSITION.md`.
The FIRST75 +20/−35 execution layer is still not a fill model.

## Layer 5 — Terminal upside, not a requirement

If a robust path-selection model exists **and** favorites remain
overpriced (P(W | FIRST_q) > K_q), the four-cell is more favorable
than the 73% baseline. Those are two sources:

1. Path selection improves P(¬T40 | X).
2. Terminal calibration deviation persists.

The combined world can have large estimated EV. It is **not**
“very, very certain.” Correct language:

> high estimated expected value with quantified uncertainty.

Markets and sports distributions can both change. Do not require
Source 2 for the strategy to function.

## Ian Tali Index (ITI)

A constrained state score, not a twenty-parameter P&L fit:

`ITI(X_τ) = w1 R_τ + w2 Δ_τ + w3 β_τ + w4 σ_τ + w5 M_τ`

- R_τ — reversion / dislocation
- Δ_τ — current market sensitivity
- β_τ — relative response to underlying / game-state changes
- σ_τ — local price volatility
- M_τ — momentum / market-dynamic state

Weights are **not** chosen to maximize historical P&L. Initial protocol:

1. economically motivated feature definitions
2. coarse, pre-specified buckets
3. training-only calibration
4. locked thresholds
5. genuinely untouched OOS evaluation

Then the object is `P(¬T40 | FIRST75, ITI ∈ A)`.

ITI is unnamed as a live signal. No weights are stored. No buckets
are locked yet.

## Target: +1 to +3 pp on S, out of sample

From the 62.96% adverse baseline, Lebronner +20/−35 needs **+0.68 pp**
to theoretical breakeven. The 1–3 pp figure is a **ΔS target**, not a
Wilson CI width and not a live Wilson rate.

Lebronner payoffs, s_L = 0, display S = 62.96% + k pp. Not measured.
Before fees, spread, queue, adverse selection, and fill uncertainty.

| ΔS | Conditional S | EV = 55S − 35 |
|---:|---:|---:|
| 0 (control) | 62.96% | **-0.37¢** |
| +1 pp | 63.96% | **+0.18¢** |
| +2 pp | 64.96% | **+0.73¢** |
| +3 pp | 65.96% | **+1.28¢** |

Published conversation rounded +1/+2/+3 to +0.16 / +0.71 / +1.26¢.
Reconstructed 55S − 35 at those display S values is the table above.
A 1 pp in-sample lift is not enough to claim an economic edge.

## Locked research objective

```
max_f  EV_OOS(f)
```

subject to:

- N_OOS ≥ N_min (to be locked before the first run)
- pre-specified interval / test criteria
- effect persists across independent periods
- feature available at entry (in F_τ, no future labels)
- entry rule frozen before OOS
- execution assumptions explicit

and the more fundamental condition:

`P(¬T40 | X)_OOS > P(¬T40)_baseline`

with the improvement evaluated out of sample, not discovered and
validated on the same tape.

## Central idea

Strategy viability should not require terminal miscalibration.

Base EV comes from robust, prospectively validated conditional path
selection. Terminal calibration deviations are additional
uncertainty / upside.

## Central experiment (not started)

Can delta, beta, volatility, reversion, and ITI produce a 1–3 pp OOS improvement in S that survives multiple testing and realistic execution assumptions?

That is the research engine of the 2026–27 program. It has not been
run. Do not start it by fishing features on the existing OOS miss.

## Related objects (not Lebronner filters)

NCAAB P5 2H first-10 FIRST75 post-τ candle vol and score-β:
`research/lebronner/ncaab_h21_beta_vol/REPORT.md`.
Descriptive only. Does not authorize fading H2_1.

NCAAB P5 H2 opening adverse-delta normalization is a **rejected
mechanism** (quiet ≠ reversion):
`research/ncaab_h2_opening_vol_shock/CONCLUSION.md`.
Do not import it as a Lebronner filter. Do not hunt a subset.

Next layer (not a filter): NCAAB P5 residual Δ — Level 2
measurement succeeded, recovery failed. Signed state
transitions failed the residual-variance gate. Stop this
branch. Not a profitable subset:
`research/ncaab_conditional_path_decomp/STATUS.md`.

Neither starts the central experiment.

## What this is not

- Not a live order, fill, or realized P&L.
- Not an implemented filter, ITI, or 77¢ entry rule.
- Not proof that Δ, β, σ, or reversion change S.
- Not a claim that Mechanism B is favorable.
- Not authorization to retune FIRST75 / FIRST80 / T40.
- Not MLB FIRST01. Not W9.

**LIVE DEPLOYMENT: NOT AUTHORIZED**

