"""Possession reconstruction following ROLLER POSSESSIONS.md v2.0.0 methodology.

Writes only under derived/terminal_efficiency/. Does not invent possessions
when the source cannot support a close. Status is categorical.
"""

from __future__ import annotations

from typing import Any

POSSESSION_RULE_VERSION = "2.0.0"
POSSESSION_STATUSES = ("CONFIRMED", "RECONSTRUCTED", "AMBIGUOUS", "UNRESOLVED")


def _n(v: Any) -> str:
    return str(v or "").strip()


def _l(v: Any) -> str:
    return _n(v).lower()


def _is_freethrow(e: dict) -> bool:
    et = _l(e.get("action_type"))
    compact = et.replace(" ", "").replace("-", "")
    return compact in {"freethrow", "freethrows"} or "free throw" in et


def _is_made_fg(e: dict) -> bool:
    if _is_freethrow(e):
        return False
    sr = _l(e.get("shot_result"))
    et = _l(e.get("action_type"))
    desc = _l(e.get("description"))
    if sr in {"made", "make"}:
        return True
    if et in {"made shot", "made field goal"}:
        return True
    if et in {"shot", "2pt", "3pt", "fieldgoal"} and ("make" in desc or "made" in desc):
        return True
    return False


def _is_defensive_rebound(e: dict) -> bool:
    et = _l(e.get("action_type"))
    st = _l(e.get("sub_type"))
    return "defensive rebound" in et or ("rebound" in et and "defensive" in st)


def _is_turnover(e: dict) -> bool:
    return "turnover" in _l(e.get("action_type"))


def _is_steal(e: dict) -> bool:
    return _l(e.get("action_type")) == "steal"


def _is_period_end(e: dict) -> bool:
    et = _l(e.get("action_type"))
    st = _l(e.get("sub_type"))
    desc = _l(e.get("description"))
    if et in {"end period", "endperiod", "end of period"}:
        return True
    if et == "period" and st in {"end", "end period"}:
        return True
    return "end of" in desc and "period" in desc


def _is_jumpball(e: dict) -> bool:
    return _l(e.get("action_type")).replace(" ", "") in {"jumpball", "jump"}


def reconstruct_possessions(events: list[dict], *, sport: str) -> list[dict]:
    if sport not in {"NBA", "NCAAB"}:
        return []
    rows = sorted(events, key=lambda e: (int(e.get("event_number") or 0), str(e.get("available_at") or "")))
    possessions: list[dict] = []
    open_p: dict | None = None

    def close(event: dict, end_status: str, end_reason: str) -> None:
        nonlocal open_p
        if open_p is None:
            return
        start_n = open_p["start_event_number"]
        end_n = event.get("event_number")
        gid = _n(event.get("game_id") or open_p.get("game_id"))
        possessions.append(
            {
                "possession_uid": f"{gid}_{start_n}_{end_n}",
                "game_id": gid,
                "league": sport,
                "offensive_team_id": open_p.get("offensive_team_id") or "",
                "start_event_number": start_n,
                "end_event_number": end_n,
                "start_status": open_p["start_status"],
                "end_status": end_status,
                "end_reason": end_reason,
                "start_event_time": open_p.get("start_event_time") or "",
                "end_event_time": event.get("event_timestamp") or "",
                "start_available_at": open_p.get("start_available_at") or "",
                "end_available_at": event.get("available_at") or "",
                "period": event.get("period"),
                "seconds_remaining_game": event.get("seconds_remaining_game"),
                "seconds_remaining_period": event.get("seconds_remaining_period"),
                "home_score": event.get("home_score"),
                "away_score": event.get("away_score"),
                "score_difference": event.get("score_difference"),
                "possession_rule_version": POSSESSION_RULE_VERSION,
            }
        )
        open_p = None

    def open_new(event: dict, team: str, start_status: str) -> None:
        nonlocal open_p
        open_p = {
            "game_id": _n(event.get("game_id")),
            "offensive_team_id": team,
            "start_event_number": event.get("event_number"),
            "start_status": start_status,
            "start_event_time": event.get("event_timestamp") or "",
            "start_available_at": event.get("available_at") or "",
        }

    for i, event in enumerate(rows):
        team = _n(event.get("team_tricode"))
        nxt = rows[i + 1] if i + 1 < len(rows) else None
        if open_p is None:
            status = "UNRESOLVED" if not team else "CONFIRMED"
            if _is_jumpball(event) and not team:
                status = "AMBIGUOUS"
            open_new(event, team, status)
        elif team and not open_p.get("offensive_team_id"):
            open_p["offensive_team_id"] = team

        ended = False
        if _is_made_fg(event):
            same_ft = (
                nxt is not None
                and _is_freethrow(nxt)
                and _n(nxt.get("team_tricode")) == (team or open_p["offensive_team_id"])
            )
            if same_ft:
                open_p["pending_and_one"] = True
            else:
                close(event, "CONFIRMED", "MADE_FIELD_GOAL")
                ended = True
        elif _is_freethrow(event) and open_p and open_p.get("pending_and_one"):
            more_ft = nxt is not None and _is_freethrow(nxt) and _n(nxt.get("team_tricode")) == (
                team or open_p["offensive_team_id"]
            )
            if not more_ft:
                close(event, "CONFIRMED", "MADE_FIELD_GOAL")
                ended = True
        elif _is_defensive_rebound(event):
            close(event, "CONFIRMED", "DEFENSIVE_REBOUND")
            ended = True
        elif _is_turnover(event):
            close(event, "CONFIRMED", "TURNOVER")
            ended = True
        elif _is_steal(event):
            close(event, "CONFIRMED", "STEAL")
            ended = True
        elif _is_period_end(event):
            st = "CONFIRMED" if open_p and open_p.get("offensive_team_id") else "RECONSTRUCTED"
            close(event, st, "PERIOD_END")
            ended = True
        elif team and open_p and open_p.get("offensive_team_id") and team != open_p["offensive_team_id"]:
            if not _is_freethrow(event):
                close(event, "RECONSTRUCTED", "TEAM_CHANGE")
                ended = True

        if ended:
            team2 = _n(event.get("team_tricode"))
            # new possession starts on the next event unless period ended
            if not _is_period_end(event) and nxt is not None:
                nxt_team = _n(nxt.get("team_tricode"))
                open_new(nxt, nxt_team, "CONFIRMED" if nxt_team else "UNRESOLVED")
                # will be revisited on next loop; avoid double-open by skipping if we already
                # opened from nxt — simpler: don't open here; next loop opens if None
                open_p = None

    if open_p is not None and rows:
        close(rows[-1], "RECONSTRUCTED", "OPEN_AT_CUTOFF")
    return possessions
