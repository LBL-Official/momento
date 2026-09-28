"""Four distinct clocks. Never collapse MARKET / GAME_EVENT / FEATURE_AS_OF / PREDICTION."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

ISO_FMT = "%Y-%m-%dT%H:%M:%S%z"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def parse_utc(value: Any) -> datetime | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
    text = str(value).strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def to_iso(dt: datetime | None) -> str:
    if dt is None:
        return ""
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def parse_iso_duration_seconds(clock: str) -> float | None:
    """Parse NBA/ISO clock like PT12M00.00S or MM:SS."""
    if not clock:
        return None
    text = str(clock).strip()
    if text.startswith("PT"):
        minutes = 0.0
        seconds = 0.0
        rest = text[2:]
        if "M" in rest:
            m, rest = rest.split("M", 1)
            try:
                minutes = float(m)
            except ValueError:
                return None
        if rest.endswith("S"):
            try:
                seconds = float(rest[:-1])
            except ValueError:
                return None
        return minutes * 60.0 + seconds
    if ":" in text:
        parts = text.split(":")
        try:
            if len(parts) == 2:
                return float(parts[0]) * 60.0 + float(parts[1])
        except ValueError:
            return None
    return None


def seconds_remaining_game(
    period: int,
    seconds_remaining_period: float,
    *,
    regulation_periods: int,
    period_seconds: int,
    ot_seconds: int,
) -> float:
    if period < 1:
        period = 1
    if period < regulation_periods:
        remaining_full = (regulation_periods - period) * period_seconds
        return float(seconds_remaining_period) + remaining_full
    if period == regulation_periods:
        return float(seconds_remaining_period)
    # OT: only current OT remaining is known without assuming further OTs
    return float(seconds_remaining_period)


def add_duration(start: datetime | None, duration: str | None) -> datetime | None:
    """Box duration like '2:13' (H:MM)."""
    if start is None or not duration:
        return None
    parts = str(duration).split(":")
    try:
        if len(parts) == 2:
            hours, minutes = int(parts[0]), int(parts[1])
            return start + timedelta(hours=hours, minutes=minutes)
        if len(parts) == 3:
            hours, minutes, seconds = int(parts[0]), int(parts[1]), int(parts[2])
            return start + timedelta(hours=hours, minutes=minutes, seconds=seconds)
    except ValueError:
        return None
    return None


@dataclass(frozen=True)
class ObservationClocks:
    prediction_timestamp: datetime
    feature_as_of_timestamp: datetime
    game_event_timestamp: datetime | None
    market_timestamp: datetime | None

    def as_dict(self) -> dict[str, str]:
        return {
            "prediction_timestamp": to_iso(self.prediction_timestamp),
            "feature_as_of_timestamp": to_iso(self.feature_as_of_timestamp),
            "game_event_timestamp": to_iso(self.game_event_timestamp),
            "market_timestamp": to_iso(self.market_timestamp),
        }
