"""Live-CDN possession reconstruction for PADE V1.

Uses NBA live PBP action types (2pt/3pt/rebound|defensive/...), not V3 names.
Wall timestamps are OBSERVED timeActual when present. Never invent walls.
"""

from __future__ import annotations

from .common import (
    elapsed_game_seconds,
    game_seconds_remaining_known,
    parse_clock_seconds,
    parse_timeactual,
)

LAST_FT = {"1 of 1", "2 of 2", "3 of 3"}
KNOWN = {
    "2pt",
    "3pt",
    "rebound",
    "turnover",
    "freethrow",
    "foul",
    "substitution",
    "timeout",
    "violation",
    "jumpball",
    "period",
    "heave",
    "steal",
    "block",
    "game",
    "",
}


def _typ(a) -> str:
    return (a.get("actionType") or "").strip().lower().replace(" ", "")


def _sub(a) -> str:
    return (a.get("subType") or "").strip().lower()


def _team(a) -> str | None:
    t = (a.get("teamTricode") or a.get("team_tricode") or "") or None
    return t.upper() if t else None


def _shot_result(a) -> str:
    return str(a.get("shotResult") or "").strip().lower()


def _is_made_fg(a) -> bool:
    return _typ(a) in ("2pt", "3pt", "heave") and _shot_result(a) == "made"


def _is_missed_fg(a) -> bool:
    return _typ(a) in ("2pt", "3pt", "heave") and _shot_result(a) == "missed"


def _is_turnover(a) -> bool:
    return _typ(a) == "turnover"


def _is_period_end(a) -> bool:
    return _typ(a) == "period" and _sub(a) == "end"


def _is_period_start(a) -> bool:
    return _typ(a) == "period" and _sub(a) == "start"


def _is_last_ft(a) -> bool:
    return _typ(a) == "freethrow" and _sub(a) in LAST_FT


def _is_and_one_follow(actions: list[dict], i: int) -> bool:
    for j in range(i + 1, min(i + 6, len(actions))):
        t = _typ(actions[j])
        s = _sub(actions[j])
        if t in ("substitution", "timeout", "instantreplay"):
            continue
        if t == "foul" and "shooting" in s:
            return True
        if t == "freethrow" and s == "1 of 1":
            return True
        return False
    return False


def _rebound_kind(a) -> str | None:
    if _typ(a) != "rebound":
        return None
    s = _sub(a)
    if s == "offensive":
        return "offensive"
    if s == "defensive":
        return "defensive"
    return None


def enrich_live_action(a: dict) -> dict:
    out = dict(a)
    rem = parse_clock_seconds(a.get("clock"))
    period = a.get("period")
    ptype = a.get("periodType")
    wall = parse_timeactual(a.get("timeActual"))
    out["_typ"] = _typ(a)
    out["_sub"] = _sub(a)
    out["_team"] = _team(a)
    out["remaining_s"] = rem
    out["elapsed_s"] = elapsed_game_seconds(period, rem, ptype)
    out["game_seconds_remaining"] = game_seconds_remaining_known(period, rem, ptype)
    out["wall_ts"] = wall
    out["wall_source"] = "timeActual" if wall is not None else None
    try:
        out["score_home"] = int(a.get("scoreHome") if a.get("scoreHome") not in (None, "") else 0)
        out["score_away"] = int(a.get("scoreAway") if a.get("scoreAway") not in (None, "") else 0)
    except (TypeError, ValueError):
        out["score_home"] = 0
        out["score_away"] = 0
    return out


