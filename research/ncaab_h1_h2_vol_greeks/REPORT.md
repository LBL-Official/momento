# NCAAB P5 — H1 20 vs H2 first 5: vol, empirical greeks, reversion

```
RESEARCH ONLY
EMPIRICAL β ≠ OPTION GREEK
VOLATILITY ≠ MISPRICING
REVERSION STAT ≠ EXECUTABLE EDGE
LIVE EXECUTION = FALSE
```

Discovery only. Not FIRST75. Not W9. Not live FIRST01.
P5 vs P5. Quality yes_bid_close. Candle path ≠ fill.

Windows (clock, not wall):
- **H1_20** — entire first half, IN_PERIOD
- **H1_5** — first 5 minutes of H1 (same-length control)
- **H2_5** — first 5 minutes of H2 (20:00→15:00 remaining)

Greeks here are **candle-path score sensitivities**, not Kalshi
option greeks and not the MLB W9 object.

Games scanned: **840** / 849 P5 (MATCHED PBP 847).
Paired games with both H1_20 and H2_5 σ: **840**.

## 1. Pooled contract-windows

Each side of each game is one observation. Complementary contracts
are not independent; paired ratios below are the fair comparison.

| Window | N sides | N games | mean \|ΔP\| ¢ | σ ΔP ¢ | p80 \|ΔP\| | path range ¢ | β ¢/pt | r(β) | ΔP \| score against | AR1 | sign-flip | R1 after adverse |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| H1_20 | 1680 | 840 | 1.790 | 2.630 | 3.080 | 25.952 | 1.070 | 0.683 | -2.292 | -0.006 | 0.349 | 0.012 |
| H1_5 | 1679 | 840 | 1.776 | 2.424 | 2.822 | 8.644 | 0.871 | 0.643 | -2.053 | -0.125 | 0.342 | 0.333 |
| H2_5 | 1674 | 840 | 1.874 | 2.710 | 3.128 | 12.107 | 1.238 | 0.669 | -2.593 | -0.087 | 0.340 | 0.329 |

Path range is larger in H1_20 because the window is longer.
Minute σ, mean |ΔP|, and β are the comparable objects.

### State-dependent β (close ≤ 10 vs not)

| Window | β close10 | β not close10 |
|---|---:|---:|
| H1_20 | 1.109 | 0.661 |
| H1_5 | 0.867 | — |
| H2_5 | 1.700 | 0.418 |

### Next-minute path after a large adverse bar

| Window | R1 after < −3¢ | R1 after < −5¢ | R1 after < −H1 p80 |
|---|---:|---:|---:|
| H1_20 | 0.012 | 0.209 | 0.116 |
| H1_5 | 0.203 | 0.291 | 0.238 |
| H2_5 | 0.562 | 0.671 | 0.458 |

## 2. Same-game paired ratios (the discovery object)

For each game, average home/away, then H2_5 / H1_20.
**1.00 = same regime.** Median ratio is the headline.

| Contrast | σ median ratio | % σ higher | mean\|ΔP\| ratio | β median ratio | % β higher | AR1 median diff | % more mean-reverting |
|---|---:|---:|---:|---:|---:|---:|---:|
| H2_5 vs H1_20 | 0.952 | 46.9 | 0.965 | 1.025 | 52.4 | -0.085 | 60.5 |
| H2_5 vs H1_5 (same length) | 1.049 | 52.1 | 1.000 | 1.068 | 57.2 | 0.036 | 47.4 |
| H1_5 vs H1_20 | 0.923 | 42.0 | 0.980 | 0.815 | 35.6 | -0.115 | 64.2 |

AR1 more negative = stronger one-minute reversal. A higher
“% more mean-reverting” means the first window flips sign more
than the second. That is still not a trade.

## 3. Calendar splits of the H2_5 / H1_20 σ ratio

| Split | N games | σ median ratio | β median ratio |
|---|---:|---:|---:|
| IN_SAMPLE | 148 | 0.953 | 0.925 |
| VALIDATION | 663 | 0.939 | 1.044 |
| OOS | 29 | 1.150 | 1.406 |

## 4. Discoveries (descriptive)

1. **Typical game: H2 first 5 is not a high-vol expansion vs own H1.**
   Paired median σ(H2_5)/σ(H1_20) = 0.952.
   Only 46.9% of games have louder early H2 than their own first half.
   Pooled *means* are slightly the other way (H2_5 σ 2.71 vs H1_20 2.63)
   because a minority of games have a very loud H2 open. The H1 p80
   shock filter is well-calibrated: the two regimes have almost the
   same p80 (|ΔP| 3.13 vs 3.08).

2. **The rest of H1 is louder than H1’s own first five.**
   H1_5 is the quietest window (σ 2.42, β 0.87). Full-half σ is
   pulled up by minutes 5–20, which is why H2_5/H1_20 < 1 while
   H2_5/H1_5 σ median = 1.049.
   Early H2 is a bit louder than early H1, not louder than all of H1.

3. **The greek that actually moves is close-state delta.**
   Pooled β: H1_5 0.87, H1_20 1.07, H2_5 1.24 ¢/pt.
   Inside |M|≤10: H2_5 β **1.70** vs H1_20 **1.11**.
   Outside that band H2_5 β collapses to 0.42. A 3-point swing
   in a close early-H2 game moves the yes much more than the same
   swing in H1. Part of that is mechanical (less clock left →
   larger win-prob per point). It is not, by itself, mispricing.

4. **One-minute reversion is a short-window effect, not an H2 effect.**
   H1_20 AR1 ≈ 0. Both 5-minute windows are mildly negative
   (H1_5 −0.13, H2_5 −0.09). After any adverse bar, R1 is ~+0.33¢
   in both 5-minute windows and ~0 over the full half. After a
   *large* adverse (−3/−5¢), H2_5 R1 is larger (+0.56 / +0.67)
   than H1_20 (+0.01 / +0.21). That is a next-minute bounce of
   well under a cent per cent of shock. The earlier H2-open shock
   study already showed this does not survive to +5m once the
   move is H1-p80 and bounded, and that vol-normalization is not
   the recovery mechanism.

5. **OOS (n=29) is too small to use.** VAL matches the full-sample
   σ ratio (~0.94). Do not chase the OOS 1.15 / 1.41 pair.

## 5. What this is not

- Not W9. Not option greeks. Not L2.
- Not FIRST75 / FIRST80 / T40 / Lebronner.
- Not an entry rule, fade, or live order.
- Not proof of inefficient delta.

**LIVE DEPLOYMENT: NOT AUTHORIZED**

