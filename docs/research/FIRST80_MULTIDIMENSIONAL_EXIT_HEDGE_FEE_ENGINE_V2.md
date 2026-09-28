# FIRST80_MULTIDIMENSIONAL_EXIT_HEDGE_FEE_ENGINE_V2

```text
VERDICT: RESEARCH ONLY

LIVE EXECUTION CHANGED: FALSE

CANDLE PATH ≠ ACTUAL FILL
STOP TRIGGER ≠ REALIZED EXIT
MAKER OPPORTUNITY ≠ MAKER FILL
GROSS EV ≠ NET EV
```

Isolated V2 extension of `FIRST80_REALISTIC_EXIT_FEE_AUDIT_V1`. Hierarchical — not a full combinatorial blast. V1 artifacts, FIRST01, Risk, live execution, and hedge V1–V4 were not modified.

Config: `docs/research/first80_multidimensional_exit_hedge_fee_v2.yaml`

Reproduce:

```text
/tmp/momento-nba-venv/bin/python apps/ncaab-data/scripts/first80_multidimensional_exit_hedge_fee_v2.py
```

Artifacts:

```text
Backtesting Suite/Data/{NBA,NCAAB}/2025-2026/warehouse/derived/{nba,ncaab}/first80_multidimensional_exit_hedge_fee_v2/
  post_entry_paths.parquet
  threshold_events.parquet
  exit_distribution.parquet
  hedge_opportunities.parquet
  policy_results.parquet
  monte_carlo_results.parquet
  fee_attribution.parquet
  trade_summaries.parquet
  config.yaml
  summary.json
```

Dashboard (research only): `frontend/first80-multidimensional-exit-hedge-fee-v2` on port 5182.

NBA 2025–26 play-by-play is already in this warehouse (NBA.com `playbyplayv3`, 1,352 games, 323 MB). It is **not** copied. Local pointers live next to this experiment:

```text
.../derived/nba/first80_multidimensional_exit_hedge_fee_v2/pbp/
  raw_pbp_v3/            → warehouse/raw/nba_stats/pbp_v3
  raw_pbp_live/          → warehouse/raw/nba_stats/pbp_live  (timeActual)
  boxscore_summary/      → warehouse/raw/nba_stats/boxscore_summary
  game_crosswalk.json    → warehouse/normalized/nba/pbp/game_crosswalk.json
  inventory.json
  live_inventory.json
  first80_pbp_index.json
```

FIRST-80 coverage: **1,223 / 1,230** events have a crosswalk `nba_game_id` and a PBP file (99.43%). Seven events are `UNMATCHED` in the crosswalk (no invented IDs). Stats V3 has period/game clock only. Observed per-play wall clock (`timeActual`) is on the live CDN feed: **1,352 / 1,352** warehouse games downloaded (780,137 / 780,137 actions), including **1,223 / 1,230** FIRST-80 events. PBP is **not** wired into V2 EV yet.

## Methods (causal, hierarchical)

Phase 1 describes frozen FIRST-80 paths. Phase 2 sweeps one dimension at a time. Phase 3 is two-way (threshold × vol, threshold × time, H × p_fill). Phase 4 discovers on TRAIN, selects on VALIDATION, evaluates OOS once.

Taker T1 = exact threshold (upper bound, grade C). T2 = trigger-candle bid close (observed proxy, grade B). T3 = trigger-candle bid low. T4 = 10k bootstrap from empirical (threshold, vol) close pools — still candle proxies, not IOC fills.

Hedge is an A2 **up-cross** of H after T0 and before the A1 taker trigger. `p_fill` is an assumed scenario (grade D). Opportunity ≠ fill. H1/H2 fill at H; H3 assumed band [H−3, H+2]; H4 multiplies p by 0.35 on ≥10¢ jumps.

