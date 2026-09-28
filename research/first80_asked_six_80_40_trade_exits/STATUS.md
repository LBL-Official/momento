# Status — per-trade 80/40 exits

```
RESEARCH ONLY
CANDLE PATH ≠ ACTUAL FILL
LIVE EXECUTION = FALSE
DO NOT CHANGE LIVE FIRST01
```

Identity: n=1,182 / wins=883 / STOP_40=299. Entry 80¢. P&L = exit − 80.

Every trade has a row in `trade_exits.csv`.

## Average exit (unweighted mean of the 1,182 per-trade exits)

| Definition | All trades | 299 stops | 883 wins |
|---|---:|---:|---:|
| Labeled 80/40 | 84.82¢ | 40.00¢ | 100¢ |
| T40 close | 83.43¢ | 34.51¢ | 100¢ |
| +5m min | 80.91¢ | 24.52¢ | 100¢ |

last_tradable is not the rule exit (stop median 0).
