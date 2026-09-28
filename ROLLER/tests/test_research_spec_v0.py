"""Phase 0: research_spec validation — structural only, no math."""

from __future__ import annotations

import json
from pathlib import Path

from roller.dashboard_adapter.research_object import (
    SAMPLES_DIR,
    compute_research_object_id,
    is_runnable,
    validate_research_spec,
)

# ROLLER/tests/file.py → parents[2] = Momento repo root
MOMENTO = Path(__file__).resolve().parents[2]
SAMPLES = MOMENTO / "docs" / "research" / "roller_dashboard" / "samples"


def _load(name: str) -> dict:
    return json.loads((SAMPLES / name).read_text(encoding="utf-8"))


def test_samples_dir_matches_adapter():
    assert SAMPLES_DIR.resolve() == SAMPLES.resolve()


def test_first80_sample_runnable():
    spec = _load("first80_q3_path_terminal.json")
    result = validate_research_spec(spec)
    assert result.ok, result.errors
    assert result.runnable
    assert result.research_object_id and result.research_object_id.startswith("RSH_")
    assert "FIRST80" in spec["definition_versions"]
    assert spec["universe"] == "BBALL1"


def test_fundamental_sample_runnable_without_first80():
    spec = _load("fundamental_basis_measurement.json")
    result = validate_research_spec(spec)
    assert result.ok, result.errors
    assert result.runnable
    assert "FIRST80" not in spec["definition_versions"]
    assert any(m["name"] == "fundamental" for m in spec["measurement_requests"])


def test_unresolved_large_move_valid_but_not_runnable():
    spec = _load("observation_large_move_unresolved.json")
    result = validate_research_spec(spec)
    assert result.ok, result.errors
    assert not result.runnable
    assert not is_runnable(spec)
    assert any("magnitude" in u for u in result.unresolved)


def test_research_object_id_stable():
    spec = _load("first80_q3_path_terminal.json")
    a = compute_research_object_id(spec)
    b = compute_research_object_id(spec)
    assert a == b
    mutated = dict(spec)
    mutated["identity"] = dict(spec["identity"])
    mutated["identity"]["name"] = "OTHER"
    assert compute_research_object_id(mutated) != a


def test_missing_caveats_invalid():
    spec = _load("first80_q3_path_terminal.json")
    bad = dict(spec)
    bad["caveats"] = []
    result = validate_research_spec(bad)
    assert not result.ok


def test_calendar_scope_is_structural_unresolved():
    spec = _load("first80_q3_path_terminal.json")
    spec["population_binding"] = {
        **spec["population_binding"],
        "seasons": ["2025-2026"],
        "season_months": ["2025-11"],
    }
    result = validate_research_spec(spec)
    assert result.ok, result.errors
    assert "population_binding.calendar_scope" in result.unresolved
    assert not result.runnable
