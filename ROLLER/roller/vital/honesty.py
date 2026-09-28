"""Honesty tokens. Missing is not zero. Unread is not RUNNING."""

from __future__ import annotations

from typing import Any


def unavailable(reason: str = "UNAVAILABLE") -> dict[str, Any]:
    return {"value": None, "status": reason}


def confirmed(value: Any) -> dict[str, Any]:
    return {"value": value, "status": "CONFIRMED"}


def observation_unavailable(reason: str = "OBSERVATION_UNAVAILABLE") -> dict[str, Any]:
    out = {"value": None, "status": "OBSERVATION_UNAVAILABLE"}
    if reason and reason != "OBSERVATION_UNAVAILABLE":
        out["detail"] = reason
    return out


def fact(*, desired: Any = None, observed: Any = None, confirmed_value: Any = None, detail: str | None = None) -> dict[str, Any]:
    out = {
        "desired": desired,
        "observed": observed,
        "confirmed": confirmed_value,
    }
    if detail is not None:
        out["detail"] = detail
    return out
