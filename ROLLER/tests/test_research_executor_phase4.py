"""Phase 4: empirical research executor orchestrator."""

from __future__ import annotations

import ast
import copy
from pathlib import Path

import pytest

from roller.dashboard_adapter import research_executor as rex
from roller.dashboard_adapter.bindings import (
    BINDING_ROLLER_FIRST80,
    BINDING_WAREHOUSE_FROZEN_V1,
    warehouse_barrier_trades_available,
    warehouse_first80_available,
)
from roller.dashboard_adapter.research_executor import execute_research_object
from roller.dashboard_adapter.research_object import compute_research_object_id, load_sample
from roller.dashboard_adapter.research_object_ops import validate_for_api
from roller.dashboard_adapter.serialize import to_jsonable


pytestmark = pytest.mark.skipif(
    not warehouse_first80_available() or not warehouse_barrier_trades_available(),
    reason="warehouse FIRST80 candidates.json or barrier trades.parquet missing",
)


def test_first80_warehouse_vertical_slice():
    spec = load_sample("first80_q3_path_terminal.json")
    v = validate_for_api(spec)
    assert v["status"] == "RUNNABLE"
    result = execute_research_object(spec)
    assert result["execution_status"] == "COMPLETE"
    assert result["research_object_id"] == compute_research_object_id(spec)
    binding = result["bindings"]["FIRST80"]
    assert binding["requested_definition_version"] == BINDING_WAREHOUSE_FROZEN_V1
    assert binding["actual_definition_version"] == BINDING_WAREHOUSE_FROZEN_V1
    assert binding["status"] == "COMPLETE"
    n = result["population"]["count"]
    assert n == result["summary"]["population_n"]
    assert n > 0
    # Artifact scale Q3 ≈ 290 — derive, allow small tolerance only via exact filter
    assert n == 290, f"expected Q3 population from barrier artifact, got {n}"
    assert result["population"]["rows_truncated"] is True  # 290 > 200 cap
    assert len(result["population"]["rows"]) == 200
    names = {m["name"]: m for m in result["measurements"]}
    assert names["t40_rate"]["status"] == "COMPLETE"
    assert names["t40_rate"]["value"] is not None
    assert names["kalshi_yes_rate"]["status"] == "COMPLETE"
    assert names["kalshi_yes_rate"]["value"] is not None
    assert "MEASUREMENT ≠ EDGE" in result["caveats"]
    arts = result["provenance"]["source_artifacts"]
    assert any("candidates.json" in a for a in arts)
    assert any("trades.parquet" in a for a in arts)
    part = result["empirical_partition"]
    assert part["status"] == "COMPLETE"
    assert part["n_population"] == 290
    cell_n = sum(int(c["n"]) for c in part["cells"])
    assert cell_n + int(part["n_missing"]) == 290
    assert {c["key"] for c in part["cells"]} == {
        "T_AND_W",
        "T_AND_NOT_W",
        "NOT_T_AND_W",
        "NOT_T_AND_NOT_W",
    }


def test_no_warehouse_fallback_for_roller_binding(monkeypatch):
    spec = load_sample("first80_q3_path_terminal.json")
    spec = copy.deepcopy(spec)
    spec["definition_versions"]["FIRST80"] = BINDING_ROLLER_FIRST80

    calls: list[str] = []

    def boom() -> Path:
        calls.append("candidates")
        raise AssertionError("warehouse candidates must not be loaded for roller_4.1.0-R")

    monkeypatch.setattr(rex, "_candidates_path_hook", boom)
    result = execute_research_object(spec)
    assert calls == []
    binding = result["bindings"]["FIRST80"]
    assert binding["requested_definition_version"] == BINDING_ROLLER_FIRST80
    # Local first80_triggers typically absent → ABSENT, never warehouse COMPLETE
    assert binding.get("actual_definition_version") != BINDING_WAREHOUSE_FROZEN_V1
    assert result["execution_status"] in ("ABSENT", "COMPLETE")
    if result["execution_status"] == "COMPLETE":
        assert binding["actual_definition_version"] == BINDING_ROLLER_FIRST80
    else:
        assert binding["status"] == "ABSENT"
        assert any("warehouse" in c.lower() and "not" in c.lower() for c in result["caveats"]) or any(
            "fallback" in c.lower() for c in result["caveats"]
        )


def test_unresolved_does_not_load_candidates(monkeypatch):
    spec = load_sample("observation_large_move_unresolved.json")
    calls: list[str] = []

    def boom() -> Path:
        calls.append("candidates")
        raise AssertionError("must not load candidates for UNRESOLVED")

    monkeypatch.setattr(rex, "_candidates_path_hook", boom)
    result = execute_research_object(spec)
    assert result["execution_status"] == "UNRESOLVED"
    assert calls == []
    assert result["population"]["count"] == 0
    assert result["population"]["rows"] == []


def test_fundamental_no_fake_first80_population():
    spec = load_sample("fundamental_basis_measurement.json")
    v = validate_for_api(spec)
    assert v["status"] == "RUNNABLE"
    assert "FIRST80" not in (spec.get("definition_versions") or {})
    result = execute_research_object(spec)
    assert result["execution_status"] == "PARTIAL"
    assert result["population"]["count"] == 0
    assert result["population"]["rows"] == []
    for m in result["measurements"]:
        assert m["status"] in ("ABSENT", "NOT_CONSTRUCTIBLE")
        assert m["value"] is None


def test_null_preservation_serializer():
    import math

    payload = {"a": None, "b": float("nan"), "c": math.nan, "d": 0}
    out = to_jsonable(payload)
    assert out["a"] is None
    assert out["b"] is None
    assert out["c"] is None
    assert out["d"] == 0  # real zero preserved; missing is null


def test_executor_scope_guard_imports():
    src = (
        Path(__file__).resolve().parents[1]
        / "roller"
        / "dashboard_adapter"
        / "research_executor.py"
    )
    tree = ast.parse(src.read_text(encoding="utf-8"))
    imports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imports.append(node.module or "")
    joined = " ".join(imports)
    # Must not pull trading / portfolio / fee engines
    for bad in (
        "portfolio",
        "fee_models",
        "openai",
        "anthropic",
        "nba_80_40_execution_audit",
        "first80_quarter_barrier_survival",
    ):
        assert bad not in joined, f"forbidden import {bad}"


def test_api_smoke_execute():
    pytest.importorskip("fastapi")
    import sys

    from fastapi.testclient import TestClient

    scripts = Path(__file__).resolve().parents[1] / "scripts"
    sys.path.insert(0, str(scripts))
    import terminal_api  # noqa: E402

    # Ensure execute route exists (may need Phase 4 API wiring)
    assert hasattr(terminal_api, "app")
    client = TestClient(terminal_api.app)

    first = load_sample("first80_q3_path_terminal.json")
    r = client.post("/research-objects/execute", json={"research_spec": first})
    assert r.status_code == 200
    body = r.json()
    assert body["execution_status"] == "COMPLETE"
    assert body["population"]["count"] == 290

    large = load_sample("observation_large_move_unresolved.json")
    u = client.post("/research-objects/execute", json={"research_spec": large})
    assert u.status_code == 200
    assert u.json()["execution_status"] == "UNRESOLVED"
