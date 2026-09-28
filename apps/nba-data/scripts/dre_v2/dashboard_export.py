"""Write static dashboard JSON. Not a live trading interface."""

from __future__ import annotations

from . import config as C


def export_dashboard(payload: dict) -> dict:
    C.DASH_PUBLIC.mkdir(parents=True, exist_ok=True)
    C.write_json(C.DASH_PUBLIC / "dashboard.json", payload)
    C.write_json(C.OUT / "16_dashboard" / "dashboard.json", payload)
    return payload
