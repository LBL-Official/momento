"""Load the V4A fundamental registry. No Greek families."""

from __future__ import annotations

from typing import Any

from roller.config import RollerConfig

REQUIRED_FIELDS = (
    "name",
    "family",
    "version",
    "definition",
    "formula",
    "required_inputs",
    "optional_inputs",
    "information_regime",
    "source_resolution",
    "availability_rule",
    "conditioning_schema_version",
    "support_requirements",
    "contains_future_information",
    "status",
)


def load_fundamental_registry(cfg: RollerConfig) -> dict[str, Any]:
    body = cfg.fundamental_registry or {}
    if not body.get("fundamentals"):
        raise FileNotFoundError("meta/fundamental_registry.json missing or empty")
    return body


def get_fundamental(cfg: RollerConfig, name: str) -> dict[str, Any]:
    for row in load_fundamental_registry(cfg).get("fundamentals", []):
        if row.get("name") == name:
            return row
    raise KeyError(name)
