"""Positman read adapter. Does not recompute quantity × route."""

from __future__ import annotations

from typing import Any

from roller.jump.data.models import LIVE_EXECUTION, UNAVAILABLE


def plan(params: dict[str, Any]) -> dict[str, Any]:
    from roller.positman.errors import PositmanError
    from roller.positman.service import plan as build_plan

    trade_id = str(params.get("trade_id") or "").strip()
    as_of = params.get("as_of")
    try:
        body = build_plan(trade_id, None if as_of in (None, "") else str(as_of), record=False)
    except PositmanError as exc:
        return {
            "availability": UNAVAILABLE,
            "source_system": "position_management",
            "error_code": exc.code,
            "detail": exc.message,
            "trade_id": trade_id or None,
            "live_execution": LIVE_EXECUTION,
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "availability": UNAVAILABLE,
            "source_system": "position_management",
            "detail": f"{type(exc).__name__}: {exc}",
            "trade_id": trade_id or None,
            "live_execution": LIVE_EXECUTION,
        }
    return {
        "availability": body.get("availability") or "OBSERVED",
        "source_system": "position_management",
        "permission": "QUERY",
        "write": "DENY",
        "trade_id": trade_id,
        "as_of": as_of or body.get("as_of"),
        "schema": body.get("schema"),
        "position_route": body.get("position_route"),
        "planned_qty": body.get("planned_qty"),
        "plan_status": body.get("plan_status"),
        "live_execution": LIVE_EXECUTION,
        "raw": body,
    }
