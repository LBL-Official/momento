"""Mutually exclusive candle-path bins. Downside classified first when both occur."""

from __future__ import annotations

import numpy as np
import pandas as pd

from . import config as C


def assign_bin(current, fmin, fmax) -> str | None:
    if current is None or fmin is None or fmax is None:
        return None
    c = float(current)
    mn = float(fmin)
    mx = float(fmax)
    down = c - mn
    up = mx - c
    if down >= 30:
        return "EXTREME_DOWN"
    if down >= 20:
        return "SEVERE_DOWN"
    if down >= 10:
        return "MODERATE_DOWN"
    if up >= 30:
        return "EXTREME_REC"
    if up >= 20:
        return "STRONG_REC"
    if up >= 10:
        return "MODERATE_REC"
    return "STABLE"


def add_path_bins(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    for hz in C.HORIZONS:
        mins = out[f"future_min_{hz}"].to_numpy()
        maxs = out[f"future_max_{hz}"].to_numpy()
        cur = out["current_price"].to_numpy()
        bins = []
        valid = []
        for c, mn, mx in zip(cur, mins, maxs):
            if pd.isna(c) or pd.isna(mn) or pd.isna(mx):
                bins.append(None)
                valid.append(False)
            else:
                bins.append(assign_bin(c, mn, mx))
                valid.append(True)
        out[f"path_bin_{hz}"] = bins
        out[f"path_valid_{hz}"] = valid
        out[f"dd_{hz}"] = np.where(
            out[f"path_valid_{hz}"],
            np.maximum(0.0, out["current_price"] - out[f"future_min_{hz}"]),
            np.nan,
        )
        out[f"uu_{hz}"] = np.where(
            out[f"path_valid_{hz}"],
            np.maximum(0.0, out[f"future_max_{hz}"] - out["current_price"]),
            np.nan,
        )
        out[f"y_rec_ge_30_{hz}"] = np.where(
            out[f"path_valid_{hz}"],
            (out[f"future_max_{hz}"] >= out["current_price"] + 30).astype(float),
            np.nan,
        )
    out["path_bin_end"] = out["path_bin_end"]
    out["jump_label_kind"] = out.get("jump_label_kind", "CANDLE_PATH_PROXY")
    out["y_jump_40_kind"] = "CANDLE_PATH_PROXY"
    return out


def bin_frequency(df: pd.DataFrame, hz: str, split: str | None = None) -> dict:
    xs = df if split is None else df[df["dataset_split"] == split]
    xs = xs[xs[f"path_valid_{hz}"]]
    vc = xs[f"path_bin_{hz}"].value_counts(dropna=False)
    n = int(vc.sum())
    rates = {b: float(vc.get(b, 0) / n) if n else None for b in C.PATH_BINS}
    s = sum(v or 0 for v in rates.values())
    return {"n": n, "rates": rates, "sum": s, "normalized": abs(s - 1.0) < 1e-9}
