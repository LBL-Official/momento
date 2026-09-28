"""Central point-in-time guard for DRE composition.

No source datum used in a composed response may have source_timestamp > as_of.
STATIC priors (Choosin Texas universe) have no path timestamp and are always valid.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterable

from roller.austin.clock import parse_utc


class DrePitError(Exception):
    def __init__(self, code: str, message: str) -> None:
        self.code = str(code)
        self.message = str(message)
        super().__init__(f"{self.code}: {self.message}")

    def as_dict(self) -> dict[str, str]:
        return {"status": self.code, "code": self.code, "message": self.message}


def to_utc(value: object) -> datetime | None:
    return parse_utc(value)


def iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    stamp = value.astimezone(timezone.utc)
    text = stamp.isoformat()
    if text.endswith("+00:00"):
        return text[:-6] + "Z"
    return text


def require_as_of(value: object) -> datetime:
    stamp = to_utc(value)
    if stamp is None:
        raise DrePitError("QUERY_REJECTED", "as_of is required and must be an ISO-8601 timestamp")
    return stamp


@dataclass(frozen=True)
class Stamped:
    field: str
    value: Any
    source: str
    source_timestamp: datetime | None
    pit_kind: str  # STATIC | PATH | QUERY | STATE

    def as_cell(self, availability: str) -> dict[str, Any]:
        return {
            "value": self.value,
            "availability": availability,
            "source": self.source,
            "source_timestamp": iso(self.source_timestamp),
            "field": self.field,
            "pit_kind": self.pit_kind,
        }


def unavailable_cell(field: str, *, source: str, detail: str) -> dict[str, Any]:
    return {
        "value": None,
        "availability": "UNAVAILABLE",
        "source": source,
        "source_timestamp": None,
        "field": field,
        "pit_kind": "MISSING",
        "detail": detail,
    }


def assert_not_after(as_of: datetime, stamped: Stamped) -> None:
    if stamped.pit_kind == "STATIC" or stamped.source_timestamp is None:
        return
    if stamped.source_timestamp > as_of:
        raise DrePitError(
            "PIT_VIOLATION",
            f"{stamped.field} source_timestamp {iso(stamped.source_timestamp)} > as_of {iso(as_of)}",
        )


def assert_all_not_after(as_of: datetime, stamps: Iterable[Stamped]) -> None:
    for item in stamps:
        assert_not_after(as_of, item)


def select_at_or_before(as_of: datetime, stamps: list[Stamped]) -> Stamped | None:
    """Latest STATIC-or-<= as_of stamp. Later stamps are not used."""
    eligible: list[Stamped] = []
    for item in stamps:
        if item.pit_kind == "STATIC" or item.source_timestamp is None:
            eligible.append(item)
            continue
        if item.source_timestamp <= as_of:
            eligible.append(item)
    if not eligible:
        return None
    dated = [item for item in eligible if item.source_timestamp is not None]
    if not dated:
        return eligible[-1]
    return max(dated, key=lambda item: item.source_timestamp or datetime.min.replace(tzinfo=timezone.utc))


def clip_path(as_of: datetime, points: list[dict[str, Any]], *, time_key: str = "t") -> list[dict[str, Any]]:
    kept: list[dict[str, Any]] = []
    for row in points:
        stamp = to_utc(row.get(time_key) or row.get("source_timestamp"))
        if stamp is None:
            continue
        if stamp > as_of:
            continue
        kept.append(row)
    return kept


def guard_value(as_of: datetime, stamped: Stamped) -> dict[str, Any]:
    """Return a cell from the latest valid stamp, or UNAVAILABLE. Reject later timestamps."""
    assert_not_after(as_of, stamped)
    if stamped.pit_kind != "STATIC" and stamped.source_timestamp is not None and stamped.source_timestamp > as_of:
        return unavailable_cell(stamped.field, source=stamped.source, detail="source_timestamp after as_of")
    if stamped.pit_kind != "STATIC" and stamped.source_timestamp is None and stamped.value is None:
        return unavailable_cell(stamped.field, source=stamped.source, detail="no source timestamp")
    if stamped.value is None:
        return unavailable_cell(stamped.field, source=stamped.source, detail="missing value at or before as_of")
    return stamped.as_cell("OBSERVED" if stamped.pit_kind != "STATIC" else "STATIC")
