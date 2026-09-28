# FIRST80_REALISTIC_EXIT_FEE_AUDIT_V1

```text
VERDICT: B

LIVE EXECUTION CHANGED: FALSE

CANDLE PATH ≠ ACTUAL FILL
STOP TRIGGER ≠ REALIZED EXIT
GROSS EV ≠ NET EV
```

Read-only measurement experiment. Does not arm trading. Does not modify FIRST01, Risk, Execution, Game Path, or hedge V1–V4.

```text
FEE MODEL STATUS: ESTIMATED
OBSERVED_PRODUCTION_MODEL: UNAVAILABLE
SETTLEMENT_FEE = 0
```

## 0. Reproduction gates

### NBA

- `BASELINE_NBA_PATH_GATE` = **PASS**
- `BASELINE_NBA_STOP_MODEL_GATE` = **PASS**
- Frozen universe: 910 / 1230 = 73.9837% path survival
- Stops: 320 · leaks: 0
- Stop rescan mismatches: 0 · missing candles: 0

### NCAAB

- `BASELINE_NCAAB_PATH_GATE` = **PASS**
- `BASELINE_NCAAB_STOP_MODEL_GATE` = **PASS**
- Frozen universe: 2998 / 4099 = 73.1398% path survival
- Stops: 1099 · leaks: 2
- Stop rescan mismatches: 0 · missing candles: 0

## 1. Fee architecture (parameterized)

Copied locally. Existing `fee_models.py` was not modified.

```text
fee = ceil_6dp(M × coef × C × P × (1 − P))
M = 1  (KXNBAGAME / KXNCAAMBGAME demo API, 2026-09-03)
SETTLEMENT_FEE = 0
```

| Scenario | Entry @80 | Exit (taker @ proxy) | Hedge (maker @ H) |
| --- | --- | --- | --- |
| CURRENT | $0 (quadratic, no maker fees) | taker 0.07 | $0 |
| MODERATE | maker 0.0175 = 0.2800¢ | taker 0.07 | maker 0.0175 |
| CONSERVATIVE | taker 0.07 = 1.1200¢ | taker 0.07 | maker 0.0175 |

### Taker exit fee grid (1 contract, M=1)

| Exit | Taker fee | Gross P&L (vs 80) | Net CURRENT | Net MODERATE | Net CONSERVATIVE |
| --- | --- | --- | --- | --- | --- |
| 40¢ | 1.6801¢ | -40.0¢ | -41.6801¢ | -41.9601¢ | -42.8001¢ |
| 35¢ | 1.5925¢ | -45.0¢ | -46.5925¢ | -46.8725¢ | -47.7125¢ |
| 30¢ | 1.4700¢ | -50.0¢ | -51.4700¢ | -51.7500¢ | -52.5900¢ |
| 25¢ | 1.3125¢ | -55.0¢ | -56.3125¢ | -56.5925¢ | -57.4325¢ |
| 20¢ | 1.1200¢ | -60.0¢ | -61.1200¢ | -61.4000¢ | -62.2400¢ |
| 15¢ | 0.8925¢ | -65.0¢ | -65.8925¢ | -66.1725¢ | -67.0125¢ |
| 10¢ | 0.6300¢ | -70.0¢ | -70.6300¢ | -70.9100¢ | -71.7500¢ |
| 5¢ | 0.3325¢ | -75.0¢ | -75.3325¢ | -75.6125¢ | -76.4525¢ |

Win-to-settlement: `PNL_NET_WIN = 20¢ − ENTRY_FEE − SETTLEMENT_FEE(0)`.

## 2. NBA — empirical exit distribution

### Threshold trigger distribution (close ≤ T)

| Exit / trigger | Count | P(trigger) |
| --- | --- | --- |
| 40¢ | 320 | 26.02% |
| 35¢ | 297 | 24.15% |
| 30¢ | 281 | 22.85% |
| 25¢ | 266 | 21.63% |
| 20¢ | 250 | 20.33% |
| 15¢ | 243 | 19.76% |
| 10¢ | 231 | 18.78% |
| 5¢ | 228 | 18.54% |

### Realized exit-price proxy (Model B: trigger-candle bid close)

Not the same object as the trigger distribution.

| Region | Count | % of FIRST-80 | % of triggered |
| --- | --- | --- | --- |
| 40-37 | 164 | 13.33% | 51.25% |
| 36-32 | 81 | 6.59% | 25.31% |
| 31-27 | 39 | 3.17% | 12.19% |
| 26-22 | 14 | 1.14% | 4.38% |
| 21-17 | 10 | 0.81% | 3.12% |
| 16-12 | 3 | 0.24% | 0.94% |
| 11-7 | 5 | 0.41% | 1.56% |
| 6-0 | 4 | 0.33% | 1.25% |
| No deterioration exit | 910 | 73.98% | — |

### Conservative wick proxy (Model C: trigger-candle bid low)

