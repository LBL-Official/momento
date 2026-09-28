"""Phase 2: Research Object validate / preview / templates."""

from __future__ import annotations

import json

import pytest

from roller.dashboard_adapter.research_object import compute_research_object_id, load_sample
from roller.dashboard_adapter.research_object_ops import (
    list_templates,
    preview_research_object,
    validate_for_api,
)


def test_first80_template_runnable():
    spec = load_sample("first80_q3_path_terminal.json")
    result = validate_for_api(spec)
    assert result["valid"] is True
    assert result["runnable"] is True
    assert result["status"] == "RUNNABLE"
    assert result["unresolved"] == []
    assert result["research_object_id"] == compute_research_object_id(spec)
    assert result["research_object_id"] == compute_research_object_id(spec)
    assert spec["definition_versions"]["FIRST80"] == "warehouse_frozen_v1"
    assert spec["schema_version"] == "research_spec_v0"


def test_large_down_move_unresolved_no_invented_magnitude():
    spec = load_sample("observation_large_move_unresolved.json")
    result = validate_for_api(spec)
    assert result["valid"] is True
    assert result["runnable"] is False
    assert result["status"] == "UNRESOLVED"
    fields = {u["field"] for u in result["unresolved"]}
    assert "anchor.magnitude_e4" in fields
    assert spec["anchor"]["magnitude_e4"] is None
    # Must not invent a numeric magnitude during validation
    assert not any(
        isinstance(u.get("reason"), (int, float)) for u in result["unresolved"]
    )
    assert "PRICE_MOVE magnitude must be explicit" in [
        u["reason"] for u in result["unresolved"] if u["field"] == "anchor.magnitude_e4"
    ]


def test_fundamental_sample_runnable_without_first80():
    spec = load_sample("fundamental_basis_measurement.json")
    result = validate_for_api(spec)
    assert result["valid"] is True
    assert result["runnable"] is True
    assert result["status"] == "RUNNABLE"
    assert "FIRST80" not in (spec.get("definition_versions") or {})
    assert spec["anchor"]["event"] == "OBSERVATION_TIME"


def test_universal_contract_same_schema_version():
    templates = list_templates()
    assert {t["id"] for t in templates} == {
        "FIRST80_Q3",
        "NCAAB_FIRST80_P5",
        "LARGE_DOWN_MOVE_Q4",
        "BASIS_EXTREME_AT_OBSERVATION",
    }
    for t in templates:
        assert t["research_spec"]["schema_version"] == "research_spec_v0"
        # Same format — validate path works for all
        validate_for_api(t["research_spec"])


def test_preview_is_structural_only():
    spec = load_sample("first80_q3_path_terminal.json")
    preview = preview_research_object(spec)
    assert preview["status"] == "RUNNABLE"
    assert preview["universe"] == "BBALL1"
    assert preview["normalized_spec"]["schema_version"] == "research_spec_v0"
    assert "STRUCTURAL PREVIEW ONLY" in preview["note"]
    assert "observation_id" not in preview  # not empirical O_t


def test_invalid_spec_status():
    result = validate_for_api({"universe": "BBALL1"})
    assert result["valid"] is False
    assert result["runnable"] is False
    assert result["status"] == "INVALID"
    assert result["errors"]


def test_api_smoke_research_object_endpoints():
    pytest.importorskip("fastapi")
    import sys
    from pathlib import Path

    from fastapi.testclient import TestClient

    scripts = Path(__file__).resolve().parents[1] / "scripts"
    sys.path.insert(0, str(scripts))
    import terminal_api  # noqa: E402 — load as normal module for Pydantic

    client = TestClient(terminal_api.app)
    templates = client.get("/research-object-templates")
    assert templates.status_code == 200
    body = templates.json()
    assert len(body) == 4

    first = next(t for t in body if t["id"] == "FIRST80_Q3")
    v = client.post("/research-objects/validate", json={"research_spec": first["research_spec"]})
    assert v.status_code == 200
    assert v.json()["status"] == "RUNNABLE"

    ncaab = next(t for t in body if t["id"] == "NCAAB_FIRST80_P5")
    vn = client.post("/research-objects/validate", json={"research_spec": ncaab["research_spec"]})
    assert vn.status_code == 200
    assert vn.json()["status"] == "RUNNABLE"

    large = next(t for t in body if t["id"] == "LARGE_DOWN_MOVE_Q4")
    u = client.post("/research-objects/validate", json={"research_spec": large["research_spec"]})
    assert u.status_code == 200
    assert u.json()["status"] == "UNRESOLVED"

    p = client.post(
        "/research-objects/preview",
        json={"research_spec": first["research_spec"]},
    )
    assert p.status_code == 200
    assert p.json()["status"] == "RUNNABLE"
