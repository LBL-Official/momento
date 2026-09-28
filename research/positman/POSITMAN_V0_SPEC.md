# Positman V0 spec

```text
LIVE EXECUTION = FALSE
CANDLE PATH ≠ FILL
quantity_source = BALLHOG
route_source = TK_ULTRA
execution_enabled = false
```

Positman is the Position Management product (`position_management`).
It composes `ballhog.hedge_intent.v1` × `tk_ultra.assessment.v0` into
`positman.plan.v0`. It does not recompute siblings. It does not submit.

Routes: `NO_CHANGE`, `ACQUIRE_B`, `REDUCE_A`, `ROUTE_PARITY_UNRESOLVED`,
`WAIT_FOR_ROUTE`, `PLAN_UNRESOLVED`, `SOURCE_UNAVAILABLE`, `IDENTITY_MISMATCH`.

API: `/positman/*` on `:8791`. Frontend: `frontend/positman` `:5194`.
Acceptance trade: `f84fd059fc0e1429`.
