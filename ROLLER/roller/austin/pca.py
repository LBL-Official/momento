"""Train-only PCA. Outcomes never enter the matrix."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from roller.austin.config import DEFAULT, AustinConfig
from roller.austin.errors import AustinError
from roller.austin.leakage import FORBIDDEN_FEATURE_NAMES
from roller.austin.mathutil import pca_fit, pca_transform, zscore_apply, zscore_fit


def complete_matrix(frame: pd.DataFrame, names: list[str]) -> tuple[pd.DataFrame, pd.Index]:
    work = frame[names].apply(pd.to_numeric, errors="coerce")
    mask = work.notna().all(axis=1)
    return work.loc[mask], work.index[mask]


def fit_pca(
    frame: pd.DataFrame,
    names: list[str],
    *,
    k: int | None = None,
    cfg: AustinConfig = DEFAULT,
) -> dict[str, Any]:
    leaked = [n for n in names if n in FORBIDDEN_FEATURE_NAMES]
    if leaked:
        raise AustinError("LEAKAGE", f"PCA names include outcomes {leaked}")
    mat, index = complete_matrix(frame, names)
    if mat.empty:
        raise AustinError("INSUFFICIENT_SAMPLE", "no complete rows for PCA")
    mu, sd = zscore_fit(mat)
    z = zscore_apply(mat, mu, sd).to_numpy(dtype=float)
    fitted = pca_fit(z, int(k or cfg.pca_k))
    scores = pca_transform(z, fitted["components"])
    loadings = []
    comps = np.asarray(fitted["components"])
    for i, ev in enumerate(fitted["explained"]):
        row = {
            "pc": i + 1,
            "explained_variance_ratio": float(ev),
            "cumulative_explained_variance": float(fitted["cumulative"][i]),
            "loadings": {names[j]: float(comps[i, j]) for j in range(len(names))},
        }
        loadings.append(row)
    return {
        "names": list(names),
        "mu": {c: float(mu[c]) for c in names},
        "sd": {c: float(sd[c]) for c in names},
        "components": comps,
        "explained": [float(x) for x in fitted["explained"]],
        "cumulative": [float(x) for x in fitted["cumulative"]],
        "scores": scores,
        "index": index,
        "loadings": loadings,
        "n": int(mat.shape[0]),
        "k": int(comps.shape[0]),
        "pca_version": cfg.pca_version,
        "feature_schema_version": cfg.feature_schema_version,
    }


def transform_row(numeric: dict[str, float | None], model: dict[str, Any]) -> np.ndarray | None:
    names = list(model["names"])
    vec = []
    for name in names:
        val = numeric.get(name)
        if val is None or not np.isfinite(val):
            return None
        vec.append(float(val))
    mu = np.array([model["mu"][n] for n in names], dtype=float)
    sd = np.array([model["sd"][n] for n in names], dtype=float)
    sd = np.where(sd == 0.0, 1.0, sd)
    z = (np.array(vec, dtype=float) - mu) / sd
    return pca_transform(z.reshape(1, -1), np.asarray(model["components"]))[0]
