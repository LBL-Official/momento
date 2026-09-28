# Conditional 83¢ entry-state search

**Question:** Given an MLB Kalshi contract trading at 83¢, what observable combination of baseball state, starting market belief, and market/price history produced the highest robust out-of-sample expected value?

This is **not** a 80-vs-81-vs-83 price comparison. The universe is `ENTRY_83` / `entry_price_cents = 83` only. 80/81/82 prints are excluded from ranking.

**Fill status:** `TRADE_PRINT_MODELED`. `executable_fill_confirmed: false`. Research labels only. Not a live rule.

## 1. Direct answer

**Given an MLB Kalshi contract already trading at 83¢, the strongest robust hold-to-settlement state was `start_price_band=40_49` (status `CANDIDATE`).**

In English: an 83¢ YES entry was most favorable when the contract **opened as a mild underdog (about 40–49¢)** and later **repriced to 83¢**. That is a large start-to-entry move, but “any move > +20¢” alone did **not** pass VAL. Strong underdogs (`P_start < 40`) were too rare and not helpful. Contracts that **opened already ≥50¢** (favorites that only drifted to 83¢) were unfavorable.

- Entry price: **83¢** (fixed)
- Games (all / test): **129 / 21**
- TEST EV: **7.48¢/contract** (lift vs ALL_83: 5.63¢)
- EV per 7-contract stake: **52.33¢** ($0.52)
- TEST Sharpe (game, unann.): **0.249**
- TEST win rate: **90.5%**
- TEST P&L (qty=7, uncompounded vs $50): **$10.99**
- TEST MaxDD: **$11.62**
- MFE / MAE (all, ¢): 14.8 / -28.4
- TRAIN EV 1.21¢ → VAL 1.62¢ → TEST 7.48¢ (decay 6.27¢)

TEST game-level bootstrap 95% CI for mean P&L/game: **$-0.48 to $1.19**. The interval **includes $0**, so this is not a confirmed edge — CANDIDATE only.

## 2. Dataset

- Universe: B1 snapshots with `entry_trade_price_cents = 83` only
- N 83¢ entries / unique games: **497 / 497**
- Date split: official B1 chronological 60/20/20 on the full W8 feature universe (not re-cut on 83¢ dates): TRAIN < `2025-10-07`, VAL < `2026-05-03`, TEST through `2026-06-27`
- Primary label: `HOLD_TO_SETTLEMENT` (W6). EV = mean(settlement_value − 83) ¢/contract. Breakeven ≈ 83% win rate before fees.
- Independence unit: **game**
- Floors: exploratory ≥30 games, candidate ≥50, strong ≥100
- Candidates evaluated: 206
- L2 / OBI / mid / fair value: unused (`UNAVAILABLE_SOURCE`)

## 3. ALL_83 baseline (hold to settlement)

| Split | Entries | Games | Win | EV¢ | Sharpe | P&L $ | MaxDD $ |
|---|---:|---:|---:|---:|---:|---:|---:|
| ALL | 497 | 497 | 0.797 | -3.32 | -0.082 | -115.57 | 140.70 |
| TRAIN | 379 | 379 | 0.794 | -3.58 | -0.088 | -94.99 | 111.93 |
| VAL | 52 | 52 | 0.750 | -8.00 | -0.183 | -29.12 | 33.88 |
| TEST | 66 | 66 | 0.848 | 1.85 | 0.051 | 8.54 | 20.58 |

Every conditional cell is compared to this ALL_83 hold baseline (`EV_Lift = Conditional_EV − All_83_EV`). 80–83 band results are a different study.

## 4. Search methodology

Staged search on ENTRY_83 only:

1. Univariate over the available B1 feature families
2. Motivated pairs plus top-TRAIN univariate pairs (TRAIN EV > ALL_83 TRAIN EV, TRAIN n≥30)
3. Motivated three-ways, then combinatorial three-ways from cells that already had +VAL and +TEST hold EV
4. Motivated four-ways, then combinatorial four-ways if TRAIN n≥50

