"""Score level, path, and SCORE_PATH_VOLATILITY_V1. Missing vol is UNAVAILABLE, not 0."""

from __future__ import annotations

import statistics
from typing import Any

from roller.base_terminal_efficiency.models import OBSERVED, UNALIGNED, UNAVAILABLE
from roller.base_terminal_efficiency.pit import filter_visible, parse_ts
from roller.base_terminal_efficiency.versions import SCORE_VOL_MIN_INCREMENTS
from roller.state.clock import clock_remaining_seconds, elapsed_game_seconds
from roller.state.clock_snap import snap_events


def _int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def points_for_side(home: int | None, away: int | None, team_side: str | None) -> tuple[int | None, int | None]:
    if home is None or away is None:
        return None, None
    if team_side == "away":
        return away, home
    return home, away


def scoring_increments(events: list[dict[str, Any]], team_side: str | None) -> list[dict[str, int]]:
    """Events that change team or opponent score, in order. No interpolation."""
    out: list[dict[str, int]] = []
    prev_t: int | None = None
    prev_o: int | None = None
    for ev in events:
        team, opp = points_for_side(_int(ev.get("home_score")), _int(ev.get("away_score")), team_side)
        if team is None or opp is None:
            continue
        if prev_t is None:
            if team != 0 or opp != 0:
                out.append(
                    {
                        "team": team,
                        "opponent": opp,
                        "d_team": team,
                        "d_opp": opp,
                        "d_total": team + opp,
                        "d_diff": team - opp,
                    }
                )
            elif team == 0 and opp == 0:
                pass
            prev_t, prev_o = team, opp
            continue
        if team == prev_t and opp == prev_o:
            continue
        out.append(
            {
                "team": team,
                "opponent": opp,
                "d_team": team - prev_t,
                "d_opp": opp - prev_o,
                "d_total": (team + opp) - (prev_t + prev_o),
                "d_diff": (team - opp) - (prev_t - prev_o),
            }
        )
        prev_t, prev_o = team, opp
    return out


def sample_stdev(values: list[int], *, min_n: int) -> float | None:
    if len(values) < min_n:
        return None
    return float(statistics.stdev(values))


