"""Monte Carlo remaining-possession simulator. Explicit, auditable assumptions."""

from __future__ import annotations

import numpy as np
import pandas as pd

from terminal_efficiency.config import LeagueConfig
from terminal_efficiency.models.metrics import probability_metrics
from terminal_efficiency.validation.temporal_split import val_mask

# Assumptions (documented; not late-game foul theater):
# 1. Remaining possessions ~ Poisson(est_possessions_remaining) with floor 0.
# 2. Each possession: offense scores 0/2/3 with probabilities from prior eFG/ortg.
# 3. Home/away offense uses that team's prior ortg vs opponent prior drtg.
# 4. If time remains after simulated possessions hit 0 and scores tied, one extra
#    possession pair (home then away) — not a full OT model.
# 5. No foul/bonus, no timeout, no lineup.

DEFAULT_POINTS_PMF = {0: 0.55, 2: 0.35, 3: 0.10}


def _points_pmf(ortg: float | None, opp_drtg: float | None) -> dict[int, float]:
    if ortg is None:
        return dict(DEFAULT_POINTS_PMF)
    # Typical possessions score ~1.05–1.20 pts at 105–120 ORTG
    exp = max(0.7, min(1.35, (ortg / 100.0) * (100.0 / (opp_drtg or 110.0))))
    p3 = min(0.2, max(0.05, 0.08 + (exp - 1.0) * 0.08))
    p2 = min(0.5, max(0.2, exp - 3 * p3))
    p0 = max(0.2, 1.0 - p2 - p3)
    s = p0 + p2 + p3
    return {0: p0 / s, 2: p2 / s, 3: p3 / s}


def _sample_points(rng: np.random.Generator, pmf: dict[int, float]) -> int:
    keys = np.array(list(pmf.keys()))
    probs = np.array(list(pmf.values()), dtype=float)
    return int(rng.choice(keys, p=probs))


def simulate_row(row: dict, cfg: LeagueConfig, rng: np.random.Generator) -> dict:
    hs = int(row.get("home_score") or 0)
    aws = int(row.get("away_score") or 0)
    n_hat = row.get("est_possessions_remaining")
    if n_hat is None:
        srg = float(row.get("seconds_remaining_game") or 0)
        pace = float(row.get("home_pace_pre") or 100)
        n_hat = srg / 60.0 * (pace / cfg.pace_minutes)
    n_hat = max(0.0, float(n_hat))
    n_poss = int(rng.poisson(n_hat)) if n_hat > 0 else 0
    home_pmf = _points_pmf(row.get("home_ortg_pre"), row.get("away_drtg_pre"))
    away_pmf = _points_pmf(row.get("away_ortg_pre"), row.get("home_drtg_pre"))
    poss_home = row.get("possession_home")
    home_ball = bool(poss_home == 1) if poss_home is not None else True
    scores = []
    for _ in range(n_poss):
        if home_ball:
            hs += _sample_points(rng, home_pmf)
        else:
            aws += _sample_points(rng, away_pmf)
        home_ball = not home_ball
    if hs == aws:
        # one extra pair; do not invent a full OT distribution
        if home_ball:
            hs += _sample_points(rng, home_pmf)
            aws += _sample_points(rng, away_pmf)
        else:
            aws += _sample_points(rng, away_pmf)
            hs += _sample_points(rng, home_pmf)
    return {"home": hs, "away": aws, "diff": hs - aws, "home_win": hs > aws}


def mcd_probability(row: dict, cfg: LeagueConfig) -> dict:
    rng = np.random.default_rng(int(cfg.mcd_seed) + hash(str(row.get("observation_id"))) % 10_000)
    wins = 0
    diffs = []
    terminals = []
    for _ in range(cfg.n_mcd_simulations):
        s = simulate_row(row, cfg, rng)
        wins += int(s["home_win"])
        diffs.append(s["diff"])
        terminals.append((s["home"], s["away"]))
    p = wins / cfg.n_mcd_simulations
    return {
        "mcd_home_win_probability": p,
        "mcd_away_win_probability": 1.0 - p,
        "mcd_expected_final_diff": float(np.mean(diffs)),
        "n_simulations": cfg.n_mcd_simulations,
    }


def evaluate_mcd_on_val(obs: pd.DataFrame, cfg: LeagueConfig, *, max_rows: int = 800) -> dict:
    val = obs[val_mask(obs)].dropna(subset=["final_home_win"])
    if len(val) > max_rows:
        val = val.sample(max_rows, random_state=cfg.mcd_seed)
    ps = []
    ys = []
    for r in val.to_dict("records"):
        out = mcd_probability(r, cfg)
        ps.append(out["mcd_home_win_probability"])
        ys.append(int(r["final_home_win"]))
    p = np.array(ps)
    y = np.array(ys)
    return {
        "object": "MCD",
        "val": probability_metrics(y, p),
        "n_evaluated": int(len(y)),
        "n_simulations": cfg.n_mcd_simulations,
        "assumptions": [
            "Poisson remaining possessions from prior pace",
            "0/2/3 point PMF from prior ORTG vs opponent DRTG",
            "No foul/bonus/timeout model",
            "Tied leftover: one extra possession pair only",
        ],
    }
