"""Momento 19-system architecture freeze. Ownership map only."""

from __future__ import annotations

from pathlib import Path

import pytest

from roller.momento.bracket import (
    BRACKET_EDGES,
    INFRA_EDGES,
    OWNERSHIP_EDGES,
    assert_acyclic,
    has_cycle,
)
from roller.momento.registry import (
    CANONICAL_IDS,
    KNOWN_FRONTEND_PRODUCTS,
    LIVE_EXECUTION,
    REGISTRY_SCHEMA,
    REQUIRED_FIELDS,
    SYSTEM_COUNT,
    default_registry_path,
    load_registry,
    parse_yaml_subset,
)

REPO = Path(__file__).resolve().parents[2]


def test_live_execution_disabled_by_default():
    assert LIVE_EXECUTION is False
    registry = load_registry()
    assert registry.live_execution is False
    assert all(row.live_capability is False for row in registry.systems)


def test_registry_file_is_repo_ssot():
    path = default_registry_path()
    assert path == REPO / "momento" / "registry" / "systems.yaml"
    assert path.is_file()
    assert "docs/momento" != str(path)


def test_registry_count_and_unique_ids():
    registry = load_registry()
    assert len(registry) == SYSTEM_COUNT == 19
    ids = [row.id for row in registry.systems]
    assert len(ids) == len(set(ids))
    assert set(ids) == set(CANONICAL_IDS)


def test_required_fields_present():
    registry = load_registry()
    for row in registry.systems:
        for field in REQUIRED_FIELDS:
            assert getattr(row, field) is not None
        assert row.frontend_target.get("kind")
        assert row.frontend_target.get("url")
        assert row.backend_target.get("kind")
        assert row.frontend_url
        assert row.api_namespace


def test_schema_and_round_counts():
    registry = load_registry()
    assert registry.schema_version == REGISTRY_SCHEMA
    rounds = {}
    for row in registry.systems:
        rounds[row.bracket_round] = rounds.get(row.bracket_round, 0) + 1
    assert rounds == {
        "first": 8,
        "second": 4,
        "final_four": 2,
        "champion": 1,
        "infrastructure": 4,
    }


def test_bracket_edges_and_no_cycles():
    registry = load_registry()
    ids = [row.id for row in registry.systems]
    assert ("database", "data_modeling") in BRACKET_EDGES
    assert ("data_analysis", "data_modeling") in BRACKET_EDGES
    assert ("fair_odds_modeling", "game_modeling") in BRACKET_EDGES
    assert ("in_house_odds_modeling", "game_modeling") in BRACKET_EDGES
    assert ("data_modeling", "signal_generation") in BRACKET_EDGES
    assert ("game_modeling", "signal_generation") in BRACKET_EDGES
    assert ("trade_breakdown", "dynamic_risk_engine") in BRACKET_EDGES
    assert ("position_stratification", "dynamic_risk_engine") in BRACKET_EDGES
    assert ("hedging_analysis", "position_management") in BRACKET_EDGES
    assert ("relative_value_hedging", "position_management") in BRACKET_EDGES
    assert ("dynamic_risk_engine", "algorithmic_execution") in BRACKET_EDGES
    assert ("position_management", "algorithmic_execution") in BRACKET_EDGES
    assert ("signal_generation", "momento_systems") in BRACKET_EDGES
    assert ("algorithmic_execution", "momento_systems") in BRACKET_EDGES
    assert INFRA_EDGES == (("data_ingestion", "database"),)
    assert ("system_maintenance", "momento_systems") not in OWNERSHIP_EDGES
    assert ("trade_reconciliation", "database") not in OWNERSHIP_EDGES
    assert ("trade_reconciliation", "algorithmic_execution") not in OWNERSHIP_EDGES
    assert ("system_orchestration", "momento_systems") not in OWNERSHIP_EDGES
    assert has_cycle(ids, OWNERSHIP_EDGES) is False
    assert_acyclic(ids)
    assert has_cycle(["a", "b"], (("a", "b"), ("b", "a"))) is True
    with pytest.raises(Exception):
        assert_acyclic(["a", "b"], (("a", "b"), ("b", "a")))


def test_upstream_downstream_match_edges():
    by_id = load_registry().by_id()
    for src, dst in OWNERSHIP_EDGES:
        assert dst in by_id[src].downstream_systems
        assert src in by_id[dst].upstream_systems


def test_existing_product_frontend_targets():
    by_id = load_registry().by_id()
    assert by_id["database"].frontend_url == "http://127.0.0.1:5179"
    assert by_id["database"].frontend_product == "ROLLER"
    assert by_id["data_analysis"].frontend_url == "http://127.0.0.1:5179/?app=superasi"
    assert by_id["data_analysis"].frontend_product == "SuperASI"
    assert by_id["data_modeling"].frontend_url == "http://127.0.0.1:5179/?app=jump"
    assert by_id["data_modeling"].frontend_product == "Jump"
    assert by_id["trade_breakdown"].frontend_url == "http://127.0.0.1:5182#/"
    assert by_id["trade_breakdown"].frontend_product == "Choosin Texas"
    assert by_id["position_stratification"].frontend_url == "http://127.0.0.1:5182#/austin"
    assert by_id["position_stratification"].frontend_product == "Austin"
    assert by_id["dynamic_risk_engine"].frontend_url == "http://127.0.0.1:5191/"
    assert by_id["dynamic_risk_engine"].frontend_product == "Drevo"
    assert KNOWN_FRONTEND_PRODUCTS["database"][0] == "ROLLER"


