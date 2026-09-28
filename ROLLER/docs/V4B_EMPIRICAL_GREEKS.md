# V4B empirical Greeks

Query-time measurements of the relationship between visible market movement and prior-only `F_t`. They are **not** signals, edge, fills, or Black-Scholes Greeks.

```text
Δ ≠ EDGE    Γ ≠ EDGE    Θ ≠ EDGE    BASIS ≠ EDGE    RESIDUAL ≠ EDGE
PURE THETA ≠ NO-EVENT THETA
CANDLE PATH ≠ FILL
```

Public API: `db.greeks(observation_id)`. Nothing produced here enters `observation()` or `dataset()`.

V3 `roller/greeks/` wrappers and `db.response` / `db.baseline` / `db.residual` keep their meanings. This document is V4B only.

## Shared inputs

`candles.py` and `fundamentals.py` build one `X_t`. Families consume that object. They do not rediscover candles or recompute `F`.

`t−1` is the previous **visible home candle** `available_at`, not a DataFrame row index.

`F_{t-1}` is `db.fundamental()` at a **new** `observation_id` whose cutoff is that candle time.

## Families

| Name | Discrete definition | Inputs | Availability | Nulls | Interpretation | Non-interpretation |
|------|---------------------|--------|--------------|-------|----------------|--------------------|
| `market_delta_1m` | `K_t − K_{t-1}` integer E4 | visible home `yes_bid_close` pair | `≥ C_t.available_at` | missing K; interval ≠ 60s (`TIME_GAP`) | signed 1-minute close-to-close move | not V3 `market_return_1m_backward`; not a fill |
| `fundamental_delta` | `F_t_e4 − F_{t-1,e4}` exact rational | two independent `db.fundamental` calls | `F_t.available_at` (V4A = observation cutoff) | missing / unsupported F | change in prior-only win-rate estimate | not truth; not edge |
| `response_delta` | `ΔK − ΔF` | the two deltas | max of input boundaries | either delta null | observed market move minus modeled F move | not inefficiency |
| `market_fundamental_basis` | `B_t = (K n − wins×10000) / n` | `K_t`, `F_t` | max(candle, F) | missing K or F | discrepancy between visible K and F | not V3 `basis.py`; not mispricing |
| `basis_delta` | `B_t − B_{t-1}` | two bases | max of B availabilities | either B null | change in that discrepancy | must equal `response_delta` when all exist |
| `score_delta` | `ΔF / ΔS` | `ΔF`, `S = home − away` | max(F, state) | `ΔS = 0` (no divide) | F change per score-diff point | not total-points sensitivity |
| `discrete_gamma` | `ΔF_t − ΔF_{t-1}` | three F on compatible 60s intervals | max of ΔF times | gap / missing F | temporal second difference of F | **not** `∂²F/∂S²`; not BS gamma |
| `theta_observed` | `ΔF / Δelapsed_seconds` | `ΔF`, elapsed clock | max(F, state) | `Δelapsed = 0` | F change per elapsed second | not calendar theta |
| `pure_theta` | `theta_observed` if period and `S` held | theta + period + S | same as theta | `MIXED_INTERVAL` | PARTIAL clock sensitivity | **not** “no basketball events” |
| `candle_range` | `high − low` E4 | last visible OHLC | `C_t.available_at` | missing OHLC | unordered candle range | not a path |
| `absolute_return` | `abs(market_delta_1m)` | market delta | same as market delta | iff market delta null | unsigned E4 movement | not a second signed delta |
| `realized_market_volatility` | `Σ \|ΔK\|` over configured visible closes | visible close path | last included close | < 2 closes | absolute-variation proxy | **not** IV, stdev, or `√Σ r²` |
| `directional_efficiency` | `abs(close−open)/(high−low)` | last visible OHLC | `C_t.available_at` | `high == low` | candle efficiency ratio | not an edge |

OHLC objects carry `path_information_status = UNORDERED_SUMMARY`.

## Arithmetic

```text
F_t     = Fraction(wins, n)
F_t_e4  = Fraction(wins * 10000, n)
B_t     = Fraction(K_t * n - wins * 10000, n)
```

Never `(wins * 10000) // n`. Reconciliation of exact rationals uses no float tolerance.

When all inputs exist, a runtime assertion requires:

```text
basis_delta = response_delta = market_delta_1m − fundamental_delta
```

Disagreement is `RECONCILIATION_FAILED`. Contradictory numbers are not published.

## Baselines and residuals

```text
E[M | core_v1]
```

Eligible history: same `core_v1` cell, `measurement_available_at_i < t`, `game_i ≠ game_t`.

Not conditioners: other V4B measurements, residuals, future realized vol, future gamma, baseline outputs, path summaries.

Mean and MAD are exact rationals. Standardized residual exists only if support passes and `MAD > 0`. `effective_n = null`. Insufficient support → `expected = null`, `residual = null`, not 0.

V3 `db.residual` remains the market-response residual. It is not V4B `R`.
