"""Cluster disclosure. N observations ≠ N independent games."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from roller.results_math.models import DERIVED, OBSERVED, UNAVAILABLE
from roller.results_math.versions import MIN_CLUSTER_UNITS


def cluster_readiness(n_units: int, n_obs: int, *, unit: str) -> dict[str, Any]:
    """Whether a cluster interval is a distinct inferential object."""
    if n_units < MIN_CLUSTER_UNITS:
        return {
            "status": UNAVAILABLE,
            "unit": unit,
            "n_units": n_units,
            "n_observations": n_obs,
            "reason": f"UNAVAILABLE · N < minimum ({MIN_CLUSTER_UNITS} {unit}s)",
        }
    if n_units == n_obs:
        return {
            "status": "COINCIDENT",
            "unit": unit,
            "n_units": n_units,
            "n_observations": n_obs,
            "reason": (
                f"{unit.upper()}-CLUSTER RESULT COINCIDES WITH OBSERVATION RESULT · "
                f"ONE OBSERVATION PER {unit.upper()}"
            ),
        }
    return {
        "status": DERIVED,
        "unit": unit,
        "n_units": n_units,
        "n_observations": n_obs,
        "reason": f"{n_obs} observations from {n_units} {unit}s · not {n_obs} independent experiments",
    }


def cluster_info(obs: list[dict[str, Any]]) -> dict[str, Any]:
    games: set[str] = set()
    tickers: set[str] = set()
    dates: set[str] = set()
    by_game: dict[str, list[int]] = defaultdict(list)
    by_date: dict[str, list[int]] = defaultdict(list)
    n_returns = 0
    for r in obs:
        gid = r.get("game_id")
        ret = r.get("return_cents")
        if ret is not None:
            n_returns += 1
        if gid:
            games.add(str(gid))
            if ret is not None:
                by_game[str(gid)].append(float(ret))
        if r.get("ticker"):
            tickers.add(str(r["ticker"]))
        ts = str(r.get("observation_ts") or r.get("date") or "")
        if ts:
            day = ts[:10]
            dates.add(day)
            if ret is not None:
                by_date[day].append(float(ret))
    game_groups = [v for v in by_game.values() if v]
    date_groups = [v for v in by_date.values() if v]

    def _sizes(groups: list[list[float]]) -> dict[str, Any]:
        sizes = [len(g) for g in groups]
        return {
            "n_clusters": len(sizes),
            "mean_observations_per_cluster": (sum(sizes) / len(sizes)) if sizes else None,
            "max_observations_per_cluster": max(sizes) if sizes else 0,
            "min_observations_per_cluster": min(sizes) if sizes else 0,
        }

    game_ready = cluster_readiness(len(game_groups), n_returns, unit="game")
    date_ready = cluster_readiness(len(date_groups), n_returns, unit="date")
    game_ready.update(_sizes(game_groups))
    date_ready.update(_sizes(date_groups))
    one_per_game = n_returns > 0 and len(game_groups) == n_returns
    return {
        "status": OBSERVED,
        "n_observations": len(obs),
        "n_returns": n_returns,
        "n_games": len(games),
        "n_tickers": len(tickers),
        "n_dates": len(dates),
        "cluster_type": "internal_game_id",
        "one_observation_per_game": one_per_game,
        "multiple_observations_per_game": bool(game_groups) and not one_per_game,
        "game_cluster": game_ready,
        "date_cluster": date_ready,
        "note": "N observations is not N independent experiments when games or dates repeat.",
        "return_groups": game_groups,
        "date_return_groups": date_groups,
    }
