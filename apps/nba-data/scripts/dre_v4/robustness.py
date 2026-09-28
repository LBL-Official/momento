"""Seasonal and concentration robustness. Not OOS tuning."""

from __future__ import annotations

import pandas as pd

from .matched_price import contrast_pair, price_bin, slice_masks


def seasonal(df: pd.DataFrame) -> dict:
    oos = df[df["dataset_split"] == "OOS"].copy()
    oos["_bin"] = price_bin(oos["current_price"], 5)
    band = oos[(oos["_bin"] >= 60) & (oos["_bin"] < 65)]
    dt = pd.to_datetime(band["game_date"], errors="coerce")
    masks = slice_masks(band)
    out = {}
    for name, sl in (
        ("early_season", dt < "2026-01-15"),
        ("mid_season", (dt >= "2026-01-15") & (dt < "2026-03-01")),
        ("late_season", dt >= "2026-03-01"),
    ):
        xs = band[sl]
        out[name] = contrast_pair(
            xs,
            xs[masks["early"].reindex(xs.index).fillna(False)],
            xs[masks["late"].reindex(xs.index).fillna(False)],
            "5",
            f"early_vs_late_{name}",
        )
    return out


def concentration(df: pd.DataFrame) -> dict:
    oos = df[(df["dataset_split"] == "OOS")].copy()
    oos["_bin"] = price_bin(oos["current_price"], 5)
    band = oos[(oos["_bin"] >= 60) & (oos["_bin"] < 65)]
    vc = band.groupby("event_id").size().sort_values(ascending=False)
    return {
        "n_rows": int(len(band)),
        "n_games": int(band["event_id"].nunique()),
        "top_game_share": float(vc.iloc[0] / len(band)) if len(vc) else None,
        "top5_share": float(vc.head(5).sum() / len(band)) if len(vc) else None,
        "top_event": None if vc.empty else str(vc.index[0]),
    }
