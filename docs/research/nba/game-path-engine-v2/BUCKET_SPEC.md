# Bucket specification

## Frozen score-differential buckets (a priori)

Applied to `score_differential` at first-80. Not tuned on OOS.

```text
Large deficit     ≤ −15
Medium deficit    −14 .. −8
Small deficit     −7 .. −1
Tie               0
Small lead        +1 .. +7
Medium lead       +8 .. +14
Large lead        ≥ +15
```

## TRAIN-only discovered buckets

Quantile edges for continuous features are estimated on **TRAIN primary
observations only**, then frozen and applied to VALIDATION and OOS.

Default: quintiles for univariate continuous features; for pace:

```text
LOW        ≤ TRAIN p25 of points_per_game_minute
NORMAL     p25–p75
HIGH       p75–p90
EXTREME    > p90
```

Missing pace (elapsed < 60s) → `PACE_UNKNOWN` (not dropped from the ledger).

## Sample-size floors (pre-registered)

| Layer | TRAIN n floor |
| --- | ---: |
| Univariate bucket reported | 40 |
| Two-way interaction tested | 40 |
| Tree leaf | 40 |
| VAL confirmation of a frozen candidate | 30 |
| OOS evaluation of the single frozen candidate | 25 |

Buckets below the floor are stored as `INSUFFICIENT_SAMPLE`, never deleted.

## Hierarchical discovery

1. Univariate (Level 1) — all pre-registered families.
2. Two-way (Level 2) — **only** the six pre-registered interactions with
   economic logic, not all N-choose-K.
3. Depth-2 tree (Level 3) — hypothesis discovery; leaves are not trading
   rules until frozen and tested forward.

## Filter freeze

Search aggressively in TRAIN. Freeze ≤5 candidates that meet TRAIN floors
and `|Δq| ≥ 4pp` **or** a pre-registered H1–H7 definition.

VALIDATION chooses **at most one** candidate (or NO FILTER).

OOS is a single evaluation of that frozen object. No threshold edits.
