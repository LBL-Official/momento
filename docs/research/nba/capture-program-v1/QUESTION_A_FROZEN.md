# Question A — frozen

Do not reopen. Do not re-fit. Do not hunt another FIRST-80 filter on
1-minute candles.

---

## Frozen close-path identity

Source (read-only):

```text
Backtesting Suite/Data/NBA/2025-2026/warehouse/derived/nba/first80_execution_audit/
```

| Quantity | Value | Status |
| --- | ---: | --- |
| Universe | 1,230 FIRST-80 observations | OBSERVED candle path |
| Close-path 40 events | 320 | OBSERVED candle path |
| Survivors | 910 | OBSERVED candle path |
| Survival | 910 / 1,230 = 73.98% | OBSERVED candle path |
| Gross EV = 3p − 2 | +0.2195 R | ESTIMATED path economics |
| Gross break-even | p_BE = 66.67% | Mathematical identity |

These numbers are **historical path statistics**. They are not executed
fills.

---

## Chronological close-stop survival (did not collapse)

| Split | n | Survival |
| --- | ---: | ---: |
| IN_SAMPLE `game_date ≤ 2025-12-31` | 504 | 71.83% |
| VALIDATION through 2026-03-15 | 483 | 75.57% |
| OOS after 2026-03-15 | 243 | 75.31% |

Thresholds were a priori. They were not fit on OOS.

---

## Conditional engines — closed

| Engine | Question | Verdict |
| --- | --- | --- |
| V1 | Market state at FIRST-80 | C / no robust OOS filter |
| V2 | Game/score state at FIRST-80 | C / no filter |
| V3 | Post-entry 1m hazard | C / proximity rediscovery |
| V4 | Coupled S_t = [G, M, P, D, E] | C / no robust conditional structure |

V4 skip-high-p̂: VAL +0.030 R, OOS +0.008 R (below the 0.02 R gate).

Keep the simpler unconditional rule. Do not modify PATH_ENGINE_V1,
GAME_PATH_ENGINE_V2, DYNAMIC_PATH_ENGINE_V3, or PATH_ENGINE_V4.

---

## What Question A did **not** establish

- Maker fill at 80¢
- Executable stop at 40¢
- Production fee schedule
- Fillable weekly N
- Realized net EV

Those belong to Question B.
