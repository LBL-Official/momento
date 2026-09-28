# FIRST80_ENTRY_QUALITY_AUDIT_V1

Research only. **LIVE EXECUTION CHANGED: FALSE.**

```text
CANDLE ENTRY-ACCESSIBILITY PROXY  ≠  ACTUAL 80¢ MAKER FILL
PATH PHENOMENON  ≠  ENTRY ACCESSIBILITY
PBP_JOIN = UNAVAILABLE
GAME_CLOCK = UNAVAILABLE
Late buckets use minutes-to-Kalshi-close, not NBA/NCAAB game clock.
80/40 EV = CANDLE PATH PAYOFF, NOT ACTUAL EXECUTION P&L
```

**VERDICT: A**

ROBUST TO ENTRY-ACCESSIBILITY FILTERS. Gradual / HIGH_ACCESS subsets keep ~73% survival; ≥20¢ jump-throughs are ~2% of each universe and do not carry the result.

Does not modify FIRST01, Risk, Execution, hedge V1–V3, liquidation, or Game Path.
FIRST-80 definition is frozen. This audit does not retune it.
Filters were defined a priori. This is accessibility validation, not strategy search.

## After removing jump-throughs, what does survival look like?

NBA: **73.98% → 73.59%** after dropping jump≥20¢ (n 1230 → 1208). HIGH_ACCESS **74.07%** (n=509).
NCAAB: **73.14% → 72.91%** after dropping jump≥20¢ (n 4099 → 3990). HIGH_ACCESS **72.61%** (n=1654).

The frozen 73–74% path result is not being carried by 53¢→93¢ one-minute jumps.
Those events exist, they win more often in a small sample, and they are ~2% of each universe.

## Reproduction

| Sport | N | Survivors | Close-40 | Leaks | Survival | Gate |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| NBA | 1230 | 910 | 320 | 0 | 73.98% | PASS |
| NCAAB | 4099 | 2998 | 1099 | 2 | 73.14% | PASS |

## Heart table — accessibility filters (a priori, not P&L-fit)

| Filter | NBA N | NBA Survival | NCAAB N | NCAAB Survival | Interpretation |
| --- | ---: | ---: | ---: | ---: | --- |
| Frozen baseline | 1230 | 73.98% | 4099 | 73.14% | Frozen FIRST-80 path result |
| Remove jump ≥10¢ | 1084 | 73.06% | 3442 | 72.20% | Drops moderate+ jumps; survival stays ~72–73% |
| Remove jump ≥20¢ | 1208 | 73.59% | 3990 | 72.91% | Core jump-through exclusion |
| Remove jump ≥30¢ | 1225 | 73.88% | 4066 | 73.09% | Extreme jump-throughs only |
| Remove close ≥90 | 1211 | 73.58% | 4020 | 72.79% | Entry-minute close already far above 80 |
| Remove extreme overshoots | 1209 | 73.53% | 4006 | 72.77% | Close≥90 or jump≥30 |
| Remove 0–15m-to-close AND jump≥20 (clock proxy, not game clock) | 1224 | 73.86% | 4098 | 73.13% | Not official Q4/final-2-min clock |
| Gradual approach only | 668 | 72.90% | 2213 | 72.21% | Jump<10, ≥2 up-steps in 5m, prior 5m level <80 where observed |
| High accessibility proxy only | 509 | 74.07% | 1654 | 72.61% | Jump<10, close 80–85, persist≥2 in 78–85, ≥2 up-steps |

CANDLE PATH PAYOFF, not execution P&L. +20 survive / −40 stop / −80 leak.

## Question 1 — How did price arrive at 80?

Primary class is mutually exclusive. Flags may stack on the same event.

| Class | NBA N | NBA % univ | NBA survival | NCAAB N | NCAAB % univ | NCAAB survival |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| GRADUAL_APPROACH | 684 | 55.61% | 73.68% | 1939 | 47.30% | 71.07% |
| MODERATE_REPRICE | 400 | 32.52% | 72.00% | 1503 | 36.67% | 73.65% |
| SUDDEN_REPRICE | 124 | 10.08% | 78.23% | 547 | 13.34% | 77.33% |
| LARGE_JUMP_THROUGH | 11 | 0.89% | 90.91% | 66 | 1.61% | 80.30% |
| EXTREME_JUMP_THROUGH | 5 | 0.41% | 100.00% | 43 | 1.05% | 83.72% |
| LATE_GAME_EVENT_SHOCK | 6 | 0.49% | 100.00% | 1 | 0.02% | 100.00% |

