"""PCA on the pre-80 matrix. numpy only. Not a signal."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from roller.nba_8040_reverse_features.errors import ReverseFeaturesError
from roller.nba_8040_reverse_features.matrix import coverage_names, standardized_matrix


def run_pca(
    features: pd.DataFrame,
    labels: pd.DataFrame,
    n_components: int = 6,
    names: list[str] | None = None,
    *,
    min_frac: float = 0.90,
) -> dict[str, Any]:
    used_names = names or coverage_names(features, min_frac=min_frac)
    matrix, used, index = standardized_matrix(features, used_names)
    n_components = min(int(n_components), matrix.shape[0] - 1, matrix.shape[1])
    if n_components < 2:
        raise ReverseFeaturesError("DATA_REQUIRED", "too few complete rows for PCA")
    u, singular, vt = np.linalg.svd(matrix, full_matrices=False)
    var = singular**2
    explained = var / var.sum()
    scores = u[:, :n_components] * singular[:n_components]
    loadings = vt[:n_components, :].T
    kept = features.loc[index].reset_index(drop=True)
    labs = labels.set_index("instance_id").loc[kept["instance_id"]].reset_index(drop=True)
    points = []
    for i in range(len(kept)):
        points.append(
            {
                "instance_id": kept.at[i, "instance_id"],
                "period": kept.at[i, "period"],
                "s": bool(labs.at[i, "s"]),
                "pc1": float(scores[i, 0]),
                "pc2": float(scores[i, 1]),
                "pc3": float(scores[i, 2]) if n_components > 2 else None,
            }
        )
    load_rows = []
    for i, name in enumerate(used):
        load_rows.append(
            {
                "feature": name,
                "pc1": float(loadings[i, 0]),
                "pc2": float(loadings[i, 1]),
                "pc3": float(loadings[i, 2]) if n_components > 2 else None,
            }
        )
    variance = [
        {
            "component": f"PC{i+1}",
            "explained": float(explained[i]),
            "cumulative": float(explained[: i + 1].sum()),
        }
        for i in range(min(n_components, len(explained)))
    ]
    return {
        "n": int(matrix.shape[0]),
        "n_features": len(used),
        "features": list(used),
        "coverage_min_frac": None if names is not None else 0.90,
        "missing_treatment": "complete-case on OBSERVED matrix features; no mean-fill",
        "scaling": "z-score",
        "points": points,
        "loadings": load_rows,
        "variance": variance,
    }
