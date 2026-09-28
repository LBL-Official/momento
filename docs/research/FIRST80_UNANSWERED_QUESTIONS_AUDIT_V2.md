# FIRST80_UNANSWERED_QUESTIONS_AUDIT_V2

Research only. **LIVE EXECUTION CHANGED: FALSE.**

```text
CANDLE PATH DATA  ≠  ACTUAL EXECUTION
POST-HOC DESCRIPTIVE  ≠  LIVE ENTRY SIGNAL
NO OOS RETUNING
```

**VERDICT: B**

FIRST80 ROBUST, BUT IMPORTANT STRUCTURAL HETEROGENEITY EXISTS. Pre-entry slices and clusters stay near 68–76% and do not reconstruct 73–74% as a narrow entry artifact. Post-entry persistence, resolution speed, and winner MAE are not homogeneous.

## After dissecting observable candle structure, how much confidence in 73–74% as a broad path effect?

Jump-throughs remain ~2% of each universe (V1). This audit asks whether the rest of the path is homogeneous.
NBA baseline 73.9837% (n=1230). NCAAB 73.1398% (n=4099). Gates: PASS.

Persistence: NBA entry-only 63.32% (n=259) vs 16+ 85.51%. NCAAB entry-only 63.32% vs 16+ 86.20%.
Requiring 3 consecutive minutes ≥80 (POST-HOC, not a live signal): NBA 78.34% n=868; NCAAB 77.12% n=2854.
Winners that are CLEAN (MAE<5¢): NBA 43.956% of winners; NCAAB 42.8286%. DEEP_DRAWDOWN_WIN (MAE≥20): NBA 18.5714%; NCAAB 20.6137%.

## Strongest remaining threat to translating the phenomenon into trading P&L

Historical candles still do not observe fills. The binding constraint on translating 73–74% into desk P&L remains **execution**: whether an 80¢ maker (or 81–82¢) actually participates, whether a 40¢ stop/hedge fills, and at what VWAP. Path heterogeneity (drawdowns among eventual winners, immediate reversals) is a second-order candle fact that would still matter even if fills were perfect, because capital and psychology sit on MAE, not on terminal yes/no.

## Reproduction

| Sport | N | Survivors | Stops | Leaks | Survival | Gate |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| NBA | 1230 | 910 | 320 | 0 | 73.9837% | PASS |
| NCAAB | 4099 | 2998 | 1099 | 2 | 73.1398% | PASS |

## What candles can say vs still unobservable

**PROVEN FROM CANDLE DATA**

- Frozen FIRST-80 universes reproduce exactly.
- One-minute jump-throughs are rare and do not carry 73–74% (V1, confirmed as a constraint here: not re-optimized).
- Post-entry persistence, MAE, MFE/barriers, approach class, and entry-price slices are measurable on every event with a candle window.

**SUGGESTED BY CANDLE DATA**

- Persistence after 80 is associated with different terminal rates (see surface; POST-HOC).
- Eventual winners are not uniformly clean: MAE buckets and winner classes quantify turbulence.
- Entry-time logistic/tree models have limited AUC; 73–74% is not a sharp pre-entry separable mixture.

**STILL UNOBSERVABLE**

- L2 / queue / maker fill at 80, 81, 82
- Opponent hedge fill at 20/28/40
- Liquidation VWAP
- Official game clock and PBP
- Fees, mid, live latency

## Q1 Persistence

| Require consec ≥80 (min) | NBA N | NBA survival | NCAAB N | NCAAB survival |
| ---: | ---: | ---: | ---: | ---: |
| 0 | 1230 | 73.98% | 4099 | 73.14% |
| 1 | 1230 | 73.98% | 4099 | 73.14% |
| 2 | 971 | 76.83% | 3232 | 75.77% |
| 3 | 868 | 78.34% | 2854 | 77.12% |
| 5 | 712 | 78.79% | 2381 | 79.21% |
| 10 | 526 | 82.70% | 1805 | 83.71% |

Consecutive buckets:

| Bucket | NBA N | NBA survival | NCAAB N | NCAAB survival |
| --- | ---: | ---: | ---: | ---: |
| 1 (entry only) | 259 | 63.32% | 867 | 63.32% |
| 2 | 103 | 64.08% | 378 | 65.61% |
| 3–5 | 210 | 75.24% | 620 | 64.84% |
| 6–15 | 230 | 67.83% | 720 | 68.61% |
| 16+ | 428 | 85.51% | 1514 | 86.20% |

## Q2 MAE

