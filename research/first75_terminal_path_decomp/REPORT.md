# FIRST75 terminal × path efficiency

Named archive of the EV cases and the p=73% held-path S: `research/lebronner/REPORT.md`.
Successor program (ROLLER +EV / in-production EV stop-path): `research/superasi/`.

Same frozen FIRST75 / FIRST80 / T40 definitions. Clock snapped at the
threshold timestamp. Candle path, not fills. Does not retune either rule.

```
LIVE EXECUTION = FALSE
CANDLE PATH ≠ ACTUAL FILL
OBSERVED CALIBRATION DEVIATION ≠ PROVEN MARKET INEFFICIENCY
```

Model:

`P(W ∩ ¬T40 | FIRST_q) = P(W | FIRST_q) × P(¬T40 | W, FIRST_q)`

`S = P(¬T40 | FIRST_q) = p · s_W + (1 − p) · s_L`

K is the triggering quote (0.75 or 0.80), not a fill.
α = P(W|FIRST_q) − K. Tests are exact binomial vs K
(scipy `binomtest`; one-sided greater / one-sided less / two-sided).

## 1. Terminal calibration  P(W | FIRST75)

| Sport | Slice | N | W | P(W) | Wilson | Clopper–Pearson | α₇₅ (pp) | two-sided p | CI vs 75% |
|---|---|---:|---:|---:|---|---|---:|---:|---|
| WNBA | 2Q | 128 | 105 | **82.0312%** | 74.4782–87.7176 | 74.2681–88.2551 | +7.0312 | 0.06665 | includes K |
| WNBA | 3Q | 85 | 70 | **82.3529%** | 72.9042–89.0037 | 72.5695–89.773 | +7.3529 | 0.1329 | includes K |
| NBA | 2Q | 318 | 242 | **76.1006%** | 71.1194–80.4588 | 71.025–80.6827 | +1.1006 | 0.6977 | includes K |
| NBA | 3Q | 258 | 192 | **74.4186%** | 68.7633–79.3574 | 68.6384–79.6283 | -0.5814 | 0.8293 | includes K |
| NCAAB P5 | 1H second 10 | 204 | 152 | **74.5098%** | 68.1146–79.999 | 67.9537–80.3388 | -0.4902 | 0.8716 | includes K |
| NCAAB P5 | 2H first 10 | 133 | 110 | **82.7068%** | 75.3858–88.1913 | 75.1903–88.7103 | +7.7068 | 0.04463 | excludes K |
| **pooled six** | asked rows | **1126** | **871** | **77.3535%** | 74.8181–79.7028 | 74.7946–79.7685 | **+2.3535** | 0.06824 | includes K |

One-sided tests (pooled FIRST75 vs 0.75): greater p=0.03571, less p=0.9695.

## 2. Winner path  P(¬T40 | W)  and loser path  P(¬T40 | L)

| Sport | Slice | W | W∩¬T40 | s_W | L | L∩¬T40 | s_L |
|---|---|---:|---:|---:|---:|---:|---:|
| WNBA | 2Q | 105 | 91 | **86.6667%** | 23 | 0 | **0.0%** |
| WNBA | 3Q | 70 | 59 | **84.2857%** | 15 | 0 | **0.0%** |
| NBA | 2Q | 242 | 208 | **85.9504%** | 76 | 1 | **1.3158%** |
| NBA | 3Q | 192 | 167 | **86.9792%** | 66 | 0 | **0.0%** |
| NCAAB P5 | 1H second 10 | 152 | 126 | **82.8947%** | 52 | 0 | **0.0%** |
| NCAAB P5 | 2H first 10 | 110 | 99 | **90.0%** | 23 | 0 | **0.0%** |
| **pooled six** | asked rows | **871** | **750** | **86.1079%** | **255** | **1** | **0.3922%** |

s_L Wilson (pooled): 0.0693–2.1876. A 0 here means every measured loser later close-touched 40 (minute-close measurement, not a continuity proof).

