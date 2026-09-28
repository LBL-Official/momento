"""TRAIN cell support. N_eff is occupancy concentration, not sample size."""

from __future__ import annotations

import math

import numpy as np
import pandas as pd

from . import config as C


def _entropy(shares: np.ndarray) -> float | None:
    s = shares[shares > 0]
    if len(s) == 0:
        return None
    return float(-np.sum(s * np.log(s)))


def cell_support_train(state: pd.DataFrame) -> pd.DataFrame:
    """CELL_GEOMETRY_DIAGNOSTIC. TRAIN rows only."""
    tr = state[state["dataset_split"] == "TRAIN"].copy()
    rows = []
    for key, g in tr.groupby("m1_key", sort=False, dropna=False):
        n_rows = int(len(g))
        trades = g.groupby("trade_id", sort=False)
        n_tr = int(trades.ngroups)
        n_ev = int(g["event_id"].nunique())
        sizes = trades.size().to_numpy(float)
        w = sizes / sizes.sum() if sizes.sum() else sizes
        n_eff = float(1.0 / np.sum(w * w)) if len(w) and np.sum(w * w) > 0 else None
        pi = trades["pi_terminal"].first()
        n_win = int((pi == 20.0).sum()) if len(pi) else 0
        n_loss = int((pi == -80.0).sum()) if len(pi) else 0
        order = np.sort(sizes)[::-1]
        max_share = float(order[0] / n_rows) if n_rows else None
        top5 = float(order[: min(5, len(order))].sum() / n_rows) if n_rows else None
        rows.append(
            {
                "m1_key": key,
                "row_count_train": n_rows,
                "unique_trade_count_train": n_tr,
                "unique_event_count_train": n_ev,
                "rows_per_trade": None if n_tr == 0 else float(n_rows / n_tr),
                "terminal_outcome_diversity": int(pi.nunique()) if len(pi) else 0,
                "win_count_train": n_win,
                "loss_count_train": n_loss,
                "p_pi_plus_20": None if n_tr == 0 else float(n_win / n_tr),
                "p_pi_minus_80": None if n_tr == 0 else float(n_loss / n_tr),
                "maximum_trade_row_share": max_share,
                "top_5_trade_row_share": top5,
                "N_EFF_TRADE": n_eff,
                "N_EFF_LABEL": "OCCUPANCY_CONCENTRATION_EFFECTIVE_TRADE_COUNT",
                "occupancy_entropy": _entropy(w) if len(w) else None,
                "support_stratum": C.stratum_id(n_tr),
                "EXACT_CELL_EXISTS": True,
                "label": C.CELL_LABEL,
                "note": C.SUPPORT_NOT_INDEPENDENCE,
            }
        )
    tab = pd.DataFrame(rows)
    return tab


def attach_support(state: pd.DataFrame, cells: pd.DataFrame) -> pd.DataFrame:
    lookup = cells.set_index("m1_key")
    out = state.copy()
    out["TRAIN_UNIQUE_TRADE_SUPPORT"] = out["m1_key"].map(lookup["unique_trade_count_train"]).fillna(0).astype(int)
    out["N_EFF_TRADE"] = out["m1_key"].map(lookup["N_EFF_TRADE"])
    out["rows_per_trade_train"] = out["m1_key"].map(lookup["rows_per_trade"])
    out["maximum_trade_row_share"] = out["m1_key"].map(lookup["maximum_trade_row_share"])
    out["support_stratum"] = [C.stratum_id(int(x)) for x in out["TRAIN_UNIQUE_TRADE_SUPPORT"]]
    # Unobserved TRAIN cells stay EXACT_CELL_EXISTS from scoring (map hit), support 0
    return out


def stratum_occupancy(cells: pd.DataFrame) -> dict:
    rec = {}
    for sid, _, _ in C.SUPPORT_STRATA:
        sub = cells[cells["support_stratum"] == sid] if len(cells) else cells
        rec[sid] = {
            "n_cells": int(len(sub)),
            "row_count_train": int(sub["row_count_train"].sum()) if len(sub) else 0,
            "label": C.CELL_LABEL,
        }
    rec["note"] = "TRAIN occupancy of locked strata. Empty strata kept. Do not merge."
    rec["prominent"] = C.PROMINENT
    return rec
