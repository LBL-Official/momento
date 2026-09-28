"""Deterministic internal_game_id from stable team codes."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime

from roller.timeutil import UTC, parse_utc


def yyyymmdd(game_date: str) -> str:
    return str(game_date).replace("-", "")[:8]


def id_token(team_id: str) -> str:
    """Keep letters, digits, and hyphen. Strip spaces so display names cannot mint IDs."""
    return "".join(ch for ch in str(team_id) if ch.isalnum() or ch == "-")


def base_game_id(sport: str, game_date: str, away_id: str, home_id: str) -> str:
    return f"{sport}_{yyyymmdd(game_date)}_{id_token(away_id)}_{id_token(home_id)}"


def assign_internal_ids(rows: list[dict]) -> list[dict]:
    """Assign rematch suffixes after sorting each day/team-pair by scheduled_start."""
    groups: dict[tuple[str, str, str, str], list[dict]] = defaultdict(list)
    for row in rows:
        key = (
            str(row["sport"]),
            str(row["game_date"]),
            str(row["away_team_id"]),
            str(row["home_team_id"]),
        )
        groups[key].append(row)

    out: list[dict] = []
    for key, items in groups.items():
        sport, game_date, away, home = key
        items = sorted(items, key=_start_sort_key)
        for i, item in enumerate(items, start=1):
            rec = dict(item)
            rec["internal_game_id"] = (
                base_game_id(sport, game_date, away, home) if i == 1 else f"{base_game_id(sport, game_date, away, home)}_{i}"
            )
            out.append(rec)
    return out


def _start_sort_key(row: dict) -> tuple:
    raw = row.get("scheduled_start") or row.get("game_date") or ""
    fallback = datetime.min.replace(tzinfo=UTC)
    try:
        dt = parse_utc(raw) if raw else fallback
    except Exception:
        dt = fallback
    return (dt or fallback, str(row.get("event_ticker") or ""), str(row.get("warehouse_game_id") or ""))


MAPPING_MAPPED = "MAPPED"
MAPPING_REVIEW = "REVIEW_REQUIRED"
MAPPING_UNMAPPED = "UNMAPPED"
CONFIDENCE_HIGH = "HIGH"
CONFIDENCE_NONE = "NONE"


def mapping_from_crosswalk(status: str | None, unique: bool, has_tickers: bool) -> tuple[str, str]:
    st = (status or "").upper()
    if st == "MATCHED" and unique and has_tickers:
        return MAPPING_MAPPED, CONFIDENCE_HIGH
    if st == "UNMATCHED" or not has_tickers:
        return MAPPING_UNMAPPED, CONFIDENCE_NONE
    return MAPPING_REVIEW, CONFIDENCE_NONE
