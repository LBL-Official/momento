"""PHASE 2–3 — analytical matrix, missingness representations, correlation."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from roller.nba_8040_reverse_features.catalog import FORBIDDEN_NAMES, spec_by_name
from roller.nba_8040_reverse_features.deep_quant.classes import PERIOD, all_pre80_names, class_sets
from roller.nba_8040_reverse_features.errors import ReverseFeaturesError
from roller.nba_8040_reverse_features.leakage import assert_predictive_columns
from roller.nba_8040_reverse_features.matrix import complete_mask

STATUS_OK = "OBSERVED"


def assert_no_future(names: list[str]) -> None:
    for name in names:
        key = name[5:] if name.startswith("miss_") else name
        if key.lower() in FORBIDDEN_NAMES:
            raise ReverseFeaturesError("LEAKAGE", f"future column {name}")
        if name.startswith("miss_"):
            continue
        if name in PERIOD:
            continue
        assert_predictive_columns([name])


def coverage(features: pd.DataFrame, name: str) -> float:
    return float(complete_mask(features, [name]).mean())


def zscore_observed(values: np.ndarray, observed: np.ndarray) -> tuple[np.ndarray, float, float]:
    present = values[observed]
    if len(present) == 0:
        raise ReverseFeaturesError("DATA_REQUIRED", "cannot z-score a fully missing column")
    mean = float(present.mean())
    std = float(present.std())
    if std < 1e-12:
        std = 1.0
    out = np.zeros(len(values), dtype=float)
    out[observed] = (values[observed] - mean) / std
    # missing stays 0 after z-score = observed mean, not economic zero
    return out, mean, std


def representation(
    features: pd.DataFrame,
    names: list[str],
    *,
    kind: str,
    allow_period: bool = False,
) -> dict[str, Any]:
    usable = []
    for name in names:
        if name in PERIOD and not allow_period:
            continue
        if name not in features.columns:
            raise ReverseFeaturesError("DATA_REQUIRED", f"missing {name}")
        usable.append(name)
    if not allow_period:
        assert_no_future(usable)

    zero = [name for name in usable if coverage(features, name) == 0.0]
    complete = [name for name in usable if coverage(features, name) == 1.0]
    partial = [name for name in usable if 0.0 < coverage(features, name) < 1.0]
    meta = features[["instance_id", "period", "dataset_split"]].copy()

    if kind == "complete_columns":
        cols = complete
        matrix = features[cols].to_numpy(dtype=float)
        mean = matrix.mean(axis=0)
        std = matrix.std(axis=0, ddof=0)
        std = np.where(std < 1e-12, 1.0, std)
        z = (matrix - mean) / std
        used = list(cols)
        index = features.index
        note = "fully observed columns only; no fill; N=604 if those columns exist"
    elif kind == "complete_case":
        cols = [name for name in usable if name not in zero]
        mask = complete_mask(features, cols)
        block = features.loc[mask, cols]
        matrix = block.to_numpy(dtype=float)
        mean = matrix.mean(axis=0)
        std = matrix.std(axis=0, ddof=0)
        std = np.where(std < 1e-12, 1.0, std)
        z = (matrix - mean) / std
        used = list(cols)
        index = block.index
        meta = meta.loc[index]
        note = "drop rows with any missing among positive-coverage columns; no fill"
    elif kind == "missing_indicator":
        z_cols = []
        used = []
        means = {}
        stds = {}
        n = len(features)
        blocks = []
        for name in complete:
            values = features[name].to_numpy(dtype=float)
            col, mean, std = zscore_observed(values, np.isfinite(values))
            blocks.append(col)
            used.append(name)
            means[name] = mean
            stds[name] = std
        for name in partial:
            values = features[name].to_numpy(dtype=float)
            obs = complete_mask(features, [name]).to_numpy()
            col, mean, std = zscore_observed(values, obs)
            blocks.append(col)
            used.append(name)
            miss = (~obs).astype(float)
            if miss.min() != miss.max():
                blocks.append(miss)
                used.append(f"miss_{name}")
            means[name] = mean
            stds[name] = std
        if not blocks:
            raise ReverseFeaturesError("DATA_REQUIRED", "missing-indicator matrix empty")
        z = np.column_stack(blocks)
        index = features.index
        note = (
            "z-score on observed values; missing residual set to 0 (observed mean), "
            "plus miss_* flag. Not an economic zero fill."
        )
        mean = means
        std = stds
    else:
        raise ReverseFeaturesError("DATA_REQUIRED", f"unknown representation {kind}")

    return {
        "kind": kind,
        "z": z,
        "used": used,
        "index": index,
        "meta": meta.reset_index(drop=True),
        "n": int(z.shape[0]),
        "p": int(z.shape[1]),
        "zero_coverage_excluded": zero,
        "complete_columns": complete,
        "partial_columns": partial,
        "note": note,
        "mean": mean,
        "std": std,
    }


def raw_matrix_frame(features: pd.DataFrame) -> pd.DataFrame:
    names = all_pre80_names() + [name for name in PERIOD if name in features.columns]
    assert_no_future([name for name in names if name not in PERIOD])
    extra = {}
    for name in names:
        extra[name] = features[name]
        extra[f"miss_{name}"] = (~complete_mask(features, [name])).astype(int)
    return pd.concat([features[["instance_id", "period", "dataset_split"]], pd.DataFrame(extra)], axis=1)


def correlate(features: pd.DataFrame, names: list[str]) -> dict[str, Any]:
    cols = [name for name in names if coverage(features, name) == 1.0]
    if len(cols) < 2:
        return {"n_features": len(cols), "pairs": []}
    block = features[cols].astype(float)
    pearson = block.corr(method="pearson")
    spearman = block.corr(method="spearman")
    pairs = []
    for i, left in enumerate(cols):
        for right in cols[i + 1 :]:
            p = float(pearson.at[left, right])
            s = float(spearman.at[left, right])
            if abs(p) >= 0.80 or abs(s) >= 0.80:
                pairs.append(
                    {
                        "left": left,
                        "right": right,
                        "pearson": p,
                        "spearman": s,
                        "kind": "near_duplicate" if abs(p) >= 0.95 else "highly_correlated",
                    }
                )
    pairs.sort(key=lambda row: abs(row["pearson"]), reverse=True)
    return {
        "n_features": len(cols),
        "n": int(len(block)),
        "pearson": pearson,
        "spearman": spearman,
        "pairs": pairs,
        "note": "computed on fully observed columns only; correlated columns are not deleted",
    }
