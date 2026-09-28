"""Concentration of |mean_SIR|. Geometry, not evidence. No verdict."""

from __future__ import annotations

import math

import numpy as np

from . import config as C
from .sir import split_trades


def _share(abs_vals: np.ndarray, frac: float) -> dict:
    n = int(len(abs_vals))
    if n == 0:
        return {"frac": frac, "n_top": 0, "share": None}
    n_top = max(1, int(math.ceil(frac * n - 1e-12)))
    order = np.sort(abs_vals)[::-1]
    total = float(order.sum())
    share = None if total == 0 else float(order[:n_top].sum() / total)
    return {"frac": frac, "n_top": n_top, "n": n, "share": share, "total_abs": total}


def measure(trades) -> dict:
    by_split = {}
    for split in C.SPLITS:
        tr = split_trades(trades, split)
        abs_v = tr["abs_mean_sir"].to_numpy(float)
        abs_v = abs_v[np.isfinite(abs_v)]
        shares = [_share(abs_v, f) for f in C.CONCENTRATION_PCTS]
        top10 = next(s for s in shares if abs(s["frac"] - C.CONCENTRATION_VERDICT_PCT) < 1e-12)
        by_split[split] = {
            "weighting": C.SURFACE_WEIGHTING_PRIMARY,
            "shares": shares,
            "top10_share": top10["share"],
            "top10_meets_40": None if top10["share"] is None else bool(top10["share"] >= C.CONCENTRATION_VERDICT_SHARE),
            "note": C.CONCENTRATION_NOT_EVIDENCE,
        }
    return {
        "primary": C.SURFACE_WEIGHTING_PRIMARY,
        "descriptive_pcts": list(C.CONCENTRATION_PCTS),
        "verdict_pct": C.CONCENTRATION_VERDICT_PCT,
        "verdict_share_threshold": C.CONCENTRATION_VERDICT_SHARE,
        "by_split": by_split,
        "concentration_not_evidence": C.CONCENTRATION_NOT_EVIDENCE,
    }
