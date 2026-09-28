"""Phase 6: authoritative NCAAB_FIRST80_P5 population expansion."""

from __future__ import annotations

import ast
import copy
from pathlib import Path

import pytest

from roller.dashboard_adapter import research_executor as rex
from roller.dashboard_adapter.bindings import (
    BINDING_NCAAB_FIRST80_P5,
    NCAAB_FIRST80_P5_EXPECTED_N,
    warehouse_barrier_trades_available,
    warehouse_first80_available,
    warehouse_ncaab_first80_p5_available,
)
from roller.dashboard_adapter.measurement_registry import (
    list_population_bindings,
    research_capabilities,
    resolve_measurement_request,
)
from roller.dashboard_adapter.research_executor import execute_research_object
from roller.dashboard_adapter.research_object import compute_research_object_id, load_sample
from roller.dashboard_adapter.research_object_ops import validate_for_api


pytestmark_ncaab = pytest.mark.skipif(
    not warehouse_ncaab_first80_p5_available(),
    reason="NCAAB P5 trades.parquet missing",
)

pytestmark_nba = pytest.mark.skipif(
    not warehouse_first80_available() or not warehouse_barrier_trades_available(),
    reason="NBA warehouse FIRST80 artifacts missing",
)


@pytestmark_ncaab
def test_a_ncaab_p5_real_population():
    spec = load_sample("ncaab_first80_p5_path_terminal.json")
    v = validate_for_api(spec)
    assert v["status"] == "RUNNABLE"
    result = execute_research_object(spec)
    assert result["execution_status"] == "COMPLETE"
    binding = result["bindings"]["NCAAB_FIRST80_P5"]
    assert binding["requested_definition_version"] == BINDING_NCAAB_FIRST80_P5
    assert binding["actual_definition_version"] == BINDING_NCAAB_FIRST80_P5
    assert binding["status"] == "COMPLETE"
    assert binding.get("fallback") is False
    assert result["population"]["count"] == NCAAB_FIRST80_P5_EXPECTED_N
    assert result["summary"]["population_n"] == NCAAB_FIRST80_P5_EXPECTED_N
    assert result["provenance"].get("fallback") is False
    assert "first80_p5_half_barrier_survival" in str(result["provenance"]["membership_authority"])
    names = {m["name"]: m for m in result["measurements"]}
    assert names["t40_rate"]["status"] == "COMPLETE"
    assert names["kalshi_yes_rate"]["status"] == "COMPLETE"
    # Producer lock: EXPECTED_T40=188, EXPECTED_W=601
    assert names["t40_rate"]["detail"]["count_true"] == 188
    assert names["kalshi_yes_rate"]["detail"]["count_true"] == 601
    assert abs(names["t40_rate"]["value"] - (188 / 721)) < 1e-12
    assert abs(names["kalshi_yes_rate"]["value"] - (601 / 721)) < 1e-12
    rows = result["population"]["rows"]
    assert rows
    assert rows[0].get("ticker") or rows[0].get("event_id")
    part = result["empirical_partition"]
    assert part["status"] == "COMPLETE"
    assert part["n_population"] == NCAAB_FIRST80_P5_EXPECTED_N
    cell_n = sum(int(c["n"]) for c in part["cells"])
    assert cell_n + int(part["n_missing"]) == NCAAB_FIRST80_P5_EXPECTED_N


@pytestmark_nba
def test_b_first80_q3_regression_lock():
    spec = load_sample("first80_q3_path_terminal.json")
    result = execute_research_object(spec)
    assert result["execution_status"] == "COMPLETE"
    assert result["population"]["count"] == 290
    names = {m["name"]: m for m in result["measurements"]}
    assert names["t40_rate"]["status"] == "COMPLETE"
    assert names["kalshi_yes_rate"]["status"] == "COMPLETE"
    t40 = names["t40_rate"]["value"]
    yes = names["kalshi_yes_rate"]["value"]
    assert t40 is not None and yes is not None
    # Locked empirical rates from Phase 4/5
    assert abs(t40 - 0.27241379310344827) < 1e-12
    assert abs(yes - 0.8206896551724138) < 1e-12
    assert "FIRST80" in result["bindings"]
    assert "NCAAB_FIRST80_P5" not in result["bindings"]


