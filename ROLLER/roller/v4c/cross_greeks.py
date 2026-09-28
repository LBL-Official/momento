"""Cross-Greek taxonomy facade. Architectural only. No estimators."""

from __future__ import annotations

from typing import Any

from roller.config import RollerConfig
from roller.v4c.registry import get_v4c_object

FAMILY = "cross_greeks"


def describe(cfg: RollerConfig, name: str) -> dict[str, Any]:
    row = get_v4c_object(cfg, name)
    if row.get("family") != FAMILY:
        raise KeyError(name)
    return {
        "measurement_name": name,
        "value": None,
        "status": row.get("status"),
        "reason": row.get("reason"),
        "required_information_regime": row.get("required_information_regime"),
        "architectural_only": True,
    }
