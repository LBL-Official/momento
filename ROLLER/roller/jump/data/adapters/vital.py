"""Vital observe adapter. Jump does not own execution."""

from __future__ import annotations

from typing import Any

from roller.jump.data.models import LIVE_EXECUTION, UNAVAILABLE
from roller.jump.vital_client import vital_bot_health


def status(_params: dict[str, Any] | None = None) -> dict[str, Any]:
    try:
        body = vital_bot_health()
    except Exception as exc:  # noqa: BLE001
        return {
            "availability": UNAVAILABLE,
            "source_system": "vital",
            "detail": f"{type(exc).__name__}: {exc}",
            "live_execution": LIVE_EXECUTION,
        }
    return {
        "availability": body.get("availability") or body.get("status") or "OBSERVED",
        "source_system": "vital",
        "permission": "QUERY",
        "write": "DENY",
        "data_mode": "OBSERVE",
        "live_execution": LIVE_EXECUTION,
        "raw": body,
    }