Jump ≥10¢: NBA 146/1230 (11.87%). NCAAB 657/4099 (16.03%).
Jump ≥20¢: NBA 22/1230 (1.79%). NCAAB 109/4099 (2.66%).
Jump ≥30¢: NBA 5/1230 (0.41%). NCAAB 33/4099 (0.81%).

## Question 2 — Immediate overshoot of 80

Entry-minute **yes_bid_close**:

| Close | NBA N | NBA survival | NCAAB N | NCAAB survival |
| --- | ---: | ---: | ---: | ---: |
| 80–82 | 762 | 71.92% | 2352 | 69.73% |
| 82–85 | 342 | 74.85% | 1274 | 75.35% |
| 85–90 | 107 | 81.31% | 394 | 82.74% |
| 90+ | 19 | 100.00% | 79 | 91.14% |

Entry-minute **yes_bid_high**:

| High | NBA N | NBA survival | NCAAB N | NCAAB survival |
| --- | ---: | ---: | ---: | ---: |
| 80–82 | 652 | 72.09% | 1890 | 69.52% |
| 82–85 | 412 | 73.06% | 1523 | 74.13% |
| 85–90 | 139 | 81.30% | 576 | 79.34% |
| 90+ | 27 | 96.30% | 110 | 89.09% |

Closes that stay near 80 (80–82): NBA 71.92% (n=762); NCAAB 69.73% (n=2352).
Closes already at 90+: NBA 100.00% (n=19); NCAAB 91.14% (n=79). Highest rates sit in the overshoot tail, but that tail is 1.5–1.9% of each universe.

## Question 3 — Late game

Official period / remaining game clock is **UNAVAILABLE**. PBP_JOIN = UNAVAILABLE. No frozen FIRST-80 ticker-to-play-by-play join exists for this audit. NBA Game Path V4 has NBA.com pbp_v3 for a different research stream; that join was not validated against the frozen FIRST-80 candidate set and is not used here. NCAAB 2025–2026 warehouse has no joinable normalized PBP parquet. Event labels are not invented. GAME_CLOCK is unavailable; late buckets are minutes-to-Kalshi-close.

Minutes-to-Kalshi-close proxy (not game clock):

- NBA 0–15m to close: 12 / 1230
- NCAAB 0–15m to close: 3 / 4099
- NBA 15–30m to close: 50 / 1230
- NCAAB 15–30m to close: 52 / 4099

This is not Q4 / final-2-minutes of basketball. It is time until the Kalshi contract ends.

## Question 4 — Late contract AND large jump

- NBA 0–15m-to-close AND jump≥20¢: **6** events
- NCAAB 0–15m-to-close AND jump≥20¢: **1** events

These cells are too small to explain 73–74%. They also cannot stand in for a buzzer-beater clock.

## Question 5 — Baseline vs high-accessibility / gradual

- NBA baseline 73.98% (n=1230) vs HIGH_ACCESS 74.07% (n=509) vs gradual 72.90% (n=668)
- NCAAB baseline 73.14% (n=4099) vs HIGH_ACCESS 72.61% (n=1654) vs gradual 72.21% (n=2213)

HIGH_ACCESS (frozen before OOS, not fit to P&L): {"max_jump_cents": 10, "max_close_cents": 85, "min_persist_78_85": 2, "min_up_steps_5m": 2}

## Question 6 — Does removing jump-throughs change 73–74%?

No. Not materially.

- NBA 73.98% → 73.59% (Δ +0.39 pp) after removing jump≥20¢.
- NCAAB 73.14% → 72.91% (Δ +0.23 pp).

Wilson 95% CIs still cover the original 73–74% region.

## Question 7 — Are the highest win rates in extreme shocks?

Yes, the **highest** rates sit in the shock tail. No, the **headline 73–74% is not composed of that tail.**

ENTRY_SHOCK_SCORE quintiles (z of jump, range, overshoot, 5m acceleration; edges frozen on TRAIN):

| Q | NBA N | NBA survival | NBA mean jump | NCAAB N | NCAAB survival | NCAAB mean jump |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Q1 | 233 | 74.25% | 1.3991 | 970 | 69.18% | 1.9979 |
| Q2 | 278 | 71.94% | 2.777 | 882 | 71.54% | 3.7256 |
| Q3 | 240 | 73.33% | 4.25 | 855 | 73.68% | 5.4538 |
| Q4 | 254 | 72.05% | 6.2244 | 699 | 73.82% | 7.5908 |
| Q5 | 225 | 79.11% | 11.8889 | 693 | 79.37% | 14.0606 |

