# TK Ultra V0 data contract

Schema: `tk_ultra.assessment.v0`.

Identity fields (aligned with `BallhogHedgeIntent` when present; never invented):

- `trade_id`
- `internal_game_id`
- `event_id`
- `a_contract` / `b_contract`
- `as_of`

## Universes

| Source | Universe | N | Adapter |
|---|---|---|---|
| Austin | `choosin_nba_2q3q_604` | 604 | `roller.tk_ultra.adapters.austin` (`query_at`, persist=False) |
| Choosin Texas | `derived_four_936` | 936 | `roller.tk_ultra.adapters.choosin` (`get_trade_context`, STATIC) |

Never sum N. Never import `roller.ballhog.adapters`.

## Feeds

`feed_mode`: `HISTORICAL | REPLAY | MANUAL_INPUT | UNAVAILABLE`.
`live_feed`: always `UNAVAILABLE`.
`execution_enabled`: false.

## Price bases (separate)

| Layer | Basis | Fields |
|---|---|---|
| Relationship | documented symmetric (`MID`, `AUSTIN_QUERY_PRICE`, …) | `a_ref_basis`, `observed_wing_basis` |
| Route | `YES_BID` / `YES_ASK` | `a_bid_basis`, `b_ask_basis` |

Stamp `relationship_route_collinear` when those numbers coincide.

## Reason codes (only when a rule fires)

Examples: `WING_CHEAP_TO_RELATIONSHIP`, `BUY_B_GROSS_ROUTE_BETTER`,
`QUOTE_UNAVAILABLE`, `ANCHOR_INVALID`, `RELATIONSHIP_ROUTE_COLLINEAR`,
`BALLHOG_CONTEXT_UNAVAILABLE`, `EXISTING_B_AVG_UNAVAILABLE`,
`HEDGE_BUDGET_UNAVAILABLE`.

No fake TK confidence.

## HTTP

Preserve:

- `GET /momento/tk-ultra`
- `GET /momento/tk-ultra/assess` (`GENERIC_RV`, same query contract)

Add:

- `GET /momento/tk-ultra/health`
- `GET /momento/tk-ultra/sources`
- `GET /momento/tk-ultra/positions`
- `GET /momento/tk-ultra/state/{trade_id}?as_of=&include_sibling=`
- `POST /momento/tk-ultra/assess` (`BINARY_COMPLEMENT_V0`)
- `GET /momento/tk-ultra/ballhog-context/{trade_id}?as_of=`

Missing quotes, anchors, or B_avg with q_B>0 → `UNAVAILABLE`, never `$0`.
Fees are not zeroed.
