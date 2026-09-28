"""Unsmoothed possession-to-possession Δh*. Primary result is unsmoothed."""

from __future__ import annotations

import numpy as np
import pandas as pd


def analyze(df: pd.DataFrame, families=("N1", "N2", "N3", "N4", "E2")) -> dict:
    out = {}
    for fam in families:
        col = f"h_{fam}"
        if col not in df.columns:
            continue
        rec = {}
        for split in ("TRAIN", "VALIDATION", "OOS"):
            xs = df[df["dataset_split"] == split][["trade_id", "possessions_since_entry", col]].dropna()
            rec[split] = _split_stats(xs, col)
        out[fam] = rec
    return out


def _split_stats(xs: pd.DataFrame, col: str) -> dict:
    dhs = []
    reversals = 0
    n_pairs = 0
    for _, g in xs.groupby("trade_id", sort=False):
        g = g.sort_values("possessions_since_entry")
        h = g[col].to_numpy(float)
        if len(h) < 2:
            continue
        dh = np.diff(h)
        dhs.append(np.abs(dh))
        n_pairs += len(dh)
        s = np.sign(dh)
        s = s[s != 0]
        if len(s) >= 2:
            reversals += int(np.sum(s[1:] * s[:-1] < 0))
    if not dhs:
        return {"n_pairs": 0}
    cat = np.concatenate(dhs)
    return {
        "n_pairs": int(n_pairs),
        "mean_abs_dh": float(cat.mean()),
        "median_abs_dh": float(np.median(cat)),
        "p90_abs_dh": float(np.quantile(cat, 0.90)),
        "reversals": reversals,
        "reversal_per_pair": reversals / n_pairs if n_pairs else None,
    }
