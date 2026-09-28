"""PIT leakage audit. Entry state must not see the future.

Invariant: PBP_FEATURE_TIMESTAMP <= MARKET_ENTRY_TIMESTAMP or EXCLUDE.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from roller.mlb.snap import snap_mlb
from roller.timeutil import parse_utc

FUTURE_FIELDS = (
    "inning",
    "half",
    "outs",
    "balls",
    "strikes",
    "runners",
    "home_score",
    "away_score",
    "yes_batting",
)


def _ts(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value
    return parse_utc(value)


def audit_snap(
    events: list[dict[str, Any]],
    entry_ts: Any,
    *,
    team_side: str | None = None,
) -> dict[str, Any]:
    snap_ts = _ts(entry_ts)
    if snap_ts is None:
        return {"ok": False, "reason": "UNPARSEABLE_ENTRY_TS", "exclude": True}
    body = snap_mlb(events, snap_ts, team_side=team_side)
    feat_ts = _ts(body.get("event_timestamp"))
    if body.get("status") == "UNALIGNED" or feat_ts is None:
        return {
            "ok": True,
            "exclude": True,
            "reason": "PIT_ALIGNMENT_FAILED",
            "snap": body,
        }
    if feat_ts > snap_ts:
        return {
            "ok": False,
            "exclude": True,
            "reason": "FORWARD_SNAP",
            "pbp_ts": body.get("event_timestamp"),
            "entry_ts": entry_ts,
        }
    return {"ok": True, "exclude": False, "reason": None, "snap": body}


def audit_population(
    cases: list[dict[str, Any]],
) -> dict[str, Any]:
    """Each case: events, entry_ts, optional team_side, forbidden_future_row."""
    failures: list[str] = []
    excluded = 0
    for i, case in enumerate(cases):
        result = audit_snap(
            case.get("events") or [],
            case.get("entry_ts"),
            team_side=case.get("team_side"),
        )
        if result.get("exclude"):
            excluded += 1
        if not result.get("ok"):
            failures.append(f"{i}:{result.get('reason')}")
            continue
        snap = result.get("snap") or {}
        forbidden = case.get("forbidden") or {}
        for key, value in forbidden.items():
            if snap.get(key) == value and key in FUTURE_FIELDS:
                failures.append(f"{i}:leaked_{key}")
    return {
        "ok": not failures,
        "n": len(cases),
        "excluded": excluded,
        "failures": failures,
    }