| Region | Count | % of FIRST-80 | % of triggered |
| --- | --- | --- | --- |
| 40-37 | 102 | 8.29% | 31.88% |
| 36-32 | 86 | 6.99% | 26.88% |
| 31-27 | 46 | 3.74% | 14.38% |
| 26-22 | 40 | 3.25% | 12.50% |
| 21-17 | 19 | 1.54% | 5.94% |
| 16-12 | 10 | 0.81% | 3.12% |
| 11-7 | 3 | 0.24% | 0.94% |
| 6-0 | 14 | 1.14% | 4.38% |
| No deterioration exit | 910 | 73.98% | — |

## 3. NBA — jump-through

Gaps are `previous_tradable_close − trigger_close`. Candle proxy, not L2.

| Stat | Close gap (¢) | Low gap (¢) |
| --- | --- | --- |
| n | 320 | 320 |
| median | 12.0000 | 16.0000 |
| p75 | 19.0000 | — |
| p90 | 30.0000 | 36.1000 |
| p95 | 37.0000 | — |
| worst | 93.0000 | 93.0000 |
| mean | 15.3187 | — |

| Event (among 40-triggers) | k | % |
| --- | --- | --- |
| Close at/below 40 (orderly class) | 58 | 18.12% |
| Jumped through 40 | 262 | 81.88% |
| From >40 to <35 on trigger candle | 116 | 36.25% |
| From >40 to <30 | 55 | 17.19% |
| From >40 to <20 | 15 | 4.69% |

Jump class counts: MODERATE_GAP=85, EXTREME_JUMP_THROUGH=72, LARGE_GAP=116, ORDERLY_TOUCH=11, SMALL_GAP=36

By minutes-to-close at trigger:

| Phase | n | median jump | p90 jump |
| --- | --- | --- | --- |
| >180m_to_close | 0 | — | — |
| 120-180m | 5 | 5.0000 | 15.2000 |
| 60-120m | 74 | 8.0000 | 15.7000 |
| 30-60m | 146 | 12.0000 | 27.0000 |
| 15-30m | 74 | 15.5000 | 37.7000 |
| 5-15m | 20 | 27.0000 | 51.7000 |
| 0-5m | 1 | 34.0000 | 34.0000 |

By terminal outcome (among triggered):

| Terminal | n | median jump | p90 | mean Model B exit |
| --- | --- | --- | --- | --- |
| eventual_yes | 109 | 12.0000 | 27.8000 | 34.5780 |
| eventual_no | 211 | 12.0000 | 30.0000 | 33.8910 |

## 4. NBA — taker strategies T1 / T2 / T3

- **T1** IDEALIZED_TRIGGER_PRICE: exit = 40 whenever close ≤ 40.
- **T2** CANDLE_EXECUTION_PROXY: per-trade exit = trigger-candle `yes_bid_close`. CURRENT fees.
- **T3** conservative: per-trade exit = trigger-candle `yes_bid_low`; CONSERVATIVE fees (taker entry).

| Split | T1 gross | T1 net | T2 gross | T2 net | T3 net |
| --- | --- | --- | --- | --- | --- |
| TRAIN | 3.0952 | 2.6219 | 1.2778 | 0.8502 | -1.3255 |
| VALIDATION | 5.3416 | 4.9312 | 4.0331 | 3.6532 | 1.8444 |
| OOS | 5.1852 | 4.7703 | 3.8189 | 3.4365 | 1.3757 |
| FULL | 4.3902 | 3.9531 | 2.8618 | 2.4618 | 0.4529 |

## 5. NBA — dynamic taker exit frontier

Trigger selected on VALIDATION only (`net_ev_moderate`). OOS evaluated once.

Selected trigger: **40¢** (VAL net EV 3.6532).

### FULL sample (descriptive — not used for selection)

| Trigger | Trigger % | Mean exit (B) | Gross EV B | Fees B | Net EV moderate | Net EV conservative |
| --- | --- | --- | --- | --- | --- | --- |
| 40 | 26.02 | 34.1250 | 2.8618 | 0.3999 | 2.4618 | 0.4529 |
| 35 | 24.15 | 28.3266 | 2.6935 | 0.3345 | 2.3590 | 0.3498 |
| 30 | 22.85 | 23.4840 | 2.5195 | 0.2794 | 2.2401 | 0.3570 |
| 25 | 21.63 | 18.8008 | 2.4398 | 0.2247 | 2.2151 | 0.4309 |
| 20 | 20.33 | 14.0920 | 2.5390 | 0.1677 | 2.3713 | 0.7979 |
| 15 | 19.76 | 9.9136 | 2.2024 | 0.1203 | 2.0821 | 0.6234 |
| 10 | 18.78 | 5.7662 | 2.3024 | 0.0700 | 2.2325 | 0.8813 |
| 5 | 18.54 | 2.7895 | 1.9805 | 0.0348 | 1.9457 | 0.7027 |

