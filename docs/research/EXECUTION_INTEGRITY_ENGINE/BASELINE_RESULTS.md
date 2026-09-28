# DRE_BASELINE_V1 results

This is the **reference state** of the current hybrid / FIRST80 stack. It is not a deterioration-rate engine.

| Sport | n | Dates | TRAIN / VAL / OOS | Reproduction |
|---|---:|---|---|---|
| NBA | 1230 | 2025-10-10–2026-06-13 | {'TRAIN': 504, 'VALIDATION': 483, 'OOS': 243} | 1230 hold=2.8455 stop=4.3902 v1=5.1707 gate=PASS |
| NCAAB P5 | 721 | 2025-11-03–2026-04-04 | {'VALIDATION': 555, 'TRAIN': 137, 'OOS': 29} | 721 hold=3.3564 stop=4.3551 v1=4.3551 gate=PASS |

P5 OOS is small — treat as `INSUFFICIENT_SAMPLE` when n<40.

## Counterfactuals (FULL mean ¢)

| Book | NBA | P5 |
|---|---:|---:|
| HOLD | 2.8455 | 3.3564 |
| 80→40 | 4.3902 | 4.3551 |
| HYBRID E1 | 4.3252 | 4.1331 |
| THEORETICAL @40 | 5.1707 | 4.3551 |
| ACTUAL | NOT_AVAILABLE | NOT_AVAILABLE |

## Waterfall

NBA: hold 2.845528 + stop 1.544715 = 80→40 4.390244 + E1 Δ -0.065041 = E1 4.325203. Gap fiction 0.845528.

P5: hold 3.356449 + stop 0.998613 = 80→40 4.355062 + E1 Δ -0.221914 = E1 4.133148. Gap fiction 0.221914.
