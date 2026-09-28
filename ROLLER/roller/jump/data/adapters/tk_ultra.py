"""TK Ultra read adapter. Does not recompute residuals."""

from __future__ import annotations

from typing import Any

from roller.jump.data.models import LIVE_EXECUTION, UNAVAILABLE


def assess(params: dict[str, Any]) -> dict[str, Any]:
    from roller.tk_ultra.api import handle_assess_v0
    from roller.tk_ultra.errors import TkUltraV0Error

    trade_id = str(params.get("trade_id") or "").strip()
    as_of = params.get("as_of")
    try:
        body = handle_assess_v0({"trade_id": trade_id, "as_of": as_of, "include_sibling": False})
    except TkUltraV0Error as exc:
        return {
            "availability": UNAVAILABLE,
            "source_system": "tk_ultra",
            "error_code": exc.code,
            "detail": exc.message,
            "trade_id": trade_id or None,
            "live_execution": LIVE_EXECUTION,
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "availability": UNAVAILABLE,
            "source_system": "tk_ultra",
            "detail": f"{type(exc).__name__}: {exc}",
            "trade_id": trade_id or None,
            "live_execution": LIVE_EXECUTION,
        }
    return {
        "availability": body.get("availability") or body.get("status") or "OBSERVED",
        "source_system": "tk_ultra",
        "permission": "QUERY",
        "write": "DENY",
        "trade_id": trade_id,
        "as_of": as_of or body.get("as_of"),
        "data_mode": "HISTORICAL_QUERY",
        "tk_ultra.gross_route_edge": body.get("gross_route_edge") or body.get("route_edge"),
        "expected_wing": body.get("expected_wing"),
        "tk_residual": body.get("tk_residual") or body.get("residual"),
        "cheap_rich": body.get("cheap_rich") or body.get("rich_cheap"),
        "hedge_budget": body.get("hedge_budget"),
        "runway": body.get("runway"),
        "live_execution": LIVE_EXECUTION,
        "raw": body,
    }
