# NCAAB 2H first 10 FIRST75 — why it differs, and post-τ β / vol

```
LIVE EXECUTION = FALSE
CANDLE PATH ≠ ACTUAL FILL
OBSERVED CALIBRATION DEVIATION ≠ PROVEN MARKET INEFFICIENCY
NO OTHER-SIDE RULE AUTHORIZED
```

Does not change live FIRST01. Does not retune FIRST75 / T40.
Does not authorize fading H2_1 or buying the opposite contract.

## 1. Why H2_1 looks different (locked four-cell, before this path scan)

NCAAB P5 **2H first 10 FIRST75** is the only asked row whose Wilson
interval on P(W) **excludes 75%**: 110/133 = **82.71%**, Wilson
75.39–88.19, two-sided p = 0.045. s_W = 99/110 = **90.00%**.
S = 99/133 = **74.44%**. s_L = 0/23.

That is not just “NCAAB is different.” Same-sport **1H second 10**
is 152/204 = **74.51%** (includes 75%), s_W = 82.89%, S = 61.76%.

Selection, not a retune: FIRST75 is the *first* tradable cross of 75¢.
An H2_1 FIRST75 means this yes **never first-crossed 75 in the first
half**. It is a late-arriving 75¢ favorite. Q2/Q3 and H1_2 are
earlier first-crosses. Those are different populations.

Split caveat (FIRST75 H2_1 winners among settled): IN_SAMPLE 21/24,
VALIDATION 83/103, OOS **6/6**. The 82.7% is not an OOS fact.
One of six asked rows was always going to be the tail. Multiple-testing
applies.

## 2. What this scan measures

After τ = FIRST75 timestamp, on quality minute closes:

- σ = stdev of Δyes_bid (cents) in the first **600s** (W600) and on the full remaining path
- range and max adverse excursion down from the entry close
- β = OLS slope of Δbid_cents on Δmargin_points on consecutive quality
  minutes whose snapped score changed (same snap as clock alignment)

W600 is the comparable window (H2_1 is a 10-minute clock bin).
FULL mixes remaining game length and is descriptive only.

## 3. Slice results (W600)

| Slice | N | P(W) | P(T40) | σ Δbid ¢ mean | range ¢ mean | MAE down ¢ | β ¢/pt | n pairs | mean Δbid | score against |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| NCAAB 2H first 10 | 133 | 82.71% | 25.56% | 3.534 | 12.767 | 6.744 | 1.892 | 484 | -3.641 |
| NCAAB 1H second 10 | 204 | 74.51% | 38.24% | 2.471 | 9.544 | 4.721 | 1.491 | 619 | -2.973 |
| NBA 2Q | 318 | 76.10% | 34.28% | 2.206 | 8.572 | 4.399 | UNRELIABLE | 1011 | -0.622 |
| NBA 3Q | 258 | 74.42% | 35.27% | 3.477 | 13.446 | 6.640 | UNRELIABLE | 939 | -0.978 |
| WNBA 2Q | 128 | 82.03% | 28.91% | 2.373 | 7.844 | 3.812 | 1.257 | 358 | -2.663 |
| WNBA 3Q | 85 | 82.35% | 30.59% | 3.851 | 14.000 | 7.165 | 1.869 | 329 | -3.847 |

| **H2_1 target** | 133 | 82.71% | 25.56% | 3.534 | 12.767 | 6.744 | 1.892 | 484 | -3.641 |
| Rest of asked five (vol ok; β if NBA usable) | 993 | 76.64% | 34.34% | 2.754 | 10.409 | 5.208 | UNRELIABLE | 3256 | -1.814 |
| NCAAB H1_2 ∪ WNBA Q2∪Q3 | 417 | 78.42% | 33.81% | 2.723 | 9.930 | 4.940 | 1.519 | 1306 | -3.111 |
| NBA+WNBA Q2∪Q3 | 789 | 77.19% | 33.33% | 2.828 | 10.632 | 5.335 | UNRELIABLE | 2637 | -1.511 |

## 4. How much more sensitive?

Ratios are H2_1 / comparator on W600 means. **1.00 = same.**
Primary β comparators exclude NBA when NBA snap β is UNRELIABLE
(collapsed pairing from 0-filled scoreHome). Vol does not use PBP
and remains valid on all rows.

| Comparator | σ ratio | β ratio | MAE-down ratio |
|---|---:|---:|---:|
| NCAAB H1_2 (same stack) | 1.430 | 1.269 | 1.429 |
| NCAAB H1_2 ∪ WNBA Q2∪Q3 | 1.298 | 1.246 | 1.365 |
| Rest of asked five | 1.283 | — | 1.295 |
| NBA+WNBA Q2∪Q3 | 1.250 | — | — |

H2_1 entry margin (yes − opponent) mean 5.887, median 6.000 (n=133). H1_2 mean 6.358.

A β ratio > 1 means a point of score moved the yes close more in H2_1
than in the comparator, on this candle pairing. That is not a fill,
not L2, and not proof the other side is +EV.

## 5. Other-side hypothesis (not a rule)

If H2_1 yes overreacts to score against it, the opposite contract
(~25¢ at a 75¢ yes) would be the candidate fade. The descriptive
object is mean Δyes_bid on minutes where snapped margin fell, W600.
Compare to usable β slices only.

H2_1: -3.641¢ (n=231).
NCAAB H1_2: -2.973¢ (n=301).
NCAAB H1_2 ∪ WNBA Q2∪Q3: -3.111¢ (n=639).

A more negative number is a larger yes drop after a bad score.
H2_1 matching WNBA 3Q (another late-clock high-vol slice) is not
the same as a unique H2_1 fade. That still needs OOS, fees, the
other-side fill, and a locked protocol. It is **not** authorized
as a trade.

## 6. What this is not

- Not a live order, fill, or realized P&L.
- Not proof of an inefficient delta or a fade edge.
- Not a retune of FIRST75.
- Not MLB FIRST01.
- H2_1 OOS n=6. Do not deploy on this slice.

**LIVE DEPLOYMENT: NOT AUTHORIZED**

