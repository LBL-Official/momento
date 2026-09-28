"""Frozen Confirm & Run question for the Jump A full-path stress.

Same priced ops as the desk Q4 CROSS 65 / REACH 85 / REACH 40 example.
No new indicators.
"""

from __future__ import annotations

from typing import Any

STRATEGY_NAME = "ITI Stress Q4 CROSS 65 REACH 85 40"

STRESS_QUESTION: dict[str, Any] = {
    "accept_limitations": False,
    "entry_conditions": [
        {
            "clock": None,
            "event_definition": "TRADABLE_CLOSE_CROSS",
            "id": "entry_iti_stress",
            "nth": None,
            "operation": "CROSS",
            "ordinal": "FIRST_TOUCH",
            "period": "Q4",
            "price_e4": 6500,
            "price_field": "yes_bid_close",
        }
    ],
    "path_conditions": [
        {
            "id": "win_iti_stress",
            "op": "REACH",
            "outcome": "win",
            "price_e4": 8500,
            "sequential": False,
        },
        {
            "id": "loss_iti_stress",
            "op": "REACH",
            "outcome": "loss",
            "price_e4": 4000,
            "sequential": False,
        },
    ],
    "requested_dimensions": ["HOLD_TO_SETTLEMENT"],
    "terminal": "BOTH",
    "universe": {
        "date_from": "2025-10-10",
        "date_to": "2025-10-31",
        "game_data": ["pbp"],
        "leagues": ["NBA"],
        "market_data": ["candles"],
        "markets": ["kalshi"],
        "seasons": ["2025-2026"],
        "sports": ["NBA"],
    },
}
