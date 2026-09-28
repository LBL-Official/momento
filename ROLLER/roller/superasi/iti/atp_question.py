"""ATP ITI source question. Not FIRST80 and not the NBA Q4 stress fixture.

Candle TRADABLE_YES_BID CROSS 65 / REACH 85 / REACH 40. No period lock.
ITI cents are not a live Kalshi signal.
"""

from __future__ import annotations

import copy
from typing import Any

STRATEGY_NAME = "ATP CANDLE CROSS 65 REACH 85 40"

ATP_ITI_QUESTION: dict[str, Any] = {
    "accept_limitations": False,
    "entry_conditions": [
        {
            "clock": None,
            "event_definition": "TRADABLE_CLOSE_CROSS",
            "id": "entry_atp_iti",
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
            "id": "win_atp_iti",
            "op": "REACH",
            "outcome": "win",
            "price_e4": 8500,
            "sequential": False,
        },
        {
            "id": "loss_atp_iti",
            "op": "REACH",
            "outcome": "loss",
            "price_e4": 4000,
            "sequential": False,
        },
    ],
    "requested_dimensions": ["HOLD_TO_SETTLEMENT"],
    "terminal": "BOTH",
    "universe": {
        "date_from": "2025-07-01",
        "date_to": "2025-07-31",
        "game_data": [],
        "leagues": ["ATP"],
        "market_data": ["candles"],
        "markets": ["kalshi"],
        "seasons": ["2025-2026"],
        "sports": ["ATP"],
    },
}


def iti_question_for_folder(folder: str) -> dict[str, Any]:
    """ATP uses the candle desk question. Do not reuse FIRST80 or NBA Q4."""
    if str(folder or "").strip().upper() == "ATP":
        return copy.deepcopy(ATP_ITI_QUESTION)
    raise ValueError("iti_question_for_folder is ATP-only; WTA keeps wta_question.py")
