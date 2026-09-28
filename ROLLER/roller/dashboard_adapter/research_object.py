"""Structural Research Object validation and identity hashing.

No research mathematics. Does not call scan/EV/fee/portfolio engines.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# Prefer stdlib jsonschema if unavailable — use lightweight required-field checks
# plus optional jsonschema when installed. Phase 0 must not add a hard dependency
# beyond what ROLLER already declares; jsonschema may be absent.
try:
    import jsonschema  # type: ignore

    _HAS_JSONSCHEMA = True
except ImportError:  # pragma: no cover
    jsonschema = None
    _HAS_JSONSCHEMA = False

REPO_DOCS = Path(__file__).resolve().parents[3] / "docs" / "research" / "roller_dashboard"
SCHEMA_PATH = REPO_DOCS / "research_spec.schema.json"
SAMPLES_DIR = REPO_DOCS / "samples"

_REQUIRED = (
    "schema_version",
    "universe",
    "anchor",
    "information_regime",
    "execution_interpretation",
    "definition_versions",
    "caveats",
)


@dataclass
class ResearchObjectValidation:
    ok: bool
    errors: list[str] = field(default_factory=list)
    runnable: bool = False
    research_object_id: str | None = None
    unresolved: list[str] = field(default_factory=list)


def load_schema() -> dict[str, Any]:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def _canonical_bytes(spec: dict[str, Any]) -> bytes:
    """Deterministic JSON for hashing. Drops optional precomputed id."""
    payload = dict(spec)
    identity = dict(payload.get("identity") or {})
    identity.pop("research_object_id", None)
    if identity:
        payload["identity"] = identity
    elif "identity" in payload:
        payload["identity"] = identity
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode(
        "utf-8"
    )


def compute_research_object_id(spec: dict[str, Any]) -> str:
    digest = hashlib.sha256(_canonical_bytes(spec)).hexdigest()
    return f"RSH_{digest[:32]}"


def _collect_unresolved(spec: dict[str, Any]) -> list[str]:
    out: list[str] = []
    anchor = spec.get("anchor") or {}
    for item in anchor.get("unresolved_parameters") or []:
        out.append(f"anchor.{item}")
    if anchor.get("direction") == "UNRESOLVED":
        out.append("anchor.direction")
    for i, cond in enumerate(spec.get("path_conditions") or []):
        if cond.get("kind") == "UNRESOLVED" or cond.get("binding") == "UNRESOLVED":
            out.append(f"path_conditions[{i}]")
    for i, cond in enumerate(spec.get("terminal_conditions") or []):
        if cond.get("kind") == "UNRESOLVED":
            out.append(f"terminal_conditions[{i}]")
    for i, m in enumerate(spec.get("measurement_requests") or []):
        if m.get("binding") == "UNRESOLVED":
            out.append(f"measurement_requests[{i}]")
    if spec.get("execution_interpretation") == "UNRESOLVED":
        out.append("execution_interpretation")
    if spec.get("information_regime") == "UNRESOLVED":
        out.append("information_regime")

    # Calendar universe filters are schema-valid but not applied by Phase 0–6
    # population routes. Non-empty scope keeps the object STRUCTURAL / UNRESOLVED.
    pop = spec.get("population_binding") if isinstance(spec.get("population_binding"), dict) else {}
    if pop.get("seasons") or pop.get("season_months") or pop.get("season_weeks"):
        out.append("population_binding.calendar_scope")
    return out


def _lightweight_schema_check(spec: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if not isinstance(spec, dict):
        return ["spec must be an object"]
    for key in _REQUIRED:
        if key not in spec:
            errors.append(f"missing required field: {key}")
    if spec.get("schema_version") != "research_spec_v0":
        errors.append("schema_version must be research_spec_v0")
    caveats = spec.get("caveats")
    if not isinstance(caveats, list) or len(caveats) < 1:
        errors.append("caveats must be a non-empty array")
    anchor = spec.get("anchor")
    if not isinstance(anchor, dict) or "event" not in anchor:
        errors.append("anchor.event is required")
    if not isinstance(spec.get("definition_versions"), dict):
        errors.append("definition_versions must be an object")
    return errors


def validate_research_spec(spec: dict[str, Any]) -> ResearchObjectValidation:
    errors = _lightweight_schema_check(spec)
    if _HAS_JSONSCHEMA and not errors:
        try:
            jsonschema.validate(instance=spec, schema=load_schema())  # type: ignore[union-attr]
        except Exception as exc:  # noqa: BLE001 — surface validator message
            errors.append(str(exc))
    unresolved = _collect_unresolved(spec) if not errors else []
    rid = compute_research_object_id(spec) if not errors else None
    runnable = (not errors) and (len(unresolved) == 0)
    return ResearchObjectValidation(
        ok=not errors,
        errors=errors,
        runnable=runnable,
        research_object_id=rid,
        unresolved=unresolved,
    )


def is_runnable(spec: dict[str, Any]) -> bool:
    return validate_research_spec(spec).runnable


def load_sample(name: str) -> dict[str, Any]:
    path = SAMPLES_DIR / name
    return json.loads(path.read_text(encoding="utf-8"))
