# MOMENTO — Dynamic Risk Engine V6

**Program:** `MOMENTO_DYNAMIC_RISK_ENGINE_V6`
**Schema:** 1.0.0
**Date:** 2026-09-03
**Live execution changed:** FALSE

```
RESEARCH ONLY — CANDLE PATH ≠ ACTUAL FILL — FORWARD DISTRIBUTION ≠ TRADABLE EDGE — CONDITIONAL ALPHA ≠ EXECUTABLE ACTION — Δα_state ≠ EDGE — 100-CONTRACT LEDGER ≠ $50 PRODUCTION SIZE — LIVE DEPLOYMENT: NOT AUTHORIZED
```

```
Δα_state ≠ EDGE
CONDITIONAL INFORMATION ≠ EXECUTION
CANDLE PATH ≠ FILL
LIVE DEPLOYMENT = NOT AUTHORIZED
```

## Central question

When the frozen state-vector model disagrees with the frozen price-only model, does the terminal outcome subsequently deviate from the price-only expectation in the predicted direction?

V5 Verdict B is historical. V6 does not reopen the 0.5¢ MAE test.

## Headline

**UNCLASSIFIED_PRE_REGISTERED_OUTCOME — HARD HALT — A/B/C/D none fired. Not a fifth scientific category.**

This is a **HARD HALT**, not a fifth scientific letter. The frozen A/B/C/D conjunctions were applied once. None fired. Thresholds were not moved.

| Flag | On |
|------|----|
| A No meaningful state information | **False** |
| B Statistical state information | **False** |
| C Concentrated state information | **False** |
| D Potential economic signal | **False** |

Even V6-D is not expected trading profit. `POTENTIAL ECONOMIC SIGNAL ≠ TRADABLE STRATEGY`.

## Gates

| Gate | Status |
|------|--------|
| A V5 locks | **PASS** |
| B Predecessors | **PASS** |
| C Map identity | **PASS** |
| D Maps persisted first | **PASS** |
| E Splits | **PASS** |
| F Protocol first | **PASS** |
| G V5 untouched | **PASS** |
| H No path/40 in headline | **PASS** |
| I Weighting labeled | **PASS** |

## Map recovery identity

OOS MAE M0 **20.557** · M1 **20.128** · Δ **0.429**. Cells M0 **20** · M1 **584**.

## TRADE_BALANCED distribution of mean_SIR

| split | weighting | mean | P50 | max |P| | P≥1¢ | P≥2¢ | P≥5¢ | P≥10¢ |
|-------|-----------|------|-----|--------|------|------|------|-------|
| TRAIN | TRADE_BALANCED | 1.204 | 0.839 | 91.358 | 0.722 | 0.473 | 0.131 | 0.014 |
| VALIDATION | TRADE_BALANCED | 0.707 | 0.747 | 11.296 | 0.705 | 0.399 | 0.046 | 0.004 |
| OOS | TRADE_BALANCED | 0.582 | 0.543 | 11.210 | 0.700 | 0.392 | 0.063 | 0.004 |

OOS P(|mean_SIR|≥5¢) **0.063**.

## Concentration (geometry, not evidence) — TRADE_BALANCED

| split | weighting | top 1% | top 5% | top 10% | top 25% | top10 ≥ 40% |
|-------|-----------|--------|--------|---------|---------|-------------|
| TRAIN | TRADE_BALANCED | 0.179 | 0.289 | 0.392 | 0.621 | False |
| VALIDATION | TRADE_BALANCED | 0.051 | 0.178 | 0.291 | 0.534 | False |
| OOS | TRADE_BALANCED | 0.058 | 0.198 | 0.311 | 0.556 | False |

A concentrated distribution of model disagreement is not evidence of predictive information unless the concentrated states also exhibit reproducible OOS separation in terminal payoff or M0 residual.

## Rank (TRADE_BALANCED)

| split | weighting | n | spread 10−1 E[Π] | n_lo | n_hi | adequate | Spearman(SIR, Π) |
|-------|-----------|---|------------------|------|------|----------|------------------|
| TRAIN | TRADE_BALANCED | 503 | 80.392 | 51 | 51 | True | 0.470 |
| VALIDATION | TRADE_BALANCED | 481 | 22.689 | 34 | 28 | True | 0.136 |
| OOS | TRADE_BALANCED | 237 | -10.000 | 20 | 12 | False | 0.039 |

OOS top−bottom decile E[Π] **-10.000**. Replication token **INCONCLUSIVE**.

Candle path does not enter this table, V6-D, or rank replication.

## Residual-on-residual (primary TRADE_BALANCED)

| split | weighting | n | spread 10−1 E[R̄] | Spearman(SIR, R̄) |
|-------|-----------|---|-------------------|-------------------|
| TRAIN | TRADE_BALANCED | 503 | 69.302 | 0.453 |
| VALIDATION | TRADE_BALANCED | 481 | 17.689 | 0.192 |
| OOS | TRADE_BALANCED | 237 | 4.256 | 0.041 |

OOS top−bottom decile E[R̄] **4.256**. Replication token **INCONCLUSIVE**.

Occupancy residual-on-residual is a STATE_OCCUPANCY_WEIGHTED DIAGNOSTIC and is not the primary test.

## Persistence — TRADE_BALANCED

OOS median duration among trades ever |da|≥5¢: **21.0** possessions. `PERSISTENCE ≠ EXECUTABILITY`.

## Forward path (diagnostic only)

CANDLE PATH ≠ FILL. Forbidden in headline, V6-D, residual replication, and rank replication.

## What this is not

Not edge. Not a fill. Not production size. Not live. Not microstructure. Not monetization.

Economic scale: 5¢ × 100 contracts = 500¢ = $5.00 research-inventory displacement. Not realizable P&L.

**LIVE DEPLOYMENT: NOT AUTHORIZED**

