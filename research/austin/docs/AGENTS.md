# Austin agent contract

Research desk. Not Vital. Not Fort Worth execution.

```
LIVE EXECUTION = FALSE
CANDLE PATH ≠ ACTUAL FILL
QUERY MODE ≠ LIVE FEED
allocation band ∈ {3%, 4%, 5%}
never BUY / SKIP
```

## Absolute

- Do not submit, cancel, or modify orders.
- Do not edit `apps/trading-engine`, `strategies/mlb`, or `first80.py`.
- Do not change live FIRST01 / 80/81/83/89, `book.json`, W9, Phase 21.
- Do not remount this inside `frontend/roller-terminal`.
- Do not import `nba_path_fe` Family E / `hedge_*` into features.
- Do not treat path-FE enter/skip as Austin’s model.
- Do not mix N=604 with 936 / 1182 / 1230 / 797.
- Do not call a 40¢ close a maker fill.
- Do not claim 1230 hedge +5.17¢ on the 604 book.
- Do not fit scaler / PCA on the query.
- Do not put the query into the training set.
- Missing is `UNAVAILABLE`, never economic 0.

## Feature space ≠ outcome space ≠ execution space

PCA/KNN use information available at snapshot `t` only.
Outcomes after `t` are labels.
Fort Worth may later read a contract. Austin does not execute it.
