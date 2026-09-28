# B1 exhaustive 80–83¢ / A1 exit search

**Classification:** DESCRIPTIVE RESEARCH FINDING. Not a trading rule.

**Fill status:** `TRADE_PRINT_MODELED`. `executable_fill_confirmed: false`.

P&L is uncompounded, `qty = 625 // entry_cents` ($6.25 of $50). No fees.

## Reconciliation

W8 first80 late-lead2 hold: n=254 games=254 hold=$33.88. Published 254 / $33.88 match=true.

Prior 110-trade JSON has no row keys; the reproducible audit target is the 254-trade full-universe hold path.

B1 snapshots: 2884. Chronological date split TRAIN < `2025-10-07`, VALIDATION < `2026-05-03`.

## A. What entry price performed best?

| Entry | Exit | N | Games | Win | EV¢ | P&L $ | Sharpe | MaxDD $|
|---|---|---:|---:|---:|---:|---:|---:|---:|
| ENTRY_80 | hold | 207 | 207 | 0.754 | -4.64 | -67.20 | -0.107 | 91.00 |
| ENTRY_81 | hold | 1500 | 1500 | 0.822 | 1.20 | 126.00 | 0.031 | 68.32 |
| ENTRY_82 | hold | 680 | 680 | 0.825 | 0.50 | 23.80 | 0.013 | 46.20 |
| ENTRY_83 | hold | 497 | 497 | 0.797 | -3.32 | -115.57 | -0.082 | 140.70 |
| ENTRY_BAND_80_83 | hold | 2884 | 2884 | 0.813 | -0.16 | -32.97 | -0.004 | 143.92 |

## B. What exit performed best?

See `b1_exit_comparison.json` and `b1_best_by_exit.json`. Hold is settlement prediction; horizons are short-term price prediction; stops are path-dependent TRADE prints.

## C–E. Baseball / start / path

See `b1_edge_shape.json` (TEST-only buckets) and Tier-1 cells in `b1_condition_matrix.json`.

## F. Highest raw performance

1. `ENTRY_80|HORIZON_1M|score_bucket=MULTI_RUN&start_move_tertile=MID` Sharpe(all)=1.591 n_games=29 P&L=$13.72 status=PROMISING_BUT_UNCONFIRMED
2. `ENTRY_80|HORIZON_1M|score_bucket=MULTI_RUN` Sharpe(all)=1.335 n_games=72 P&L=$31.08 status=PROMISING_BUT_UNCONFIRMED
3. `ENTRY_82|HORIZON_15M|regime=LATE_LEAD` Sharpe(all)=1.303 n_games=28 P&L=$16.59 status=REJECTED
4. `ENTRY_BAND_80_83|HORIZON_5M|score_bucket=MULTI_RUN&start_move_tertile=LOW` Sharpe(all)=1.246 n_games=132 P&L=$49.77 status=PROMISING_BUT_UNCONFIRMED
5. `ENTRY_BAND_80_83|HORIZON_15M|score_bucket=MULTI_RUN&start_move_tertile=LOW` Sharpe(all)=1.239 n_games=133 P&L=$63.07 status=PROMISING_BUT_UNCONFIRMED

## G. Chronological OOS

1. `ENTRY_BAND_80_83|HORIZON_1M|score_bucket=MULTI_RUN&start_move_tertile=MID` test Sharpe=0.872 test EV¢=3.11 test P&L=$16.52 n_test=76
2. `ENTRY_81|HORIZON_1M|score_bucket=MULTI_RUN&start_move_tertile=MID` test Sharpe=0.861 test EV¢=3.00 test P&L=$11.34 n_test=54
3. `ENTRY_BAND_80_83|HORIZON_1M|score_bucket=MULTI_RUN` test Sharpe=0.821 test EV¢=3.09 test P&L=$47.95 n_test=222
4. `ENTRY_BAND_80_83|HORIZON_5M|score_bucket=MULTI_RUN` test Sharpe=0.716 test EV¢=3.84 test P&L=$59.64 n_test=222
5. `ENTRY_81|HOLD_TO_SETTLEMENT|personality=CHOPPY&vol_5m_tertile=MID` test Sharpe=0.713 test EV¢=14.65 test P&L=$70.77 n_test=69

## H–I. Bootstrap and concentration

Game-level bootstrap (n=1000, seed=42) is in `b1_bootstrap_results.json`. One-month domination flag is on each candidate.

## J. Most robust historical cohort

