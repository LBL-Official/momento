# Path object

The research object is the **arrival path**, not a row of state variables.

## Primary: FULL_WINDOW

All valid 1-minute candles with

```text
game_window_start ≤ end_period_ts ≤ first_80_timestamp
```

The last point **is** the first-80 candle (`SAME_BAR_1M_LIMITATION`).
No candle after first-80 is used. No future PBP event is used.

## Secondary: FROM_50

The ascent segment: after the last close **below** 50¢ before first-80,
through first-80 inclusive.

If the contract is never observed below 50¢ before first-80:

```text
FROM_50_STATUS = NEVER_BELOW_50
```

That stratum is reported. It is not imputed.

## Tertiary: GAME_ALIGNED

Score differential along the same market timestamps, using
`PERIOD_BOUNDED_LINEAR_GAME_CLOCK` snaps with `modeled_wall_ts ≤ candle_ts`.
Tip is `gameTimeUTC`, never Kalshi open. Alignment confidence is a
**quality** label, not a trading feature.

## Time-normalized curve

Each path with ≥ 3 points is linearly interpolated onto

```text
u ∈ {0, 1/31, …, 1}     GRID_N = 32
u = 0 → first candle of that definition
u = 1 → first-80 candle
```

Duration is **normalized out** of this representation. Duration itself is
kept as a separate functional (it is a path property, not a local state).

Raw unequal-length sequences are kept for DTW (downsample cap 96).

## What V4 is not

- Not V1’s 5/15-minute local windows as the primary object
- Not V2’s single `path_state` string at snap
- Not V3’s post-entry hazard panel
- Not L2, not maker fills, not intra-minute order
