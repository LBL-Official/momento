# Splits

Cuts on `game_date`. A trade’s **entire panel** stays in one split.

```text
TRAIN       game_date ≤ 2025-12-31     BUILD
VALIDATION  2026-01-01 .. 2026-03-15   CHOOSE (model family + warning threshold)
OOS         game_date > 2026-03-15     VERIFY once
```

No threshold search on OOS. No trade split across folds.
