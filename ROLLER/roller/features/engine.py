"""Shift-then-roll team feature engine. Order by result_available_at."""

from __future__ import annotations

from datetime import datetime

from roller.timeutil import parse_utc


def win_pct_e4(wins: int, games: int) -> str:
    if games <= 0:
        return ""
    return str((wins * 10000) // games)


def rest_days(prev_date: str | None, game_date: str | None) -> str:
    if not prev_date or not game_date:
        return ""
    try:
        a = datetime.fromisoformat(str(prev_date)[:10])
        b = datetime.fromisoformat(str(game_date)[:10])
    except ValueError:
        return ""
    return str((b - a).days)


def summarize_priors(priors: list[dict], team_id: str, windows: list[int]) -> dict:
    games_n = len(priors)
    wins = sum(1 for p in priors if p["won"])
    losses = games_n - wins
    home = [p for p in priors if p["is_home"]]
    away = [p for p in priors if not p["is_home"]]
    home_wins = sum(1 for p in home if p["won"])
    away_wins = sum(1 for p in away if p["won"])
    out = {
        "games_played_pre": games_n,
        "wins_pre": wins,
        "losses_pre": losses,
        "win_pct_pre": win_pct_e4(wins, games_n),
        "home_games_pre": len(home),
        "home_wins_pre": home_wins,
        "away_games_pre": len(away),
        "away_wins_pre": away_wins,
    }
    for w in windows:
        last = priors[-w:] if games_n else []
        lw = sum(1 for p in last if p["won"])
        out[f"wins_last_{w}_pre"] = lw
        out[f"losses_last_{w}_pre"] = len(last) - lw
    prev_date = priors[-1]["game_date"] if priors else None
    return out, prev_date


def team_appearances(game: dict) -> list[dict]:
    hw = str(game.get("home_win") or "")
    aw = str(game.get("away_win") or "")
    has_result = hw in {"0", "1"} and aw in {"0", "1"} and str(game.get("result_available_at") or "").strip()
    return [
        {
            "team_id": game["home_team_id"],
            "is_home": True,
            "won": hw == "1",
            "has_result": bool(has_result),
            "result_available_at": game.get("result_available_at") or "",
            "game_date": game.get("game_date") or "",
            "scheduled_start": game.get("scheduled_start") or "",
            "internal_game_id": game["internal_game_id"],
            "game": game,
        },
        {
            "team_id": game["away_team_id"],
            "is_home": False,
            "won": aw == "1",
            "has_result": bool(has_result),
            "result_available_at": game.get("result_available_at") or "",
            "game_date": game.get("game_date") or "",
            "scheduled_start": game.get("scheduled_start") or "",
            "internal_game_id": game["internal_game_id"],
            "game": game,
        },
    ]


def result_sort_key(app: dict):
    ts = parse_utc(app["result_available_at"]) if app.get("result_available_at") else None
    return (ts is None, ts or parse_utc(app.get("scheduled_start") or app.get("game_date")))


def appearance_cutoff(app: dict):
    """When this appearance becomes a known result, or its conservative identity time."""
    ts = parse_utc(app.get("result_available_at")) if app.get("result_available_at") else None
    if ts is not None:
        return ts
    return parse_utc(app.get("scheduled_start") or app.get("game_date"))


def priors_before(completed: list[dict], app: dict) -> list[dict]:
    """Completed appearances with result_available_at < this appearance's cutoff.

    Do not compare the (missing-first) sort tuple: a missing result sorts *after*
    every dated result, which would treat the entire rest of the season as prior.
    """
    cutoff = appearance_cutoff(app)
    if cutoff is None:
        return []
    out = []
    for prior in completed:
        if prior["internal_game_id"] == app["internal_game_id"]:
            continue
        ts = parse_utc(prior.get("result_available_at")) if prior.get("result_available_at") else None
        if ts is not None and ts < cutoff:
            out.append(prior)
    return out
