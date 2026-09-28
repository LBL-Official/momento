"""Deterministic possession reconstruction from PlayByPlayV3.

Wall timestamps are MODELED via GPE V2. Possession sequence is OBSERVED.
"""

from __future__ import annotations

import re

OFF_DEF_RE = re.compile(r"REBOUND \(Off:(\d+) Def:(\d+)\)", re.I)


def _typ(a) -> str:
    return (a.get("actionType") or "").strip().lower()


def _sub(a) -> str:
    return (a.get("subType") or "").strip().lower()


def _team(a) -> str | None:
    t = (a.get("team_tricode") or a.get("teamTricode") or "") or None
    return t.upper() if t else None


def _is_made_fg(a) -> bool:
    return _typ(a) == "made shot" or (
        bool(a.get("isFieldGoal")) and str(a.get("shotResult") or "").lower() == "made"
    )


def _is_missed_fg(a) -> bool:
    return _typ(a) == "missed shot" or (
        bool(a.get("isFieldGoal")) and str(a.get("shotResult") or "").lower() == "missed"
    )


def _is_turnover(a) -> bool:
    return _typ(a) == "turnover"


def _is_period_end(a) -> bool:
    return _typ(a) == "period" and _sub(a) == "end"


def _is_period_start(a) -> bool:
    return _typ(a) == "period" and _sub(a) == "start"


def rebound_kind(a, last_shot_team: str | None) -> str | None:
    """Return 'offensive' | 'defensive' | None."""
    if _typ(a) != "rebound":
        return None
    desc = a.get("description") or ""
    team = _team(a)
    m = OFF_DEF_RE.search(desc)
    if m and last_shot_team and team:
        # Off count in the description is the player's season total, not a flag.
        # Use team vs shooter.
        if team == last_shot_team:
            return "offensive"
        return "defensive"
    if last_shot_team and team:
        return "offensive" if team == last_shot_team else "defensive"
    if "off:" in desc.lower() and team is None:
        return None
    # Team rebound without tricode: "Rockets Rebound" after a miss is usually defensive.
    if "rebound" in desc.lower() and last_shot_team:
        # If description contains the shooting team's code, offensive; else defensive.
        if last_shot_team.lower() in desc.lower():
            return "offensive"
        return "defensive"
    return "defensive" if last_shot_team else None


