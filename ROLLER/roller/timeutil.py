"""UTC timestamps and half-open as_of cutoffs.

as_of always filters: available_at < cutoff
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import pandas as pd

UTC = timezone.utc


class TimestampError(ValueError):
    pass


def now_utc() -> datetime:
    return datetime.now(UTC)


def now_utc_iso() -> str:
    return to_iso(now_utc())


def to_iso(dt: datetime) -> str:
    if dt.tzinfo is None:
        raise TimestampError("refusing timezone-naive datetime")
    return dt.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S") + "Z"


def parse_utc(value: Any) -> datetime | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    if isinstance(value, pd.Timestamp):
        if value.tzinfo is None:
            raise TimestampError("refusing timezone-naive timestamp")
        return value.to_pydatetime().astimezone(UTC)
    if isinstance(value, datetime):
        if value.tzinfo is None:
            raise TimestampError("refusing timezone-naive datetime")
        return value.astimezone(UTC)
    text = str(value).strip()
    if not text or text.lower() in {"nan", "nat", "none"}:
        return None
    if len(text) == 10 and text[4] == "-" and text[7] == "-":
        return datetime(int(text[:4]), int(text[5:7]), int(text[8:10]), tzinfo=UTC)
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    dt = datetime.fromisoformat(text)
    if dt.tzinfo is None:
        raise TimestampError(f"refusing timezone-naive value: {value!r}")
    return dt.astimezone(UTC)


def parse_utc_required(value: Any) -> datetime:
    dt = parse_utc(value)
    if dt is None:
        raise TimestampError(f"missing timestamp: {value!r}")
    return dt


def resolve_cutoff(as_of: Any, end_of_day: bool = False) -> datetime:
    """Date → UTC start (or next midnight if end_of_day). Timestamp → literal UTC."""
    if isinstance(as_of, datetime):
        if as_of.tzinfo is None:
            raise TimestampError("refusing timezone-naive as_of")
        cutoff = as_of.astimezone(UTC)
        if end_of_day and cutoff.time() == datetime.min.time():
            return cutoff + timedelta(days=1)
        return cutoff
    text = str(as_of).strip()
    if len(text) == 10 and text[4] == "-" and text[7] == "-":
        start = datetime(int(text[:4]), int(text[5:7]), int(text[8:10]), tzinfo=UTC)
        return start + timedelta(days=1) if end_of_day else start
    return parse_utc_required(text)


def series_to_utc(series: pd.Series) -> pd.Series:
    parsed = []
    for v in series.tolist():
        parsed.append(parse_utc(v) if pd.notna(v) and str(v).strip() != "" else pd.NaT)
    return pd.Series(parsed, index=series.index)


def apply_as_of(
    df: pd.DataFrame,
    cutoff: datetime,
    column: str = "available_at",
) -> pd.DataFrame:
    """Half-open: keep rows with available_at < cutoff."""
    if column not in df.columns:
        raise TimestampError(f"dataset missing {column}; cannot apply as_of")
    ts = series_to_utc(df[column])
    if cutoff.tzinfo is None:
        raise TimestampError("cutoff must be timezone-aware UTC")
    mask = ts.notna() & (ts < cutoff)
    return df.loc[mask].copy()
