"""Attach TARGET_* after PIT keys. Never used to assign state."""

from __future__ import annotations

from typing import Any

from roller.austin.experiments.hazard.ids import (
    FORBIDDEN_PIT,
    NEGATIVE_STATES,
    NOT_APPLICABLE,
    RECOVERY_NA_STATES,
    STATE_DEPTH,
    UNRESOLVED,
)
from roller.austin.experiments.persistence.util import as_float


def _valid_ev(row: dict[str, Any] | None) -> float | None:
    if row is None:
        return None
    if row.get("core_state") == UNRESOLVED:
        return None
    return as_float(row.get("EV"))


def _later(timeline: list[dict[str, Any]], entry: dict[str, Any]) -> list[dict[str, Any]]:
    seq = int(entry.get("state_sequence_number") or 0)
    return [r for r in timeline if int(r.get("state_sequence_number") or 0) > seq]


def recovery_horizon(timeline: list[dict[str, Any]], entry: dict[str, Any], k: int) -> object:
    if entry.get("core_state") in RECOVERY_NA_STATES:
        return NOT_APPLICABLE
    later = _later(timeline, entry)
    prev = int(entry.get("state_sequence_number") or 0)
    valids: list[float] = []
    for row in later:
        seq = int(row.get("state_sequence_number") or 0)
        if seq != prev + 1:
            return None
        ev = _valid_ev(row)
        if ev is None:
            return None
        valids.append(ev)
        prev = seq
        if any(v >= 0 for v in valids):
            return 1
        if len(valids) >= k:
            return 0
    return None


def deeper_distress_next(timeline: list[dict[str, Any]], entry: dict[str, Any]) -> object:
    if entry.get("core_state") not in NEGATIVE_STATES:
        return NOT_APPLICABLE
    later = _later(timeline, entry)
    if not later:
        return None
    nxt = later[0]
    if int(nxt.get("state_sequence_number") or 0) != int(entry.get("state_sequence_number") or 0) + 1:
        return None
    ev = _valid_ev(nxt)
    if ev is None:
        return None
    src = STATE_DEPTH.get(str(entry.get("core_state")))
    dst = STATE_DEPTH.get(str(nxt.get("core_state")))
    if src is None:
        return None
    if dst is None:
        return 0
    return 1 if dst > src else 0


def t40_before_recovery(
    timeline: list[dict[str, Any]],
    entry: dict[str, Any],
    primary: list[dict[str, Any]],
) -> object:
    if entry.get("core_state") not in NEGATIVE_STATES:
        return NOT_APPLICABLE
    idx = int(entry.get("state_sequence_number") or 0)
    now = primary[idx] if 0 <= idx < len(primary) else None
    if now is None:
        return None
    if now.get("t40_already"):
        return NOT_APPLICABLE
    later = _later(timeline, entry)
    prev = idx
    for row in later:
        seq = int(row.get("state_sequence_number") or 0)
        if seq != prev + 1:
            return None
        src = primary[seq] if 0 <= seq < len(primary) else None
        ev = _valid_ev(row)
        if ev is None or src is None:
            return None
        hit = bool(src.get("t40_already") or src.get("hit_40_after"))
        if ev >= 0 and not hit:
            return 0
        if hit:
            return 1
        if ev >= 0:
            return 0
        prev = seq
    return None


def pit_keys(entry: dict[str, Any]) -> dict[str, Any]:
    lo = as_float(entry.get("CI_lower"))
    hi = as_float(entry.get("CI_upper"))
    payload = {
        "core_state": entry.get("core_state"),
        "CI_state": entry.get("CI_state"),
        "support_state": entry.get("support_state"),
        "negative_streak_length": entry.get("negative_streak_length"),
        "EV": as_float(entry.get("EV")),
        "CI_lower": lo,
        "CI_upper": hi,
        "CI_width": None if lo is None or hi is None else hi - lo,
    }
    leaked = set(payload) & FORBIDDEN_PIT
    if leaked:
        raise RuntimeError(f"hazard PIT leaked {sorted(leaked)}")
    return payload


def attach_targets(
    entry: dict[str, Any],
    timeline: list[dict[str, Any]],
    primary: list[dict[str, Any]],
) -> dict[str, Any]:
    out = dict(entry)
    out.update(pit_keys(entry))
    result = str(entry.get("OUTCOME_eventual_result") or "")
    out["TARGET_terminal_loss"] = 1 if result == "LOSS" else 0
    out["TARGET_recovery_t1"] = recovery_horizon(timeline, entry, 1)
    out["TARGET_recovery_by_t2"] = recovery_horizon(timeline, entry, 2)
    out["TARGET_recovery_by_t3"] = recovery_horizon(timeline, entry, 3)
    out["TARGET_deeper_distress_next"] = deeper_distress_next(timeline, entry)
    out["TARGET_T40_before_recovery"] = t40_before_recovery(timeline, entry, primary)
    return out
