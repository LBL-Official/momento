"""Single feature builder. Historical and query RawState share this function."""

from __future__ import annotations

from typing import Any

from roller.austin.clock import time_since_entry_seconds
from roller.austin.raw_state import Lookback, PathPoint, RawState

UNAVAILABLE = "UNAVAILABLE"
MISSING = "MISSING"
NOT_APPLICABLE = "NOT_APPLICABLE"


def _num(*values: object) -> float | None:
    for value in values:
        if value is None:
            continue
        try:
            return float(value)
        except (TypeError, ValueError):
            continue
    return None


def _status(value: float | None, *, reason: str = UNAVAILABLE) -> dict[str, Any]:
    if value is None:
        return {"value": None, "status": reason}
    return {"value": float(value), "status": "VALUE"}


def _favorite_pair(
    side: str,
    home: float | None,
    away: float | None,
) -> tuple[float | None, float | None]:
    if home is None or away is None:
        return None, None
    if side == "home":
        return home, away
    return away, home


def _lookback(looks: list[Lookback], seconds: int) -> Lookback | None:
    for row in looks:
        if int(row.seconds_ago) == int(seconds):
            return row
    return None


def _price_at_offset(path: list[PathPoint], now_sec: int, bars: int) -> float | None:
    if not path:
        return None
    target = now_sec - 60 * int(bars)
    prior = [p for p in path if p.t_sec <= target and p.price_cents is not None]
    if not prior:
        return None
    return float(prior[-1].price_cents)


def _reversals(path: list[PathPoint]) -> float | None:
    prices = [float(p.price_cents) for p in path if p.price_cents is not None]
    if len(prices) < 3:
        return None
    count = 0
    prev = 0.0
    for i in range(1, len(prices)):
        delta = prices[i] - prices[i - 1]
        sign = 1.0 if delta > 0 else (-1.0 if delta < 0 else 0.0)
        if sign != 0 and prev != 0 and sign != prev:
            count += 1
        if sign != 0:
            prev = sign
    return float(count)


def _slope(xs: list[float], ys: list[float]) -> float | None:
    n = min(len(xs), len(ys))
    if n < 2:
        return None
    x = xs[:n]
    y = ys[:n]
    mx = sum(x) / n
    my = sum(y) / n
    den = sum((v - mx) ** 2 for v in x)
    if den <= 1e-12:
        return None
    return sum((x[i] - mx) * (y[i] - my) for i in range(n)) / den


