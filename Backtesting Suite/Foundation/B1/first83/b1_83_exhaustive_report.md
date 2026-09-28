# Exhaustive Conditional 83¢ Research

## 1. Executive answer

VAL-selected primary (TEST locked): **`inning_grp=7&p_max_vs_83=PEAK_AT`** class `CANDIDATE`.

TRAIN n=65 EV=7.77¢ WR=90.8% · VAL n=25 EV=13.00¢ WR=96.0% · TEST n=48 EV=2.42¢ WR=85.4% Sharpe=0.068

**NO ROBUST OPTIMAL STATE FOUND** under TRAIN≥50 / VAL≥25 / TEST≥25. The primary is the strongest VAL-selected simple state that stayed +TEST.

## 2. Universe and methodology

- Universe: `entry_trade_price_cents=83` only. N snapshots/games = 2906/2906.
- Duplicate policy: B1 stores **one** primary 83¢ TRADE snapshot per game (`max_entries_per_game=1`). Sharpe/bootstrap/permutation use game-level P&L.
- Split (unchanged): TRAIN < `2025-10-07`, VAL < `2026-05-03`, TEST through `2026-06-27`.
- Discovery: TRAIN. Selection score: TRAIN+VAL only. TEST evaluated after freeze.
- Stake: qty = 625 // 83 = 7. Uncompounded. Sharpe = game mean P&L / sample stdev (unannualized).
- Fill: `TRADE_PRINT_MODELED`.

Selection score (no TEST): `+2+clip(train_ev,8)/4` if TRAIN EV>0 else −2; `+3+clip(val_ev,8)/4` if VAL EV>0 else −4; +1 if TRAIN n≥50; +2 if VAL n≥25 else +0.5 if VAL n≥15 else −1.5−0.2×(15−VAL n) if VAL n≥10; −3 if VAL EV≥16 and VAL n<15 (perfect thin cell); +TRAIN/VAL positive-month fraction; −0.4×(depth−1); −max(train−val,0)/8; −2 if month concentration ≥0.60. Primary confirmation after freeze: TEST n≥min_test and TEST EV>0; REJECTED/OVERFIT cannot be primary.

## 3. Data leakage controls

Forbidden keys asserted on every feature name and condition: settlement, mfe, mae, exit_, future, pnl, return_cents, win_rate, fair_value, obi, microprice. Tertiles/quantiles fit on 83¢ TRAIN only. Settlement is label only.

## 4. Search-space definition

49 registry features across START_BELIEF, BASEBALL_STATE, PATH, PERSONALITY, VELOCITY, ACCELERATION, VOLATILITY, EVENT_RESPONSE. Same-family pairs skipped (redundancy map). 40–49 is a competing 1-way, not a seed.

## 5. Search counts

| Stage | Generated (TRAIN-pruned) | Share |
|---|---:|---:|
| 1-way | 153 | 2.5% |
| 2-way | 5732 | 93.5% |
| 3-way | 243 | 4.0% |
| 4-way | 0 | 0.0% |
| 5-way | 0 | 0.0% |
| Stored | 6128 | |
| TRAIN+ | 3491 | |
| TRAIN+VAL+ | 1726 | |
| TEST evaluated | 6128 | |

## 6. ALL_83 baseline

| Split | Games | WR | EV¢ | Sharpe | P&L $ |
|---|---:|---:|---:|---:|---:|
| ALL | 2906 | 0.833 | 0.28 | 0.007 | 56.14 |
| TRAIN | 1699 | 0.831 | 0.11 | 0.003 | 12.81 |
| VAL | 494 | 0.822 | -0.81 | -0.021 | -28.14 |
| TEST | 713 | 0.844 | 1.43 | 0.039 | 71.47 |

## 7. Best single-feature states