### VALIDATION (selection)

| Trigger | n trig % | Net EV moderate | Net EV conservative |
| --- | --- | --- | --- |
| 40 | 24.43 | 3.6532 | 1.8444 |
| 35 | 22.57 | 3.4647 | 1.5619 |
| 30 | 21.53 | 3.1655 | 1.3582 |
| 25 | 20.50 | 3.2168 | 1.4321 |
| 20 | 19.46 | 3.1525 | 1.5774 |
| 15 | 19.05 | 2.7050 | 1.2943 |
| 10 | 18.01 | 3.0064 | 1.6494 |
| 5 | 17.60 | 2.8362 | 1.6117 |

### OOS (once)

| Trigger | n trig % | Net EV moderate | Net EV conservative |
| --- | --- | --- | --- |
| 40 | 24.69 | 3.4365 | 1.3757 |
| 35 | 22.63 | 3.4200 | 1.4985 |
| 30 | 20.99 | 3.7164 | 1.8010 |
| 25 | 20.16 | 3.4579 | 1.7261 |
| 20 | 18.52 | 4.1005 | 2.5633 |
| 15 | 18.11 | 3.6039 | 2.2044 |
| 10 | 16.87 | 4.0514 | 2.7345 |
| 5 | 16.46 | 4.0113 | 2.7836 |

## 6. NBA — dynamic maker hedge (FILL SCENARIO)

Opponent available: 1230 / 1230. Missing: 0.

Opportunity = A2 tradable `yes_bid_close` **up-crosses H from below** after T0 and not after A1 40-close. Already-at-or-above on the first A2 print is **not** treated as a maker fill at H. **Not a fill.**

| H | A2 ≥H before resolution | % | A2 ≥H before A1 stop | % | P(reach & A1 wins) | P(reach & A1 loses) | False-hedge share of opps |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 40 | 456 | 37.07 | 454 | 36.91 | 19.84 | 17.07 | 53.74 |
| 35 | 535 | 43.50 | 534 | 43.41 | 26.34 | 17.07 | 60.67 |
| 30 | 620 | 50.41 | 619 | 50.33 | 33.25 | 17.07 | 66.07 |
| 25 | 718 | 58.37 | 717 | 58.29 | 41.46 | 16.83 | 71.13 |
| 20 | 853 | 69.35 | 847 | 68.86 | 53.58 | 15.28 | 77.80 |
| 15 | 779 | 63.33 | 763 | 62.03 | 50.81 | 11.22 | 81.91 |
| 10 | 646 | 52.52 | 627 | 50.98 | 44.80 | 6.18 | 87.88 |
| 5 | 518 | 42.11 | 496 | 40.33 | 38.46 | 1.87 | 95.36 |

Max A2 before resolution:

| Max A2 ≥ | Count | % |
| --- | --- | --- |
| 40 | 456 | 37.07 |
| 35 | 535 | 43.50 |
| 30 | 623 | 50.65 |
| 25 | 733 | 59.59 |
| 20 | 949 | 77.15 |
| 15 | 1132 | 92.03 |
| 10 | 1200 | 97.56 |
| 5 | 1219 | 99.11 |

### Hedge lock economics (CURRENT / MODERATE / CONSERVATIVE fees)

| H | Paired cost | Lock gross | Entry fee | Hedge fee | Lock net CURRENT |
| --- | --- | --- | --- | --- | --- |
| 40 | 120 | -20.0 | 0.0 | 0.0 | -20.0 |
| 35 | 115 | -15.0 | 0.0 | 0.0 | -15.0 |
| 30 | 110 | -10.0 | 0.0 | 0.0 | -10.0 |
| 25 | 105 | -5.0 | 0.0 | 0.0 | -5.0 |
| 20 | 100 | 0.0 | 0.0 | 0.0 | 0.0 |
| 15 | 95 | 5.0 | 0.0 | 0.0 | 5.0 |
| 10 | 90 | 10.0 | 0.0 | 0.0 | 10.0 |
| 5 | 85 | 15.0 | 0.0 | 0.0 | 15.0 |

### H1 / H2 / H3 net EV (FULL)

| H | H1 p=100% CURRENT | H2 p=50% CURRENT | H3 p=25% CONSERVATIVE |
| --- | --- | --- | --- |
| 40 | 5.1355 | 4.5443 | 3.0900 |
| 35 | 4.7547 | 4.3539 | 2.9903 |
| 30 | 4.8021 | 4.3776 | 2.9992 |
| 25 | 5.1260 | 4.5395 | 3.0785 |
| 20 | 4.4224 | 4.1878 | 2.9022 |
| 15 | 4.6776 | 4.3153 | 2.9796 |
| 10 | 4.7729 | 4.3630 | 3.0180 |
| 5 | 4.1433 | 4.0482 | 2.8723 |

Best validated hedge (VAL, H2 p=50%): **H=40** · VAL net 5.5505 · OOS net 5.3893.

