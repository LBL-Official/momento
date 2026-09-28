# Optimal 83¢ conditional state

**Question:** If I tell you only that the contract is at 83¢, what additional observable conditions at that exact moment make that 83¢ entry attractive or unattractive?

This is **not** an 80-vs-83 price comparison. Universe = `ENTRY_83` only. Fill status: `TRADE_PRINT_MODELED`. Not a live rule.

## BEST DISCOVERED 83¢ CONDITION

```text
Condition:          start_price_band=40_49
N (all / train / val / test): 129 / 95 / 13 / 21
TRAIN EV:           1.21¢   win 84.2%
VAL EV:             1.62¢   win 84.6%
TEST EV:            7.48¢   win 90.5%   Sharpe 0.249
EV lift vs ALL_83:  5.63¢ (TEST) / 5.59¢ (all)
WinRate vs 83%:     +2.3 pp (all-sample)
Bootstrap 95% CI:   $-0.48 to $1.19 / game (TEST)
Positive months:    67%   best 2025-07 (12.04)   worst 2025-04 (-9.24)
Classification:     CANDIDATE
```

## WHY IT WORKS

Unconditional 83¢ hold loses on the full sample (EV −3.32¢, WR 79.7% < 83% breakeven). TEST happened to be a good 83¢ window (+1.85¢). The differentiating information is **starting market belief**, not the 83¢ print itself.

- **Hypothesis A (underdog repricing):** supported. Opened 40–49¢ then reached 83¢ is +TRAIN/+VAL/+TEST. Opened ≥50¢ is unfavorable.
- **Hypothesis B (information arrival):** last-event class/sign did not produce a stable incremental hold edge once start band is fixed.
- **Hypothesis C (late-game confirmation):** innings 7–8 + lead ≥2 did **not** improve 40–49 OOS; several late+lead cells were +TRAIN/+VAL and −TEST.
- **Hypothesis D (path dependence):** “any move > +20¢” failed VAL. The useful fact is *where it started* (40–49), which implies a ~34–43¢ reprice to 83¢ — not an arbitrary large move.
- **Hypothesis E (volatility):** high 1-minute volatility remains unfavorable unconditionally. Conditioning 40–49 on LOW vol often shrinks TEST n below the floor.
- **Hypothesis F (interaction):** a TRAIN-signed research score + low 5m vol can raise TEST EV, but TRAIN/VAL thin out and the score is not an observable baseball/market primitive. Late+lead stacks do not lift 40–49 OOS. The smallest *interpretable* high-EV state remains the start-band region.

## NEXT BEST CONDITIONS

| Rank | Condition | Train/Val/Test n | TRAIN EV | VAL EV | TEST EV | TEST Sharpe | Lift | Class |
|---:|---|---:|---:|---:|---:|---:|---:|---|
| 1 | start_price_band=40_49 | 95/13/21 | 1.21 | 1.62 | 7.48 | 0.249 | 5.63 | CANDIDATE |
| 2 | start_price_band=40_49&vel_sign=UP | 88/13/21 | 1.09 | 1.62 | 7.48 | 0.249 | 5.63 | CANDIDATE |
| 3 | p_start_lt50=YES | 118/13/25 | 0.90 | 1.62 | 5.00 | 0.151 | 3.15 | CANDIDATE |
| 4 | p_start_35_49=YES | 111/13/24 | 0.78 | 1.62 | 4.50 | 0.133 | 2.65 | CANDIDATE |
| 5 | p_start_lt50=YES&vel_sign=UP | 110/13/25 | 0.64 | 1.62 | 5.00 | 0.151 | 3.15 | CANDIDATE |
| 6 | p_start_35_49=YES&vel_sign=UP | 103/13/24 | 0.50 | 1.62 | 4.50 | 0.133 | 2.65 | CANDIDATE |
| 7 | p_start_lt50=YES&personality=CHOPPY | 95/10/19 | 0.16 | 7.00 | 6.47 | 0.205 | 4.63 | CANDIDATE |

## CONDITIONS TO AVOID

