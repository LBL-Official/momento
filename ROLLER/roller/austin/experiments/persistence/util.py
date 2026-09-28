"""Shared persistence helpers. Missing stays UNAVAILABLE. Never zero-fill."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from roller.state.clock import elapsed_game_seconds

from roller.austin.experiments.persistence.ids import UNAVAILABLE


def as_float(value: object) -> float | None:
    if value is None or value == "" or value == UNAVAILABLE:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def as_int(value: object) -> int | None:
    num = as_float(value)
    return None if num is None else int(round(num))


def as_bool(value: object) -> bool | None:
    if value is None or value == "" or value == UNAVAILABLE:
        return None
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in {"true", "1", "yes"}:
        return True
    if text in {"false", "0", "no"}:
        return False
    return None


def cell(value: object) -> object:
    if value is None:
        return UNAVAILABLE
    if isinstance(value, bool):
        return value
    return value


def elapsed(period: object, remaining: object) -> int | None:
    return elapsed_game_seconds(period, remaining, sport="NCAAB")


def clock_minutes_between(start: dict[str, Any] | None, end: dict[str, Any] | None) -> float | None:
    if start is None or end is None:
        return None
    a = elapsed(start.get("period"), start.get("game_clock_remaining"))
    b = elapsed(end.get("period"), end.get("game_clock_remaining"))
    if a is None or b is None:
        return None
    return max(0.0, (b - a) / 60.0)


def game_seconds_remaining(period: object, remaining: object) -> int | None:
    used = elapsed(period, remaining)
    if used is None:
        return None
    if used <= 2400:
        return max(0, 2400 - used)
    return max(0, 300 - ((used - 2400) % 300))


def primary_sort_key(row: dict[str, Any]) -> tuple[int, str, int, int]:
    used = elapsed(row.get("period"), row.get("game_clock_remaining"))
    return (
        used if used is not None else 10**12,
        str(row.get("timestamp_utc") or ""),
        int(row.get("period") or 99),
        -int(row.get("game_clock_remaining") or 0),
    )


def sort_primary(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(rows, key=primary_sort_key)


def valid_ev(row: dict[str, Any]) -> bool:
    return row.get("conditional_ev_cents") is not None


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({name: cell(row.get(name)) for name in fields})
