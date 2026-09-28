"""Static dashboard JSON. Does not fit models."""

from __future__ import annotations

from . import config as C


def export(payload: dict) -> None:
    C.DASH_PUBLIC.mkdir(parents=True, exist_ok=True)
    C.write_json(C.DASH_PUBLIC / "dashboard.json", payload)
    C.write_json(C.OUT / "14_dashboard.json", payload)