Fees: CURRENT = $0 maker entry + quadratic taker on the realized proxy (M=1, coef 0.07). CONSERVATIVE / FUTURE add stressed maker entry (2× 0.0175) and/or 1.5× taker. Settlement fee = 0. Copied locally — production `fee_models.py` was not edited.

**Central measured result:** on the FULL frozen universes, **no T2 bid-close stop in 75→5 beats hold-to-settlement** (best NBA T2 is 45¢ at +2.57 vs hold +2.85; best NCAAB T2 is 5¢ at +2.45 vs hold +2.80). Slippage, not fees, is the gap (T1−T2 ≈ 1.5–1.8¢; fee drag ≈ 0.40¢).

## 0. Reproduction

- **NBA** path **PASS** 910/1230 = 73.9837% · stop **PASS** · OOS n=243 
- **NCAAB** path **PASS** 2998/4099 = 73.1398% · stop **PASS** · OOS n=84 INSUFFICIENT_SAMPLE

## 1. Phase 1 — what actually happens

### NBA reach rates (close ≤ T) and P(win | close ≤ T)

| T | P(close) | P(touch) | P(jump) | P(close|win) | P(close|lose) | P(win|close) |
| --- | --- | --- | --- | --- | --- | --- |
| 75 | 63.82 | 73.33 | 37.97 | 56.33 | 100.00 | 73.12 |
| 70 | 53.17 | 61.95 | 34.96 | 43.47 | 100.00 | 67.74 |
| 65 | 45.53 | 53.17 | 32.68 | 34.25 | 100.00 | 62.32 |
| 60 | 38.29 | 46.34 | 27.40 | 25.52 | 100.00 | 55.20 |
| 55 | 34.55 | 40.73 | 25.53 | 21.00 | 100.00 | 50.35 |
| 50 | 30.49 | 36.67 | 24.96 | 16.09 | 100.00 | 43.73 |
| 45 | 27.97 | 33.01 | 23.41 | 13.05 | 100.00 | 38.66 |
| 40 | 26.02 | 30.81 | 21.30 | 10.70 | 100.00 | 34.06 |
| 35 | 24.15 | 28.05 | 20.73 | 8.44 | 100.00 | 28.96 |
| 30 | 22.85 | 26.67 | 19.27 | 6.87 | 100.00 | 24.91 |
| 25 | 21.63 | 25.53 | 18.21 | 5.40 | 100.00 | 20.68 |
| 20 | 20.33 | 23.41 | 16.99 | 3.83 | 100.00 | 15.60 |
| 15 | 19.76 | 22.11 | 16.26 | 3.14 | 100.00 | 13.17 |
| 10 | 18.78 | 20.73 | 16.10 | 1.96 | 100.00 | 8.66 |
| 5 | 18.54 | 19.76 | 14.15 | 1.67 | 100.00 | 7.46 |

P(win | min price ≤ X) — nba

| X | n | % univ | P(win) |
| --- | --- | --- | --- |
| 75 | 785 | 63.82 | 73.12 |
| 70 | 654 | 53.17 | 67.74 |
| 65 | 560 | 45.53 | 62.32 |
| 60 | 471 | 38.29 | 55.20 |
| 55 | 425 | 34.55 | 50.35 |
| 50 | 375 | 30.49 | 43.73 |
| 45 | 344 | 27.97 | 38.66 |
| 40 | 320 | 26.02 | 34.06 |
| 35 | 297 | 24.15 | 28.96 |
| 30 | 281 | 22.85 | 24.91 |
| 25 | 266 | 21.63 | 20.68 |
| 20 | 250 | 20.33 | 15.60 |
| 15 | 243 | 19.76 | 13.17 |
| 10 | 231 | 18.78 | 8.66 |
| 5 | 228 | 18.54 | 7.46 |

Exit-band % given trigger (Model B close) — nba

