# VOLATILITY NORMALIZATION FAILS AS A RECOVERY MECHANISM

**QUIET DOES NOT MEAN REVERSION** — H2 opening adverse-delta
normalization. Archived rejected mechanism.

```
RESULT: NEGATIVE
QUIET TAPE = NEW PRICE ACCEPTANCE
VOLATILITY NORMALIZATION ≠ PRICE RECOVERY
CLOSE_5 = DESCRIPTIVE OBSERVATION
DO NOT HUNT A PROFITABLE SUBSET
LIVE EXECUTION = FALSE
```

Completely separate from FIRST75. Does not change live FIRST01.
Candle path ≠ fill. P5 vs P5 only.

Freeze: `CONCLUSION.md`. Object: `SPEC.md`.

## Universe

- P5 vs P5 games (gate): **849**
- Two-sided markets: 849
- MATCHED ESPN PBP: 847
- Games with ≥1 H2-open i* bar: **835**
- H2-open bar events: **8157**

## 1. Event population (no rule selected)

Every quality H2-open minute with a unique adverse contract i*.
Primary shock is a *flag*, not the universe.

| Slice | N bars | N games | mean ΔP ¢ | R5 ¢ | R10 ¢ | P(R5>0)% | P(vol_norm)% | P(W)% |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| all H2-open bars with unique i* | 8157 | 835 | -2.466 | -0.099 | -0.064 | 42.7 | 52.6 | 45.0 |
| primary: |ΔP|>H1 p80 and ΔP<0 | 1892 | 623 | -6.311 | 0.142 | 0.107 | 45.6 | 45.6 | 44.6 |
| control: ΔP<0 and |ΔP|≤H1 p80 | 4608 | 795 | -1.792 | 0.002 | 0.039 | 44.6 | 53.6 | 45.9 |
| shock ∩ |ΔM|∈[1,4] ∩ deterioration | 1419 | 575 | -6.390 | -0.061 | -0.063 | 44.5 | 47.0 | 43.7 |
| shock ∩ bounded ∩ prop 25–50% ∩ |M_pre|≥4 | 510 | 330 | -6.233 | -0.492 | -0.648 | 42.5 | 48.5 | 45.3 |
| ordinary ∩ |ΔM|∈[1,4] ∩ deterioration | 1688 | 688 | -2.114 | -0.584 | -0.739 | 40.3 | 61.6 | 44.2 |
| first primary shock per game | 623 | 623 | -6.339 | -0.445 | -0.424 | 41.4 | 37.8 | 45.7 |

## 2. Object B — price after the bar

R_h = later quality yes_bid_close minus the shock-minute close.
Not a fill. Comparable control is ordinary adverse (ΔP<0, not above p80).

| Horizon | Shock mean ¢ | Control mean ¢ | Shock − control |
|---|---:|---:|---:|
| +1m | -0.004 | -0.050 | 0.046 |
| +2m | -0.051 | -0.111 | 0.060 |
| +3m | 0.040 | 0.010 | 0.030 |
| +5m | 0.142 | 0.002 | 0.139 |
| +10m | 0.107 | 0.039 | 0.069 |

H1 is descriptively favored if Shock − control > 0 (better subsequent
bid path after an abnormal adverse bar than after an ordinary one).
That is not proof of a temporary component, and not a trade.

## 3. Object A — does volatility normalize?

- P(vol_norm | primary shock) = 45.6%
- P(vol_norm | ordinary adverse) = 53.6%

vol_norm := mean |ΔP| over the next 5 minutes ≤ that contract's H1 mean |ΔP|.

## 4. Object C — recovery only when vol normalizes?

| Condition | N | R5 ¢ | R10 ¢ | P(R5>0)% |
|---|---:|---:|---:|---:|
| shock ∧ vol_norm | 862 | -0.495 | -0.600 | 40.8 |
| shock ∧ ¬vol_norm | 1028 | 0.685 | 0.705 | 49.6 |

If R | (shock ∧ ¬norm) ≥ R | (shock ∧ norm), volatility quieting is
*not* the mechanism of recovery (the market may have finished
repricing and then gone quiet at the new level).

## 5. Close bands (all frozen; none selected)

| Band | Shock N | Shock R5 | Ordinary N | Ordinary R5 | Δ R5 |
|---|---:|---:|---:|---:|---:|
| CLOSE_5 | 1137 | 0.313 | 2004 | -0.078 | 0.391 |
| CLOSE_7 | 1434 | 0.209 | 2626 | 0.003 | 0.205 |
| CLOSE_10 | 1693 | 0.150 | 3334 | 0.007 | 0.143 |
| CLOSE_12 | 1804 | 0.121 | 3701 | 0.033 | 0.088 |

Do not promote the largest Δ R5 to a structural close threshold.

## 6. Calendar splits (descriptive; no selection)

IN_SAMPLE ≤ 2025-12-31; VALIDATION ≤ 2026-03-15; else OOS.

| Split | Shock N | Shock R5 | Ordinary N | Ordinary R5 | Δ R5 |
|---|---:|---:|---:|---:|---:|
| IN_SAMPLE | 317 | -0.110 | 861 | -0.144 | 0.034 |
| VALIDATION | 1486 | 0.289 | 3603 | 0.031 | 0.259 |
| OOS | 89 | -1.427 | 144 | 0.167 | -1.594 |

## 7. Reading (descriptive; not a rule)

Primary shocks are large: mean ΔP **-6.311¢** (median -6.000). Subsequent R5 is **0.142¢** versus 0.002¢ for ordinary adverse (Δ ≈ 0.139¢). R5 sd is 8.484¢. Median R5 is 0. That is not a recoverable temporary component.

The tighter, intended information filter is *worse* for the bounce:
- shock ∩ bounded deterioration: R5 -0.061¢ (n=1419)
- plus prop 25–50% and |M_pre|≥4: R5 -0.492¢ (n=510)
- first primary shock in the game: R5 -0.445¢ (n=623)

Object A: vol is *less* likely to return to the H1 mean after a
primary shock than after an ordinary adverse bar (45.6% vs 53.6%).

Object C rejects the causal chain. After a primary shock:
- vol_norm: R5 -0.495¢ (n=862)
- ¬vol_norm: R5 0.685¢ (n=1028)

When the tape quiets, the damaged contract does **not** reclaim
the shock. Quiet looks like a finished reprice. Continued vol
is where the small positive mean lives — not a normalization bounce.

CLOSE_5 has the largest Δ R5 among frozen close bands. That is
**not** selected. OOS primary Δ R5 is negative. Do not promote
a close threshold from this table.

## 8. What this is not

- Not FIRST75, FIRST80, T40, or Lebronner.
- Not an authorized entry rule or fade.
- Not evidence that vol normalization *causes* price recovery.
- Not a fill, fee, or live P&L.
- Not MLB FIRST01. Not W9.

**LIVE DEPLOYMENT: NOT AUTHORIZED**

