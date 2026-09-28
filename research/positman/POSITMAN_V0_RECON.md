# Positman V0 — recon

Facts from disk. No behavior in this file.

```text
LIVE EXECUTION = FALSE
19 SYSTEMS = 19
position_management id stays
Positman is the product name
```

## Today

[`ROLLER/roller/momento/position_management.py`](../../ROLLER/roller/momento/position_management.py)
`target_from_research(hedge, rv, ...)` copies `hedge.target_exposure_bps`,
ignores RV, returns `TargetExposure` `status=RESEARCH_ONLY`.

Call site: [`lifecycle.py`](../../ROLLER/roller/momento/lifecycle.py)
`run_offline_first80` only. Types are momento envelopes
`HedgeAnalysis` / `RVHedgeAssessment`, not Ballhog/TK Ultra products.

Registry `position_management`: PARTIAL, momento_page `:5190/#/systems/position_management`,
`api_namespace` registry_only. Systimo `systems.csv` status `NOT_IMPLEMENTED`.
Edges `ballhog_to_pm` / `tk_ultra_to_pm` DECLARED DENY.

No `/positman` routes. No Vite app. Port 5194 unused.

## Canonical inputs (siblings)

Ballhog `ballhog.hedge_intent.v1` via `handle_intent(trade_id, as_of)`:
`position_id`, `as_of`, `q_star`, `rho_star`, `risk_intent`,
`hedge_feasibility`, `decision_status`, `current_exposure`.

TK Ultra `tk_ultra.assessment.v0` via `handle_assess_v0`:
`identity.{trade_id,internal_game_id,event_id,a_contract,b_contract}`,
`as_of`, `route_preference` in `BUY_B_BETTER` / `SELL_A_BETTER` / `PARITY`.

Positman must consume those public handlers. Do not import
`roller.ballhog.adapters` or `roller.tk_ultra.adapters`.

## Keep

`target_from_research` for the old lifecycle fixture. New V0 lives in
`ROLLER/roller/positman/`.