| Trigger | n | mean | 37–40 | 32–36 | 27–31 | 22–26 | <22 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 40 | 320 | 34.12 | 51.2 | 25.3 | 12.2 | 4.4 | 6.9 |
| 35 | 297 | 28.33 | 0.0 | 43.1 | 30.0 | 11.8 | 15.2 |
| 30 | 281 | 23.48 | 0.0 | 0.0 | 45.6 | 26.7 | 27.8 |
| 25 | 266 | 18.80 | 0.0 | 0.0 | 0.0 | 47.0 | 53.0 |
| 20 | 250 | 14.09 | 0.0 | 0.0 | 0.0 | 0.0 | 100.0 |
| 15 | 243 | 9.91 | 0.0 | 0.0 | 0.0 | 0.0 | 100.0 |
| 10 | 231 | 5.77 | 0.0 | 0.0 | 0.0 | 0.0 | 100.0 |
| 5 | 228 | 2.79 | 0.0 | 0.0 | 0.0 | 0.0 | 100.0 |

### NCAAB reach rates (close ≤ T) and P(win | close ≤ T)

| T | P(close) | P(touch) | P(jump) | P(close|win) | P(close|lose) | P(win|close) |
| --- | --- | --- | --- | --- | --- | --- |
| 75 | 63.92 | 80.31 | 40.99 | 56.45 | 99.86 | 73.13 |
| 70 | 53.62 | 70.11 | 38.89 | 44.02 | 99.86 | 67.97 |
| 65 | 45.50 | 61.99 | 35.23 | 34.21 | 99.86 | 62.25 |
| 60 | 39.94 | 54.94 | 30.01 | 27.49 | 99.86 | 56.99 |
| 55 | 35.67 | 48.94 | 27.57 | 22.33 | 99.86 | 51.85 |
| 50 | 31.96 | 44.16 | 24.66 | 17.86 | 99.86 | 46.26 |
| 45 | 29.28 | 39.50 | 25.27 | 14.64 | 99.72 | 41.42 |
| 40 | 26.81 | 36.55 | 22.49 | 11.67 | 99.72 | 36.03 |
| 35 | 24.84 | 33.91 | 21.25 | 9.28 | 99.72 | 30.94 |
| 30 | 22.96 | 31.06 | 19.52 | 7.01 | 99.72 | 25.29 |
| 25 | 21.59 | 28.59 | 17.98 | 5.36 | 99.72 | 20.57 |
| 20 | 20.42 | 24.69 | 17.76 | 3.98 | 99.57 | 16.13 |
| 15 | 19.59 | 22.96 | 16.71 | 3.01 | 99.43 | 12.70 |
| 10 | 18.76 | 21.30 | 15.25 | 2.00 | 99.43 | 8.84 |
| 5 | 17.91 | 19.54 | 13.27 | 0.97 | 99.43 | 4.50 |

P(win | min price ≤ X) — ncaab

| X | n | % univ | P(win) |
| --- | --- | --- | --- |
| 75 | 2620 | 63.92 | 73.13 |
| 70 | 2198 | 53.62 | 67.97 |
| 65 | 1865 | 45.50 | 62.25 |
| 60 | 1637 | 39.94 | 56.99 |
| 55 | 1462 | 35.67 | 51.85 |
| 50 | 1310 | 31.96 | 46.26 |
| 45 | 1200 | 29.28 | 41.42 |
| 40 | 1099 | 26.81 | 36.03 |
| 35 | 1018 | 24.84 | 30.94 |
| 30 | 941 | 22.96 | 25.29 |
| 25 | 885 | 21.59 | 20.57 |
| 20 | 837 | 20.42 | 16.13 |
| 15 | 803 | 19.59 | 12.70 |
| 10 | 769 | 18.76 | 8.84 |
| 5 | 734 | 17.91 | 4.50 |

Exit-band % given trigger (Model B close) — ncaab

