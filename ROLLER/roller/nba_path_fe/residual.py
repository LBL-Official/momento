"""Residual mining after state-fair + interactions. Pre-declared only. ≤2 promotions."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from roller.nba_path_fe.config import DEFAULT, PathFeConfig
from roller.nba_path_fe.mathutil import fit_logistic


PREDECLARED = (
    "log1p_time_to_80",
    "sq_velocity_ratio",
    "overshoot_x_thin",
)


def add_predeclared(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    out["log1p_time_to_80"] = np.log1p(out["time_to_80_sec"].clip(lower=0))
    out["sq_velocity_ratio"] = out["velocity_ratio_1_5"] ** 2
    thin = out["spread_own"].fillna(np.nan) + out["spread_opp"].fillna(np.nan)
    out["overshoot_x_thin"] = out["overshoot_cents"] * thin
    return out


@dataclass
class ResidualScreen:
    promoted: list[str]
    scores: dict[str, float]
    warranted: bool
    note: str


def screen_residuals(
    train: pd.DataFrame,
    y: np.ndarray,
    base_cols: list[str],
    cfg: PathFeConfig = DEFAULT,
) -> ResidualScreen:
    """Promote ≤2 predeclared transforms with |z|>=2.5 on nested train only."""
    work = add_predeclared(train)
    # residual of Y after logistic on base_cols complete case
    cols = [c for c in base_cols if c in work.columns]
    extra = [c for c in PREDECLARED if c in work.columns]
    use = work[cols + extra].copy()
    ok = use.notna().all(axis=1).to_numpy() & np.isfinite(y)
    if int(ok.sum()) < 40:
        return ResidualScreen([], {}, False, "insufficient complete rows")
    xb = use.loc[ok, cols].to_numpy(dtype=float)
    yy = y[ok]
    w = fit_logistic(xb, yy, l2=1.0)
    from roller.nba_path_fe.mathutil import predict_logistic

    pred = predict_logistic(xb, w)
    resid = yy - pred
    scores: dict[str, float] = {}
    for name in extra:
        zc = use.loc[ok, name].to_numpy(dtype=float)
        zc = (zc - zc.mean()) / (zc.std() + 1e-9)
        # correlation z
        r = float(np.corrcoef(zc, resid)[0, 1]) if zc.std() > 0 else 0.0
        z = r * np.sqrt(max(len(resid) - 2, 1)) / np.sqrt(max(1e-9, 1 - r * r))
        scores[name] = float(z)
    ranked = sorted(scores.items(), key=lambda kv: -abs(kv[1]))
    promoted = [n for n, z in ranked if abs(z) >= cfg.residual_z_min][: cfg.residual_promote_max]
    warranted = bool(promoted)
    return ResidualScreen(promoted, scores, warranted, "predeclared_only")
