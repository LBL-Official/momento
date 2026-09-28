# V4C Greek architecture

V4C is the **measurement constitution** above frozen V4B. It is not a second Greek calculator. It decides when the system is permitted to claim that an object exists.

```text
EPISTEMIC     what could have been known?          V4A O_t / I(t)
FUNDAMENTAL   what historically happened?          V4A F_t
MEASUREMENT   what can this regime observe?        V4B
IDENTITY      what is this object?                 V4C
RESIDUAL      how unusual vs comparable states?    V4B E[M|core_v1]
RESEARCH      does it structurally replicate?      not authorized
ECONOMIC      not authorized
```

V4B is the empirical measurement layer, not “the Greek layer.” Greeks are a taxonomy imposed on measurements.

```text
A GREEK NAME DOES NOT AUTHORIZE A MEASUREMENT.
V4C CREATES ZERO NEW EMPIRICAL NUMBERS.
Δ/Γ/Θ/VEGA/Λ/Ω/Ψ/B/R ≠ EDGE
PURE THETA ≠ NO-EVENT THETA
MEASUREMENT ≠ EDGE
CANDLE PATH ≠ EXECUTABLE PATH
LIVE EXECUTION = FALSE
```

## API

```python
db.greeks(observation_id)                            # V4B payload, unchanged
db.greeks(observation_id, schema_version="4.0.0-B")  # same
db.greeks(observation_id, schema_version="4.0.0-C")  # lossless overlay
```

`4.0.0-C` calls the same canonical V4B path, then maps. It does not rediscover candles, reconstruct `X_t`, or recalculate Δ.

```text
COPY numerator
COPY denominator
ATTACH identity
ATTACH contract
ATTACH provenance
```

Invariance is integer identity:

```python
assert v4c_value["numerator"] == v4b_value["numerator"]
assert v4c_value["denominator"] == v4b_value["denominator"]
```

Internal invariant: `V4C_EMPIRICAL_COMPUTATION_COUNT = 0`.

## Payload

- `measurements` — V4B-derived objects only. A null value is `DATA_UNAVAILABLE`, `INSUFFICIENT_SUPPORT`, or `INVALID_INPUT`.
- `catalog` — architectural objects only. `value=None` means intentionally no measurement exists.

These two `None`s are not the same meaning.

## Constructibility

```text
CONSTRUCTIBLE(M) requires:
  required data
  valid information regime
  point-in-time availability
  approved definition
  implemented definition
  unambiguous identity
  no prohibited proxy
```

Approved-definition and implemented-definition are separate. A registry name is not an estimator.

## Identity

```text
MeasurementIdentity =
    measurement_name
  + measurement_class
  + definition_version
  + information_regime
  + resolution
  + conditioning_schema
```

`market_delta_1m` / `CANDLE_1M` / `60_SECOND_CANDLE` is not a lower-resolution alias of `market_delta_1s`.

Classes are not interchangeable:

```text
DIRECT_DIFFERENCE
        ≠
EMPIRICAL_DISCRETE_SENSITIVITY
        ≠
PATH_DESCRIPTOR
        ≠
CONDITIONAL_SURFACE
        ≠
MICROSTRUCTURE
```

The V4B public key `realized_market_volatility` is frozen. Its constitutional identity is `canonical_identity = market_absolute_variation`, class `PATH_DESCRIPTOR`, informal family `VEGA_ANALOGUE`. `Σ|ΔK| ≠ σ_K`.

Frozen negatives:

```text
discrete_gamma ≠ score_surface_gamma
realized_market_volatility ≠ sigma_K
pure_theta ≠ no_event_theta
score_delta ≠ conditional_score_surface_delta
```

## Provenance

Every mapped measurement:

```text
source = V4B_CANONICAL_RESULT
source_schema_version = 4.0.0-B
transformation = LOSSLESS_METADATA_MAPPING
```

Never `source = V4C_COMPUTATION`.

Versions: `greek_schema_version` remains `4.0.0-B`. `greek_architecture_version` is `4.0.0-C`.