Fill-probability sensitivity at best H (CURRENT fees, FULL):

| p_fill | Net EV |
| --- | --- |
| 0.25 | 4.2487 |
| 0.40 | 4.4261 |
| 0.50 | 4.5443 |
| 0.60 | 4.6625 |
| 0.75 | 4.8399 |
| 0.90 | 5.0172 |
| 1.00 | 5.1355 |

## 7. NBA — master comparison (FULL)

| Strategy | Gross EV | Entry fees | Exit/hedge fees | Net EV | Moderate net | Conservative net |
| --- | --- | --- | --- | --- | --- | --- |
| Hold | 2.8455 | 0.0000 | 0.0000 | 2.8455 | 2.8455 | 1.7255 |
| 80→40 ideal | 4.3902 | 0.0000 | 0.4371 | 3.9531 | 3.9531 | 2.8331 |
| Dynamic taker exit (40 trigger) | 2.8618 | 0.0000 | 0.3999 | 2.4618 | 2.4618 | 0.4529 |
| Maker hedge H=40 | -20.0000 | 0.0000 | 0.0000 | 5.1355 | 4.5443 | 3.0900 |
| Maker hedge H=35 | -15.0000 | 0.0000 | 0.0000 | 4.7547 | 4.3539 | 2.9903 |
| Maker hedge H=30 | -10.0000 | 0.0000 | 0.0000 | 4.8021 | 4.3776 | 2.9992 |
| Maker hedge H=25 | -5.0000 | 0.0000 | 0.0000 | 5.1260 | 4.5395 | 3.0785 |
| Maker hedge H=20 | 0.0000 | 0.0000 | 0.0000 | 4.4224 | 4.1878 | 2.9022 |
| Maker hedge H=15 | 5.0000 | 0.0000 | 0.0000 | 4.6776 | 4.3153 | 2.9796 |
| Maker hedge H=10 | 10.0000 | 0.0000 | 0.0000 | 4.7729 | 4.3630 | 3.0180 |
| Maker hedge H=5 | 15.0000 | 0.0000 | 0.0000 | 4.1433 | 4.0482 | 2.8723 |
| Best validated hedge H=40 (VAL select, p=0.50) | -20.0000 | 0.0000 | 0.0000 | 4.5443 | 5.5505 | 4.0845 |

## 8. NBA — capital efficiency

INITIAL NOTIONAL ≠ MAXIMUM CAPITAL COMMITMENT.

| Strategy | EV/contract | Initial | Reserved | EV / $ deployed | EV / reserved |
| --- | --- | --- | --- | --- | --- |
| Hold | 2.8455 | 80 | 80 | 0.035569 | 0.035569 |
| 80→40 ideal | 3.9531 | 80 | 80 | 0.049414 | 0.049414 |
| Dynamic taker 40 moderate | 2.4618 | 80 | 80 | 0.030773 | 0.030773 |
| Dynamic taker 40 conservative | 0.4529 | 80 | 80 | 0.005661 | 0.005661 |
| Hedge H=40 reserved | 4.5443 | 80 | 120 | 0.056804 | 0.037869 |
| Hedge H=40 sequential (initial only until fill) | 4.5443 | 80 | 80 | 0.056804 | 0.056804 |
| Hedge H=35 reserved | 4.3539 | 80 | 115 | 0.054424 | 0.037860 |
| Hedge H=30 reserved | 4.3776 | 80 | 110 | 0.054720 | 0.039796 |
| Hedge H=25 reserved | 4.5395 | 80 | 105 | 0.056744 | 0.043233 |
| Hedge H=20 reserved | 4.1878 | 80 | 100 | 0.052348 | 0.041878 |
| Hedge H=15 reserved | 4.3153 | 80 | 95 | 0.053941 | 0.045424 |
| Hedge H=10 reserved | 4.3630 | 80 | 90 | 0.054538 | 0.048478 |

## 9. NBA — risk (T2 moderate FULL)

| Stat | Value |
| --- | --- |
| n | 1230 |
| mean | 2.4618 |
| median | 20.0000 |
| std | 29.8001 |
| downside_deviation | 47.9212 |
| sharpe_style | 0.0826 |
| sortino_style | 0.0514 |
| max_single_trade_loss | -80.0000 |
| loss_frequency | 26.0163 |
| average_loss | -47.4123 |
| average_win | 20.0000 |
| profit_factor | 1.1996 |
| expected_shortfall_5pct | -58.7850 |

Per-trade P&L moments. Not annualized. Discrete payoff distribution.

## 2. NCAAB — empirical exit distribution

### Threshold trigger distribution (close ≤ T)

| Exit / trigger | Count | P(trigger) |
| --- | --- | --- |
| 40¢ | 1099 | 26.81% |
| 35¢ | 1018 | 24.84% |
| 30¢ | 941 | 22.96% |
| 25¢ | 885 | 21.59% |
| 20¢ | 837 | 20.42% |
| 15¢ | 803 | 19.59% |
| 10¢ | 769 | 18.76% |
| 5¢ | 734 | 17.91% |

