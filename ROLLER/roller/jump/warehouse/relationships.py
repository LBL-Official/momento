"""Canonical GameMarketLink relationships only. Name-similar is CANDIDATE."""

from __future__ import annotations

from typing import Any

from roller.jump.versions import LIVE_EXECUTION
from roller.jump.warehouse.catalog import load_catalog, save_catalog
from roller.jump.warehouse.registry import require_available

DECLARED_EDGES = (
    {
        "id": "games-markets",
        "from_table": "games",
        "from_column": "internal_game_id",
        "to_table": "markets",
        "to_column": "internal_game_id",
        "cardinality": "1:N",
        "status": "DECLARED",
        "origin": "CANONICAL_MAPPING",
    },
    {
        "id": "games-links",
        "from_table": "games",
        "from_column": "internal_game_id",
        "to_table": "game_market_links",
        "to_column": "internal_game_id",
        "cardinality": "1:N",
        "status": "DECLARED",
        "origin": "CANONICAL_MAPPING",
    },
    {
        "id": "markets-links",
        "from_table": "markets",
        "from_column": "market_id",
        "to_table": "game_market_links",
        "to_column": "market_id",
        "cardinality": "1:1",
        "status": "DECLARED",
        "origin": "CANONICAL_MAPPING",
    },
    {
        "id": "markets-observations-id",
        "from_table": "markets",
        "from_column": "market_id",
        "to_table": "observations",
        "to_column": "market_id",
        "cardinality": "1:N",
        "status": "DECLARED",
        "origin": "CANONICAL_MAPPING",
    },
    {
        "id": "markets-observations-ticker",
        "from_table": "markets",
        "from_column": "ticker",
        "to_table": "observations",
        "to_column": "ticker",
        "cardinality": "1:N",
        "status": "DECLARED",
        "origin": "CANONICAL_MAPPING",
    },
    {
        "id": "games-observations",
        "from_table": "games",
        "from_column": "internal_game_id",
        "to_table": "observations",
        "to_column": "internal_game_id",
        "cardinality": "1:N",
        "status": "DECLARED",
        "origin": "CANONICAL_MAPPING",
    },
    {
        "id": "games-pbp",
        "from_table": "games",
        "from_column": "internal_game_id",
        "to_table": "pbp",
        "to_column": "internal_game_id",
        "cardinality": "1:N",
        "status": "DECLARED",
        "origin": "CANONICAL_MAPPING",
    },
    {
        "id": "markets-settlements",
        "from_table": "markets",
        "from_column": "market_id",
        "to_table": "settlements",
        "to_column": "market_id",
        "cardinality": "1:1",
        "status": "DECLARED",
        "origin": "CANONICAL_MAPPING",
    },
    {
        "id": "games-settlements",
        "from_table": "games",
        "from_column": "internal_game_id",
        "to_table": "settlements",
        "to_column": "internal_game_id",
        "cardinality": "1:N",
        "status": "DECLARED",
        "origin": "CANONICAL_MAPPING",
    },
)

CANDIDATE_EDGES = (
    {
        "id": "season-name-similar",
        "from_table": "games",
        "from_column": "season",
        "to_table": "markets",
        "to_column": "season",
        "cardinality": "UNKNOWN",
        "status": "CANDIDATE",
        "origin": "NAME_SIMILAR",
        "trusted": False,
        "note": "Name-similar only. Not a trusted join.",
    },
)

DEFAULT_LAYOUT = {
    "games": {"x": 40, "y": 36},
    "markets": {"x": 280, "y": 36},
    "game_market_links": {"x": 160, "y": 170},
    "observations": {"x": 40, "y": 300},
    "settlements": {"x": 280, "y": 300},
    "pbp": {"x": 480, "y": 170},
}


def relationship_graph(warehouse_id: str, *, root=None) -> dict[str, Any]:
    rec = require_available(warehouse_id, root=root)
    catalog = load_catalog(root=root)
    layout = catalog.get("relationship_layouts", {}).get(rec.id) or dict(DEFAULT_LAYOUT)
    return {
        "warehouse_id": rec.id,
        "nodes": [
            {"id": name, "label": name, **layout.get(name, DEFAULT_LAYOUT[name])}
            for name in DEFAULT_LAYOUT
        ],
        "edges": [dict(edge, trusted=True) for edge in DECLARED_EDGES],
        "candidates": [dict(edge) for edge in CANDIDATE_EDGES],
        "note": "Trusted joins are DECLARED / CANONICAL_MAPPING only.",
        "live_execution": LIVE_EXECUTION,
    }


def save_layout(warehouse_id: str, layout: dict[str, Any], *, root=None) -> dict[str, Any]:
    rec = require_available(warehouse_id, root=root)
    catalog = load_catalog(root=root)
    cleaned: dict[str, Any] = {}
    for name, pos in (layout or {}).items():
        if name not in DEFAULT_LAYOUT or not isinstance(pos, dict):
            continue
        try:
            cleaned[name] = {"x": int(pos.get("x", DEFAULT_LAYOUT[name]["x"])), "y": int(pos.get("y", DEFAULT_LAYOUT[name]["y"]))}
        except (TypeError, ValueError):
            cleaned[name] = dict(DEFAULT_LAYOUT[name])
    catalog.setdefault("relationship_layouts", {})[rec.id] = cleaned or dict(DEFAULT_LAYOUT)
    save_catalog(catalog, root=root)
    return relationship_graph(warehouse_id, root=root)
