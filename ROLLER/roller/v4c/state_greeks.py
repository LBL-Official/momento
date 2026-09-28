"""State-Greek taxonomy facade. No estimators."""

from __future__ import annotations

from typing import Any

from roller.config import RollerConfig
from roller.v4c.capability import possession_delta_authorized
from roller.v4c.registry import get_v4c_object

FAMILY = "state_greeks"


def describe(cfg: RollerConfig, name: str) -> dict[str, Any]:
    row = get_v4c_object(cfg, name)
    if row.get("family") != FAMILY:
        raise KeyError(name)
    if name == "possession_delta" and possession_delta_authorized():
        raise RuntimeError("possession_delta must remain NOT_YET_IMPLEMENTED")
    if row.get("status") in {"IMPLEMENTED", "PARTIAL"}:
        raise ValueError(f"{name} is a V4B measurement; use db.greeks schema_version=4.0.0-C")
    return {
        "measurement_name": name,
        "value": None,
        "status": row.get("status"),
        "reason": row.get("reason"),
        "required_information_regime": row.get("required_information_regime"),
    }
