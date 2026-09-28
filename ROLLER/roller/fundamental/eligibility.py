"""Prior-only eligibility. Both clocks and current-game identity."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from roller.timeutil import parse_utc, parse_utc_required


def fundamental_eligible(
    row: dict[str, Any],
    *,
    current_game_id: str,
    cutoff,
) -> bool:
    """eligible iff other game AND state_available_at < cutoff AND result_available_at < cutoff."""
    if str(row.get("internal_game_id") or "") == str(current_game_id or ""):
        return False
    cut = cutoff if isinstance(cutoff, datetime) else parse_utc_required(cutoff)
    state_at = parse_utc(row.get("state_available_at"))
    result_at = parse_utc(row.get("result_available_at"))
    if state_at is None or result_at is None:
        return False
    return state_at < cut and result_at < cut
