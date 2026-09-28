# Prospective 83¢ conditional-state research

## Does any observable state justify paying 83¢?

**YES — research candidate only / INSUFFICIENT DATA — prospective validation pending**

Canonical first-exact-83 N=2906. Locked exhaustive grid tested 6128 hypotheses. One predeclared 3-way (Candidate B: start_move>30 ∧ outs=0 ∧ vol_1m LOW) meets the historical ROBUST_RESEARCH_CANDIDATE gates on TRAIN/VAL/locked TEST, including discovery FDR q≤0.10. That is not prospective validation and not production. 40–49 remains the simplest +EV-on-all-splits 1-way (q≈0.173, TEST +2.41¢ < +3¢ report bar). Prospective holdout: 0 first-83 games. 757 W6 games exist after 2026-06-27 but W7 TRADE paths were not reconstructed.

PRODUCTION_COUNT = 0. Fill = `TRADE_PRINT_MODELED`. L2 = `UNAVAILABLE_SOURCE`.

## Integrity

{
  "n_duplicate_games": 0,
  "n_excluded": 0,
  "n_invalid_83": 0,
  "n_missing_settlement": 0,
  "n_test": 713,
  "n_total": 2906,
  "n_train": 1699,
  "n_val": 494,
  "one_per_game": true,
  "split_ok": true
}

## Primary table

| Rank | Condition | Cx | TRAIN N | VAL N | TEST N | TRAIN EV | VAL EV | TEST EV | FDR q | Bootstrap CI | Cost | Class |
|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---|
| 1 | `ALL_83` | 0 | 1699 | 494 | 713 | 0.11 | -0.81 | 1.43 | — | [-1.37, 3.96] | 1.0 | REJECTED |
| 2 | `start_price_band=40_49` | 1 | 486 | 141 | 233 | 3.42 | 1.40 | 2.41 | 0.173 | [-2.31, 6.70] | 2.0 | PROSPECTIVE_HOLDOUT_PENDING |
| 3 | `p_start_lt50=YES` | 1 | 600 | 176 | 259 | 3.17 | 1.09 | 1.94 | 0.168 | [-2.69, 6.19] | 1.0 | PROSPECTIVE_HOLDOUT_PENDING |
| 4 | `p_start_ge50=YES` | 1 | 1099 | 318 | 454 | -1.56 | -1.87 | 1.14 | 1.000 | [-2.16, 4.44] | 1.0 | REJECTED |
| 5 | `start_sentiment=UNDERDOG` | 1 | 301 | 93 | 147 | 4.04 | 0.87 | 5.44 | 0.200 | [-0.01, 10.20] | 5.0 | PROSPECTIVE_HOLDOUT_PENDING |
| 6 | `start_move_gt30=YES&outs=0&vol_1m_tertile=LOW` | 3 | 62 | 28 | 41 | 10.55 | 9.86 | 12.12 | 0.039 | [4.80, 17.00] | 5.0 | ROBUST_RESEARCH_CANDIDATE |
| 7 | `lead_signed=LEAD_2&start_move_gt30=YES&vol_1m_tertile=LOW` | 3 | 121 | 50 | 92 | 8.74 | 13.00 | 3.96 | 0.033 | [-2.57, 10.48] | 3.0 | PROSPECTIVE_HOLDOUT_PENDING |
| 8 | `score_bucket=TWO_RUN&start_move_gt30=YES&vol_1m_tertile=LOW` | 3 | 121 | 50 | 92 | 8.74 | 13.00 | 3.96 | 0.033 | [-2.57, 10.48] | 3.0 | PROSPECTIVE_HOLDOUT_PENDING |
| 9 | `move_fine=30_35&vol_1m_tertile=LOW&vol_15m_tertile=LOW` | 3 | 125 | 61 | 102 | 9.00 | 8.80 | 4.25 | 0.021 | [-2.61, 10.14] | 3.0 | PROSPECTIVE_HOLDOUT_PENDING |
| 10 | `inning_grp=7&p_max_vs_83=PEAK_AT` | 2 | 65 | 25 | 48 | 7.77 | 13.00 | 2.42 | 0.184 | [-5.92, 10.75] | 2.0 | PROSPECTIVE_HOLDOUT_PENDING |
| 11 | `start_price_band=40_49&lead_ge2=YES` | 2 | 378 | 115 | 183 | 5.10 | 2.22 | 2.79 | 0.067 | [-2.67, 7.71] | 2.0 | PROSPECTIVE_HOLDOUT_PENDING |
| 12 | `start_price_band=40_49&inning_late68=YES` | 2 | 206 | 43 | 97 | 2.92 | 3.05 | 3.60 | 0.442 | [-3.62, 9.78] | 3.0 | PROSPECTIVE_HOLDOUT_PENDING |
| 13 | `start_price_band=40_49&vol_1m_tertile=LOW` | 2 | 211 | 86 | 143 | 6.57 | 6.53 | 5.11 | 0.059 | [-0.48, 10.01] | 5.0 | PROSPECTIVE_HOLDOUT_PENDING |
| 14 | `start_price_band=40_49&start_move_gt20=YES` | 2 | 483 | 140 | 232 | 3.34 | 1.29 | 2.34 | 0.186 | [-2.40, 6.66] | 2.0 | PROSPECTIVE_HOLDOUT_PENDING |
| 15 | `start_price_band=40_49&vel_sign=UP` | 2 | 392 | 139 | 233 | 3.73 | 1.17 | 2.41 | 0.176 | [-2.31, 6.70] | 2.0 | PROSPECTIVE_HOLDOUT_PENDING |
| 16 | `start_price_band=40_49&last_event_class=RUN` | 2 | 43 | 29 | 55 | 10.02 | -0.24 | 2.45 | — | [-8.45, 11.55] | 2.0 | REJECTED |
| 17 | `p_start_lt50=YES&lead_ge2=YES` | 2 | 460 | 142 | 205 | 5.04 | 2.92 | 2.85 | 0.040 | [-2.02, 7.24] | 2.0 | PROSPECTIVE_HOLDOUT_PENDING |
| 18 | `p_start_ge50=YES&tied=YES` | 2 | 83 | 12 | 25 | -13.12 | -24.67 | -15.00 | 1.000 | [-35.00, 1.00] | — | REJECTED |
| 19 | `start_sentiment=FAVORITE` | 1 | 386 | 135 | 204 | -4.50 | 0.70 | -1.63 | 1.000 | [-7.02, 3.76] | — | REJECTED |
| 20 | `tied=YES` | 1 | 100 | 16 | 28 | -14.00 | -14.25 | -15.14 | 1.000 | [-29.43, -0.86] | — | REJECTED |
| 21 | `vol_1m_tertile=HIGH` | 1 | 425 | 66 | 117 | -2.76 | -5.73 | -6.08 | 1.000 | [-13.77, 1.62] | — | REJECTED |
| 22 | `lead_eq1=YES` | 1 | 456 | 116 | 174 | -2.30 | -7.14 | -1.97 | 1.000 | [-7.71, 3.78] | — | REJECTED |

