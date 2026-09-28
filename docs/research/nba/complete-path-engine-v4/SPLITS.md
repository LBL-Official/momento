# Splits

Cuts on `game_date`. One trade = one path = one split.

```text
TRAIN       game_date ≤ 2025-12-31     BUILD (means, medoids, SVD, functionals)
VALIDATION  2026-01-01 .. 2026-03-15   CHOOSE (model family; optional q threshold)
OOS         game_date > 2026-03-15     VERIFY once
```

No threshold search on OOS. No path leaking post-80 information.
Do not rerun OOS until a curve test “works.”