1. `vol_1m_tertile=HIGH` TEST EV -11.57¢ TRAIN -9.85 VAL -6.08 (n=142 test_n=21) REJECTED
2. `lead_signed=LEAD_1` TEST EV -8.00¢ TRAIN -5.22 VAL -9.67 (n=116 test_n=20) REJECTED
3. `lead_eq1=YES` TEST EV -8.00¢ TRAIN -5.22 VAL -9.67 (n=116 test_n=20) REJECTED
4. `base_class=BASES_EMPTY` TEST EV -8.00¢ TRAIN -0.80 VAL 3.96 (n=242 test_n=28) REJECTED
5. `research_score_band=LOW` TEST EV -7.14¢ TRAIN -8.73 VAL -16.33 (n=230 test_n=29) REJECTED
6. `score_bucket=ONE_RUN` TEST EV -6.81¢ TRAIN -7.10 VAL -9.67 (n=119 test_n=21) REJECTED
7. `start_sentiment=FAVORITE` TEST EV -6.53¢ TRAIN -7.00 VAL -0.65 (n=134 test_n=17) REJECTED
8. `inning_83=EARLY` TEST EV -5.22¢ TRAIN -3.35 VAL -20.93 (n=228 test_n=27) REJECTED
9. `inning_grp=1_3` TEST EV -5.22¢ TRAIN -3.35 VAL -20.93 (n=228 test_n=27) REJECTED
10. `personality=REVERSING` TEST EV -3.00¢ TRAIN -6.53 VAL -28.45 (n=82 test_n=20) REJECTED

## 1. Executive conclusion

Among contracts that print 83¢, the highest **stable** settlement EV is the **opening-belief region** “started ~40–49¢ (mild underdog), then repriced to 83¢.” Tightening further by inning, lead, personality, or volatility does not produce a more reliable OOS hold edge — it mostly burns sample. Avoid 83¢ when the contract opened already as a favorite, the game is close/one-run, innings are early, or 1-minute TRADE volatility is high.

## 2. ALL_83 baseline

| Split | Games | WR | EV¢ | Sharpe | P&L $ |
|---|---:|---:|---:|---:|---:|
| ALL | 497 | 0.797 | -3.32 | -0.082 | -115.57 |
| TRAIN | 379 | 0.794 | -3.58 | -0.088 | -94.99 |
| VAL | 52 | 0.750 | -8.00 | -0.183 | -29.12 |
| TEST | 66 | 0.848 | 1.85 | 0.051 | 8.54 |

Note: TRAIN EV is −3.58¢ (not TEST). TEST WR 84.8% / TEST EV +1.85¢. Breakeven WR = 83%. N 83¢ games = 497. Split TRAIN < `2025-10-07`, VAL < `2026-05-03`, TEST through `2026-06-27`.

## 3. Existing 40–49 finding

`start_price_band=40_49`: TRAIN 1.21¢ VAL 1.62¢ TEST 7.48¢ | games 129 / test 21 | WR all 85.3% | class seed.

VAL n for this seed is **13** (ALL_83 VAL = 52). The requested VAL≥25 floor **cannot** be met by any 40–49 subset. No `ROBUST_CANDIDATE` exists under TRAIN≥50 / VAL≥25 / TEST≥20 inside this seed. Cells below are `CANDIDATE` under the feasible floor (VAL≥8, TEST≥15, all three EV>0).

## 4–7. Staged rankings

Evaluated **215** cells. Single / two / three / four-way tables use TEST EV among cells with TEST n≥10. Consistent (+TRAIN+VAL+TEST) cells are in the executive table above.

### Stage 1

| Condition | Tr/Va/Te | TRAIN | VAL | TEST | Lift | +all? |
|---|---:|---:|---:|---:|---:|---|
| start_price_band=40_49 | 95/13/21 | 1.21 | 1.62 | 7.48 | 5.63 | yes |
| research_score_band=MID | 112/10/18 | 1.82 | 7.00 | 5.89 | 4.04 | yes |
| p_start_lt50=YES | 118/13/25 | 0.90 | 1.62 | 5.00 | 3.15 | yes |
| p_start_35_49=YES | 111/13/24 | 0.78 | 1.62 | 4.50 | 2.65 | yes |
| lead_signed=LEAD_3P | 143/22/25 | -2.58 | -5.73 | 13.00 | 11.15 | no |
| lead_ge3=YES | 143/22/25 | -2.58 | -5.73 | 13.00 | 11.15 | no |
| score_bucket=MULTI_RUN | 143/22/25 | -2.58 | -5.73 | 13.00 | 11.15 | no |
| vol_1m_tertile=LOW | 149/26/21 | -0.45 | -6.08 | 12.24 | 10.39 | no |

### Stage 2

