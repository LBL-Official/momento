"""Possession reconstruction. Categorical status only. No numeric confidence.

NBA raw `possession` is an auxiliary offensive teamId, not a segment key.
WNBA / NCAAB use ESPN type_text + team / homeAway when present.
Do not parse player names from text. Status is PARTIAL when team is often missing.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from roller.canonical.events import event_records, project_events
from roller.config import RollerConfig
from roller.io_csv import write_csv
from roller.paths import derived_dir

POSSESSION_RULE_VERSION = "2.0.0"
POSSESSION_STATUSES = ("CONFIRMED", "RECONSTRUCTED", "AMBIGUOUS", "UNRESOLVED")

POSSESSION_COLUMNS = [
    "possession_uid",
    "internal_game_id",
    "sport",
    "offensive_team_id",
    "start_event_number",
    "end_event_number",
    "start_status",
    "end_status",
    "end_reason",
    "start_event_time",
    "end_event_time",
    "start_available_at",
    "end_available_at",
    "possession_rule_version",
]


def _norm(value: Any) -> str:
    return str(value or "").strip()


def _lower(value: Any) -> str:
    return _norm(value).lower()


def actor_team(event: dict[str, Any], home_team_id: str = "", away_team_id: str = "") -> str:
    tri = _norm(event.get("team_tricode"))
    if tri:
        return tri
    tid = _norm(event.get("team_id"))
    if tid:
        return tid
    ha = _lower(event.get("home_away"))
    if ha == "home" and home_team_id:
        return home_team_id
    if ha == "away" and away_team_id:
        return away_team_id
    return ""


def aux_possession_team(event: dict[str, Any]) -> str:
    return _norm(event.get("possession"))


def _is_freethrow(event: dict[str, Any]) -> bool:
    et = _lower(event.get("event_type"))
    compact = et.replace(" ", "").replace("-", "")
    if compact in {"freethrow", "freethrows"}:
        return True
    return "free throw" in et


def _is_made_fg(event: dict[str, Any]) -> bool:
    if _is_freethrow(event):
        return False
    sr = _lower(event.get("shot_result"))
    et = _lower(event.get("event_type"))
    desc = _lower(event.get("event_description"))
    if sr in {"made", "make"}:
        return True
    if et in {"made shot", "made field goal"}:
        return True
    if et in {"shot", "2pt", "3pt", "fieldgoal"} and ("make" in desc or "made" in desc):
        return True
    return False


def _is_defensive_rebound(event: dict[str, Any]) -> bool:
    et = _lower(event.get("event_type"))
    st = _lower(event.get("sub_type"))
    if "defensive rebound" in et:
        return True
    return "rebound" in et and "defensive" in st


def _is_offensive_rebound(event: dict[str, Any]) -> bool:
    et = _lower(event.get("event_type"))
    st = _lower(event.get("sub_type"))
    if "offensive rebound" in et:
        return True
    return "rebound" in et and "offensive" in st


def _is_turnover(event: dict[str, Any]) -> bool:
    return "turnover" in _lower(event.get("event_type"))


def _is_steal(event: dict[str, Any]) -> bool:
    return _lower(event.get("event_type")) == "steal"


def _is_period_end(event: dict[str, Any]) -> bool:
    et = _lower(event.get("event_type"))
    desc = _lower(event.get("event_description"))
    if et in {"end period", "endperiod", "end of period"}:
        return True
    return et == "period" and desc in {"end", "end period", "endperiod"}


def _is_period_start(event: dict[str, Any]) -> bool:
    et = _lower(event.get("event_type"))
    desc = _lower(event.get("event_description"))
    if et in {"start period", "startperiod", "start of period"}:
        return True
    return et == "period" and desc in {"start", "start period", "startperiod"}


def _is_jumpball(event: dict[str, Any]) -> bool:
    return _lower(event.get("event_type")).replace(" ", "") in {"jumpball", "jump"}


def _next_nonempty(events: list[dict[str, Any]], i: int) -> dict[str, Any] | None:
    if i + 1 < len(events):
        return events[i + 1]
    return None


def _close(
    open_poss: dict[str, Any],
    event: dict[str, Any],
    *,
    end_status: str,
    end_reason: str,
) -> dict[str, Any]:
    gid = _norm(event.get("internal_game_id") or open_poss.get("internal_game_id"))
    start_n = open_poss["start_event_number"]
    end_n = event.get("event_number")
    return {
        "possession_uid": f"{gid}_{start_n}_{end_n}",
        "internal_game_id": gid,
        "sport": open_poss.get("sport") or event.get("sport") or "NBA",
        "offensive_team_id": open_poss.get("offensive_team_id") or "",
        "start_event_number": start_n,
        "end_event_number": end_n,
        "start_status": open_poss["start_status"],
        "end_status": end_status,
        "end_reason": end_reason,
        "start_event_time": open_poss.get("start_event_time") or "",
        "end_event_time": event.get("event_time") or event.get("event_timestamp") or "",
        "start_available_at": open_poss.get("start_available_at") or "",
        "end_available_at": event.get("available_at") or "",
        "possession_rule_version": POSSESSION_RULE_VERSION,
    }


def _open_new(
    event: dict[str, Any],
    *,
    team: str,
    start_status: str,
    sport: str,
) -> dict[str, Any]:
    return {
        "internal_game_id": _norm(event.get("internal_game_id")),
        "sport": sport,
        "offensive_team_id": team,
        "start_event_number": event.get("event_number"),
        "start_status": start_status,
        "start_event_time": event.get("event_time") or event.get("event_timestamp") or event.get("time_actual") or "",
        "start_available_at": event.get("available_at") or "",
    }


def _start_status_for(event: dict[str, Any], team: str) -> str:
    aux = aux_possession_team(event)
    actor = actor_team(event)
    if _is_jumpball(event) and aux and actor and aux != actor:
        return "AMBIGUOUS"
    if not team:
        return "UNRESOLVED"
    if actor and aux and aux != actor and not _is_steal(event) and not _is_defensive_rebound(event):
        return "AMBIGUOUS"
    if actor:
        return "CONFIRMED"
    if aux:
        return "RECONSTRUCTED"
    return "UNRESOLVED"


def reconstruct_possessions(
    events: list[dict[str, Any]] | pd.DataFrame,
    *,
    sport: str,
    home_team_id: str = "",
    away_team_id: str = "",
) -> dict[str, Any]:
    if sport not in {"NBA", "WNBA", "NCAAB"}:
        return {"status": "NOT_SUPPORTED", "possessions": [], "possession_rule_version": POSSESSION_RULE_VERSION}
    rows = event_records(events) if isinstance(events, pd.DataFrame) else list(events or [])
    rows = sorted(
        rows,
        key=lambda e: (
            str(e.get("available_at") or ""),
            str(e.get("event_number") or ""),
        ),
    )
    possessions: list[dict[str, Any]] = []
    open_poss: dict[str, Any] | None = None

    for i, event in enumerate(rows):
        team = actor_team(event, home_team_id, away_team_id)
        aux = aux_possession_team(event)
        nxt = _next_nonempty(rows, i)

        if open_poss is None:
            start_team = team or aux
            open_poss = _open_new(
                event, team=start_team, start_status=_start_status_for(event, start_team), sport=sport
            )
        elif team and not open_poss.get("offensive_team_id"):
            open_poss["offensive_team_id"] = team

        ended = False
        if _is_made_fg(event):
            same_ft = (
                nxt is not None
                and _is_freethrow(nxt)
                and actor_team(nxt, home_team_id, away_team_id) == (team or open_poss["offensive_team_id"])
            )
            if same_ft:
                open_poss["pending_and_one"] = True
            else:
                possessions.append(_close(open_poss, event, end_status="CONFIRMED", end_reason="MADE_FIELD_GOAL"))
                ended = True
        elif _is_freethrow(event) and open_poss.get("pending_and_one"):
            more_ft = (
                nxt is not None
                and _is_freethrow(nxt)
                and actor_team(nxt, home_team_id, away_team_id) == (team or open_poss["offensive_team_id"])
            )
            if not more_ft:
                possessions.append(_close(open_poss, event, end_status="CONFIRMED", end_reason="MADE_FIELD_GOAL"))
                ended = True
        elif _is_defensive_rebound(event):
            possessions.append(_close(open_poss, event, end_status="CONFIRMED", end_reason="DEFENSIVE_REBOUND"))
            ended = True
        elif _is_turnover(event):
            if not open_poss.get("offensive_team_id"):
                open_poss["offensive_team_id"] = team
            possessions.append(_close(open_poss, event, end_status="CONFIRMED", end_reason="TURNOVER"))
            ended = True
        elif _is_steal(event):
            possessions.append(_close(open_poss, event, end_status="CONFIRMED", end_reason="STEAL"))
            ended = True
        elif _is_period_end(event):
            possessions.append(
                _close(
                    open_poss,
                    event,
                    end_status="CONFIRMED" if open_poss.get("offensive_team_id") else "RECONSTRUCTED",
                    end_reason="PERIOD_END",
                )
            )
            ended = True
        elif (
            team
            and open_poss.get("offensive_team_id")
            and team != open_poss["offensive_team_id"]
            and not _is_offensive_rebound(event)
            and not _is_freethrow(event)
            and not _is_period_start(event)
        ):
            possessions.append(_close(open_poss, event, end_status="RECONSTRUCTED", end_reason="TEAM_CHANGE"))
            ended = True
            # TEAM_CHANGE event belongs to the new possession.
            open_poss = _open_new(event, team=team, start_status=_start_status_for(event, team), sport=sport)
            ended = False
            continue

        if ended:
            open_poss = None
            continue

    if open_poss is not None:
        last = rows[-1] if rows else {}
        possessions.append(
            _close(
                open_poss,
                last,
                end_status="UNRESOLVED" if not open_poss.get("offensive_team_id") else "RECONSTRUCTED",
                end_reason="OPEN_AT_CUTOFF" if last else "UNRESOLVED",
            )
        )

    status = "REAL"
    if sport in {"WNBA", "NCAAB"}:
        known = sum(1 for p in possessions if p.get("offensive_team_id"))
        status = "PARTIAL" if not possessions or known < len(possessions) else "REAL"
    return {
        "status": status,
        "possessions": possessions,
        "possession_rule_version": POSSESSION_RULE_VERSION,
    }


def write_possessions(
    cfg: RollerConfig,
    sport: str,
    season: str,
    pbp: pd.DataFrame,
    games: pd.DataFrame | None = None,
) -> pd.DataFrame:
    path_key = cfg.season_meta(sport, season)["path_key"]
    out_path = derived_dir(cfg.root, sport, path_key) / "possessions.csv"
    if sport not in {"NBA", "WNBA", "NCAAB"} or pbp is None or pbp.empty:
        empty = pd.DataFrame(columns=POSSESSION_COLUMNS)
        write_csv(out_path, empty, POSSESSION_COLUMNS)
        return empty
    home_away: dict[str, tuple[str, str]] = {}
    if games is not None and not games.empty:
        for g in games.to_dict("records"):
            home_away[str(g.get("internal_game_id") or "")] = (
                str(g.get("home_team_id") or ""),
                str(g.get("away_team_id") or ""),
            )
    events = project_events(pbp)
    rows: list[dict[str, Any]] = []
    for gid, grp in events.groupby("internal_game_id", sort=False):
        recs = event_records(grp)
        home, away = home_away.get(str(gid), ("", ""))
        built = reconstruct_possessions(recs, sport=sport, home_team_id=home, away_team_id=away)
        for poss in built["possessions"]:
            poss["internal_game_id"] = gid
            poss["sport"] = sport
            rows.append(poss)
    df = pd.DataFrame(rows)
    if df.empty:
        df = pd.DataFrame(columns=POSSESSION_COLUMNS)
    else:
        df = df[POSSESSION_COLUMNS]
    write_csv(out_path, df, POSSESSION_COLUMNS)
    return df
