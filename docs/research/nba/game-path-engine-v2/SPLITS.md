# Chronological splits — frozen before OOS

Cuts are on `game_date`. Copied from the frozen execution audit.

```text
TRAIN       game_date ≤ 2025-12-31     BUILD
VALIDATION  2026-01-01 .. 2026-03-15   CHOOSE (at most one frozen candidate)
OOS         game_date > 2026-03-15     VERIFY once
```

## Roles

```text
TRAIN       Discover univariate structure, H1–H7, interactions, tree leaves,
            logistic/elastic-net, quantile edges, sizing *parameters are not
            optimized here against OOS*.

VALIDATION  Confirm direction and economics. Choose ≤1 filter or NO FILTER.
            No Platt. No new thresholds. No new features.

OOS         One untouched pass. If it fails: REJECT. Do not retune.
```

## Season-regime slices (robustness, not selection)

On TRAIN+VAL combined, after a candidate is frozen:

```text
early   game_date ≤ 2025-12-31   (TRAIN)
middle  2026-01-01 .. 2026-02-14
late    2026-02-15 .. 2026-03-15
```

OOS is not sliced for selection.

## Primary analysis subset

Tests that need game path use `alignment_confidence ∈ {HIGH, MEDIUM}`.
The full 1,230-row ledger is always written. Exclusion-bias `q` is reported
before any filter is discussed.
