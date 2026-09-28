"""Systimo V0 constants. Not live. Not a 20th system."""

from __future__ import annotations

from datetime import datetime, timezone

LIVE_EXECUTION = False
PRODUCT = "Systimo"
SYSTEM_ID = "system_maintenance"
MOMENTO_SLOT = "system_maintenance"
AUSTIN_N = 604
AUSTIN_UNIVERSE = "choosin_nba_2q3q_604"
CHOOSIN_N = 936
CHOOSIN_UNIVERSE = "derived_four_936"
UNAVAILABLE = "UNAVAILABLE"
ANSWER_SCHEMA = "systimo.answer.v0"

HEALTH_STATES = (
    "HEALTHY",
    "DEGRADED",
    "UNAVAILABLE",
    "MISCONFIGURED",
    "STALE",
    "UNKNOWN",
)
LIFECYCLES = ("DECLARED", "IMPLEMENTED", "DEPRECATED", "DISABLED")
PERMISSIONS = ("READ", "QUERY", "WRITE", "CONTROL", "DENY")
CONNECTION_TYPES = (
    "API_READ",
    "DOMAIN_CALL",
    "FILE_READ",
    "WAREHOUSE_QUERY",
    "ARTIFACT_READ",
    "ARTIFACT_WRITE",
    "HEALTH_CHECK",
)
QUERY_TYPES = (
    "systems",
    "connections",
    "dependencies",
    "reverse_dependencies",
    "datasets",
    "interfaces",
    "health",
    "artifacts",
    "provenance",
    "paths",
    "path_back",
    "drift",
    "governance",
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
ALLOWLISTED_ACTIONS = (
    "REFRESH_CONNECTION",
    "RECHECK_HEALTH",
    "REBUILD_QUERY_INDEX",
    "REGENERATE_TREE",
    "EXPORT_ARTIFACT",
    "VALIDATE_SCHEMA",
)
EXECUTION_MODES = ("OBSERVE", "PLAN", "APPLY")


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
