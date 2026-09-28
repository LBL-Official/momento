"""Frozen FIRST80 game window.

Same rule as nba_80_40_execution_audit.load_games:
game_date 16:00Z → game_date+2d 04:00Z (16h … 52h after date midnight UTC).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from roller.timeutil import parse_utc, to_iso


def game_window(game_date: Any) -> tuple[str, str]:
    raw = str(game_date or "").strip()
    if not raw:
        return "", ""
    if "T" in raw:
        dt = parse_utc(raw)
        if dt is None:
            return "", ""
        day = dt.replace(hour=0, minute=0, second=0, microsecond=0)
    else:
        try:
            day = datetime.strptime(raw[:10], "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except ValueError:
            return "", ""
    start = day + timedelta(hours=16)
    end = day + timedelta(hours=52)
    return to_iso(start), to_iso(end)