| Trigger | n | mean | 37–40 | 32–36 | 27–31 | 22–26 | <22 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 40 | 1099 | 33.15 | 45.8 | 27.8 | 12.0 | 6.3 | 8.2 |
| 35 | 1018 | 27.88 | 0.0 | 44.6 | 27.0 | 13.0 | 15.4 |
| 30 | 941 | 22.87 | 0.0 | 0.0 | 43.4 | 28.1 | 28.6 |
| 25 | 885 | 18.32 | 0.0 | 0.0 | 0.0 | 45.2 | 54.8 |
| 20 | 837 | 13.34 | 0.0 | 0.0 | 0.0 | 0.0 | 100.0 |
| 15 | 803 | 9.41 | 0.0 | 0.0 | 0.0 | 0.0 | 100.0 |
| 10 | 769 | 6.01 | 0.0 | 0.0 | 0.0 | 0.0 | 100.0 |
| 5 | 734 | 2.74 | 0.0 | 0.0 | 0.0 | 0.0 | 100.0 |

## 2. Phase 2 — univariate (T2 close, CURRENT fees unless noted)

### NBA threshold sweep T2

| T | Trig % | Mean exit | Gross | Fees | Net | Max loss |
| --- | --- | --- | --- | --- | --- | --- |
| 75 | 63.82 | 72.59 | 2.5041 | 0.8833 | 1.6208 | -39.7053 |
| 70 | 53.17 | 67.22 | 2.5691 | 0.8145 | 1.7546 | -42.6653 |
| 65 | 45.53 | 61.71 | 2.5683 | 0.7469 | 1.8214 | -46.5925 |
| 60 | 38.29 | 55.97 | 3.1398 | 0.6516 | 2.4882 | -70.6300 |
| 55 | 34.55 | 50.61 | 2.9333 | 0.5966 | 2.3367 | -70.6300 |
| 50 | 30.49 | 44.37 | 3.0382 | 0.5159 | 2.5224 | -80.0000 |
| 45 | 27.97 | 39.31 | 3.0276 | 0.4574 | 2.5702 | -80.0000 |
| 40 | 26.02 | 34.12 | 2.8618 | 0.3999 | 2.4618 | -80.0000 |
| 35 | 24.15 | 28.33 | 2.6935 | 0.3345 | 2.3590 | -80.0000 |
| 30 | 22.85 | 23.48 | 2.5195 | 0.2794 | 2.2401 | -80.0000 |
| 25 | 21.63 | 18.80 | 2.4398 | 0.2247 | 2.2151 | -80.0000 |
| 20 | 20.33 | 14.09 | 2.5390 | 0.1677 | 2.3713 | -80.0000 |
| 15 | 19.76 | 9.91 | 2.2024 | 0.1203 | 2.0821 | -80.0000 |
| 10 | 18.78 | 5.77 | 2.3024 | 0.0700 | 2.2325 | -80.0000 |
| 5 | 18.54 | 2.79 | 1.9805 | 0.0348 | 1.9457 | -80.0000 |

Trigger-type @40 T2 — nba

| Type | P | Trig % | Net |
| --- | --- | --- | --- |
| BID_CLOSE_BELOW_THRESHOLD | 1 | 26.02 | 2.4618 |
| BID_LOW_BELOW_THRESHOLD | 1 | 30.81 | 2.3937 |
| MID_PROXY_BELOW_THRESHOLD | 1 | 25.28 | 2.5705 |
| PERCENTAGE_DECLINE_FROM_ENTRY | 1 | 26.34 | 2.5590 |
| RATE_OF_CHANGE_DETERIORATION | 1 | 58.37 | 1.6317 |
| N_CONSECUTIVE_MINUTES_BELOW_THRESHOLD | 1 | 26.02 | 2.4618 |
| N_CONSECUTIVE_MINUTES_BELOW_THRESHOLD | 2 | 24.23 | 2.4987 |
| N_CONSECUTIVE_MINUTES_BELOW_THRESHOLD | 3 | 23.09 | 2.3425 |
| N_CONSECUTIVE_MINUTES_BELOW_THRESHOLD | 5 | 20.73 | 2.5164 |