@pytestmark_ncaab
def test_c_wrong_version_absent_no_nba_fallback(monkeypatch):
    spec = copy.deepcopy(load_sample("ncaab_first80_p5_path_terminal.json"))
    spec["definition_versions"]["NCAAB_FIRST80_P5"] = "not_a_real_version"
    nba_loads: list[str] = []

    def boom_nba() -> Path:
        nba_loads.append("candidates")
        raise AssertionError("must not load NBA candidates for bad NCAAB binding")

    monkeypatch.setattr(rex, "_candidates_path_hook", boom_nba)
    result = execute_research_object(spec)
    assert nba_loads == []
    assert result["execution_status"] == "ABSENT"
    binding = result["bindings"]["NCAAB_FIRST80_P5"]
    assert binding["status"] == "ABSENT"
    assert binding.get("fallback") is False
    assert result["population"]["count"] == 0
    assert not any("KXNBAGAME" in str(r) for r in result["population"]["rows"])


@pytestmark_ncaab
def test_d_unresolved_does_not_load_ncaab_parquet(monkeypatch):
    spec = load_sample("observation_large_move_unresolved.json")
    calls: list[str] = []

    def boom() -> Path:
        calls.append("ncaab")
        raise AssertionError("must not load NCAAB parquet for UNRESOLVED")

    monkeypatch.setattr(rex, "_ncaab_p5_path_hook", boom)
    result = execute_research_object(spec)
    assert result["execution_status"] == "UNRESOLVED"
    assert calls == []
    assert result["population"]["count"] == 0


@pytestmark_ncaab
def test_e_research_context_isolation():
    """Explorer researchContext must not change fingerprint / population selection."""
    spec = load_sample("ncaab_first80_p5_path_terminal.json")
    rid = compute_research_object_id(spec)
    result_a = execute_research_object(spec)
    result_b = execute_research_object(copy.deepcopy(spec))
    assert result_a["research_object_id"] == rid
    assert result_b["research_object_id"] == rid
    assert result_a["population"]["count"] == result_b["population"]["count"] == 721
    assert result_a["bindings"]["NCAAB_FIRST80_P5"]["actual_definition_version"] == (
        result_b["bindings"]["NCAAB_FIRST80_P5"]["actual_definition_version"]
    )


def test_f_registry_lists_ncaab_implemented():
    caps = research_capabilities()
    assert caps["phase"] == 6
    pops = list_population_bindings()
    assert any(
        p["name"] == "NCAAB_FIRST80_P5"
        and p["definition_version"] == BINDING_NCAAB_FIRST80_P5
        and p["status"] == "IMPLEMENTED"
        for p in pops
    )
    ctx = {
        "definition_family": "NCAAB_FIRST80_P5",
        "available_fields": ["T40", "W", "ticker"],
    }
    t40 = resolve_measurement_request({"name": "t40_rate"}, population_context=ctx)
    assert t40["route_status"] == "IMPLEMENTED"


@pytestmark_ncaab
def test_g_unsupported_measurement_does_not_abort():
    spec = copy.deepcopy(load_sample("ncaab_first80_p5_path_terminal.json"))
    spec["measurement_requests"].append({"name": "banana_rate", "not_edge": True})
    result = execute_research_object(spec)
    assert result["execution_status"] == "COMPLETE"
    assert result["population"]["count"] == 721
    by_name = {m["name"]: m for m in result["measurements"]}
    assert by_name["t40_rate"]["status"] == "COMPLETE"
    assert by_name["banana_rate"]["status"] == "UNSUPPORTED"
    assert by_name["banana_rate"]["value"] is None


def test_h_structural_guard_no_generic_engine():
    src = Path(rex.__file__).read_text(encoding="utf-8")
    tree = ast.parse(src)
    fn_names = {
        n.name
        for n in ast.walk(tree)
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    assert "_execute_warehouse_first80" in fn_names
    assert "_execute_ncaab_first80_p5" in fn_names
    forbidden = {
        "discover_populations",
        "auto_route_parquet",
        "generic_population_execute",
        "scan_candles_for_population",
    }
    assert not (forbidden & fn_names)
    assert "reconstruct_p5" not in src.lower()
    assert "load_frozen_p5_first80" not in src


def test_i_membership_authority_no_p5_rebuild():
    src = Path(rex.__file__).read_text(encoding="utf-8")
    assert "load_frozen_p5_first80" not in src
    assert "ncaab_pbp_espn_ingest" not in src
    assert "P5_CODES" not in src
    assert "Membership = artifact rows as-is" in src or "Membership authority" in src


@pytestmark_ncaab
def test_wrong_half_slice_only_filters_not_fallback():
    spec = copy.deepcopy(load_sample("ncaab_first80_p5_path_terminal.json"))
    spec["population_binding"]["default_structural_slices"] = ["H1_1"]
    result = execute_research_object(spec)
    assert result["execution_status"] == "COMPLETE"
    assert result["population"]["count"] == 217  # producer bucket count
    assert result["bindings"]["NCAAB_FIRST80_P5"]["status"] == "COMPLETE"
    assert "FIRST80" not in result["bindings"]
