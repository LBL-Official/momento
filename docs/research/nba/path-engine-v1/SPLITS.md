# Chronological splits — frozen before OOS

Cuts are on `game_date`. Copied from the frozen execution audit. Not taken
from MLB B1 (those dates predate this NBA season).

```text
TRAIN       game_date ≤ 2025-12-31     (~504 first-80, ~131 barrier events)
VALIDATION  2026-01-01 .. 2026-03-15   (~483)
OOS         game_date > 2026-03-15     (~243)
```

## Roles (no dual use of VALIDATION)

```text
TRAIN       → BUILD
              Fit Model 0 / 1 / 2A / 2B.
              Internal chronological cross-validation.
              Optional Platt calibration on TRAIN CV predictions only.

VALIDATION  → CHOOSE
              Compare Model 0 vs 2A vs 2B.
              Apply frozen 2B promotion gate.
              Apply frozen Model 3 VAL gate (tree is not selected unless it passes).
              Choose at most one reject-high-q filter threshold from the
              pre-registered set {0.20, 0.25, 0.30, 0.3333}, or NO FILTER.
              No Platt / isotonic on VALIDATION.
              No threshold search outside the pre-registered set.

OOS         → VERIFY
              One untouched pass of the fully frozen pipeline.
              First time OOS is used for evaluation.
              No retune.
```

## Model 2B promotion gate (frozen)

2B may replace 2A as the frozen logistic only if **all** hold on VALIDATION:

1. `Brier_2B ≤ 0.95 × Brier_2A`
2. `ECE_2B ≤ ECE_2A + 0.005`
3. At least two adjacent predicted-q buckets with n ≥ 30 separate
   (non-overlapping Wilson 95% CIs on actual q, or monotone gap ≥ 8pp)
4. If a reject-high-q filter is implied, acceptance rate ≥ 50% of first-80
   on VALIDATION

Otherwise 2A remains confirmatory; 2B is diagnostic / exploratory.

## Model 3 VAL gate (frozen before any tree is trained for selection)

All four required versus the chosen logistic:

1. `Brier_3 ≤ 0.95 × Brier_logistic`
2. `ECE_3 ≤ ECE_logistic + 0.005`
3. Bucket separation (same rule as 2B)
4. Implied filter acceptance ≥ 50% of first-80 on VALIDATION

If the gate fails, the tree is not selected and is not used on OOS as a
candidate. It may be stored as a labeled diagnostic.

## Production candidate (OOS, all required)

1. Statistical separation of risk buckets (usable n)
2. Calibration: predicted q ≈ actual q in the traded bucket
3. `EV_accepted > EV_unconditional` (~+0.219 R)
4. `AcceptanceRate ≥ 50%` of first-80 opportunities

```text
ProductionUtility = f(Edge, Calibration, AcceptanceRate, Capacity, Drawdown)
```
