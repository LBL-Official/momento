"""Workstream 2 — prior-informed expected remaining possessions.

Lock 6: one 03_possessions row = one offensive possession.
R_x = pace_A1 + pace_A2.
A team's pace for game G uses only games whose terminal completion
(max wall_end_ts, timeActual) is strictly before G began (min wall_start_ts).
Same-day games are excluded unless that inequality holds.
Never uses actual_remaining_possessions.
"""

from __future__ import annotations

from collections import defaultdict

import numpy as np
import pandas as pd

from . import config as C


def _game_bounds(poss: pd.DataFrame) -> pd.DataFrame:
    g = poss.groupby("nba_game_id", as_index=False).agg(
        game_start_ts=("wall_start_ts", "min"),
        game_completion_ts=("wall_end_ts", "max"),
        n_possessions=("possession_index", "size"),
    )
    return g


def _team_game_pace(poss: pd.DataFrame) -> pd.DataFrame:
    tg = (
        poss.dropna(subset=["offensive_team"])
        .groupby(["nba_game_id", "offensive_team"], as_index=False)
        .size()
        .rename(columns={"size": "team_poss_in_game"})
    )
    return tg


def build_priors(poss: pd.DataFrame, panel: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Per-game prior pace for every FIRST-80 matched game (and extras in possessions)."""
    bounds = _game_bounds(poss)
    tg = _team_game_pace(poss)
    tg = tg.merge(bounds, on="nba_game_id", how="left")

    split_map = (
        panel.dropna(subset=["nba_game_id"])
        .groupby("nba_game_id")["dataset_split"]
        .first()
        .to_dict()
    )
    date_map = (
        panel.dropna(subset=["nba_game_id"])
        .groupby("nba_game_id")["game_date"]
        .first()
        .to_dict()
    )
    team_map = (
        panel.dropna(subset=["nba_game_id"])
        .groupby("nba_game_id")
        .agg(A1_team=("A1_team", "first"), A2_team=("A2_team", "first"))
    )

    tg["dataset_split"] = tg["nba_game_id"].map(split_map)
    tg["game_date"] = tg["nba_game_id"].map(date_map)

    train_pace = tg.loc[tg["dataset_split"] == "TRAIN", "team_poss_in_game"]
    league_mean = float(train_pace.mean()) if len(train_pace) else float(tg["team_poss_in_game"].mean())

    by_team: dict[str, list[dict]] = defaultdict(list)
    for r in tg.to_dict("records"):
        by_team[str(r["offensive_team"])].append(r)
    for team in by_team:
        by_team[team].sort(key=lambda x: (x["game_completion_ts"] is None, x["game_completion_ts"] or 0))

    rows = []
    n_fallback = 0
    n_same_day_included = 0
    n_same_day_excluded = 0
    for gid, meta in bounds.set_index("nba_game_id").iterrows():
        start = meta["game_start_ts"]
        a1 = None if gid not in team_map.index else team_map.loc[gid, "A1_team"]
        a2 = None if gid not in team_map.index else team_map.loc[gid, "A2_team"]
        gdate = date_map.get(gid)

        def pace_for(team: str | None) -> tuple[float, int, int, str]:
            nonlocal n_fallback, n_same_day_included, n_same_day_excluded
            if not team or team not in by_team or start is None or not np.isfinite(start):
                n_fallback += 1
                return league_mean, 0, 0, "TRAIN_LEAGUE_MEAN"
            eligible = []
            same_day_in = 0
            same_day_out = 0
            for rec in by_team[team]:
                if rec["nba_game_id"] == gid:
                    continue
                end = rec.get("game_completion_ts")
                if end is None or not np.isfinite(end):
                    continue
                if not (float(end) < float(start)):
                    if rec.get("game_date") == gdate and gdate is not None:
                        same_day_out += 1
                    continue
                if rec.get("game_date") == gdate and gdate is not None:
                    same_day_in += 1
                eligible.append(rec)
            n_same_day_included += same_day_in
            n_same_day_excluded += same_day_out
            eligible.sort(key=lambda x: float(x["game_completion_ts"]), reverse=True)
            take = eligible[: C.PACE_K]
            if len(take) >= C.PACE_MIN_GAMES:
                return float(np.mean([x["team_poss_in_game"] for x in take])), len(take), len(eligible), "ROLLING_PRIOR"
            n_fallback += 1
            return league_mean, len(take), len(eligible), "TRAIN_LEAGUE_MEAN"

        p1, k1, n1, s1 = pace_for(None if a1 is None or (isinstance(a1, float) and np.isnan(a1)) else str(a1))
        p2, k2, n2, s2 = pace_for(None if a2 is None or (isinstance(a2, float) and np.isnan(a2)) else str(a2))
        rx = p1 + p2
        rows.append(
            {
                "nba_game_id": gid,
                "dataset_split": split_map.get(gid),
                "game_date": gdate,
                "game_start_ts": start,
                "game_completion_ts": meta["game_completion_ts"],
                "A1_team": None if a1 is None or (isinstance(a1, float) and np.isnan(a1)) else str(a1),
                "A2_team": None if a2 is None or (isinstance(a2, float) and np.isnan(a2)) else str(a2),
                "pace_a1_prior": p1,
                "pace_a2_prior": p2,
                "r_x_prior": rx,
                "pace_a1_n_used": k1,
                "pace_a2_n_used": k2,
                "pace_a1_n_eligible": n1,
                "pace_a2_n_eligible": n2,
                "pace_a1_source": s1,
                "pace_a2_source": s2,
                "rx_identity": C.PACE_RX_IDENTITY,
                "chronology": C.PACE_CHRONOLOGY,
                "timestamp_field_start": "min(wall_start_ts) of 03_possessions (timeActual)",
                "timestamp_field_completion": "max(wall_end_ts) of 03_possessions (timeActual)",
                "note": "Prior-informed expected TOTAL possessions. Not observed remaining.",
            }
        )

    priors = pd.DataFrame(rows)
    audit = {
        "possession_row_is_one_offensive_possession": True,
        "rx_identity": C.PACE_RX_IDENTITY,
        "chronology": C.PACE_CHRONOLOGY,
        "k": C.PACE_K,
        "min_games": C.PACE_MIN_GAMES,
        "train_league_mean_team_poss": league_mean,
        "n_games": int(len(priors)),
        "r_x": {
            "n": int(priors["r_x_prior"].notna().sum()),
            "mean": float(priors["r_x_prior"].mean()) if len(priors) else None,
            "median": float(priors["r_x_prior"].median()) if len(priors) else None,
            "p10": float(priors["r_x_prior"].quantile(0.10)) if len(priors) else None,
            "p90": float(priors["r_x_prior"].quantile(0.90)) if len(priors) else None,
        },
        "fallback_team_pace_calls": n_fallback,
        "same_day_included_via_earlier_completion": n_same_day_included,
        "same_day_excluded_no_earlier_completion": n_same_day_excluded,
        "identity_illustration_352_used": False,
        "actual_remaining_used_as_feature": False,
    }
    return priors, audit


def attach_n_hat(panel: pd.DataFrame, priors: pd.DataFrame) -> pd.DataFrame:
    df = panel.merge(
        priors[
            [
                "nba_game_id",
                "pace_a1_prior",
                "pace_a2_prior",
                "r_x_prior",
                "pace_a1_source",
                "pace_a2_source",
                "game_start_ts",
                "game_completion_ts",
            ]
        ],
        on="nba_game_id",
        how="left",
    )
    pidx = pd.to_numeric(df["possession_index"], errors="coerce")
    rx = pd.to_numeric(df["r_x_prior"], errors="coerce")
    # n_hat_remaining_prior = max(0, R_x - possession_index).
    # Not a predicted possession index. R_x is estimated total game possessions.
    df["n_hat_remaining_prior"] = np.maximum(0.0, rx - pidx)
    return df