### Realized exit-price proxy (Model B: trigger-candle bid close)

Not the same object as the trigger distribution.

| Region | Count | % of FIRST-80 | % of triggered |
| --- | --- | --- | --- |
| 40-37 | 503 | 12.27% | 45.77% |
| 36-32 | 305 | 7.44% | 27.75% |
| 31-27 | 132 | 3.22% | 12.01% |
| 26-22 | 69 | 1.68% | 6.28% |
| 21-17 | 23 | 0.56% | 2.09% |
| 16-12 | 18 | 0.44% | 1.64% |
| 11-7 | 16 | 0.39% | 1.46% |
| 6-0 | 33 | 0.81% | 3.00% |
| No deterioration exit | 3000 | 73.19% | — |

### Conservative wick proxy (Model C: trigger-candle bid low)

| Region | Count | % of FIRST-80 | % of triggered |
| --- | --- | --- | --- |
| 40-37 | 226 | 5.51% | 20.56% |
| 36-32 | 330 | 8.05% | 30.03% |
| 31-27 | 194 | 4.73% | 17.65% |
| 26-22 | 130 | 3.17% | 11.83% |
| 21-17 | 77 | 1.88% | 7.01% |
| 16-12 | 38 | 0.93% | 3.46% |
| 11-7 | 40 | 0.98% | 3.64% |
| 6-0 | 64 | 1.56% | 5.82% |
| No deterioration exit | 3000 | 73.19% | — |

## 3. NCAAB — jump-through

Gaps are `previous_tradable_close − trigger_close`. Candle proxy, not L2.

| Stat | Close gap (¢) | Low gap (¢) |
| --- | --- | --- |
| n | 1098 | 1098 |
| median | 14.0000 | 17.0000 |
| p75 | 21.0000 | — |
| p90 | 34.0000 | 41.0000 |
| p95 | 46.0000 | — |
| worst | 95.0000 | 95.0000 |
| mean | 17.2286 | — |

| Event (among 40-triggers) | k | % |
| --- | --- | --- |
| Close at/below 40 (orderly class) | 177 | 16.11% |
| Jumped through 40 | 922 | 83.89% |
| From >40 to <35 on trigger candle | 438 | 39.85% |
| From >40 to <30 | 226 | 20.56% |
| From >40 to <20 | 77 | 7.01% |

Jump class counts: MODERATE_GAP=256, LARGE_GAP=389, EXTREME_JUMP_THROUGH=295, SMALL_GAP=120, ORDERLY_TOUCH=38, UNKNOWN=1

By minutes-to-close at trigger:

| Phase | n | median jump | p90 jump |
| --- | --- | --- | --- |
| >180m_to_close | 6 | 10.5000 | 41.0000 |
| 120-180m | 79 | 10.0000 | 21.0000 |
| 60-120m | 521 | 11.0000 | 24.0000 |
| 30-60m | 410 | 18.0000 | 40.2000 |
| 15-30m | 73 | 25.0000 | 61.2000 |
| 5-15m | 7 | 26.0000 | 66.0000 |
| 0-5m | 3 | 55.0000 | 75.0000 |

By terminal outcome (among triggered):

| Terminal | n | median jump | p90 | mean Model B exit |
| --- | --- | --- | --- | --- |
| eventual_yes | 396 | 12.0000 | 25.5000 | 35.5328 |
| eventual_no | 703 | 15.0000 | 41.0000 | 31.8023 |

## 4. NCAAB — taker strategies T1 / T2 / T3

- **T1** IDEALIZED_TRIGGER_PRICE: exit = 40 whenever close ≤ 40.
- **T2** CANDLE_EXECUTION_PROXY: per-trade exit = trigger-candle `yes_bid_close`. CURRENT fees.
- **T3** conservative: per-trade exit = trigger-candle `yes_bid_low`; CONSERVATIVE fees (taker entry).

| Split | T1 gross | T1 net | T2 gross | T2 net | T3 net |
| --- | --- | --- | --- | --- | --- |
| TRAIN | 5.1566 | 4.7409 | 3.4165 | 3.0475 | 0.6579 |
| VALIDATION | 3.4020 | 2.9376 | 1.4697 | 1.0540 | -1.1950 |
| OOS | 7.8571 | 7.5171 | 6.4524 | 6.1515 | 3.9593 |
| FULL | 3.9034 | 3.4529 | 2.0268 | 1.6243 | -0.6564 |

OOS note: `INSUFFICIENT_SAMPLE`.

## 5. NCAAB — dynamic taker exit frontier

Trigger selected on VALIDATION only (`net_ev_moderate`). OOS evaluated once.

Selected trigger: **5¢** (VAL net EV 1.5411).

### FULL sample (descriptive — not used for selection)

