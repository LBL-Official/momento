# Exhaustive Conditional 83¢ Research

## 1. Executive answer

VAL-selected primary (TEST locked): **`lead_ge2=YES&personality=CHOPPY`** class `CANDIDATE`.

TRAIN n=201 EV=0.08¢ WR=83.1% · VAL n=27 EV=2.19¢ WR=85.2% · TEST n=31 EV=7.32¢ WR=90.3% Sharpe=0.244

**NO ROBUST OPTIMAL STATE FOUND** under TRAIN≥50 / VAL≥25 / TEST≥25. The primary is the strongest VAL-selected simple state that stayed +TEST.

## 2. Universe and methodology

- Universe: `entry_trade_price_cents=83` only. N snapshots/games = 497/497.
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
| 1-way | 140 | 5.7% |
| 2-way | 2318 | 94.2% |
| 3-way | 4 | 0.2% |
| 4-way | 0 | 0.0% |
| 5-way | 0 | 0.0% |
| Stored | 2462 | |
| TRAIN+ | 544 | |
| TRAIN+VAL+ | 65 | |
| TEST evaluated | 2462 | |

## 6. ALL_83 baseline

| Split | Games | WR | EV¢ | Sharpe | P&L $ |
|---|---:|---:|---:|---:|---:|
| ALL | 497 | 0.797 | -3.32 | -0.082 | -115.57 |
| TRAIN | 379 | 0.794 | -3.58 | -0.088 | -94.99 |
| VAL | 52 | 0.750 | -8.00 | -0.183 | -29.12 |
| TEST | 66 | 0.848 | 1.85 | 0.051 | 8.54 |

## 7. Best single-feature states

- sel=8.32 `p_start_fine=45_49` TRAIN 3.54 VAL 2.71 TEST 2.71 n=52/7/14 class=EXPLORATORY
- sel=8.32 `p_start_45_49=YES` TRAIN 3.54 VAL 2.71 TEST 2.71 n=52/7/14 class=EXPLORATORY
- sel=6.33 `inning_83=LATE_6_7` TRAIN 2.33 VAL 17.00 TEST -1.18 n=75/3/11 class=REJECTED
- sel=5.56 `p_start_35_49=YES` TRAIN 0.78 VAL 1.62 TEST 4.50 n=111/13/24 class=CANDIDATE_THIN_VALIDATION
- sel=5.44 `p_start_lt50=YES` TRAIN 0.90 VAL 1.62 TEST 5.00 n=118/13/25 class=CANDIDATE_THIN_VALIDATION
- sel=5.44 `p_start_ge50=NO` TRAIN 0.90 VAL 1.62 TEST 5.00 n=118/13/25 class=CANDIDATE_THIN_VALIDATION
- sel=5.38 `start_price_band=40_49` TRAIN 1.21 VAL 1.62 TEST 7.48 n=95/13/21 class=CANDIDATE_THIN_VALIDATION
- sel=3.99 `base_class=BASES_EMPTY` TRAIN -0.80 VAL 3.96 TEST -8.00 n=191/23/28 class=REJECTED

## 8. Best 2-way states

- sel=9.23 `p_start_tertile=LOW&half=BOTTOM` TRAIN 7.57 VAL 4.50 TEST 4.50 n=53/8/8 class=REJECTED
- sel=9.16 `p_start_lt50=YES&half=BOTTOM` TRAIN 7.00 VAL 4.50 TEST -3.00 n=50/8/5 class=REJECTED
- sel=9.16 `p_start_ge50=NO&half=BOTTOM` TRAIN 7.00 VAL 4.50 TEST -3.00 n=50/8/5 class=REJECTED
- sel=9.05 `base_class=BASES_EMPTY&vol_15m_tertile=LOW` TRAIN 4.50 VAL 3.96 TEST -8.93 n=104/23/27 class=REJECTED
- sel=9.02 `vel_1m_tertile=MID&last_event_sign=UP` TRAIN 4.80 VAL 5.89 TEST 17.00 n=82/9/7 class=REJECTED
- sel=8.95 `base_class=BASES_EMPTY&vol_5m_tertile=LOW` TRAIN 1.62 VAL 7.00 TEST -4.05 n=104/20/19 class=REJECTED
- sel=8.91 `base_class=BASES_EMPTY&reversal_tertile=HIGH` TRAIN 3.67 VAL 3.96 TEST -8.00 n=60/23/28 class=REJECTED
- sel=8.87 `lead_ge2=YES&personality=CHOPPY` TRAIN 0.08 VAL 2.19 TEST 7.32 n=201/27/31 class=CANDIDATE