```json
{
  "bootstrap_ci": {
    "id": "ENTRY_BAND_80_83|HORIZON_1M|score_bucket=MULTI_RUN",
    "test_ev_usd_ci95": [
      0.1835135135135135,
      0.24846846846846848
    ]
  },
  "classification": "ROBUST_CANDIDATE",
  "concentration_metrics": {
    "month_concentration": 0.16329225352112675,
    "one_month_domination": false
  },
  "condition_definition": "score_bucket=MULTI_RUN",
  "entry_bucket": "ENTRY_BAND_80_83",
  "ev": 2.704761904761905,
  "executable_fill_confirmed": false,
  "exit_bucket": "HORIZON_1M",
  "feature_conditions": "score_bucket=MULTI_RUN",
  "fill_status": "TRADE_PRINT_MODELED",
  "mae": -24.95357142857143,
  "max_drawdown": 3.57,
  "mfe": 16.50952380952381,
  "multiple_testing_adjustment": "Benjamini-Hochberg FDR q=0.10 on TRAIN P(EV<=0)",
  "n_entries": 840,
  "n_unique_games": 840,
  "note": "DESCRIPTIVE_ONLY. Not a trading rule.",
  "research_status": "ROBUST_CANDIDATE",
  "return_pct": 3.1808,
  "sharpe": 0.6180812726400486,
  "sharpe_monthly_ann": 5.8292408598366645,
  "sortino": 1.264944085202457,
  "test_metrics": {
    "best_trade_cents": 98,
    "entries_per_game": 1.0,
    "ev_cents": 3.0855855855855854,
    "exit_positive_rate": 0.6936936936936937,
    "longest_lose_streak": 4,
    "longest_win_streak": 18,
    "max_dd_cents": 49,
    "max_dd_usd": 0.49,
    "max_entries_per_game": 1,
    "mean_mae_cents": -23.87837837837838,
    "mean_mfe_cents": 16.846846846846848,
    "mean_return_cents": 3.0855855855855854,
    "median_entries_per_game": 1.0,
    "median_return_cents": 3,
    "n_entries": 222,
    "n_unique_games": 222,
    "profit_factor": 8.696629213483146,
    "return_pct_of_50": 0.959,
    "sharpe_game_unann": 0.8212965881445561,
    "sharpe_monthly_ann": null,
    "sortino_game_unann": 3.1705058420737577,
    "stdev_pnl_cents": 26.29878098957529,
    "total_pnl_cents": 4795,
    "total_pnl_usd": 47.95,
    "win_rate": 0.8918918918918919,
    "worst_trade_cents": -49
  },
  "total_pnl": 159.04,
  "train_metrics": {
    "best_trade_cents": 98,
    "entries_per_game": 1.0,
    "ev_cents": 2.5881057268722465,
    "exit_positive_rate": 0.6629955947136564,
    "longest_lose_streak": 3,
    "longest_win_streak": 22,
    "max_dd_cents": 357,
    "max_dd_usd": 3.57,
    "max_entries_per_game": 1,
    "mean_mae_cents": -25.273127753303964,
    "mean_mfe_cents": 16.262114537444933,
    "mean_return_cents": 2.5881057268722465,
    "median_entries_per_game": 1.0,
    "median_return_cents": 2,
    "n_entries": 454,
    "n_unique_games": 454,
    "profit_factor": 5.718875502008032,
    "return_pct_of_50": 1.645,
    "sharpe_game_unann": 0.5414538526077807,
    "sharpe_monthly_ann": 5.018839917391838,
    "sortino_game_unann": 0.9474251066211344,
    "stdev_pnl_cents": 33.45943518704476,
    "total_pnl_cents": 8225,
    "total_pnl_usd": 82.25,
    "win_rate": 0.8480176211453745,
    "worst_trade_cents": -343
  },
  "validation_metrics": {
    "best_trade_cents": 91,
    "entries_per_game": 1.0,
    "ev_cents": 2.5121951219512195,
    "exit_positive_rate": 0.6829268292682927,
    "longest_lose_streak": 2,
    "longest_win_streak": 10,
    "max_dd_cents": 56,
    "max_dd_usd": 0.56,
    "max_entries_per_game": 1,
    "mean_mae_cents": -25.524390243902438,
    "mean_mfe_cents": 16.73780487804878,
    "mean_return_cents": 2.5121951219512195,
    "median_entries_per_game": 1.0,
    "median_return_cents": 2,
    "n_entries": 164,
    "n_unique_games": 164,
    "profit_factor": 5.847058823529411,
    "return_pct_of_50": 0.5768,
    "sharpe_game_unann": 0.6347808803923243,
    "sharpe_monthly_ann": 2.7851404036419827,
    "sortino_game_unann": 2.0577522181240253,
    "stdev_pnl_cents": 27.703049031328668,
    "total_pnl_cents": 2884,
    "total_pnl_usd": 28.84,
    "win_rate": 0.8292682926829268,
    "worst_trade_cents": -56
  },
  "win_rate": 0.8559523809523809
}
```

