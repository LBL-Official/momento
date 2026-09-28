"""Empirical gradient, curvature, and path Lambda. Derived after the payoff surface.

Scientific OOS Lambda uses TRAIN-frozen α only.
Descriptive OOS Lambda uses OOS-estimated α and is never a verdict input.
40¢ framework is excluded.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from . import config as C
from .surfaces import descriptive_oos_lookup_maps, map_alpha, train_lookup_maps


def _l3_price_cells(surface_rows: list[dict], split: str) -> dict[float, dict]:
    out = {}
    for r in surface_rows:
        if (
            r.get("split") == split
            and r.get("level") == "L3"
            and r.get("slice") == "price_only"
            and r.get("payoff") == C.PRIMARY_PAYOFF
            and r.get("adequate")
            and r.get("mean_pi") is not None
            and r.get("price_bin_5") is not None
        ):
            out[float(r["price_bin_5"])] = r
    return out


def empirical_gradients(surface_rows: list[dict], split: str) -> list[dict]:
    """Ascending finite differences of α_frozen. Adjacent filled bins only."""
    cells = _l3_price_cells(surface_rows, split)
    bins = sorted(cells)
    rows = []
    for i in range(len(bins) - 1):
        lo, hi = bins[i], bins[i + 1]
        if hi - lo <= 0:
            continue
        a_lo = float(cells[lo]["mean_pi"])
        a_hi = float(cells[hi]["mean_pi"])
        rows.append(
            {
                "split": split,
                "coordinate": "P_A1_cents",
                "orientation": "ascending",
                "p_low_cents": lo,
                "p_high_cents": hi,
                "alpha_low": a_lo,
                "alpha_high": a_hi,
                "delta_emp": (a_hi - a_lo) / (hi - lo),
                "payoff": C.PRIMARY_PAYOFF,
                "weighting": C.SURFACE_WEIGHTING_PRIMARY,
                "n_rows_low": cells[lo].get("n_rows"),
                "n_rows_high": cells[hi].get("n_rows"),
                "n_unique_trades_low": cells[lo].get("n_unique_trades"),
                "n_unique_trades_high": cells[hi].get("n_unique_trades"),
                "n_unique_games_low": cells[lo].get("n_unique_games"),
                "n_unique_games_high": cells[hi].get("n_unique_games"),
                "note": "Slope of the payoff surface. Not options delta. Not Δ_inv=Q.",
            }
        )
    for coord, col, order in (
        ("clock_l2", "clock_bin_l2", ["early", "late"]),
        ("score_l2", "score_bin_l2", ["tie_trail", "lead"]),
        ("n_hat_l2", "n_hat_bin_l2", ["low", "high"]),
    ):
        by_p: dict[float, dict] = {}
        for r in surface_rows:
            if (
                r.get("split") != split
                or r.get("level") != "L3"
                or r.get("payoff") != C.PRIMARY_PAYOFF
                or not r.get("adequate")
                or r.get("mean_pi") is None
            ):
                continue
            slice_ok = (
                (coord == "clock_l2" and r.get("slice") == "price_clock")
                or (coord == "score_l2" and r.get("slice") == "price_score")
                or (coord == "n_hat_l2" and r.get("slice") == "price_nhat")
            )
            if not slice_ok:
                continue
            p = r.get("price_bin_5")
            lab = r.get(col)
            if p is None or lab not in order:
                continue
            by_p.setdefault(float(p), {})[lab] = r
        for p, d in sorted(by_p.items()):
            if order[0] not in d or order[1] not in d:
                continue
            a0 = float(d[order[0]]["mean_pi"])
            a1 = float(d[order[1]]["mean_pi"])
            rows.append(
                {
                    "split": split,
                    "coordinate": coord,
                    "orientation": "ascending",
                    "low_label": order[0],
                    "high_label": order[1],
                    "price_bin_5": p,
                    "alpha_low": a0,
                    "alpha_high": a1,
                    "delta_emp": a1 - a0,
                    "payoff": C.PRIMARY_PAYOFF,
                    "weighting": C.SURFACE_WEIGHTING_PRIMARY,
                    "n_unique_trades_low": d[order[0]].get("n_unique_trades"),
                    "n_unique_trades_high": d[order[1]].get("n_unique_trades"),
                    "note": "Finite contrast at matched A1 5-cent bin. OT excluded from clock early/late.",
                }
            )
    return rows


def empirical_gamma(surface_rows: list[dict], split: str) -> dict:
    """Change of Δ_P in the 70¢ region vs the 50¢ region."""
    cells = _l3_price_cells(surface_rows, split)

    def slope_near(center: float) -> dict | None:
        lo, hi = center, center + 5
        if lo in cells and hi in cells:
            return {
                "p_low_cents": lo,
                "p_high_cents": hi,
                "delta_emp": (float(cells[hi]["mean_pi"]) - float(cells[lo]["mean_pi"])) / 5.0,
                "alpha_low": float(cells[lo]["mean_pi"]),
                "alpha_high": float(cells[hi]["mean_pi"]),
            }
        return None

    s50 = slope_near(50.0)
    s70 = slope_near(70.0)
    gamma = None
    if s50 and s70:
        gamma = (s70["delta_emp"] - s50["delta_emp"]) / 20.0
    return {
        "split": split,
        "payoff": C.PRIMARY_PAYOFF,
        "region_low": "50s_cents",
        "region_high": "70s_cents",
        "slope_50s": s50,
        "slope_70s": s70,
        "gamma_emp": gamma,
        "note": "Empirical curvature of α_frozen. Not implied-vol gamma. Units: cents.",
    }


def _attach_alpha(df: pd.DataFrame, maps: dict, global_mean: float, col: str) -> pd.DataFrame:
    out = df.copy()
    out[col] = [map_alpha(r, maps, global_mean) for r in out.to_dict("records")]
    return out


def _lambda_along(df: pd.DataFrame, alpha_col: str) -> pd.DataFrame:
    lam = np.full(len(df), np.nan)
    idx = np.arange(len(df))
    out = df.copy()
    out["_i"] = idx
    for _, g in out.groupby("trade_id", sort=False):
        g = g.sort_values("possession_index")
        ii = g["_i"].to_numpy()
        a = pd.to_numeric(g[alpha_col], errors="coerce").to_numpy(float)
        for k in range(len(g) - 1):
            if np.isfinite(a[k]) and np.isfinite(a[k + 1]):
                lam[ii[k]] = -(a[k + 1] - a[k])
    out["lambda_path"] = lam
    return out.drop(columns=["_i"])


def _lambda_summary(df: pd.DataFrame, name: str, surface_source: str, paths: str) -> dict:
    xs = df[df["lambda_path"].notna()]
    if xs.empty:
        return {"name": name, "n_steps": 0, "surface_source": surface_source, "paths": paths}
    g = xs.groupby("trade_id")["lambda_path"].mean()
    return {
        "name": name,
        "surface_source": surface_source,
        "paths": paths,
        "payoff": C.PRIMARY_PAYOFF,
        "formula": "-(alpha(X_{t+1})-alpha(X_t)) / 1 possession",
        "not_claimed": "isolated partial alpha / partial tau",
        "n_steps": int(len(xs)),
        "n_trades": int(g.nunique() if False else g.shape[0]),
        "n_games": int(xs["event_id"].nunique()),
        "mean_trade_balanced": float(g.mean()),
        "mean_occupancy": float(xs["lambda_path"].mean()),
        "occupancy_label": "STATE_OCCUPANCY_WEIGHTED DIAGNOSTIC",
        "p10_trade": float(g.quantile(0.10)),
        "p50_trade": float(g.quantile(0.50)),
        "p90_trade": float(g.quantile(0.90)),
        "verdict_input": name == "scientific_oos_lambda" or name == "discovery_lambda",
    }


def path_lambdas(df: pd.DataFrame, surface_rows: list[dict]) -> dict:
    train = df[(df["dataset_split"] == "TRAIN") & df["pi_terminal"].notna()]
    global_mean = float(train.groupby("trade_id")["pi_terminal"].mean().mean()) if len(train) else 0.0
    train_maps = train_lookup_maps(surface_rows)
    oos_maps = descriptive_oos_lookup_maps(surface_rows)

    tagged = _attach_alpha(df, train_maps, global_mean, "alpha_train_frozen")
    oos_only = df[df["dataset_split"] == "OOS"].copy()
    oos_desc = _attach_alpha(oos_only, oos_maps, global_mean, "alpha_oos_descriptive")

    disc = _lambda_along(tagged[tagged["dataset_split"] == "TRAIN"], "alpha_train_frozen")
    val = _lambda_along(tagged[tagged["dataset_split"] == "VALIDATION"], "alpha_train_frozen")
    sci = _lambda_along(tagged[tagged["dataset_split"] == "OOS"], "alpha_train_frozen")
    desc = _lambda_along(oos_desc, "alpha_oos_descriptive")

    return {
        "discovery_lambda": _lambda_summary(disc, "discovery_lambda", "TRAIN", "TRAIN"),
        "validation_lambda": _lambda_summary(val, "validation_lambda", "TRAIN-frozen", "VALIDATION"),
        "scientific_oos_lambda": _lambda_summary(sci, "scientific_oos_lambda", "TRAIN-frozen", "OOS"),
        "descriptive_oos_lambda": {
            **_lambda_summary(desc, "descriptive_oos_lambda", "OOS-estimated", "OOS"),
            "verdict_input": False,
            "note": "NEVER verdict input. Different scientific object from scientific_oos_lambda.",
        },
        "global_mean_train": global_mean,
        "n_train_l2_cells": len(train_maps["l2"]),
        "n_oos_l2_cells": len(oos_maps["l2"]),
    }


def volatility_summary(df: pd.DataFrame) -> dict:
    out = {"definition": "as-of rolling std of ΔP_cents per possession (window ≤5)", "by_split": {}}
    for split in ("TRAIN", "VALIDATION", "OOS"):
        xs = df[(df["dataset_split"] == split) & df["sigma_P"].notna()]
        if xs.empty:
            out["by_split"][split] = {"n": 0}
            continue
        g = xs.groupby("trade_id")["sigma_P"].mean()
        out["by_split"][split] = {
            "n_rows": int(len(xs)),
            "n_trades": int(g.shape[0]),
            "mean_trade_balanced": float(g.mean()),
            "mean_occupancy": float(xs["sigma_P"].mean()),
            "occupancy_label": "STATE_OCCUPANCY_WEIGHTED DIAGNOSTIC",
            "p50_trade": float(g.median()),
        }
    return out