## 9. Best 3-way states

- sel=6.58 `last_delta_band=2_5&vol_15m_tertile=LOW&vol_1m_tertile=LOW` TRAIN 6.09 VAL 17.00 TEST 17.00 n=55/6/1 class=REJECTED
- sel=-0.51 `p_start_lt50=YES&base_class=BASES_EMPTY&start_move_tertile=HIGH` TRAIN 6.47 VAL -3.00 TEST 7.91 n=57/5/11 class=EXPLORATORY
- sel=-4.09 `p_start_lt50=YES&vol_15m_tertile=LOW&start_move_tertile=HIGH` TRAIN 1.29 VAL -3.00 TEST 7.48 n=70/10/21 class=EXPLORATORY
- sel=-8.18 `start_price_band=40_49&vol_15m_tertile=LOW&start_move_tertile=HIGH` TRAIN -0.54 VAL -3.00 TEST 11.12 n=57/10/17 class=OVERFIT

## 10. Best 4-way states

No 4-way cell met TRAIN n≥40 after family/support pruning.

## 11. Raw TEST winners (OVERFIT RISK)

- `start_price_band=70_79` TRAIN -2.05 VAL -83.00 TEST 17.00 n=21/1/1
- `p_start_fine=40_44` TRAIN -1.60 VAL 0.33 TEST 17.00 n=43/6/7
- `p_start_fine=70_79` TRAIN -2.05 VAL -83.00 TEST 17.00 n=21/1/1
- `p_start_40_44=YES` TRAIN -1.60 VAL 0.33 TEST 17.00 n=43/6/7
- `p_start_70p=YES` TRAIN -3.83 VAL -83.00 TEST 17.00 n=24/1/1
- `inning_83=LATE_8` TRAIN -7.24 VAL 4.50 TEST 17.00 n=33/8/4
- `inning_grp=8` TRAIN -7.24 VAL 4.50 TEST 17.00 n=33/8/4
- `base_class=LOADED` TRAIN -0.65 VAL -16.33 TEST 17.00 n=17/3/4

Do not treat these as trading candidates.

## 12. Validation-selected winners

- sel=9.05 `base_class=BASES_EMPTY&vol_15m_tertile=LOW` TRAIN 4.50 VAL 3.96 TEST -8.93 n=104/23/27
- sel=8.95 `base_class=BASES_EMPTY&vol_5m_tertile=LOW` TRAIN 1.62 VAL 7.00 TEST -4.05 n=104/20/19
- sel=8.91 `base_class=BASES_EMPTY&reversal_tertile=HIGH` TRAIN 3.67 VAL 3.96 TEST -8.00 n=60/23/28
- sel=8.87 `lead_ge2=YES&personality=CHOPPY` TRAIN 0.08 VAL 2.19 TEST 7.32 n=201/27/31
- sel=8.50 `base_class=BASES_EMPTY&start_move_gt20=YES` TRAIN 0.22 VAL 7.00 TEST -9.09 n=143/20/23
- sel=7.82 `base_class=BASES_EMPTY&vel_sign=UP` TRAIN 0.54 VAL 3.96 TEST -8.00 n=164/23/28
- sel=7.76 `base_class=BASES_EMPTY&vel_5m_sign=UP` TRAIN 0.70 VAL 3.96 TEST -8.00 n=184/23/28
- sel=7.38 `p_start_50_54=NO&base_class=BASES_EMPTY` TRAIN 0.73 VAL 2.00 TEST -8.00 n=166/20/24
- sel=7.20 `move_fine=25_30&vel_5m_sign=UP` TRAIN 0.53 VAL 1.21 TEST 2.71 n=85/19/14
- sel=7.16 `half=TOP&vol_15m_tertile=LOW` TRAIN 0.81 VAL 1.21 TEST 2.71 n=105/19/35

## 13. Robust winners

