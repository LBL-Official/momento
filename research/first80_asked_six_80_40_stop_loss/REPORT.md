# Asked-six 80/40 — average stop loss when 40 is missing

```
RESEARCH ONLY
CANDLE PATH ≠ ACTUAL FILL
LIVE EXECUTION = FALSE
A 40 CLOSE IS NOT A PROVEN FILL
DO NOT CHANGE LIVE FIRST01
```

Generated: `2026-09-10T06:53:27.085043+00:00`

## Question

The book assumes every loser exits at 40¢ (−40¢). What is the
average stop loss if we only get 40 when the first tradable
close ≤40 is actually 40, and otherwise we get that first print?

## Frozen rule

- **PRINTED_40** (can try 40): first T40 close == 40. Modeled loss **−40¢**.
- **NO_40_PRINT** (cannot get 40 on that bar): first T40 close < 40.
  Modeled loss = 80 − that close.
- **FAST_GAP**: prior close > 40, first T40 close < 40, one-bar drop ≥ 10¢.

This is still a candle close, not a Kalshi fill.

## Average stop loss on the 299 stops

- When a 40 print existed (**54 / 299**, 18.1%): **−40.00¢** (exit 40.00¢).
- When it did not (**245 / 299**, 81.9%): **−46.70¢** (exit 33.30¢).
- Blended, using 40 only when it printed: **−45.49¢** (avg exit 34.51¢).
- FAST_GAP subset: **181 / 299** (60.5%), avg loss **−48.01¢**, avg one-bar drop 20.5083¢ from prior 52.4972¢.

| Class | n | % | Avg exit | Avg stop loss | Avg prior | Avg drop | 5m min |
|---|---:|---:|---:|---:|---:|---:|---:|
| ALL stops | 299 | 100.0% | 34.51¢ | −45.49¢ | 50.1¢ | 15.6¢ | 24.5¢ |
| PRINTED_40 | 54 | 18.1% | 40.00¢ | −40.00¢ | 50.3¢ | 10.3¢ | 30.4¢ |
| NO_40_PRINT | 245 | 81.9% | 33.30¢ | −46.70¢ | 50.1¢ | 16.8¢ | 23.2¢ |
|   mild 35–39 | 134 | 44.8% | 37.56¢ | −42.44¢ | 49.7¢ | 12.2¢ | 27.5¢ |
|   fast ≤34 | 98 | 32.8% | 30.37¢ | −49.63¢ | 49.8¢ | 19.4¢ | 19.2¢ |
|   crash ≤20 | 13 | 4.3% | 11.46¢ | −68.54¢ | 55.6¢ | 44.2¢ | 8.6¢ |
| FAST_GAP (drop≥10) | 181 | 60.5% | 31.99¢ | −48.01¢ | 52.5¢ | 20.5¢ | 21.5¢ |

## What this does to the book

Wins stay +20¢. 883 wins, 299 stops.

- If every stop is −40: EV = +4.82¢/trade.
- If stops use this modeled loss (−45.49¢): EV = +3.43¢/trade.

Breakeven average stop loss at 74.70% WR is still **59.06¢**.
This blended loss (first print) is below that line. The 5-minute
chase on NO_40_PRINT is closer to it.

## Does not

- Prove a 40 close was liftable.
- Change live FIRST01.
- Use rest-of-game min (hold-to-0 on losers).

