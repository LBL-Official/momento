"""ROLLER Terminal dashboard adapter — Phase 0–5 contracts.

Import-only / validation / serialization / vocabulary compile / empirical orchestrate.
No scan, EV, fee, or portfolio mathematics inside the adapter itself.
FIRST80 is one Research Object binding — not this package's architecture.
"""

from __future__ import annotations

from roller.dashboard_adapter.explorer import ExplorerError, list_universe_games
from roller.dashboard_adapter.measurement_registry import (
    list_measurements,
    list_population_bindings,
    research_capabilities,
    resolve_measurement_request,
)
from roller.dashboard_adapter.object_inspector import ObjectInspectorError, build_object_payload
from roller.dashboard_adapter.research_executor import execute_research_object
from roller.dashboard_adapter.research_object import (
    ResearchObjectValidation,
    compute_research_object_id,
    is_runnable,
    load_schema,
    validate_research_spec,
)
from roller.dashboard_adapter.research_object_ops import (
    blank_research_spec,
    list_templates,
    preview_research_object,
    validate_for_api,
)
from roller.dashboard_adapter.vocabulary_compiler import (
    compile_research_text,
    load_vocabulary,
)

__all__ = [
    "ExplorerError",
    "ObjectInspectorError",
    "ResearchObjectValidation",
    "blank_research_spec",
    "build_object_payload",
    "compile_research_text",
    "compute_research_object_id",
    "execute_research_object",
    "is_runnable",
    "list_measurements",
    "list_population_bindings",
    "list_templates",
    "list_universe_games",
    "load_schema",
    "load_vocabulary",
    "preview_research_object",
    "research_capabilities",
    "resolve_measurement_request",
    "validate_for_api",
    "validate_research_spec",
]
