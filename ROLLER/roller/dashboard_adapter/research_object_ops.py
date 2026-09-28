"""Phase 2 Research Object operations — structural only.

Wraps existing validate_research_spec. No scan, EV, observation, or path evaluation.
"""

from __future__ import annotations

import json
from typing import Any

from roller.dashboard_adapter.research_object import (
    SAMPLES_DIR,
    compute_research_object_id,
    load_sample,
    validate_research_spec,
)
from roller.dashboard_adapter.serialize import to_jsonable

_TEMPLATE_FILES: list[tuple[str, str, str]] = [
    ("FIRST80_Q3", "FIRST80 Q3", "first80_q3_path_terminal.json"),
    (
        "NCAAB_FIRST80_P5",
        "NCAAB FIRST80 P5",
        "ncaab_first80_p5_path_terminal.json",
    ),
    ("LARGE_DOWN_MOVE_Q4", "Large Down Move Q4", "observation_large_move_unresolved.json"),
    (
        "BASIS_EXTREME_AT_OBSERVATION",
        "Basis Extreme at Observation",
        "fundamental_basis_measurement.json",
    ),
]

_UNRESOLVED_REASONS: dict[str, str] = {
    "anchor.magnitude_e4": "PRICE_MOVE magnitude must be explicit",
    "anchor.favorite_definition": "favorite definition must be explicit",
    "anchor.direction": "anchor direction is UNRESOLVED",
    "execution_interpretation": "execution_interpretation is UNRESOLVED",
    "information_regime": "information_regime is UNRESOLVED",
    "population_binding.calendar_scope": (
        "season / season_month / season_week filters are STRUCTURAL — "
        "no Phase 0–6 population route applies them yet"
    ),
}


def _reason_for(field: str) -> str:
    if field in _UNRESOLVED_REASONS:
        return _UNRESOLVED_REASONS[field]
    if field.startswith("path_conditions"):
        return "path condition is UNRESOLVED or has UNRESOLVED binding"
    if field.startswith("terminal_conditions"):
        return "terminal condition kind is UNRESOLVED"
    if field.startswith("measurement_requests"):
        return "measurement binding is UNRESOLVED"
    if field.startswith("anchor."):
        return f"{field} must be resolved before run"
    return f"{field} is unresolved"


def _status_for(*, valid: bool, runnable: bool, unresolved: list[Any]) -> str:
    if not valid:
        return "INVALID"
    if unresolved:
        return "UNRESOLVED"
    if runnable:
        return "RUNNABLE"
    return "UNRESOLVED"


def validate_for_api(spec: dict[str, Any]) -> dict[str, Any]:
    """Wrap validate_research_spec for Terminal API responses."""
    result = validate_research_spec(spec)
    unresolved = [{"field": f, "reason": _reason_for(f)} for f in result.unresolved]
    status = _status_for(valid=result.ok, runnable=result.runnable, unresolved=unresolved)
    return to_jsonable(
        {
            "valid": result.ok,
            "runnable": bool(result.runnable and result.ok and not unresolved),
            "status": status,
            "research_object_id": result.research_object_id,
            "errors": list(result.errors),
            "unresolved": unresolved,
        }
    )


def preview_research_object(spec: dict[str, Any]) -> dict[str, Any]:
    """Structural preview only — no empirical execution."""
    validation = validate_for_api(spec)
    identity = spec.get("identity") if isinstance(spec.get("identity"), dict) else {}
    population = (
        spec.get("population_binding") if isinstance(spec.get("population_binding"), dict) else {}
    )
    anchor = spec.get("anchor") if isinstance(spec.get("anchor"), dict) else {}
    path = spec.get("path_conditions") if isinstance(spec.get("path_conditions"), list) else []
    terminal = (
        spec.get("terminal_conditions") if isinstance(spec.get("terminal_conditions"), list) else []
    )
    measurements = (
        spec.get("measurement_requests") if isinstance(spec.get("measurement_requests"), list) else []
    )
    state = spec.get("state_filters")

    rid = validation.get("research_object_id")
    if rid is None and validation.get("valid"):
        rid = compute_research_object_id(spec)

    return to_jsonable(
        {
            "research_object_id": rid,
            "normalized_spec": spec,
            "identity": identity,
            "universe": spec.get("universe"),
            "population": population,
            "anchor": anchor,
            "information": {
                "information_regime": spec.get("information_regime"),
                "information_set": spec.get("information_set"),
            },
            "state": state,
            "path": path,
            "terminal": terminal,
            "measurements": measurements,
            "definition_versions": spec.get("definition_versions") or {},
            "dataset_versions": spec.get("dataset_versions") or {},
            "execution_interpretation": spec.get("execution_interpretation"),
            "caveats": spec.get("caveats") or [],
            "valid": validation.get("valid"),
            "runnable": validation.get("runnable"),
            "status": validation.get("status"),
            "errors": validation.get("errors") or [],
            "unresolved": validation.get("unresolved") or [],
            "note": "STRUCTURAL PREVIEW ONLY — no empirical execution",
        }
    )


def list_templates() -> list[dict[str, Any]]:
    """Load Phase 0 sample research_specs as templates."""
    out: list[dict[str, Any]] = []
    for tid, label, filename in _TEMPLATE_FILES:
        path = SAMPLES_DIR / filename
        spec = json.loads(path.read_text(encoding="utf-8"))
        out.append(
            {
                "id": tid,
                "label": label,
                "source_file": str(filename),
                "research_spec": spec,
            }
        )
    return to_jsonable(out)


def blank_research_spec() -> dict[str, Any]:
    """Smallest useful shell — no invented FIRST80 bindings or thresholds."""
    return {
        "schema_version": "research_spec_v0",
        "identity": {
            "name": "",
            "description": "",
            "tags": [],
        },
        "universe": "BBALL1",
        "population_binding": {
            "leagues": ["NBA"],
            "default_structural_slices": [],
            "selection": "all_matching",
            "p5_vs_p5_only": False,
            "locked_population_id": None,
        },
        "anchor": {
            "event": "OBSERVATION_TIME",
            "unresolved_parameters": [],
        },
        "information_regime": "POINT_IN_TIME",
        "information_set": "O_t",
        "state_filters": {"op": "AND", "args": []},
        "path_conditions": [],
        "terminal_conditions": [{"kind": "UNRESTRICTED"}],
        "measurement_requests": [],
        "sample_binding": {},
        "definition_versions": {},
        "dataset_versions": {},
        "execution_interpretation": "OBSERVABLE_PATH_ONLY",
        "caveats": [
            "MEASUREMENT ≠ EDGE",
            "CANDLE PATH ≠ FILL",
        ],
        "economic_layer": None,
        "portfolio_layer": None,
        "persistence": {"kind": "ephemeral"},
    }


__all__ = [
    "blank_research_spec",
    "list_templates",
    "load_sample",
    "preview_research_object",
    "validate_for_api",
]
