"""Locked transition identity. Systimo-owned. Same trace_id every stage."""

from __future__ import annotations

import hashlib
from typing import Any

UNAVAILABLE = "UNAVAILABLE"
MISSING = frozenset({"", "null", "none", UNAVAILABLE, "UNAVAILABLE"})

MATCH_FIELDS = (
    "trade_id",
    "internal_game_id",
    "event_id",
    "a_contract",
    "b_contract",
    "as_of",
)


def _norm(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if text.lower() in MISSING:
        return None
    return text


def extract_identity(body: dict[str, Any] | None) -> dict[str, str | None]:
    payload = body if isinstance(body, dict) else {}
    nested = payload.get("identity") if isinstance(payload.get("identity"), dict) else {}
    trade = (
        nested.get("trade_id")
        or payload.get("trade_id")
        or payload.get("position_id")
    )
    return {
        "trade_id": _norm(trade),
        "internal_game_id": _norm(nested.get("internal_game_id") or payload.get("internal_game_id") or payload.get("game_id")),
        "event_id": _norm(nested.get("event_id") or payload.get("event_id")),
        "a_contract": _norm(nested.get("a_contract") or payload.get("a_contract") or payload.get("A_contract")),
        "b_contract": _norm(nested.get("b_contract") or payload.get("b_contract") or payload.get("B_contract")),
        "as_of": _norm(nested.get("as_of") or payload.get("as_of")),
        "source_mode": _norm(payload.get("source_mode") or payload.get("feed_mode") or payload.get("data_mode") or "HISTORICAL"),
    }


def trace_id(identity: dict[str, str | None]) -> str:
    parts = [
        identity.get("trade_id") or "",
        identity.get("event_id") or "",
        identity.get("a_contract") or "",
        identity.get("b_contract") or "",
        identity.get("as_of") or "",
        identity.get("source_mode") or "HISTORICAL",
    ]
    raw = "|".join(parts).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:16]


def match_identities(left: dict[str, str | None], right: dict[str, str | None]) -> dict[str, Any]:
    mismatches: list[str] = []
    time_mismatch = False
    merged: dict[str, str | None] = {}
    for field in MATCH_FIELDS:
        a = left.get(field)
        b = right.get(field)
        if a and b and a != b:
            mismatches.append(field)
            if field == "as_of":
                time_mismatch = True
        merged[field] = a or b
    merged["source_mode"] = left.get("source_mode") or right.get("source_mode") or "HISTORICAL"
    if time_mismatch:
        status = "STATE_TIME_MISMATCH"
    elif mismatches:
        status = "IDENTITY_MISMATCH"
    else:
        status = "MATCHED"
    merged_trace = trace_id(merged)
    return {
        "match_status": status,
        "mismatched_fields": mismatches,
        "identity": merged,
        "trace_id": merged_trace,
        "live_execution": False,
    }
