# MLB FIRST80 80→40 — observational backtest

Research only. Does not change live trading. Does not invent L2.

Same FIRST80 / close-40 rule as `apps/nba-data/scripts/nba_80_40_execution_audit.py`
on Kalshi `KXMLBGAME` 2025–2026. Definition is imported, not rewritten.

```
LIVE EXECUTION = FALSE
CANDLE PATH ≠ ACTUAL FILL
```

---

## 0. Universe

| | N | % of n universe |
|---|---:|---:|
| n universe (game events) | 4,379 | 100.00% |
| FIRST-80 settled | 4,303 | 98.2644% |
| No tradable 80 | 76 | 1.7356% |
| Same-minute FIRST80 tie | 0 | 0.0% |
| Unsettled FIRST80 (dropped from P&L) | 0 | 0.0% |

## 1. Observed FIRST-80 / close-40 path

| | N |
|---|---:|
| Games | 4,379 |
| First tradable 80 cross (settled) | 4,303 |
| Never later `yes_bid_close ≤ 40¢` and won | 3,326 |
| Later `yes_bid_close ≤ 40¢` | 977 |
| LOSS ∧ ¬T40 (measurement gap) | 0 |

Strategy win rate (hold unless close-stop): **77.2949%**  
95% Wilson CI: **76.0192% – 78.522%** (n = 4303)

| Quantity | Estimate |
|---|---:|
| P(Kalshi yes \| first 80) | 84.4062% |
| P(no close-40 \| first 80) | 77.2949% |
| Gross EV / trade (+1R/−2R) | 6.3769 ¢ (0.3188 R) |
| EVN (net ¢ / trade; stop taker fee at M=0.5, no entry fee) | 6.1862 ¢ (0.3093 R) |
| EVN with published maker-entry estimate (M=0.5) | 6.0462 ¢ |
| +1R/−2R breakeven | 66.67% |

Candle path ≠ fill. Historical L2 is NOT AVAILABLE.
`KXMLBGAME` fee_multiplier = 0.5 is a labeled published-schedule estimate.

## 2. Execution-realism models

| Model | Trades | Win rate | Gross EV R | EVN ¢ |
|---|---:|---:|---:|---:|
| original (close-stop, all fills) | 4,303 | 77.2949% | 0.3188 | 6.1862 |
| require last-print through 80 | 3,557 | 76.8625% | 0.3059 | 5.9232 |
| HIGH + wick-stop | 2,219 | 66.1109% | -0.0167 | -0.6182 |
| HIGH + close-stop | 2,219 | 74.6282% | 0.2388 | 4.5638 |
| all fills + wick-stop | 4,303 | 60.9807% | -0.1706 | -3.7393 |

## 3. Chronological splits (a priori MLB cuts; not retuned)

IN_SAMPLE `game_date <= 2025-10-31`; VALIDATION through 2026-07-15; OOS after.

- **IN_SAMPLE**: n=2,197 win=78.061% CI [76.2823, 79.7417] EV_R=0.3418 EVN=6.6523¢
- **VALIDATION**: n=1,442 win=77.3232% CI [75.0909, 79.4102] EV_R=0.3197 EVN=6.2034¢
- **OOS**: n=664 win=74.6988% CI [71.2565, 77.857] EV_R=0.241 EVN=4.6067¢

## 4. What this is not

- Not a live order, fill, or realized P&L.
- Not live MLB FIRST01 / 80/81/83/89.
- Not W9. Not a production MLB strategy change.
- Fees use labeled `KXMLBGAME` quadratic M=0.5. Not a production KalshiFeeModel.

**LIVE DEPLOYMENT: NOT AUTHORIZED**

