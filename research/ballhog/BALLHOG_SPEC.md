# Ballhog spec

```text
LIVE EXECUTION = FALSE
CANDLE PATH ≠ FILL
asked-six 1182 ≠ derived four 936 ≠ NBA 604
Austin a_t is not Ballhog alpha
THEORETICAL ≠ EXECUTABLE ≠ ECONOMICALLY BENEFICIAL
```

Ballhog is the Hedging Analysis product: **WHEN / HOW MUCH / ΔP\*(Xt) / q\***.
It is not a 20th system. BDR `#/bdr` remains the write-up library.

## Ownership

| Piece | Owner | N | Mode |
|---|---|---|---|
| remaining α(Xt) + uncertainty | Austin | 604 | HISTORICAL_QUERY |
| FIRST80 / 80→40 population prior | Choosin Texas | 936 | STATIC |
| WHEN / q\* / ρ\* / Δ\* | Ballhog | — | research |
| how q\* is expressed | TK Ultra | — | formula |
| combine current vs target | Position Management | — | NOT_IMPLEMENTED |
| accept/reject | DRE | — | observation |
| orders | Execution | — | DISABLED |

## Arithmetic

```text
L(p) = 20 − p     per paired unit
EV_before = n * a_t
portfolio_EV_after = (n − q) * a_t + q * (20 − p)
economic_EV_cost_of_hedge = q * [a_t − (20 − p)]
```

`economic_EV_cost_of_hedge` may be negative. Do not clamp. Do not call it
alpha surrendered. Assumed `p` is THEORETICAL / CANDLE_PATH.

Replay default `q_dir = 1` so `q ∈ {0,1}`. Explicit integer `q_dir` scales
the transformation only. Austin evidence stays per research unit. Policy
`max_q_dir` (500) is the ceiling. Non-integers are `INVALID_QUANTITY`.

## Optimizer (two-stage)

Stage A `risk_intent` is the existing timing state:
`RETAIN | WATCH | BEGIN_REDUCTION | REDUCE | NEUTRALIZE | UNAVAILABLE`.
Timing is never mutated to `REDUCE` because a hedge cell was chosen.

Stage B `hedge_feasibility` looks only at frontier cells with `q_hedge > 0`
and `robust_portfolio_EV_after > 0`.

| risk_intent | non-zero admissible | result |
|---|---|---|
| RETAIN / WATCH | ignored | `q*=0`, `NOT_REQUESTED`, `RESOLVED` |
| BEGIN_REDUCTION / REDUCE / NEUTRALIZE | exactly one | that candidate, `ADMISSIBLE_HEDGE_AVAILABLE`, `RESOLVED` |
| same | more than one, no YAML tie-break | `q*=null`, `POLICY_UNRESOLVED` |
| same | none, unhedged `n*a_L > 0` | `q*=0`, `NO_ADMISSIBLE_HEDGE`, `RESOLVED` |
| NEUTRALIZE | none, unhedged `n*a_L <= 0` | `q*=null`, `decision_status=UNAVAILABLE`, `ROBUST_PORTFOLIO_NONPOSITIVE` |
| SOURCE_UNAVAILABLE | — | `hedge_feasibility=SOURCE_UNAVAILABLE` |

`NO_ADMISSIBLE_HEDGE` fires only when reduction is requested and no `q>0`
candidate is economically admissible. Not for missing data, not for ties.

`BEGIN_REDUCTION` + `NO_ADMISSIBLE_HEDGE` + `q*=0` is a valuable state:
risk-off is indicated, but no modeled 35–45 hedge preserves
`robust_portfolio_EV_after > 0`.

Pareto is still `economic_EV_cost_of_hedge` vs `T40_RISK_PROXY`
`risk_removed`. No λ. No Λα. No silent nearest-looking pick.

## Timing

`RETAIN | WATCH | BEGIN_REDUCTION | REDUCE | NEUTRALIZE` from Austin
evidence + policy thresholds only. 35–45 is a counterfactual price grid,
not `if A2 <= 45` and not `if A1 <= 55`.

`current_hedge_price = UNAVAILABLE` until an approved source has a PIT
hedge-side print.

## default_as_of (UX only)

```text
default_as_of = Austin replay path midpoint index // 2
replay_available = path is non-empty
```

This is not a second evidence definition. Do not search for
deterioration. Do not use settlement. Do not call `query_at` to pick the
stamp.

## Absolute

- Do not submit. `execution_enabled` is false in the package.
- Do not invent fills, L2, λ, Λα, live Xt, or BUY NO taker.
- Do not modify `GET /momento/tk-ultra/assess`.
- Do not fake Position Management.
- Do not mix 604 into 936.
- Do not edit `first80.py`, live FIRST01 / 80/81/83/89, `book.json`, W9,
  or warehouse Phase 21.