- sel=11.33 `inning_grp=7` TRAIN 1.74 VAL 14.62 TEST 5.89 n=190/42/72 class=CANDIDATE
- sel=11.04 `inning_83=LATE_6_7` TRAIN 1.67 VAL 6.89 TEST -0.72 n=424/89/158 class=REJECTED
- sel=10.74 `last_event_class=RUN` TRAIN 5.10 VAL 3.21 TEST 5.89 n=168/87/153 class=CANDIDATE
- sel=10.39 `move_fine=30_35` TRAIN 2.94 VAL 4.21 TEST 3.58 n=313/86/149 class=CANDIDATE
- sel=10.31 `lead_signed=LEAD_2` TRAIN 3.93 VAL 2.71 TEST -0.05 n=528/182/258 class=REJECTED
- sel=10.27 `score_bucket=TWO_RUN` TRAIN 3.60 VAL 2.71 TEST -0.05 n=530/182/258 class=REJECTED
- sel=10.12 `p_start_fine=45_49` TRAIN 2.19 VAL 3.11 TEST -0.27 n=297/72/139 class=REJECTED
- sel=10.12 `p_start_45_49=YES` TRAIN 2.19 VAL 3.11 TEST -0.27 n=297/72/139 class=REJECTED

## 8. Best 2-way states

- sel=12.54 `inning_grp=7&p_max_vs_83=PEAK_AT` TRAIN 7.77 VAL 13.00 TEST 2.42 n=65/25/48 class=CANDIDATE
- sel=12.49 `p_start_fine=45_49&lead_signed=LEAD_2` TRAIN 8.03 VAL 13.00 TEST -6.68 n=78/25/38 class=REJECTED
- sel=12.49 `p_start_fine=45_49&score_bucket=TWO_RUN` TRAIN 8.03 VAL 13.00 TEST -6.68 n=78/25/38 class=REJECTED
- sel=12.49 `p_start_45_49=YES&lead_signed=LEAD_2` TRAIN 8.03 VAL 13.00 TEST -6.68 n=78/25/38 class=REJECTED
- sel=12.49 `p_start_45_49=YES&score_bucket=TWO_RUN` TRAIN 8.03 VAL 13.00 TEST -6.68 n=78/25/38 class=REJECTED
- sel=12.22 `p_start_lt50=YES&inning_83=LATE_6_7` TRAIN 6.47 VAL 17.00 TEST 2.29 n=171/36/68 class=CANDIDATE
- sel=12.22 `p_start_ge50=NO&inning_83=LATE_6_7` TRAIN 6.47 VAL 17.00 TEST 2.29 n=171/36/68 class=CANDIDATE
- sel=12.22 `p_start_tertile=LOW&inning_83=LATE_6_7` TRAIN 6.47 VAL 17.00 TEST 2.29 n=171/36/68 class=CANDIDATE

## 9. Best 3-way states

- sel=12.12 `lead_ge2=YES&outs=0&vol_1m_tertile=LOW` TRAIN 7.70 VAL 10.02 TEST 10.94 n=86/43/66 class=CANDIDATE
- sel=12.08 `move_fine=30_35&vol_1m_tertile=LOW&vol_15m_tertile=LOW` TRAIN 9.00 VAL 8.80 TEST 4.25 n=125/61/102 class=ROBUST
- sel=12.01 `start_move_gt30=YES&outs=0&vol_1m_tertile=LOW` TRAIN 10.55 VAL 9.86 TEST 12.12 n=62/28/41 class=ROBUST
- sel=12.00 `lead_signed=LEAD_2&start_move_gt30=YES&vol_1m_tertile=LOW` TRAIN 8.74 VAL 13.00 TEST 3.96 n=121/50/92 class=ROBUST
- sel=12.00 `score_bucket=TWO_RUN&start_move_gt30=YES&vol_1m_tertile=LOW` TRAIN 8.74 VAL 13.00 TEST 3.96 n=121/50/92 class=ROBUST
- sel=11.93 `lead_signed=LEAD_2&vol_1m_tertile=LOW&accel_sign=NEG` TRAIN 6.91 VAL 13.30 TEST 4.80 n=109/27/41 class=CANDIDATE

## 10. Best 4-way states

