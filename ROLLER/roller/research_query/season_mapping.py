"""UI season labels → warehouse season keys. Config is the authority."""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from roller.config import RollerConfig


_UI_ALIASES = {
    "2025-26": "2025-2026",
    "2026-27": "2026-2027",
    "2024-25": "2024-2025",
    "2023-24": "2023-2024",
}


@lru_cache(maxsize=1)
def _seasons_block() -> dict[str, Any]:
    return RollerConfig().seasons


def warehouse_season(ui_or_warehouse: str, sport: str | None = None) -> str:
    raw = str(ui_or_warehouse or "").strip()
    if not raw:
        raise ValueError("season required")
    if raw in _UI_ALIASES:
        mapped = _UI_ALIASES[raw]
    else:
        mapped = raw
    seasons = _seasons_block()
    if sport:
        block = seasons.get(sport) or {}
        if mapped in block:
            return mapped
        if raw in block:
            return raw
    for _sport, block in seasons.items():
        if mapped in block or raw in block:
            return mapped if mapped in block else raw
    return mapped


def default_warehouse_season(sport: str) -> str:
    block = _seasons_block().get(sport) or {}
    if "2025-2026" in block:
        return "2025-2026"
    keys = list(block.keys())
    if not keys:
        raise ValueError(f"no seasons configured for {sport}")
    return str(keys[0])


def normalize_league(league: str) -> str:
    raw = str(league or "").strip()
    key = raw.upper()
    if key in {"NBA", "WNBA", "NCAAB", "MLB", "ATP", "WTA"}:
        return key
    if raw.lower() == "baseball":
        return "MLB"
    if raw.lower() == "tennis":
        return "ATP"
    raise ValueError(f"unknown league {league!r}")


def sport_from_league(league: str) -> str:
    """UI league or sport-family alias → warehouse sport.

    Baseball / MLB both resolve to MLB. Basketball aliases stay league-native.
    Tennis family alias resolves to ATP so a sport-only draft still maps.
    ATP and WTA remain distinct warehouse sports sharing one data tree.
    """
    return normalize_league(league)