def test_existing_product_backend_namespaces():
    by_id = load_registry().by_id()
    assert by_id["database"].api_namespace == "/warehouse-research"
    assert "/warehouse-research" in by_id["database"].backend_target["namespaces"]
    assert by_id["data_analysis"].api_namespace == "/superasi"
    assert by_id["data_modeling"].api_namespace == "/jump"
    assert by_id["trade_breakdown"].api_namespace == "/choosin-texas"
    assert by_id["position_stratification"].api_namespace == "/austin"
    assert by_id["dynamic_risk_engine"].api_namespace == "/dre"
    assert by_id["hedging_analysis"].api_namespace == "/ballhog"
    assert "/ballhog" in by_id["hedging_analysis"].backend_target["namespaces"]
    assert by_id["algorithmic_execution"].api_namespace == "/momento/systems/algorithmic_execution"
    assert by_id["system_maintenance"].backend_target["port"] == 8791
    assert by_id["system_maintenance"].api_namespace == "/systimo"
    assert by_id["system_maintenance"].frontend_product == "Systimo"
    assert by_id["system_maintenance"].frontend_url == "http://127.0.0.1:5193/"
    assert "ROLLER/roller/ls/" in by_id["system_maintenance"].implementation_paths
    assert "ROLLER/roller/systimo/" in by_id["system_maintenance"].implementation_paths


def test_algorithmic_execution_is_not_vital_or_mlb():
    row = load_registry().by_id()["algorithmic_execution"]
    assert row.status == "NOT_IMPLEMENTED"
    assert row.frontend_product == "Momento"
    assert row.frontend_target["kind"] == "momento_page"
    assert "5180" not in row.frontend_url
    assert "vital" not in row.frontend_url.lower()
    assert row.api_namespace != "/vital"
    assert "/vital" not in row.backend_target.get("namespaces", [])
    assert "ROLLER/roller/vital/" not in row.implementation_paths
    assert "crates/risk/" not in row.implementation_paths
    assert "apps/trading-engine/" not in row.implementation_paths
    assert "NO NBA SUBMISSION IMPLEMENTATION" in row.notes
    assert "momento-nba-001.service" in row.notes
    assert "NBA_SUBMISSION_NOT_IMPLEMENTED" in row.feature_flags
    assert row.live_capability is False


def test_bottom_infra_boxes_are_not_implemented_and_have_no_edges():
    by_id = load_registry().by_id()
    recon = by_id["trade_reconciliation"]
    orch = by_id["system_orchestration"]
    assert recon.status == "NOT_IMPLEMENTED"
    assert orch.status == "NOT_IMPLEMENTED"
    assert recon.upstream_systems == ()
    assert recon.downstream_systems == ()
    assert orch.upstream_systems == ()
    assert orch.downstream_systems == ()
    assert recon.live_capability is False
    assert orch.live_capability is False
    assert recon.frontend_target["kind"] == "momento_page"
    assert orch.frontend_target["kind"] == "momento_page"
    assert "/vital" not in recon.frontend_url.lower()
    assert "ROLLER/roller/vital/" not in recon.implementation_paths
    assert orch.id != "momento_systems"
    assert "Distinct from champion Momento Systems" in orch.notes
    assert "Not Vital" in recon.notes
    assert recon.output_contracts == ("PositionReconciliation",)


def test_austin_split_and_risk_collision_are_recorded():
    by_id = load_registry().by_id()
    assert by_id["position_stratification"].implementation_paths[0] == "ROLLER/roller/austin/"
    assert by_id["dynamic_risk_engine"].frontend_url == "http://127.0.0.1:5191/"
    assert by_id["hedging_analysis"].frontend_url == "http://127.0.0.1:5192/"
    assert by_id["hedging_analysis"].frontend_product == "Ballhog"
    assert by_id["hedging_analysis"].extra.get("visual_subtitle") == "Ballhog"
    assert by_id["relative_value_hedging"].frontend_url.endswith("#/tk-ultra")
    assert by_id["relative_value_hedging"].frontend_product == "TK Ultra"
    assert by_id["relative_value_hedging"].extra.get("visual_subtitle") == "TK Ultra"
    assert "crates/risk/" not in by_id["algorithmic_execution"].implementation_paths
    assert "crates/risk/" not in by_id["dynamic_risk_engine"].implementation_paths
    assert "PHASE_3_NOT_EXECUTION_POLICY" in by_id["dynamic_risk_engine"].feature_flags
    assert "research/dre/" in by_id["dynamic_risk_engine"].research_paths
    assert "research/dre/PORTFOLIO_OBJECTIVE_V1.md" in by_id["dynamic_risk_engine"].research_paths


def test_yaml_subset_parses_nested_lists():
    parsed = parse_yaml_subset(
        "schema_version: momento_systems_registry_v1\n"
        "live_execution: false\n"
        "items:\n"
        "  - alpha\n"
        "  - beta\n"
        "nested:\n"
        "  kind: hash_route\n"
        "  url: http://127.0.0.1:5182#/austin\n"
    )
    assert parsed["live_execution"] is False
    assert parsed["items"] == ["alpha", "beta"]
    assert parsed["nested"]["url"] == "http://127.0.0.1:5182#/austin"
