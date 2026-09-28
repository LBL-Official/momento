"""Positman constants. LIVE EXECUTION = FALSE."""

from __future__ import annotations

from datetime import datetime, timezone

LIVE_EXECUTION = False
PRODUCT = "Positman"
SYSTEM_ID = "position_management"
PLAN_SCHEMA = "positman.plan.v0"
BOUNDARY_SCHEMA = "positman.execution_boundary.v0"
DEFAULT_TRADE_ID = "f84fd059fc0e1429"
UNAVAILABLE = "UNAVAILABLE"

ROUTES = (
    "NO_CHANGE",
    "ACQUIRE_B",
    "REDUCE_A",
    "ROUTE_PARITY_UNRESOLVED",
    "WAIT_FOR_ROUTE",
    "PLAN_UNRESOLVED",
    "SOURCE_UNAVAILABLE",
    "IDENTITY_MISMATCH",
)


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