Tertile cuts are fit on **83¢ TRAIN only**. No threshold is tuned on TEST. Ranking for the primary table requires +VAL EV, +TEST EV, TEST Sharpe > 0, TEST n≥15, VAL n≥10, and ≥30 unique games. Tiny TEST slices that go 100% (EV = +17.00¢ exactly, Sharpe undefined) are discarded. Prefer +TRAIN EV for stability, then TEST EV, then TEST Sharpe. Do not rank by total P&L or in-sample Sharpe.

## 5. Feature universe

Used (B1 schema, TRADE prints): inning (raw + EARLY/MID/LATE_6_7/LATE_8/NINTH), half, lead thresholds, score_bucket, outs, base class/state, start sentiment / P_start thresholds, StartToEntryMove thresholds and tertiles, personality, velocity / acceleration / path efficiency / path distance / reversals, volatility 1/5/15/30m and TRAIN z tertile, last event class/sign, event-count band.

Unused (UNAVAILABLE_SOURCE): OBI, OBI_z, MicroPrice, Spread, Depth, OFI, Absorption, Replenishment, FairValue, bid/ask.

## 6. Best individual conditions

| Condition | Games | Test n | TEST EV¢ | VAL EV¢ | TRAIN EV¢ | TEST Sharpe | Lift | Status |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| inning_83=MID | 128 | 23 | 8.30 | 7.91 | -5.34 | 0.288 | 6.46 | CANDIDATE |
| start_price_band=40_49 | 129 | 21 | 7.48 | 1.62 | 1.21 | 0.249 | 5.63 | CANDIDATE |
| p_start_lt50=YES | 156 | 25 | 5.00 | 1.62 | 0.90 | 0.151 | 3.15 | CANDIDATE |
| p_start_ge50=NO | 156 | 25 | 5.00 | 1.62 | 0.90 | 0.151 | 3.15 | CANDIDATE |
| outs=2 | 155 | 25 | 1.00 | 2.00 | -13.00 | 0.027 | -0.85 | EXPLORATORY |
| outs_band=LATE_OUT | 155 | 25 | 1.00 | 2.00 | -13.00 | 0.027 | -0.85 | EXPLORATORY |
| lead_ge4=YES | 61 | 12 | 17.00 | -16.33 | 5.37 | NaN | 15.15 | WEAK |
| event_run_sign=UP | 150 | 10 | 17.00 | -20.50 | -1.18 | NaN | 15.15 | WEAK |
| score_bucket=MULTI_RUN | 190 | 25 | 13.00 | -5.73 | -2.58 | 0.650 | 11.15 | WEAK |
| lead_ge3=YES | 190 | 25 | 13.00 | -5.73 | -2.58 | 0.650 | 11.15 | WEAK |
| vol_1m_tertile=LOW | 196 | 21 | 12.24 | -6.08 | -0.45 | 0.561 | 10.39 | WEAK |
| last_event_sign=UP | 285 | 18 | 11.44 | -10.27 | -0.96 | 0.486 | 9.60 | WEAK |

## 7. Best 2-way conditions

