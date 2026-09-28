"""Canonical V4A orientation: subject = home. Do not silently flip."""

from __future__ import annotations

from typing import Any


def parse_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def score_diff_home(home_score: Any, away_score: Any) -> int | None:
    """score_diff = home − away. Positive = home leads."""
    home = parse_int(home_score)
    away = parse_int(away_score)
    if home is None or away is None:
        return None
    return home - away


def home_leading(score_diff: Any) -> bool | None:
    parsed = parse_int(score_diff)
    if parsed is None:
        return None
    return parsed > 0


def home_trailing(score_diff: Any) -> bool | None:
    parsed = parse_int(score_diff)
    if parsed is None:
        return None
    return parsed < 0


def y_home_win(home_win: Any) -> int | None:
    """Y=1 iff home_win == 1. Ties are home_win=0, away_win=0 → Y=0."""
    text = str(home_win).strip() if home_win is not None else ""
    if text == "1":
        return 1
    if text == "0":
        return 0
    return None
