"""Tennis PIT snap: latest timestamped point with event_timestamp <= market_ts.

SEQUENCE_ONLY rows are retained in the warehouse but NEVER used as a PIT snap.
No interpolation. No nearest-future. No fabricated clocks.

    TIMESTAMPED_OBSERVED + point_ts <= market_ts → REAL
    no prior timestamped point                     → NO_POINT_DATA
    only SEQUENCE_ONLY rows                        → NO_POINT_DATA
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from roller.tennis.state import derive_state, yes_view
from roller.timeutil import parse_utc

PBP_TIMESTAMPED = "TIMESTAMPED_OBSERVED"
PBP_SEQUENCE = "SEQUENCE_ONLY"
NO_POINT_DATA = "NO_POINT_DATA"
UNALIGNED = "UNALIGNED"


def _bool(value: Any) -> bool | None:
    if value in (True, "true", "True", 1, "1"):
        return True
    if value in (False, "false", "False", 0, "0"):
        return False
    return None


def _int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _event_ts(ev: dict[str, Any]) -> datetime | None:
    return parse_utc(ev.get("event_timestamp") or ev.get("point_timestamp") or ev.get("event_time"))


def pit_joinable(ev: dict[str, Any]) -> bool:
    flag = _bool(ev.get("pit_joinable"))
    if flag is False:
        return False
    if str(ev.get("pbp_basis") or "") == PBP_SEQUENCE:
        return False
    if flag is True:
        return _event_ts(ev) is not None
    # Unlabeled rows: only joinable if they actually carry a timestamp.
    return _event_ts(ev) is not None and str(ev.get("pbp_basis") or "") != PBP_SEQUENCE


def pit_visible(events: list[dict[str, Any]], snap_ts: datetime) -> list[dict[str, Any]]:
    """Timestamped, PIT-joinable events with event_timestamp <= snap_ts."""
    out: list[dict[str, Any]] = []
    for ev in events:
        if not pit_joinable(ev):
            continue
        clock = _event_ts(ev)
        if clock is None or clock > snap_ts:
            continue
        out.append(ev)
    return out


def choose_pit_row(events: list[dict[str, Any]], snap_ts: datetime) -> dict[str, Any] | None:
    chosen: dict[str, Any] | None = None
    chosen_ts: datetime | None = None
    for ev in events:
        if not pit_joinable(ev):
            continue
        clock = _event_ts(ev)
        if clock is None or clock > snap_ts:
            continue
        if chosen is None or chosen_ts is None or clock > chosen_ts:
            chosen = ev
            chosen_ts = clock
            continue
        if clock == chosen_ts and int(ev.get("point_number") or ev.get("event_number") or 0) > int(
            chosen.get("point_number") or chosen.get("event_number") or 0
        ):
            chosen = ev
    return chosen


def tennis_slice(set_number: int | None, game_number: int | None) -> str:
    if set_number is None:
        return UNALIGNED
    if game_number is None:
        return f"S{set_number}"
    return f"S{set_number}"


def snapshot_age_seconds(point_ts: datetime | None, market_ts: datetime) -> int | None:
    if point_ts is None:
        return None
    return int((market_ts - point_ts).total_seconds())


def snap_tennis(
    events: list[dict[str, Any]],
    snap_ts: datetime,
    *,
    team_side: str | None = None,
    yes_player: int | None = None,
) -> dict[str, Any]:
    """ASOF_BACKWARD onto timestamped tennis PBP. Fail closed otherwise."""
    empty = {
        "status": NO_POINT_DATA,
        "slice": UNALIGNED,
        "exclusion_reason": "NO_POINT_DATA",
        "pbp_basis": None,
        "pit_joinable": False,
        "point_snapshot_available": False,
        "set_number": None,
        "game_number": None,
        "server": None,
        "receiver": None,
        "is_tiebreak": None,
        "point_score_raw": None,
        "snapshot_age_seconds": None,
        "point_snapshot_ts": None,
    }
    if not events:
        return {**empty, "exclusion_reason": "NO_PBP_EVENTS"}
    if yes_player is None:
        if team_side in {"1", "p1", "player_1", "yes"}:
            yes_player = 1
        elif team_side in {"2", "p2", "player_2"}:
            yes_player = 2
        else:
            yes_player = _int(team_side)

    any_timestamped = any(pit_joinable(ev) for ev in events)
    if not any_timestamped:
        basis = next((str(ev.get("pbp_basis") or "") for ev in events if ev.get("pbp_basis")), PBP_SEQUENCE)
        return {
            **empty,
            "pbp_basis": basis or PBP_SEQUENCE,
            "exclusion_reason": "SEQUENCE_ONLY",
        }

    chosen = choose_pit_row(events, snap_ts)
    if chosen is None:
        return {**empty, "pbp_basis": PBP_TIMESTAMPED, "exclusion_reason": "NO_PRIOR_POINT"}

    point_ts = _event_ts(chosen)
    set_n = _int(chosen.get("set_number"))
    game_n = _int(chosen.get("game_number"))
    state = derive_state(chosen)
    yes = yes_view(chosen, yes_player) if yes_player is not None else {}
    return {
        "status": "REAL",
        "slice": tennis_slice(set_n, game_n),
        "exclusion_reason": None,
        "pbp_basis": PBP_TIMESTAMPED,
        "pit_joinable": True,
        "point_snapshot_available": True,
        "set_number": set_n,
        "game_number": game_n,
        "sets_p1": _int(chosen.get("sets_p1")),
        "sets_p2": _int(chosen.get("sets_p2")),
        "games_p1": _int(chosen.get("games_p1")),
        "games_p2": _int(chosen.get("games_p2")),
        "points_p1_raw": chosen.get("points_p1_raw"),
        "points_p2_raw": chosen.get("points_p2_raw"),
        "point_score_raw": chosen.get("point_score_raw"),
        "server": _int(chosen.get("server")),
        "receiver": _int(chosen.get("receiver")),
        "is_tiebreak": _bool(chosen.get("is_tiebreak")),
        "best_of": _int(chosen.get("best_of")),
        "point_number": _int(chosen.get("point_number") or chosen.get("event_number")),
        "event_timestamp": point_ts.isoformat().replace("+00:00", "Z") if point_ts else None,
        "point_snapshot_ts": point_ts.isoformat().replace("+00:00", "Z") if point_ts else None,
        "snapshot_age_seconds": snapshot_age_seconds(point_ts, snap_ts),
        "yes_player": yes_player,
        **state,
        **yes,
    }