def build_possessions(
    nba_game_id: str,
    actions: list[dict],
    home_tri: str | None,
    away_tri: str | None,
) -> tuple[list[dict], dict]:
    issues = {
        "unmapped_action_types": {},
        "impossible_score_jumps": 0,
        "nonmonotonic_clock": 0,
        "open_possession_at_end": 0,
        "ambiguous_possessions": 0,
        "missing_wall": 0,
    }
    poss: list[dict] = []
    seq = 0
    current = None
    last_clock: dict[int, float] = {}

    def team_is_home(t: str | None):
        if t is None:
            return None
        if home_tri and t == home_tri:
            return True
        if away_tri and t == away_tri:
            return False
        return None

    def close(end_idx: int, result: str, ambiguous: bool = False):
        nonlocal current, seq
        if current is None:
            return
        a0 = actions[current["start_idx"]]
        a1 = actions[end_idx]
        sh0, sa0 = current["home_score_start"], current["away_score_start"]
        sh1 = a1.get("score_home", sh0)
        sa1 = a1.get("score_away", sa0)
        jump = abs((sh1 + sa1) - (sh0 + sa0))
        if jump > 4:
            issues["impossible_score_jumps"] += 1
        seq += 1
        team = current["possession_team"]
        if current["team_is_home"] is True:
            pts_for = sh1 - sh0
            diff_start = sh0 - sa0
            diff_end_a1 = sh1 - sa1
        elif current["team_is_home"] is False:
            pts_for = sa1 - sa0
            diff_start = sa0 - sh0
            diff_end_a1 = sa1 - sh1
        else:
            pts_for = (sh1 + sa1) - (sh0 + sa0)
            diff_start = None
            diff_end_a1 = None
            ambiguous = True
        if a0.get("wall_ts") is None or a1.get("wall_ts") is None:
            issues["missing_wall"] += 1
        if ambiguous:
            issues["ambiguous_possessions"] += 1
        def_team = None
        if team and home_tri and away_tri:
            def_team = away_tri if team == home_tri else home_tri if team == away_tri else None
        poss.append(
            {
                "nba_game_id": nba_game_id,
                "possession_id": f"{nba_game_id}|{seq:04d}",
                "possession_index": seq,
                "period": current["period"],
                "period_type": a0.get("periodType"),
                "start_idx": current["start_idx"],
                "end_idx": end_idx,
                "event_count": end_idx - current["start_idx"] + 1,
                "game_clock_start": a0.get("clock"),
                "game_clock_end": a1.get("clock"),
                "game_clock_seconds_remaining_period_start": a0.get("remaining_s"),
                "game_clock_seconds_remaining_period_end": a1.get("remaining_s"),
                "elapsed_game_seconds_start": a0.get("elapsed_s"),
                "elapsed_game_seconds_end": a1.get("elapsed_s"),
                "game_seconds_remaining_start": a0.get("game_seconds_remaining"),
                "duration_game_seconds": (
                    None
                    if a0.get("elapsed_s") is None or a1.get("elapsed_s") is None
                    else max(0.0, float(a1["elapsed_s"]) - float(a0["elapsed_s"]))
                ),
                "wall_start_ts": a0.get("wall_ts"),
                "wall_end_ts": a1.get("wall_ts"),
                "wall_start_source": a0.get("wall_source"),
                "wall_end_source": a1.get("wall_source"),
                "offensive_team": team,
                "defensive_team": def_team,
                "score_home_start": sh0,
                "score_away_start": sa0,
                "score_home_end": sh1,
                "score_away_end": sa1,
                "score_differential_offense": diff_start,
                "score_differential_end_offense": diff_end_a1,
                "score_differential_absolute": None if diff_start is None else abs(diff_start),
                "possession_result": result,
                "points_scored": int(pts_for) if pts_for is not None else 0,
                "field_goal_attempt": current["fga"],
                "field_goal_made": current["fgm"],
                "turnover": 1 if result == "turnover" else 0,
                "offensive_rebound": current["oreb"],
                "defensive_rebound": 1 if result == "defensive_rebound" else 0,
                "free_throw_attempts": current["fta"],
                "free_throws_made": current["ftm"],
                "timeout": current["timeout"],
                "ambiguous_possession_flag": bool(ambiguous or not team),
                "source_confidence": (
                    "LOW" if ambiguous or not team else ("HIGH" if a0.get("wall_ts") and a1.get("wall_ts") else "MEDIUM")
                ),
            }
        )
        current = None

    def open_poss(i: int, team: str | None, period, sh: int, sa: int, ambiguous: bool = False):
        nonlocal current
        current = {
            "start_idx": i,
            "period": period,
            "possession_team": team,
            "team_is_home": team_is_home(team),
            "home_score_start": sh,
            "away_score_start": sa,
            "fga": 0,
            "fgm": 0,
            "oreb": 0,
            "fta": 0,
            "ftm": 0,
            "timeout": 0,
            "ambiguous": ambiguous,
        }

    for i, a in enumerate(actions):
        typ = a.get("_typ") or _typ(a)
        if typ not in KNOWN:
            issues["unmapped_action_types"][typ] = issues["unmapped_action_types"].get(typ, 0) + 1
        period = a.get("period")
        rem = a.get("remaining_s")
        if period is not None and rem is not None:
            prev = last_clock.get(int(period))
            if prev is not None and rem > prev + 1.5:
                issues["nonmonotonic_clock"] += 1
            last_clock[int(period)] = rem
        sh = int(a.get("score_home") or 0)
        sa = int(a.get("score_away") or 0)
        team = a.get("_team") or _team(a)

        if _is_period_start(a):
            if current is not None:
                close(i, "period_boundary", ambiguous=True)
            continue
        if _is_period_end(a) or typ == "game":
            close(i, "period_end" if _is_period_end(a) else "game_end")
            continue

        if typ == "jumpball" and current is None and team:
            open_poss(i, team, period, sh, sa)
            continue

        if current is None:
            if team and typ in ("2pt", "3pt", "heave", "freethrow", "turnover", "foul", "rebound"):
                open_poss(i, team, period, sh, sa)
            elif typ == "steal" and team:
                # Steal team is defensive; possession belongs to them after the steal.
                open_poss(i, team, period, sh, sa)

        if current is None:
            continue

        if typ == "timeout":
            current["timeout"] += 1
        if typ == "freethrow":
            current["fta"] += 1
            if _shot_result(a) == "made":
                current["ftm"] += 1

        if _is_made_fg(a):
            current["fga"] += 1
            current["fgm"] += 1
            if not _is_and_one_follow(actions, i):
                close(i, "made_fg")
            continue

        if _is_missed_fg(a):
            current["fga"] += 1
            continue

        if typ == "rebound":
            kind = _rebound_kind(a)
            if kind == "offensive":
                current["oreb"] += 1
            elif kind == "defensive":
                close(i, "defensive_rebound")
                if team:
                    open_poss(i, team, period, sh, sa)
            else:
                close(i, "rebound_unclassified", ambiguous=True)
                if team:
                    open_poss(i, team, period, sh, sa, ambiguous=True)
            continue

        if _is_turnover(a):
            close(i, "turnover")
            continue

        if _is_last_ft(a) and _shot_result(a) == "made" and "technical" not in _sub(a):
            close(i, "made_ft")
            continue

    if current is not None:
        issues["open_possession_at_end"] += 1
        close(len(actions) - 1, "game_end_open", ambiguous=True)

    issues["n_possessions"] = len(poss)
    issues["duplicate_ids"] = len(poss) - len({p["possession_id"] for p in poss})
    return poss, issues