def build_possessions(nba_game_id: str, actions: list[dict]) -> tuple[list[dict], dict]:
    """Return (possession rows, validation issues)."""
    issues = {
        "unmapped_action_types": {},
        "impossible_score_jumps": 0,
        "nonmonotonic_clock": 0,
        "open_possession_at_end": 0,
    }
    poss = []
    seq = 0
    current = None
    last_shot_team = None
    last_clock = {}  # period -> remaining
    known_types = {
        "made shot",
        "missed shot",
        "rebound",
        "turnover",
        "foul",
        "free throw",
        "substitution",
        "timeout",
        "violation",
        "jump ball",
        "instant replay",
        "period",
        "heave",
        "",
    }

    def close(end_idx, result, pts=0, end_team=None):
        nonlocal current, seq
        if current is None:
            return
        a0 = actions[current["start_idx"]]
        a1 = actions[end_idx]
        sh0, sa0 = current["home_score_start"], current["away_score_start"]
        sh1 = a1.get("score_home") if a1.get("score_home") is not None else sh0
        sa1 = a1.get("score_away") if a1.get("score_away") is not None else sa0
        try:
            sh1 = int(sh1)
            sa1 = int(sa1)
        except (TypeError, ValueError):
            sh1, sa1 = sh0, sa0
        jump = abs((sh1 + sa1) - (sh0 + sa0))
        if jump > 4:
            issues["impossible_score_jumps"] += 1
        seq += 1
        team = current["possession_team"]
        if team:
            pts_for = (sh1 - sh0) if current["team_is_home"] is True else (
                (sa1 - sa0) if current["team_is_home"] is False else pts
            )
        else:
            pts_for = pts
        poss.append(
            {
                "nba_game_id": nba_game_id,
                "possession_id": f"{nba_game_id}|{seq:04d}",
                "possession_sequence": seq,
                "period": current["period"],
                "start_idx": current["start_idx"],
                "end_idx": end_idx,
                "official_clock_start": a0.get("clock"),
                "official_clock_end": a1.get("clock"),
                "remaining_start_s": a0.get("remaining_s"),
                "remaining_end_s": a1.get("remaining_s"),
                "elapsed_start_s": a0.get("elapsed_s"),
                "elapsed_end_s": a1.get("elapsed_s"),
                "wall_start_ts": a0.get("modeled_wall_ts"),
                "wall_end_ts": a1.get("modeled_wall_ts"),
                "wall_start_source": "DERIVED_PROXY" if a0.get("modeled_wall_ts") else None,
                "wall_end_source": "DERIVED_PROXY" if a1.get("modeled_wall_ts") else None,
                "home_score_start": sh0,
                "away_score_start": sa0,
                "home_score_end": sh1,
                "away_score_end": sa1,
                "score_differential_start": current["diff_start"],
                "score_differential_end": None,
                "possession_team": team,
                "possession_result": result,
                "points_scored": int(pts_for) if pts_for is not None else 0,
                "field_goal_attempt": current["fga"],
                "field_goal_made": current["fgm"],
                "turnover": 1 if result == "turnover" else 0,
                "offensive_rebound": current["oreb"],
                "defensive_rebound": 1 if result == "defensive_rebound" else 0,
                "shooting_foul": current["s_foul"],
                "non_shooting_foul": current["ns_foul"],
                "free_throw_attempts": current["fta"],
                "free_throws_made": current["ftm"],
                "timeout": current["timeout"],
                "lead_change": 0,
            }
        )
        current = None

    def open_poss(i, team, team_is_home, period, sh, sa):
        nonlocal current
        diff = None
        if team_is_home is True:
            diff = sh - sa
        elif team_is_home is False:
            diff = sa - sh
        current = {
            "start_idx": i,
            "period": period,
            "possession_team": team,
            "team_is_home": team_is_home,
            "home_score_start": sh,
            "away_score_start": sa,
            "diff_start": diff,
            "fga": 0,
            "fgm": 0,
            "oreb": 0,
            "s_foul": 0,
            "ns_foul": 0,
            "fta": 0,
            "ftm": 0,
            "timeout": 0,
        }

    home_tri = None
    away_tri = None
    # Infer home/away from location + first scoring teams if needed later.
    for i, a in enumerate(actions):
        typ = _typ(a)
        if typ not in known_types:
            issues["unmapped_action_types"][typ] = issues["unmapped_action_types"].get(typ, 0) + 1
        period = a.get("period")
        rem = a.get("remaining_s")
        if period is not None and rem is not None:
            prev = last_clock.get(period)
            if prev is not None and rem > prev + 1.5:
                issues["nonmonotonic_clock"] += 1
            last_clock[period] = rem
        sh = int(a.get("score_home") or 0)
        sa = int(a.get("score_away") or 0)
        team = _team(a)
        loc = (a.get("location") or "").lower()
        if team and loc == "h" and home_tri is None:
            home_tri = team
        if team and loc == "v" and away_tri is None:
            away_tri = team

        def team_is_home(t):
            if t is None:
                return None
            if home_tri and t == home_tri:
                return True
            if away_tri and t == away_tri:
                return False
            if loc == "h":
                return True
            if loc == "v":
                return False
            return None

        if _is_period_start(a):
            if current is not None:
                close(i, "period_boundary")
            continue
        if _is_period_end(a):
            close(i, "period_end")
            last_shot_team = None
            continue
        if typ == "jump ball" and current is None and team:
            open_poss(i, team, team_is_home(team), period, sh, sa)
            continue

        if current is None:
            # Infer start from first offensive-looking event.
            if team and typ in ("made shot", "missed shot", "free throw", "turnover", "foul"):
                open_poss(i, team, team_is_home(team), period, sh, sa)
            elif team and typ == "rebound":
                open_poss(i, team, team_is_home(team), period, sh, sa)

        if current is None:
            continue

        if typ == "timeout":
            current["timeout"] += 1
        if typ == "foul":
            if "shooting" in _sub(a):
                current["s_foul"] += 1
            else:
                current["ns_foul"] += 1
        if typ == "free throw":
            current["fta"] += 1
            desc = (a.get("description") or "").lower()
            if "miss" not in desc and str(a.get("shotResult") or "").lower() != "missed":
                # Made FT often has empty shotResult; pointsTotal or score change.
                current["ftm"] += 1

        if _is_made_fg(a):
            current["fga"] += 1
            current["fgm"] += 1
            last_shot_team = team or current["possession_team"]
            # Peek: shooting foul / 1 of 1 FT keeps possession open.
            peek = actions[i + 1] if i + 1 < len(actions) else None
            and_one = False
            if peek and _typ(peek) == "foul" and "shooting" in _sub(peek):
                and_one = True
            if peek and _typ(peek) == "free throw" and "1 of 1" in _sub(peek):
                and_one = True
            if not and_one:
                close(i, "made_fg", pts=int(a.get("shotValue") or a.get("pointsTotal") or 0))
                last_shot_team = None
            continue

        if _is_missed_fg(a):
            current["fga"] += 1
            last_shot_team = team or current["possession_team"]
            continue

        if _typ(a) == "rebound":
            kind = rebound_kind(a, last_shot_team or current["possession_team"])
            if kind == "offensive":
                current["oreb"] += 1
            elif kind == "defensive":
                close(i, "defensive_rebound")
                last_shot_team = None
                # New possession for rebound team.
                if team:
                    open_poss(i, team, team_is_home(team), period, sh, sa)
            continue

        if _is_turnover(a):
            close(i, "turnover")
            last_shot_team = None
            continue

    if current is not None:
        issues["open_possession_at_end"] += 1
        close(len(actions) - 1, "game_end_open")

    # Fill score_differential_end and lead_change vs start.
    for p in poss:
        team = p["possession_team"]
        # differential from home-away at end is not signed for team unless we know home.
        p["score_differential_end"] = (p["home_score_end"] or 0) - (p["away_score_end"] or 0)
        d0 = p.get("score_differential_start")
        d1 = p.get("score_differential_end")
        if d0 is not None and d1 is not None:
            # lead change in home-away space (unsigned team). Flag if sign flip and not 0->0.
            if d0 * d1 < 0:
                p["lead_change"] = 1
    issues["n_possessions"] = len(poss)
    issues["duplicate_ids"] = len(poss) - len({p["possession_id"] for p in poss})
    return poss, issues
