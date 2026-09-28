"""PHASE 4–7 — PCA without labels, then descriptive overlays."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from roller.nba_8040_reverse_features.catalog import spec_by_name
from roller.nba_8040_reverse_features.deep_quant.classes import CLASS_LETTER, class_sets
from roller.nba_8040_reverse_features.deep_quant.space import representation
from roller.nba_8040_reverse_features.deep_quant.util import overlap_coef, smd_arrays, wilson_interval
from roller.nba_8040_reverse_features.errors import ReverseFeaturesError


def fit_pca(z: np.ndarray, names: list[str], n_keep: int = 12) -> dict[str, Any]:
    if z.shape[0] < 3 or z.shape[1] < 2:
        raise ReverseFeaturesError("DATA_REQUIRED", "PCA matrix too small")
    u, singular, vt = np.linalg.svd(z, full_matrices=False)
    var = singular**2
    total = float(var.sum())
    explained = var / total
    cumulative = np.cumsum(explained)
    k = min(int(n_keep), z.shape[1], z.shape[0] - 1)
    scores = u[:, :k] * singular[:k]
    loadings = vt[:k, :].T
    recon = []
    for dim in range(1, k + 1):
        approx = (u[:, :dim] * singular[:dim]) @ vt[:dim, :]
        err = float(np.linalg.norm(z - approx) / np.linalg.norm(z))
        recon.append({"k": dim, "relative_frobenius_error": err})
    thresholds = {}
    for pct in (0.50, 0.75, 0.90, 0.95):
        idx = int(np.searchsorted(cumulative, pct) + 1)
        thresholds[f"dims_for_{int(pct*100)}pct"] = min(idx, len(cumulative))
    specs = spec_by_name()
    class_share = []
    for i in range(k):
        weights = loadings[:, i] ** 2
        denom = float(weights.sum()) or 1.0
        bucket: dict[str, float] = {}
        for j, name in enumerate(names):
            if name.startswith("miss_"):
                key = "missingness_flag"
            else:
                spec = specs.get(name)
                key = CLASS_LETTER.get(spec.feature_class, "other") if spec else "other"
            bucket[key] = bucket.get(key, 0.0) + float(weights[j] / denom)
        class_share.append({"pc": i + 1, **bucket})
    top = []
    for i in range(k):
        order = np.argsort(np.abs(loadings[:, i]))[::-1]
        top.append(
            {
                "pc": i + 1,
                "contributors": [
                    {"feature": names[j], "loading": float(loadings[j, i])}
                    for j in order[:12]
                ],
            }
        )
    return {
        "n": int(z.shape[0]),
        "p": int(z.shape[1]),
        "k": k,
        "singular_values": [float(v) for v in singular[:k]],
        "explained": [float(v) for v in explained[:k]],
        "cumulative": [float(v) for v in cumulative[:k]],
        "scores": scores,
        "loadings": loadings,
        "names": names,
        "reconstruction": recon,
        "variance_thresholds": thresholds,
        "class_share": class_share,
        "top": top,
        "sign_convention": "PC sign is SVD-arbitrary; reported as computed",
        "scaling": "z-score on the documented representation",
    }


def _align_labels(meta: pd.DataFrame, labels: pd.DataFrame, index: pd.Index, features: pd.DataFrame) -> pd.DataFrame:
    ids = features.loc[index, "instance_id"].to_numpy()
    labs = labels.set_index("instance_id").loc[ids].reset_index()
    out = meta.copy()
    out["t40"] = labs["t40"].to_numpy()
    out["s"] = labs["s"].to_numpy()
    return out


def composition_on_scores(scores: np.ndarray, meta: pd.DataFrame, k: int = 6) -> list[dict[str, Any]]:
    rows = []
    for i in range(min(k, scores.shape[1])):
        col = scores[:, i]
        q2 = col[meta["period"].to_numpy() == "Q2"]
        q3 = col[meta["period"].to_numpy() == "Q3"]
        rows.append(
            {
                "pc": i + 1,
                "q2_mean": float(q2.mean()),
                "q3_mean": float(q3.mean()),
                "q2_median": float(np.median(q2)),
                "q3_median": float(np.median(q3)),
                "q2_p10": float(np.quantile(q2, 0.10)),
                "q3_p10": float(np.quantile(q3, 0.10)),
                "q2_p90": float(np.quantile(q2, 0.90)),
                "q3_p90": float(np.quantile(q3, 0.90)),
                "smd": smd_arrays(q2, q3),
                "overlap": overlap_coef(q2, q3),
            }
        )
    return rows


def outcome_overlay(scores: np.ndarray, aligned: pd.DataFrame, k: int = 6) -> list[dict[str, Any]]:
    rows = []
    for i in range(min(k, scores.shape[1])):
        col = scores[:, i]
        qs = np.quantile(col, [0.0, 0.2, 0.4, 0.6, 0.8, 1.0])
        uniq = [qs[0]]
        for item in qs[1:]:
            if item > uniq[-1]:
                uniq.append(item)
        if len(uniq) < 3:
            continue
        bins = pd.cut(col, bins=uniq, include_lowest=True)
        for bucket, idx in pd.Series(np.arange(len(col))).groupby(bins, observed=False):
            take = idx.to_numpy()
            t40_n = int(aligned.loc[take, "t40"].sum())
            s_n = int(aligned.loc[take, "s"].sum())
            n = int(len(take))
            lo, hi = wilson_interval(t40_n, n)
            rows.append(
                {
                    "pc": i + 1,
                    "quantile": str(bucket),
                    "n": n,
                    "t40_rate": t40_n / n,
                    "s_rate": s_n / n,
                    "t40_wilson_lo": lo,
                    "t40_wilson_hi": hi,
                    "t40_minus_base": (t40_n / n) - float(aligned["t40"].mean()),
                }
            )
    return rows


def run_pca_suite(features: pd.DataFrame, labels: pd.DataFrame) -> dict[str, Any]:
    sets = class_sets()
    reps = {}
    for kind in ("complete_columns", "complete_case", "missing_indicator"):
        reps[kind] = representation(features, sets["ALL_PRE80"], kind=kind)
    primary = reps["complete_columns"]
    pca = fit_pca(primary["z"], primary["used"])
    aligned = _align_labels(primary["meta"], labels, primary["index"], features)
    composition = composition_on_scores(pca["scores"], aligned)
    smds = [abs(row["smd"] or 0.0) for row in composition[:3]]
    overlaps = [row["overlap"] or 0.0 for row in composition[:3]]
    if max(smds) >= 0.80 or min(overlaps) <= 0.55:
        label = "COMPOSITIONALLY DIFFERENT"
    elif max(smds) <= 0.25 and min(overlaps) >= 0.80:
        label = "COMPOSITIONALLY SIMILAR"
    else:
        label = "COMPOSITIONALLY PARTIAL"
    class_pcas = {}
    for name, cols in sets.items():
        if name.startswith("ALL_PRE80") or name in {"PRICE_TIME", "PRICE_SCORE", "TIME_SCORE", "MARKET_PATH"}:
            continue
        allow = name == "PERIOD"
        try:
            rep = representation(features, cols, kind="complete_columns", allow_period=allow)
            if rep["p"] < 2 or rep["n"] < 10:
                # 1-d period: still report mean difference
                if rep["p"] == 1:
                    class_pcas[name] = {
                        "n": rep["n"],
                        "p": 1,
                        "note": "single complete column; SVD not run",
                        "feature": rep["used"][0],
                    }
                continue
            fitted = fit_pca(rep["z"], rep["used"], n_keep=min(6, rep["p"]))
            aln = _align_labels(rep["meta"], labels, rep["index"], features)
            class_pcas[name] = {
                "n": fitted["n"],
                "p": fitted["p"],
                "explained": fitted["explained"][:4],
                "cumulative": fitted["cumulative"][:4],
                "top": fitted["top"][:3],
                "composition": composition_on_scores(fitted["scores"], aln, k=3),
                "used": fitted["names"],
            }
        except ReverseFeaturesError as exc:
            class_pcas[name] = {"status": "NOT_FIT", "reason": exc.message}
    # robustness PCA on missing-indicator
    mi = reps["missing_indicator"]
    pca_mi = fit_pca(mi["z"], mi["used"])
    return {
        "representations": {
            kind: {
                "n": item["n"],
                "p": item["p"],
                "used": item["used"],
                "zero_coverage_excluded": item["zero_coverage_excluded"],
                "complete_columns": item["complete_columns"],
                "partial_columns": item["partial_columns"],
                "note": item["note"],
            }
            for kind, item in reps.items()
        },
        "primary_kind": "complete_columns",
        "pca": pca,
        "pca_missing_indicator": {
            "n": pca_mi["n"],
            "p": pca_mi["p"],
            "explained": pca_mi["explained"][:8],
            "cumulative": pca_mi["cumulative"][:8],
            "variance_thresholds": pca_mi["variance_thresholds"],
            "top": pca_mi["top"][:4],
        },
        "composition": composition,
        "composition_label": label,
        "outcome_overlay": outcome_overlay(pca["scores"], aligned),
        "aligned": aligned,
        "class_pcas": class_pcas,
        "reps": reps,
    }
