# What the Greeks do

ROLLER Greeks are **measurements of observed paths**, not trading signals and not live risk inputs.

```text
MEASUREMENT ≠ EDGE
SENSITIVITY ≠ PREDICTIVE
CANDLE PATH ≠ FILL
```

They answer: given what was knowable at `t`, how did the **visible candle path** and the **prior-only fundamental** move? They do not say a contract is mispriced, and they do not authorize an order.

## The stack

| Layer | API | Job |
|-------|-----|-----|
| I(t) / O_t | `db.observation()` | What could have been known? No labels. No FIRST80. |
| F_t | `db.fundamental()` | Prior-only empirical P(home wins) among earlier same-bucket games. `wins/n`. Never 0.50 or K when support fails. |
| V4B | `db.greeks()` | Compute the observed numbers from candles + F_t. |
| V4C | `db.greeks(..., schema_version="4.0.0-C")` | Same numbers plus identity: name, class, regime. Zero new values. |

## Implemented families (what each does)

| Informal name | Actual object | What it does | What it is not |
|---------------|---------------|--------------|----------------|
| Δ (delta) | `market_delta_1m`, `fundamental_delta`, `score_delta` | First difference of K, F, or score over the last visible minute / state | Not ∂price/∂spot. Not hedge ratio. |
| Γ (gamma) | `discrete_gamma` | Temporal second difference of the market path | Not ∂²F/∂S². Not option gamma. |
| Θ (theta) | `theta_observed`, `pure_theta` | Clock-associated change in the visible path | Not a no-event theta. Time passing ≠ information arriving. |
| ν (vega analogue) | `market_absolute_variation` (`Σ\|ΔK\|`) | How much the candle path wiggled | Not implied vol. Not Vega. Frozen key `realized_market_volatility` is this path descriptor. |
| B (basis) | `K − F` | Disagreement between market close and empirical F | Not edge. Not fair value residual. |
| R (residual) | `M − E[M \| core_v1]` | How unusual this measurement is versus prior same-condition observations | Not market error. Not a trade. |

## Refused (constitutionally null)

No proxy is emitted. The catalog row exists with `value=None`.

- **Λ / price impact / resilience / OBI / microprice** — need L2 or signed flow. Historical L2 is not invented. Forward-only orderbook snapshots are stored as **snapshots**, not as these Greeks.
- **possession_delta** — possessions may be REAL/PARTIAL as **data**. The Greek is still `NOT_YET_IMPLEMENTED`.
- **Fill-at-40 / slippage** — use the trades tape (`TRADE_PRINT`), not OHLC, and still do not treat a print as *your* fill.

## How to read a number

1. Confirm the information regime (`available_at < cutoff`, prior-only F).
2. Read the identity class (`DIRECT_DIFFERENCE` vs `PATH_DESCRIPTOR` vs `MICROSTRUCTURE`).
3. Do not promote a path descriptor into a surface or a microstructure object.
4. Do not feed Greeks into live Risk or Execution.

Source of truth for identities: [ROLLER_V4_GREEKS.md](ROLLER_V4_GREEKS.md) and [V4C_MEASUREMENT_CONSTITUTION.md](V4C_MEASUREMENT_CONSTITUTION.md).
