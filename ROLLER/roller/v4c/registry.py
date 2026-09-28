"""Authoritative V4C taxonomy. Declarative only. No estimators."""

from __future__ import annotations

from typing import Any

from roller.config import RollerConfig
from roller.v4c.information_regimes import REGIMES, RESOLUTIONS, is_regime, is_resolution, regime_of
from roller.v4c.measurement_classes import MEASUREMENT_CLASSES, is_measurement_class

REQUIRED_OBJECT_FIELDS = (
    "family",
    "measurement_name",
    "measurement_class",
    "status",
    "requires",
    "information_boundary",
    "definition_version",
    "edge_claim",
)

MAPPED_STATUSES = frozenset({"IMPLEMENTED", "PARTIAL"})
RESERVED_STATUSES = frozenset({"NOT_YET_IMPLEMENTED", "NOT_CONSTRUCTIBLE"})


def load_v4c_registry(cfg: RollerConfig) -> dict[str, Any]:
    body = cfg.greek_v4c_registry or {}
    if not body.get("objects"):
        raise FileNotFoundError("config/greek_v4c_registry.json missing or empty")
    return body


def v4c_objects(cfg: RollerConfig) -> list[dict[str, Any]]:
    return list(load_v4c_registry(cfg).get("objects") or [])


def get_v4c_object(cfg: RollerConfig, name: str) -> dict[str, Any]:
    for row in v4c_objects(cfg):
        if row.get("measurement_name") == name:
            return row
    raise KeyError(name)


def mapped_names(cfg: RollerConfig) -> list[str]:
    return [row["measurement_name"] for row in v4c_objects(cfg) if row.get("status") in MAPPED_STATUSES]


def catalog_names(cfg: RollerConfig) -> list[str]:
    return [row["measurement_name"] for row in v4c_objects(cfg) if row.get("status") in RESERVED_STATUSES]


def validate_registry_row(row: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    name = row.get("measurement_name")
    for field in REQUIRED_OBJECT_FIELDS:
        if field not in row:
            errors.append(f"{name} missing {field}")
    regime = regime_of(row)
    if not is_regime(regime):
        errors.append(f"{name} unknown regime {regime}")
    if "information_regime" not in row and "required_information_regime" not in row:
        errors.append(f"{name} missing information_regime or required_information_regime")
    status = row.get("status")
    if status in MAPPED_STATUSES:
        if row.get("definition_version") != "4.0.0-B":
            errors.append(f"{name} mapped object must keep definition_version 4.0.0-B")
        if row.get("information_regime") != "CANDLE_1M":
            errors.append(f"{name} mapped object must be CANDLE_1M")
        if row.get("resolution") != "60_SECOND_CANDLE":
            errors.append(f"{name} mapped object must be 60_SECOND_CANDLE")
    if status in RESERVED_STATUSES:
        if row.get("definition_version") is not None:
            errors.append(f"{name} reserved object must have definition_version null")
        if not row.get("reason"):
            errors.append(f"{name} reserved object missing reason")
        if "not" not in row:
            errors.append(f"{name} reserved object missing not")
    if row.get("resolution") and not is_resolution(str(row["resolution"])):
        errors.append(f"{name} unknown resolution {row.get('resolution')}")
    if row.get("edge_claim") is not False:
        errors.append(f"{name} edge_claim must be false")
    klass = row.get("measurement_class")
    if not is_measurement_class(str(klass or "")):
        errors.append(f"{name} unknown measurement_class {klass} (allowed: {MEASUREMENT_CLASSES})")
    if "conditioning_schema" not in row:
        errors.append(f"{name} missing conditioning_schema")
    if name == "realized_market_volatility":
        if row.get("canonical_identity") != "market_absolute_variation":
            errors.append("realized_market_volatility canonical_identity must be market_absolute_variation")
        if row.get("measurement_class") != "PATH_DESCRIPTOR":
            errors.append("realized_market_volatility must be PATH_DESCRIPTOR")
        if row.get("informal_family") != "VEGA_ANALOGUE":
            errors.append("realized_market_volatility informal_family must be VEGA_ANALOGUE")
    if name == "discrete_gamma" and row.get("identity_kind") != "temporal_second_difference":
        errors.append("discrete_gamma identity_kind must be temporal_second_difference")
    if name == "discrete_gamma" and row.get("measurement_class") != "EMPIRICAL_DISCRETE_SENSITIVITY":
        errors.append("discrete_gamma must be EMPIRICAL_DISCRETE_SENSITIVITY")
    if name == "score_surface_gamma" and row.get("measurement_class") != "CONDITIONAL_SURFACE":
        errors.append("score_surface_gamma must be CONDITIONAL_SURFACE")
    if name == "microprice" and row.get("measurement_class") != "MICROSTRUCTURE":
        errors.append("microprice must be MICROSTRUCTURE")
    if regime and regime not in REGIMES:
        errors.append(f"{name} regime not in REGIMES")
    if row.get("resolution") and row["resolution"] not in RESOLUTIONS:
        errors.append(f"{name} resolution not in RESOLUTIONS")
    return errors
