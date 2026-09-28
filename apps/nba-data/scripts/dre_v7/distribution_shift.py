"""TRAIN / VAL / OOS occupancy, rare-cell exposure, fallback, TV."""

from __future__ import annotations

import numpy as np
import pandas as pd

from . import config as C


def _freq(state: pd.DataFrame, split: str) -> pd.Series:
    st = state[state["dataset_split"] == split]
    if st.empty:
        return pd.Series(dtype=float)
    c = st["m1_key"].value_counts(dropna=False)
    return c / c.sum()


def total_variation(p: pd.Series, q: pd.Series) -> float | None:
    keys = sorted(set(p.index) | set(q.index))
    if not keys:
        return None
    a = np.asarray([float(p.get(k, 0.0)) for k in keys])
    b = np.asarray([float(q.get(k, 0.0)) for k in keys])
    return float(0.5 * np.abs(a - b).sum())


def measure(state: pd.DataFrame) -> dict:
    train_keys = set(state.loc[(state["dataset_split"] == "TRAIN") & state["EXACT_CELL_EXISTS"], "m1_key"])
    by_split = {}
    freqs = {s: _freq(state, s) for s in C.SPLITS}
    for split in C.SPLITS:
        st = state[state["dataset_split"] == split]
        n = int(len(st))
        on_train = st["m1_key"].isin(train_keys) if n else pd.Series(dtype=bool)
        rare = {}
        for sid, lo, hi in C.SUPPORT_STRATA:
            if hi <= 19 or sid in ("0", "1", "2-4", "5-9", "10-19"):
                rare[sid] = float((st["support_stratum"] == sid).mean()) if n else None
        paths = {p: float((st["SCORING_PATH"] == p).mean()) if n else None for p in ("M1_EXACT", "M0_FALLBACK", "GLOBAL_FALLBACK")}
        by_split[split] = {
            "n_rows": n,
            "n_trades": int(st["trade_id"].nunique()) if n else 0,
            "pct_on_train_observed_m1": float(on_train.mean()) if n else None,
            "rare_cell_row_share_by_stratum": rare,
            "scoring_path_rates": paths,
            "label": C.OCCUPANCY_LABEL,
        }
    return {
        "object": "Distribution shift of M1 cell occupancy",
        "label": C.OCCUPANCY_LABEL,
        "tv_train_val": total_variation(freqs["TRAIN"], freqs["VALIDATION"]),
        "tv_train_oos": total_variation(freqs["TRAIN"], freqs["OOS"]),
        "tv_definition": "0.5 * sum_c |p_c - q_c|",
        "by_split": by_split,
        "four_fields": C.SPECIFICATION_LOCKS["four_fields"],
        "note": "Structural geometry. Not edge.",
    }
