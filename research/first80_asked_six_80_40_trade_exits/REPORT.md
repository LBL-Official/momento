# Asked-six 80/40 per-trade exits

```
RESEARCH ONLY
CANDLE PATH ≠ ACTUAL FILL
LIVE EXECUTION = FALSE
DO NOT CHANGE LIVE FIRST01
```

Generated: `2026-09-10T06:50:14.512106+00:00`

## Identity

- n = **1182**
- wins = **883** — rule exit **100¢** (settlement YES)
- STOP_40 = **299** — labeled **40¢** is the signal, not a fill
- Entry is 80¢ on every row. P&L = exit − 80.

## Average exit — all 1,182 trades

Each trade has one exit under each definition. The number below is
the unweighted mean of those 1,182 values.

| Definition | Avg exit | Avg P&L | What it is |
|---|---:|---:|---|
| Labeled 80/40 | **84.82¢** | +4.82¢ | 883×100 + 299×40. Assumes every stop fills at 40. |
| T40 close | **83.43¢** | +3.43¢ | Wins 100. Stops = first tradable close ≤40. |
| +1m after T40 | 83.64¢ | +3.64¢ | Wins 100. Stops with a +1m bar only. |
| +5m min close | **80.91¢** | +0.91¢ | Wins 100. Stops = worst tradable close in the next 5 minutes. |
| last_tradable | 82.98¢ | +2.98¢ | **Not** the 80/40 exit. Stop median is 0 (hold-to-expiry). |

## Average exit — the 299 stops only

| Definition | Avg exit | Avg loss vs 80 | n |
|---|---:|---:|---:|
| Labeled 40 | 40.00¢ | -40.00¢ | 299 |
| T40 close | **34.51¢** | -45.49¢ | 299 |
| +1m | 33.82¢ | -46.18¢ | 290 |
| +2m | 33.69¢ | -46.31¢ | 298 |
| +5m close | 32.76¢ | -47.24¢ | 296 |
| +5m min | **24.52¢** | -55.48¢ | 299 |

## Wins

- n = 883. Rule exit = **100¢** on every winning trade.
- last_tradable mean = 98.98¢ (almost all 99; settlement is still 100).

## By sport

| Book | n | labeled | T40 close | 5m min |
|---|---:|---:|---:|---:|
| NBA | 604 | 84.70¢ | 83.34¢ | 81.04¢ |
| WNBA | 246 | 84.63¢ | 83.09¢ | 79.91¢ |
| NCAAB | 332 | 85.18¢ | 83.85¢ | 81.40¢ |
| NBA_STOPS | 154 | 40.00¢ | 34.68¢ | 25.64¢ |
| WNBA_STOPS | 63 | 40.00¢ | 33.98¢ | 21.56¢ |
| NCAAB_STOPS | 82 | 40.00¢ | 34.60¢ | 24.70¢ |

## By split

| Split | n | labeled | T40 close | 5m min |
|---|---:|---:|---:|---:|
| IN_SAMPLE | 418 | 84.50¢ | 82.95¢ | 80.58¢ |
| VALIDATION | 582 | 85.15¢ | 83.82¢ | 80.94¢ |
| OOS | 182 | 84.51¢ | 83.31¢ | 81.54¢ |

## Files

- `trade_exits.csv` — one row per trade, integer cents.
- `summary.json` — the averages above.

None of these exits is a Kalshi fill.

