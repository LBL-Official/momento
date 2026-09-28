"""Phase 5–6 measurement & population capability registry.

Declarative only. Does not load observations, scan candles, or compute EV.
The executor routes using this registry; the registry does not execute.
"""

from __future__ import annotations

from typing import Any

from roller.dashboard_adapter.bindings import (
    BINDING_BARRIER_SURVIVAL_V1,
    BINDING_NCAAB_FIRST80_P5,
    BINDING_ROLLER_FIRST80,
    BINDING_WAREHOUSE_FROZEN_V1,
    NCAAB_FIRST80_P5_ARTIFACT_LABEL,
)

# Population capability rows (what populations the registry can bind).
_POPULATION_BINDINGS: list[dict[str, Any]] = [
    {
        "name": "FIRST80",
        "definition_version": BINDING_WAREHOUSE_FROZEN_V1,
        "status": "IMPLEMENTED",
        "artifacts": [
            "first80_execution_audit/candidates.json",
            "first80_quarter_barrier_survival/trades.parquet",
        ],
    },
    {
        "name": "FIRST80",
        "definition_version": BINDING_ROLLER_FIRST80,
        "status": "ABSENT_IF_UNAVAILABLE",
        "artifacts": ["roller.research.first80.load_first80"],
        "note": "No silent fallback to warehouse_frozen_v1",
    },
    {
        "name": "NCAAB_FIRST80_P5",
        "definition_version": BINDING_NCAAB_FIRST80_P5,
        "status": "IMPLEMENTED",
        "artifacts": [NCAAB_FIRST80_P5_ARTIFACT_LABEL],
        "note": (
            "Membership authority is the frozen parquet alone. "
            "No P5∩P5 reconstruction; no NBA FIRST80 fallback."
        ),
    },
]

# Measurement definitions. REGISTERED ≠ IMPLEMENTED.
_MEASUREMENTS: list[dict[str, Any]] = [
    {
        "name": "t40_rate",
        "kind": "PATH_PROPORTION",
        "definition_version": BINDING_BARRIER_SURVIVAL_V1,
        "implementation_status": "IMPLEMENTED",
        "handler_key": "t40_rate",
        "requires": {
            "fields": ["T40"],
        },
        "population_requirements": {
            "definition_families": ["FIRST80", "NCAAB_FIRST80_P5"],
        },
        "caveat": "Path condition proportion (T40 == True). MEASUREMENT ≠ EDGE. Not a win rate.",
    },
    {
        "name": "kalshi_yes_rate",
        "kind": "TERMINAL_PROPORTION",
        "definition_version": BINDING_WAREHOUSE_FROZEN_V1,
        "implementation_status": "IMPLEMENTED",
        "handler_key": "kalshi_yes_rate",
        "requires": {
            "one_of_fields": ["W", "expiration_result_yes"],
        },
        "population_requirements": {
            "definition_families": ["FIRST80", "NCAAB_FIRST80_P5"],
        },
        "caveat": "Terminal YES proportion (Kalshi settlement). Not box-score win. MEASUREMENT ≠ EDGE.",
    },
    {
        "name": "fundamental",
        "kind": "ROLLER_MEASUREMENT",
        "definition_version": "4.0.0-A",
        "implementation_status": "REGISTERED",
        "handler_key": None,
        "requires": {},
        "population_requirements": {
            "definition_family": "OBSERVATION",
        },
        "caveat": "Registered concept; Phase 5 has no authoritative bulk population producer.",
    },
    {
        "name": "market_fundamental_basis",
        "kind": "ROLLER_MEASUREMENT",
        "definition_version": "4.0.0-B",
        "implementation_status": "REGISTERED",
        "handler_key": None,
        "requires": {},
        "population_requirements": {
            "definition_family": "OBSERVATION",
        },
        "caveat": "Registered concept; Phase 5 has no authoritative bulk population producer.",
    },
    {
        "name": "residual",
        "kind": "ROLLER_MEASUREMENT",
        "definition_version": "3.0.0",
        "implementation_status": "REGISTERED",
        "handler_key": None,
        "requires": {},
        "population_requirements": {
            "definition_family": "OBSERVATION",
        },
        "caveat": "Registered concept; Phase 5 has no authoritative bulk population producer.",
    },
]


def _allowed_families(population_requirements: dict[str, Any] | None) -> list[str]:
    req = population_requirements or {}
    families = req.get("definition_families")
    if isinstance(families, list) and families:
        return [str(x) for x in families]
    singular = req.get("definition_family")
    if singular:
        return [str(singular)]
    return []


