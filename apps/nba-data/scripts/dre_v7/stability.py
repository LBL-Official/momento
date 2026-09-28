"""Support-stratified temporal stability. TRADE_BALANCED residual. Gate J for edges."""

from __future__ import annotations

import numpy as np
import pandas as pd

from . import config as C
from . import replication as R
from dre_v6.rank import assign_decile


def _spread(tr: pd.DataFrame, edges, compatible: bool) -> dict:
    if not compatible or edges is None:
        return {"status": "NOT_APPLICABLE", "reason": "Gate J incompatible or edges missing"}
    if tr.empty:
        return {"status": "INCONCLUSIVE", "n_trades": 0}
    dec = assign_decile(tr["mean_da_i"].to_numpy(float), np.asarray(edges, float))
    xs = tr.assign(decile=dec)
    lo = xs[xs["decile"] == 1]
    hi = xs[xs["decile"] == 10]
    adequate = R.coverage_adequate(len(lo), len(hi))
    spread = None
    if len(lo) and len(hi):
        spread = float(hi["r_bar_i"].mean() - lo["r_bar_i"].mean())
    return {
        "status": "OK" if adequate else "INCONCLUSIVE",
        "n_lo": int(len(lo)),
        "n_hi": int(len(hi)),
        "adequate": adequate,
        "spread_hi_minus_lo_r_bar": spread,
        "edges_source": "V6 TRAIN mean_SIR_i qcut",
        "weighting": C.SURFACE_WEIGHTING_PRIMARY,
    }


def measure(trades: pd.DataFrame, gate_j: dict) -> dict:
    compatible = bool(gate_j.get("compatible"))
    edges = gate_j.get("edges") if compatible else None
    by_split = {}
    for split in C.SPLITS:
        tr = trades[trades["dataset_split"] == split]
        strata = {}
        for sid, lo, hi in C.SUPPORT_STRATA:
            # min-support stratum of the trade
            sub = tr[tr["support_stratum_min"] == sid]
            rec = {
                "n_trades": int(len(sub)),
                "n_games": int(sub["event_id"].nunique()) if len(sub) else 0,
                "mean_da": float(sub["mean_da_i"].mean()) if len(sub) else None,
                "mean_r_bar": float(sub["r_bar_i"].mean()) if len(sub) else None,
                "spearman_mean_da_r_bar": R.spearman(sub["mean_da_i"], sub["r_bar_i"]) if len(sub) >= 3 else None,
                "eligible_stability": lo >= C.STABILITY_MIN_TRADES,
                "high_low": _spread(sub, edges, compatible) if lo >= C.STABILITY_MIN_TRADES else {"status": "SKIPPED_SPARSE"},
                "label": C.STABILITY_LABEL,
                "weighting": C.SURFACE_WEIGHTING_PRIMARY,
            }
            strata[sid] = rec
        by_split[split] = {
            "overall": {
                "n_trades": int(len(tr)),
                "spearman_mean_da_r_bar": R.spearman(tr["mean_da_i"], tr["r_bar_i"]) if len(tr) >= 3 else None,
                "high_low": _spread(tr, edges, compatible),
                "label": C.STABILITY_LABEL,
                "weighting": C.SURFACE_WEIGHTING_PRIMARY,
            },
            "by_min_support_stratum": strata,
        }
    return {
        "object": "Support-stratified temporal stability of mean_da → r_bar",
        "label": C.STABILITY_LABEL,
        "r_bar_formula": C.R_BAR_FORMULA,
        "gate_j": {k: gate_j.get(k) for k in ("status", "compatible", "source_variable", "unit_of_observation")},
        "by_split": by_split,
        "note": "Does increasing unique-trade support correspond to more TRAIN→VAL→OOS consistency?",
    }