| Trigger | Trigger % | Mean exit (B) | Gross EV B | Fees B | Net EV moderate | Net EV conservative |
| --- | --- | --- | --- | --- | --- | --- |
| 40 | 26.81 | 33.1465 | 2.0268 | 0.4025 | 1.6243 | -0.6564 |
| 35 | 24.84 | 27.8831 | 2.0407 | 0.3375 | 1.7032 | -0.4030 |
| 30 | 22.96 | 22.8672 | 2.2440 | 0.2737 | 1.9703 | 0.0389 |
| 25 | 21.59 | 18.3153 | 2.3150 | 0.2187 | 2.0962 | 0.2748 |
| 20 | 20.42 | 13.3393 | 2.2310 | 0.1600 | 2.0710 | 0.4044 |
| 15 | 19.59 | 9.4122 | 2.1561 | 0.1137 | 2.0424 | 0.5073 |
| 10 | 18.76 | 6.0078 | 2.2688 | 0.0726 | 2.1962 | 0.7995 |
| 5 | 17.91 | 2.7425 | 2.4867 | 0.0330 | 2.4537 | 1.2282 |

### VALIDATION (selection)

| Trigger | n trig % | Net EV moderate | Net EV conservative |
| --- | --- | --- | --- |
| 40 | 27.64 | 1.0540 | -1.1950 |
| 35 | 25.81 | 1.0064 | -1.0943 |
| 30 | 23.81 | 1.3040 | -0.6502 |
| 25 | 22.37 | 1.4055 | -0.4380 |
| 20 | 21.30 | 1.2655 | -0.4391 |
| 15 | 20.48 | 1.2091 | -0.3649 |
| 10 | 19.56 | 1.4061 | -0.0165 |
| 5 | 18.81 | 1.5411 | 0.3053 |

### OOS (once)

| Trigger | n trig % | Net EV moderate | Net EV conservative |
| --- | --- | --- | --- |
| 40 | 20.24 | 6.1515 | 3.9593 |
| 35 | 17.86 | 5.9544 | 3.9636 |
| 30 | 15.48 | 6.7695 | 4.8634 |
| 25 | 15.48 | 6.5876 | 4.6261 |
| 20 | 15.48 | 6.2371 | 4.5461 |
| 15 | 14.29 | 6.6066 | 4.9728 |
| 10 | 14.29 | 6.3492 | 4.8276 |
| 5 | 13.10 | 7.1268 | 5.8625 |

## 6. NCAAB — dynamic maker hedge (FILL SCENARIO)

Opponent available: 4099 / 4099. Missing: 0.

Opportunity = A2 tradable `yes_bid_close` **up-crosses H from below** after T0 and not after A1 40-close. Already-at-or-above on the first A2 print is **not** treated as a maker fill at H. **Not a fill.**

| H | A2 ≥H before resolution | % | A2 ≥H before A1 stop | % | P(reach & A1 wins) | P(reach & A1 loses) | False-hedge share of opps |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 40 | 1541 | 37.59 | 1534 | 37.42 | 20.44 | 16.98 | 54.63 |
| 35 | 1736 | 42.35 | 1730 | 42.21 | 25.20 | 17.00 | 59.71 |
| 30 | 2013 | 49.11 | 2010 | 49.04 | 32.06 | 16.98 | 65.37 |
| 25 | 2361 | 57.60 | 2352 | 57.38 | 40.62 | 16.76 | 70.79 |
| 20 | 2745 | 66.97 | 2716 | 66.26 | 50.67 | 15.59 | 76.47 |
| 15 | 2659 | 64.87 | 2578 | 62.89 | 51.18 | 11.71 | 81.38 |
| 10 | 2308 | 56.31 | 2211 | 53.94 | 46.94 | 7.00 | 87.02 |
| 5 | 1875 | 45.74 | 1771 | 43.21 | 40.38 | 2.83 | 93.45 |

Max A2 before resolution:

| Max A2 ≥ | Count | % |
| --- | --- | --- |
| 40 | 1546 | 37.72 |
| 35 | 1744 | 42.55 |
| 30 | 2029 | 49.50 |
| 25 | 2406 | 58.70 |
| 20 | 2968 | 72.41 |
| 15 | 3662 | 89.34 |
| 10 | 3959 | 96.58 |
| 5 | 4053 | 98.88 |

### Hedge lock economics (CURRENT / MODERATE / CONSERVATIVE fees)

| H | Paired cost | Lock gross | Entry fee | Hedge fee | Lock net CURRENT |
| --- | --- | --- | --- | --- | --- |
| 40 | 120 | -20.0 | 0.0 | 0.0 | -20.0 |
| 35 | 115 | -15.0 | 0.0 | 0.0 | -15.0 |
| 30 | 110 | -10.0 | 0.0 | 0.0 | -10.0 |
| 25 | 105 | -5.0 | 0.0 | 0.0 | -5.0 |
| 20 | 100 | 0.0 | 0.0 | 0.0 | 0.0 |
| 15 | 95 | 5.0 | 0.0 | 0.0 | 5.0 |
| 10 | 90 | 10.0 | 0.0 | 0.0 | 10.0 |
| 5 | 85 | 15.0 | 0.0 | 0.0 | 15.0 |

