# NHL FIRST80 80→40 — observational backtest

Research only. Does not change live trading. Does not invent L2.

Same FIRST80 / close-40 rule as `apps/nba-data/scripts/nba_80_40_execution_audit.py`
on Kalshi `KXNHLGAME` 2025–2026. Definition is imported, not rewritten.

```
LIVE EXECUTION = FALSE
CANDLE PATH ≠ ACTUAL FILL
```

---

## 0. Universe

| | N | % of n universe |
|---|---:|---:|
| n universe (game events) | 1,455 | 100.00% |
| FIRST-80 settled | 1,444 | 99.244% |
| No tradable 80 | 11 | 0.756% |
| Same-minute FIRST80 tie | 0 | 0.0% |
| Unsettled FIRST80 (dropped from P&L) | 0 | 0.0% |

## 1. Observed FIRST-80 / close-40 path

| | N |
|---|---:|
| Games | 1,455 |
| First tradable 80 cross (settled) | 1,444 |
| Never later `yes_bid_close ≤ 40¢` and won | 1,159 |
| Later `yes_bid_close ≤ 40¢` | 285 |
| LOSS ∧ ¬T40 (measurement gap) | 0 |

Strategy win rate (hold unless close-stop): **80.2632%**  
95% Wilson CI: **78.1311% – 82.2346%** (n = 1444)

| Quantity | Estimate |
|---|---:|
| P(Kalshi yes \| first 80) | 84.7645% |
| P(no close-40 \| first 80) | 80.2632% |
| Gross EV / trade (+1R/−2R) | 8.1579 ¢ (0.4079 R) |
| EVN (net ¢ / trade; stop taker fee, no entry fee) | 7.8263 ¢ (0.3913 R) |
| EVN with published maker-entry estimate | 7.5463 ¢ |
| +1R/−2R breakeven | 66.67% |

Candle path ≠ fill. Historical L2 is NOT AVAILABLE.

## 2. Execution-realism models

| Model | Trades | Win rate | Gross EV R | EVN ¢ |
|---|---:|---:|---:|---:|
| original (close-stop, all fills) | 1,444 | 80.2632% | 0.4079 | 7.8263 |
| require last-print through 80 | 1,300 | 80.4615% | 0.4138 | 7.9487 |
| HIGH + wick-stop | 846 | 69.6217% | 0.0887 | 1.2627 |
| HIGH + close-stop | 846 | 78.1324% | 0.344 | 6.512 |
| all fills + wick-stop | 1,444 | 68.6288% | 0.0589 | 0.6502 |

## 3. Chronological splits (a priori, same cuts as NBA)

IN_SAMPLE `game_date <= 2025-12-31`; VALIDATION through 2026-03-15; OOS after.

- **IN_SAMPLE**: n=683 win=78.4773% CI [75.2403, 81.3958] EV_R=0.3543 EVN=6.7248¢
- **VALIDATION**: n=431 win=80.7425% CI [76.7546, 84.1871] EV_R=0.4223 EVN=8.1219¢
- **OOS**: n=330 win=83.3333% CI [78.9336, 86.9659] EV_R=0.5 EVN=9.72¢

## 4. What this is not

- Not a live order, fill, or realized P&L.
- Not MLB FIRST01 / 80/81/83/89.
- Not W9. Not a production NHL strategy.
- Fees are a labeled published-schedule estimate. `KXNHLGAME` maker multiplier is UNKNOWN.

**LIVE DEPLOYMENT: NOT AUTHORIZED**

