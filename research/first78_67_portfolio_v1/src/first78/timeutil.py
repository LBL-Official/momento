"""America/Los_Angeles clocks. DST is observed. UTC−8 is not forced."""

from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

LA = ZoneInfo("America/Los_Angeles")
ENTRY_START = datetime(2025, 11, 1, 0, 0, tzinfo=LA)
ENTRY_END = datetime(2026, 4, 2, 0, 0, tzinfo=LA)
LAUNCH_START = datetime(2026, 11, 1, 0, 0, tzinfo=LA)
LAUNCH_END = datetime(2027, 4, 2, 0, 0, tzinfo=LA)


def as_utc(ts: int | float | datetime) -> datetime:
    if isinstance(ts, datetime):
        if ts.tzinfo is None:
            return ts.replace(tzinfo=timezone.utc)
        return ts.astimezone(timezone.utc)
    return datetime.fromtimestamp(int(ts), tz=timezone.utc)


def iso_utc(ts: int | float | datetime | None) -> str | None:
    if ts is None:
        return None
    return as_utc(ts).isoformat()


def iso_la(ts: int | float | datetime | None) -> str | None:
    if ts is None:
        return None
    local = as_utc(ts).astimezone(LA)
    abbr = local.tzname() or ""
    return f"{local.isoformat()} {abbr}"


def in_historical_entry_window(ts: int | float | datetime) -> bool:
    local = as_utc(ts).astimezone(LA)
    return ENTRY_START <= local < ENTRY_END


def local_date(ts: int | float | datetime):
    return as_utc(ts).astimezone(LA).date()


def week_start(ts: int | float | datetime):
    """Monday-start local week."""
    day = local_date(ts)
    return day.fromordinal(day.toordinal() - day.weekday())
