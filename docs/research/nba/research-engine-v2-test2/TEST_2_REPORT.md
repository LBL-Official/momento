# TEST_2_REPORT — NBA Research Engine V2

Identity: `NBA_RESEARCH_ENGINE_V2_TEST2`

Written `2026-09-01T19:10:57.214064+00:00`

This report does **not** overwrite Path Engine V1 (Verdict C / NO FILTER) or
Game Path Engine V2 (Verdict C / NO FILTER). Research only. Not live FIRST01.

## Scientific verdict

**D**

Simple game-state logistic outperforms the full possession/market stack on VAL; neither beats Model 0 Brier. Complex models overfit TRAIN. An exploratory q̂<0.30 filter is not promoted (Brier/calibration gates fail).

## Production status

**NO FILTER**

A production candidate still requires OOS `EV_accepted > EV_unconditional`
(≈ 0.220 R), calibration, separation, and acceptance ≥ 50%.
This run: oos_filter_ok=True.

## Frozen baseline

| Quantity | Count |
| --- | ---: |
| First-80 | 1230 |
| Survive close-path 40 | 910 |
| Hit close-path 40 | 320 |
| Unconditional q | 0.2602 |
| Unconditional EV | 0.2195 R |

Source: `path_engine_v1_observations`

## Phase 1 gate

- ok: True
- primary HIGH∪MEDIUM n=1169 q=0.2643
- excluded n=54 Δq=0.0042
- material exclusion bias: False
- overlay quality: {'EXACT_ALIGNMENT': 19191, 'MULTI_POSSESSION_CANDLE': 145013, 'MULTI_CANDLE_POSSESSION': 57527, 'PARTIAL_ALIGNMENT': 3226}
- leakage audit pass: True

Primary clock is **possession index**. Intra-period wall time is MODELED
(`PERIOD_BOUNDED_LINEAR_GAME_CLOCK`). Per-play `timeActual` remains unavailable.
1-minute candles are market-sampling artifacts. No L2.

## Feature store

- rows: 1230 primary=1169 columns=201
- TRAIN n=480 VAL n=458 OOS n=231
- numeric features: 141
- high-correlation pairs (|r|≥0.9): 40

Exploratory univariate tests (BH q=0.10) are labeled
`DISCOVERED AFTER MULTIPLE SEARCHES`.

## Unsupervised

PCA leading variance: 0.5725
best k (TRAIN q range): 10
cluster TRAIN separation ≥8pp (n≥30): True
OOS assignment persistence: True

A 2-D embedding is **not** evidence. UMAP was not used as proof.

## Supervised vs Model 0 (q̂ = 26.02%)

| Item | Value |
| --- | --- |
| Model 0 VAL Brier | 0.1892 |
| Best L2 logistic family | game_state |
| Best VAL Brier | 0.1888 |
| Best OOS Brier | 0.1815 |
| VAL beats Model 0 (≤95%) | False |
| OOS beats Model 0 (≤95%) | False |
| Simple game-state wins VAL | True |
| Coupling helps VAL | False |

Mandatory family ablation is in `models.json` (game state / path / market
state / path / coupling / game+market / full).

Calibration (Platt/isotonic) is TRAIN-CV only if present in the registry.
Never fit on VALIDATION or OOS.

## Economics

`EV_gross = 1 − 3q`. Breakeven q = 33.33%. Research fee estimates, if any,
are **NOT** the production FeeModel.

