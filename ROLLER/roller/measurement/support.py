"""First-class support metadata. Observation count ≠ independent games."""

from __future__ import annotations

from typing import Any

from roller.timeutil import parse_utc


def support_object(rows: list[dict[str, Any]], *, min_unique_games: int, min_observations: int) -> dict[str, Any]:
    games = {str(r.get("internal_game_id") or "") for r in rows if r.get("internal_game_id")}
    games.discard("")
    dates = set()
    teams = set()
    seasons = set()
    times = []
    for r in rows:
        ot = parse_utc(r.get("observation_time") or r.get("response_available_at"))
        if ot is not None:
            times.append(ot)
            dates.add(ot.date().isoformat())
        if r.get("season"):
            seasons.add(str(r["season"]))
        if r.get("sport"):
            pass
        for key in ("home_team_id", "away_team_id", "team_id"):
            if r.get(key):
                teams.add(str(r[key]))
    n_obs = len(rows)
    n_games = len(games)
    repeated = n_obs > n_games
    sufficient = n_games >= min_unique_games and n_obs >= min_observations
    times_sorted = sorted(times)
    return {
        "n_observations": n_obs,
        "n_unique_games": n_games,
        "n_unique_dates": len(dates),
        "n_unique_teams": len(teams),
        "n_unique_seasons": len(seasons),
        "first_observation_time": times_sorted[0].strftime("%Y-%m-%dT%H:%M:%S") + "Z" if times_sorted else None,
        "last_observation_time": times_sorted[-1].strftime("%Y-%m-%dT%H:%M:%S") + "Z" if times_sorted else None,
        "repeated_observation_warning": repeated,
        "effective_n": None,
        "effective_n_status": "NOT_IMPLEMENTED",
        "sufficient": sufficient,
        "min_unique_games": min_unique_games,
        "min_observations": min_observations,
    }
