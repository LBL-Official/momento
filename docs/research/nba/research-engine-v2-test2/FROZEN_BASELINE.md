# Frozen baseline (do not rebuild)

Imported from `nba_80_40_execution_audit.py`. Pipeline exits 1 on mismatch.

| Quantity | Count |
| ---: | ---: |
| Games | 1,362 |
| First-80 | 1,230 |
| Survive close-path 40 | 910 |
| Hit close-path 40 | 320 |

```text
q = 26.02%
EV_gross = 1 − 3q ≈ +0.219 R
breakeven q = 33.33%
ENTRY_DECISION_TIME = end of first-80 candle
```

Primary target: close-path `Y_40` / `SURVIVE_40`. Wick is secondary.
Eventual winner is TARGET_ONLY.
