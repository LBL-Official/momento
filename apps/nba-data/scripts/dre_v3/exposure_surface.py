"""Aggregate theoretical h* surfaces. No hand-designed regimes first."""

from __future__ import annotations

import numpy as np
import pandas as pd


def surface_price_clock(df: pd.DataFrame, fam: str) -> list[dict]:
    col = f"h_{fam}"
    xs = df[df[col].notna() & df["current_price"].notna() & df["game_seconds_remaining"].notna()]
    out = []
    for split in ("TRAIN", "VALIDATION", "OOS"):
        sub = xs[xs["dataset_split"] == split]
        for plo in range(5, 85, 5):
            for clo, chi, clab in (
                (1440, 10000, "early"),
                (360, 1440, "mid"),
                (0, 360, "late"),
            ):
                b = sub[
                    (sub["current_price"] >= plo)
                    & (sub["current_price"] < plo + 5)
                    & (sub["game_seconds_remaining"] >= clo)
                    & (sub["game_seconds_remaining"] < chi)
                ]
                if len(b) < 15:
                    continue
                h = b[col].to_numpy(float)
                out.append(
                    {
                        "split": split,
                        "family": fam,
                        "price_lo": plo,
                        "price_hi": plo + 5,
                        "clock": clab,
                        "n": int(len(b)),
                        "mean_h": float(h.mean()),
                        "median_h": float(np.median(h)),
                        "interior_rate": float(np.mean((h > 0) & (h < 1))),
                        "emp_settle": float(b["y_settle_yes"].mean()) if b["y_settle_yes"].notna().any() else None,
                    }
                )
    return out


def same_price_contrast(df: pd.DataFrame) -> list[dict]:
    out = []
    for split in ("TRAIN", "VALIDATION", "OOS"):
        xs = df[df["dataset_split"] == split]
        for lo, hi, name in ((58, 63, "price_60"), (48, 53, "price_50"), (68, 73, "price_70")):
            base = xs[(xs["current_price"] >= lo) & (xs["current_price"] < hi)]
            early = base[(base["period"] <= 2) & (base["game_seconds_remaining"] >= 1440)]
            late = base[(base["period"] >= 4) & (base["game_seconds_remaining"] <= 360)]
            lead = base[base["score_differential_from_A1"] >= 10]
            trail = base[base["score_differential_from_A1"] <= -10]
            rec = {"split": split, "band": name}
            for label, sl in (("early", early), ("late", late), ("leading", lead), ("trailing", trail)):
                rec[label] = _slice(sl)
            out.append(rec)
    return out


def _slice(b: pd.DataFrame) -> dict:
    if len(b) < 20:
        return {"n": int(len(b))}
    out = {"n": int(len(b)), "mean_price": float(b["current_price"].mean()), "emp_settle": float(b["y_settle_yes"].mean())}
    for fam in ("N1", "N2", "N3", "N4", "E2", "E3"):
        col = f"h_{fam}"
        if col in b.columns:
            h = b[col].dropna().to_numpy(float)
            if len(h):
                out[f"mean_h_{fam}"] = float(h.mean())
                out[f"interior_{fam}"] = float(np.mean((h > 0) & (h < 1)))
    return out
