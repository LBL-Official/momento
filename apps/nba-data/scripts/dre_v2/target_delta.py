"""Theoretical target-delta summaries. Not execution instructions."""

from __future__ import annotations

import numpy as np


def stability(rows, model_fam: str = "M3") -> dict:
    """Is h* stable across splits, or does it flip with time?"""
    out = {}
    for fam in ("A", "B", "C", "D"):
        key = f"target_delta_{model_fam}_{fam}"
        by_split = {}
        for split in ("TRAIN", "VALIDATION", "OOS"):
            vs = [
                float(r[key])
                for r in rows
                if r["dataset_split"] == split and r.get(key) is not None
            ]
            if not vs:
                by_split[split] = {"n": 0}
                continue
            arr = np.asarray(vs, dtype=float)
            by_split[split] = {
                "n": int(len(arr)),
                "mean_h": float(arr.mean()),
                "frac_zero": float(np.mean(arr == 0)),
                "frac_one": float(np.mean(arr == 1)),
                "frac_interior": float(np.mean((arr > 0) & (arr < 1))),
            }
        out[fam] = by_split
    return out


def corner_note() -> str:
    return (
        "Families A/B/C are linear in h, so theoretical_target_delta is typically "
        "a corner {0, 1}. Family D adds a concave regularizer so interior h can appear. "
        "Neither is a live policy. THEORETICAL TARGET DELTA ≠ EXECUTED DELTA."
    )
