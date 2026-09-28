"""Positman HTTP handlers."""

from __future__ import annotations

from typing import Any

from roller.positman.models import DEFAULT_TRADE_ID, LIVE_EXECUTION, PRODUCT, SYSTEM_ID
from roller.positman.service import plan as build_plan
from roller.positman.service import sources as source_catalog


def handle_health() -> dict[str, Any]:
    return {
        "ok": True,
        "product": PRODUCT,
        "system_id": SYSTEM_ID,
        "canonical_role": "position_management",
        "live_execution": LIVE_EXECUTION,
        "execution_enabled": False,
        "submits": False,
        "note": "Positman combines Ballhog quantity with TK Ultra route. Does not submit.",
    }


def handle_sources() -> dict[str, Any]:
    return source_catalog()


def handle_state(trade_id: str, as_of: str | None = None) -> dict[str, Any]:
    from roller.positman.adapters.ballhog import read_intent
    from roller.positman.adapters.tk_ultra import read_assessment

    wanted = str(trade_id or DEFAULT_TRADE_ID).strip()
    return {
        "product": PRODUCT,
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
