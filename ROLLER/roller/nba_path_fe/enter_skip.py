"""Enter / skip decision. Touch-80 kept. No Family E. No post-t_s."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from roller.nba_path_fe.config import DEFAULT, PathFeConfig
from roller.nba_path_fe.mathutil import pairwise_euclid


@dataclass
class KnnFit:
    k: int
    tau: float
    dmax: float
    train_x: np.ndarray
    train_y: np.ndarray
    train_ids: np.ndarray
    columns: tuple[str, ...]


def _weights(dist: np.ndarray) -> np.ndarray:
    return 1.0 / np.maximum(dist, 1e-6)


def fit_knn(train_x: np.ndarray, train_y: np.ndarray, train_ids: np.ndarray, columns: tuple[str, ...], k: int, tau: float, dmax: float) -> KnnFit:
    return KnnFit(k, tau, dmax, train_x, train_y, train_ids, columns)


def decide(
    x: np.ndarray,
    fit: KnnFit,
    *,
    regime_ok: np.ndarray | None = None,
    query_ids: np.ndarray | None = None,
    cfg: PathFeConfig = DEFAULT,
) -> pd.DataFrame:
    """Distance-weighted KNN. Skip if <k_min usable neighbors or regime fail."""
    n = int(x.shape[0])
    d = pairwise_euclid(x, fit.train_x)
    if query_ids is not None:
        for i, eid in enumerate(query_ids):
            d[i, fit.train_ids == eid] = np.inf
    keep = np.zeros(n, dtype=int)
    score = np.full(n, np.nan)
    n_used = np.zeros(n, dtype=int)
    skipped_reason = np.array(["ok"] * n, dtype=object)
    for i in range(n):
        if regime_ok is not None and not bool(regime_ok[i]):
            skipped_reason[i] = "regime_gate"
            continue
        if np.any(np.isnan(x[i])):
            skipped_reason[i] = "feature_missing"
            continue
        di = d[i]
        usable = np.isfinite(di) & (di <= fit.dmax)
        idx = np.where(usable)[0]
        if idx.size < cfg.k_min:
            # Score anyway on k nearest so r is not dominated by dmax skips.
            finite = np.where(np.isfinite(di))[0]
            if finite.size < cfg.k_min:
                skipped_reason[i] = "k_min"
                continue
            idx = finite
        order = idx[np.argsort(di[idx], kind="mergesort")]
        take = order[: fit.k]
        w = _weights(di[take])
        p = float(np.sum(w * fit.train_y[take]) / np.sum(w))
        score[i] = p
        n_used[i] = int(take.size)
        if p >= fit.tau:
            keep[i] = 1
            skipped_reason[i] = "enter"
        else:
            skipped_reason[i] = "below_tau"
    return pd.DataFrame(
        {
            "keep": keep,
            "p_hat": score,
            "n_neighbors": n_used,
            "reason": skipped_reason,
        }
    )


def p_k_identity(p0: float, p_r: float, r: float) -> float:
    if r >= 1.0 or r < 0.0:
        return float("nan")
    return p0 + (r / (1.0 - r)) * (p0 - p_r)
