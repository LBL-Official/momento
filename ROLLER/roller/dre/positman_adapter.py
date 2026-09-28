"""Drevo-owned reader of public positman.plan.v0. Does not recompute siblings."""

from __future__ import annotations

from typing import Any

from roller.dre.models import LIVE_EXECUTION

UNAVAILABLE = "UNAVAILABLE"


def read_plan(trade_id: str, as_of: str | None = None) -> dict[str, Any]:
    from roller.positman.errors import PositmanError
    from roller.positman.service import plan

    try:
        body = plan(str(trade_id or "").strip(), as_of, record=False)
    except PositmanError as exc:
        return {
            "availability": UNAVAILABLE,
            "source_system": "position_management",
            "error_code": exc.code,
            "detail": exc.message,
            "live_execution": LIVE_EXECUTION,
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "availability": UNAVAILABLE,
            "source_system": "position_management",
            "detail": f"{type(exc).__name__}: {exc}",
            "live_execution": LIVE_EXECUTION,
        }
    if not isinstance(body, dict):
        return {"availability": UNAVAILABLE, "source_system": "position_management"}
    return {**body, "availability": body.get("availability") or "OBSERVED"}
