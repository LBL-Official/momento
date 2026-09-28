# DRE V5 — Model Card

**Program:** `MOMENTO_DYNAMIC_RISK_ENGINE_V5`
**Date:** 2026-09-03

## Intended use

Offline research into whether observable state reproducibly segments the frozen FIRST-80 terminal payoff distribution.

Not for order routing, stops, hedges, exposure, or live risk.

## Data

Frozen FIRST-80 + PADE V1 panel + `03_possessions.parquet`. Chronological game-level TRAIN/VAL/OOS.

## Primary estimand

\(\alpha_{\mathrm{frozen}}(X)=E[100Y-80\mid X]=100P(Y=1\mid X)-80\).

Primary weighting: TRADE_BALANCED. Secondary: STATE_OCCUPANCY_WEIGHTED.

## Units

Cents per contract. \(P_{A1}\in[0,100]\). \(V^{\mathrm{mtm}}_{\mathrm{cents}}=100\times P_{A1,\mathrm{cents}}\).

## Limitations

Candle path ≠ fill. Clustered rows. Binary payoff quantiles are coarse. OT clock is separately flagged. No L2 book. No execution.

## Safety

LIVE DEPLOYMENT: **NOT AUTHORIZED**