Fee scenarios @40 T2 — nba

| Scenario | Net | Fees |
| --- | --- | --- |
| CURRENT_BASE_CASE | 2.4618 | 0.3999 |
| CONSERVATIVE_FEE_STRESS | 1.9018 | 0.9599 |
| HIGHER_FUTURE_FEE_STRESS | 1.7019 | 1.1599 |

T4 Monte Carlo (10k) — nba

| T | mean | p05 | p50 | p95 | P(EV>0) |
| --- | --- | --- | --- | --- | --- |
| 40 | 2.4441 | 1.0273 | 2.4456 | 3.8482 | 0.998 |
| 30 | 2.2135 | 0.6505 | 2.2083 | 3.7263 | 0.990 |
| 20 | 2.3509 | 0.6799 | 2.3681 | 3.9410 | 0.990 |

### NCAAB threshold sweep T2

| T | Trig % | Mean exit | Gross | Fees | Net | Max loss |
| --- | --- | --- | --- | --- | --- | --- |
| 75 | 63.92 | 71.97 | 2.0578 | 0.8900 | 1.1678 | -80.0000 |
| 70 | 53.62 | 66.16 | 1.8300 | 0.8234 | 1.0066 | -80.0000 |
| 65 | 45.50 | 60.37 | 1.9424 | 0.7437 | 1.1987 | -80.0000 |
| 60 | 39.94 | 54.79 | 1.9188 | 0.6737 | 1.2450 | -80.0000 |
| 55 | 35.67 | 49.42 | 1.9341 | 0.6053 | 1.3288 | -80.0000 |
| 50 | 31.96 | 43.85 | 2.0298 | 0.5334 | 1.4963 | -80.0000 |
| 45 | 29.28 | 37.98 | 1.7958 | 0.4673 | 1.3285 | -80.0000 |
| 40 | 26.81 | 33.15 | 2.0268 | 0.4025 | 1.6243 | -80.0000 |
| 35 | 24.84 | 27.88 | 2.0407 | 0.3375 | 1.7032 | -80.0000 |
| 30 | 22.96 | 22.87 | 2.2440 | 0.2737 | 1.9703 | -80.0000 |
| 25 | 21.59 | 18.32 | 2.3150 | 0.2187 | 2.0962 | -80.0000 |
| 20 | 20.42 | 13.34 | 2.2310 | 0.1600 | 2.0710 | -80.0000 |
| 15 | 19.59 | 9.41 | 2.1561 | 0.1137 | 2.0424 | -80.0000 |
| 10 | 18.76 | 6.01 | 2.2688 | 0.0726 | 2.1962 | -80.0000 |
| 5 | 17.91 | 2.74 | 2.4867 | 0.0330 | 2.4537 | -80.0000 |

Trigger-type @40 T2 — ncaab

| Type | P | Trig % | Net |
| --- | --- | --- | --- |
| BID_CLOSE_BELOW_THRESHOLD | 1 | 26.81 | 1.6243 |
| BID_LOW_BELOW_THRESHOLD | 1 | 36.55 | 1.4276 |
| MID_PROXY_BELOW_THRESHOLD | 1 | 26.15 | 1.6484 |
| PERCENTAGE_DECLINE_FROM_ENTRY | 1 | 27.35 | 1.6332 |
| RATE_OF_CHANGE_DETERIORATION | 1 | 61.94 | 0.9066 |
| N_CONSECUTIVE_MINUTES_BELOW_THRESHOLD | 1 | 26.81 | 1.6243 |
| N_CONSECUTIVE_MINUTES_BELOW_THRESHOLD | 2 | 25.01 | 1.6325 |
| N_CONSECUTIVE_MINUTES_BELOW_THRESHOLD | 3 | 23.84 | 1.7690 |
| N_CONSECUTIVE_MINUTES_BELOW_THRESHOLD | 5 | 21.81 | 2.0576 |

