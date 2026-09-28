# Status — asked-six 80/40 liquidation calibration

```
RESEARCH ONLY
CANDLE PATH ≠ ACTUAL FILL
LIVE EXECUTION = FALSE
DO NOT CHANGE LIVE FIRST01
NO MIX IS A PROVEN KALSHI FILL
NOT W9
```

## Done

Calibrated the 299 STOP_40 trades. The ledger labels every stop at exactly
40¢. That is a close-path signal, not a fill.

- Identity halt: n=1,182 / win_80_40=883 / STOP_40=299.
- Breakeven average loss at 74.70% WR = **59.06¢** (exit ≈ 20.94¢).
- Declared mixes rerun on the 2–8% week-start bankroll grid (22 weeks and
  52 weeks), plus true-p 70% / 72% / 74.7%.
- Candle scan: first tradable close ≤40 after entry, then +5 minutes.
  Do **not** use `post_entry_min_yes_bid` (rest-of-game min; often 0).

## Headline (candle path, still not a fill)

- 245 / 299 first T40 closes were already **<40¢**. Median T40 close = **37¢**,
  mean = **34.5¢**. Most gaps are a few cents, not a crash to zero.
- Only 13 / 299 were ≤20¢ at the T40 bar itself.
- Min close in the next 5 minutes: median **26¢**, mean **24.5¢**,
  112 / 298 ≤20¢, 19 = 0. That is continuation after the signal, not a fill.

## Sizing (frozen viability)

Gate set before looking: 22-week IN_SAMPLE, median end > $20k, P(lose)≤10%,
P(DD>20%)≤10%, P5 end ≥ $16k.

| Mix | Avg loss | EV @ 74.70% | Max viable f (IN_SAMPLE 22w) |
|---|---:|---:|---|
| Optimistic 40 | 40.0¢ | +4.82¢ | 5% |
| 90/10 at 40/20 | 42.0¢ | +4.32¢ | 4% |
| T40 close as exit | 45.5¢ | +3.43¢ | 3% |
| 75/20/5 at 40/20/0 | 46.0¢ | +3.30¢ | 3% |
| Legacy 50/30/20 at 40/20/10 | 52.0¢ | +1.79¢ | none |
| 50/30/20 at 40/20/0 | 54.0¢ | +1.28¢ | none |
| 5m min close | 55.5¢ | +0.89¢ | none |
| All stops at 0 | 80.0¢ | −5.30¢ | none |

The previous 3–5% recommendation is the optimistic column only.
It is **not** a living-size recommendation.

At 72% true WR: optimistic max 4%; T40-close and 75/20/5: none.
At 70%: no mix is viable, including optimistic 40.

## Does not

- Change live FIRST01 / 80/81/83/89.
- Authorize a production liquidation model.
- Start W9.
- Treat any mix as an estimated Kalshi fill rate.
