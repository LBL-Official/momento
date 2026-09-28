"""Families A–D at t_s. No post-entry ticks. No Family E."""

from __future__ import annotations

import numpy as np
import pandas as pd

from roller.nba_path_fe.config import DEFAULT, PathFeConfig
from roller.nba_path_fe.errors import PathFeError
from roller.nba_path_fe.episodes import opposite_market_id
from roller.nba_path_fe.registry import enter_skip_names, load_registry
from roller.nba_path_fe.state_fair import StateFairModel, apply_state_fair, fit_state_fair


def _window(ticks: pd.DataFrame, rec, minutes: int) -> pd.DataFrame:
    lo = int(rec.t_s) - minutes
    return ticks.loc[
        (ticks["game_id"] == rec.game_id)
        & (ticks["market_id"] == rec.market_id)
        & (ticks["t"] >= lo)
        & (ticks["t"] <= int(rec.t_s))
    ].sort_values("t")


def _clock_bucket(sec_left) -> float:
    if sec_left is None or (isinstance(sec_left, float) and sec_left != sec_left) or pd.isna(sec_left):
        return float("nan")
    sec_left = int(sec_left)
    if sec_left >= 540:
        return 0
    if sec_left >= 360:
        return 1
    if sec_left >= 180:
        return 2
    return 3


def _path_features(ticks: pd.DataFrame, rec) -> dict:
    w5 = _window(ticks, rec, 5)
    w1 = _window(ticks, rec, 1)
    bids5 = w5["yes_bid"].astype(int).to_numpy()
    bids1 = w1["yes_bid"].astype(int).to_numpy()
    rise5 = float(bids5[-1] - bids5[0]) if len(bids5) >= 2 else 0.0
    rise1 = float(bids1[-1] - bids1[0]) if len(bids1) >= 2 else 0.0
    vr = rise1 / rise5 if abs(rise5) > 1e-9 else (rise1 if rise1 != 0 else 0.0)
    gaps = np.diff(bids5) if len(bids5) >= 2 else np.array([0.0])
    max_up = float(np.max(gaps)) if gaps.size else 0.0
    n_rebids = int(np.sum(gaps > 0))
    tip_t = 0
    time_to_80 = float((int(rec.t_s) - tip_t) * 60)
    return {
        "time_to_80_sec": time_to_80,
        "velocity_ratio_1_5": float(vr),
        "max_uptick_gap_5m": max_up,
        "overshoot_cents": float(int(rec.p_ts) - 80),
        "n_rebids_5m": float(n_rebids),
    }


def _book_at(ticks: pd.DataFrame, game_id: str, market_id: str, t_s: int) -> tuple[float | None, float | None]:
    row = ticks.loc[
        (ticks["game_id"] == game_id) & (ticks["market_id"] == market_id) & (ticks["t"] == t_s)
    ]
    if row.empty:
        return None, None
    r = row.iloc[0]
    spread = None if pd.isna(r["spread"]) else float(r["spread"])
    size = None if pd.isna(r["size_bid"]) else float(r["size_bid"])
    return spread, size


def build_enter_features(
    episodes: pd.DataFrame,
    ticks: pd.DataFrame,
    labels: pd.DataFrame,
    cfg: PathFeConfig = DEFAULT,
) -> tuple[pd.DataFrame, dict]:
    """PIT enter/skip matrix + state-fair models keyed by season."""
    load_registry()
    models: dict[int, StateFairModel] = {}
    for season in sorted(episodes["season"].unique()):
        season = int(season)
        try:
            models[season] = fit_state_fair(episodes, labels, season, cfg)
        except PathFeError:
            continue
    if not models:
        # bootstrap: fit on all filled except current game is handled at apply time;
        # first season has no prior — mark state_fair unavailable via NaN, not 0.
        pass
    rows: list[dict] = []
    for rec in episodes.itertuples(index=False):
        path_f = _path_features(ticks, rec)
        spread_own = None if pd.isna(rec.spread_own) else float(rec.spread_own)
        size_own = None if pd.isna(rec.size_own_bid) else float(rec.size_own_bid)
        opp_id = None if pd.isna(getattr(rec, "opposite_market_id", None)) else str(rec.opposite_market_id)
        if opp_id is None:
            try:
                opp_id = opposite_market_id(str(rec.market_id))
            except PathFeError:
                opp_id = None
        spread_opp, size_opp = (None, None)
        if opp_id is not None:
            spread_opp, size_opp = _book_at(ticks, str(rec.game_id), opp_id, int(rec.t_s))
        l2_missing = int(
            size_own is None
            or size_opp is None
            or rec.book_source in {"SOURCE_UNAVAILABLE", "MISSING"}
        )
        book_missing = l2_missing
        model = models.get(int(rec.season))
        if model is None:
            state_fair = np.nan
        else:
            state_fair = float(apply_state_fair(pd.DataFrame([rec._asdict()]), model).iloc[0])
        p_minus = float(rec.p_ts) - state_fair if not np.isnan(state_fair) else np.nan
        abs_pm = abs(p_minus) if not np.isnan(p_minus) else np.nan
        so = np.nan if spread_own is None else float(spread_own)
        sop = np.nan if spread_opp is None else float(spread_opp)
        rows.append(
            {
                "episode_id": rec.episode_id,
                "game_id": rec.game_id,
                "era": rec.era,
                "season": int(rec.season),
                "timestamp_utc": rec.timestamp_utc,
                "t_s": int(rec.t_s),
                "period": rec.period if rec.period is not None and not pd.isna(rec.period) else np.nan,
                "clock_bucket": _clock_bucket(rec.sec_left_period),
                "rest_days": float(rec.rest_days) if pd.notna(rec.rest_days) else np.nan,
                **path_f,
                "spread_own": so,
                "spread_opp": sop,
                "size_own_bid": np.nan if size_own is None else float(size_own),
                "size_opp_bid": np.nan if size_opp is None else float(size_opp),
                "book_features_missing": float(book_missing),
                "state_fair_price": state_fair,
                "price_minus_state_fair": p_minus,
                "abs_price_minus_state_fair": abs_pm,
                "impulse_x_disagreement": (
                    float(path_f["velocity_ratio_1_5"]) * max(0.0, p_minus) if not np.isnan(p_minus) else np.nan
                ),
                "thin_x_disagreement": (
                    (float(so) + float(sop)) * abs_pm
                    if not np.isnan(so) and not np.isnan(sop) and not np.isnan(abs_pm)
                    else np.nan
                ),
                "state_fair_version": cfg.state_fair_version if model is not None else None,
                "state_fair_trained_through": model.trained_through_season if model is not None else None,
            }
        )
    feat = pd.DataFrame(rows)
    names = enter_skip_names()
    missing_cols = [c for c in names if c not in feat.columns]
    if missing_cols:
        raise PathFeError("FEATURE_CONTRACT", f"missing columns {missing_cols}")
    return feat, {s: {"version": m.version, "through": m.trained_through_season} for s, m in models.items()}