{
  "ev_unconditional": 0.2195121951219512,
  "q_unconditional": 0.2601626016260163,
  "breakeven_q": 0.3333333333333333,
  "research_fee_estimate": "NOT production FeeModel",
  "rows": [
    {
      "model": "model0_unconditional",
      "feature_set": "none",
      "split": "validation",
      "n": null,
      "q": null,
      "ev": null,
      "brier": 0.18917426579740287,
      "auc": 0.5,
      "ece": 0.0068874924557106865,
      "chosen_threshold": null,
      "oos_frozen_filter": null
    },
    {
      "model": "model0_unconditional",
      "feature_set": "none",
      "split": "oos",
      "n": null,
      "q": null,
      "ev": null,
      "brier": 0.18189286422480944,
      "auc": 0.5,
      "ece": null,
      "chosen_threshold": null,
      "oos_frozen_filter": null
    },
    {
      "model": "l2_logistic",
      "feature_set": "game_state",
      "split": "validation",
      "n": 458,
      "q": 0.25327510917030566,
      "ev": 0.24017467248908297,
      "brier": 0.1887991650390557,
      "auc": 0.5599415204678363,
      "ece": 0.04021374828560698,
      "chosen_threshold": 0.3,
      "oos_frozen_filter": null
    },
    {
      "model": "l2_logistic",
      "feature_set": "game_state",
      "split": "oos",
      "n": 231,
      "q": 0.23809523809523808,
      "ev": 0.2857142857142858,
      "brier": 0.18152889363326846,
      "auc": 0.5794421487603306,
      "ece": 0.05264463844560567,
      "chosen_threshold": 0.3,
      "oos_frozen_filter": {
        "threshold": 0.3,
        "n_accepted": 135,
        "acceptance_rate": 0.5844155844155844,
        "actual_q": 0.2,
        "ev": 0.3999999999999999,
        "beats": true,
        "acc_ok": true
      }
    },
    {
      "model": "l2_logistic",
      "feature_set": "game_path",
      "split": "validation",
      "n": 458,
      "q": 0.25327510917030566,
      "ev": 0.24017467248908297,
      "brier": 0.20166321239971402,
      "auc": 0.5144938495664448,
      "ece": 0.0916136383798978,
      "chosen_threshold": 0.3,
      "oos_frozen_filter": null
    },
    {
      "model": "l2_logistic",
      "feature_set": "game_path",
      "split": "oos",
      "n": 231,
      "q": 0.23809523809523808,
      "ev": 0.2857142857142858,
      "brier": 0.18905819479585836,
      "auc": 0.5673553719008264,
      "ece": 0.06693338589784496,
      "chosen_threshold": 0.3,
      "oos_frozen_filter": {
        "threshold": 0.3,
        "n_accepted": 138,
        "acceptance_rate": 0.5974025974025974,
        "actual_q": 0.2028985507246377,
        "ev": 0.3913043478260869,
        "beats": true,
        "acc_ok": true
      }
    },
    {
      "model": "l2_logistic",
      "feature_set": "market_state",
      "split": "validation",
      "n": 458,
      "q": 0.25327510917030566,
      "ev": 0.24017467248908297,
      "brier": 0.18896905501819497,
      "auc": 0.5602440008066142,
      "ece": 0.03556553334759403,
      "chosen_threshold": 0.3333,
      "oos_frozen_filter": null
    },
    {
      "model": "l2_logistic",
      "feature_set": "market_state",
      "split": "oos",
      "n": 231,
      "q": 0.23809523809523808,
      "ev": 0.2857142857142858,
      "brier": 0.1839113790767962,
      "auc": 0.5339876033057851,
      "ece": 0.04919415101166606,
      "chosen_threshold": 0.3333,
      "oos_frozen_filter": {
        "threshold": 0.3333,
        "n_accepted": 224,
        "acceptance_rate": 0.9696969696969697,
        "actual_q": 0.23660714285714285,
        "ev": 0.2901785714285714,
        "beats": true,
        "acc_ok": true
      }
    },
    {
      "model": "l2_logistic",
      "feature_set": "market_path",
      "split": "validation",
      "n": 458,
      "q": 0.25327510917030566,
      "ev": 0.24017467248908297,
      "brier": 0.20967648796110158,
      "auc": 0.5223835450695705,
      "ece": 0.12637497029829792,
      "chosen_threshold": 0.3,
      "oos_frozen_filter": null
    },
    {
      "model": "l2_logistic",
      "feature_set": "market_path",
      "s

## Portfolio

Research concurrency only. Not live MLB allocations. Not optimized on OOS.

{
  "max_same_day": 14,
  "mean_same_day": 5.514150943396227,
  "days": 212,
  "note": "Research concurrency diagnostic. Not live capital. Not optimized on OOS.",
  "weekly_first80_primary": 33.26422764227642,
  "expected_weekly_unfiltered": 33.26422764227642,
  "capital_note": "Research bankroll parameters \u2014 not live MLB allocations."
}

Weekly first-80 (primary set): 33.26

## Guardrails honored

- Frozen 1230 / 910 / 320 labels reused; not rebuilt as a new definition
- No L2 invented; no maker fills claimed
- Modeled wall clock not claimed OBSERVED
- TRAIN=BUILD, VAL=CHOOSE, OOS=VERIFY once
- Failed hypotheses remain in `experiment_registry.json`

## Line of production

**NO FILTER**

Does not change live 80/40, Risk, or Kalshi execution.
