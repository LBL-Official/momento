"""Clock helpers. Modeled / sequence clocks are not warehouse PIT."""

from __future__ import annotations

import re
from datetime import datetime, timezone

_ISO = re.compile(r"^PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+(?:\.\d+)?)S)?$")
_MMSS = re.compile(r"^(\d{1,2}):(\d{2})(?:\.(\d+))?$")


def parse_utc(value: object) -> datetime | None:
    if isinstance(value, datetime):
        stamp = value
        if stamp.tzinfo is None:
            stamp = stamp.replace(tzinfo=timezone.utc)
        return stamp.astimezone(timezone.utc)
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        seconds = float(value)
        if seconds >= 1_000_000_000:
            return datetime.fromtimestamp(seconds, tz=timezone.utc)
        return None
    text = str(value or "").strip()
    if not text:
        return None
    if text.isdigit() or (text.replace(".", "", 1).isdigit() and text.count(".") <= 1):
        try:
            seconds = float(text)
        except ValueError:
            seconds = None
        if seconds is not None and seconds >= 1_000_000_000:
            return datetime.fromtimestamp(seconds, tz=timezone.utc)
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        stamp = datetime.fromisoformat(text)
    except ValueError:
        return None
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=timezone.utc)
    return stamp.astimezone(timezone.utc)


def clock_to_seconds(value: object) -> int | None:
    text = str(value or "").strip()
    if not text:
        return None
    iso = _ISO.match(text)
    if iso is not None:
        hours = int(iso.group(1) or 0)
        mins = int(iso.group(2) or 0)
        secs = float(iso.group(3) or 0.0)
        return int(round(hours * 3600 + mins * 60 + secs))
    mmss = _MMSS.match(text)
    if mmss is not None:
        return int(mmss.group(1)) * 60 + int(mmss.group(2))
    try:
        return int(round(float(text)))
    except (TypeError, ValueError):
        return None


def format_clock(seconds: int | None) -> str | None:
    if seconds is None:
        return None
    sec = max(0, int(seconds))
    return f"{sec // 60:02d}:{sec % 60:02d}"


def period_to_quarter(value: object) -> int | None:
    text = str(value or "").strip().upper()
    if not text:
        return None
    if text in {"2", "Q2", "2Q"}:
        return 2
    if text in {"3", "Q3", "3Q"}:
        return 3
    if text in {"1", "Q1", "1Q"}:
        return 1
    if text in {"4", "Q4", "4Q"}:
        return 4
    try:
        n = int(float(text))
    except (TypeError, ValueError):
        return None
    return n if n > 0 else None


def game_elapsed_seconds(quarter: int | None, seconds_remaining: int | None) -> int | None:
    if quarter is None or seconds_remaining is None:
        return None
    q = int(quarter)
    left = max(0, int(seconds_remaining))
    return (q - 1) * 720 + (720 - min(left, 720))


def time_since_entry_seconds(
    *,
    entry_quarter: int | None,
    entry_seconds_remaining: int | None,
    current_quarter: int | None,
    current_seconds_remaining: int | None,
    wall_seconds: float | None = None,
) -> int | None:
    start = game_elapsed_seconds(entry_quarter, entry_seconds_remaining)
    now = game_elapsed_seconds(current_quarter, current_seconds_remaining)
    if start is not None and now is not None:
        return max(0, now - start)
    if wall_seconds is None:
        return None
    return max(0, int(round(float(wall_seconds))))
