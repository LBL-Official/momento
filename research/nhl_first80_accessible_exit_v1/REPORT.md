# NHL FIRST80 — gettable-at-80 and actual available exits

Research only. Does not change live trading. Does not invent L2.

Hockey goals reprice in jumps. The 80→40 +1R/−2R number treats a
bid-close cross as a maker fill at 80 and a later ≤40 close as a 40¢ exit.
This page splits **gettable-at-80** from jump-throughs and reports the
**actual printed exit**, not 40.

```
LIVE EXECUTION = FALSE
CANDLE PATH ≠ ACTUAL FILL
GETTABLE_AT_80 ≠ PROVEN MAKER FILL
```

GETTABLE_AT_80 = HIGH maker-fill confidence ∩ NBA HIGH_ACCESS
(jump < 10¢, close in [80, 85),
persist ≥ 2m in 78–85, ≥ 2 up-steps in prior 5m).
Rule was frozen on NBA/NCAAB. Not fit to NHL P&L.

n universe (game events) = **1455**.

## 1. Universes

| Universe | N | % of n universe | Assumed 80→40 EVN | Actual-exit EVN (leave-80 close or settlement) |
|---|---:|---:|---:|---:|
| ALL_FIRST80 | 1,444 | 99.244% | 7.8263¢ | 3.6578¢ |
| HIGH_FILL | 846 | 58.1443% | 6.512¢ | 2.1498¢ |
| NO_JUMP10 | 766 | 52.646% | 4.9423¢ | 0.7958¢ |
| RESTABLE_80 | 533 | 36.6323% | 4.2617¢ | -0.242¢ |
| GETTABLE_AT_80 | 298 | 20.4811% | 3.4416¢ | -0.9049¢ |

## 2. GETTABLE_AT_80 — can we actually rest 80?

- n = **298** / 1,455 games = **20.4811%** of n universe
- / 1,444 FIRST-80 = **20.6371%** of FIRST-80
- Entry jump mean/median: 3.4094 / 3.0 ¢
- Entry close mean/median: 80.9094 / 80.0 ¢

If GETTABLE is a small slice of FIRST-80, most of the raw 80→40 EV
is jump-through path, not a restable 80¢ maker book.

## 3. Actual exits available (GETTABLE_AT_80) — not 40

When the path first **leaves 80** (subsequent tradable bid close < 80):

- n left 80: **212** (71.1409%)
- mean / median exit **close**: **71.9575 / 78.0** ¢
- mean / median exit **low**: **67.9387 / 75.0** ¢

When a later bar **closes ≤ 40** (the old stop trigger), the printed bid is:

- n hit 40-close: **80** (26.8456%)
- jumped through 40 (prev close > 40 and this close < 40): **68** (22.8188%)
- mean / median actual 40-bar close: **22.1 / 25.0** ¢  (assumed 40)
- mean / median actual 40-bar low: **18.375 / 19.0** ¢
- actual close minus 40: mean / median **-17.9 / -15.0** ¢

All GETTABLE trades (leave-80 close, else settlement 100/0):

- mean / median exit: **80.0503 / 79.0** ¢

## 4. EV on GETTABLE using actual exits

| Model | Gross EV ¢ | EVN ¢ |
|---|---:|---:|
| Assumed 80→40 (+20/−40) | 3.8926 | 3.4416 |
| Actual leave-80 close or settlement | 0.0503 | -0.9049 |
| Actual leave-80 low or settlement | -2.8087 | — |
| Actual 40-bar close or settlement | -0.9128 | -1.1888 |
| Actual 40-bar low or settlement | -1.9128 | — |

Leave-80 EV exits at the first printed bid under 80 (a goal against).
That is harsher than waiting for 40 and is the hockey-honest liquidation
proxy: the book often is not still 79 after the goal.

40-bar actual EV keeps the old stop *timing* but uses the printed close/low
instead of 40. If that EV is much worse than assumed 80→40, the original
NHL +7.83¢ was a 40¢-fill fiction.

## 5. What this is not

- Not a proven maker fill at 80. HIGH_ACCESS + HIGH fill is a candle proxy.
- Not L2, queue, or IOC fill quality.
- Not live FIRST01 / 80/81/83/89.
- Not a production NHL strategy.

**LIVE DEPLOYMENT: NOT AUTHORIZED**

