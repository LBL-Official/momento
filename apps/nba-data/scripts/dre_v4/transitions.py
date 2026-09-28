"""Empirical regime transition matrices. Not a Markov proof."""

from __future__ import annotations

import numpy as np
import pandas as pd

REGIMES = ("STABLE", "RECOVERING", "DETERIORATING", "SEVERELY_DRAWDOWN", "HIGH_VOLATILITY", "STALE_MARKET")
STEPS = (1, 3, 5)


def matrices(df: pd.DataFrame) -> dict:
    out = {"note": "EMPIRICAL TRANSITION MATRICES — not proof of a Markov process.", "by_split": {}}
    for split in ("TRAIN", "VALIDATION", "OOS"):
        xs = df[df["dataset_split"] == split][["trade_id", "possession_index", "regime"]].copy()
        rec = {}
        for h in STEPS:
            counts = np.zeros((len(REGIMES), len(REGIMES)))
            idx = {r: i for i, r in enumerate(REGIMES)}
            for _, g in xs.groupby("trade_id", sort=False):
                g = g.sort_values("possession_index")
                r = g["regime"].to_numpy()
                for i in range(len(r) - h):
                    a, b = r[i], r[i + h]
                    if a in idx and b in idx:
                        counts[idx[a], idx[b]] += 1
            row = counts.sum(axis=1, keepdims=True)
            probs = np.zeros_like(counts, dtype=float)
            np.divide(counts, row, out=probs, where=row > 0)
            rec[str(h)] = {
                "regimes": list(REGIMES),
                "counts": counts.astype(int).tolist(),
                "probs": [[None if not np.isfinite(x) else float(x) for x in prow] for prow in probs],
                "n_transitions": int(counts.sum()),
            }
        out["by_split"][split] = rec
    return out