No 4-way cell met TRAIN n≥40 after family/support pruning.

## 11. Raw TEST winners (OVERFIT RISK)

- `p_start_30_34=YES` TRAIN 12.45 VAL 2.71 TEST 17.00 n=22/7/4
- `move_fine=0_5` TRAIN 2.71 VAL NaN TEST 17.00 n=14/0/1
- `move_fine=5_10` TRAIN 4.23 VAL -27.44 TEST 17.00 n=47/9/7
- `last_delta_band=GE_10` TRAIN -6.44 VAL NaN TEST 17.00 n=64/0/3
- `start_price_band=40_49&reversal_tertile=MID` TRAIN -0.72 VAL NaN TEST 17.00 n=158/0/1
- `start_price_band=50_59&vol_15m_tertile=HIGH` TRAIN -2.05 VAL 17.00 TEST 17.00 n=126/1/6
- `start_price_band=60_69&path_eff_tertile=HIGH` TRAIN -2.27 VAL NaN TEST 17.00 n=109/0/1
- `start_price_band=60_69&path_eff_tertile=MID` TRAIN -4.28 VAL 9.31 TEST 17.00 n=94/13/7

Do not treat these as trading candidates.

## 12. Validation-selected winners

- sel=12.54 `inning_grp=7&p_max_vs_83=PEAK_AT` TRAIN 7.77 VAL 13.00 TEST 2.42 n=65/25/48
- sel=12.49 `p_start_fine=45_49&lead_signed=LEAD_2` TRAIN 8.03 VAL 13.00 TEST -6.68 n=78/25/38
- sel=12.49 `p_start_fine=45_49&score_bucket=TWO_RUN` TRAIN 8.03 VAL 13.00 TEST -6.68 n=78/25/38
- sel=12.49 `p_start_45_49=YES&lead_signed=LEAD_2` TRAIN 8.03 VAL 13.00 TEST -6.68 n=78/25/38
- sel=12.49 `p_start_45_49=YES&score_bucket=TWO_RUN` TRAIN 8.03 VAL 13.00 TEST -6.68 n=78/25/38
- sel=12.22 `p_start_lt50=YES&inning_83=LATE_6_7` TRAIN 6.47 VAL 17.00 TEST 2.29 n=171/36/68
- sel=12.22 `p_start_ge50=NO&inning_83=LATE_6_7` TRAIN 6.47 VAL 17.00 TEST 2.29 n=171/36/68
- sel=12.22 `p_start_tertile=LOW&inning_83=LATE_6_7` TRAIN 6.47 VAL 17.00 TEST 2.29 n=171/36/68
- sel=12.18 `base_class=BASES_EMPTY&move_fine=GE_40` TRAIN 6.76 VAL 10.33 TEST -3.45 n=127/30/44
- sel=12.16 `inning_grp=7&vol_1m_tertile=LOW` TRAIN 6.25 VAL 17.00 TEST 5.10 n=93/31/42

## 13. Robust winners

ROBUST count (n gates + +EV on all three + BH FDR q≤0.10): 4. ALL_83 VAL n=52; few subsets can hit VAL≥25. FDR typically keeps 0–1 cells, so ROBUST is expected to be empty.

## 14. Best negative states

- `p_start_40_54=NO&lead_signed=TIED` TRAIN -13.38 VAL -28.45 TEST -13.00 n=79/11/20
- `p_start_40_54=NO&tied=YES` TRAIN -13.38 VAL -28.45 TEST -13.00 n=79/11/20
- `p_start_40_54=NO&score_bucket=TIED` TRAIN -13.38 VAL -28.45 TEST -13.00 n=79/11/20
- `p_start_35_49=NO&lead_signed=TIED` TRAIN -14.76 VAL -24.67 TEST -15.00 n=85/12/25
- `p_start_35_49=NO&tied=YES` TRAIN -14.76 VAL -24.67 TEST -15.00 n=85/12/25
- `p_start_35_49=NO&score_bucket=TIED` TRAIN -14.76 VAL -24.67 TEST -15.00 n=85/12/25
- `p_start_lt50=NO&lead_signed=TIED` TRAIN -13.12 VAL -24.67 TEST -15.00 n=83/12/25
- `p_start_lt50=NO&tied=YES` TRAIN -13.12 VAL -24.67 TEST -15.00 n=83/12/25

