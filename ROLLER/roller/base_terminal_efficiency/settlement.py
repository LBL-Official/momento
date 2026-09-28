"""Kalshi settlement only. Import settled_yes. Never infer from box score."""

from __future__ import annotations

from typing import Any

from roller.base_terminal_efficiency.models import TERMINAL_MISSING, TERMINAL_NO, TERMINAL_YES
from roller.research.first80 import settled_yes


def terminal_outcome(market: dict[str, Any] | None) -> str:
    if not market:
        return TERMINAL_MISSING
    flag = settled_yes(market.get("result") or market.get("kalshi_result"), market.get("settlement_value_e4"))
    if flag == "1":
        return TERMINAL_YES
    if flag == "0":
        return TERMINAL_NO
    return TERMINAL_MISSING
