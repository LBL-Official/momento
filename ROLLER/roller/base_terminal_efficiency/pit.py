"""ROLLER I(t): available_at < observation_ts. Equality is excluded."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Iterable

from roller.timeutil import parse_utc


def parse_ts(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value
    return parse_utc(value)


def is_visible(available_at: Any, observation_ts: Any) -> bool:
    """Constitutional visibility. available_at == t is invisible."""
    avail = parse_ts(available_at)
    obs = parse_ts(observation_ts)
    if avail is None or obs is None:
        return False
    return avail < obs


def filter_visible(rows: Iterable[dict[str, Any]], observation_ts: Any) -> list[dict[str, Any]]:
    return [r for r in rows if is_visible(r.get("available_at"), observation_ts)]


def assert_source_before_observation(available_at: Any, observation_ts: Any, *, field: str) -> None:
    if not is_visible(available_at, observation_ts):
        raise ValueError(f"PIT violation on {field}: available_at is not < observation_ts")