| MAE ¢ | NBA N | NBA survival | NBA median MAE | NCAAB N | NCAAB survival |
| --- | ---: | ---: | ---: | ---: | ---: |
| 0–2 | 124 | 100.00% | 1.0 | 377 | 99.73% |
| 2–5 | 150 | 100.00% | 3.0 | 439 | 100.00% |
| 5–10 | 139 | 100.00% | 7.0 | 492 | 100.00% |
| 10–20 | 202 | 100.00% | 14.0 | 604 | 100.00% |
| 20–40 | 165 | 100.00% | 28.0 | 596 | 100.00% |
| 40–201 | 324 | 1.23% | 80.0 | 1122 | 1.96% |

MAE ≥40¢ is **almost the close-40 stop definition** for entries near 80 (entry 80 − 40 = 40). 100% survival in MAE 0–40 is therefore largely tautological. The non-tautological winner fact is median MAE among survivors = 6¢, and ~19–21% of winners have MAE ≥20¢ without printing a close-40.

## Q3 MFE / barriers (FULL, candle close)

NBA P(90 before 40)=83.0081% n=1230. P(95 before 40)=77.1545%. P(99 before 40)=74.2276%.
NCAAB P(90 before 40)=82.2152% n=4099. P(95 before 40)=76.604%. P(99 before 40)=73.1154%.

## Q8 Approach class (a priori rules, not P&L-fit)

| Class | NBA N | NBA survival | NCAAB N | NCAAB survival |
| --- | ---: | ---: | ---: | ---: |
| STEADY_RISE | 2 | 100.00% | 8 | 100.00% |
| RECOVERY | 223 | 70.40% | 741 | 73.28% |
| BREAKOUT | 246 | 75.61% | 684 | 71.49% |
| SIDEWAYS_THEN_BREAK | 316 | 70.25% | 784 | 70.03% |
| VOLATILE_APPROACH | 327 | 77.06% | 1330 | 74.14% |
| SHOCK_REPRICE | 38 | 86.84% | 221 | 78.28% |
| UNCLASSIFIED | 78 | 74.36% | 331 | 75.53% |

## Q11 Entry price

| Close | NBA N | NBA survival | NCAAB N | NCAAB survival |
| --- | ---: | ---: | ---: | ---: |
| 80–81 | 531 | 72.13% | 1523 | 68.16% |
| 81–82 | 231 | 71.43% | 829 | 72.62% |
| 82–83 | 170 | 75.29% | 566 | 75.80% |
| 83–85 | 172 | 74.42% | 708 | 75.00% |
| 85–87 | 75 | 81.33% | 269 | 79.93% |
| 87–90 | 32 | 81.25% | 125 | 88.80% |
| 90+ | 19 | 100.00% | 79 | 91.14% |

## Q16 Winner anatomy (share of winners)

| Class | NBA share | NBA n | NCAAB share | NCAAB n |
| --- | ---: | ---: | ---: | ---: |
| CLEAN_WIN | 43.956% | 400 | 42.8286% | 1284 |
| DRAWDOWN_WIN | 37.4725% | 341 | 36.5243% | 1095 |
| DEEP_DRAWDOWN_WIN | 18.5714% | 169 | 20.6137% | 618 |
| OPPONENT_HEDGE_WIN | 0.0% | 0 | 0.0334% | 1 |

## Q10 / Q13 Pre-entry models (TRAIN fit, VAL then OOS once)

NBA logistic eval: [{'split': 'TRAIN', 'n': 490, 'logistic_auc': 0.6019, 'tree_acc': 0.7163, 'base_rate': 0.7163, 'flag': None}, {'split': 'VALIDATION', 'n': 463, 'logistic_auc': 0.5344, 'tree_acc': 0.7538, 'base_rate': 0.7538, 'flag': None}, {'split': 'OOS', 'n': 231, 'logistic_auc': 0.5099, 'tree_acc': 0.7576, 'base_rate': 0.7576, 'flag': None}].
NCAAB logistic eval: [{'split': 'TRAIN', 'n': 928, 'logistic_auc': 0.5635, 'tree_acc': 0.7554, 'base_rate': 0.7554, 'flag': None}, {'split': 'VALIDATION', 'n': 2977, 'logistic_auc': 0.5562, 'tree_acc': 0.7256, 'base_rate': 0.7256, 'flag': None}, {'split': 'OOS', 'n': 81, 'logistic_auc': 0.4954, 'tree_acc': 0.7901, 'base_rate': 0.7901, 'flag': 'NCAAB_OOS_SMALL'}].
NCAAB OOS n≈84 is N_TOO_SMALL for stability claims.
VALIDATION AUC 0.53–0.56. OOS AUC ≈0.50–0.51. Tree accuracy equals the majority base rate. Pre-entry candles do not split FIRST80 into a sharp strong/weak mixture. That is evidence for a **broad path effect at T0**, not a narrow artifact.

