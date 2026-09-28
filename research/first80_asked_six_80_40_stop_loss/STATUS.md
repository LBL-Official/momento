# Status — average stop loss when 40 is missing

```
RESEARCH ONLY
CANDLE PATH ≠ ACTUAL FILL
A 40 CLOSE IS NOT A PROVEN FILL
LIVE EXECUTION = FALSE
DO NOT CHANGE LIVE FIRST01
```

On the 299 STOP_40 trades:

- 54 (18.1%) printed 40 on the first tradable close ≤40 → modeled loss **−40¢**
- 245 (81.9%) were already through → first print 33.30¢ → modeled loss **−46.70¢**
- Blended: **−45.49¢** (avg exit 34.51¢)
- FAST_GAP (prior >40, through 40, one-bar drop ≥10¢): 181 / 299, **−48.01¢**
- Crash (first print ≤20): 13 / 299, **−68.54¢**

Book EV at 74.70% WR falls from +4.82¢ to +3.43¢. Still above the 59.06¢ breakeven loss. Not a fill.
