"""Systimo catalog adapter. Jump does not own the registry."""

from __future__ import annotations

from typing import Any

from roller.jump.data.catalog import jump_connections, sources
from roller.jump.data.models import LIVE_EXECUTION


def catalog(_params: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "availability": "OBSERVED",
        "source_system": "systimo",
        "permission": "QUERY",
        "write": "DENY",
        "live_execution": LIVE_EXECUTION,
        "sources": sources(),
        "connections": jump_connections(),
    }
