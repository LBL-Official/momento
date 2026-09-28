"""MLB PIT snap: last PBP row with event_timestamp <= market_entry_ts.

Never snap forward. Missing → UNALIGNED. Do not run basketball clock math.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from roller.mlb.state import (
    batting_team,
    count_display,
    count_leverage,
    inning_slice,
    live_balls,
    live_outs,
    live_strikes,
    normalize_half,
    runner_category,
    runner_flags,
    yes_batting,
    yes_pitching,
)
from roller.timeutil import parse_utc


def _int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _event_ts(ev: dict[str, Any]) -> datetime | None:
    return parse_utc(ev.get("event_timestamp") or ev.get("event_time") or ev.get("time_actual"))


def pit_visible(events: list[dict[str, Any]], snap_ts: datetime) -> list[dict[str, Any]]:
    """Events with event_timestamp <= snap_ts. Equality is visible (MLB PIT).

    Basketball I(t) stays available_at < t. Do not reuse that filter here.
    """
    out: list[dict[str, Any]] = []
    for ev in events:
        clock = _event_ts(ev)
        if clock is None or clock > snap_ts:
            continue
        out.append(ev)
    return out


def choose_pit_row(events: list[dict[str, Any]], snap_ts: datetime) -> dict[str, Any] | None:
    chosen: dict[str, Any] | None = None
    chosen_ts: datetime | None = None
    for ev in events:
        clock = _event_ts(ev)
        if clock is None or clock > snap_ts:
            continue
        if chosen is None or chosen_ts is None or clock > chosen_ts:
            chosen = ev
            chosen_ts = clock
            continue
        if clock == chosen_ts and int(ev.get("event_number") or 0) > int(chosen.get("event_number") or 0):
            chosen = ev
    return chosen


def snap_mlb(
    events: list[dict[str, Any]],
    snap_ts: datetime,
    *,
    team_side: str | None = None,
) -> dict[str, Any]:
    """Last event with event_timestamp <= snap_ts. Fail closed if none."""
    unaligned = {
        "status": "UNALIGNED",
        "slice": "UNALIGNED",
        "period": None,
        "clock": None,
        "period_remaining_s": None,
        "elapsed_game_seconds": None,
        "event_number": None,
        "event_timestamp": None,
        "available_at": None,
        "time_actual": None,
        "inning": None,
        "half": None,
        "outs": None,
        "balls": None,
        "strikes": None,
        "count_display": None,
        "count_leverage": None,
        "runner_on_1": None,
        "runner_on_2": None,
        "runner_on_3": None,
        "runners": None,
        "batting_team": None,
        "home_score": None,
        "away_score": None,
        "yes_batting": None,
        "yes_pitching": None,
        "exclusion_reason": "PIT_ALIGNMENT_FAILED",
    }
    if not events:
        return unaligned
    chosen = choose_pit_row(events, snap_ts)
    if chosen is None:
        return unaligned
    inning = _int(chosen.get("inning"))
    half = normalize_half(chosen.get("half"))
    outs = live_outs(chosen.get("outs"))
    balls = live_balls(chosen.get("balls"))
    strikes = live_strikes(chosen.get("strikes"))
    on1, on2, on3 = runner_flags(chosen)
    bat = str(chosen.get("batting_team") or "") or batting_team(half)
    sl = inning_slice(inning, half)
    if sl == "UNALIGNED":
        return {**unaligned, "event_number": chosen.get("event_number"), "event_timestamp": chosen.get("event_timestamp")}
    yes_bat = yes_batting(half=half, batting=bat, team_side=team_side)
    return {
        "status": "REAL",
        "slice": sl,
        "period": sl,
        "clock": None,
        "period_remaining_s": None,
        "elapsed_game_seconds": None,
        "event_number": chosen.get("event_number"),
        "event_timestamp": chosen.get("event_timestamp") or chosen.get("event_time"),
        "available_at": chosen.get("available_at"),
        "time_actual": chosen.get("time_actual") or chosen.get("event_timestamp"),
        "inning": inning,
        "half": half,
        "outs": outs,
        "balls": balls,
        "strikes": strikes,
        "count_display": count_display(balls, strikes),
        "count_leverage": count_leverage(balls, strikes),
        "runner_on_1": on1,
        "runner_on_2": on2,
        "runner_on_3": on3,
        "runners": runner_category(on1, on2, on3),
        "batting_team": bat,
        "home_score": _int(chosen.get("home_score")),
        "away_score": _int(chosen.get("away_score")),
        "yes_batting": yes_bat,
        "yes_pitching": yes_pitching(yes_bat),
        "exclusion_reason": None,
        "note": "PIT PBP_ts <= entry_ts. Not a fill. Not a prediction.",
    }
