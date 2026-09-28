"""Independent availability clocks. Do not collapse to a generic timestamp.

event occurrence time
    ≠ source publication time
    ≠ database availability time
    ≠ measurement availability time

V4C declares these clocks. It does not compute future-regime measurements.
"""

from __future__ import annotations

from typing import Any

DECLARED_CLOCKS = (
    "state_available_at",
    "candle_available_at",
    "measurement_available_at",
    "event_available_at",
    "trade_available_at",
    "book_snapshot_available_at",
)

FUTURE_REGIME_CLOCKS = frozenset(
    {
        "event_available_at",
        "trade_available_at",
        "book_snapshot_available_at",
    }
)


def declare_clocks(v4b_payload: dict[str, Any] | None = None) -> dict[str, Any]:
    """Copy known V4B clocks. Leave future-regime clocks explicitly null."""
    src = v4b_payload or {}
    availability = src.get("availability") or {}
    market = src.get("market") or {}
    copied = {
        "state_available_at": availability.get("state_available_at"),
        "candle_available_at": market.get("available_at"),
        "measurement_available_at": availability.get("measurement_available_at"),
        "event_available_at": None,
        "trade_available_at": None,
        "book_snapshot_available_at": None,
    }
    return {
        "declared": list(DECLARED_CLOCKS),
        "values": copied,
        "collapsed_to_timestamp": False,
        "note": "future-regime clocks are declared, not computed",
    }
