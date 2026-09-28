# DRE V2 — Model Card

**Program:** `MOMENTO_DYNAMIC_RISK_ENGINE_V2`  
**Date:** 2026-09-03  
**Live execution changed:** FALSE

## Intended use

Offline research: estimate `P(Settle YES | X_n)`, recovery and downside path probabilities, and a **theoretical** exposure fraction `h`.

Not intended for order routing, stop placement, or live risk.

## Training data

- Frozen FIRST-80 NBA 2025–2026 candle-path universe (1230 / 910 / 320 / 0).
- PADE V1 HIGH+MEDIUM trade × possession panel.
- Chronological game-level TRAIN / VALIDATION / OOS.

## Features

See `04_feature_dictionary/feature_dictionary.json`. Nested families B0–M5 plus `M3_NO_REM` ablation.

## Hyperparameters (frozen)

- LogisticRegression `C=1.0`, `class_weight=balanced`, `max_iter=400`, `random_state=42`
- StandardScaler
- Objective lambdas selected on VALIDATION only (see `11_exposure_surfaces/hyperparameters_selected.json`)
- **OOS was not used to tune**

## Metrics (OOS, selected)

| Target | B0 AUC | B1 AUC | B2 AUC | M3 AUC | M4 AUC | M5 AUC | B0 Brier | B1 Brier | B2 Brier | M3 Brier | M4 Brier | M5 Brier |
|--------|-------:|-------:|-------:|-------:|-------:|-------:|-------:|-------:|-------:|-------:|-------:|-------:|
| `y_settle_yes` | 0.843 | 0.842 | 0.847 | 0.861 | 0.853 | 0.845 | 0.160 | 0.163 | 0.161 | 0.157 | 0.157 | 0.159 |
| `y_rec_ge_10_k5` | 0.852 | 0.849 | 0.884 | 0.887 | 0.890 | 0.891 | 0.158 | 0.160 | 0.132 | 0.132 | 0.127 | 0.126 |
| `y_det_ge_10_end` | 0.810 | 0.786 | 0.802 | 0.803 | 0.807 | 0.807 | 0.206 | 0.206 | 0.183 | 0.182 | 0.178 | 0.178 |
| `y_jump_40` | 0.832 | 0.814 | 0.784 | 0.780 | 0.790 | 0.790 | 0.196 | 0.199 | 0.193 | 0.187 | 0.181 | 0.181 |
| `y_min_le_40_k5` | 0.990 | 0.990 | 0.995 | 0.994 | 0.994 | 0.994 | 0.036 | 0.036 | 0.029 | 0.028 | 0.029 | 0.029 |

## Limitations

- Complete-case drops rows with invalid velocity/acceleration (M5) or missing R2 (M3).
- Candle path ≠ fill.
- Class-balanced logits are not probability-calibrated to raw base rates; ECE is reported, not “fixed” on OOS.
- Theoretical `h` is not executable.

## Ethical / trading safety

LIVE DEPLOYMENT: **NOT AUTHORIZED**

RESEARCH ONLY — CANDLE PATH ≠ ACTUAL FILL — THEORETICAL TARGET DELTA ≠ EXECUTED DELTA — THEORETICAL EXPOSURE ≠ ACTUAL EXECUTION — LIVE DEPLOYMENT: NOT AUTHORIZED
