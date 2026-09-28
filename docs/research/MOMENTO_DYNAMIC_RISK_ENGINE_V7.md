# MOMENTO — Dynamic Risk Engine V7

**Program:** `MOMENTO_DYNAMIC_RISK_ENGINE_V7`
**Schema:** 1.0.0
**Date:** 2026-09-03
**Live execution changed:** FALSE
**Descriptive token:** `MIXED_EVIDENCE` — not a V7-A/B/C/D letter.

```
RESEARCH ONLY — Δα_state ≠ EDGE — CONDITIONAL INFORMATION ≠ EXECUTION — REPEATED POSSESSIONS ≠ INDEPENDENT OUTCOMES — LIVE DEPLOYMENT: NOT AUTHORIZED
```

> An observed state is not necessarily a well-supported state; a well-populated state is not necessarily independently supported; and an exactly scored state is not necessarily supported by a robust empirical distribution.

```
UNIQUE_TRADE_SUPPORT ≠ STATISTICAL_INDEPENDENCE. N_EFF_TRADE = OCCUPANCY CONCENTRATION MEASURE ≠ INDEPENDENT SAMPLE SIZE.
```

## Central question

Does the V6 disagreement structure survive when viewed through unique-trade support rather than possession occupancy?

V7 is a structural diagnostic of the frozen V5/V6 state surface. It does not fit a new M0 or M1. It does not rescue V6. It does not declare tradability.

## What this is not

- Not edge.
- Not a claim that M1 is wrong.
- Not an exploitable signal.
- Not a trading rule.
- Not statistical independence.
- Not a newly cleaned causal pipeline.

## Residual formula (TRADE_BALANCED)

r_bar_i = Pi_i - mean_t alpha_M0_it, where mean_t alpha_M0_it = (1/T_i) sum_t alpha_M0_it. One residual per trade. Repeated possessions are not independent terminals.

```
r_bar_i = Pi_i - mean_t(alpha_M0_it)
mean_t(alpha_M0_it) = (1/T_i) * sum_t alpha_M0_it
```

One residual per trade. Repeated possessions from the same trade are not independent terminals.

## Reconstruction provenance

Builders: `['dre_v5.possession_remaining.build_priors', 'dre_v5.state_panel.build_panel']`. `m0_m1_calls = 0`. Quietly improved: `False`.

Panel after scoring: **139966** rows / **1221** trades. Before-scoring counts matched after-scoring counts in the first scientific pass.

Priors use completion-before-start pace and TRAIN league-mean fallback. V7 documents the frozen V5 process; it does not claim a newly cleaned causal pipeline.

`Reproduce V5 exactly ≠ quietly improve V5 during reconstruction.`

## Gates

| Gate | Status |
|------|--------|
| A | **PASS** |
| B | **PASS** |
| C | **PASS** |
| D | **PASS** |
| E | **PASS** |
| F | **PASS** |
| G | **PASS** |
| H | **PASS** |
| I | **PASS** |
| J | **PASS** |

Gate J records V6 decile source = TRAIN `mean_SIR_i` qcut, unit = trade, `CLIP_TO_TRAIN_EXTREMA`. High-versus-low on `mean_da_i` is therefore applicable. OOS high-versus-low coverage was still inadequate (n_hi = 12 < 15) and is recorded as INCONCLUSIVE.

## Map integrity

Persisted V6 maps only. M0 **20** · M1 **584**. `m0_m1_calls = 0`.

## Four fields that never collapse

| Field | Meaning |
|-------|---------|
| `EXACT_CELL_EXISTS` | Frozen M1 key is present in the persisted map |
| `TRAIN_UNIQUE_TRADE_SUPPORT` | Unique TRAIN `trade_id` count in that cell (0 if missing) |
| `N_EFF_TRADE` | Occupancy-concentration effective trade count |
| `SCORING_PATH` | `M1_EXACT` / `M0_FALLBACK` / `GLOBAL_FALLBACK` |

A cell that exists with one TRAIN trade is not the same as missing → M0.

## Relationship A — STATE_OCCUPANCY_WEIGHTED DIAGNOSTIC

