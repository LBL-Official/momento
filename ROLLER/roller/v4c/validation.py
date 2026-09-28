"""Thin exports used by validate_roller hooks."""

from __future__ import annotations

from typing import Any

from roller.config import RollerConfig
from roller.v4c.registry import validate_registry_row, v4c_objects


def audit_registry(cfg: RollerConfig) -> list[str]:
    errors: list[str] = []
    seen: set[str] = set()
    for row in v4c_objects(cfg):
        name = str(row.get("measurement_name") or "")
        if name in seen:
            errors.append(f"duplicate measurement_name {name}")
        seen.add(name)
        errors.extend(validate_registry_row(row))
        if row.get("edge_claim"):
            errors.append(f"{name} claims edge")
    return errors