## Incremental information

| Parent | Added | Δ TRAIN | Δ VAL | Δ TEST | Cx | Verdict |
|---|---|---:|---:|---:|---:|---|
| `start_price_band=40_49` | `start_price_band=40_49&lead_ge2=YES` | 1.68 | 0.82 | 0.38 | 2 | small lift |
| `start_price_band=40_49` | `start_price_band=40_49&inning_late68=YES` | -0.50 | 1.65 | 1.19 | 2 | adds on locked TEST; still not FDR-robust |
| `start_price_band=40_49` | `start_price_band=40_49&vol_1m_tertile=LOW` | 3.15 | 5.14 | 2.70 | 2 | adds on locked TEST; still not FDR-robust |
| `start_price_band=40_49` | `start_price_band=40_49&start_move_gt20=YES` | -0.08 | -0.11 | -0.06 | 2 | no useful incremental TEST EV |
| `start_price_band=40_49` | `start_price_band=40_49&vel_sign=UP` | 0.31 | -0.22 | 0.00 | 2 | no useful incremental TEST EV |
| `start_price_band=40_49` | `start_price_band=40_49&last_event_class=RUN` | 6.60 | -1.64 | 0.05 | 2 | small lift |
| `p_start_lt50=YES` | `p_start_lt50=YES&lead_ge2=YES` | 1.88 | 1.82 | 0.91 | 2 | small lift |

## Distinctions

| Layer | Meaning |
|---|---|
| historical association | cell EV on TRAIN/VAL |
| predictive evidence | survived TRAIN→VAL→locked TEST + FDR |
| prospective validation | frozen definition on post-2026-06-27 games |

## Conditional questions

### Q10_50k_scalable

No demonstrated scalability. qty=7 and +2–3¢ cannot produce 20% on $50k at observed first-83 frequency without inventing depth, fills, and annualization.

### Q1_start_belief

Partially. 40–49 and p_start<50 are +EV on TRAIN/VAL/TEST; favorites are not a demonstrated edge.

### Q2_baseball_after_pstart

Lead≥2 on 40–49 adds TRAIN/VAL EV; locked TEST lift is small. Not incremental enough to be the primary state.

### Q3_path_after_pstart

start_move on 40–49 is nearly redundant with being 40–49 (most 40–49 already moved >20¢ to 83). Little incremental TEST EV.

### Q4_vol_after_pstart

LOW 1m vol on 40–49 shows the largest predeclared incremental TRAIN/VAL/TEST lift in the frozen panel. Still FDR-uncorrected as a new 2-way versus the 6,128-test grid.

### Q5_momentum_after_pstart

vel_sign=UP on 40–49 does not add TEST EV versus 40–49 alone in this panel.

### Q6_event_after_pstart

last_event_class=RUN is historically interesting as a 1-way; incremental on 40–49 is not a frozen robust finding.

### Q7_interactions

3-ways (B/C/D/E) have high historical TEST EV and thin N. They are predeclared, not newly mined. None have discovery q≤0.10 documented on the 6,128-test BH.

### Q8_survives_train_val_test

Yes: 40–49 and several frozen 3-ways are +EV on all three locked splits. That is historical association + locked TEST, not prospective validation.

### Q9_cost_1_to_5

40–49 locked TEST +2.41¢ survives 0–2¢ hypothetical cost, not 3–5¢. Candidate B’s historical TEST +12¢ would survive 5¢ if the holdout confirmed it — the holdout does not exist.

## $50k capital simulation (not a forecast)

At qty=7, +3¢ EV earns $0.21/entry. 20% on $50k needs ~47,600 such entries/year. First-83 opportunity count cannot support that without inventing fills and depth.

## Prospective holdout

status=PROSPECTIVE_DATA_NOT_YET_AVAILABLE · available first-83=0 · W6 after cutoff=757 · W7 overlap=0

New data required: reconstruct W7 EventMarketPath for the 757 post-cutoff W6 games, then extract first-exact-83. A decisive holdout needs at least 25 first-83 games (research gate), preferably ≥50.

## Reproducibility

```
./target/release/momento-research-b1 --prospective-83
```

Research only. No live FIRST01 / W9 / L2 / orders.