## 15. Starting-price analysis

Predeclared bands (TRAIN-defined / overlapping regions declared before TEST). H1: is the edge localized in 40–49 or a broader underdog-repricing effect?

- `start_price_band=40_49` TRAIN 3.42 VAL 1.40 TEST 2.41 n=486/141/233
- `p_start_lt50=YES` TRAIN 3.17 VAL 1.09 TEST 1.94 n=600/176/259
- `p_start_ge50=YES` TRAIN -1.56 VAL -1.87 TEST 1.14 n=1099/318/454
- `p_start_lt30=YES` TRAIN -16.33 VAL 17.00 TEST NaN n=12/1/0
- `p_start_30_34=YES` TRAIN 12.45 VAL 2.71 TEST 17.00 n=22/7/4
- `p_start_35_39=YES` TRAIN 2.00 VAL -1.52 TEST -5.73 n=80/27/22
- `p_start_35_49=YES` TRAIN 3.22 VAL 0.93 TEST 1.71 n=566/168/255
- `p_start_40_44=YES` TRAIN 5.36 VAL -0.39 TEST 6.36 n=189/69/94
- `p_start_45_49=YES` TRAIN 2.19 VAL 3.11 TEST -0.27 n=297/72/139
- `p_start_40_54=YES` TRAIN 2.62 VAL -0.14 TEST 2.79 n=786/245/401
- `p_start_50_54=YES` TRAIN 1.33 VAL -2.23 TEST 3.31 n=300/104/168
- `p_start_55_59=YES` TRAIN -4.73 VAL 1.96 TEST -1.29 n=336/113/164
- `p_start_60_69=YES` TRAIN -2.39 VAL -2.77 TEST 0.78 n=361/86/111
- `p_start_70p=YES` TRAIN 3.27 VAL -23.00 TEST 7.91 n=102/15/11
- `p_start_fine=40_44` TRAIN 5.36 VAL -0.39 TEST 6.36 n=189/69/94
- `p_start_fine=45_49` TRAIN 2.19 VAL 3.11 TEST -0.27 n=297/72/139
- `p_start_tertile=LOW` TRAIN 3.17 VAL 1.09 TEST 1.94 n=600/176/259
- `p_start_tertile=MID` TRAIN -0.11 VAL -1.00 TEST 1.64 n=567/200/306
- `p_start_tertile=HIGH` TRAIN -3.11 VAL -3.34 TEST 0.11 n=532/118/148
- `start_sentiment=UNDERDOG` TRAIN 4.04 VAL 0.87 TEST 5.44 n=301/93/147
- `start_sentiment=FAVORITE` TRAIN -4.50 VAL 0.70 TEST -1.63 n=386/135/204

## 16. Incremental-information analysis