Fee scenarios @40 T2 — ncaab

| Scenario | Net | Fees |
| --- | --- | --- |
| CURRENT_BASE_CASE | 1.6243 | 0.4025 |
| CONSERVATIVE_FEE_STRESS | 1.0643 | 0.9625 |
| HIGHER_FUTURE_FEE_STRESS | 0.8631 | 1.1637 |

T4 Monte Carlo (10k) — ncaab

| T | mean | p05 | p50 | p95 | P(EV>0) |
| --- | --- | --- | --- | --- | --- |
| 40 | 1.6223 | 0.8556 | 1.6203 | 2.4060 | 1.000 |
| 30 | 1.9706 | 1.1248 | 1.9728 | 2.8257 | 1.000 |
| 20 | 2.0687 | 1.1662 | 2.0702 | 2.9764 | 1.000 |

## 3. Phase 3 — two-dimensional

### NBA H × p_fill (hybrid H2, T2@40 fallback) net EV

| H | 0% | 10% | 20% | 30% | 40% | 50% | 60% | 70% | 80% | 90% | 100% |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 40 | 2.4618 | 2.7276 | 2.9934 | 3.2592 | 3.5250 | 3.7908 | 4.0565 | 4.3223 | 4.5881 | 4.8539 | 5.1197 |
| 35 | 2.4618 | 2.6911 | 2.9204 | 3.1497 | 3.3790 | 3.6083 | 3.8376 | 4.0669 | 4.2962 | 4.5254 | 4.7547 |
| 30 | 2.4618 | 2.6957 | 2.9296 | 3.1635 | 3.3973 | 3.6312 | 3.8651 | 4.0989 | 4.3328 | 4.5667 | 4.8005 |
| 25 | 2.4618 | 2.7267 | 2.9916 | 3.2565 | 3.5214 | 3.7863 | 4.0512 | 4.3161 | 4.5810 | 4.8459 | 5.1108 |
| 20 | 2.4618 | 2.6469 | 2.8320 | 3.0170 | 3.2021 | 3.3871 | 3.5722 | 3.7573 | 3.9423 | 4.1274 | 4.3124 |
| 15 | 2.4618 | 2.6494 | 2.8369 | 3.0245 | 3.2120 | 3.3995 | 3.5871 | 3.7746 | 3.9621 | 4.1497 | 4.3372 |
| 10 | 2.4618 | 2.6218 | 2.7818 | 2.9418 | 3.1018 | 3.2618 | 3.4218 | 3.5818 | 3.7418 | 3.9018 | 4.0618 |
| 5 | 2.4618 | 2.5141 | 2.5664 | 2.6187 | 2.6709 | 2.7232 | 2.7755 | 2.8277 | 2.8800 | 2.9323 | 2.9846 |

H4 jump-skip (p=50% H=40) net=3.0357 · H3 band fill net=3.5318 — both ASSUMED.

### NCAAB H × p_fill (hybrid H2, T2@40 fallback) net EV

