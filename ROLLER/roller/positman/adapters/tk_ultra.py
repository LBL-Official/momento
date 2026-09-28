"""Public TK Ultra assessment reader. Does not import roller.tk_ultra.adapters."""

from __future__ import annotations

from typing import Any

from roller.positman.models import LIVE_EXECUTION, UNAVAILABLE


def read_assessment(trade_id: str, as_of: str | None = None) -> dict[str, Any]:
    from roller.tk_ultra.api import handle_assess_v0
    from roller.tk_ultra.errors import TkUltraV0Error

    try:
        body = handle_assess_v0({"trade_id": trade_id, "as_of": as_of, "include_sibling": False})
    except TkUltraV0Error as exc:
        return {
            "availability": UNAVAILABLE,
            "source_system": "tk_ultra",
            "error_code": exc.code,
            "detail": exc.message,
            "live_execution": LIVE_EXECUTION,
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "availability": UNAVAILABLE,
            "source_system": "tk_ultra",
            "detail": f"{type(exc).__name__}: {exc}",
            "live_execution": LIVE_EXECUTION,
        }
    return {
        "availability": body.get("availability") or "OBSERVED",
        "source_system": "tk_ultra",
        "schema": body.get("schema") or "tk_ultra.assessment.v0",
        "assessment": body,
        "live_execution": LIVE_EXECUTION,
    }