def build_feature_vector(state: RawState) -> dict[str, Any]:
    """Canonical feature vector. Never uses settlement or post-t outcomes."""
    pre80 = state.query_mode == "PRE_80" or state.entry_price_cents is None
    entry_reason = NOT_APPLICABLE if pre80 else UNAVAILABLE
    entry = None if pre80 else _num(state.entry_price_cents)
    current = _num(state.current_price_cents)
    travel = None if entry is None or current is None else current - entry
    home_e = _num(state.home_score_entry)
    away_e = _num(state.away_score_entry)
    home_c = _num(state.home_score_current)
    away_c = _num(state.away_score_current)
    fav_e, opp_e = _favorite_pair(state.side, home_e, away_e)
    fav_c, opp_c = _favorite_pair(state.side, home_c, away_c)
    score_e = None if home_e is None or away_e is None else home_e + away_e
    score_c = None if home_c is None or away_c is None else home_c + away_c
    diff_e = None if fav_e is None or opp_e is None else fav_e - opp_e
    diff_c = None if fav_c is None or opp_c is None else fav_c - opp_c
    score_travel = None if score_e is None or score_c is None else score_c - score_e
    diff_travel = None if diff_e is None or diff_c is None else diff_c - diff_e
    clock_sport = str(getattr(state, "clock_sport", None) or "").upper()
    if clock_sport == "NCAAB" and state.time_since_entry_sec is not None:
        t_sec = int(state.time_since_entry_sec)
    else:
        t_sec = time_since_entry_seconds(
            entry_quarter=state.entry_quarter,
            entry_seconds_remaining=state.entry_seconds_remaining,
            current_quarter=state.current_quarter,
            current_seconds_remaining=state.current_seconds_remaining,
            wall_seconds=None if state.time_since_entry_sec is None else float(state.time_since_entry_sec),
        )
    if t_sec is None and state.time_since_entry_sec is not None:
        t_sec = int(state.time_since_entry_sec)
    minutes = None if t_sec is None or t_sec <= 0 else t_sec / 60.0
    sec_left = _num(state.current_seconds_remaining)
    quarter = _num(state.current_quarter)
    period_len = 720.0
    if clock_sport == "NCAAB":
        period_len = 300.0 if quarter is not None and int(quarter) >= 3 else 1200.0
    q_progress = None if sec_left is None else max(0.0, min(1.0, 1.0 - (sec_left / period_len)))
    elapsed = None
    if quarter is not None and sec_left is not None:
        elapsed = (int(quarter) - 1) * int(period_len) + (int(period_len) - min(int(sec_left), int(period_len)))
    game_norm = None if elapsed is None else elapsed / (2 * 1200.0 if clock_sport == "NCAAB" else 2880.0)
    time_bucket = None
    if q_progress is not None:
        time_bucket = 0.0 if q_progress < 1.0 / 3.0 else (1.0 if q_progress < 2.0 / 3.0 else 2.0)

    path = list(state.path_to_t)
    prices = [float(p.price_cents) for p in path if p.price_cents is not None]
    if not prices:
        prices = [p for p in (entry, current) if p is not None]
    max_px = max(prices) if prices else None
    min_px = min(prices) if prices else None
    mfe = None if entry is None or max_px is None else max(0.0, max_px - entry)
    mae = None if entry is None or min_px is None else max(0.0, entry - min_px)
    tmax_f = None
    tmax_a = None
    if path and max_px is not None and min_px is not None:
        for p in path:
            if p.price_cents is not None and float(p.price_cents) == max_px:
                tmax_f = float(p.t_sec)
                break
        for p in path:
            if p.price_cents is not None and float(p.price_cents) == min_px:
                tmax_a = float(p.t_sec)
                break

    now_sec = 0 if t_sec is None else int(t_sec)
    vel: dict[int, float | None] = {}
    for bars in (1, 2, 3, 5, 10):
        prior = _price_at_offset(path, now_sec, bars)
        if prior is None and state.lookbacks:
            lb = _lookback(state.lookbacks, 60 * bars)
            if lb is not None and lb.price_cents is not None:
                prior = float(lb.price_cents)
        vel[bars] = None if prior is None or current is None else current - prior
    accel = None
    if vel[1] is not None and current is not None:
        prior2 = _price_at_offset(path, now_sec, 2)
        if prior2 is None:
            lb2 = _lookback(state.lookbacks, 120)
            prior2 = None if lb2 is None or lb2.price_cents is None else float(lb2.price_cents)
        if prior2 is not None and vel[1] is not None:
            prev_v = (current - vel[1]) - prior2
            accel = vel[1] - prev_v
    direction = None if travel is None else (0.0 if travel == 0 else (1.0 if travel > 0 else -1.0))
    reversals = _reversals(path)

    path_reason = UNAVAILABLE if state.is_query and not state.lookbacks and not path else MISSING
    vel_reason = "UNAVAILABLE — QUERY PATH NOT PROVIDED" if state.is_query and not state.lookbacks and not path else UNAVAILABLE

    def _recent_points(seconds: int) -> float | None:
        lb = _lookback(state.lookbacks, seconds)
        if lb is not None and lb.home_score is not None and lb.away_score is not None and score_c is not None:
            return score_c - (float(lb.home_score) + float(lb.away_score))
        if not path or score_c is None:
            return None
        target = now_sec - seconds
        prior = [p for p in path if p.t_sec <= target and p.home_score is not None and p.away_score is not None]
        if not prior:
            return None
        last = prior[-1]
        return score_c - (float(last.home_score) + float(last.away_score))

    def _recent_diff(seconds: int) -> float | None:
        if diff_c is None:
            return None
        lb = _lookback(state.lookbacks, seconds)
        if lb is not None and lb.home_score is not None and lb.away_score is not None:
            fav, opp = _favorite_pair(state.side, float(lb.home_score), float(lb.away_score))
            if fav is None or opp is None:
                return None
            return diff_c - (fav - opp)
        prior = [p for p in path if p.t_sec <= now_sec - seconds and p.home_score is not None and p.away_score is not None]
        if not prior:
            return None
        last = prior[-1]
        fav, opp = _favorite_pair(state.side, float(last.home_score), float(last.away_score))
        if fav is None or opp is None:
            return None
        return diff_c - (fav - opp)

    xs: list[float] = []
    ys: list[float] = []
    for p in path:
        if p.home_score is None or p.away_score is None:
            continue
        fav, opp = _favorite_pair(state.side, float(p.home_score), float(p.away_score))
        if fav is None or opp is None:
            continue
        xs.append(float(p.t_sec))
        ys.append(fav - opp)
    slope = _slope(xs, ys)
    accel_s = None
    if len(xs) >= 4:
        mid = len(xs) // 2
        s1 = _slope(xs[: mid + 1], ys[: mid + 1])
        s2 = _slope(xs[mid:], ys[mid:])
        if s1 is not None and s2 is not None:
            accel_s = s2 - s1
    leads = 0.0
    ties = 0.0
    if ys:
        prev = ys[0]
        for val in ys[1:]:
            if val == 0:
                ties += 1
            if (prev > 0 and val < 0) or (prev < 0 and val > 0):
                leads += 1
            prev = val
    largest_lead = max(ys) if ys else diff_c
    largest_def = min(ys) if ys else diff_c
    vs_max = None if diff_c is None or largest_lead is None else diff_c - largest_lead
    lead_growth = None if diff_c is None or diff_e is None else max(0.0, diff_c - diff_e)
    lead_shrink = None if diff_c is None or diff_e is None else max(0.0, diff_e - diff_c)

    values: dict[str, dict[str, Any]] = {
        "entry_price": _status(None if entry is None else entry / 100.0, reason=entry_reason),
        "entry_price_decimal": _status(None if entry is None else entry / 100.0, reason=entry_reason),
        "entry_price_cents": _status(entry, reason=entry_reason),
        "distance_from_50": _status(None if entry is None else entry - 50.0, reason=entry_reason),
        "distance_from_50_abs": _status(None if entry is None else abs(entry - 50.0), reason=entry_reason),
        "distance_from_80": _status(None if entry is None else entry - 80.0, reason=entry_reason),
        "entry_price_distance_from_trigger": _status(None if entry is None else entry - 80.0, reason=entry_reason),
        "current_price_cents": _status(current),
        "price_travel": _status(travel, reason=entry_reason),
        "price_travel_pct": _status(None if entry in (None, 0) or travel is None else travel / entry, reason=entry_reason),
        "max_price_after_entry": _status(max_px, reason=path_reason if max_px is None else "VALUE"),
        "min_price_after_entry": _status(min_px, reason=path_reason if min_px is None else "VALUE"),
        "max_favorable_move": _status(mfe, reason=entry_reason if entry is None else path_reason),
        "max_adverse_move": _status(mae, reason=entry_reason if entry is None else path_reason),
        "max_favorable_move_pct": _status(
            None if entry in (None, 0) or mfe is None else mfe / entry,
            reason=entry_reason if entry is None else path_reason,
        ),
        "max_adverse_move_pct": _status(
            None if entry in (None, 0) or mae is None else mae / entry,
            reason=entry_reason if entry is None else path_reason,
        ),
        "path_range": _status(None if max_px is None or min_px is None else max_px - min_px, reason=path_reason),
        "time_to_max_favorable_move": _status(tmax_f, reason=path_reason),
        "time_to_max_adverse_move": _status(tmax_a, reason=path_reason),
        "price_velocity_1": _status(vel[1], reason=vel_reason),
        "price_velocity_2": _status(vel[2], reason=vel_reason),
        "price_velocity_3": _status(vel[3], reason=vel_reason),
        "price_velocity_5": _status(vel[5], reason=vel_reason),
        "price_velocity_10": _status(vel[10], reason=vel_reason),
        "price_acceleration": _status(accel, reason=vel_reason),
        "price_direction": _status(direction),
        "price_reversal_count": _status(reversals, reason=path_reason),
        "home_score": _status(home_c),
        "away_score": _status(away_c),
        "score": _status(score_c),
        "score_differential": _status(diff_c),
        "favorite_score": _status(fav_c),
        "opponent_score": _status(opp_c),
        "score_travel": _status(score_travel),
        "score_differential_travel": _status(diff_travel),
        "points_per_minute": _status(None if minutes is None or score_travel is None else score_travel / minutes),
        "favorite_points_per_minute": _status(
            None if minutes is None or fav_c is None or fav_e is None else (fav_c - fav_e) / minutes
        ),
        "opponent_points_per_minute": _status(
            None if minutes is None or opp_c is None or opp_e is None else (opp_c - opp_e) / minutes
        ),
        "score_diff_velocity": _status(None if minutes is None or diff_travel is None else diff_travel / minutes),
        "points_last_30s": _status(_recent_points(30), reason=vel_reason),
        "points_last_60s": _status(_recent_points(60), reason=vel_reason),
        "points_last_120s": _status(_recent_points(120), reason=vel_reason),
        "score_diff_change_last_30s": _status(_recent_diff(30), reason=vel_reason),
        "score_diff_change_last_60s": _status(_recent_diff(60), reason=vel_reason),
        "score_diff_change_last_120s": _status(_recent_diff(120), reason=vel_reason),
        "score_diff_slope": _status(slope, reason=vel_reason),
        "score_diff_acceleration": _status(accel_s, reason=vel_reason),
        "lead_changes": _status(leads if ys else None, reason=vel_reason),
        "tie_count": _status(ties if ys else None, reason=vel_reason),
        "lead_growth": _status(lead_growth),
        "lead_shrinkage": _status(lead_shrink),
        "largest_lead_since_entry": _status(largest_lead, reason=vel_reason if not ys else "VALUE"),
        "largest_deficit_since_entry": _status(largest_def, reason=vel_reason if not ys else "VALUE"),
        "current_lead_vs_max_lead": _status(vs_max),
        "quarter": _status(quarter),
        "seconds_remaining": _status(sec_left),
        "minutes_remaining": _status(None if sec_left is None else sec_left / 60.0),
        "normalized_quarter_time": _status(q_progress),
        "normalized_game_time": _status(game_norm),
        "time_since_entry": _status(None if pre80 or t_sec is None else float(t_sec), reason=entry_reason),
        "quarter_progress": _status(q_progress),
        "time_bucket": _status(time_bucket),
        "price_x_score_diff": _status(None if diff_c is None or current is None else current * diff_c),
        "price_x_time": _status(None if t_sec is None or current is None else current * float(t_sec)),
        "score_diff_x_time": _status(None if diff_c is None or t_sec is None else diff_c * float(t_sec)),
        "score_travel_x_time": _status(None if score_travel is None or t_sec is None else score_travel * float(t_sec)),
        "price_travel_x_score_diff_travel": _status(
            None if diff_travel is None or travel is None else travel * diff_travel,
            reason=entry_reason,
        ),
        "entry_price_x_score_diff": _status(
            None if diff_c is None or entry is None else entry * diff_c,
            reason=entry_reason,
        ),
        "entry_price_x_time": _status(None if t_sec is None or entry is None else entry * float(t_sec), reason=entry_reason),
    }
    missing = [name for name, cell in values.items() if cell["status"] != "VALUE"]
    present = len(values) - len(missing)
    return {
        "features": values,
        "numeric": {name: cell["value"] for name, cell in values.items()},
        "feature_names": list(values),
        "missing_features": missing,
        "feature_coverage": present / len(values) if values else 0.0,
        "is_query": bool(state.is_query),
        "trade_id": state.trade_id,
        "query_mode": state.query_mode,
        "entry_source": state.entry_source,
        "path_mode": "PATH_ENRICHED" if path or state.lookbacks else "POINT_IN_TIME",
    }


def numeric_row(bundle: dict[str, Any], names: list[str]) -> dict[str, float | None]:
    src = bundle.get("numeric") or {}
    return {name: src.get(name) for name in names}


def assert_same_schema(historical: dict[str, Any], query: dict[str, Any]) -> None:
    from roller.austin.errors import AustinError

    left = list(historical.get("feature_names") or [])
    right = list(query.get("feature_names") or [])
    if left != right:
        raise AustinError("FEATURE_SCHEMA_MISMATCH", "historical_feature_names != query_feature_names")
