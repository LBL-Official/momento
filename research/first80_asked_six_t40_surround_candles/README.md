# Asked-six T40 ±5 candle window

```
RESEARCH ONLY
CANDLE PATH ≠ ACTUAL FILL
LIVE EXECUTION = FALSE
DO NOT CHANGE LIVE FIRST01
```

- Universe: asked-six FIRST80 (NBA/WNBA Q2∪Q3, NCAAB H1_2∪H2_1).
- Trades: **299** STOP_40.
- File: `t40_surround_pm5.csv` — one row per candle.
- Window: offset_min **-5 … +5** around the first tradable close ≤40.
- `is_t40_bar` is the stop print. Prices are cents. `tradable` is the FIRST80 quality filter.
- This does **not** prove a 40¢ bid was liftable.
