"""Canonical 19-system bracket edges. Architecture freeze only."""

from __future__ import annotations

from collections import defaultdict
from typing import Iterable

# Tournament edges only. Infrastructure is INFRA_EDGES.
BRACKET_EDGES: tuple[tuple[str, str], ...] = (
    ("database", "data_modeling"),
    ("data_analysis", "data_modeling"),
    ("fair_odds_modeling", "game_modeling"),
    ("in_house_odds_modeling", "game_modeling"),
    ("data_modeling", "signal_generation"),
    ("game_modeling", "signal_generation"),
    ("trade_breakdown", "dynamic_risk_engine"),
    ("position_stratification", "dynamic_risk_engine"),
    ("hedging_analysis", "position_management"),
    ("relative_value_hedging", "position_management"),
    ("dynamic_risk_engine", "algorithmic_execution"),
    ("position_management", "algorithmic_execution"),
    ("signal_generation", "momento_systems"),
    ("algorithmic_execution", "momento_systems"),
)

# Data Ingestion feeds Database. Maintenance, Trade Reconciliation, and
# System Orchestration observe; they are not producer edges.
INFRA_EDGES: tuple[tuple[str, str], ...] = (("data_ingestion", "database"),)

OWNERSHIP_EDGES: tuple[tuple[str, str], ...] = BRACKET_EDGES + INFRA_EDGES


class BracketError(ValueError):
    """Illegal bracket relationship."""


def adjacency(edges: Iterable[tuple[str, str]]) -> dict[str, list[str]]:
    graph: dict[str, list[str]] = defaultdict(list)
    for src, dst in edges:
        graph[src].append(dst)
    return dict(graph)


def has_cycle(nodes: Iterable[str], edges: Iterable[tuple[str, str]]) -> bool:
    graph = adjacency(edges)
    visiting: set[str] = set()
    seen: set[str] = set()

    def walk(node: str) -> bool:
        if node in visiting:
            return True
        if node in seen:
            return False
        visiting.add(node)
        for nxt in graph.get(node, ()):
            if walk(nxt):
                return True
        visiting.remove(node)
        seen.add(node)
        return False

    return any(walk(node) for node in nodes)


def assert_acyclic(nodes: Iterable[str], edges: Iterable[tuple[str, str]] = OWNERSHIP_EDGES) -> None:
    node_list = list(nodes)
    if has_cycle(node_list, edges):
        raise BracketError("illegal cycle in Momento system graph")
