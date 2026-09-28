# Splits

```text
TRAIN       game_date ≤ 2025-12-31     BUILD
VALIDATION  2026-01-01 .. 2026-03-15   CHOOSE
OOS         game_date > 2026-03-15     VERIFY once
```

No random K-fold across dates. No Platt on VALIDATION. No OOS retune.

Primary analysis set for game/possession features: GPE V2 alignment
`HIGH ∪ MEDIUM`. Full 1,230 always written. Report exclusion Δq vs 26.02%.
