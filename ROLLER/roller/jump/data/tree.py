"""Capability tree for the Jump data explorer. Built from context, not React constants."""

from __future__ import annotations

from typing import Any

from roller.jump.data.models import UNAVAILABLE


def _node(node_id: str, label: str, owner: str, availability: str, payload: Any = None, children: list | None = None) -> dict[str, Any]:
    return {
        "id": node_id,
        "label": label,
        "owner": owner,
        "availability": availability or UNAVAILABLE,
        "payload": payload,
        "children": children or [],
    }


def from_context(context: dict[str, Any]) -> dict[str, Any]:
    austin = context.get("Austin") or {}
    choosin = context.get("Choosin") or {}
    ballhog = context.get("Ballhog") or {}
    tk = context.get("TKUltra") or {}
    positman = context.get("Positman") or {}
    drevo = context.get("Drevo") or {}
    game = context.get("game_state") or {}
    market = context.get("market_state") or {}
    pbp = context.get("pbp") or {}
    vital = context.get("Vital") or {}
    ident = context.get("identity") or {}
    return {
        "root": "GAME",
        "identity": ident,
        "as_of": context.get("as_of"),
        "nodes": [
            _node("identity", "Identity", "roller", game.get("availability"), ident),
            _node(
                "market",
                "Market",
                "roller",
                market.get("availability"),
                market,
                children=[_node("roller.observations", "ROLLER observations", "roller", market.get("availability"), market)],
            ),
            _node(
                "pbp",
                "PBP",
                "roller",
                pbp.get("availability"),
                children=[_node("roller.pbp", "ROLLER", "roller", pbp.get("availability"), pbp)],
            ),
            _node(
                "first80",
                "FIRST80",
                "choosin_texas",
                choosin.get("availability"),
                children=[_node("choosin", "Choosin Texas", "choosin_texas", choosin.get("availability"), choosin)],
            ),
            _node(
                "alpha",
                "Conditional Alpha",
                "austin",
                austin.get("availability"),
                children=[_node("austin", "Austin", "austin", austin.get("availability"), austin)],
            ),
            _node(
                "hedge",
                "Hedging Analysis",
                "ballhog",
                ballhog.get("availability"),
                children=[_node("ballhog", "Ballhog", "ballhog", ballhog.get("availability"), ballhog)],
            ),
            _node(
                "rv",
                "Relative Value",
                "tk_ultra",
                tk.get("availability"),
                children=[_node("tk_ultra", "TK Ultra", "tk_ultra", tk.get("availability"), tk)],
            ),
            _node(
                "position",
                "Position Management",
                "position_management",
                positman.get("availability"),
                children=[_node("positman", "Positman", "position_management", positman.get("availability"), positman)],
            ),
            _node(
                "risk",
                "Dynamic Risk",
                "dre",
                drevo.get("availability"),
                children=[_node("drevo", "Drevo", "dre", drevo.get("availability"), drevo)],
            ),
            _node(
                "execution",
                "Execution",
                "vital",
                vital.get("availability"),
                children=[_node("vital", "Vital", "vital", vital.get("availability"))],
            ),
        ],
    }
