"""Static dashboard JSON. Not a live trading interface."""

from __future__ import annotations

from . import config as C


def export(payload: dict) -> dict:
    C.DASH_PUBLIC.mkdir(parents=True, exist_ok=True)
    C.write_json(C.DASH_PUBLIC / "dashboard.json", payload)
    C.write_json(C.OUT / "dashboard.json", payload)
    return payload