| Condition | Games | Test n | TEST EV¢ | VAL EV¢ | TRAIN EV¢ | TEST Sharpe | Lift | Status |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| start_price_band=40_49&p_start_lt50=YES | 129 | 21 | 7.48 | 1.62 | 1.21 | 0.249 | 5.63 | CANDIDATE |
| start_price_band=40_49&p_start_ge50=NO | 129 | 21 | 7.48 | 1.62 | 1.21 | 0.249 | 5.63 | CANDIDATE |
| p_start_lt50=YES&p_start_ge50=NO | 156 | 25 | 5.00 | 1.62 | 0.90 | 0.151 | 3.15 | CANDIDATE |
| score_bucket=MULTI_RUN&start_move_gt20=YES | 175 | 23 | 12.65 | -3.00 | -2.70 | 0.607 | 10.80 | WEAK |
| lead_ge3=YES&p_start_lt50=YES | 83 | 14 | 9.86 | -8.00 | 2.25 | 0.369 | 8.01 | WEAK |
| start_sentiment=UNDERDOG&start_move_gt20=YES | 77 | 13 | 9.31 | 4.50 | -4.43 | 0.336 | 7.46 | WEAK |
| outs=0&outs_band=EARLY_OUT | 101 | 12 | 8.67 | -8.00 | 2.71 | 0.300 | 6.82 | WEAK |
| vel_1m_tertile=MID&p_start_lt50=YES | 59 | 11 | 7.91 | -33.00 | 1.09 | 0.262 | 6.06 | WEAK |
| vel_1m_tertile=MID&p_start_ge50=NO | 59 | 11 | 7.91 | -33.00 | 1.09 | 0.262 | 6.06 | WEAK |
| lead_ge2=YES&vol_z_tertile=LOW | 133 | 32 | 7.62 | -0.39 | -3.51 | 0.257 | 5.78 | WEAK |
| lead_ge2=YES&start_move_gt20=YES | 297 | 39 | 6.74 | -4.21 | -2.11 | 0.219 | 4.90 | WEAK |
| start_move_dir=UP&vol_5m_tertile=LOW | 315 | 53 | 3.79 | -7.44 | -1.43 | 0.111 | 1.94 | WEAK |

## 8. Best 3-way conditions

| Condition | Games | Test n | TEST EV¢ | VAL EV¢ | TRAIN EV¢ | TEST Sharpe | Lift | Status |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| score_bucket=MULTI_RUN&p_start_lt50=YES&start_move_gt20=YES | 83 | 14 | 9.86 | -8.00 | 2.25 | 0.369 | 8.01 | WEAK |
| lead_ge2=YES&start_move_gt20=YES&vol_5m_tertile=LOW | 199 | 35 | 5.57 | -6.33 | -2.40 | 0.173 | 3.72 | WEAK |
| lead_ge2=YES&p_start_lt50=YES&start_move_gt20=YES | 121 | 19 | 1.21 | -3.00 | 1.78 | 0.032 | -0.64 | WEAK |

## 9. Best 4-way conditions

*No cells at this stage with ≥30 unique games and ≥10 TEST games.*

## 10. Best overall 83¢ condition (hold)

| Rank | 83¢ condition | Stage | Games | Test n | Test EV¢ | Test Sharpe | Test WR | EV lift | Status |
|---:|---|---:|---:|---:|---:|---:|---:|---:|---|
| 1 | start_price_band=40_49 | 1 | 129 | 21 | 7.48 | 0.249 | 0.905 | 5.63 | CANDIDATE |
| 2 | p_start_lt50=YES | 1 | 156 | 25 | 5.00 | 0.151 | 0.880 | 3.15 | CANDIDATE |
| 3 | inning_83=MID | 1 | 128 | 23 | 8.30 | 0.288 | 0.913 | 6.46 | CANDIDATE |
| 4 | outs=2 | 1 | 155 | 25 | 1.00 | 0.027 | 0.840 | -0.85 | EXPLORATORY |

## 11. Worst overall 83¢ condition (hold)

These are **UNFAVORABLE_83_STATE** candidates: same 83¢ entry, worse TEST settlement EV.