ROBUST count (n gates + +EV on all three + BH FDR q≤0.10): 0. ALL_83 VAL n=52; few subsets can hit VAL≥25. FDR typically keeps 0–1 cells, so ROBUST is expected to be empty.

## 14. Best negative states

- `p_start_35_49=NO&base_class=RISP` TRAIN -7.42 VAL -33.00 TEST 7.00 n=86/10/20
- `p_start_lt50=NO&base_class=RISP` TRAIN -7.10 VAL -33.00 TEST 6.47 n=83/10/19
- `p_start_ge50=YES&base_class=RISP` TRAIN -7.10 VAL -33.00 TEST 6.47 n=83/10/19
- `p_start_40_50=NO&vel_1m_tertile=HIGH` TRAIN -13.00 VAL -25.86 TEST -3.00 n=80/14/20
- `p_start_lt50=NO&vel_1m_tertile=HIGH` TRAIN -12.87 VAL -25.86 TEST -2.05 n=77/14/21
- `p_start_ge50=YES&vel_1m_tertile=HIGH` TRAIN -12.87 VAL -25.86 TEST -2.05 n=77/14/21
- `p_start_35_49=NO&vel_1m_tertile=HIGH` TRAIN -12.49 VAL -25.86 TEST -2.05 n=78/14/21
- `base_class=RISP&p_max_vs_83=PEAK_AT` TRAIN -7.36 VAL -28.45 TEST 7.91 n=78/11/11

## 15. Starting-price analysis

Predeclared bands (TRAIN-defined / overlapping regions declared before TEST). H1: is the edge localized in 40–49 or a broader underdog-repricing effect?

- `start_price_band=40_49` TRAIN 1.21 VAL 1.62 TEST 7.48 n=95/13/21
- `p_start_lt50=YES` TRAIN 0.90 VAL 1.62 TEST 5.00 n=118/13/25
- `p_start_ge50=YES` TRAIN -5.61 VAL -11.21 TEST -0.07 n=261/39/41
- `p_start_35_39=YES` TRAIN -1.75 VAL NaN TEST -16.33 n=16/0/3
- `p_start_35_49=YES` TRAIN 0.78 VAL 1.62 TEST 4.50 n=111/13/24
- `p_start_40_44=YES` TRAIN -1.60 VAL 0.33 TEST 17.00 n=43/6/7
- `p_start_45_49=YES` TRAIN 3.54 VAL 2.71 TEST 2.71 n=52/7/14
- `p_start_40_54=YES` TRAIN -2.75 VAL -6.08 TEST 4.88 n=157/26/33
- `p_start_50_54=YES` TRAIN -8.81 VAL -13.77 TEST 0.33 n=62/13/12
- `p_start_55_59=YES` TRAIN -7.71 VAL -4.43 TEST -3.00 n=85/14/15
- `p_start_60_69=YES` TRAIN -1.89 VAL -10.27 TEST 1.62 n=90/11/13
- `p_start_70p=YES` TRAIN -3.83 VAL -83.00 TEST 17.00 n=24/1/1
- `p_start_fine=40_44` TRAIN -1.60 VAL 0.33 TEST 17.00 n=43/6/7
- `p_start_fine=45_49` TRAIN 3.54 VAL 2.71 TEST 2.71 n=52/7/14
- `p_start_tertile=LOW` TRAIN 0.59 VAL -3.00 TEST 3.67 n=128/15/30
- `p_start_tertile=MID` TRAIN -8.55 VAL -7.00 TEST -1.18 n=137/25/22
- `p_start_tertile=HIGH` TRAIN -2.30 VAL -16.33 TEST 2.71 n=114/12/14
- `start_sentiment=UNDERDOG` TRAIN -3.69 VAL 5.89 TEST 9.31 n=58/9/13
- `start_sentiment=FAVORITE` TRAIN -7.00 VAL -0.65 TEST -6.53 n=100/17/17

## 16. Incremental-information analysis

