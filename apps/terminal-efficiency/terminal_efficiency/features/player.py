"""Player features. V1: UNAVAILABLE. Do not invent historical availability."""

from __future__ import annotations

PLAYER_V1_STATUS = "UNAVAILABLE"


def player_feature_row() -> dict:
    return {
        "player_availability": None,
        "player_availability_status": PLAYER_V1_STATUS,
        "data_gap": "GAP-001 — no verified point-in-time injury/lineup feed",
    }
