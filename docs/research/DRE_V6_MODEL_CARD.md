# DRE V6 — Model Card

**Program:** `MOMENTO_DYNAMIC_RISK_ENGINE_V6`
**Date:** 2026-09-03

## Intended use

Offline attribution of V5's 0.429¢ OOS MAE improvement: where TRAIN-frozen M1 disagrees with TRAIN-frozen M0, and whether that disagreement predicts M0 residuals.

If A/B/C/D none fire, the recorded status is UNCLASSIFIED_PRE_REGISTERED_OUTCOME. That is a halt, not a fifth scientific category.

Not for order routing, stops, hedges, exposure, or live risk.

## Primary estimand

TRADE_BALANCED \(\overline{\Delta\alpha}_i \longrightarrow \bar R_i\).

Row-level residual-on-residual is STATE_OCCUPANCY_WEIGHTED DIAGNOSTIC.

## Concentration

A concentrated distribution of model disagreement is not evidence of predictive information unless the concentrated states also exhibit reproducible OOS separation in terminal payoff or M0 residual.

## Units / inventory

Cents per contract. 5¢ × 100 contracts = 500¢ = $5.00 research-inventory displacement. Not realizable P&L.

## Limitations

Δα_state ≠ EDGE. CONDITIONAL INFORMATION ≠ EXECUTION. CANDLE PATH ≠ FILL. No microstructure. No fees. No fills.

## Safety

LIVE DEPLOYMENT: **NOT AUTHORIZED**
