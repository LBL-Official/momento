# Kalshi overlay quality

Candles are 1-minute top-of-book OHLC. Not ticks. Not L2.

A possession with modeled wall `[t0, t1]` overlaps candle `end_period_ts = T`
if `(T−60, T]` intersects `[t0, t1]`.

| Code | Meaning |
| --- | --- |
| EXACT_ALIGNMENT | One candle, and that candle overlaps only this possession |
| MULTI_POSSESSION_CANDLE | Overlapping candle(s) also overlap other possessions |
| MULTI_CANDLE_POSSESSION | This possession spans two or more candles |
| PARTIAL_ALIGNMENT | Missing modeled wall on start or end |

If MULTI_POSSESSION_CANDLE, do not attribute the candle move to one possession.
Keep the label as a feature and diagnostic.

Aggregation (deterministic):

- before: last `yes_bid_close` with `end_period_ts ≤ t0`
- after: first `yes_bid_close` with `end_period_ts ≥ t1`
- during: min/max/sum volume over overlapping candles