### H1 / H2 / H3 net EV (FULL)

| H | H1 p=100% CURRENT | H2 p=50% CURRENT | H3 p=25% CONSERVATIVE |
| --- | --- | --- | --- |
| 40 | 4.7999 | 4.1264 | 2.6304 |
| 35 | 5.0276 | 4.2403 | 2.6846 |
| 30 | 5.1187 | 4.2858 | 2.7043 |
| 25 | 5.2288 | 4.3409 | 2.7298 |
| 20 | 5.2233 | 4.3381 | 2.7291 |
| 15 | 4.9484 | 4.2006 | 2.6717 |
| 10 | 4.2736 | 3.8633 | 2.5169 |
| 5 | 3.7605 | 3.6067 | 2.4008 |

Best validated hedge (VAL, H2 p=50%): **H=25** · VAL net 3.9734 · OOS net 7.0719.

Fill-probability sensitivity at best H (CURRENT fees, FULL):

| p_fill | Net EV |
| --- | --- |
| 0.25 | 3.8969 |
| 0.40 | 4.1633 |
| 0.50 | 4.3409 |
| 0.60 | 4.5185 |
| 0.75 | 4.7849 |
| 0.90 | 5.0512 |
| 1.00 | 5.2288 |

## 7. NCAAB — master comparison (FULL)

| Strategy | Gross EV | Entry fees | Exit/hedge fees | Net EV | Moderate net | Conservative net |
| --- | --- | --- | --- | --- | --- | --- |
| Hold | 2.8007 | 0.0000 | 0.0000 | 2.8007 | 2.8007 | 1.6807 |
| 80→40 ideal | 3.9034 | 0.0000 | 0.4505 | 3.4529 | 3.4529 | 2.3329 |
| Dynamic taker exit (40 trigger) | 2.0268 | 0.0000 | 0.4025 | 1.6243 | 1.6243 | -0.6564 |
| Maker hedge H=40 | -20.0000 | 0.0000 | 0.0000 | 4.7999 | 4.1264 | 2.6304 |
| Maker hedge H=35 | -15.0000 | 0.0000 | 0.0000 | 5.0276 | 4.2403 | 2.6846 |
| Maker hedge H=30 | -10.0000 | 0.0000 | 0.0000 | 5.1187 | 4.2858 | 2.7043 |
| Maker hedge H=25 | -5.0000 | 0.0000 | 0.0000 | 5.2288 | 4.3409 | 2.7298 |
| Maker hedge H=20 | 0.0000 | 0.0000 | 0.0000 | 5.2233 | 4.3381 | 2.7291 |
| Maker hedge H=15 | 5.0000 | 0.0000 | 0.0000 | 4.9484 | 4.2006 | 2.6717 |
| Maker hedge H=10 | 10.0000 | 0.0000 | 0.0000 | 4.2736 | 3.8633 | 2.5169 |
| Maker hedge H=5 | 15.0000 | 0.0000 | 0.0000 | 3.7605 | 3.6067 | 2.4008 |
| Best validated hedge H=25 (VAL select, p=0.50) | -5.0000 | 0.0000 | 0.0000 | 4.3409 | 3.9734 | 2.2878 |

## 8. NCAAB — capital efficiency

INITIAL NOTIONAL ≠ MAXIMUM CAPITAL COMMITMENT.

| Strategy | EV/contract | Initial | Reserved | EV / $ deployed | EV / reserved |
| --- | --- | --- | --- | --- | --- |
| Hold | 2.8007 | 80 | 80 | 0.035009 | 0.035009 |
| 80→40 ideal | 3.4529 | 80 | 80 | 0.043161 | 0.043161 |
| Dynamic taker 40 moderate | 1.6243 | 80 | 80 | 0.020304 | 0.020304 |
| Dynamic taker 40 conservative | -0.6564 | 80 | 80 | -0.008205 | -0.008205 |
| Hedge H=40 reserved | 4.1264 | 80 | 120 | 0.051580 | 0.034387 |
| Hedge H=40 sequential (initial only until fill) | 4.1264 | 80 | 80 | 0.051580 | 0.051580 |
| Hedge H=35 reserved | 4.2403 | 80 | 115 | 0.053004 | 0.036872 |
| Hedge H=30 reserved | 4.2858 | 80 | 110 | 0.053573 | 0.038962 |
| Hedge H=25 reserved | 4.3409 | 80 | 105 | 0.054261 | 0.041342 |
| Hedge H=20 reserved | 4.3381 | 80 | 100 | 0.054226 | 0.043381 |
| Hedge H=15 reserved | 4.2006 | 80 | 95 | 0.052507 | 0.044217 |
| Hedge H=10 reserved | 3.8633 | 80 | 90 | 0.048291 | 0.042926 |

