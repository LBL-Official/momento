"""Empirical and modeled path-bin distributions. Must sum to 1."""

from __future__ import annotations

import pandas as pd

from . import config as C
from .forward_paths import bin_frequency


def summarize(df: pd.DataFrame) -> dict:
    out = {"empirical": {}, "modeled_mean": {}, "normalization": {}}
    for hz in C.HORIZONS:
        out["empirical"][hz] = {s: bin_frequency(df, hz, s) for s in ("TRAIN", "VALIDATION", "OOS")}
        for s in ("TRAIN", "VALIDATION", "OOS"):
            xs = df[(df["dataset_split"] == s) & df[f"p_path_sum_{hz}"].notna()]
            if xs.empty:
                continue
            rates = {b: float(xs[f"p_{b}_{hz}"].mean()) for b in C.PATH_BINS}
            sm = sum(rates.values())
            out["modeled_mean"].setdefault(hz, {})[s] = {"rates": rates, "sum": sm}
            mx = float((xs[f"p_path_sum_{hz}"] - 1.0).abs().max())
            out["normalization"][f"{hz}_{s}"] = {
                "max_abs_sum_error": mx,
                "status": "PASS" if mx < 1e-6 else "FAIL",
            }
    fails = [k for k, v in out["normalization"].items() if v["status"] != "PASS"]
    out["status"] = "FAIL" if fails else "PASS"
    out["fails"] = fails
    out["rule"] = "Downside-first exclusive bins. Candle-path outcomes, not fills."
    return out
