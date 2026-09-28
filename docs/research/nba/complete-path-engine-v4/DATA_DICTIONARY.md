# Data dictionary (selected)

`trade_id` = `{event_id}|{ticker}|first80`

## Path grids (`arrival_curves.npz`)

- `full_grid` (n × 32): time-normalized bid **cents**, FULL_WINDOW
- `from50_grid` (n × 32): FROM_50; NaN if insufficient / never-below-50
- `score_grid` (n × 32): score differential on FULL_WINDOW time; NaN if unaligned
- `full_mask`, `from50_mask`, `score_mask`

## Path functionals (parquet)

duration_minutes, n_candles, total_variation_cents, path_efficiency,
n_reversals, min_bid_cents, max_bid_cents, mean_bid_cents,
frac_below_50/60/70, minutes_from_50_to_80, from50_status,
score_tv, n_lead_changes_pre80, net_score_change_pre80

Volatility of the **whole path** is labeled
`1-MINUTE CANDLE VOLATILITY PROXY` (path-wide), not true RV.

## State competitor (not the V4 claim)

entry bid/spread, minutes_to_close, local 5m vol proxy, score_diff at 80.
Labeled `STATE_OR_LOCAL`. Used only as HS.

## Targets

Y_40_CLOSE, Y_40_WICK. TARGET_ONLY.
