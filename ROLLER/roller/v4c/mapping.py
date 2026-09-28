"""Lossless V4B → V4C overlay. Copy rationals. Attach identity. Compute nothing.

V4C_EMPIRICAL_COMPUTATION_COUNT = 0
"""

from __future__ import annotations

from typing import Any

from roller.config import RollerConfig
from roller.v4c import V4C_EMPIRICAL_COMPUTATION_COUNT
from roller.v4c.availability import declare_clocks
from roller.v4c.capability import MAPPED_STATUSES, instance_status
from roller.v4c.information_regimes import regime_of
from roller.v4c.provenance import measurement_provenance
from roller.v4c.registry import load_v4c_registry, v4c_objects
from roller.v4c.types import contract_from_row, identity_from_row

SCHEMA_VERSION = "4.0.0-C"
ARCHITECTURE_VERSION = "4.0.0-C"
SOURCE_GREEK_SCHEMA = "4.0.0-B"


def copy_rational(value: Any) -> dict[str, Any] | None:
    """Copy V4B numerator/denominator. Do not reduce, recompute, or float."""
    if value is None:
        return None
    if not isinstance(value, dict):
        raise TypeError("V4C may only copy a V4B rational dict")
    if "numerator" not in value or "denominator" not in value:
        raise ValueError("V4C rational copy requires numerator and denominator")
    out = {
        "numerator": value["numerator"],
        "denominator": value["denominator"],
    }
    if "units" in value:
        out["units"] = value["units"]
    return out


def _map_measurement(row: dict[str, Any], source: dict[str, Any]) -> dict[str, Any]:
    identity = identity_from_row(row)
    src_status = source.get("status")
    value = copy_rational(source.get("value"))
    status = instance_status(src_status, str(row.get("status")))
    prov = measurement_provenance(identity, source_status=src_status)
    return {
        "value": value,
        "status": status,
        "identity": identity.public(),
        "contract": contract_from_row(row).public(),
        "provenance": prov.public(),
    }


def _map_catalog(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "value": None,
        "status": row.get("status"),
        "measurement_class": row.get("measurement_class"),
        "canonical_identity": row.get("canonical_identity") or row.get("measurement_name"),
        "conditioning_schema": row.get("conditioning_schema"),
        "informal_family": row.get("informal_family"),
        "required_information_regime": row.get("required_information_regime") or regime_of(row),
        "resolution": row.get("resolution"),
        "requires": list(row.get("requires") or []),
        "information_boundary": row.get("information_boundary"),
        "definition_version": row.get("definition_version"),
        "edge_claim": False,
        "reason": row.get("reason"),
        "not": list(row.get("not") or []),
    }


def overlay_architecture(cfg: RollerConfig, v4b_payload: dict[str, Any]) -> dict[str, Any]:
    """Consume a canonical V4B payload. Do not reconstruct X_t."""
    if V4C_EMPIRICAL_COMPUTATION_COUNT != 0:
        raise RuntimeError("V4C must not compute empirical Greeks")
    body = load_v4c_registry(cfg)
    observed = v4b_payload.get("observed") or {}
    measurements: dict[str, Any] = {}
    catalog: dict[str, Any] = {}
    for row in v4c_objects(cfg):
        name = str(row["measurement_name"])
        if row.get("status") in MAPPED_STATUSES:
            measurements[name] = _map_measurement(row, observed.get(name) or {})
        else:
            catalog[name] = _map_catalog(row)
    identity = v4b_payload.get("identity") or {}
    return {
        "schema_version": SCHEMA_VERSION,
        "greek_architecture_version": body.get("greek_architecture_version") or ARCHITECTURE_VERSION,
        "source_measurement_schema": {"greek_schema_version": SOURCE_GREEK_SCHEMA},
        "observation_id": identity.get("observation_id"),
        "measurements": measurements,
        "catalog": catalog,
        "availability": declare_clocks(v4b_payload),
        "empirical_computation_count": V4C_EMPIRICAL_COMPUTATION_COUNT,
        "contains_future_information": True,
    }
