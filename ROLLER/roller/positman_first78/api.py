"""HTTP handlers for Positman 78/67. Does not submit."""

from __future__ import annotations

from typing import Any

from roller.positman.models import LIVE_EXECUTION, PRODUCT, SYSTEM_ID
from roller.positman_first78.service import plan as build_plan
from roller.positman_first78.service import read_assessment, read_intent, sources as source_catalog


def handle_health() -> dict[str, Any]:
    return {
        "ok": True,
        "product": PRODUCT,
        "book": "FIRST78_67",
        "system_id": SYSTEM_ID,
        "canonical_role": "position_management",
        "live_execution": LIVE_EXECUTION,
        "execution_enabled": False,
        "submits": False,
        "note": "Positman 78/67 combines Ballhog quantity with the TK Ultra route. Drevo is the structural gate.",
    }


def handle_sources() -> dict[str, Any]:
    return source_catalog()


def handle_state(trade_id: str, as_of: str | None = None) -> dict[str, Any]:
    wanted = str(trade_id or "").strip()
    return {
        "product": PRODUCT,
        "book": "FIRST78_67",
        "trade_id": wanted,
        "as_of": as_of,
        "ballhog": read_intent(wanted, as_of),
        "tk_ultra": read_assessment(wanted, as_of),
        "live_execution": LIVE_EXECUTION,
    }


def handle_plan(trade_id: str | None = None, as_of: str | None = None) -> dict[str, Any]:
    return build_plan(trade_id, as_of)


def handle_trace(trace_id: str) -> dict[str, Any]:
    from roller.systimo.transitions import get_trace

    return get_trace(trace_id)
