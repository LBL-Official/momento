"""Relationships A and B. Occupancy geometry, not prediction."""

from __future__ import annotations

import numpy as np
import pandas as pd

from . import config as C
from . import replication as R


def _mass(abs_da: np.ndarray) -> dict:
    a = np.asarray(abs_da, float)
    a = a[np.isfinite(a)]
    if len(a) == 0:
        return {"n": 0}
    return {
        "n": int(len(a)),
        "mean_abs_da": float(a.mean()),
        "median_abs_da": float(np.median(a)),
        "P_abs_ge": {str(int(k)): float(np.mean(a >= k)) for k in C.MAGNITUDE_CUTS_CENTS},
    }


def relationship_a(state: pd.DataFrame) -> dict:
    """|da_state| by TRAIN support stratum. STATE_OCCUPANCY_WEIGHTED DIAGNOSTIC."""
    by_split = {}
    for split in C.SPLITS:
        st = state[state["dataset_split"] == split]
        strata = {}
        for sid, _, _ in C.SUPPORT_STRATA:
            sub = st[st["support_stratum"] == sid]
            rec = _mass(sub["da_state"].abs().to_numpy(float))
            rec["n_trades"] = int(sub["trade_id"].nunique()) if len(sub) else 0
            rec["n_games"] = int(sub["event_id"].nunique()) if len(sub) else 0
            rec["label"] = C.OCCUPANCY_LABEL
            strata[sid] = rec
        overall = _mass(st["da_state"].abs().to_numpy(float))
        overall["spearman_abs_da_vs_unique_trades"] = R.spearman(st["da_state"].abs(), st["TRAIN_UNIQUE_TRADE_SUPPORT"])
        overall["label"] = C.OCCUPANCY_LABEL
        by_split[split] = {"overall": overall, "by_stratum": strata}
    return {
        "object": "Relationship A — |da_state| versus TRAIN unique-trade support",
        "label": C.OCCUPANCY_LABEL,
        "by_split": by_split,
        "prominent": C.PROMINENT,
        "note": "Not a predictive test. Occupancy-weighted.",
    }


def _bucket(st: pd.DataFrame, mask, name: str) -> dict:
    sub = st[mask]
    return {
        "name": name,
        "n_rows": int(len(sub)),
        "n_trades": int(sub["trade_id"].nunique()) if len(sub) else 0,
        "n_games": int(sub["event_id"].nunique()) if len(sub) else 0,
        "median_TRAIN_unique_trades": float(sub["TRAIN_UNIQUE_TRADE_SUPPORT"].median()) if len(sub) else None,
        "median_N_EFF_TRADE": float(sub["N_EFF_TRADE"].median()) if len(sub) and sub["N_EFF_TRADE"].notna().any() else None,
        "median_rows_per_trade": float(sub["rows_per_trade_train"].median()) if len(sub) and sub["rows_per_trade_train"].notna().any() else None,
        "support_distribution": {sid: int((sub["support_stratum"] == sid).sum()) for sid, _, _ in C.SUPPORT_STRATA},
        "scoring_path": {p: int((sub["SCORING_PATH"] == p).sum()) for p in ("M1_EXACT", "M0_FALLBACK", "GLOBAL_FALLBACK")},
        "label": C.CELL_LABEL,
    }


def relationship_b(state: pd.DataFrame) -> dict:
    """Extreme |da| source-cell audit. CELL_GEOMETRY_DIAGNOSTIC."""
    by_split = {}
    for split in C.SPLITS:
        st = state[state["dataset_split"] == split]
        abs_da = st["da_state"].abs()
        rec = {"baseline_abs_lt_1": _bucket(st, abs_da < C.BASELINE_ABS_CENTS, "abs_da_lt_1")}
        for k in C.EXTREME_KS:
            rec[f"abs_ge_{int(k)}"] = _bucket(st, abs_da >= k, f"abs_da_ge_{int(k)}")
        rec["label"] = C.CELL_LABEL
        by_split[split] = rec
    return {
        "object": "Relationship B — extreme SIR source-cell provenance",
        "label": C.CELL_LABEL,
        "by_split": by_split,
        "four_fields": C.SPECIFICATION_LOCKS["four_fields"],
        "note": "Forensic provenance. Not a predictive test.",
    }