| H | 0% | 10% | 20% | 30% | 40% | 50% | 60% | 70% | 80% | 90% | 100% |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 40 | 1.6243 | 1.9343 | 2.2443 | 2.5542 | 2.8642 | 3.1741 | 3.4841 | 3.7941 | 4.1040 | 4.4140 | 4.7239 |
| 35 | 1.6243 | 1.9578 | 2.2913 | 2.6247 | 2.9582 | 3.2916 | 3.6251 | 3.9586 | 4.2920 | 4.6255 | 4.9589 |
| 30 | 1.6243 | 1.9680 | 2.3117 | 2.6553 | 2.9990 | 3.3426 | 3.6863 | 4.0300 | 4.3736 | 4.7173 | 5.0609 |
| 25 | 1.6243 | 1.9765 | 2.3287 | 2.6808 | 3.0330 | 3.3851 | 3.7373 | 4.0894 | 4.4416 | 4.7937 | 5.1459 |
| 20 | 1.6243 | 1.9669 | 2.3094 | 2.6520 | 2.9945 | 3.3371 | 3.6796 | 4.0222 | 4.3647 | 4.7072 | 5.0498 |
| 15 | 1.6243 | 1.9064 | 2.1884 | 2.4704 | 2.7524 | 3.0344 | 3.3165 | 3.5985 | 3.8805 | 4.1625 | 4.4445 |
| 10 | 1.6243 | 1.7992 | 1.9740 | 2.1489 | 2.3237 | 2.4986 | 2.6734 | 2.8483 | 3.0231 | 3.1980 | 3.3728 |
| 5 | 1.6243 | 1.6978 | 1.7713 | 1.8448 | 1.9183 | 1.9918 | 2.0653 | 2.1388 | 2.2123 | 2.2857 | 2.3592 |

H4 jump-skip (p=50% H=40) net=2.1719 · H3 band fill net=2.9048 — both ASSUMED.

## 4. Phase 4 — selection (VAL → OOS once)

- **nba**: VAL taker T=40 net=3.6532 → OOS net=3.4365 (n=243 )
- **nba**: VAL hedge H=40 net=4.9115 → OOS net=4.7224
- **ncaab**: VAL taker T=5 net=1.5411 → OOS net=7.1268 (n=84 INSUFFICIENT_SAMPLE)
- **ncaab**: VAL hedge H=25 net=2.9921 → OOS net=6.1875

## 5. Master EV table (FULL)

| Strategy | NBA Gross | NBA Moderate Net | NBA Conservative Net | NCAAB Gross | NCAAB Moderate Net | NCAAB Conservative Net |
| --- | --- | --- | --- | --- | --- | --- |
| Hold | 2.8455 | 2.8455 | 2.8455 | 2.8007 | 2.8007 | 2.8007 |
| 80→40 | 4.3902 | 2.4618 | 1.0129 | 3.8644 | 1.6243 | -0.0964 |
| 80→35 | 4.3049 | 2.3590 | 0.9098 | 3.8082 | 1.7032 | 0.1570 |
| 80→30 | 4.0081 | 2.2401 | 0.9170 | 3.8814 | 1.9703 | 0.5989 |
| Dynamic taker T2@40 | 2.8618 | 2.4618 | 1.0129 | 2.0268 | 1.6243 | -0.0964 |
| Hedge H=40 H2 p50 | 3.9919 | 3.7908 | 1.4059 | 3.3775 | 3.1741 | 0.3312 |
| Hedge H=30 H2 p50 | 3.8325 | 3.6312 | 1.4059 | 3.5455 | 3.3426 | 0.3312 |
| Hybrid H40/T40 | 3.9919 | 3.7908 | 1.4059 | 3.3775 | 3.1741 | 0.3312 |
| Dynamic exposure r=50% H40 | 3.4268 | 3.1263 | 1.4059 | 2.7022 | 2.3992 | 0.3312 |

## 6. Fee vs slippage

- **nba**: T1 net 3.9531 vs T2 net 2.4618 · fee drag T1 0.4371 vs T2 0.3999. Slippage (T1−T2) dominates fees.
- **ncaab**: T1 net 3.4139 vs T2 net 1.6243 · fee drag T1 0.4505 vs T2 0.4025. Slippage (T1−T2) dominates fees.

## 7. Break-evens (NBA shown in dashboard for both)

- NBA taker mixture crosses 0 near exit ≈ **25¢** (hold+stop blend, CURRENT fees).
- NBA hybrid vs hold: first p_fill with EV≥hold is **0.2**.

## 8. Season Monte Carlo (ESTIMATED C — not a $50 book)

