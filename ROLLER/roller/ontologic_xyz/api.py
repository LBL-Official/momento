"""Read the stored date probe and the joint status. Does not submit."""

from __future__ import annotations

from typing import Any

from roller.ontologic_xyz.probe import probe_day
from roller.ontologic_xyz.status import joint_status


def handle_health() -> dict[str, Any]:
    return {
        "ok": True,
        "product": "Ontologic XYZ",
        "live_execution": False,
        "submits": False,
        "x": "the_odds_api",
        "y": "MARKET_MODEL_UNAVAILABLE",
        "z": "NOT_CALIBRATED",
    }


def handle_status(day: str = "2026-10-03") -> dict[str, Any]:
    return joint_status(day)


def handle_probe(day: str = "2026-10-03") -> dict[str, Any]:
    return probe_day(day)
