"""Interior-solution rates by family and split. Primary endpoint."""

from __future__ import annotations

import numpy as np
import pandas as pd


def analyze(df: pd.DataFrame, families=None) -> dict:
    families = families or ("N1", "N2", "N3", "N4", "N2_LINEAR", "E0", "E1", "E2", "E3")
    out = {}
    for fam in families:
        col = f"h_{fam}"
        if col not in df.columns:
            continue
        rec = {}
        for split in ("TRAIN", "VALIDATION", "OOS"):
            h = df.loc[df["dataset_split"] == split, col].dropna().to_numpy(float)
            rec[split] = _stats(h)
        rec["stability"] = _stability(rec.get("TRAIN") or {}, rec.get("OOS") or {})
        out[fam] = rec
    return out


def _stats(h: np.ndarray) -> dict:
    if len(h) == 0:
        return {"n": 0}
    return {
        "n": int(len(h)),
        "mean_h": float(h.mean()),
        "median_h": float(np.median(h)),
        "std_h": float(h.std()),
        "corner_zero": float(np.mean(h == 0)),
        "corner_one": float(np.mean(h == 1)),
        "interior_rate": float(np.mean((h > 0) & (h < 1))),
    }


def _stability(tr: dict, oos: dict) -> str:
    ti = tr.get("interior_rate")
    oi = oos.get("interior_rate")
    if ti is None or oi is None:
        return "INCONCLUSIVE"
    if ti < 0.05 and oi < 0.05:
        return "CORNER_DOMINATED"
    if ti >= 0.15 and oi < 0.25 * ti:
        return "UNSTABLE"
    if abs(ti - oi) <= 0.10:
        return "STABLE"
    return "PARTIAL"