10k resamples of the **entire frozen universe** × 7 contracts. Units are ¢ × contracts over that resample. This is **not** a $50 sequential season and does **not** enforce max concurrent exposure. Do not read the means as live expectancy.

| Book | NBA mean ¢ | NBA p05 | NBA P(lose) | NCAAB mean ¢ | NCAAB p05 | NCAAB P(lose) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Hold | 24326 | 9100 | 0.0041 | 80199 | 52360 | 0.0000 |
| T2@40 | 21093 | 8980 | 0.0024 | 46637 | 24410 | 0.0002 |
| Hybrid H40 p=50% (D) | 32539 | 23069 | 0.0000 | 91098 | 73625 | 0.0000 |
| Conservative T3+fees | 8612 | −4211 | 0.1314 | −2740 | −26516 | 0.5717 |

Hold beats T2@40 on the independent universe resample. Hybrid only wins if the unobserved maker fill rate is assumed.

## 9. Six decision questions

**Q1 Idealized highest EV:** `80→40` NBA net 3.9531 (NCAAB 80→40 3.4139). Evidence C for exact-threshold fills.

**Q2 Moderate highest EV:** `Hedge H=40 H2 p50` NBA net 3.7908. Hedge/hybrid numbers are **D — assumed p_fill**. Among observed-proxy policies, Hold vs T2@40 is the honest fight.

**Q3 Conservative highest EV:** `Hold` NBA net 2.8455. NCAAB conservative taker -0.0964.

**Q4 Least assumption-dependent:** Hold (evidence A) then T2 candle close (B). Hedge p_fill is D.

**Q5 Min execution quality for FIRST80 + stop to beat hold:** NBA T2@40 2.4618 vs hold 2.8455; NCAAB T2@40 1.6243 vs hold 2.8007. A 40-stop needs realized exits close enough to 40 that T2 ≥ hold, or a later/persistent trigger.

**Q6 Balance:** Path edge is measured (A). Taker stops depend on the exit proxy (B/C). Maker hedge can dominate on paper only by assuming fills (D). This experiment does not authorize a live policy.

## 10. Final verdict

```text
FIRST80 PATH EFFECT:           PASS
GROSS ECONOMIC EDGE:           PASS   (ideal 80→40 net 3.9531 / 3.4139 ¢)
MODERATE EXECUTION EDGE:       FAIL vs hold   (T2@40 2.4618 / 1.6243 < hold 2.8455 / 2.8007; still > 0)
CONSERVATIVE EXECUTION EDGE:   FAIL   (T3+fee-stress 1.0129 / -0.0964 ¢)
TAKER EXIT VIABILITY:          LOW CONFIDENCE
MAKER HEDGE VIABILITY:         LOW CONFIDENCE  (fill rate UNOBSERVED)
FEE BURDEN:                    IMMATERIAL vs slippage  (T1−T2 ≈ 1.5–1.8¢; fees ≈ 0.40¢)
PRIMARY REMAINING UNCERTAINTY: IOC realized fill vs candle close; maker fill probability
LIVE DEPLOYMENT:               NOT AUTHORIZED BY THIS EXPERIMENT
```

VAL NBA T2@40 (3.65) slightly beat VAL hold (3.44) and was selected; OOS hold is 6.01 vs that stop 3.44. NCAAB VAL selected T=5 (near-hold); OOS n=84 is `INSUFFICIENT_SAMPLE` and OOS hold 8.10 still beats T=5 (7.13). Do not treat VAL/OOS stop wins as a deployable policy.

## 11. Integrity flags

| Claim | Grade |
| --- | --- |
| FIRST-80 survival | A |
| Trigger-candle exit | B |
| IOC realized fill | C |
| Maker hedge fill probability | D |
| T4 / season Monte Carlo | C |

No lookahead in trigger types. No oracle hedge. NCAAB OOS is small.

Do not arm. Do not modify live trading.

