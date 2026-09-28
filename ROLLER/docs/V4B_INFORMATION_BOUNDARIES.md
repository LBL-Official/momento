# V4B information boundaries

V4B is a **query-time** empirical measurement system. It does **not** extend the PIT observation schema.

```text
Nothing produced by V4B becomes part of O_t.
```

That includes `F_t`, every observed measurement, baselines, and residuals. `dataset()` rejects `v4b_*`, `greek_observations`, and `greek_baselines` with `use db.greeks()`.

## Three clocks (do not collapse)

```text
state_available_at < cutoff          # O_t / GAME_STATE
candle.available_at < cutoff         # visible K / OHLC; equality hidden
measurement_available_at_i < t       # baseline eligibility
AND game_i != target_game
```

A candle that closes **exactly** at the observation cutoff is invisible.

`measurement_available_at` is no earlier than the latest availability of every input required to construct that measurement.

V4A timestamps `F_t.available_at` as the **observation cutoff**. Any measurement that requires `F_t` inherits that bound.

## Three “previous” concepts (do not collapse)

```text
previous observation state   = assemble_observation at C_{t-1}.available_at
previous visible candle      = C_{t-1} immediately preceding latest visible C_t
previous fundamental         = db.fundamental(new observation_id at C_{t-1}.available_at)
```

Forbidden: `F_previous = F_current`, or a historical lookup that uses the current cutoff.

## What V1–V4A vs V4B answer

```text
V1–V4A:  What was knowable at time t?
V4B:     Using only properly bounded inputs, what empirical measurements
         can be constructed at query time, and how unusual are they
         relative to eligible core_v1 history?
```

V4B does not establish trade, signal, execution, alpha, or expected PnL.

## V3 vs V4B

| Object | V3 | V4B |
|--------|----|-----|
| 1m market change | `market_return_1m_backward` (adjacency, including 90s gaps) | `market_delta_1m` (configured 60s only) |
| Range | `high_low_range_1m` | `candle_range` |
| Abs variation | `close_to_close_realized_volatility` | `realized_market_volatility` (named vol; **not** IV/stdev) |
| Basis | `basis.py` `NOT_YET_IMPLEMENTED` | `market_fundamental_basis` |
| Residual | `db.residual` on forward Y | `R = M − E[M\|core_v1]` inside `db.greeks()` |

Do not implement V4B by editing `backward.py` or filling `basis.py`.
