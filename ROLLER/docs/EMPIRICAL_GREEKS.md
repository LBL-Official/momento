# Empirical Greeks

K field is always `yes_bid_close` (integer E4) unless noted. Path status for candle OHLC is `UNORDERED_SUMMARY`.

## market_return_1m_backward

| Field | Value |
|-------|--------|
| VERSION | v1 |
| PURPOSE | Backward 1m close-to-close move visible at t |
| INPUT | last two visible `yes_bid_close` |
| FORMULA | `K_t - K_{t-1}` |
| TIME RESOLUTION | 1m |
| INFORMATION BOUNDARY | backward; on `O_t` |
| CONDITIONING | none |
| SUPPORT REQUIREMENTS | two visible closes |
| LIMITATIONS | not a forward response |
| STATUS | REAL |

## market_response_1m / 5m / 10m

| Field | Value |
|-------|--------|
| VERSION | v1 |
| PURPOSE | Forward market move over a documented horizon |
| INPUT | `K_t` (visible at t) and `K` on candles with `t < available_at <= t+h` |
| FORMULA | `K_{t+h} - K_t` |
| TIME RESOLUTION | source 1m; horizon 1m/5m/10m (identity includes both) |
| INFORMATION BOUNDARY | forward; `db.response` only |
| CONDITIONING | `conditioning_schema_v1` for baselines |
| SUPPORT REQUIREMENTS | at least one candle in the forward window |
| LIMITATIONS | 1m ≠ 1s L2 |
| STATUS | REAL |

## market_acceleration_1m

| Field | Value |
|-------|--------|
| VERSION | v1 |
| PURPOSE | Empirical curvature of visible closes |
| INPUT | three visible closes |
| FORMULA | `(K_t-K_{t-1})-(K_{t-1}-K_{t-2})` |
| TIME RESOLUTION | 1m |
| INFORMATION BOUNDARY | backward |
| CONDITIONING | none |
| SUPPORT REQUIREMENTS | three visible closes |
| LIMITATIONS | no smoother; not a second derivative of a continuous process |
| STATUS | REAL / insufficient_history |

## clock_response / theta

| Field | Value |
|-------|--------|
| VERSION | v1 |
| PURPOSE | Clock-associated elapsed-seconds change |
| INPUT | PBP clock at t and in (t, t+h] |
| FORMULA | `elapsed_{t+h} - elapsed_t` |
| TIME RESOLUTION | event |
| INFORMATION BOUNDARY | forward |
| CONDITIONING | optional |
| SUPPORT REQUIREMENTS | parseable clocks |
| LIMITATIONS | pure clock isolation is PARTIAL; events are not proven absent |
| STATUS | PARTIAL |

## close_to_close_realized_volatility / high_low_range / directional_efficiency

| Field | Value |
|-------|--------|
| VERSION | v1 |
| PURPOSE | Candle volatility proxies |
| INPUT | visible OHLC |
| FORMULA | sum of abs close deltas; high-low; abs(close-open)/(high-low) |
| TIME RESOLUTION | 1m |
| INFORMATION BOUNDARY | backward on `O_t`; forward twins are `future_realized_*` |
| CONDITIONING | volatility bucket uses backward range |
| SUPPORT REQUIREMENTS | zero range → `undefined_zero_range`; do not divide |
| LIMITATIONS | not Vega; not basketball-state volatility; high-low is not ordered |
| STATUS | REAL |

## basis

| Field | Value |
|-------|--------|
| VERSION | v1 |
| PURPOSE | `K_t - F_t` |
| INPUT | requires a versioned F_t provider |
| FORMULA | not populated |
| STATUS | NOT_YET_IMPLEMENTED / SCHEMA_ONLY |

## response_beta

| Field | Value |
|-------|--------|
| VERSION | v1 |
| PURPOSE | Grouped mean Y vs mean X |
| ESTIMATOR | conditional grouped means, eligible Y only |
| LIMITATIONS | not a global regression; n is not independent trials |
| STATUS | REAL (grouped) |

## response_residual

| Field | Value |
|-------|--------|
| VERSION | v1 |
| PURPOSE | Observed minus PIT-safe conditional expected |
| FORMULA | `(Y*n - sum) / n` stored as integer numerator/denominator |
| INFORMATION BOUNDARY | forward |
| SUPPORT REQUIREMENTS | min unique games and observations from `conditioning.json` |
| LIMITATIONS | insufficient support → undefined, not 0 |
| STATUS | REAL |