- {"condition":"ALL_83","layer":"ALL_83","n":2906,"test_ev":1.4319775596072932,"train_ev":0.10771041789287816,"val_ev":-0.8137651821862348}
- {"condition":"p_start_lt50=YES","layer":"START_BELIEF","n":1035,"test_ev":1.942084942084942,"train_ev":3.1666666666666665,"val_ev":1.0909090909090908}
- {"condition":"start_price_band=40_49","layer":"START_40_49","n":860,"test_ev":2.407725321888412,"train_ev":3.419753086419753,"val_ev":1.3971631205673758}
- {"condition":"p_start_lt50=YES&lead_ge2=YES","ev_lift_vs_all83_test":1.4216809769780725,"layer":"START+LEAD","n":807,"test_ev":2.8536585365853657,"test_n":205,"train_ev":5.043478260869565,"train_n":460,"val_ev":2.915492957746479,"val_n":142}
- {"condition":"start_price_band=40_49&lead_ge2=YES","ev_lift_vs_all83_test":1.3603721671686633,"layer":"START_40_49+LEAD","n":676,"test_ev":2.7923497267759565,"test_n":183,"train_ev":5.095238095238095,"train_n":378,"val_ev":2.217391304347826,"val_n":115}
- {"condition":"start_price_band=40_49&inning_late68=YES","ev_lift_vs_all83_test":2.1659605847226038,"layer":"START_40_49+INNING","n":346,"test_ev":3.597938144329897,"test_n":97,"train_ev":2.9223300970873787,"train_n":206,"val_ev":3.046511627906977,"val_n":43}
- {"condition":"start_price_band=40_49&start_move_gt20=YES","ev_lift_vs_all83_test":0.9128500265996031,"layer":"START_40_49+PATH","n":855,"test_ev":2.3448275862068964,"test_n":232,"train_ev":3.3354037267080745,"train_n":483,"val_ev":1.2857142857142858,"val_n":140}
- {"condition":"start_price_band=40_49&vol_1m_tertile=LOW","ev_lift_vs_all83_test":3.6799105522808184,"layer":"START_40_49+VOL","n":440,"test_ev":5.111888111888112,"test_n":143,"train_ev":6.57345971563981,"train_n":211,"val_ev":6.534883720930233,"val_n":86}
- {"condition":"start_price_band=40_49&vel_sign=UP","ev_lift_vs_all83_test":0.9757477622811188,"layer":"START_40_49+VEL","n":764,"test_ev":2.407725321888412,"test_n":233,"train_ev":3.7346938775510203,"train_n":392,"val_ev":1.1726618705035972,"val_n":139}

## 17. Bootstrap

Game-level, n=10000, seed=42, on TEST of VAL finalists. See `b1_83_bootstrap.json`.

## 18. Permutation/placebo test

Shuffle game P&L, keep condition size. See `b1_83_permutation_test.json`.

## 19. Multiple-testing analysis

BH FDR q=0.10 on TRAIN P(mean P&L≤0). Tested 6128. Reject 162. Uncorrected TEST EV is not an edge.

## 20. Monthly stability

See `b1_83_monthly_stability.json`.

## 21. Economic sensitivity

- {"hypothetical_cost_cents":0,"note":"Hypothetical TRADE-print cost. Not Kalshi fees.","survives":true,"test_ev_gross":2.4166666666666665,"test_ev_net":2.4166666666666665}
- {"hypothetical_cost_cents":1,"note":"Hypothetical TRADE-print cost. Not Kalshi fees.","survives":true,"test_ev_gross":2.4166666666666665,"test_ev_net":1.4166666666666665}
- {"hypothetical_cost_cents":2,"note":"Hypothetical TRADE-print cost. Not Kalshi fees.","survives":true,"test_ev_gross":2.4166666666666665,"test_ev_net":0.4166666666666665}
- {"hypothetical_cost_cents":3,"note":"Hypothetical TRADE-print cost. Not Kalshi fees.","survives":false,"test_ev_gross":2.4166666666666665,"test_ev_net":-0.5833333333333335}
- {"hypothetical_cost_cents":5,"note":"Hypothetical TRADE-print cost. Not Kalshi fees.","survives":false,"test_ev_gross":2.4166666666666665,"test_ev_net":-2.5833333333333335}

## 22. 40–49 benchmark comparison

Benchmark (not a seed): `start_price_band=40_49` TRAIN 3.42 VAL 1.40 TEST 2.41 n=486/141/233.

