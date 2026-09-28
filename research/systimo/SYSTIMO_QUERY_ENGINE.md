# Systimo query engine (transition types)

Existing types remain. Added:

`TRANSITION_TRACE`, `CURRENT_POSITION_CHAIN`, `POSITMAN_PLAN`,
`DREVO_DECISION`, `TRANSITION_INTEGRITY`, `TRANSITION_SOURCES`,
`UNRESOLVED_TRANSITIONS`, `REJECTED_TRANSITIONS`,
`SOURCE_TO_DECISION_LINEAGE`, `LATEST_STAGE`, `ORCHESTRA_CONTEXT`.

Capabilities resolve through `roller.systimo.query.capabilities`.
Missing capability is `UNAVAILABLE`, never `$0`.
