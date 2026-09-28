# MLB FIRST80 — inning × score-differential tensor

Research only. Does not change live trading. Does not invent L2 or gamePk.

```
LIVE EXECUTION = FALSE
CANDLE PATH ≠ ACTUAL FILL
```

Frozen FIRST80 from `research/mlb_first80_80_40_v1/candidates.json` (n=4,303).
State at entry = last completed StatsAPI play with `endTime ≤ first_80_timestamp`.
Lead = FIRST80 yes-team score − opponent (ticker suffix vs home/away).
Observed alias only: AZ ↔ ARI. Trailing-`2` Kalshi events are not mapped to game 1.

---

## 0. Identity (frozen close-stop)

- FIRST80 settled: **4,303** (expected 4,303)
- Close-40 survivors (WIN ∧ ¬T40): **3,326**
- Close-40 stops: **977**
- Close-stop win rate: **77.2949%**

## 1. PBP coverage

- Mapped + snapped (usable tensor): **4,235** (98.4197% of FIRST80)
- Unaligned (no unique gamePk, missing PBP, or yes-team side unknown): **68**
- Pregame FIRST80: **0**
- Postgame FIRST80: **37**
- Crosswalk method: foundation rejoin + unique observed abbr concat for new Finals

## 2. Overall (aligned only vs all FIRST80)

| Universe | Model | n | Win rate | EVN ¢ | Gross EV R |
|---|---|---:|---:|---:|---:|
| all FIRST80 | all fills + close-stop | 4,303 | 77.2949% | 6.1862 | 0.3188 |
| aligned PBP | all fills + close-stop | 4,235 | 77.3554% | 6.223 | 0.3207 |
| all FIRST80 | all fills + wick-stop | 4,303 | 60.9807% | -3.7393 | -0.1706 |
| aligned PBP | all fills + wick-stop | 4,235 | 61.0862% | -3.6752 | -0.1674 |
| all FIRST80 | HIGH + close-stop | 2,219 | 74.6282% | 4.5638 | 0.2388 |
| aligned PBP | HIGH + close-stop | 2,189 | 74.7373% | 4.6302 | 0.2421 |
| all FIRST80 | HIGH + wick-stop | 2,219 | 66.1109% | -0.6182 | -0.0167 |
| aligned PBP | HIGH + wick-stop | 2,189 | 66.286% | -0.5116 | -0.0114 |

Wick-stop remains the MLB-specific failure: all-fills and HIGH wick-stop stay negative on the full frozen universe, unlike the basketball first80strat notebooks.

## 3. Inning marginal (aligned + pregame/postgame/unaligned)

Close-stop EVN vs wick-stop EVN. n is the same rows; only the stop model changes.

| Inning | n | Close win | Close EVN ¢ | Wick win | Wick EVN ¢ |
|---|---:|---:|---:|---:|---:|
| 1 | 489 | 75.4601% | 5.0699 | 63.8037% | -2.0218 |
| 2 | 494 | 76.3158% | 5.5905 | 63.7652% | -2.0453 |
| 3 | 608 | 71.875% | 2.8887 | 56.7434% | -6.3173 |
| 4 | 545 | 76.3303% | 5.5993 | 61.8349% | -3.2197 |
| 5 | 573 | 81.3264% | 8.639 | 63.0017% | -2.5097 |
| 6 | 530 | 76.2264% | 5.5362 | 59.6226% | -4.5656 |
| 7 | 413 | 80.1453% | 7.9204 | 60.7748% | -3.8646 |
| 8 | 416 | 80.2885% | 8.0075 | 59.1346% | -4.8625 |
| 9 | 61 | 83.6066% | 10.0262 | 57.377% | -5.9318 |
| 10+ | 69 | 78.2609% | 6.7739 | 56.5217% | -6.4522 |
| POSTGAME | 37 | 100.0% | 20.0 | 81.0811% | 8.4897 |
| UNALIGNED | 68 | 73.5294% | 3.8953 | 54.4118% | -7.7359 |

## 4. Lead marginal (FIRST80-team run differential)

| Lead | n | Close win | Close EVN ¢ | Wick win | Wick EVN ¢ |
|---|---:|---:|---:|---:|---:|
| -1 | 10 | 80.0% | 7.832 | 70.0% | 1.748 |
| 0 | 219 | 72.1461% | 3.0537 | 59.8174% | -4.4471 |
| +1 | 1,163 | 77.1281% | 6.0847 | 61.5649% | -3.3839 |
| +2 | 1,475 | 76.7458% | 5.8521 | 61.4915% | -3.4286 |
| +3 | 956 | 77.1967% | 6.1264 | 58.159% | -5.4561 |
| +4+ | 412 | 83.2524% | 9.8108 | 65.534% | -0.9691 |
| NA | 68 | 73.5294% | 3.8953 | 54.4118% | -7.7359 |

## 5. Tensor — close-stop EVN ¢ (n in parentheses)

Cells with n < 20 are noisy. Do not retune live 80/81/83/89 from a sparse cell.

