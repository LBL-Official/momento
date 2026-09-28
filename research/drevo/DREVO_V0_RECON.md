# Drevo V0 — recon

Facts from disk. Canonical product name for existing DRE.

```text
LIVE EXECUTION = FALSE
Do not create another DRE
/dre/* remains
frontend/dynamic-risk-engine :5191 remains
```

## Today

Package [`ROLLER/roller/dre/`](../../ROLLER/roller/dre/).
API `/dre/*` on `:8791`. Frontend `:5191`.
Upstream: Austin + Choosin only. No Ballhog, TK Ultra, or Position Management.

[`models.py`](../../ROLLER/roller/dre/models.py) `PRODUCT = "DRE"`.
`hold_reason_v1` = `MODEL_OBSERVATION_ONLY`.
`dynamic_risk_class` = `UNAVAILABLE`.
`intervention_stub()`: `policy_status=NO_POLICY_FROZEN`, `authorized=False`,
`execution_enabled=False`.

[`PORTFOLIO_OBJECTIVE_V1.md`](../dre/PORTFOLIO_OBJECTIVE_V1.md) calculus
`NOT_IMPLEMENTED`. No policy YAML. Do not invent ACCEPT thresholds.

## V0

Drevo consumes `positman.plan.v0` through a Drevo-owned adapter.
Structural VALID/INVALID separate from `POLICY_UNRESOLVED`.
`execution_authorized` always false.
Keep Austin/Choosin independent context on the existing position page.