## Q4 Immediate aftermath (event study, POST-HOC)

Mean yes_bid_close at T0 / T+5 / T+15:
- NBA survivors: 81.7769 → 83.0167 → 85.0708
- NBA stops: 81.3 → 78.8438 → 71.817
- NCAAB survivors: 82.0767 → 83.7017 → 85.7738
- NCAAB stops: 81.4158 → 78.1968 → 71.7027

T0 prices overlap. Divergence is after T0. Not a live entry signal.

## Q6 Volatility quintiles (pre-15m range, TRAIN edges)

| Q | NBA N | NBA survival | NCAAB N | NCAAB survival |
| --- | ---: | ---: | ---: | ---: |
| Q1 | 278 | 69.06% | 988 | 69.84% |
| Q2 | 247 | 74.90% | 772 | 72.80% |
| Q3 | 266 | 74.44% | 705 | 74.61% |
| Q4 | 221 | 74.21% | 805 | 74.78% |
| Q5 | 218 | 78.44% | 829 | 74.55% |

Calm (Q1) is slightly lower (~69%) than volatile Q5 (~75–78%). Difference is a few points, not a regime collapse.

## Q9 Time to resolution (POST-ENTRY)

| Minutes | NBA N | NBA survival | NCAAB N | NCAAB survival |
| --- | ---: | ---: | ---: | ---: |
| 0–15 | 36 | 33.33% | 96 | 3.12% |
| 15–30 | 96 | 48.96% | 242 | 19.83% |
| 30–60 | 288 | 67.36% | 748 | 54.14% |
| 60–120 | 467 | 73.66% | 1640 | 74.21% |
| 120–240 | 303 | 91.09% | 1296 | 97.61% |
| 240–10000 | 40 | 92.50% | 76 | 78.95% |

Fast resolution is enriched for stops (NCAAB 0–15m survival 3.13%, n=96 SMALL_SAMPLE; 15–30m 19.83%, n=242). Paths still open at 120–240m survive 91% NBA / 97.6% NCAAB. Capital is exposed a median ~86–95 minutes.

## Q12 Capital minutes (DESCRIPTIVE, not a portfolio backtest)

NBA median ¢/contract-minute 0.164013 (winners 0.202208, stops -0.689655).
NCAAB median 0.150244 (winners 0.175824, stops -0.769231).

## Q15 Loser vs winner anatomy at entry vs after

| Feature | NBA winners median | NBA stops median | NCAAB winners median | NCAAB stops median | When |
| --- | ---: | ---: | ---: | ---: | --- |
| jump_1m | 4.0 | 4.0 | 5.0 | 4.0 | AVAILABLE_AT_ENTRY |
| entry close | 81.0 | 81.0 | 81.0 | 81.0 | AVAILABLE_AT_ENTRY |
| pre15 range | 14.0 | 13.0 | 16.0 | 15.0 | AVAILABLE_AT_ENTRY |
| consec ≥80 | 8.0 | 4.0 | 10.0 | 4.0 | POST_ENTRY |
| MAE | 6.0 | 80.0 | 6.0 | 80.0 | POST_ENTRY |

At T0, losers are not a distinct jump or volatility population. After T0 they recross and go to 40 (median MAE 80¢ because the stop is 40 and many go to ~0).

## Q17 Hedge path structure (close-opportunity, NOT a fill)

H=40 close-opportunity: NBA 456/1230; NCAAB 1546/4099. Favorite-lost (economically ‘true’ hedge if filled): NBA 211; NCAAB 704. Favorite-won (‘false’ hedge): NBA 245; NCAAB 842. Pre-entry jump medians of winners vs stops are the same (~4–5¢), so true vs false hedges are not separated by arrival jump. Exploratory only.

## Q14 Season (existing EARLY/MIDDLE/LATE regime on frozen candidates)

| Regime | NBA N | NBA survival | NBA % jump≥20 | NCAAB N | NCAAB survival | NCAAB flag |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| EARLY | 504 | 71.83% | 2.1825 | 958 | 75.26% | None |
| MIDDLE | 579 | 75.47% | 1.209 | 3131 | 72.47% | None |
| LATE | 147 | 75.51% | 2.7211 | 10 | 80.00% | N_TOO_SMALL |

## Remaining unknowns that require a real order

- L2 / queue / actual 80¢ maker fill
- Actual hedge fill at H=20/28/40
- Liquidation VWAP vs candle 40-stop
- Official game clock and PBP at jump-throughs
- Live latency and fees

LIVE EXECUTION CHANGED: FALSE

