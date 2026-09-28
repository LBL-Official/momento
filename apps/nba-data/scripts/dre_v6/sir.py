"""Attach Δα_state and trade-level mean_SIR / mean_M0_residual from persisted maps."""

from __future__ import annotations

import numpy as np
import pandas as pd

from . import config as C
from . import maps as M


def attach_state(df: pd.DataFrame, maps: dict) -> pd.DataFrame:
    recs = df.to_dict("records")
    a0, a1 = [], []
    for r in recs:
        p = r.get("price_bin_5")
        a0.append(M.predict_m0(p, maps))
        a1.append(M.predict_m1(p, r.get("score_bin_l1"), r.get("clock_bin_l1"), r.get("n_hat_bin_l1"), maps))
    out = df.copy()
    out["alpha_m0"] = a0
    out["alpha_m1"] = a1
    out["da_state"] = out["alpha_m1"] - out["alpha_m0"]
    out["r_t"] = out["pi_terminal"] - out["alpha_m0"]
    out["da_state_note"] = "M1_TRAIN(P,X) - M0_TRAIN(P)"
    out["r_t_label"] = C.OCCUPANCY_LABEL
    return out


def trade_table(df: pd.DataFrame) -> pd.DataFrame:
    xs = df[df["pi_terminal"].notna() & df["da_state"].notna()].copy()
    if xs.empty:
        return pd.DataFrame()
    g = xs.groupby("trade_id", sort=False)
    tab = g.agg(
        event_id=("event_id", "first"),
        dataset_split=("dataset_split", "first"),
        T_i=("da_state", "size"),
        mean_sir=("da_state", "mean"),
        mean_alpha_m0=("alpha_m0", "mean"),
        mean_alpha_m1=("alpha_m1", "mean"),
        pi_terminal=("pi_terminal", "first"),
        y_settle_yes=("y_settle_yes", "first"),
    ).reset_index()
    tab["mean_r"] = tab["pi_terminal"] - tab["mean_alpha_m0"]
    tab["abs_mean_sir"] = tab["mean_sir"].abs()
    tab["weighting"] = C.SURFACE_WEIGHTING_PRIMARY
    tab["note"] = "mean_SIR_i = mean_t (M1-M0); mean_R_i = Pi - mean_t M0"
    return tab


def split_trades(trades: pd.DataFrame, split: str) -> pd.DataFrame:
    return trades[trades["dataset_split"] == split].copy()


def quantile_dict(vals: np.ndarray) -> dict:
    if len(vals) == 0:
        return {}
    qs = (0.01, 0.05, 0.10, 0.25, 0.50, 0.75, 0.90, 0.95, 0.99)
    out = {f"p{int(q*100):02d}": float(np.quantile(vals, q)) for q in qs}
    out["mean"] = float(vals.mean())
    out["median"] = float(np.median(vals))
    out["std"] = float(vals.std(ddof=1)) if len(vals) > 1 else 0.0
    out["min"] = float(vals.min())
    out["max"] = float(vals.max())
    out["max_abs"] = float(np.max(np.abs(vals)))
    return out
