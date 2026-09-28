"""Deterministic PIT INTERVENE / NONE. Missing required hazard is NONE. No H2 fallback."""

from __future__ import annotations

from typing import Any

from roller.austin.experiments.policy_v2.ids import (
    FORBIDDEN_STATES,
    INTERVENE,
    LOW_SUPPORT,
    NONE,
    ON_TIME,
    REQUIRED_HAZARD_UNAVAILABLE,
    TOO_LATE,
)


def _num(value: object) -> float | None:
    if value is None or value == "" or value == "UNAVAILABLE" or value == "NOT_APPLICABLE":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _meets(cond: dict[str, Any] | None, entry: dict[str, Any]) -> tuple[bool, str | None]:
    if not cond:
        return True, None
    field = cond["field"]
    val = _num(entry.get(field))
    if val is None:
        return False, REQUIRED_HAZARD_UNAVAILABLE
    op = cond["op"]
    cut = float(cond["value"])
    if op == "ge":
        return val >= cut, None
    if op == "lt":
        return val < cut, None
    return False, "UNKNOWN_OP"


def decide(candidate: dict[str, Any], entry: dict[str, Any]) -> dict[str, Any]:
    state = str(entry.get("core_state") or "")
    if state in FORBIDDEN_STATES:
        return {"action": NONE, "reason": "FORBIDDEN_STATE", "timing_class": None}
    allowed = set(candidate.get("required_core_states") or [])
    if state not in allowed:
        return {"action": NONE, "reason": "STATE_NOT_IN_CANDIDATE", "timing_class": None}
    ci_need = candidate.get("required_CI_state")
    if ci_need and entry.get("CI_state") != ci_need:
        return {"action": NONE, "reason": "CI_NOT_IN_CANDIDATE", "timing_class": None}
    support = candidate.get("support_requirement") or {}
    if support.get("reject_low_historical_support") and entry.get("support_state") == LOW_SUPPORT:
        return {"action": NONE, "reason": "LOW_HISTORICAL_SUPPORT", "timing_class": None}
    for field, minimum in support.items():
        if field == "reject_low_historical_support":
            continue
        key = "support_n_" + field[2:] if field.startswith("p_") else field
        n = _num(entry.get(key))
        if n is None or n < float(minimum):
            return {"action": NONE, "reason": "SUPPORT_BELOW_MINIMUM", "timing_class": None}
    ok_loss, why = _meets(candidate.get("p_terminal_loss_condition"), entry)
    if why:
        return {"action": NONE, "reason": why, "timing_class": None}
    if not ok_loss:
        return {"action": NONE, "reason": "LOSS_HAZARD_NOT_MET", "timing_class": None}
    ok_rec, why = _meets(candidate.get("p_recovery_condition"), entry)
    if why:
        return {"action": NONE, "reason": why, "timing_class": None}
    if not ok_rec:
        return {"action": NONE, "reason": "RECOVERY_HAZARD_NOT_MET", "timing_class": None}
    t40 = bool(entry.get("t40_already"))
    return {
        "action": INTERVENE,
        "reason": "PIT_RULE",
        "timing_class": TOO_LATE if t40 else ON_TIME,
    }