## 9. NCAAB — risk (T2 moderate FULL)

| Stat | Value |
| --- | --- |
| n | 4099 |
| mean | 1.6243 |
| median | 20.0000 |
| std | 30.6261 |
| downside_deviation | 49.1099 |
| sharpe_style | 0.0530 |
| sortino_style | 0.0331 |
| max_single_trade_loss | -80.0000 |
| loss_frequency | 26.8602 |
| average_loss | -48.4122 |
| average_win | 20.0000 |
| profit_factor | 1.1249 |
| expected_shortfall_5pct | -62.4667 |

Per-trade P&L moments. Not annualized. Discrete payoff distribution.

## 10. NBA vs NCAAB

| Metric | NBA | NCAAB |
| --- | --- | --- |
| n / survivors | 1230 / 910 | 4099 / 2998 |
| T1 net EV | 3.9531 | 3.4529 |
| T2 moderate net EV | 2.4618 | 1.6243 |
| T3 conservative net EV | 0.4529 | -0.6564 |
| Median jump @40 | 12.0000 | 14.0000 |
| P90 jump @40 | 30.0000 | 34.0000 |
| P(jump through 40) | 81.88 | 83.89 |
| Best VAL hedge H | 40 | 25 |
| Best hedge H2 FULL net | 4.5443 | 4.3409 |

## 11. Dynamic delta / exposure (conceptual)

| State | A1 | A2 | Portfolio | Action |
| --- | --- | --- | --- | --- |
| Healthy | High positive | Low | Directional | Hold |
| Mild deterioration | Falling | Rising | Increasing risk | Monitor |
| Hedge opportunity | Moderate | Moderate | High uncertainty | Rest maker hedge (scenario) |
| Hedge filled | Offset | Offset | Reduced terminal payoff if pair settles 100 | Manage pair |
| Severe deterioration | Low | High | Thesis failed | Taker liquidate or wait |

TERMINAL PAYOFF NEUTRALITY (80+H=100 ⇒ lock 20−H) is not PATHWISE DELTA NEUTRALITY. Candles cannot prove simultaneous complementary books or equal contract counts.

## 12. Verdict grades

| Grade | Meaning |
| --- | --- |
| A. Path robustness | Frozen 80/40 close-stop reproduced |
| B. Exit-price realism | Trigger ≠ fill; Model B/C measured from candles |
| C. Fee burden | CURRENT taker-on-stop only; stress scenarios explicit |
| D. Hedge opportunity structure | A2 prints measured; fills are scenarios |
| E. Actual execution evidence | UNOBSERVED |

## 13. Strongest remaining uncertainty

1. No historical maker/taker fills — all exits and hedges are candle proxies or assumed fill probabilities.
2. IOC liquidation can print through the trigger-candle close; bid_low is a wick proxy, not a queue.
3. FCM $0.01 rounding not applied to fees.
4. NCAAB OOS is small.
5. Production `GET /series` was not re-verified in this run (demo API 2026-09-03: `quadratic`, M=1).

## 14. Artifacts

- Ledgers: `.../derived/{nba,ncaab}/first80_realistic_exit_fee_audit_v1/ledger.parquet`
- Summaries: `summary.json`
- Dashboard: `frontend/first80-realistic-exit-fee-audit-v1` (port 5180)

## 15. Final research questions

**Does FIRST-80 retain positive EV after moderate and conservative execution?**

- **T1 (ideal 40):** yes, net +3.95¢ NBA / +3.45¢ NCAAB after CURRENT taker-stop fees.
- **T2 (moderate candle exit):** still positive on FULL (+2.46 / +1.62), but **below hold-to-settlement** (+2.85 / +2.80). The stop only beats hold if you actually realize ~40. Mean Model B exits are 34.1¢ / 33.1¢.
- **T3 (conservative wick + taker entry):** NBA +0.45¢ (thin); NCAAB **−0.66¢**. The phenomenon does **not** robustly survive adverse liquidation.

**Does a dynamic maker hedge beat a dynamic taker liquidation once fill uncertainty is included?**

- Only as a **FILL SCENARIO**. H=40 up-cross opportunity ≈ 37% of trades; **~54% of those are false hedges** (A1 still settles YES).
- H2 p=50% at H=40: +4.54¢ NBA / +4.13¢ NCAAB, above T1 — **if** half of those candle opportunities were maker fills at 40. That fill rate is ASSUMED, not measured.
- H3 p=25% still above T2, still a scenario.
- NCAAB VAL picked H=25; OOS n=84 is `INSUFFICIENT_SAMPLE`. NCAAB taker frontier picked **5¢** on VAL (closer to hold than to a 40-stop).

Do not arm. Do not modify live trading.

