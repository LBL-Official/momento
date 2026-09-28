# DRE V7 — Model Card

**Program:** `MOMENTO_DYNAMIC_RISK_ENGINE_V7`
**Schema:** 1.0.0
**Date:** 2026-09-03
**Descriptive token:** `MIXED_EVIDENCE`

```
RESEARCH ONLY — Δα_state ≠ EDGE — CONDITIONAL INFORMATION ≠ EXECUTION — REPEATED POSSESSIONS ≠ INDEPENDENT OUTCOMES — LIVE DEPLOYMENT: NOT AUTHORIZED
```

> An observed state is not necessarily a well-supported state; a well-populated state is not necessarily independently supported; and an exactly scored state is not necessarily supported by a robust empirical distribution.

## Intended use

Offline structural diagnosis of the frozen V5/V6 state surface.

V7 does not establish tradability.

V7 does not fit a new predictive state model.

V7 diagnoses support and stability properties of the existing frozen V5/V6 state surface.

A state cell with many possession rows may still have low independent terminal-outcome support.

Repeated observations from the same trade do not constitute independent terminal outcomes.

## Support language (verbatim)

UNIQUE_TRADE_SUPPORT ≠ STATISTICAL_INDEPENDENCE. N_EFF_TRADE = OCCUPANCY CONCENTRATION MEASURE ≠ INDEPENDENT SAMPLE SIZE.

Unique trade count is a support unit, not proof of statistical independence.

N_eff,trade measures concentration of row occupancy across trades; it does not estimate the number of statistically independent terminal experiments.

One trade per game on this panel does not make trades i.i.d.

## Residual

r_bar_i = Pi_i - mean_t alpha_M0_it, where mean_t alpha_M0_it = (1/T_i) sum_t alpha_M0_it. One residual per trade. Repeated possessions are not independent terminals.

## Four fields

`EXACT_CELL_EXISTS` · `TRAIN_UNIQUE_TRADE_SUPPORT` · `N_EFF_TRADE` · `SCORING_PATH`

These fields must never be collapsed into one “support” chip.

## Bootstrap

Variation under resampling of observed game-level clusters. Not a population causal CI.

## Gates

A=PASS B=PASS C=PASS D=PASS E=PASS F=PASS G=PASS H=PASS I=PASS J=PASS

## Safety

LIVE DEPLOYMENT: **NOT AUTHORIZED**