- Did any VAL-selected condition beat 40–49 on both TRAIN and VAL EV? **yes**
  - `inning_grp=7&p_max_vs_83=PEAK_AT` TRAIN 7.77 VAL 13.00 TEST 2.42 n=65/25/48
  - `p_start_fine=45_49&lead_signed=LEAD_2` TRAIN 8.03 VAL 13.00 TEST -6.68 n=78/25/38
  - `p_start_fine=45_49&score_bucket=TWO_RUN` TRAIN 8.03 VAL 13.00 TEST -6.68 n=78/25/38
  - `p_start_45_49=YES&lead_signed=LEAD_2` TRAIN 8.03 VAL 13.00 TEST -6.68 n=78/25/38
  - `p_start_45_49=YES&score_bucket=TWO_RUN` TRAIN 8.03 VAL 13.00 TEST -6.68 n=78/25/38
- Did any simple VAL-supported state beat 40–49 on locked TEST without being a raw-TEST winner? **yes**
- Incremental add-ons to 40–49 are in §16 / `b1_83_incremental_information.json` (baseball, path, velocity, volatility).
- Is 40–49 still the simplest VAL-selected primary? **no — see §1 / §25**

## 23. What information actually matters

Ranked by how often the group appears in VAL-selected +TRAIN+VAL cells (TEST shown after freeze, not used to choose the group):

1. `BASEBALL_STATE` (21 hits among VAL finalists)
2. `START_BELIEF` (14 hits among VAL finalists)
3. `VOLATILITY` (11 hits among VAL finalists)
4. `PATH` (9 hits among VAL finalists)
5. `ACCELERATION` (2 hits among VAL finalists)

## 24. What information does not help

Groups / patterns that did not produce a VAL-stable lift over the start-belief 1-ways, or that fail TRAIN+VAL:

1. Higher-order (3–4 way) cells: extra predicates shrink VAL n below the ROBUST gate without a pre-TEST score advantage.
2. Repricing magnitude (`start_move_*`) without start location: H2 — move size is largely a restatement of P_start when entry is fixed at 83¢.
3. Last-event class / last-delta as a stand-alone hold filter (H event-response): no VAL-stable incremental edge after start belief.

## 25. Final optimal conditional state

**NO ROBUST OPTIMAL STATE FOUND** (ROBUST requires TRAIN≥50 / VAL≥25 / TEST≥25 and +EV on all three). ALL_83 VAL n makes most 40–49 subsets ineligible for ROBUST.

```text
At 83¢, the best supported observable entry state is:

inning_grp=7&p_max_vs_83=PEAK_AT

Why:
- Selected by the TRAIN+VAL score (TEST locked); TEST is a pass/fail gate only.
- Historically associated with higher HOLD_TO_SETTLEMENT EV than ALL_83 in TRAIN and VAL. Not a causal claim.
- Simpler 1-way start-belief cells (40–49, P_start<50) have higher TRAIN EV but fail VAL≥25 and FDR.
- BH FDR q and game-level bootstrap CI are in the artifacts; +TEST EV is not a confirmed trading edge.

TRAIN:
N = 65
EV = 7.77
WR = 0.908

VAL:
N = 25
EV = 13.00
WR = 0.960

TEST:
N = 48
EV = 2.42
WR = 0.854
Sharpe = 0.068
95% CI = see b1_83_bootstrap.json

Compared with ALL_83:
EV lift = 0.98

Robustness classification:
CANDIDATE
```

Second-best state:
`p_start_lt50=YES&inning_83=LATE_6_7` TRAIN 6.47 VAL 17.00 TEST 2.29 n=171/36/68

Third-best state:
`p_start_ge50=NO&inning_83=LATE_6_7` TRAIN 6.47 VAL 17.00 TEST 2.29 n=171/36/68


## 26. Limitations

TRADE≠fill. VAL≥25 infeasible for most 40–49 subsets. Multiple testing. No fees. No L2. Research score unused in this exhaustive run.

## 27. Reproducibility

```text
./target/release/momento-research-b1 --search-83-exhaustive
# optional: --max-interaction-depth 4 --min-train 50 --min-val 10 --min-test 15 --bootstrap-reps 10000 --permutation-reps 2000
```

## 28. Research-only status

RESEARCH ONLY. No live FIRST01 / 80/81/83/89 / stop / risk / W9 / L2 / orders.
