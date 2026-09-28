"""Trajectory after first negative. No invented checkpoints."""

from __future__ import annotations

from typing import Any

from roller.austin.experiments.persistence.util import as_float, clock_minutes_between, elapsed, valid_ev


def ev_area_below_zero(points: list[dict[str, Any]]) -> float | None:
    """Trapezoid of negative EV on consecutive valid PRIMARY points.

    dt is NCAAB game-clock minutes between consecutive valid states.
    If both EV < 0: 0.5 * (|ev_i| + |ev_{i+1}|) * dt.
    If the segment crosses zero, only the negative portion of the linear
    interpolant is counted. Gaps with dt <= 0 are skipped. Not a policy.
    """
    valid = [p for p in points if p.get("EV") is not None]
    if len(valid) < 2:
        return None
    area = 0.0
    used = False
    for left, right in zip(valid, valid[1:]):
        dt = clock_minutes_between(
            {"period": left.get("period"), "game_clock_remaining": left.get("clock")},
            {"period": right.get("period"), "game_clock_remaining": right.get("clock")},
        )
        if dt is None or dt <= 0:
            continue
        a = float(left["EV"])
        b = float(right["EV"])
        used = True
        if a < 0 and b < 0:
            area += 0.5 * (abs(a) + abs(b)) * dt
        elif a < 0 and b >= 0:
            denom = b - a
            if denom != 0:
                frac = max(0.0, min(1.0, -a / denom))
                area += 0.5 * abs(a) * frac * dt
        elif a >= 0 and b < 0:
            denom = b - a
            if denom != 0:
                frac = max(0.0, min(1.0, 1.0 - (-a / denom)))
                area += 0.5 * abs(b) * frac * dt
    return area if used else None


def build_trajectory(event: dict[str, Any]) -> list[dict[str, Any]]:
    first = event["_first"]
    later_valid = event["_later_valid"]
    states = [first, *later_valid]
    rows = []
    prev_ev = None
    prev_vel = None
    prev_row = None
    price0 = first.get("current_price_cents")
    score0 = None
    if first.get("home_score") is not None and first.get("away_score") is not None:
        score0 = int(first["home_score"]) - int(first["away_score"])
    for step, row in enumerate(states):
        ev = as_float(row.get("conditional_ev_cents"))
        price = row.get("current_price_cents")
        score = None
        if row.get("home_score") is not None and row.get("away_score") is not None:
            score = int(row["home_score"]) - int(row["away_score"])
        dt = None if prev_row is None else clock_minutes_between(prev_row, row)
        vel = None
        if ev is not None and prev_ev is not None and dt not in (None, 0):
            vel = (ev - prev_ev) / dt
        acc = None
        if vel is not None and prev_vel is not None and dt not in (None, 0):
            acc = (vel - prev_vel) / dt
        depth = None if ev is None else abs(min(ev, 0.0))
        rows.append(
            {
                "trade_id": event["trade_id"],
                "internal_game_id": event.get("internal_game_id"),
                "source_experiment_id": event["source_experiment_id"],
                "step_from_first_negative": step,
                "step_from_t0": step,
                "period": row.get("period"),
                "clock": row.get("game_clock_remaining"),
                "timestamp": row.get("timestamp_utc"),
                "EV": ev,
                "EV_DEPTH": depth,
                "EV_VELOCITY": vel,
                "EV_ACCELERATION": acc,
                "CI_lower": as_float(row.get("ci_lower_cents")),
                "CI_upper": as_float(row.get("ci_upper_cents")),
                "EV_change_from_t0": None if ev is None or event["first_negative_EV"] is None else ev - event["first_negative_EV"],
                "EV_change_from_previous": None if ev is None or prev_ev is None else ev - prev_ev,
                "price": price,
                "price_change_from_t0": None if price is None or price0 is None else int(price) - int(price0),
                "score_diff": score,
                "score_diff_change_from_t0": None if score is None or score0 is None else score - score0,
                "time_since_first_negative_game_clock": 0.0 if step == 0 else clock_minutes_between(first, row),
                "game_clock_minutes_from_t0": 0.0 if step == 0 else clock_minutes_between(first, row),
                "ESS": as_float(row.get("effective_sample_size")),
                "effective_neighbors": as_float(row.get("effective_neighbors")),
                "mean_distance": as_float(row.get("mean_distance")),
                "median_distance": as_float(row.get("median_distance")),
                "feature_coverage": as_float(row.get("feature_coverage")),
                "support_status": row.get("support_status"),
                "negative_ev_class": event["negative_ev_class"],
            }
        )
        prev_ev = ev
        prev_vel = vel
        prev_row = row
    return rows