def score_state(
    pbp_events: list[dict[str, Any]],
    observation_ts: Any,
    *,
    team_side: str | None,
    sport: str = "NBA",
) -> dict[str, Any]:
    from roller.research_query.sport_family import is_baseball, is_tennis

    if is_baseball(sport):
        from roller.mlb.snap import pit_visible, snap_mlb

        obs_ts = parse_ts(observation_ts)
        # MLB PIT: event_timestamp <= entry_ts. Do not use basketball available_at < t.
        visible = pit_visible(pbp_events, obs_ts) if obs_ts is not None else []
        snap = (
            snap_mlb(visible, obs_ts, team_side=team_side)
            if visible and obs_ts is not None
            else {
                "status": UNALIGNED,
                "slice": UNALIGNED,
                "period": None,
                "clock": None,
                "period_remaining_s": None,
                "elapsed_game_seconds": None,
            }
        )
    elif is_tennis(sport):
        from roller.tennis.snap import NO_POINT_DATA, snap_tennis

        obs_ts = parse_ts(observation_ts)
        snap = (
            snap_tennis(pbp_events, obs_ts, team_side=team_side)
            if obs_ts is not None
            else {
                "status": NO_POINT_DATA,
                "slice": UNALIGNED,
                "period": None,
                "clock": None,
                "period_remaining_s": None,
                "elapsed_game_seconds": None,
                "point_snapshot_available": False,
            }
        )
        tennis_real = snap.get("status") == "REAL" and bool(snap.get("point_snapshot_available"))
        alignment = "aligned" if tennis_real else UNALIGNED
        return {
            "period": None,
            "game_clock": None,
            "remaining_game_time": None,
            "elapsed_game_time": None,
            "alignment_status": alignment,
            "team_points": None,
            "opponent_points": None,
            "total_points": None,
            "point_differential": None,
            "point_differential_abs_e0": None,
            "point_differential_sign": None,
            "score_path_team": (),
            "score_path_opponent": (),
            "score_change_from_start": None,
            "opponent_score_change_from_start": None,
            "total_score_change_from_start": None,
            "differential_change_from_start": None,
            "team_score_volatility": None,
            "opponent_score_volatility": None,
            "total_score_volatility": None,
            "differential_volatility": None,
            "score_status": OBSERVED if tennis_real else UNALIGNED,
        }
    else:
        visible = filter_visible(pbp_events, observation_ts)
        snap = snap_events(visible, parse_ts(observation_ts), sport=sport) if visible else {
            "status": UNALIGNED,
            "slice": UNALIGNED,
            "period": None,
            "clock": None,
            "period_remaining_s": None,
            "elapsed_game_seconds": None,
        }
    alignment = UNALIGNED if snap.get("status") == UNALIGNED or snap.get("slice") == UNALIGNED else "aligned"
    incs = scoring_increments(visible, team_side)
    if incs:
        path_t = (0, *tuple(x["team"] for x in incs))
        path_o = (0, *tuple(x["opponent"] for x in incs))
    else:
        path_t, path_o = (), ()
    team_pts = opp_pts = None
    if snap.get("status") != UNALIGNED and visible:
        chosen = None
        # snap does not return scores; recover from last visible event used by snap
        ev_ts = snap.get("event_timestamp")
        ev_n = snap.get("event_number")
        for ev in visible:
            if ev_n is not None and _int(ev.get("event_number")) == _int(ev_n):
                chosen = ev
                break
            if ev_ts and str(ev.get("event_timestamp") or ev.get("event_time") or "") == str(ev_ts):
                chosen = ev
        if chosen is None and visible:
            chosen = visible[-1]
        if chosen is not None:
            team_pts, opp_pts = points_for_side(
                _int(chosen.get("home_score") if chosen.get("home_score") not in (None, "") else snap.get("home_score")),
                _int(chosen.get("away_score") if chosen.get("away_score") not in (None, "") else snap.get("away_score")),
                team_side,
            )
        elif snap.get("home_score") is not None and snap.get("away_score") is not None:
            team_pts, opp_pts = points_for_side(
                _int(snap.get("home_score")),
                _int(snap.get("away_score")),
                team_side,
            )
    if team_pts is None and path_t:
        team_pts, opp_pts = path_t[-1], path_o[-1]
        alignment = "aligned"
    total = (team_pts + opp_pts) if team_pts is not None and opp_pts is not None else None
    diff = (team_pts - opp_pts) if team_pts is not None and opp_pts is not None else None
    score_ok = team_pts is not None and opp_pts is not None
    rem = snap.get("period_remaining_s")
    if rem is None:
        rem = clock_remaining_seconds(snap.get("clock"))
    elapsed = snap.get("elapsed_game_seconds")
    if elapsed is None:
        elapsed = elapsed_game_seconds(snap.get("period"), snap.get("clock"), sport=sport)
    return {
        "period": snap.get("period"),
        "game_clock": snap.get("clock"),
        "remaining_game_time": int(rem) if rem is not None else None,
        "elapsed_game_time": int(elapsed) if elapsed is not None else None,
        "alignment_status": alignment if score_ok else UNALIGNED,
        "team_points": team_pts,
        "opponent_points": opp_pts,
        "total_points": total,
        "point_differential": diff,
        "point_differential_abs_e0": abs(diff) if diff is not None else None,
        "point_differential_sign": (0 if diff == 0 else (1 if diff and diff > 0 else -1)) if diff is not None else None,
        "score_path_team": path_t,
        "score_path_opponent": path_o,
        "score_change_from_start": (path_t[-1] - 0) if path_t else None,
        "opponent_score_change_from_start": (path_o[-1] - 0) if path_o else None,
        "total_score_change_from_start": (path_t[-1] + path_o[-1]) if path_t and path_o else None,
        "differential_change_from_start": (
            (path_t[-1] - path_o[-1]) - (path_t[0] - path_o[0]) if len(path_t) >= 1 else None
        ),
        "team_score_volatility": sample_stdev([x["d_team"] for x in incs], min_n=SCORE_VOL_MIN_INCREMENTS),
        "opponent_score_volatility": sample_stdev([x["d_opp"] for x in incs], min_n=SCORE_VOL_MIN_INCREMENTS),
        "total_score_volatility": sample_stdev([x["d_total"] for x in incs], min_n=SCORE_VOL_MIN_INCREMENTS),
        "differential_volatility": sample_stdev([x["d_diff"] for x in incs], min_n=SCORE_VOL_MIN_INCREMENTS),
        "score_status": OBSERVED if score_ok else (UNALIGNED if alignment == UNALIGNED else UNAVAILABLE),
    }
