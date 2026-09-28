# MOMENTO — Dynamic Risk Engine V5

**Program:** `MOMENTO_DYNAMIC_RISK_ENGINE_V5`
**Schema:** 1.0.0
**Date:** 2026-09-03
**Live execution changed:** FALSE

```
RESEARCH ONLY — CANDLE PATH ≠ ACTUAL FILL — FORWARD DISTRIBUTION ≠ TRADABLE EDGE — CONDITIONAL ALPHA ≠ EXECUTABLE ACTION — 100-CONTRACT LEDGER ≠ $50 PRODUCTION SIZE — LIVE DEPLOYMENT: NOT AUTHORIZED
```

## Central question

Does the historical FIRST-80 payoff distribution contain reproducible conditional structure that can be identified using only information observable during the life of the position?

V5 is **not** asking whether we can make more money by exiting, hedging, or trading. V6 (later) asks that.

## Headline

**Verdict B**

| Flag | On |
|------|----|
| A Strong state segmentation | **False** |
| B Price dominates | **True** |
| C Prior-informed remaining adds information | **False** |
| D Nothing replicates OOS | **True** |

TRAIN interestingness is not a discovery. OOS decided the headline under a protocol written before OOS tables.

## Terminology

V5 Conditional Alpha is the **conditional expected payoff** of frozen \(\Pi_{\mathrm{terminal}}=100Y-80\). It is not benchmark-relative financial alpha.

Because that payoff takes only \(\{+20,-80\}\), \(\alpha_{\mathrm{frozen}}(X)=100P(Y=1\mid X)-80\). A cell of +7¢ means historical settle probability \(\approx 0.87\). P10/P50/P90 are empirical; a realized 0 never occurs.

## Frozen inputs

| Gate | Status |
|------|--------|
| A Frozen FIRST-80 | **PASS** |
| B PADE integrity | **PASS** |
| C DRE V4 integrity | **PASS** |
| D Leakage | **PASS** |
| E Split isolation | **PASS** |
| F Prior-only \(\widehat N\) | **PASS** |
| G Path/label normalization | **PASS** |
| H No OOS tuning + protocol first | **PASS** |
| I TRADE_BALANCED labeled | **PASS** |

## Universe

Universe **1230**. Panel-eligible **1221**. Unresolved **9** (preserved). Panel rows **139966**. Q=100 research inventory. \(V^{\mathrm{mtm}}_{\mathrm{cents}}=100\times P_{A1,{\mathrm{cents}}}\). \(\Delta^{\mathrm{inv}}=100\).

## Prior-informed remaining

One `03_possessions` row = one offensive possession. \(R_x=\widehat{\mathrm{pace}}_{A1}+\widehat{\mathrm{pace}}_{A2}\). Chronology: `COMPLETED_BEFORE_G_START_WALL_END_TS`. TRAIN league mean team pace **104.51**. Observed \(R_x\) mean **206.73** (352 was an identity illustration, not used).

## Pre-registered OOS contrasts (trade-balanced \(\alpha_{\mathrm{frozen}}\))

- `L3_clock_early_late_60`: token **FAIL** · TRAIN -4.905 · VAL -0.975 · OOS 2.976 · ratio -0.607
- `L3_score_lead_trail_60`: token **PARTIAL** · TRAIN 11.560 · VAL 6.938 · OOS 3.129 · ratio 0.271
- `L3_nhat_high_low_60`: token **FAIL** · TRAIN 4.869 · VAL 3.680 · OOS -4.427 · ratio -0.909

## M0 vs M1 (Lock 5)

OOS TRADE_BALANCED MAE M0 **20.557** · M1 **20.128** · \(\Delta\) **0.429**. M1 beats M0: **False**.

Occupancy MAE is a STATE_OCCUPANCY_WEIGHTED DIAGNOSTIC, not the economic comparison.

## Path Lambda

Scientific OOS Lambda (TRAIN-frozen α, OOS paths): mean trade-balanced **-0.218**.
Descriptive OOS Lambda is **not** a verdict input: **-0.147**.

## What this is not

Not an action. Not a fill. Not production size. Not live. Not isolated time decay.

**LIVE DEPLOYMENT: NOT AUTHORIZED**

