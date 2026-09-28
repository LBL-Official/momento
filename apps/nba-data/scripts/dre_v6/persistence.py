"""Possession-clock persistence of |da_state|. Measurements only. PERSISTENCE ≠ EXECUTABILITY."""

from __future__ import annotations

import numpy as np
import pandas as pd

from . import config as C
from .sir import split_trades


def _longest_same_sign(vals: np.ndarray) -> int:
    best = 0
    cur = 0
    last = 0
    for v in vals:
        if not np.isfinite(v) or v == 0:
            cur = 0
            last = 0
            continue
        s = 1 if v > 0 else -1
        if s == last:
            cur += 1
        else:
            cur = 1
            last = s
        best = max(best, cur)
    return int(best)


def per_trade(state_df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for tid, g in state_df.sort_values("possession_index").groupby("trade_id", sort=False):
        da = pd.to_numeric(g["da_state"], errors="coerce").to_numpy(float)
        pidx = pd.to_numeric(g["possession_index"], errors="coerce").to_numpy(float)
        rec = {
            "trade_id": tid,
            "event_id": g["event_id"].iloc[0],
            "dataset_split": g["dataset_split"].iloc[0],
            "T_i": int(len(g)),
            "max_abs_da": float(np.nanmax(np.abs(da))) if len(da) else None,
            "longest_same_sign": _longest_same_sign(da),
        }
        for k in C.TAIL_KS:
            above = np.isfinite(da) & (np.abs(da) >= k)
            rec[f"n_above_{int(k)}"] = int(above.sum())
            rec[f"ever_{int(k)}"] = bool(above.any())
            if above.any():
                first = int(np.flatnonzero(above)[0])
                rec[f"first_pidx_{int(k)}"] = None if not np.isfinite(pidx[first]) else float(pidx[first])
                rec[f"poss_after_first_{int(k)}"] = int(len(da) - first)
            else:
                rec[f"first_pidx_{int(k)}"] = None
                rec[f"poss_after_first_{int(k)}"] = None
        rows.append(rec)
    return pd.DataFrame(rows)


def measure(state_df: pd.DataFrame, trades: pd.DataFrame) -> dict:
    pers = per_trade(state_df)
    merged = pers.merge(trades[["trade_id", "mean_sir", "mean_r", "pi_terminal"]], on="trade_id", how="left")
    by_split = {}
    for split in C.SPLITS:
        xs = merged[merged["dataset_split"] == split]
        k5 = xs[xs["ever_5"] == True] if len(xs) else xs
        dur = k5["n_above_5"] if len(k5) else pd.Series(dtype=float)
        persist = k5[k5["n_above_5"] >= C.PERSISTENCE_MEDIAN_MIN] if len(k5) else k5
        eph = k5[k5["n_above_5"] == 1] if len(k5) else k5
        by_split[split] = {
            "n_trades": int(len(xs)),
            "n_ever_5": int(len(k5)),
            "median_duration_k5": float(dur.median()) if len(dur) else None,
            "median_meets_3": None if not len(dur) else bool(float(dur.median()) >= C.PERSISTENCE_MEDIAN_MIN),
            "persistent_n": int(len(persist)),
            "ephemeral_n": int(len(eph)),
            "persistent_mean_pi": float(persist["pi_terminal"].mean()) if len(persist) else None,
            "ephemeral_mean_pi": float(eph["pi_terminal"].mean()) if len(eph) else None,
            "persistent_mean_r": float(persist["mean_r"].mean()) if len(persist) else None,
            "ephemeral_mean_r": float(eph["mean_r"].mean()) if len(eph) else None,
            "weighting": C.SURFACE_WEIGHTING_PRIMARY,
        }
    return {
        "k": list(C.TAIL_KS),
        "duration_definition": "n_possessions with |da_state| >= k",
        "persistence_k": C.PERSISTENCE_K,
        "persistence_median_min": C.PERSISTENCE_MEDIAN_MIN,
        "by_split": by_split,
        "note": "PERSISTENCE ≠ EXECUTABILITY. Measurement only.",
    }