## K. Economic caveats

No fees. TRADE print ≠ maker fill. No L2, size, or queue. Live FIRST01 is unchanged. A positive cell is not an executable edge.

## Top 20 validated / robust

| Rank | Entry | Exit | Condition | N | Games | TrEV | VaEV | TeEV | TrSh | VaSh | TeSh | TeP&L | MaxDD | WR | Status |
|---:|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| 1 | ENTRY_BAND_80_83 | HORIZON_1M | score_bucket=MULTI_RUN&start_move_tertile=MID | 307 | 307 | 2.32 | 3.01 | 3.11 | 0.56 | 0.76 | 0.87 | 16.52 | 0.35 | 0.857 | ROBUST_CANDIDATE |
| 2 | ENTRY_81 | HORIZON_1M | score_bucket=MULTI_RUN&start_move_tertile=MID | 154 | 154 | 1.14 | 2.60 | 3.00 | 0.26 | 0.63 | 0.86 | 11.34 | 0.35 | 0.877 | PROMISING_BUT_UNCONFIRMED |
| 3 | ENTRY_BAND_80_83 | HORIZON_1M | score_bucket=MULTI_RUN | 840 | 840 | 2.59 | 2.51 | 3.09 | 0.54 | 0.63 | 0.82 | 47.95 | 0.49 | 0.856 | ROBUST_CANDIDATE |
| 4 | ENTRY_BAND_80_83 | HORIZON_5M | score_bucket=MULTI_RUN | 896 | 896 | 3.24 | 2.76 | 3.84 | 0.58 | 0.51 | 0.72 | 59.64 | 2.38 | 0.855 | ROBUST_CANDIDATE |
| 5 | ENTRY_81 | HOLD_TO_SETTLEMENT | personality=CHOPPY&vol_5m_tertile=MID | 358 | 358 | -0.25 | 5.00 | 14.65 | -0.01 | 0.14 | 0.71 | 70.77 | 5.67 | 0.844 | REJECTED |
| 6 | ENTRY_81 | HORIZON_1M | score_bucket=MULTI_RUN | 402 | 402 | 1.28 | 2.15 | 2.60 | 0.22 | 0.55 | 0.71 | 27.09 | 0.35 | 0.871 | ROBUST_CANDIDATE |
| 7 | ENTRY_BAND_80_83 | HORIZON_5M | score_bucket=MULTI_RUN&start_move_tertile=HIGH | 435 | 435 | 2.66 | 1.80 | 3.62 | 0.44 | 0.29 | 0.68 | 28.35 | 1.05 | 0.853 | ROBUST_CANDIDATE |
| 8 | ENTRY_BAND_80_83 | HORIZON_5M | late_6_9_lead2=YES | 336 | 336 | 2.17 | 3.94 | 3.67 | 0.30 | 0.62 | 0.68 | 23.10 | 0.70 | 0.845 | ROBUST_CANDIDATE |
| 9 | ENTRY_BAND_80_83 | HORIZON_1M | score_bucket=MULTI_RUN&start_move_tertile=HIGH | 404 | 404 | 2.42 | 1.43 | 2.63 | 0.61 | 0.36 | 0.65 | 20.65 | 0.77 | 0.854 | ROBUST_CANDIDATE |
| 10 | ENTRY_82 | HORIZON_1M | lead_regime=LEAD | 395 | 395 | 1.34 | 0.57 | 2.89 | 0.28 | 0.11 | 0.65 | 14.14 | 1.12 | 0.866 | ROBUST_CANDIDATE |
| 11 | ENTRY_BAND_80_83 | HORIZON_1M | lead_regime=LEAD&start_move_tertile=LOW | 399 | 399 | 2.07 | 2.28 | 2.40 | 0.42 | 0.56 | 0.65 | 16.10 | 0.49 | 0.852 | ROBUST_CANDIDATE |
| 12 | ENTRY_BAND_80_83 | HORIZON_1M | lead_regime=LEAD&start_sentiment=STRONG_FAVORITE&personality=CHOPPY | 230 | 230 | 2.88 | 2.08 | 2.64 | 0.76 | 0.66 | 0.64 | 9.24 | 0.49 | 0.848 | ROBUST_CANDIDATE |
| 13 | ENTRY_81 | HORIZON_5M | score_bucket=MULTI_RUN | 430 | 430 | 2.31 | 2.10 | 3.42 | 0.42 | 0.38 | 0.62 | 35.70 | 2.38 | 0.867 | ROBUST_CANDIDATE |
| 14 | ENTRY_81 | HORIZON_5M | late_6_9_lead2=YES | 179 | 179 | 2.50 | 3.42 | 3.15 | 0.41 | 0.53 | 0.61 | 15.68 | 0.70 | 0.821 | ROBUST_CANDIDATE |
| 15 | ENTRY_81 | HORIZON_30M | vel_1m_tertile=LOW&accel_sign=NEG | 235 | 235 | -0.52 | 1.96 | 6.82 | -0.03 | 0.12 | 0.60 | 23.87 | 4.90 | 0.826 | REJECTED |
| 16 | ENTRY_BAND_80_83 | HORIZON_5M | score_bucket=MULTI_RUN&start_move_tertile=MID | 329 | 329 | 3.02 | 3.13 | 3.58 | 0.61 | 0.64 | 0.59 | 19.04 | 2.31 | 0.854 | ROBUST_CANDIDATE |
| 17 | ENTRY_81 | HORIZON_5M | regime=MID_LEAD&start_sentiment=UNDERDOG | 131 | 131 | 1.67 | 0.21 | 3.72 | 0.33 | 0.03 | 0.58 | 13.79 | 1.05 | 0.870 | PROMISING_BUT_UNCONFIRMED |
| 18 | ENTRY_81 | HORIZON_5M | regime=MID_LEAD&start_sentiment=UNDERDOG&start_move_tertile=HIGH | 131 | 131 | 1.67 | 0.21 | 3.72 | 0.33 | 0.03 | 0.58 | 13.79 | 1.05 | 0.870 | PROMISING_BUT_UNCONFIRMED |
| 19 | ENTRY_BAND_80_83 | HORIZON_1M | late_6_9_lead2=YES | 307 | 307 | 2.49 | 3.24 | 2.58 | 0.58 | 0.69 | 0.58 | 16.24 | 0.98 | 0.850 | ROBUST_CANDIDATE |
| 20 | ENTRY_BAND_80_83 | HORIZON_5M | regime=MID_LEAD&start_sentiment=NEUTRAL | 290 | 290 | 1.95 | 0.78 | 3.00 | 0.30 | 0.11 | 0.57 | 17.22 | 1.12 | 0.838 | ROBUST_CANDIDATE |