def persistence_duration(event: dict[str, Any], trajectory: list[dict[str, Any]]) -> dict[str, Any]:
    later_valid = event["_later_valid"]
    first = event["_first"]
    consecutive = 0
    for row in [first, *later_valid]:
        ev = as_float(row.get("conditional_ev_cents"))
        if ev is None or ev >= 0:
            break
        consecutive += 1
    recover = next((r for r in later_valid if as_float(r.get("conditional_ev_cents")) is not None and float(r["conditional_ev_cents"]) >= 0), None)
    later_evs = [float(r["conditional_ev_cents"]) for r in later_valid]
    minutes_to_recovery = clock_minutes_between(first, recover) if recover is not None else None
    last = later_valid[-1] if later_valid else None
    minutes_to_end = clock_minutes_between(first, last) if last is not None else None
    return {
        "trade_id": event["trade_id"],
        "source_experiment_id": event["source_experiment_id"],
        "negative_ev_class": event["negative_ev_class"],
        "N_VALID_STATES_AFTER_FIRST_NEGATIVE": len(later_valid),
        "N_CONSECUTIVE_NEGATIVE_FROM_T0": consecutive,
        "GAME_CLOCK_MINUTES_NEGATIVE_BEFORE_RECOVERY": minutes_to_recovery,
        "GAME_CLOCK_MINUTES_NEGATIVE_BEFORE_SETTLEMENT": minutes_to_end,
        "FIRST_RECOVERY_TO_EV_GE_0_timestamp": None if recover is None else recover.get("timestamp_utc"),
        "FIRST_RECOVERY_TO_EV_GE_0_period": None if recover is None else recover.get("period"),
        "FIRST_RECOVERY_TO_EV_GE_0_clock": None if recover is None else recover.get("game_clock_remaining"),
        "MIN_EV_AFTER_FIRST_NEGATIVE": None if not later_evs else min(later_evs),
        "MAX_EV_AFTER_FIRST_NEGATIVE": None if not later_evs else max(later_evs),
        "EV_RANGE_AFTER_FIRST_NEGATIVE": None if not later_evs else max(later_evs) - min(later_evs),
        "EV_AREA_BELOW_ZERO": ev_area_below_zero(trajectory),
        "EV_AREA_FORMULA": (
            "trapezoid of negative EV on consecutive valid PRIMARY points; "
            "dt = NCAAB game-clock minutes; zero-crossing uses the negative linear portion; "
            "gaps with dt<=0 skipped; not a policy"
        ),
    }


TRAJECTORY_FIELDS = [
    "trade_id",
    "internal_game_id",
    "source_experiment_id",
    "step_from_first_negative",
    "step_from_t0",
    "period",
    "clock",
    "timestamp",
    "EV",
    "EV_DEPTH",
    "EV_VELOCITY",
    "EV_ACCELERATION",
    "CI_lower",
    "CI_upper",
    "EV_change_from_t0",
    "EV_change_from_previous",
    "price",
    "price_change_from_t0",
    "score_diff",
    "score_diff_change_from_t0",
    "time_since_first_negative_game_clock",
    "game_clock_minutes_from_t0",
    "ESS",
    "effective_neighbors",
    "mean_distance",
    "median_distance",
    "feature_coverage",
    "support_status",
]

DURATION_FIELDS = [
    "trade_id",
    "source_experiment_id",
    "negative_ev_class",
    "N_VALID_STATES_AFTER_FIRST_NEGATIVE",
    "N_CONSECUTIVE_NEGATIVE_FROM_T0",
    "GAME_CLOCK_MINUTES_NEGATIVE_BEFORE_RECOVERY",
    "GAME_CLOCK_MINUTES_NEGATIVE_BEFORE_SETTLEMENT",
    "FIRST_RECOVERY_TO_EV_GE_0_timestamp",
    "FIRST_RECOVERY_TO_EV_GE_0_period",
    "FIRST_RECOVERY_TO_EV_GE_0_clock",
    "MIN_EV_AFTER_FIRST_NEGATIVE",
    "MAX_EV_AFTER_FIRST_NEGATIVE",
    "EV_RANGE_AFTER_FIRST_NEGATIVE",
    "EV_AREA_BELOW_ZERO",
    "EV_AREA_FORMULA",
]


def unused_elapsed(row: dict[str, Any]) -> int | None:
    return elapsed(row.get("period"), row.get("game_clock_remaining"))
