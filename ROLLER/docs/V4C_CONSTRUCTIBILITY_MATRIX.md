# V4C constructibility matrix

Source of truth: [`config/greek_v4c_registry.json`](../config/greek_v4c_registry.json).

Statuses are not interchangeable.

| Status | Meaning |
|--------|---------|
| `IMPLEMENTED` | Valid regime + approved implemented definition |
| `PARTIAL` | Measurement exists but the broader Greek name would overclaim |
| `NOT_YET_IMPLEMENTED` | Potentially constructible later; no proxy |
| `NOT_CONSTRUCTIBLE` | Current information regime cannot produce the object |
| `DATA_UNAVAILABLE` | Required data absent for this instance (mapped V4B null) |
| `INSUFFICIENT_SUPPORT` | Definition exists but empirical support is inadequate |
| `INVALID_INPUT` | Input fails the measurement contract |

```text
NOT_YET_IMPLEMENTED ≠ NOT_CONSTRUCTIBLE
```

`response_beta` is `NOT_YET_IMPLEMENTED` (`CONDITIONAL_SURFACE`). `microprice` is `NOT_CONSTRUCTIBLE` (`MICROSTRUCTURE`).

Classes are not interchangeable: `DIRECT_DIFFERENCE` ≠ `EMPIRICAL_DISCRETE_SENSITIVITY` ≠ `PATH_DESCRIPTOR` ≠ `CONDITIONAL_SURFACE` ≠ `MICROSTRUCTURE`.

The frozen V4B key `realized_market_volatility` has canonical identity `market_absolute_variation`.

## Mapped (V4B identities)

Thirteen V4B families, `definition_version=4.0.0-B`, `CANDLE_1M`, `60_SECOND_CANDLE`. `pure_theta` is `PARTIAL`.

## Reserved — not yet implemented

`possession_delta`, `event_delta`, `conditional_score_surface_delta`, `score_surface_gamma`, `time_gamma`, `sigma_F`, `sigma_K`, `volatility_difference`, `volatility_ratio`, `response_beta`, `standardized_basis`, `basis_half_life`, `no_event_theta`, `market_delta_1s`, `residual_family_beyond_v4b`, cross-Greeks.

NBA `possessions=REAL` is data capability only:

```text
POSSESSION_STATE = AVAILABLE
POSSESSION_CONDITIONED_F = NOT VALIDATED
possession_delta = NOT_YET_IMPLEMENTED
```

## Reserved — not constructible

`microprice`, `order_book_imbalance`, `price_impact_lambda`, `signed_flow_lambda`, `psi_resilience`.

```text
OHLC ≠ ORDER BOOK
CANDLE RETURN ≠ SIGNED FLOW
HIGH/LOW ≠ MICROPRICE
VOLUME ≠ QUEUE STATE
MORE DERIVATION ≠ MORE INFORMATION
```
