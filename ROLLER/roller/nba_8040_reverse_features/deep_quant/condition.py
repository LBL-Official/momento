"""PHASE 13–19 — matching, balancing, ablation, interactions, temporal, stability, bootstrap."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from roller.nba_8040_reverse_features.deep_quant.classes import LETTER_SETS, TIME, class_sets
from roller.nba_8040_reverse_features.deep_quant.knn_study import (
    cross_period_match,
    distance_geometry,
    knn_tables,
    match_summary,
)
from roller.nba_8040_reverse_features.deep_quant.pca_study import composition_on_scores, fit_pca
from roller.nba_8040_reverse_features.deep_quant.space import representation
from roller.nba_8040_reverse_features.deep_quant.util import (
    BOOT_SEED,
    BOOTSTRAPS,
    MATCH_QUANTILES,
    mann_whitney_auc,
    quantile_bins,
    smd_arrays,
    wilson_interval,
)
from roller.nba_8040_reverse_features.errors import ReverseFeaturesError
from roller.nba_8040_reverse_features.matrix import complete_mask


def threshold_matches(dist: np.ndarray, aligned: pd.DataFrame) -> list[dict[str, Any]]:
    periods = aligned["period"].to_numpy()
    t40 = aligned["t40"].to_numpy(dtype=bool)
    survive = aligned["s"].to_numpy(dtype=bool)
    q2 = np.where(periods == "Q2")[0]
    q3 = np.where(periods == "Q3")[0]
    q2_nn = dist[np.ix_(q2, q3)].argmin(axis=1)
    q2_d = dist[np.ix_(q2, q3)].min(axis=1)
    q3_nn = dist[np.ix_(q3, q2)].argmin(axis=1)
    q3_d = dist[np.ix_(q3, q2)].min(axis=1)
    rows = []
    for label, src, dst, nn, dd, src_name, dst_name in (
        ("Q2_to_Q3", q2, q3, q2_nn, q2_d, "Q2", "Q3"),
        ("Q3_to_Q2", q3, q2, q3_nn, q3_d, "Q3", "Q2"),
    ):
        for q in MATCH_QUANTILES:
            cutoff = float(np.quantile(dd, q))
            keep = dd <= cutoff
            if keep.sum() < 8:
                rows.append({"direction": label, "quantile": q, "n": int(keep.sum()), "status": "n too small"})
                continue
            src_t = t40[src[keep]]
            dst_t = t40[dst[nn[keep]]]
            src_s = survive[src[keep]]
            dst_s = survive[dst[nn[keep]]]
            lo_s, hi_s = wilson_interval(int(src_t.sum()), int(keep.sum()))
            lo_d, hi_d = wilson_interval(int(dst_t.sum()), int(keep.sum()))
            rows.append(
                {
                    "direction": label,
                    "quantile": q,
                    "distance_cutoff": cutoff,
                    "n": int(keep.sum()),
                    "source_t40": float(src_t.mean()),
                    "matched_t40": float(dst_t.mean()),
                    "difference": float(src_t.mean() - dst_t.mean()),
                    "source_s": float(src_s.mean()),
                    "matched_s": float(dst_s.mean()),
                    "source_t40_wilson": [lo_s, hi_s],
                    "matched_t40_wilson": [lo_d, hi_d],
                    "source_period": src_name,
                    "match_period": dst_name,
                }
            )
    return rows


def linear_probability(z: np.ndarray, y: np.ndarray) -> dict[str, Any]:
    n = z.shape[0]
    x = np.column_stack([np.ones(n), z])
    beta, *_ = np.linalg.lstsq(x, y.astype(float), rcond=None)
    fitted = x @ beta
    auc = mann_whitney_auc(fitted, y.astype(int))
    sst = float(((y - y.mean()) ** 2).sum())
    sse = float(((y - fitted) ** 2).sum())
    r2 = None if sst < 1e-12 else 1.0 - sse / sst
    return {"beta0": float(beta[0]), "auc": auc, "r2": r2, "fitted": fitted}


def state_balancing(z: np.ndarray, aligned: pd.DataFrame, dist: np.ndarray) -> dict[str, Any]:
    y = (aligned["period"].to_numpy() == "Q2").astype(int)
    full = linear_probability(z, y)
    return {
        "full_space": {"auc": full["auc"], "r2": full["r2"]},
        "fitted": full["fitted"],
        "y": y,
    }


def propensity_match(fitted: np.ndarray, aligned: pd.DataFrame) -> list[dict[str, Any]]:
    periods = aligned["period"].to_numpy()
    t40 = aligned["t40"].to_numpy(dtype=bool)
    q2 = np.where(periods == "Q2")[0]
    q3 = np.where(periods == "Q3")[0]
    rows = []
    for src, dst, name in ((q2, q3, "Q2_to_Q3"), (q3, q2, "Q3_to_Q2")):
        diffs = np.abs(fitted[src][:, None] - fitted[dst][None, :])
        nn = diffs.argmin(axis=1)
        src_t = t40[src]
        dst_t = t40[dst[nn]]
        rows.append(
            {
                "direction": name,
                "n": int(len(src)),
                "source_t40": float(src_t.mean()),
                "matched_t40": float(dst_t.mean()),
                "difference": float(src_t.mean() - dst_t.mean()),
                "median_propensity_gap": float(np.median(diffs.min(axis=1))),
            }
        )
    return rows


def ablation_table(features: pd.DataFrame, labels: pd.DataFrame) -> list[dict[str, Any]]:
    sets = class_sets()
    rows = []
    for letter, key in LETTER_SETS.items():
        names = sets[key]
        allow = key == "PERIOD"
        try:
            rep = representation(features, names, kind="complete_columns", allow_period=allow)
        except ReverseFeaturesError as exc:
            rows.append({"set": letter, "key": key, "status": exc.message})
            continue
        if rep["p"] < 1 or rep["n"] < 20:
            rows.append({"set": letter, "key": key, "n": rep["n"], "p": rep["p"], "status": "too small"})
            continue
        meta = labels.set_index("instance_id").loc[features.loc[rep["index"], "instance_id"]].reset_index()
        aligned = rep["meta"].copy()
        aligned["t40"] = meta["t40"].to_numpy()
        aligned["s"] = meta["s"].to_numpy()
        if rep["p"] >= 2:
            pca = fit_pca(rep["z"], rep["used"], n_keep=min(4, rep["p"]))
            comp = composition_on_scores(pca["scores"], aligned, k=1)[0]
            pc1_smd = comp["smd"]
            pc1_overlap = comp["overlap"]
        else:
            col = rep["z"][:, 0]
            pc1_smd = smd_arrays(col[aligned["period"].eq("Q2")], col[aligned["period"].eq("Q3")])
            pc1_overlap = None
        knn = knn_tables(rep["z"], aligned, ks=(10,))
        matches = cross_period_match(knn["distance"], aligned, k=10)
        msum = match_summary(matches, k=10)
        q2m = next((row for row in msum if row["source_period"] == "Q2"), None)
        geom = distance_geometry(knn["distance"], aligned)
        rows.append(
            {
                "set": letter,
                "key": key,
                "n": rep["n"],
                "p": rep["p"],
                "pc1_smd_q2_q3": pc1_smd,
                "pc1_overlap": pc1_overlap,
                "knn_k10_agreement": knn["agreement"][0]["mean_agreement"],
                "q2_to_q3_t40_diff": None if q2m is None else q2m["difference"],
                "distance_support": geom["support"],
                "median_cross_over_within": geom["median_cross_over_within"],
            }
        )
    return rows


def interactions(features: pd.DataFrame, labels: pd.DataFrame) -> list[dict[str, Any]]:
    joined = features.merge(labels[["instance_id", "t40", "s"]], on="instance_id")
    pairs = (
        ("frac_period_remaining", "bought_margin"),
        ("frac_game_elapsed", "velocity_5m"),
        ("bought_margin", "delta_5m"),
        ("pregame_cents", "entry_bid_cents"),
        ("range_5m", "entry_bid_cents"),
    )
    rows = []
    for left, right in pairs:
        mask = complete_mask(joined, [left, right])
        block = joined.loc[mask].copy()
        if len(block) < 40:
            continue
        block["_l"] = quantile_bins(block[left])
        block["_r"] = quantile_bins(block[right])
        for (lb, rb), cell in block.groupby(["_l", "_r"], observed=False):
            for period in ("Q2", "Q3", "ALL"):
                sub = cell if period == "ALL" else cell[cell["period"] == period]
                if len(sub) < 8:
                    continue
                t_n = int(sub["t40"].sum())
                n = int(len(sub))
                lo, hi = wilson_interval(t_n, n)
                rows.append(
                    {
                        "left": left,
                        "right": right,
                        "left_bin": str(lb),
                        "right_bin": str(rb),
                        "period": period,
                        "n": n,
                        "t40_rate": t_n / n,
                        "t40_wilson_lo": lo,
                        "t40_wilson_hi": hi,
                    }
                )
    return rows


def temporal_suite(features: pd.DataFrame, labels: pd.DataFrame) -> dict[str, Any]:
    sets = class_sets()
    variants = {
        "all_pre80": sets["ALL_PRE80"],
        "ex_time": sets["ALL_PRE80_EX_TIME"],
        "time_frac_plus_nontime": sets["ALL_PRE80_EX_TIME"] + sets["TIME_FRAC"],
        "time_raw_plus_nontime": sets["ALL_PRE80_EX_TIME"] + sets["TIME_RAW"],
    }
    out = {}
    for name, cols in variants.items():
        rep = representation(features, cols, kind="complete_columns")
        meta = labels.set_index("instance_id").loc[features.loc[rep["index"], "instance_id"]].reset_index()
        aligned = rep["meta"].copy()
        aligned["t40"] = meta["t40"].to_numpy()
        aligned["s"] = meta["s"].to_numpy()
        pca = fit_pca(rep["z"], rep["used"], n_keep=min(6, rep["p"]))
        comp = composition_on_scores(pca["scores"], aligned, k=3)
        knn = knn_tables(rep["z"], aligned, ks=(10,))
        matches = match_summary(cross_period_match(knn["distance"], aligned, k=10), k=10)
        geom = distance_geometry(knn["distance"], aligned)
        out[name] = {
            "n": rep["n"],
            "p": rep["p"],
            "composition": comp,
            "knn_k10_agreement": knn["agreement"][0]["mean_agreement"],
            "matching": matches,
            "support": geom["support"],
            "median_cross_over_within": geom["median_cross_over_within"],
        }
    return out


def stability_suite(
    features: pd.DataFrame,
    labels: pd.DataFrame,
    scores: np.ndarray,
    aligned: pd.DataFrame,
    summary: pd.DataFrame,
    match_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    rows = []
    for split in ("IN_SAMPLE", "VALIDATION", "OOS"):
        mask = aligned["dataset_split"].eq(split).to_numpy()
        if mask.sum() < 20:
            rows.append({"split": split, "n": int(mask.sum()), "status": "n too small"})
            continue
        pc1 = scores[mask, 0]
        periods = aligned.loc[mask, "period"]
        t40 = aligned.loc[mask, "t40"]
        q2 = pc1[periods.eq("Q2")]
        q3 = pc1[periods.eq("Q3")]
        q2_t = t40[periods.eq("Q2")]
        q3_t = t40[periods.eq("Q3")]
        knn = summary[(summary["k"] == 10) & (summary["instance_id"].isin(aligned.loc[mask, "instance_id"]))]
        q2_match = next((row for row in match_rows if row.get("source_period") == "Q2"), None)
        rows.append(
            {
                "split": split,
                "n": int(mask.sum()),
                "q2_n": int(periods.eq("Q2").sum()),
                "q3_n": int(periods.eq("Q3").sum()),
                "pc1_smd": smd_arrays(q2, q3),
                "raw_t40_q2": float(q2_t.mean()) if len(q2_t) else None,
                "raw_t40_q3": float(q3_t.mean()) if len(q3_t) else None,
                "raw_t40_diff": float(q2_t.mean() - q3_t.mean()) if len(q2_t) and len(q3_t) else None,
                "knn_k10_agreement": float(knn["outcome_agreement"].mean()) if len(knn) else None,
            }
        )
    return rows


def bootstrap_suite(
    aligned: pd.DataFrame,
    scores: np.ndarray,
    threshold_rows: list[dict[str, Any]],
    *,
    seed: int = BOOT_SEED,
    n_boot: int = BOOTSTRAPS,
) -> dict[str, Any]:
    rng = np.random.default_rng(seed)
    periods = aligned["period"].to_numpy()
    t40 = aligned["t40"].to_numpy(dtype=bool)
    q2 = periods == "Q2"
    q3 = periods == "Q3"
    raw = []
    pc1 = []
    n = len(aligned)
    for _ in range(n_boot):
        idx = rng.integers(0, n, size=n)
        t = t40[idx]
        p = periods[idx]
        s = scores[idx, 0]
        if (p == "Q2").sum() < 8 or (p == "Q3").sum() < 8:
            continue
        raw.append(float(t[p == "Q2"].mean() - t[p == "Q3"].mean()))
        pc1.append(smd_arrays(s[p == "Q2"], s[p == "Q3"]))
    raw_a = np.array(raw)
    pc1_a = np.array([v for v in pc1 if v is not None], dtype=float)
    q2q3 = next((row for row in threshold_rows if row.get("direction") == "Q2_to_Q3" and row.get("quantile") == 0.5), None)
    return {
        "seed": seed,
        "n_boot": n_boot,
        "raw_t40_diff": {
            "observed": float(t40[q2].mean() - t40[q3].mean()),
            "boot_p025": float(np.quantile(raw_a, 0.025)),
            "boot_p50": float(np.median(raw_a)),
            "boot_p975": float(np.quantile(raw_a, 0.975)),
        },
        "pc1_smd": {
            "boot_p025": float(np.quantile(pc1_a, 0.025)) if len(pc1_a) else None,
            "boot_p50": float(np.median(pc1_a)) if len(pc1_a) else None,
            "boot_p975": float(np.quantile(pc1_a, 0.975)) if len(pc1_a) else None,
        },
        "matched_q50_reference": q2q3,
    }


def clusters(scores: np.ndarray, aligned: pd.DataFrame, *, k: int = 4) -> list[dict[str, Any]]:
    from roller.nba_8040_reverse_features.deep_quant.util import kmeans

    dim = min(3, scores.shape[1])
    labels = kmeans(scores[:, :dim], k, seed=8040)
    rows = []
    for i in range(k):
        mask = labels == i
        block = aligned.loc[mask]
        rows.append(
            {
                "state_region": f"STATE_REGION_{i+1}",
                "n": int(mask.sum()),
                "q2_share": float((block["period"] == "Q2").mean()) if len(block) else None,
                "t40_rate": float(block["t40"].mean()) if len(block) else None,
                "s_rate": float(block["s"].mean()) if len(block) else None,
            }
        )
    return rows