NBA Q5 79.11% vs Q1 74.25%. NCAAB Q5 79.37% vs Q1 69.18%.
Q1 (lowest shock) remains ~70–74%. That is the robustness result.

## Question 8 — How much of 73–74% depends on inaccessible entries?

Candles cannot support a maker-fill percentage. L2, queue, and depth are unobserved for **100%** of the universe.
Do not treat HIGH_ACCESS failure as proof of inaccessibility. HIGH_ACCESS is a strict persist/approach rule;
most failures are missing persist or approach steps, not 53→93 jumps.

- Jump ≥20¢ share of universe: NBA 22/1230 = 1.79%; NCAAB 109/4099 = 2.66%.
- Survivors among remaining jump<20: NBA 889/1208; NCAAB 2909/3990.
- HIGH_ACCESS coverage: NBA 509/1230 = 41.4%; NCAAB 1654/4099 = 40.4%. Survival in that subset matches baseline.

The share of the original result that is **structurally jump-through** is about 2–3% of entries, not the majority.
The share whose **actual 80¢ maker fill is unknown** is 100%. Those are different statements.

## Question 9 — Strongest candle conclusion

**VERDICT A — ROBUST TO ENTRY-ACCESSIBILITY FILTERS.**

Two separate statements:

1. **PATH PHENOMENON = STRONG.** After removing ≥20¢ one-minute jumps, survival is still ~73.6% NBA and ~72.9% NCAAB. Gradual and HIGH_ACCESS subsets stay in the same band.
2. **80¢ MAKER ENTRY ACCESSIBILITY = PARTIALLY UNKNOWN.** Historical L2 is unavailable. A candle that prints 80 inside a 53→93 bar is not a fill. Those bars are rare here.

Not C: jump-through removal does not drop survival by a material amount.
Not D: the remaining gradual/near-80 universe still shows a ~70–74% close-40 survival path.

## TRAIN / VALIDATION / OOS (HIGH_ACCESS frozen; not retuned)

| Split | Universe | NBA N | NBA survival | NCAAB N | NCAAB survival |
| --- | --- | ---: | ---: | ---: | ---: |
| TRAIN | baseline | 504 | 71.83% | 958 | 75.26% |
| TRAIN | remove jump≥20 | 493 | 71.40% | 916 | 74.67% |
| TRAIN | HIGH_ACCESS | 221 | 70.14% | 337 | 73.89% |
| VALIDATION | baseline | 483 | 75.57% | 3057 | 72.29% |
| VALIDATION | remove jump≥20 | 477 | 75.26% | 2992 | 72.16% |
| VALIDATION | HIGH_ACCESS | 201 | 78.11% | 1282 | 72.31% |
| OOS | baseline | 243 | 75.31% | 84 | 79.76% |
| OOS | remove jump≥20 | 238 | 74.79% | 82 | 80.49% |
| OOS | HIGH_ACCESS | 87 | 74.71% | 35 | 71.43% |
| FULL | baseline | 1230 | 73.98% | 4099 | 73.14% |
| FULL | remove jump≥20 | 1208 | 73.59% | 3990 | 72.91% |
| FULL | HIGH_ACCESS | 509 | 74.07% | 1654 | 72.61% |

NCAAB OOS n is small (84 baseline). Do not overweight that cell.

## Jump threshold sweep (remaining universe after removing jump ≥ T)

| T | NBA remaining N | NBA survival | NBA mean T+1..T+10 close | NCAAB remaining N | NCAAB survival | NCAAB mean T+1..T+10 close |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 5 | 684 | 73.68% | 80.9051 | 1939 | 71.07% | 80.8663 |
| 10 | 1084 | 73.06% | 81.4654 | 3442 | 72.20% | 81.6725 |
| 15 | 1192 | 73.57% | 81.8062 | 3878 | 72.85% | 81.8489 |
| 20 | 1208 | 73.59% | 81.8318 | 3990 | 72.91% | 81.9329 |
| 25 | 1218 | 73.81% | 81.9183 | 4034 | 72.98% | 81.9759 |
| 30 | 1225 | 73.88% | 81.9306 | 4066 | 73.09% | 82.0133 |

## Remaining execution unknowns

- Actual 80¢ maker fill, queue, depth: **UNOBSERVED**
- Official game clock / period: **UNAVAILABLE**
- Play-by-play event at the jump: **UNAVAILABLE** (see `pbp_join_unavailable.json`)
- Fees, mid, L2: not invented

LIVE EXECUTION CHANGED: FALSE

