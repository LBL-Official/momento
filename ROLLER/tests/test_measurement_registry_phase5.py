"""Phase 5: measurement registry & execution routing."""

from __future__ import annotations

import ast
import copy
from pathlib import Path

import pytest

from roller.dashboard_adapter import research_executor as rex
from roller.dashboard_adapter.bindings import (
    BINDING_BARRIER_SURVIVAL_V1,
    BINDING_WAREHOUSE_FROZEN_V1,
    warehouse_barrier_trades_available,
    warehouse_first80_available,
)
from roller.dashboard_adapter.measurement_registry import (
    get_measurement_definition,
    list_measurements,
    list_population_bindings,
    research_capabilities,
    resolve_measurement_request,
)
from roller.dashboard_adapter.research_executor import execute_research_object
from roller.dashboard_adapter.research_object import load_sample
from roller.dashboard_adapter.serialize import to_jsonable


def test_registry_completeness():
    for m in list_measurements():
        assert m.get("name")
        assert m.get("status") in ("IMPLEMENTED", "REGISTERED_NOT_EXECUTABLE")
        assert m.get("definition_version")
        assert "population_requirements" in m
        assert "requires" in m
    pops = list_population_bindings()
    assert any(
        p["name"] == "FIRST80" and p["definition_version"] == BINDING_WAREHOUSE_FROZEN_V1
        for p in pops
    )


def test_known_first80_measurements_resolve_implemented():
    ctx = {
        "definition_family": "FIRST80",
        "available_fields": ["T40", "W", "expiration_result_yes", "ticker"],
    }
    t40 = resolve_measurement_request({"name": "t40_rate"}, population_context=ctx)
    assert t40["route_status"] == "IMPLEMENTED"
    assert t40["handler_key"] == "t40_rate"
    assert t40["definition_version"] == BINDING_BARRIER_SURVIVAL_V1

    yes = resolve_measurement_request({"name": "kalshi_yes_rate"}, population_context=ctx)
    assert yes["route_status"] == "IMPLEMENTED"
    assert yes["handler_key"] == "kalshi_yes_rate"
    assert yes["definition_version"] == BINDING_WAREHOUSE_FROZEN_V1


def test_unknown_measurement_unsupported():
    route = resolve_measurement_request({"name": "banana_rate"}, population_context={})
    assert route["route_status"] == "UNSUPPORTED"
    assert route["handler_key"] is None


@pytest.mark.skipif(
    not warehouse_first80_available() or not warehouse_barrier_trades_available(),
    reason="warehouse FIRST80 artifacts missing",
)
def test_banana_rate_does_not_abort_first80_execute():
    spec = copy.deepcopy(load_sample("first80_q3_path_terminal.json"))
    spec["measurement_requests"].append({"name": "banana_rate", "not_edge": True})
    result = execute_research_object(spec)
    assert result["execution_status"] == "COMPLETE"
    assert result["population"]["count"] == 290
    by_name = {m["name"]: m for m in result["measurements"]}
    assert by_name["t40_rate"]["status"] == "COMPLETE"
    assert by_name["kalshi_yes_rate"]["status"] == "COMPLETE"
    assert by_name["banana_rate"]["status"] == "UNSUPPORTED"
    assert by_name["banana_rate"]["value"] is None


def test_fundamental_does_not_load_warehouse(monkeypatch):
    calls: list[str] = []

    def boom():
        calls.append("candidates")
        raise AssertionError("must not load FIRST80 candidates for fundamental sample")

    monkeypatch.setattr(rex, "_candidates_path_hook", boom)
    spec = load_sample("fundamental_basis_measurement.json")
    result = execute_research_object(spec)
    assert calls == []
    assert result["execution_status"] == "PARTIAL"
    assert result["population"]["count"] == 0
    assert result["population"]["rows"] == []
    for m in result["measurements"]:
        assert m["status"] == "NOT_CONSTRUCTIBLE"
        assert m["value"] is None


@pytest.mark.skipif(
    not warehouse_first80_available() or not warehouse_barrier_trades_available(),
    reason="warehouse FIRST80 artifacts missing",
)
def test_first80_regression_population_and_values():
    spec = load_sample("first80_q3_path_terminal.json")
    result = execute_research_object(spec)
    assert result["execution_status"] == "COMPLETE"
    assert result["population"]["count"] == 290
    by_name = {m["name"]: m for m in result["measurements"]}
    assert by_name["t40_rate"]["status"] == "COMPLETE"
    assert by_name["kalshi_yes_rate"]["status"] == "COMPLETE"
    # Phase 4 locked empirical values
    assert abs(float(by_name["t40_rate"]["value"]) - 0.27241379310344827) < 1e-12
    assert abs(float(by_name["kalshi_yes_rate"]["value"]) - 0.8206896551724138) < 1e-12
    assert by_name["t40_rate"]["source"]["field"] == "T40"
    assert by_name["kalshi_yes_rate"]["source"]["field"] == "W"
    assert get_measurement_definition("t40_rate") is not None


def test_null_preservation():
    payload = {"value": None, "status": "NOT_CONSTRUCTIBLE"}
    out = to_jsonable(payload)
    assert out["value"] is None
    assert out["status"] == "NOT_CONSTRUCTIBLE"


def test_api_capabilities_endpoint():
    pytest.importorskip("fastapi")
    import sys

    from fastapi.testclient import TestClient

    scripts = Path(__file__).resolve().parents[1] / "scripts"
    sys.path.insert(0, str(scripts))
    import terminal_api  # noqa: E402

    client = TestClient(terminal_api.app)
    health = client.get("/health")
    assert health.status_code == 200
    assert health.json()["phase"] == 6
    assert "measurement_registry" in health.json()["capabilities"]

    caps = client.get("/research-capabilities")
    assert caps.status_code == 200
    body = caps.json()
    assert body["phase"] == 6
    names = {m["name"] for m in body["measurements"]}
    assert "t40_rate" in names
    assert "kalshi_yes_rate" in names
    impl = [m for m in body["measurements"] if m["status"] == "IMPLEMENTED"]
    assert {m["name"] for m in impl} == {"t40_rate", "kalshi_yes_rate"}
    pops = { (p["name"], p["definition_version"]) for p in body["population_bindings"] }
    assert ("NCAAB_FIRST80_P5", "p5_half_barrier_survival_v1") in pops

    # Must not claim future concepts as IMPLEMENTED
    for m in body["measurements"]:
        if m["name"] in ("fundamental", "market_fundamental_basis", "residual"):
            assert m["status"] != "IMPLEMENTED"


def test_registry_import_guard():
    src = (
        Path(__file__).resolve().parents[1]
        / "roller"
        / "dashboard_adapter"
        / "measurement_registry.py"
    )
    tree = ast.parse(src.read_text(encoding="utf-8"))
    imports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imports.append(node.module or "")
    joined = " ".join(imports)
    for bad in ("portfolio", "fee_models", "openai", "frontend", "explorer", "object_inspector"):
        assert bad not in joined


def test_research_capabilities_helper():
    caps = research_capabilities()
    assert caps["phase"] == 6
    assert caps["population_bindings"]
    assert caps["measurements"]
