# Hazard model

Each FIRST-80 trade is a survival process.

```text
ENTRY (end of first-80 candle)
  → alive while no close-path 40 has printed
  → event at first post-entry 40-close candle
  → else censored at last valid candle / contract close
```

The risk set at state time `t` contains only trades still alive.
The barrier candle itself is **not** in the risk set (no same-bar
prediction of the event using that bar's close as if it were a hold
decision after the print).

Discrete time: one row per completed 1m candle while alive.
Same-bar OHLC ordering is unknown (`SAME_BAR_1M_LIMITATION`).

## Targets (future-only)

| Name | Definition |
| --- | --- |
| H_40_5M | close-path 40 in `(t, t+5m]` |
| H_40_10M | in `(t, t+10m]` |
| H_40_15M | in `(t, t+15m]` |
| EVENTUAL_40 | barrier before expiration (trade-level, attached) |
| barrier_event_next_1m | event in `(t, t+1m]` (discrete hazard step) |

Features use information with source timestamp `≤ t`.

## Model 0

Unconditional discrete hazard, stratified by `minutes_since_entry` bins
on TRAIN. A second baseline (0b) stratifies by `distance_to_40` only —
to avoid “rediscovering” proximity.

## Model 2

Regularized logistic for `H_40_5M` (and separately `barrier_event_next_1m`).
Panel rows from the same trade are **not** independent. Fit may use all
alive minutes; selection and OOS metrics are reported **trade-clustered**
(mean predicted hazard vs realized outcome; clustered bootstrap).

## Model 3

Discrete-time survival with time-varying covariates = Model 2 plus explicit
time basis (`minutes_since_entry`, spline/quadratic). Cox PH is not forced:
clock is discrete, covariates are time-varying, PH is untested.

## Model 4

Shallow GBM only if Model 2/3 beat Model 0 on VALIDATION Brier (clustered)
by the frozen gate (≤ 0.95 × Brier_0).