- {"condition":"ALL_83","layer":"ALL_83","n":497,"test_ev":1.8484848484848484,"train_ev":-3.5804749340369395,"val_ev":-8.0}
- {"condition":"p_start_lt50=YES","layer":"START_BELIEF","n":156,"test_ev":5.0,"train_ev":0.8983050847457628,"val_ev":1.6153846153846154}
- {"condition":"start_price_band=40_49","layer":"START_40_49","n":129,"test_ev":7.476190476190476,"train_ev":1.2105263157894737,"val_ev":1.6153846153846154}
- {"condition":"p_start_lt50=YES&lead_ge2=YES","ev_lift_vs_all83_test":-0.6379585326953747,"layer":"START+LEAD","n":122,"test_ev":1.2105263157894737,"test_n":19,"train_ev":1.946236559139785,"train_n":93,"val_ev":-3.0,"val_n":10}
- {"condition":"start_price_band=40_49&lead_ge2=YES","ev_lift_vs_all83_test":1.8181818181818181,"layer":"START_40_49+LEAD","n":102,"test_ev":3.6666666666666665,"test_n":15,"train_ev":2.7142857142857144,"train_n":77,"val_ev":-3.0,"val_n":10}
- {"condition":"start_price_band=40_49&inning_late68=YES","ev_lift_vs_all83_test":15.151515151515152,"layer":"START_40_49+INNING","n":56,"test_ev":17.0,"test_n":10,"train_ev":-2.0476190476190474,"train_n":42,"val_ev":17.0,"val_n":4}
- {"condition":"start_price_band=40_49&start_move_gt20=YES","ev_lift_vs_all83_test":5.627705627705628,"layer":"START_40_49+PATH","n":126,"test_ev":7.476190476190476,"test_n":21,"train_ev":0.8709677419354839,"train_n":93,"val_ev":0.3333333333333333,"val_n":12}
- {"condition":"start_price_band=40_49&vol_1m_tertile=LOW","ev_lift_vs_all83_test":15.151515151515152,"layer":"START_40_49+VOL","n":32,"test_ev":17.0,"test_n":2,"train_ev":-3.0,"train_n":25,"val_ev":-3.0,"val_n":5}
- {"condition":"start_price_band=40_49&vel_sign=UP","ev_lift_vs_all83_test":5.627705627705628,"layer":"START_40_49+VEL","n":122,"test_ev":7.476190476190476,"test_n":21,"train_ev":1.0909090909090908,"train_n":88,"val_ev":1.6153846153846154,"val_n":13}

## 17. Bootstrap

Game-level, n=10000, seed=42, on TEST of VAL finalists. See `b1_83_bootstrap.json`.

## 18. Permutation/placebo test

Shuffle game P&L, keep condition size. See `b1_83_permutation_test.json`.

## 19. Multiple-testing analysis

BH FDR q=0.10 on TRAIN P(mean P&L≤0). Tested 2462. Reject 1. Uncorrected TEST EV is not an edge.

## 20. Monthly stability

See `b1_83_monthly_stability.json`.

## 21. Economic sensitivity

- {"hypothetical_cost_cents":0,"note":"Hypothetical TRADE-print cost. Not Kalshi fees.","survives":true,"test_ev_gross":7.32258064516129,"test_ev_net":7.32258064516129}
- {"hypothetical_cost_cents":1,"note":"Hypothetical TRADE-print cost. Not Kalshi fees.","survives":true,"test_ev_gross":7.32258064516129,"test_ev_net":6.32258064516129}
- {"hypothetical_cost_cents":2,"note":"Hypothetical TRADE-print cost. Not Kalshi fees.","survives":true,"test_ev_gross":7.32258064516129,"test_ev_net":5.32258064516129}
- {"hypothetical_cost_cents":3,"note":"Hypothetical TRADE-print cost. Not Kalshi fees.","survives":true,"test_ev_gross":7.32258064516129,"test_ev_net":4.32258064516129}
- {"hypothetical_cost_cents":5,"note":"Hypothetical TRADE-print cost. Not Kalshi fees.","survives":true,"test_ev_gross":7.32258064516129,"test_ev_net":2.32258064516129}

## 22. 40–49 benchmark comparison

Benchmark (not a seed): `start_price_band=40_49` TRAIN 1.21 VAL 1.62 TEST 7.48 n=95/13/21.

