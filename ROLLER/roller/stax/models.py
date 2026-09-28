"""STAX data shapes and errors. Research only. No order submission."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


class StaxError(Exception):
    def __init__(self, code: str, message: str, details: dict[str, Any] | None = None):
        self.code = code
        self.message = message
        self.details = details or {}
        super().__init__(f"{code}: {message}")

    def as_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "status": self.code,
            "code": self.code,
            "message": self.message,
        }
        if self.details:
            out["details"] = self.details
        return out


class ConstraintViolation(StaxError):
    def __init__(self, message: str, details: dict[str, Any] | None = None):
        super().__init__(
            "STAX_CONSTRAINT_VIOLATION",
            message,
            details,
        )


STATUS_COMPLETE = "COMPLETE"
STATUS_PARTIAL = "PARTIAL"
STATUS_FAILED = "FAILED"
STATUS_PENDING = "PENDING"
STATUS_DATA_REQUIRED = "DATA_REQUIRED"

KIND_MAJOR = "MAJOR"
KIND_MINOR = "MINOR"
KIND_PATCH = "PATCH"


@dataclass(frozen=True)
class CanonicalUniverse:
    sport_family: str
    league_set: tuple[str, ...]
    seasons: tuple[str, ...]
    date_from: str | None
    date_to: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "sport_family": self.sport_family,
            "league_set": list(self.league_set),
            "seasons": list(self.seasons),
            "date_from": self.date_from,
            "date_to": self.date_to,
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any] | None) -> CanonicalUniverse:
        raw = raw or {}
        return cls(
            sport_family=str(raw.get("sport_family") or "unknown"),
            league_set=tuple(raw.get("league_set") or ()),
            seasons=tuple(raw.get("seasons") or ()),
            date_from=_empty_to_none(raw.get("date_from")),
            date_to=_empty_to_none(raw.get("date_to")),
        )


def _empty_to_none(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def utc_now() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_version(text: str) -> tuple[int, int, int]:
    raw = str(text or "").strip().lstrip("v")
    parts = raw.split(".")
    if len(parts) != 3:
        raise StaxError("STAX_VERSION_INVALID", f"invalid version {text!r}")
    try:
        return int(parts[0]), int(parts[1]), int(parts[2])
    except ValueError as exc:
        raise StaxError("STAX_VERSION_INVALID", f"invalid version {text!r}") from exc


def format_version(major: int, minor: int, patch: int) -> str:
    return f"{major}.{minor}.{patch}"


def bump_version(
    current: str | None,
    *,
    kind: str,
) -> str:
    if not current:
        return "1.0.0"
    major, minor, patch = parse_version(current)
    if kind == KIND_MAJOR:
        return format_version(major + 1, 0, 0)
    if kind == KIND_MINOR:
        return format_version(major, minor + 1, 0)
    if kind == KIND_PATCH:
        return format_version(major, minor, patch + 1)
    raise StaxError("STAX_VERSION_INVALID", f"unknown bump kind {kind!r}")


def next_numeric_id(prefix: str, existing: list[str], width: int = 4) -> str:
    highest = 0
    for item in existing:
        text = str(item or "")
        if not text.startswith(prefix):
            continue
        tail = text[len(prefix) :].lstrip("-")
        if tail.isdigit():
            highest = max(highest, int(tail))
    return f"{prefix}-{str(highest + 1).zfill(width)}"
