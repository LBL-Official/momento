"""Parse NBA live PBP and ESPN normalized plays. Never invent wall clocks."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def nba_pbp_live_path(warehouse: Path, nba_game_id: str) -> Path:
    return warehouse / "raw" / "nba_stats" / "pbp_live" / f"{nba_game_id}.json"


def nba_pbp_v3_path(warehouse: Path, nba_game_id: str) -> Path:
    return warehouse / "raw" / "nba_stats" / "pbp_v3" / f"{nba_game_id}.json"


def nba_box_path(warehouse: Path, nba_game_id: str) -> Path:
    return warehouse / "raw" / "nba_stats" / "boxscore_summary" / f"{nba_game_id}.json"


def espn_plays_path(warehouse: Path, sport: str, espn_game_id: str) -> Path:
    return warehouse / "normalized" / sport.lower() / "pbp" / "plays" / f"{espn_game_id}.json"


def box_scores(box: dict[str, Any] | None) -> tuple[int | None, int | None, str | None]:
    if not box:
        return None, None, None
    hdr = box.get("boxScoreSummary") or {}
    home = hdr.get("homeTeam") or {}
    away = hdr.get("awayTeam") or {}
    tip = hdr.get("gameTimeUTC")
    try:
        hs = int(home["score"]) if home.get("score") not in (None, "") else None
    except (TypeError, ValueError):
        hs = None
    try:
        as_ = int(away["score"]) if away.get("score") not in (None, "") else None
    except (TypeError, ValueError):
        as_ = None
    return hs, as_, tip


def parse_nba_actions(payload: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not payload:
        return []
    game = payload.get("game") or {}
    actions = game.get("actions") or []
    out = []
    for a in actions:
        try:
            sh = int(a.get("scoreHome") if a.get("scoreHome") not in (None, "") else 0)
        except (TypeError, ValueError):
            sh = 0
        try:
            sa = int(a.get("scoreAway") if a.get("scoreAway") not in (None, "") else 0)
        except (TypeError, ValueError):
            sa = 0
        wall = a.get("timeActual")
        person = a.get("personId")
        team_id = a.get("teamId")
        out.append(
            {
                "event_number": a.get("actionNumber") if a.get("actionNumber") is not None else a.get("orderNumber"),
                "event_timestamp": wall,
                "time_actual": wall or "",
                "timestamp_status": "OBSERVED" if wall else "CLOCK_ONLY",
                "available_at": wall,
                "availability_quality": "OBSERVED" if wall else "CONSERVATIVE_PROXY",
                "period": a.get("period"),
                "clock": a.get("clock"),
                "home_score": sh,
                "away_score": sa,
                "score_differential_home": sh - sa,
                "event_type": a.get("actionType"),
                "event_description": a.get("description"),
                "team_tricode": a.get("teamTricode"),
                "possession": a.get("possession"),
                "person_id": "" if person in (None, "") else str(person),
                "sub_type": a.get("subType") or "",
                "shot_result": a.get("shotResult") or "",
                "team_id": "" if team_id in (None, "") else str(team_id),
                "player_name": a.get("playerName") or a.get("playerNameI") or "",
                "home_away": "",
            }
        )
    return out


def parse_espn_plays(payload: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not payload:
        return []
    plays = payload.get("plays") or []
    out = []
    for i, a in enumerate(plays, start=1):
        wall = a.get("timeActual") or a.get("time_actual") or a.get("wallclock")
        team = a.get("team") if isinstance(a.get("team"), dict) else {}
        team_id = team.get("id") or team.get("abbreviation") or a.get("team_id") or ""
        team_tri = team.get("abbreviation") or a.get("team_tricode") or ""
        home_away = a.get("homeAway") or a.get("home_away") or ""
        try:
            sh = int(a.get("homeScore") if a.get("homeScore") not in (None, "") else 0)
        except (TypeError, ValueError):
            sh = 0
        try:
            sa = int(a.get("awayScore") if a.get("awayScore") not in (None, "") else 0)
        except (TypeError, ValueError):
            sa = 0
        seq = a.get("sequenceNumber")
        clock = a.get("clock")
        if isinstance(clock, dict):
            clock = clock.get("displayValue") or clock.get("display")
        period = a.get("period")
        if isinstance(period, dict):
            period = period.get("number")
        out.append(
            {
                "event_number": seq if seq not in (None, "") else i,
                "event_timestamp": wall,
                "time_actual": wall or "",
                "timestamp_status": "OBSERVED" if wall else "CLOCK_ONLY",
                "available_at": wall,
                "availability_quality": "OBSERVED" if wall else "CONSERVATIVE_PROXY",
                "period": period,
                "clock": clock,
                "home_score": sh,
                "away_score": sa,
                "score_differential_home": sh - sa,
                "event_type": a.get("type_text") or a.get("type_id"),
                "event_description": a.get("text"),
                "team_tricode": team_tri or "",
                "possession": "",
                "person_id": "",
                "sub_type": "",
                "shot_result": "",
                "team_id": "" if team_id in (None, "") else str(team_id),
                "player_name": "",
                "home_away": home_away,
            }
        )
    return out


def last_scored_result(events: list[dict[str, Any]]) -> tuple[int | None, int | None, str | None]:
    if not events:
        return None, None, None
    last = events[-1]
    wall = None
    for e in reversed(events):
        if e.get("event_timestamp"):
            wall = e["event_timestamp"]
            break
    return last.get("home_score"), last.get("away_score"), wall