- Did any VAL-selected condition beat 40–49 on both TRAIN and VAL EV? **yes**
  - `base_class=BASES_EMPTY&vol_15m_tertile=LOW` TRAIN 4.50 VAL 3.96 TEST -8.93 n=104/23/27
  - `base_class=BASES_EMPTY&vol_5m_tertile=LOW` TRAIN 1.62 VAL 7.00 TEST -4.05 n=104/20/19
  - `base_class=BASES_EMPTY&reversal_tertile=HIGH` TRAIN 3.67 VAL 3.96 TEST -8.00 n=60/23/28
  - `vel_1m_tertile=LOW&accel_sign=POS` TRAIN 2.94 VAL 9.31 TEST -3.00 n=64/13/5
  - `base_class=BASES_EMPTY&p_max_vs_83=PEAK_AT` TRAIN 2.05 VAL 9.31 TEST -11.57 n=107/13/14
- Did any simple VAL-supported state beat 40–49 on locked TEST without being a raw-TEST winner? **yes**
- Incremental add-ons to 40–49 are in §16 / `b1_83_incremental_information.json` (baseball, path, velocity, volatility).
- Is 40–49 still the simplest VAL-selected primary? **no — see §1 / §25**

## 23. What information actually matters

Ranked by how often the group appears in VAL-selected +TRAIN+VAL cells (TEST shown after freeze, not used to choose the group):

1. `BASEBALL_STATE` (18 hits among VAL finalists)
2. `VELOCITY` (8 hits among VAL finalists)
3. `PATH` (7 hits among VAL finalists)
4. `VOLATILITY` (7 hits among VAL finalists)
5. `EVENT_RESPONSE` (3 hits among VAL finalists)

## 24. What information does not help

Groups / patterns that did not produce a VAL-stable lift over the start-belief 1-ways, or that fail TRAIN+VAL:

1. Higher-order (3–4 way) cells: extra predicates shrink VAL n below the ROBUST gate without a pre-TEST score advantage.
2. Repricing magnitude (`start_move_*`) without start location: H2 — move size is largely a restatement of P_start when entry is fixed at 83¢.
3. Last-event class / last-delta as a stand-alone hold filter (H event-response): no VAL-stable incremental edge after start belief.

## 25. Final optimal conditional state

**NO ROBUST OPTIMAL STATE FOUND** (ROBUST requires TRAIN≥50 / VAL≥25 / TEST≥25 and +EV on all three). ALL_83 VAL n makes most 40–49 subsets ineligible for ROBUST.

```text
At 83¢, the best supported observable entry state is:

lead_ge2=YES&personality=CHOPPY

Why:
- Selected by the TRAIN+VAL score (TEST locked); TEST is a pass/fail gate only.
- Historically associated with higher HOLD_TO_SETTLEMENT EV than ALL_83 in TRAIN and VAL. Not a causal claim.
- Simpler 1-way start-belief cells (40–49, P_start<50) have higher TRAIN EV but fail VAL≥25 and FDR.
- BH FDR q and game-level bootstrap CI are in the artifacts; +TEST EV is not a confirmed trading edge.

TRAIN:
N = 201
EV = 0.08
WR = 0.831

VAL:
N = 27
EV = 2.19
WR = 0.852

TEST:
N = 31
EV = 7.32
WR = 0.903
Sharpe = 0.244
95% CI = see b1_83_bootstrap.json

Compared with ALL_83:
EV lift = 5.47

Robustness classification:
CANDIDATE
```

Second-best state:
`half=TOP&vol_15m_tertile=LOW` TRAIN 0.81 VAL 1.21 TEST 2.71 n=105/19/35

Third-best state:
`lead_ge2=YES&vol_1m_tertile=LOW` TRAIN 0.33 VAL 1.21 TEST 11.74 n=108/19/19


## 26. Limitations

TRADE≠fill. VAL≥25 infeasible for most 40–49 subsets. Multiple testing. No fees. No L2. Research score unused in this exhaustive run.

## 27. Reproducibility

```text
./target/release/momento-research-b1 --search-83-exhaustive
# optional: --max-interaction-depth 4 --min-train 50 --min-val 10 --min-test 15 --bootstrap-reps 10000 --permutation-reps 2000
```

## 28. Research-only status

RESEARCH ONLY. No live FIRST01 / 80/81/83/89 / stop / risk / W9 / L2 / orders.
