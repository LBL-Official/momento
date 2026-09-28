"""Descriptive previous-game windows. Not a model input."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from roller.ontologic_x.identity import _parse_time, season_type_from_game_id

WINDOW = 10
LONG_GAP = timedelta(days=45)
LABEL = "DESCRIPTIVE_ONLY"


def descriptive_windows(history: list[dict], tipoff: object, target_game_id: str) -> dict:
    """Up to ten completed games of each season type, strictly before tipoff."""
    start = _aware(tipoff)
    grouped: dict[str, list[dict]] = {}
    if start is None:
        return {"label": LABEL, "windows": {}, "reason": "TIPOFF_UNAVAILABLE"}
    for row in history:
        game_id = str(row.get("nba_game_id") or "")
        if not game_id or game_id == str(target_game_id):
            continue
        played = _aware(row.get("start_utc"))
        if played is None or played >= start:
            continue
        if row.get("completed") is False:
            continue
        season_type = str(row.get("season_type") or season_type_from_game_id(game_id))
        grouped.setdefault(season_type, []).append(row)
    windows = {}
    for season_type, rows in grouped.items():
        rows.sort(key=lambda item: str(item.get("start_utc")))
        chosen = rows[-WINDOW:]
        windows[season_type] = {
            "label": LABEL,
            "season_type": season_type,
            "count": len(chosen),
            "requested": WINDOW,
            "game_ids": [row.get("nba_game_id") for row in chosen],
            "games": chosen,
            "cross_season": len({str(row.get("season")) for row in chosen if row.get("season")}) > 1,
            "long_gap": _long_gap(chosen),
            "model_input": False,
        }
    return {"label": LABEL, "windows": windows, "reason": None}


def _aware(value: object) -> datetime | None:
    parsed = _parse_time(value)
    if parsed is None:
        text = str(value or "").strip()
        for fmt in ("%b %d, %Y", "%B %d, %Y"):
            try:
                parsed = datetime.strptime(text, fmt)
                break
            except ValueError:
                parsed = None
    if parsed is None:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _long_gap(rows: list[dict]) -> bool:
    times = [parsed for row in rows if (parsed := _aware(row.get("start_utc"))) is not None]
    times.sort()
    return any(right - left >= LONG_GAP for left, right in zip(times, times[1:]))