1. `vol_1m_tertile=HIGH` TEST EV -11.57¢ TRAIN -9.85¢ VAL -6.08¢ (n=142 test_n=21) status=UNFAVORABLE
2. `vol_z_tertile=MID` TEST EV -9.67¢ TRAIN -3.13¢ VAL -16.33¢ (n=179 test_n=15) status=UNFAVORABLE
3. `lead_ge2=NO` TEST EV -9.09¢ TRAIN -9.32¢ VAL -12.41¢ (n=154 test_n=23) status=UNFAVORABLE
4. `lead_regime=CLOSE` TEST EV -9.09¢ TRAIN -8.66¢ VAL -12.41¢ (n=153 test_n=23) status=UNFAVORABLE
5. `base_class=BASES_EMPTY` TEST EV -8.00¢ TRAIN -0.80¢ VAL 3.96¢ (n=242 test_n=28) status=UNFAVORABLE
6. `base_state=___` TEST EV -8.00¢ TRAIN -0.80¢ VAL 3.96¢ (n=242 test_n=28) status=UNFAVORABLE
7. `lead_eq1=YES` TEST EV -8.00¢ TRAIN -5.22¢ VAL -9.67¢ (n=116 test_n=20) status=UNFAVORABLE
8. `score_bucket=ONE_RUN` TEST EV -6.81¢ TRAIN -7.10¢ VAL -9.67¢ (n=119 test_n=21) status=UNFAVORABLE
9. `start_sentiment=FAVORITE` TEST EV -6.53¢ TRAIN -7.00¢ VAL -0.65¢ (n=134 test_n=17) status=UNFAVORABLE
10. `inning_83=EARLY` TEST EV -5.22¢ TRAIN -3.35¢ VAL -20.93¢ (n=228 test_n=27) status=UNFAVORABLE

## 12. Train / VAL / Test

See ALL_83 table above and per-condition columns in `b1_83_condition_rankings.csv`. Conditions were proposed from TRAIN (and motivated baseball/market hypotheses). VAL and TEST were not used to cut thresholds.

## 13. Bootstrap CI

Game-level bootstrap (n=1000, seed=42) on TEST P&L/game for each cell is in `b1_83_condition_search.json` (`bootstrap_test_ev_usd_ci95`). A CI that crosses $0 is not a confirmed edge.

## 14. Monthly stability

ALL_83 monthly hold P&L is in `b1_83_stability.json`. Leave-one-month-out for the top validated cell is in the same file (`remains_positive` per left-out month). A cell that flips sign when one month is removed is not robust.

## 15. Threshold sensitivity

- `start_move_gt5=YES` TEST EV 1.85¢ VAL -8.00¢ TRAIN -3.33¢ n=487 status=WEAK
- `start_move_gt10=YES` TEST EV 1.38¢ VAL -5.00¢ TRAIN -3.45¢ n=471 status=WEAK
- `start_move_gt15=YES` TEST EV 1.13¢ VAL -5.92¢ TRAIN -3.06¢ n=445 status=WEAK
- `start_move_gt20=YES` TEST EV 0.64¢ VAL -7.44¢ TRAIN -3.27¢ n=391 status=WEAK
- `start_move_gt25=YES` TEST EV 2.71¢ VAL -2.35¢ TRAIN -2.65¢ n=302 status=WEAK
- `start_move_gt30=YES` TEST EV 2.71¢ VAL -8.00¢ TRAIN -4.13¢ n=182 status=WEAK
- `p_start_lt40=YES` TEST EV -8.00¢ VAL NaN¢ TRAIN -0.39¢ n=27 status=TOO_SMALL
- `p_start_lt45=YES` TEST EV 7.91¢ VAL 0.33¢ TRAIN -1.18¢ n=83 status=WEAK
- `p_start_lt50=YES` TEST EV 5.00¢ VAL 1.62¢ TRAIN 0.90¢ n=156 status=CANDIDATE

If only one adjacent threshold is positive, label the cut **fragile**.

## 16. Other exits (do not replace the settlement question)

Primary question remains settlement EV of an 83¢ state. Horizon labels are short-term TRADE continuation. Stops are path-dependent TRADE prints. None are maker fills.

### Short-horizon (HORIZON_1M) top cells

