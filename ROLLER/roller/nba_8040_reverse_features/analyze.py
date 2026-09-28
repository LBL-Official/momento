"""Q2 vs Q3 composition, within-period S vs T40, temporal, ablation."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from roller.nba_8040_reverse_features.catalog import matrix_specs
from roller.nba_8040_reverse_features.knn import neighborhood_table
from roller.nba_8040_reverse_features.locks import GAIN_CENTS, LOSS_CENTS
from roller.nba_8040_reverse_features.matrix import complete_mask, predictive_frame
from roller.nba_8040_reverse_features.stats import describe_feature, population_row, smd
from roller.choosin_texas.ev import book_cents

FEATURE_SETS = {
    "PRICE": ["entry_bid_cents", "jump_through_80", "exact_80", "prior_close_cents", "delta_5m", "velocity_5m"],
    "TIME": ["period_remaining_s", "game_seconds_remaining", "frac_period_remaining", "frac_game_elapsed"],
    "SCORE": ["bought_margin", "abs_margin", "leading", "tie", "favorite_leading"],
    "OPEN": ["pregame_cents", "distance_from_open"],
    "PRICE_TIME": [
        "entry_bid_cents",
        "delta_5m",
        "velocity_5m",
        "frac_period_remaining",
        "frac_game_elapsed",
    ],
    "PRICE_SCORE": ["entry_bid_cents", "delta_5m", "bought_margin", "abs_margin"],
    "ALL_PRE80": [spec.name for spec in matrix_specs()],
}


def _join(features: pd.DataFrame, labels: pd.DataFrame) -> pd.DataFrame:
    keep = ["instance_id", "t40", "s", "ev_contribution", "w_and_t40", "l_and_t40"]
    return features.merge(labels[keep], on="instance_id", how="inner", suffixes=("", "_lab"))


def composition_tables(features: pd.DataFrame, labels: pd.DataFrame) -> dict[str, Any]:
    joined = _join(features, labels)
    pops = [
        population_row(labels, name="Q2∪Q3"),
        population_row(labels[labels["period"] == "Q2"], name="Q2"),
        population_row(labels[labels["period"] == "Q3"], name="Q3"),
        population_row(labels[labels["period"] == "Q2"], name="Q2 all-phase"),
        population_row(labels[labels["period"] == "Q3"], name="Q3 all-phase"),
        population_row(
            labels[(labels["period"] == "Q2") & (labels["regular_season"])],
            name="Q2 regular season",
        ),
        population_row(
            labels[(labels["period"] == "Q3") & (labels["regular_season"])],
            name="Q3 regular season",
        ),
    ]
    names = [spec.name for spec in matrix_specs()]
    q2 = joined[joined["period"] == "Q2"]
    q3 = joined[joined["period"] == "Q3"]
    diffs = []
    for name in names:
        left = q2[name]
        right = q3[name]
        d2 = describe_feature(q2, name)
        d3 = describe_feature(q3, name)
        diffs.append(
            {
                "feature": name,
                "q2_median": d2.get("median"),
                "q3_median": d3.get("median"),
                "q2_mean": d2.get("mean", d2.get("share")),
                "q3_mean": d3.get("mean", d3.get("share")),
                "standardized_difference": smd(left, right),
                "q2_available_n": d2["available_n"],
                "q3_available_n": d3["available_n"],
            }
        )
    availability = []
    for name in names:
        spec = next(item for item in matrix_specs() if item.name == name)
        desc = describe_feature(features, name)
        availability.append(
            {
                "feature_class": spec.feature_class,
                "feature": name,
                "available_n": desc["available_n"],
                "missing_pct": None if desc["missing_rate"] is None else round(desc["missing_rate"] * 100, 2),
                "source": spec.source,
            }
        )
    return {"population": pops, "q2_vs_q3": diffs, "availability": availability}


def within_period(features: pd.DataFrame, labels: pd.DataFrame) -> list[dict[str, Any]]:
    joined = _join(features, labels)
    names = [spec.name for spec in matrix_specs()]
    rows = []
    for name in names:
        row = {"feature": name}
        for period in ("Q2", "Q3"):
            block = joined[joined["period"] == period]
            survive = block.loc[block["s"], name]
            t40 = block.loc[~block["s"], name]
            row[f"{period.lower()}_survive_mean"] = float(survive.mean()) if survive.notna().any() else None
            row[f"{period.lower()}_t40_mean"] = float(t40.mean()) if t40.notna().any() else None
            row[f"{period.lower()}_smd"] = smd(survive, t40)
        rows.append(row)
    return rows


def temporal_normalization(features: pd.DataFrame, labels: pd.DataFrame) -> list[dict[str, Any]]:
    joined = _join(features, labels)
    out = []
    for col, bins in (
        ("frac_period_remaining", (0.0, 0.25, 0.5, 0.75, 1.01)),
        ("frac_game_elapsed", (0.25, 0.4, 0.55, 0.7, 0.85, 1.01)),
    ):
        joined["_bin"] = pd.cut(joined[col], bins=bins, include_lowest=True)
        for bucket, block in joined.groupby("_bin", observed=False):
            for period in ("Q2", "Q3"):
                sub = block[block["period"] == period]
                if sub.empty:
                    continue
                s_n = int(sub["s"].sum())
                n = int(len(sub))
                out.append(
                    {
                        "axis": col,
                        "bin": str(bucket),
                        "period": period,
                        "n": n,
                        "s": s_n,
                        "ev_cents": float(book_cents(s_n, n, gain=GAIN_CENTS, loss=LOSS_CENTS) / n),
                    }
                )
    return out


def ablation(features: pd.DataFrame, labels: pd.DataFrame) -> list[dict[str, Any]]:
    joined = _join(features, labels)
    rows = []
    for set_name, names in FEATURE_SETS.items():
        usable = [name for name in names if name in joined.columns]
        predictive_frame(features, usable)
        q2 = joined[joined["period"] == "Q2"]
        q3 = joined[joined["period"] == "Q3"]
        smds = [smd(q2[name], q3[name]) for name in usable]
        smds = [value for value in smds if value is not None]
        q2_out = [smd(q2.loc[q2["s"], name], q2.loc[~q2["s"], name]) for name in usable]
        q3_out = [smd(q3.loc[q3["s"], name], q3.loc[~q3["s"], name]) for name in usable]
        q2_out = [value for value in q2_out if value is not None]
        q3_out = [value for value in q3_out if value is not None]
        knn_agree = None
        mask = complete_mask(features, usable)
        if int(mask.sum()) >= 40:
            table = neighborhood_table(features, labels, usable, ks=(10,), within=True)
            if table:
                knn_agree = table[0].get("outcome_agreement")
        rows.append(
            {
                "feature_set": set_name,
                "n_features": len(usable),
                "q2_q3_mean_abs_smd": float(np.mean(np.abs(smds))) if smds else None,
                "q2_outcome_mean_abs_smd": float(np.mean(np.abs(q2_out))) if q2_out else None,
                "q3_outcome_mean_abs_smd": float(np.mean(np.abs(q3_out))) if q3_out else None,
                "knn_k10_agreement": knn_agree,
            }
        )
    return rows
