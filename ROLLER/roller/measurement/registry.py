"""Load and query the V3 measurement registry."""

from __future__ import annotations

from typing import Any

from roller.config import RollerConfig


REQUIRED_FIELDS = (
    "measurement_name",
    "measurement_version",
    "family",
    "description",
    "mathematical_definition",
    "required_inputs",
    "information_boundary",
    "output_type",
    "source_resolution",
    "sport_capability",
    "status",
    "contains_future_information",
    "label_dependency",
    "provenance_requirements",
    "conditioning_dimensions",
    "implementation_status",
)


def load_measurement_registry(cfg: RollerConfig) -> dict[str, Any]:
    body = cfg.measurement_registry or {}
    if not body.get("measurements"):
        raise FileNotFoundError("meta/measurement_registry.json missing or empty")
    return body


def implemented_measurements(body: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        m
        for m in body.get("measurements", [])
        if m.get("implementation_status") == "IMPLEMENTED"
    ]


def get_measurement(cfg: RollerConfig, name: str) -> dict[str, Any]:
    for m in load_measurement_registry(cfg).get("measurements", []):
        if m.get("measurement_name") == name:
            return m
    raise KeyError(name)
