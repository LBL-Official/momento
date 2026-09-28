"""Backward event-type sequences."""

from __future__ import annotations

from typing import Any


def event_type_sequence(events: list[dict[str, Any]], last_n: int = 8) -> list[str]:
    return [str(e.get("event_type") or "") for e in events[-last_n:]]
