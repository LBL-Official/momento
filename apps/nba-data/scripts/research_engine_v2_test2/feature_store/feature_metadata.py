"""Feature metadata registry."""

from __future__ import annotations

METADATA: list[dict] = []


def register(**kwargs):
    METADATA.append(kwargs)
    return kwargs["feature_name"]


def family(name: str) -> list[str]:
    return [m["feature_name"] for m in METADATA if m["feature_family"] == name]


# Families registered in trade_state when features are materialized.
FAMILIES = {
    "game_state": "A",
    "possession_path": "B",
    "game_dynamics": "C_D_H",
    "market_state": "E",
    "market_path": "F_I",
    "coupling": "G",
}