## 3. Four-cell joint  (W, L) × (¬T40, T40)

| Sport | Slice | W∩¬T40 | W∩T40 | L∩¬T40 | L∩T40 | sum |
|---|---|---:|---:|---:|---:|---:|
| WNBA | 2Q | 91 | 14 | 0 | 23 | 128 |
| WNBA | 3Q | 59 | 11 | 0 | 15 | 85 |
| NBA | 2Q | 208 | 34 | 1 | 75 | 318 |
| NBA | 3Q | 167 | 25 | 0 | 66 | 258 |
| NCAAB P5 | 1H second 10 | 126 | 26 | 0 | 52 | 204 |
| NCAAB P5 | 2H first 10 | 99 | 11 | 0 | 23 | 133 |
| **pooled six** | asked rows | **750** | **121** | **1** | **254** | **1126** |

## 4. Unconditional objects and the product identity

| Sport | Slice | p | s_W | p·s_W = P(W∩¬T40) | S = P(¬T40) |
|---|---|---:|---:|---:|---:|
| WNBA | 2Q | 82.0312% | 86.6667% | **71.0938%** | **71.0938%** |
| WNBA | 3Q | 82.3529% | 84.2857% | **69.4118%** | **69.4118%** |
| NBA | 2Q | 76.1006% | 85.9504% | **65.4088%** | **65.7233%** |
| NBA | 3Q | 74.4186% | 86.9792% | **64.7287%** | **64.7287%** |
| NCAAB P5 | 1H second 10 | 74.5098% | 82.8947% | **61.7647%** | **61.7647%** |
| NCAAB P5 | 2H first 10 | 82.7068% | 90.0% | **74.4361%** | **74.4361%** |
| **pooled six** | asked rows | 77.3535% | 86.1079% | **66.6075%** | **66.6963%** |

Pooled reconstruction: p·s_W = 0.666075 = observed joint 0.666075. S = 0.666963.

If p were set to K=0.75 and s_W held: joint → 0.6458 (delta -0.0203). **Not a forecast.**

## 5. FIRST75 vs FIRST80 on the same clock slices (not retuned)

| Sport | Slice | p₇₅ | s_W,₇₅ | joint₇₅ | p₈₀ | s_W,₈₀ | joint₈₀ |
|---|---|---:|---:|---:|---:|---:|---:|
| WNBA | 2Q | 82.0312% | 86.6667% | **71.0938%** | 82.6772% | 84.7619% | **70.0787%** |
| WNBA | 3Q | 82.3529% | 84.2857% | **69.4118%** | 84.0336% | 94.0% | **78.9916%** |
| NBA | 2Q | 76.1006% | 85.9504% | **65.4088%** | 85.0318% | 89.5131% | **76.1146%** |
| NBA | 3Q | 74.4186% | 86.9792% | **64.7287%** | 82.069% | 88.6555% | **72.7586%** |
| NCAAB P5 | 1H second 10 | 74.5098% | 82.8947% | **61.7647%** | 84.456% | 87.1166% | **73.5751%** |
| NCAAB P5 | 2H first 10 | 82.7068% | 90.0% | **74.4361%** | 84.8921% | 91.5254% | **77.6978%** |
| **pooled six** | asked rows | 77.3535% | 86.1079% | **66.6075%** | 83.8409% | 89.1019% | **74.7039%** |

FIRST80 null for α is K=0.80, not 0.75.
Pooled FIRST80 four-cell: W∩¬T40=883, W∩T40=108, L∩¬T40=0, L∩T40=191.

## 6. What this is not

- Not a live order, fill, or realized P&L.
- Not proof of a tradable inefficiency.
- A high s_W is not an independent FIRST80 path edge.
- L∩¬T40 = 0 is a minute-close measurement, not proof losers cannot skip 40.
- If 2026–27 terminal p moves toward K, s_W and s_L can move separately.
- Not MLB FIRST01.

**LIVE DEPLOYMENT: NOT AUTHORIZED**

