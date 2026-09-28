# V3 measurement model

```text
O_t  ≠  Y_{t→t+h}  ≠  E[Y | C(O_t)]  ≠  R_t
```

```text
db.observation(...)  → what could have been known (S_t + Γ_t + M_{≤t})
db.response(...)     → what subsequently happened
db.baseline(...)     → historically available conditional expectation
db.residual(...)     → how unusual Y was versus that baseline
```

There is no `db.measure` dispatcher.

## Observed measurement (backward)

`M_{≤t}` is assembled on `O_t` as `BACKWARD_MEASUREMENTS` from rows with `available_at < cutoff`.

Examples: `market_return_1m_backward`, completed-candle open-to-close, high-low range.

These are not future responses.

## Response (forward)

`Y_{t→t+h}` is only available through `db.response`. Every row carries `observation_time`, `response_start_time`, `response_end_time`, `horizon`, `source_resolution`, and `response_available_at`.

`contains_future_information = true`.

## Conditional baseline

```text
eligible(Y_i, t) iff
    observation_time_i < t
    AND
    response_available_at_i < t
```

Equality is hidden. `observation_time_i < t` alone is not sufficient.

The baseline exposes `baseline_start`, `baseline_end`, `baseline_construction_version`.

## Empirical Greek

A documented finite-difference or grouped sensitivity. Not a Black-Scholes derivative. Not a prediction. Not an edge.

## Residual

```text
R_t = Y_{t→t+h} - E[Y_i | C(O_i)=C(O_t), response_available_at_i < t]
```

If support is insufficient, `residual_status = INSUFFICIENT_SUPPORT` and `value` is undefined. Undefined ≠ 0.

## Structural replication

V3 reports support (unique games ≠ observation count). V3 does not implement train/OOS. That is V4.
