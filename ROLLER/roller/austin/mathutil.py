"""Scaler, SVD PCA, pairwise Euclidean. No sklearn."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd


def zscore_fit(frame: pd.DataFrame) -> tuple[pd.Series, pd.Series]:
    mu = frame.mean(axis=0)
    sd = frame.std(axis=0, ddof=0).replace(0.0, 1.0)
    sd = sd.mask(sd == 0.0, 1.0)
    return mu, sd


def zscore_apply(frame: pd.DataFrame, mu: pd.Series, sd: pd.Series) -> pd.DataFrame:
    return (frame - mu) / sd.replace(0.0, 1.0)


def pca_fit(z: np.ndarray, k: int) -> dict[str, Any]:
    x = np.asarray(z, dtype=float)
    if x.size == 0:
        return {"components": np.zeros((0, 0)), "mean": np.zeros(0), "explained": np.zeros(0)}
    x = np.nan_to_num(x, nan=0.0)
    u, s, vt = np.linalg.svd(x, full_matrices=False)
    kk = min(int(k), vt.shape[0])
    ev = (s**2)
    tot = float(ev.sum()) if ev.size else 1.0
    explained = ev[:kk] / tot if tot else ev[:kk]
    return {
        "components": vt[:kk],
        "singular": s[:kk],
        "explained": explained,
        "cumulative": np.cumsum(explained),
    }


def pca_transform(z: np.ndarray, components: np.ndarray) -> np.ndarray:
    x = np.nan_to_num(np.asarray(z, dtype=float), nan=0.0)
    if components.size == 0:
        return np.zeros((x.shape[0], 0))
    return x @ components.T


def pairwise_euclid(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    a2 = (a * a).sum(axis=1, keepdims=True)
    b2 = (b * b).sum(axis=1, keepdims=True).T
    return np.sqrt(np.maximum(a2 + b2 - 2.0 * a @ b.T, 0.0))


def pearson(x: np.ndarray, y: np.ndarray) -> float:
    xx = np.asarray(x, dtype=float)
    yy = np.asarray(y, dtype=float)
    mask = np.isfinite(xx) & np.isfinite(yy)
    if int(mask.sum()) < 3:
        return float("nan")
    return float(np.corrcoef(xx[mask], yy[mask])[0, 1])


def spearman(x: np.ndarray, y: np.ndarray) -> float:
    xx = np.asarray(x, dtype=float)
    yy = np.asarray(y, dtype=float)
    mask = np.isfinite(xx) & np.isfinite(yy)
    if int(mask.sum()) < 3:
        return float("nan")
    rx = pd.Series(xx[mask]).rank().to_numpy()
    ry = pd.Series(yy[mask]).rank().to_numpy()
    return float(np.corrcoef(rx, ry)[0, 1])