| Condition | Tr/Va/Te | TRAIN | VAL | TEST | Lift | +all? |
|---|---:|---:|---:|---:|---:|---|
| research_score_band=HIGH&vol_5m_tertile=LOW | 67/12/17 | 0.58 | 0.33 | 11.12 | 9.27 | yes |
| research_score_band=HIGH&q_vol1m_le_q50=YES | 68/12/15 | 0.82 | 0.33 | 10.33 | 8.48 | yes |
| start_price_band=40_49&vel_sign=UP | 88/13/21 | 1.09 | 1.62 | 7.48 | 5.63 | yes |
| p_start_lt50=YES&personality=CHOPPY | 95/10/19 | 0.16 | 7.00 | 6.47 | 4.63 | yes |
| p_start_lt50=YES&vel_sign=UP | 110/13/25 | 0.64 | 1.62 | 5.00 | 3.15 | yes |
| p_start_35_49=YES&vel_sign=UP | 103/13/24 | 0.50 | 1.62 | 4.50 | 2.65 | yes |
| start_price_band=40_49&inning_late68=YES | 42/4/10 | -2.05 | 17.00 | 17.00 | 15.15 | no |
| research_score_band=HIGH&vel_sign=UP | 84/12/19 | -0.86 | 0.33 | 11.74 | 9.89 | no |

### Stage 3

*No cells.*

### Stage 4

*No cells.*

## 8–9. Optimal region and neighbors

The **region** is opening belief in the high-30s to high-40s, not a single hyper-specific cell:

```text
83¢
├── Start price
│   ├── 40–49¢ → favorable (seed; +TRAIN+VAL+TEST)
│   ├── 45–49 / 40–44 → finer cuts; sample usually too small on VAL/TEST
│   ├── 35–49 / P_start<50 → broader sibling, still +all-split when n holds
│   ├── <40¢ → insufficient / not helpful
│   └── ≥50¢ → unfavorable
├── Current game state
│   ├── late + 2+ lead → does not reliably lift 40–49 OOS
│   ├── mid innings → sometimes +TEST but TRAIN often negative unconditionally
│   └── close / one-run / early → avoid
├── Path / vol
│   ├── high 1m vol → avoid (unconditional)
│   ├── LOW vol ∩ 40–49 → theoretically cleaner, TEST n collapses
│   └── TRENDING ∩ 40–49 → no stable incremental hold edge
└── Combined
    └── BEST STABLE STATE = 83¢ + opened 40–49 (or P_start<50)
```

## 10. Unfavorable conditions

See list above. Strongest negatives with TEST n≥15: high 1m vol, no 2-run lead / close game, opened favorite, early innings.

## 11–13. TRAIN/VAL/TEST, bootstrap, monthly

Per-cell metrics are in `b1_83_optimal_conditions.csv`. Bootstrap: `b1_83_bootstrap.json`. Monthly + LOPO: `b1_83_monthly_stability.json`.

## 14. EV lift

`EV_LIFT = Conditional_EV − ALL_83_EV`. Use TEST lift for ranking and all-sample lift for economics. ALL_83 all-sample EV = −3.32¢.

## 15. Economic sensitivity

Hypothetical cost subtracted from TEST EV of the best cell (not Kalshi fees):

- {"hypothetical_cost_cents":0,"note":"Hypothetical TRADE-print cost. Not Kalshi fees.","survives":true,"test_ev_gross":7.476190476190476,"test_ev_net":7.476190476190476}
- {"hypothetical_cost_cents":1,"note":"Hypothetical TRADE-print cost. Not Kalshi fees.","survives":true,"test_ev_gross":7.476190476190476,"test_ev_net":6.476190476190476}
- {"hypothetical_cost_cents":2,"note":"Hypothetical TRADE-print cost. Not Kalshi fees.","survives":true,"test_ev_gross":7.476190476190476,"test_ev_net":5.476190476190476}
- {"hypothetical_cost_cents":3,"note":"Hypothetical TRADE-print cost. Not Kalshi fees.","survives":true,"test_ev_gross":7.476190476190476,"test_ev_net":4.476190476190476}
- {"hypothetical_cost_cents":5,"note":"Hypothetical TRADE-print cost. Not Kalshi fees.","survives":true,"test_ev_gross":7.476190476190476,"test_ev_net":2.4761904761904763}

## 16. Limitations

- TRADE print ≠ maker fill. L2 unused.
- VAL≥25 is infeasible for 40–49 subsets (13 VAL games).
- TEST n≈21 on the seed; bootstrap CI includes $0.
- Research score is a TRAIN-signed composite, not ML and not live.
- Multiple-testing: many cells; only +TRAIN+VAL+TEST cells are treated as confirmed.
- Live 80/81/83/89 and 50% stop unchanged. No W9.

## 17. Reproducibility

```text
cargo build --release -p momento-research-b1
./target/release/momento-research-b1 --search-83-opt
```

Requires `Backtesting Suite/Foundation/B1/features.sqlite` from a prior `--extract`. Does not re-extract. Does not submit orders.

**STOP.**