def list_population_bindings() -> list[dict[str, Any]]:
    return [dict(row) for row in _POPULATION_BINDINGS]


def list_measurements() -> list[dict[str, Any]]:
    """Public capability view — does not claim REGISTERED as IMPLEMENTED."""
    out: list[dict[str, Any]] = []
    for m in _MEASUREMENTS:
        status = m["implementation_status"]
        public_status = "IMPLEMENTED" if status == "IMPLEMENTED" else "REGISTERED_NOT_EXECUTABLE"
        out.append(
            {
                "name": m["name"],
                "kind": m["kind"],
                "definition_version": m["definition_version"],
                "status": public_status,
                "population_requirements": dict(m.get("population_requirements") or {}),
                "requires": dict(m.get("requires") or {}),
                "caveat": m.get("caveat"),
            }
        )
    return out


def get_measurement_definition(name: str) -> dict[str, Any] | None:
    if not name:
        return None
    for m in _MEASUREMENTS:
        if m["name"] == name:
            return dict(m)
    return None


def research_capabilities() -> dict[str, Any]:
    return {
        "phase": 6,
        "population_bindings": list_population_bindings(),
        "measurements": list_measurements(),
        "notes": [
            "REGISTRY ≠ EXECUTOR",
            "REGISTERED ≠ IMPLEMENTED",
            "MEASUREMENT ≠ EDGE",
            "NOT_CONSTRUCTIBLE ≠ ZERO",
            "UNSUPPORTED ≠ invent a value",
            "NCAAB_FIRST80_P5 membership = frozen parquet rows only",
        ],
    }


def resolve_measurement_request(
    request: dict[str, Any],
    *,
    definition_versions: dict[str, Any] | None = None,
    population_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Authorize a measurement_request against the registry + population context.

    Does not compute values. Returns a routing decision for the executor.
    """
    _ = definition_versions  # reserved for future version negotiation
    name = request.get("name") if isinstance(request, dict) else None
    binding = request.get("binding") if isinstance(request, dict) else None
    ctx = population_context or {}
    family = ctx.get("definition_family")

    if not name:
        return {
            "name": name,
            "route_status": "UNSUPPORTED",
            "definition_version": None,
            "handler_key": None,
            "reason": "measurement_request missing name",
            "caveat": "No registered authoritative measurement binding",
        }

    definition = get_measurement_definition(str(name))
    if definition is None:
        return {
            "name": name,
            "route_status": "UNSUPPORTED",
            "definition_version": binding,
            "handler_key": None,
            "reason": f"No registered measurement named {name!r}",
            "caveat": "No registered authoritative measurement binding",
        }

    allowed = _allowed_families(definition.get("population_requirements"))
    impl = definition.get("implementation_status")

    if impl == "IMPLEMENTED":
        if allowed and family not in allowed:
            return {
                "name": name,
                "route_status": "NOT_CONSTRUCTIBLE",
                "definition_version": definition.get("definition_version"),
                "handler_key": None,
                "reason": (
                    f"{name} requires population family in {allowed}; got family={family!r}"
                ),
                "caveat": definition.get("caveat"),
            }
        requires = definition.get("requires") or {}
        fields = list(requires.get("fields") or [])
        one_of = list(requires.get("one_of_fields") or [])
        available = set(ctx.get("available_fields") or [])
        if fields and not all(f in available for f in fields):
            return {
                "name": name,
                "route_status": "NOT_CONSTRUCTIBLE",
                "definition_version": definition.get("definition_version"),
                "handler_key": None,
                "reason": f"required fields {fields} not available on population",
                "caveat": definition.get("caveat"),
            }
        if one_of and not any(f in available for f in one_of):
            return {
                "name": name,
                "route_status": "NOT_CONSTRUCTIBLE",
                "definition_version": definition.get("definition_version"),
                "handler_key": None,
                "reason": f"none of fields {one_of} available on population",
                "caveat": definition.get("caveat"),
            }
        return {
            "name": name,
            "route_status": "IMPLEMENTED",
            "definition_version": definition.get("definition_version"),
            "handler_key": definition.get("handler_key"),
            "reason": None,
            "caveat": definition.get("caveat"),
        }

    # REGISTERED but no Phase 5/6 producer
    return {
        "name": name,
        "route_status": "NOT_CONSTRUCTIBLE",
        "definition_version": definition.get("definition_version"),
        "handler_key": None,
        "reason": (
            "No authoritative population/measurement binding for this registered concept"
        ),
        "caveat": definition.get("caveat"),
    }


__all__ = [
    "get_measurement_definition",
    "list_measurements",
    "list_population_bindings",
    "research_capabilities",
    "resolve_measurement_request",
]
