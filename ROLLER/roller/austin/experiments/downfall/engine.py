"""Deterministic PIT downfall state assignment. History through t only."""

from __future__ import annotations

from typing import Any

from roller.austin.experiments.downfall.ids import (
    CI_CROSSES_ZERO,
    CI_NEGATIVE,
    CI_POSITIVE,
    CI_UNAVAILABLE,
    FORBIDDEN_PIT,
    HEALTHY,
    HEALTHY_AFTER_RECOVERY,
    LOW_HISTORICAL_SUPPORT,
    NORMAL_SUPPORT,
    PERSISTENCE_2,
    PERSISTENCE_3PLUS,
    PRE_ENTRY,
    RECOVERING,
    SUPPORT_UNAVAILABLE,
    UNRESOLVED,
    WATCH_NEGATIVE,
)
from roller.austin.experiments.persistence.util import as_float, clock_minutes_between, game_seconds_remaining


def ci_state(lo: float | None, hi: float | None) -> str:
    if lo is None or hi is None:
        return CI_UNAVAILABLE
    if lo > 0:
        return CI_POSITIVE
    if hi < 0:
        return CI_NEGATIVE
    return CI_CROSSES_ZERO


def support_state(status: object) -> str:
    text = str(status or "").strip()
    if text == "OBSERVED":
        return NORMAL_SUPPORT
    if text == "LOW_HISTORICAL_SUPPORT":
        return LOW_HISTORICAL_SUPPORT
    return SUPPORT_UNAVAILABLE


def _valid_ev(row: dict[str, Any] | None) -> float | None:
    if row is None:
        return None
    return as_float(row.get("conditional_ev_cents"))


def walk_core(history: list[dict[str, Any]]) -> tuple[str, int]:
    """Assign core state from PRIMARY history through t. No future rows."""
    if not history:
        return PRE_ENTRY, 0
    last_valid_ev: float | None = None
    last_core: str | None = None
    streak = 0
    saw_recovering = False
    current_state = UNRESOLVED
    current_streak = 0
    for row in history:
        ev = _valid_ev(row)
        if ev is None:
            current_state = UNRESOLVED
            current_streak = 0
            last_valid_ev = None
            last_core = None
            streak = 0
            saw_recovering = False
            continue
        if last_valid_ev is None:
            if ev < 0:
                current_state = WATCH_NEGATIVE
                streak = 1
            else:
                current_state = HEALTHY
                streak = 0
            saw_recovering = False
        elif ev < 0:
            if last_valid_ev < 0:
                streak += 1
                current_state = PERSISTENCE_3PLUS if streak >= 3 else PERSISTENCE_2
            else:
                current_state = WATCH_NEGATIVE
                streak = 1
        elif last_valid_ev < 0:
            current_state = RECOVERING
            saw_recovering = True
            streak = 0
        else:
            if last_core in {RECOVERING, HEALTHY_AFTER_RECOVERY} or saw_recovering:
                current_state = HEALTHY_AFTER_RECOVERY
            else:
                current_state = HEALTHY
            streak = 0
        last_valid_ev = ev
        last_core = current_state
        current_streak = streak
    return current_state, current_streak


def _velocity(prev: dict[str, Any] | None, now: dict[str, Any] | None) -> float | None:
    if prev is None or now is None:
        return None
    ev_a = _valid_ev(prev)
    ev_b = _valid_ev(now)
    dt = clock_minutes_between(prev, now)
    if ev_a is None or ev_b is None or dt in (None, 0):
        return None
    return (ev_b - ev_a) / dt


def derive_downfall_state(history_up_to_t: list[dict[str, Any]]) -> dict[str, Any]:
    """PIT state from rows <= t. Outcome keys are forbidden."""
    core, streak = walk_core(history_up_to_t)
    now = history_up_to_t[-1] if history_up_to_t else None
    valids = [r for r in history_up_to_t if _valid_ev(r) is not None]
    prev_valid = valids[-2] if len(valids) >= 2 else None
    ev_now = _valid_ev(now)
    ev_prev = _valid_ev(prev_valid)
    ev_entry = None if now is None else as_float(now.get("ev_at_entry"))
    if ev_entry is None and valids:
        ev_entry = _valid_ev(valids[0])
    vel = _velocity(prev_valid, now)
    acc = None
    if len(valids) >= 3:
        v0 = _velocity(valids[-3], valids[-2])
        v1 = _velocity(valids[-2], valids[-1])
        dt = clock_minutes_between(valids[-2], valids[-1])
        if v0 is not None and v1 is not None and dt not in (None, 0):
            acc = (v1 - v0) / dt
    lo = None if now is None else as_float(now.get("ci_lower_cents"))
    hi = None if now is None else as_float(now.get("ci_upper_cents"))
    home = None if now is None else now.get("home_score")
    away = None if now is None else now.get("away_score")
    score = None
    score_diff = None
    if home not in (None, "") and away not in (None, ""):
        try:
            score = f"{int(home)}-{int(away)}"
            score_diff = int(home) - int(away)
        except (TypeError, ValueError):
            score = None
            score_diff = None
    payload = {
        "core_state": core,
        "negative_streak_length": streak,
        "CI_state": ci_state(lo, hi),
        "support_state": support_state(None if now is None else now.get("support_status")),
        "EV_now": ev_now,
        "EV_previous": ev_prev,
        "EV_entry": ev_entry,
        "EV_change_from_previous": None if ev_now is None or ev_prev is None else ev_now - ev_prev,
        "EV_change_from_entry": None if ev_now is None or ev_entry is None else ev_now - ev_entry,
        "EV_velocity": vel,
        "EV_acceleration": acc,
        "price": None if now is None else now.get("current_price_cents"),
        "price_travel": None if now is None else as_float(now.get("price_travel")),
        "score": score,
        "score_diff": score_diff,
        "score_travel": None if now is None else as_float(now.get("score_travel")),
        "score_diff_travel": None if now is None else as_float(now.get("score_diff_travel")),
        "time_since_entry": None if now is None else as_float(now.get("time_since_entry")),
        "game_time_remaining": None
        if now is None
        else game_seconds_remaining(now.get("period"), now.get("game_clock_remaining")),
        "ESS": None if now is None else as_float(now.get("effective_sample_size")),
        "effective_neighbors": None if now is None else as_float(now.get("effective_neighbors")),
        "mean_distance": None if now is None else as_float(now.get("mean_distance")),
        "median_distance": None if now is None else as_float(now.get("median_distance")),
        "feature_coverage": None if now is None else as_float(now.get("feature_coverage")),
        "availability_status": None if now is None else (now.get("availability_status") or None),
        "CI_lower": lo,
        "CI_upper": hi,
    }
    leaked = set(payload) & FORBIDDEN_PIT
    if leaked:
        raise RuntimeError(f"downfall PIT leaked {sorted(leaked)}")
    return payload
