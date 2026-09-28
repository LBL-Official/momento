# Model card — XIB-NBA-V1

**Status:** FROZEN among evaluated 2024–25 VAL candidates. Market evaluation not authorized.

| Field | Value |
|-------|-------|
| Purpose | Calibrated P(home win \| information at t) for NBA research |
| Training data | NBA 2024–25 Dataset B. TRAIN `game_date <= 2025-02-28` (n=186,614). VAL after that date (n=90,380) |
| Selected model | **model1_plus_pregame** — simplest model with a material VAL Brier improvement (≥ 0.001) over Model 0 |
| Features | `score_difference`, `seconds_remaining_game`, `period`, `home/away_win_pct_pre`, `home/away_net_rating_pre`, `home/away_wins_last5_pre` |
| Calibration | Platt on VAL raw scores after TRAIN fit |
| VAL Brier | Model 0: 0.1743 · **Model 1: 0.1596** · Model 2: 0.1588 (Δ 0.00076 < bar) |
| VAL log loss / ECE | 0.4840 / 0.0351 |
| 2025–26 OOS | **not run — Phase 7 gated** |

### MODEL 3 COMPARISON: NOT RUN

```text
REASON: ENVIRONMENT DEPENDENCY UNAVAILABLE (libomp / LightGBM)
IMPLICATION: SELECTED MODEL IS BEST AMONG EVALUATED CANDIDATES
```

Do not rewrite as “Model 1 beat Model 3.”

**Intended use:** Frozen basketball F_t for later alignment research.

**Prohibited uses:** Live trading, sizing, edge claims, FIRST80 auto-integration, fit on 2025–26, treat MODELED candle rows as OBSERVED.

`MODEL ≠ EDGE`. Kalshi prices were not features.

Dataset C (not used in selection): **5,201 MODELED** alignments, **42,646 UNALIGNED**, 58 playoff tickers. See CURRENT_STATE.md.
