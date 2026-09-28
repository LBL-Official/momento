"""Relationship C — one row per trade. Exact r_bar formula."""

from __future__ import annotations

import pandas as pd

from . import config as C


def trade_table(state: pd.DataFrame) -> pd.DataFrame:
    xs = state[state["pi_terminal"].notna() & state["da_state"].notna()].copy()
    rows = []
    for tid, g in xs.groupby("trade_id", sort=False):
        t = int(len(g))
        mean_a0 = float(g["alpha_m0"].mean())
        pi = float(g["pi_terminal"].iloc[0])
        rows.append(
            {
                "trade_id": tid,
                "event_id": g["event_id"].iloc[0],
                "dataset_split": g["dataset_split"].iloc[0],
                "T_i": t,
                "mean_da_i": float(g["da_state"].mean()),
                "mean_alpha_m0_i": mean_a0,
                "pi_i": pi,
                "r_bar_i": pi - mean_a0,
                "y_settle_yes": float(g["y_settle_yes"].iloc[0]) if pd.notna(g["y_settle_yes"].iloc[0]) else None,
                "mean_cell_trade_support_i": float(g["TRAIN_UNIQUE_TRADE_SUPPORT"].mean()),
                "minimum_cell_trade_support_i": float(g["TRAIN_UNIQUE_TRADE_SUPPORT"].min()),
                "median_cell_trade_support_i": float(g["TRAIN_UNIQUE_TRADE_SUPPORT"].median()),
                "fraction_sparse_states_i": float((g["TRAIN_UNIQUE_TRADE_SUPPORT"] <= C.SPARSE_UNIQUE_TRADES).mean()),
                "support_weighted_mean_abs_da": float(
                    (g["da_state"].abs() * g["TRAIN_UNIQUE_TRADE_SUPPORT"]).sum() / max(g["TRAIN_UNIQUE_TRADE_SUPPORT"].sum(), 1e-12)
                ),
                "max_abs_da": float(g["da_state"].abs().max()),
                "max_abs_da_train_support": float(g.loc[g["da_state"].abs().idxmax(), "TRAIN_UNIQUE_TRADE_SUPPORT"]),
                "support_stratum_min": C.stratum_id(int(g["TRAIN_UNIQUE_TRADE_SUPPORT"].min())),
                "frac_m1_exact": float((g["SCORING_PATH"] == "M1_EXACT").mean()),
                "frac_m0_fallback": float((g["SCORING_PATH"] == "M0_FALLBACK").mean()),
                "frac_global_fallback": float((g["SCORING_PATH"] == "GLOBAL_FALLBACK").mean()),
                "weighting": C.SURFACE_WEIGHTING_PRIMARY,
                "r_bar_formula": C.R_BAR_FORMULA,
            }
        )
    tab = pd.DataFrame(rows)
    tab["abs_mean_da"] = tab["mean_da_i"].abs()
    return tab


def exposure_summary(trades: pd.DataFrame) -> dict:
    by_split = {}
    for split in C.SPLITS:
        tr = trades[trades["dataset_split"] == split]
        by_split[split] = {
            "n_trades": int(len(tr)),
            "mean_abs_mean_da": float(tr["abs_mean_da"].mean()) if len(tr) else None,
            "mean_min_support": float(tr["minimum_cell_trade_support_i"].mean()) if len(tr) else None,
            "mean_fraction_sparse": float(tr["fraction_sparse_states_i"].mean()) if len(tr) else None,
            "spearman_abs_da_vs_min_support": None,
            "label": C.SURFACE_WEIGHTING_PRIMARY,
        }
        if len(tr) >= 3:
            from . import replication as R

            by_split[split]["spearman_abs_da_vs_min_support"] = R.spearman(
                tr["abs_mean_da"], tr["minimum_cell_trade_support_i"]
            )
    return {
        "object": "Relationship C — trade-level SIR versus support exposure",
        "label": C.SURFACE_WEIGHTING_PRIMARY,
        "r_bar_formula": C.R_BAR_FORMULA,
        "by_split": by_split,
        "note": "One observation per trade. Not independent sample size.",
    }
