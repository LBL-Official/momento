# P(¬T40 | W, FIRST75) on requested clock slices

Research only. Same tradable-cross rule as FIRST80, threshold **75¢**.
T40 is a later tradable `yes_bid_close ≤ 40¢`. Clock is snapped at the
FIRST75 timestamp, not the FIRST80 timestamp.

```
LIVE EXECUTION = FALSE
CANDLE PATH ≠ ACTUAL FILL
OBSERVED CALIBRATION DEVIATION ≠ PROVEN MARKET INEFFICIENCY
```

NCAAB uses the established **P5 vs P5** universe (same as the H1_2 / H2_1
FIRST80 half-bin work). UNALIGNED prints are not in these slices.

## Asked quantity

| Sport | Slice | W | ¬T40 ∩ W | P(¬T40 \| W, FIRST75) | 95% Wilson |
|---|---|---:|---:|---:|---|
| WNBA | 2Q | 105 | 91 | **86.6667%** | 78.8563–91.8887 |
| WNBA | 3Q | 70 | 59 | **84.2857%** | 74.0115–90.9925 |
| WNBA | 2Q ∪ 3Q | 175 | 150 | **85.7143%** | 79.7615–90.1328 |
| NBA | 2Q | 242 | 208 | **85.9504%** | 81.0085–89.7688 |
| NBA | 3Q | 192 | 167 | **86.9792%** | 81.4849–91.0226 |
| NBA | 2Q ∪ 3Q | 434 | 375 | **86.4055%** | 82.8599–89.3123 |
| NCAAB P5 | 1H second 10 | 152 | 126 | **82.8947%** | 76.1164–88.0513 |
| NCAAB P5 | 2H first 10 | 110 | 99 | **90.0%** | 82.9763–94.324 |
| NCAAB P5 | 1H-2nd-10 ∪ 2H-1st-10 | 262 | 225 | **85.8779%** | 81.1411–89.5777 |

## P(W | FIRST75) and terminal residual α₇₅ = P(W|FIRST75) − 0.75

K = 0.75 is the triggering quote, not a fill.
α₇₅ is an observed residual, not a proven inefficiency.

| Sport | Slice | N₇₅ | N_W,₇₅ | P(W \| FIRST75) | 95% Wilson | α₇₅ (pp) | α₇₅ Wilson | CI vs 75% |
|---|---|---:|---:|---:|---|---:|---|---|
| wnba | 2Q | 128 | 105 | **82.0312%** | 74.4782–87.7176 | +7.0312 | -0.5218–+12.7176 | includes 75% |
| wnba | 3Q | 85 | 70 | **82.3529%** | 72.9042–89.0037 | +7.3529 | -2.0958–+14.0037 | includes 75% |
| nba | 2Q | 318 | 242 | **76.1006%** | 71.1194–80.4588 | +1.1006 | -3.8806–+5.4588 | includes 75% |
| nba | 3Q | 258 | 192 | **74.4186%** | 68.7633–79.3574 | -0.5814 | -6.2367–+4.3574 | includes 75% |
| ncaab_p5 | 1H second 10 | 204 | 152 | **74.5098%** | 68.1146–79.999 | -0.4902 | -6.8854–+4.9990 | includes 75% |
| ncaab_p5 | 2H first 10 | 133 | 110 | **82.7068%** | 75.3858–88.1913 | +7.7068 | +0.3858–+13.1913 | excludes 75% |
| **pooled six** | asked rows | **1126** | **871** | **77.3535%** | 74.8181–79.7028 | **+2.3535** | -0.1819–+4.7028 | includes 75% |

Pooled weighting: one observation per FIRST75 event (871/1126), not the unweighted mean of six rates.

## FIRST80 on the same clock slices (control, not retuned)

| Sport | Slice | P(¬T40 \| W, FIRST80) | P(¬T40 \| W, FIRST75) |
|---|---|---|---|
| WNBA | 2Q | 89/105 = **84.7619%** (CI 76.6725–90.3974) | 91/105 = **86.6667%** (CI 78.8563–91.8887) |
| WNBA | 3Q | 94/100 = **94.0%** (CI 87.523–97.2214) | 59/70 = **84.2857%** (CI 74.0115–90.9925) |
| WNBA | 2Q ∪ 3Q | 183/205 = **89.2683%** (CI 84.2864–92.8055) | 150/175 = **85.7143%** (CI 79.7615–90.1328) |
| NBA | 2Q | 239/267 = **89.5131%** (CI 85.2609–92.6444) | 208/242 = **85.9504%** (CI 81.0085–89.7688) |
| NBA | 3Q | 211/238 = **88.6555%** (CI 83.9975–92.0853) | 167/192 = **86.9792%** (CI 81.4849–91.0226) |
| NBA | 2Q ∪ 3Q | 450/505 = **89.1089%** (CI 86.0908–91.5365) | 375/434 = **86.4055%** (CI 82.8599–89.3123) |
| NCAAB P5 | 1H second 10 | 142/163 = **87.1166%** (CI 81.107–91.4169) | 126/152 = **82.8947%** (CI 76.1164–88.0513) |
| NCAAB P5 | 2H first 10 | 108/118 = **91.5254%** (CI 85.1005–95.3318) | 99/110 = **90.0%** (CI 82.9763–94.324) |
| NCAAB P5 | 1H-2nd-10 ∪ 2H-1st-10 | 250/281 = **88.968%** (CI 84.7664–92.1185) | 225/262 = **85.8779%** (CI 81.1411–89.5777) |

## Full-tape FIRST75 (identity / context)

- **WNBA**: 368/446 = **82.5112%** (CI 78.7122–85.755); settled FIRST75 n=566
- **NBA**: 781/915 = **85.3552%** (CI 82.9165–87.4982); settled FIRST75 n=1176
- **NCAAB P5**: 456/538 = **84.7584%** (CI 81.4755–87.5484); settled FIRST75 n=683

NBA full-tape FIRST75 is gated to the 2026-09-04 alpha-decomp count
(1176 settled / 915 winners / 781 never-T40).

## What this is not

- Not a live order, fill, or realized P&L.
- Not proof that FIRST80 has an independent path edge vs FIRST75.
- α₇₅ ≠ executable edge. Observed calibration residual ≠ proven inefficiency.
- Not MLB FIRST01.

**LIVE DEPLOYMENT: NOT AUTHORIZED**

