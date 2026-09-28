"""Distribution measurements. No verdict."""

from __future__ import annotations

import numpy as np

from . import config as C
from .sir import quantile_dict, split_trades


def _mass(vals, weighting: str, n_units: int) -> dict:
    arr = np.asarray(vals, float)
    arr = arr[np.isfinite(arr)]
    rec = {
        "weighting": weighting,
        "n": int(len(arr)),
        "n_units": int(n_units),
        **quantile_dict(arr),
        "P_abs_ge": {str(int(k)): float(np.mean(np.abs(arr) >= k)) if len(arr) else None for k in C.MAGNITUDE_CUTS_CENTS},
    }
    return rec


def measure(state_df, trades) -> dict:
    by_split = {}
    for split in C.SPLITS:
        tr = split_trades(trades, split)
        st = state_df[state_df["dataset_split"] == split]
        by_split[split] = {
            "TRADE_BALANCED": _mass(tr["mean_sir"].to_numpy(float), C.SURFACE_WEIGHTING_PRIMARY, int(len(tr))),
            C.OCCUPANCY_LABEL: _mass(st["da_state"].to_numpy(float), C.OCCUPANCY_LABEL, int(st["trade_id"].nunique())),
        }
    return {
        "primary": C.SURFACE_WEIGHTING_PRIMARY,
        "cuts_cents": list(C.MAGNITUDE_CUTS_CENTS),
        "by_split": by_split,
        "note": "Primary economic sentence uses trade-balanced P(|mean_SIR_i| >= k).",
    }
