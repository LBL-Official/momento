# V4C measurement constitution

V4C is not a catalog of Greeks the desk hopes to calculate.

It is the set of conditions under which ROLLER is legally permitted to claim that a measurement exists.

```text
A measurement may exist only if:

DATA
∧ PIT
∧ INFORMATION REGIME
∧ APPROVED DEFINITION
∧ UNIQUE IDENTITY
∧ VALID RESOLUTION
∧ NO FORBIDDEN PROXY

Otherwise: NULL
```

```text
ROLLER V4
MEASUREMENT BEFORE INTERPRETATION

NO PROXY WITHOUT IDENTITY
NO SIGNAL WITHOUT REPLICATION
```

## Layers (operational names stay V4A / V4B / V4C)

| Layer | Question | Where |
|-------|----------|--------|
| Epistemic | What could have been known? | `db.observation()` / `I(t)` |
| Fundamental | What historically happened from knowable states? | `db.fundamental()` |
| Measurement | What can the current regime observe? | `db.greeks()` V4B |
| Identity | What is this object? | `db.greeks(..., 4.0.0-C)` |
| Residual | How unusual vs comparable observations? | V4B `R = M − E[M \| core_v1]` |
| Research | Does it structurally replicate? | Not authorized |
| Economic | Is it exploitable? | **Not authorized** |

## Measurement classes

V4B is not “the Greek layer.” These are different scientific types:

| Class | Meaning | Examples |
|-------|---------|----------|
| `DIRECT_DIFFERENCE` | Transformation of observed or independently computed objects | `market_delta_1m`, `fundamental_delta`, `basis_delta`, `response_delta`, `absolute_return` |
| `EMPIRICAL_DISCRETE_SENSITIVITY` | Discrete analogue, not a derivative | `score_delta`, `theta_observed`, `discrete_gamma` |
| `PATH_DESCRIPTOR` | Describes the candle path; not a sensitivity | `market_absolute_variation` (V4B key `realized_market_volatility`), `directional_efficiency`, `candle_range` |
| `CONDITIONAL_SURFACE` | True conditional object | `∂F/∂S`, `σ_K`, `response_beta`, `possession_delta` — reserved |
| `MICROSTRUCTURE` | Book / flow | `microprice`, OBI, λ, Ψ — `NOT_CONSTRUCTIBLE` |

A Class II object cannot become a Class IV object by renaming.

`discrete_gamma.identity_kind = temporal_second_difference`. It is not score-surface curvature.

## Frozen V4B name vs constitutional identity

```text
V4B public key:     realized_market_volatility     (frozen; do not rename)
canonical_identity: market_absolute_variation
what it measures:   Σ|ΔK|
informal_family:    VEGA_ANALOGUE
what it is not:     σ_K / implied volatility / Vega
```

The field name must not be allowed to smuggle a volatility interpretation.

## Residual

```text
Rᵐ_t = M_t − E[M | core_v1]
```

means only: this measurement was unusual in the current conditioning cell.

```text
R^M ≠ CAUSAL RESIDUAL
R^M ≠ MARKET ERROR
R^M ≠ EDGE
UNUSUAL ≠ PREDICTIVE
PREDICTIVE ≠ CAUSAL
CAUSAL ≠ ECONOMICALLY EXPLOITABLE
MODEL DISAGREEMENT ≠ MARKET INEFFICIENCY
MARKET INEFFICIENCY ≠ EXECUTABLE PROFIT
```

## Null

```text
NULL ≠ UNKNOWN
NULL ≠ ZERO
NULL ≠ NOT COMPUTED
```

Catalog `None` is constitutional refusal. Mapped V4B `None` is an instance status (`DATA_UNAVAILABLE` / `INSUFFICIENT_SUPPORT` / `INVALID_INPUT`).
