"""Cluster bootstrap primitive. Interprets as game-cluster resampling variation."""

from __future__ import annotations

import numpy as np
import pandas as pd

from . import config as C


def cluster_interval(trades: pd.DataFrame, stat_fn, min_valid: int = 20) -> dict:
    xs = trades.dropna(subset=["event_id"]).copy()
    games = xs["event_id"].dropna().unique()
    if len(games) < 10:
        return {"status": "INCONCLUSIVE", "n_games": int(len(games)), "meaning": C.SPECIFICATION_LOCKS["bootstrap"]["meaning"]}
    by_game = {g: xs[xs["event_id"] == g] for g in games}
    rng = np.random.default_rng(C.RANDOM_SEED)
    vals = []
    for _ in range(C.BOOTSTRAP_GAMES):
        draw = rng.choice(games, size=len(games), replace=True)
        boot = pd.concat([by_game[g] for g in draw], ignore_index=True)
        v = stat_fn(boot)
        if v is None or (isinstance(v, float) and not np.isfinite(v)):
            continue
        vals.append(float(v))
    if len(vals) < min_valid:
        return {"status": "INCONCLUSIVE", "n_valid": int(len(vals)), "n_games": int(len(games)),
                "meaning": C.SPECIFICATION_LOCKS["bootstrap"]["meaning"]}
    arr = np.asarray(vals, float)
    return {
        "status": "OK",
        "n_games": int(len(games)),
        "n_valid": int(len(arr)),
        "mean": float(arr.mean()),
        "p05": float(np.quantile(arr, 0.05)),
        "p95": float(np.quantile(arr, 0.95)),
        "cluster": "event_id",
        "seed": C.RANDOM_SEED,
        "meaning": C.SPECIFICATION_LOCKS["bootstrap"]["meaning"],
        "weighting": C.SURFACE_WEIGHTING_PRIMARY,
    }