1. `lead_ge4=YES` TEST EV 5.08¢ Sharpe 1.808 n=58
2. `score_bucket=MULTI_RUN` TEST EV 4.48¢ Sharpe 1.306 n=174
3. `lead_ge3=YES` TEST EV 4.48¢ Sharpe 1.306 n=174
4. `score_bucket=MULTI_RUN&start_move_gt20=YES` TEST EV 4.35¢ Sharpe 1.229 n=160
5. `last_event_class=RUN` TEST EV 4.07¢ Sharpe 0.953 n=81

### Stop-path (LIVE_50PCT_STOP) top cells

1. `lead_ge4=YES` TEST EV 11.08¢ Sharpe 0.541 n=61
2. `outs=0` TEST EV 7.00¢ Sharpe 0.300 n=101
3. `outs_band=EARLY_OUT` TEST EV 7.00¢ Sharpe 0.300 n=101
4. `outs=0&outs_band=EARLY_OUT` TEST EV 7.00¢ Sharpe 0.300 n=101
5. `score_bucket=MULTI_RUN` TEST EV 6.96¢ Sharpe 0.295 n=190

### Best hold condition under every A1 exit

- `FIRST01` TEST EV -2.90¢ Sharpe -0.101 n_test=21 status=WEAK
- `HARD_STOP_60` TEST EV -1.19¢ Sharpe -0.055 n_test=21 status=WEAK
- `HARD_STOP_65` TEST EV -0.19¢ Sharpe -0.010 n_test=21 status=WEAK
- `HARD_STOP_70` TEST EV 0.38¢ Sharpe 0.023 n_test=21 status=CANDIDATE
- `HARD_STOP_75` TEST EV -0.76¢ Sharpe -0.058 n_test=21 status=WEAK
- `HOLD_TO_SETTLEMENT` TEST EV 7.48¢ Sharpe 0.249 n_test=21 status=CANDIDATE
- `HORIZON_15M` TEST EV -1.29¢ Sharpe -0.092 n_test=21 status=WEAK
- `HORIZON_1M` TEST EV -1.76¢ Sharpe -0.204 n_test=21 status=WEAK
- `HORIZON_30M` TEST EV 3.43¢ Sharpe 0.238 n_test=21 status=CANDIDATE
- `HORIZON_5M` TEST EV -0.33¢ Sharpe -0.038 n_test=21 status=WEAK
- `LIVE_50PCT_STOP` TEST EV -2.90¢ Sharpe -0.101 n_test=21 status=WEAK

## 17. Multiple-testing / data-mining warning

206 cells were scored. Many share overlapping games. A raw TEST winner is expected under noise, especially when the unconditional 83¢ hold EV is already negative. Benjamini–Hochberg was **not** used as the primary ranker (the primary ranker is chronological +EV). Do not promote a cell to a live rule because it is rank 1 in this file.

## 18. Execution limitations

- TRADE print ≠ maker fill. Queue, cancel, and fill probability are unknown.
- Fees are omitted. 83¢ maker/taker economics are not invented.
- qty = 625 // 83 = 7 contracts; P&L is uncompounded vs a $50 snapshot.
- A1 exits are **research labels**, not live execution assumptions.
- Live FIRST01 80/81/83/89 and the 50% stop were **not** changed.
- W9 was **not** started. L2 was **not** invented. No ML. No fair value.

## 19. Final research conclusion

**FAVORABLE_83_STATE:** `start_price_band=40_49` (status `CANDIDATE`). An 83¢ YES print was most favorable when this opening-belief / game-state filter held, with +VAL and +TEST settlement EV and adequate TEST games. Treat as a research discovery, not a production filter.

**UNFAVORABLE_83_STATE:** `vol_1m_tertile=HIGH` — TEST EV -11.57¢ on 21 TEST / 142 total games (status `UNFAVORABLE`).

The example hypothesis “late innings + lead ≥2 + large start-to-entry repricing” did **not** earn a robust hold-to-settlement promotion: several of those cells were +TRAIN/+VAL and −TEST. Do not deploy it.

**STOP.** Do not modify live FIRST01, risk, or W9 from this report.