| Split | n rows | mean \|da\| | Spearman(\|da\|, unique TRAIN trades) | P(\|da\|≥5¢) |
|-------|-------:|------------:|----------------------------------------:|---------------:|
| TRAIN | 57059 | 4.928 | -0.520 | 0.270 |
| VALIDATION | 55192 | 4.215 | -0.473 | 0.247 |
| OOS | 27715 | 4.391 | -0.460 | 0.246 |

OOS occupancy-weighted mean \|da\| declines as unique-trade support rises (stratum 1 mean 37.9¢ → 50+ mean 2.7¢). This is a location statement, not a tradability statement.

## Relationship B — CELL_GEOMETRY_DIAGNOSTIC

OOS \|da\|≥5¢: n_rows **6814** · n_trades **221** · median TRAIN unique trades **31.000** · median N_eff **18.932** · scoring path M1_EXACT **6814** / M0_FALLBACK **0**.

OOS \|da\|≥10¢: n_rows **2663** · median TRAIN unique trades **18.000** · median N_eff **11.362**.

OOS baseline \|da\|<1¢: median TRAIN unique trades **146.000** · median N_eff **94.045**.

Extreme disagreement rows are exactly scored (M1_EXACT) more often than they are well supported. Exact scoring and robust support are not the same object.

## Relationship C — TRADE_BALANCED

TRAIN mean fraction sparse **0.023** · Spearman(\|mean_da\|, min support) **-0.400**.

OOS mean fraction sparse **0.025** · Spearman(\|mean_da\|, min support) **-0.297**.

## Distribution shift — STATE_OCCUPANCY_WEIGHTED DIAGNOSTIC

TV(TRAIN, VAL) **0.108**. TV(TRAIN, OOS) **0.148**.

OOS on TRAIN-observed M1 cells **0.995**. OOS M1_EXACT **0.995** · M0_FALLBACK **0.005** · GLOBAL **0.000**.

VALIDATION M0_FALLBACK **0.004**.

## Temporal stability — TEMPORAL_STABILITY_DIAGNOSTIC

| Split | Spearman(mean_da, r_bar) | high–low status |
|-------|-------------------------:|-----------------|
| TRAIN | 0.453 | OK |
| VALIDATION | 0.192 | OK |
| OOS | 0.041 | INCONCLUSIVE |

OOS cluster-bootstrap Spearman mean **0.047** · 5th **-0.086** · 95th **0.175**. This is variation under resampling of observed game-level clusters, not a population causal CI.

## Descriptive synthesis

Token: `MIXED_EVIDENCE`. Flags S1–S5: `{'S1': True, 'S2': False, 'S3': False, 'S4': True, 'S5': True}`.

- S1 (large \|da\| associated with lower unique-trade support): **True**. TRAIN Spearman -0.520; OOS -0.460. OOS \|da\|≥5 median TRAIN trades 31.000 vs baseline 146.000.
- S2 (occupancy inflation of independence): **False**. OOS extreme median rows/trade 4.119; median N_eff 18.932. The locked occupancy-inflation rule did not fire.
- S3 (VAL/OOS rare-cell or TV shift): **False**. Rare-row share TRAIN 0.022 vs OOS 0.025. TV(TRAIN,OOS) 0.148 is below the locked 0.15 token threshold.
- S4 (high-support Spearman larger in magnitude than low-support): **True**. OOS 20–49 0.186 vs 2–4 -0.089. Point estimates differ; high–low coverage is INCONCLUSIVE.
- S5 (well-supported extremes still degrade TRAIN→OOS): **True**. Overall Spearman TRAIN 0.453 → OOS 0.041 while OOS extreme-cell median unique trades is 31.000.

Allowed reading: extreme disagreement is disproportionately associated with lower unique-trade support, and TRAIN→OOS residual association still weakens after that association is visible.

Forbidden reading: therefore M1 is wrong; therefore there is an exploitable signal; therefore trade it.

## Bootstrap meaning

Variation under resampling of observed game-level clusters. Not a population causal CI.

**LIVE DEPLOYMENT: NOT AUTHORIZED**
