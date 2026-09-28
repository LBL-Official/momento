"""Lightweight field and section missingness. Never return a bare null without status."""

from __future__ import annotations

from typing import Any

SOURCE_STATUSES = ("REAL", "PARTIAL", "INCOMPLETE", "SCHEMA_ONLY", "NOT_SUPPORTED")
FIELD_STATUSES = ("observed", "known_missing", "source_missing", "not_supported", "not_implemented")


def field(value: Any, status: str = "observed", source: str = "") -> dict[str, Any]:
    if value in (None, "") and status == "observed":
        status = "source_missing"
    return {"value": None if value == "" else value, "status": status, "source": source}


def section(status: str, data: Any = None, **extra: Any) -> dict[str, Any]:
    body = {
        "status": status,
        "source_availability_status": status,
        "data": data,
    }
    body.update(extra)
    return body
