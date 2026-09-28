# Drevo V0 spec

Canonical product name for the existing Dynamic Risk Engine.

```text
LIVE EXECUTION = FALSE
/dre/* remains
frontend/dynamic-risk-engine :5191 remains
execution_authorized = false
```

`drevo.decision.v0` consumes `positman.plan.v0`. Structural `VALID`/`INVALID`
is separate from `POLICY_UNRESOLVED`. V0 has no frozen ACCEPT policy
(`NO_POLICY_FROZEN`). Do not invent Λα or ACCEPT thresholds.

Austin/Choosin position observation stays independent on `/dre/positions*`.
`/drevo/*` is an alias.
