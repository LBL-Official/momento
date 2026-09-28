"""Versioned f_ν. Prior-season games only. PIT score/clock. Not a live quote."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from roller.nba_path_fe.config import DEFAULT, PathFeConfig
from roller.nba_path_fe.errors import PathFeError
from roller.nba_path_fe.mathutil import fit_logistic, predict_logistic


@dataclass
class StateFairModel:
    version: str
    weights: np.ndarray
    columns: tuple[str, ...]
    trained_through_season: int
    possession_used: bool


def _score_diff(rec) -> float:
    hs, aws = rec.home_score, rec.away_score
    if pd.isna(hs) or pd.isna(aws):
        return float("nan")
    if rec.side == "home":
        return float(int(hs) - int(aws))
    return float(int(aws) - int(hs))


def _design(rows: pd.DataFrame, possession_used: bool) -> np.ndarray:
    score_diff = [_score_diff(rec) for rec in rows.itertuples(index=False)]
    cols = [
        np.asarray(score_diff, dtype=float),
        pd.to_numeric(rows["sec_left_period"], errors="coerce").to_numpy() / 720.0,
        pd.to_numeric(rows["sec_left_game"], errors="coerce").to_numpy() / 2880.0,
        pd.to_numeric(rows["period"], errors="coerce").to_numpy(),
    ]
    if possession_used:
        poss = rows["possession"].to_numpy()
        miss = pd.isna(rows["possession"]).to_numpy()
        filled = np.where(miss, 0.0, poss.astype(float))
        cols.append(filled)
        cols.append(miss.astype(float))
    return np.column_stack(cols)


def fit_state_fair(
    episodes: pd.DataFrame,
    labels: pd.DataFrame,
    season: int,
    cfg: PathFeConfig = DEFAULT,
) -> StateFairModel:
    """Train on episodes with season < `season` (previous seasons only). Target = S."""
    merged = episodes.merge(labels[["episode_id", "S", "filled"]], on="episode_id", how="inner")
    hist = merged.loc[(merged["season"] < season) & (merged["filled"] == 1)].copy()
    if len(hist) < 40:
        raise PathFeError("STATE_FAIR_DATA_REQUIRED", f"need prior-season filled rows, got {len(hist)}")
    possession_used = bool(hist["possession"].notna().mean() >= 0.5)
    x = _design(hist, possession_used)
    ok = np.isfinite(x).all(axis=1)
    hist = hist.loc[ok]
    x = x[ok]
    if len(hist) < 40:
        raise PathFeError("STATE_FAIR_DATA_REQUIRED", f"need finite prior-state rows, got {len(hist)}")
    y = hist["S"].astype(int).to_numpy()
    w = fit_logistic(x, y, l2=0.5)
    cols = ("score_diff", "sec_left_period_n", "sec_left_game_n", "period")
    if possession_used:
        cols = cols + ("possession", "possession_missing")
    through = season - 1
    if season >= 202001:
        y, m = divmod(int(season), 100)
        through = (y - 1) * 100 + 12 if m <= 1 else y * 100 + (m - 1)
    return StateFairModel(
        version=cfg.state_fair_version,
        weights=w,
        columns=cols,
        trained_through_season=through,
        possession_used=possession_used,
    )


def apply_state_fair(episodes: pd.DataFrame, model: StateFairModel) -> pd.Series:
    x = _design(episodes, model.possession_used)
    p = predict_logistic(x, model.weights)
    return pd.Series(np.clip(p * 100.0, 0.0, 100.0), index=episodes.index, name="state_fair_price")
