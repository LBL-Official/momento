# Positman data contract

Schema `positman.plan.v0`.

Required: `schema`, `trace_id`, `identity`, `as_of`, `match_status`,
`ballhog_ref`, `tk_ultra_ref`, `risk_intent`, `requested_reduction_qty`,
`route_preference`, `position_route`, `planned_qty`, `plan_status`,
`reason_codes`, `quantity_source=BALLHOG`, `route_source=TK_ULTRA`,
`execution_enabled=false`, `created_at`.

Missing is `UNAVAILABLE`, never `$0`. Candle path is not a fill.
