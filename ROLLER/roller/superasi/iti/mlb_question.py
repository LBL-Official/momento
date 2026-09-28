"""MLB ITI source question. Not the NBA Q4 stress fixture.

Candle TRADABLE_YES_BID CROSS 65 / REACH 85 / REACH 40. No basketball period or clock.
Last-trade remains selectable on the desk. ITI cents are not a live 80/81 signal.
"""

from __future__ import annotations

import copy
from typing import Any

STRATEGY_NAME = "MLB CANDLE CROSS 65 REACH 85 40"

MLB_ITI_QUESTION: dict[str, Any] = {
    "accept_limitations": False,
    "entry_conditions": [
        {
            "clock": None,
            "event_definition": "TRADABLE_CLOSE_CROSS",
            "id": "entry_mlb_iti",
            "nth": None,
            "operation": "CROSS",
            "ordinal": "FIRST_TOUCH",
            "period": None,
            "price_e4": 6500,
            "price_field": "yes_bid_close",
        }
    ],
    "path_conditions": [
        {
            "id": "win_mlb_iti",
            "op": "REACH",
            "outcome": "win",
            "price_e4": 8500,
            "sequential": False,
        },
        {
            "id": "loss_mlb_iti",
            "op": "REACH",
            "outcome": "loss",
            "price_e4": 4000,
            "sequential": False,
        },
    ],
    "requested_dimensions": ["HOLD_TO_SETTLEMENT"],
    "terminal": "BOTH",
    "universe": {
        "date_from": "2025-04-01",
        "date_to": "2025-04-30",
        "game_data": [],
        "leagues": ["MLB"],
        "market_data": ["candles"],
        "markets": ["kalshi"],
        "seasons": ["2025-2026"],
        "sports": ["MLB"],
    },
}


def iti_question_for_folder(folder: str) -> dict[str, Any]:
    """MLB uses the candle desk question. Do not reuse the NBA Q4 stress fixture."""
    if str(folder or "").strip().upper() == "MLB":
        return copy.deepcopy(MLB_ITI_QUESTION)
    raise ValueError("iti_question_for_folder is MLB-only; NBA keeps stress_question.py")
