"""Locked transition data types. Systimo-owned. Not product economics."""

from __future__ import annotations

LIVE_EXECUTION = False
CANDLE_PATH_IS_FILL = False

# Canonical object schemas. Product packages remain the business SSOT.
LOCKED_SCHEMAS = (
    "ballhog.hedge_intent.v1",
    "tk_ultra.assessment.v0",
    "positman.plan.v0",
    "drevo.decision.v0",
    "positman.execution_boundary.v0",
    "systimo.transition_trace.v0",
    "systimo.orchestra_context.v0",
)

STAGE_ORDER = (
    "SOURCE_STATE",
    "BALLHOG_INTENT",
    "TK_ULTRA_ASSESSMENT",
    "POSITMAN_PLAN",
    "DREVO_DECISION",
    "EXECUTION_BOUNDARY",
    "VITAL_STATE",
    "JUMP_OBSERVATION",
)

STAGE_SEQ = {
    "SOURCE_STATE": 100,
    "BALLHOG_INTENT": 200,
    "TK_ULTRA_ASSESSMENT": 300,
    "POSITMAN_PLAN": 400,
    "DREVO_DECISION": 500,
    "EXECUTION_BOUNDARY": 600,
    "VITAL_STATE": 700,
    "JUMP_OBSERVATION": 800,
}

IDENTITY_FIELDS = (
    "trade_id",
    "internal_game_id",
    "event_id",
    "a_contract",
    "b_contract",
    "as_of",
)

MATCH_STATUSES = (
    "MATCHED",
    "IDENTITY_MISMATCH",
    "STATE_TIME_MISMATCH",
)

POSITION_ROUTES = (
    "NO_CHANGE",
    "ACQUIRE_B",
    "REDUCE_A",
    "ROUTE_PARITY_UNRESOLVED",
    "WAIT_FOR_ROUTE",
    "PLAN_UNRESOLVED",
    "SOURCE_UNAVAILABLE",
    "IDENTITY_MISMATCH",
)

PLAN_STATUSES = (
    "PLAN_RESOLVED",
    "PLAN_UNRESOLVED",
    "SOURCE_UNAVAILABLE",
    "IDENTITY_MISMATCH",
    "STATE_TIME_MISMATCH",
)

DECISION_STATUSES = (
    "POLICY_UNRESOLVED",
    "REJECT",
    "SOURCE_UNAVAILABLE",
    "IDENTITY_MISMATCH",
)

STRUCTURAL_STATUSES = ("VALID", "INVALID")

INTEGRITY_STATUSES = (
    "VERIFIED",
    "HASH_MISMATCH",
    "TRANSITION_INTEGRITY_ERROR",
    "UNAVAILABLE",
)

EXECUTION_STATUSES = ("NOT_SUBMITTED", "EXECUTION_DISABLED")

TRANSITION_QUERY_TYPES = (
    "TRANSITION_TRACE",
    "CURRENT_POSITION_CHAIN",
    "POSITMAN_PLAN",
    "DREVO_DECISION",
    "TRANSITION_INTEGRITY",
    "TRANSITION_SOURCES",
    "UNRESOLVED_TRANSITIONS",
    "REJECTED_TRANSITIONS",
    "SOURCE_TO_DECISION_LINEAGE",
    "LATEST_STAGE",
    "ORCHESTRA_CONTEXT",
)

CAPABILITIES = (
    "BALLHOG_INTENT",
    "TK_ULTRA_ASSESSMENT",
    "POSITMAN_PLAN",
    "DREVO_DECISION",
    "TRANSITION_TRACE",
    "ORCHESTRA_CONTEXT",
)

ORCHESTRA_NAMESPACES = (
    "austin",
    "choosin_texas",
    "ballhog",
    "tk_ultra",
    "positman",
    "drevo",
    "execution_boundary",
    "vital",
    "jump",
)

UNAVAILABLE = "UNAVAILABLE"
MISSING_IS_NEVER_ZERO = True