## False winners

- `ENTRY_80|HORIZON_15M|lead_regime=LEAD&start_move_tertile=LOW` — small sample
- `ENTRY_BAND_80_83|HORIZON_5M|late_6_9_lead2=YES&start_sentiment=STRONG_FAVORITE` — small sample
- `ENTRY_BAND_80_83|HORIZON_30M|personality=ACCELERATING&vol_5m_tertile=LOW` — small sample
- `ENTRY_82|FIRST01|late_6_9_lead2=YES&start_sentiment=UNDERDOG` — small sample
- `ENTRY_82|LIVE_50PCT_STOP|late_6_9_lead2=YES&start_sentiment=UNDERDOG` — small sample
- `ENTRY_83|HORIZON_5M|regime=MID_LEAD&start_sentiment=UNDERDOG` — small sample
- `ENTRY_83|HORIZON_1M|accel_sign=NEG` — train/test decay / validation fail
- `ENTRY_BAND_80_83|HORIZON_15M|personality=ACCELERATING&vol_5m_tertile=LOW` — small sample
- `ENTRY_BAND_80_83|FIRST01|late_6_9_lead2=YES&start_sentiment=STRONG_FAVORITE` — small sample
- `ENTRY_BAND_80_83|LIVE_50PCT_STOP|late_6_9_lead2=YES&start_sentiment=STRONG_FAVORITE` — small sample
- `ENTRY_83|HORIZON_15M|personality=CHOPPY&start_sentiment=STRONG_UNDERDOG` — small sample
- `ENTRY_80|HORIZON_5M|lead_regime=LEAD&start_move_tertile=LOW` — small sample
- `ENTRY_80|HORIZON_1M|lead_regime=LEAD&start_move_tertile=LOW` — small sample
- `ENTRY_83|HORIZON_1M|vel_1m_tertile=LOW&accel_sign=NEG` — train/test decay / validation fail
- `ENTRY_BAND_80_83|FIRST01|late_6_9_lead2=YES&start_move_tertile=LOW` — small sample

## Universe

8894 candidates tested. This is a multiple-comparison search. RAW BEST ≠ VALIDATED BEST.

**STOP.** No B2, W9, or live change.