| Inning \ Lead | -4+ | -3 | -2 | -1 | 0 | +1 | +2 | +3 | +4+ |
|---|---|---|---|---|---|---|---|---|---|
| 1 | — | — | — | -10.42 (2) | 0.1339 (49) | 4.1287 (92) | 3.493 (129) | 9.0908 (145) | 4.79 (72) |
| 2 | — | — | — | 20.0 (1) | 6.48 (18) | 0.6418 (66) | 2.9012 (153) | 4.4097 (160) | 14.93 (96) |
| 3 | — | — | — | -40.84 (1) | -0.28 (12) | -0.28 (75) | 2.7425 (208) | 2.1575 (208) | 7.715 (104) |
| 4 | — | — | — | 20.0 (1) | 15.6543 (14) | 5.471 (67) | 5.4751 (222) | 3.5374 (170) | 8.8603 (71) |
| 5 | — | — | — | 20.0 (1) | -18.7164 (11) | 4.4664 (94) | 10.4654 (268) | 8.9382 (154) | 11.888 (45) |
| 6 | — | — | — | 20.0 (1) | 4.79 (24) | 3.6549 (134) | 4.79 (276) | 10.3546 (82) | 10.64 (13) |
| 7 | — | — | — | 20.0 (1) | 0.9875 (16) | 7.4908 (214) | 7.6676 (148) | 15.32 (26) | 12.395 (8) |
| 8 | — | — | — | 20.0 (1) | 2.9648 (25) | 8.0811 (342) | 7.832 (40) | 20.0 (7) | 20.0 (1) |
| 9 | — | — | — | — | 8.4114 (21) | 9.86 (30) | 13.24 (9) | 20.0 (1) | — |
| 10+ | — | — | — | 20.0 (1) | 5.3145 (29) | 4.79 (16) | 9.86 (18) | -0.28 (3) | 20.0 (2) |
| POSTGAME | — | — | — | — | — | 20.0 (33) | 20.0 (4) | — | — |

## 6. Tensor — wick-stop EVN ¢ (n in parentheses)

| Inning \ Lead | -4+ | -3 | -2 | -1 | 0 | +1 | +2 | +3 | +4+ |
|---|---|---|---|---|---|---|---|---|---|
| 1 | — | — | — | -10.42 (2) | -7.3159 (49) | -3.1457 (92) | -1.6949 (129) | 1.1186 (145) | -3.66 (72) |
| 2 | — | — | — | 20.0 (1) | 6.48 (18) | -3.0455 (66) | -3.4612 (153) | -6.2373 (160) | 6.0575 (96) |
| 3 | — | — | — | -40.84 (1) | -0.28 (12) | -6.7696 (75) | -5.4475 (208) | -7.7875 (208) | -5.155 (104) |
| 4 | — | — | — | 20.0 (1) | 15.6543 (14) | 3.6549 (67) | -3.0205 (222) | -7.9148 (170) | -3.1363 (71) |
| 5 | — | — | — | 20.0 (1) | -18.7164 (11) | -2.6532 (94) | 0.0227 (268) | -6.4694 (154) | -0.28 (45) |
| 6 | — | — | — | 20.0 (1) | -2.815 (24) | -2.7015 (134) | -5.1296 (276) | -8.1941 (82) | 5.96 (13) |
| 7 | — | — | — | 20.0 (1) | -6.6175 (16) | -3.8811 (214) | -5.487 (148) | 5.96 (26) | -2.815 (8) |
| 8 | — | — | — | 20.0 (1) | -9.2032 (25) | -4.7274 (342) | -7.378 (40) | 11.3086 (7) | 20.0 (1) |
| 9 | — | — | — | — | -3.1771 (21) | -8.392 (30) | -7.04 (9) | 20.0 (1) | — |
| 10+ | — | — | — | -40.84 (1) | -9.371 (29) | -6.6175 (16) | -0.28 (18) | -0.28 (3) | -10.42 (2) |
| POSTGAME | — | — | — | — | — | 7.0945 (33) | 20.0 (4) | — | — |

## 7. Requested example — 2nd inning, +2 lead

Close-stop: n=153 (3.5557% of FIRST80) win=71.8954% EVN=2.9012¢
Wick-stop: n=153 win=61.4379% EVN=-3.4612¢

## 8. Wick-stop cells that stay +EV (n≥20)

If this list is empty, wick-stop does not recover a tradeable MLB pocket at this resolution.

| Inning | Lead | n | Wick win | Wick EVN ¢ | Close EVN ¢ |
|---|---|---:|---:|---:|---:|
| POSTGAME | +1 | 33 | 78.7879% | 7.0945 | 20.0 |
| 2 | +4+ | 96 | 77.0833% | 6.0575 | 14.93 |
| 7 | +3 | 26 | 76.9231% | 5.96 | 15.32 |
| 4 | +1 | 67 | 73.1343% | 3.6549 | 5.471 |
| 1 | +3 | 145 | 68.9655% | 1.1186 | 9.0908 |
| 5 | +2 | 268 | 67.1642% | 0.0227 | 10.4654 |

## 9. What this is not

- Not a live order, fill, or realized P&L.
- Not live MLB FIRST01 / 80/81/83/89.
- Not W9. Candle path ≠ fill. Historical L2 is NOT AVAILABLE.
- Fees: labeled KXMLBGAME quadratic M=0.5 (same as the frozen audit).

**LIVE DEPLOYMENT: NOT AUTHORIZED**

