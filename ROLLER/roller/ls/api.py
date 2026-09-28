"""HTTP handlers for Momento LS. Observe only. Not Vital."""

from __future__ import annotations

from typing import Any

from roller.ls.host import compose_snapshot, inspect_host
from roller.ls.identity import INSTANCE_ID, SERVICE_NAME


def handle_health() -> dict[str, Any]:
    return {
        "ok": True,
        "product": "Momento LS",
        "observe_only": True,
        "submits": False,
        "service": SERVICE_NAME,
        "instance_id": INSTANCE_ID,
    }


def handle_observe() -> dict[str, Any]:
    raw = inspect_host()
    return compose_snapshot(raw)


def handle_snapshot() -> dict[str, Any]:
    return handle_observe()
