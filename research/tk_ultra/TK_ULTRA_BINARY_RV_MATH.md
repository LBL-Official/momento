# TK Ultra — BINARY_COMPLEMENT_V0 math

Money uses `Fraction` (or integer cents). No naive `f64` equality.

`beta = -1`. `beta_source = STRUCTURAL_COMPLEMENT`.

Valid complementary anchors: `A_anchor + B_anchor = 100`. Then:

```text
EXPECTED_B = B_anchor + beta * (A_ref - A_anchor)
           = 100 - A_ref
```

If `A_anchor + B_anchor != 100`, return `ANCHOR_INVALID`. Do not silently
normalize. A documented `price_basis_transform` may explain a mismatch; stamp
it. Still no silent rewrite.

V0 anchors do not add predictive information beyond binary complementarity.

## Relationship (symmetric basis)

```text
TK_RESIDUAL = B_observed - EXPECTED_B
```

`A_ref` / `B_observed` come from a documented symmetric basis (MID, matched
candle close, Austin query price). Do not auto-set `A_ref = A_bid` and
`B_observed = B_ask` merely because those quotes exist.

CHEAP if residual < 0. RICH if residual > 0. PARITY if residual = 0.
Missing observed B → `UNAVAILABLE`. Expected B outside [0, 100] →
`MODEL_OUT_OF_BINARY_BOUNDS` (no silent clip).

## Route (A_bid / B_ask only)

```text
SYNTHETIC_A_EXIT     = 100 - B_ask
GROSS_ROUTE_EDGE     = 100 - B_ask - A_bid
B_ROUTE_PARITY_PRICE = 100 - A_bid
```

Positive edge → `BUY_B_BETTER`. Negative → `SELL_A_BETTER`. Zero → `PARITY`.
Relative preference copy only. Not an order. `route_execution_quality =
OBSERVATIONAL_ONLY` when only candles exist.

## Collinear flag

If relationship is forced onto the same bid/ask pair:

```text
relationship_route_collinear = true
TK_RESIDUAL = -GROSS_ROUTE_EDGE   # under structural β = -1
```

Those two sections are algebraically redundant. Do not present them as
independent confirmations.

## Hedge budget

```text
B_STOP_EQ           = 100 - S_A          # canonical 80/40 → 60
LOCKED_PNL          = 100 - E_A - B_avg
MAX_REMAINING_AVG   = (B_target - f * B_existing) / (1 - f)   # f < 1
```

`f = q_B / q_A`. `f = 1` or missing `B_avg` with `q_B > 0` → `UNAVAILABLE`.
Fees, slippage, fill, depth stay `UNAVAILABLE`.

Canonical identities: A entry 80 with B_avg 55/60/65 → locked PnL −35/−40/−45.

Partial example: f=0.40, B_existing=52, target=60 → max remaining 196/3
(65.333…). f=0 → 60. f=1 → UNAVAILABLE.

Acceptance route: A_bid 45, B_ask 54 → synthetic 46, edge +1, `BUY_B_BETTER`.
