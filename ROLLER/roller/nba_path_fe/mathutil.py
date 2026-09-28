"""Integer-safe helpers. No sklearn."""

from __future__ import annotations

import hashlib
from typing import Iterable

import numpy as np
import pandas as pd


def sha256_hex(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def episode_id(game_id: str, market_id: str, side: str, ts_iso: str) -> str:
    return sha256_hex(f"{game_id}|{market_id}|{side}|{ts_iso}|FIRST80")[:16]


def zscore(frame: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series, pd.Series]:
    mu = frame.mean(axis=0)
    sd = frame.std(axis=0, ddof=0).replace(0.0, 1.0)
    return (frame - mu) / sd, mu, sd


def apply_z(frame: pd.DataFrame, mu: pd.Series, sd: pd.Series) -> pd.DataFrame:
    return (frame - mu) / sd.replace(0.0, 1.0)


def pava_isotonic(x: np.ndarray, y: np.ndarray) -> np.ndarray:
    """PAVA: nondecreasing fit of y on sorted x. Returns predictions in original order."""
    order = np.argsort(np.asarray(x, dtype=float), kind="mergesort")
    ys = np.asarray(y, dtype=float)[order]
    n = int(ys.size)
    if n == 0:
        return np.asarray(y, dtype=float)
    level = ys.copy()
    weight = np.ones(n, dtype=float)
    # adjacent violator merge
    i = 0
    while i < n - 1:
        if level[i] <= level[i + 1] + 1e-15:
            i += 1
            continue
        w = weight[i] + weight[i + 1]
        v = (level[i] * weight[i] + level[i + 1] * weight[i + 1]) / w
        level[i] = v
        level[i + 1] = v
        weight[i] = w
        weight[i + 1] = w
        j = i
        while j > 0 and level[j - 1] > level[j] + 1e-15:
            w2 = weight[j - 1] + weight[j]
            v2 = (level[j - 1] * weight[j - 1] + level[j] * weight[j]) / w2
            level[j - 1] = v2
            level[j] = v2
            weight[j - 1] = w2
            weight[j] = w2
            j -= 1
        i = max(j, 0)
    pred = np.empty(n, dtype=float)
    pred[order] = level
    return pred


def fit_logistic(x: np.ndarray, y: np.ndarray, l2: float = 1e-2, steps: int = 40) -> np.ndarray:
    n = int(x.shape[0])
    xb = np.concatenate([np.ones((n, 1)), np.asarray(x, dtype=float)], axis=1)
    w = np.zeros(xb.shape[1], dtype=float)
    yy = np.asarray(y, dtype=float)
    for _ in range(steps):
        z = xb @ w
        p = 1.0 / (1.0 + np.exp(-np.clip(z, -30.0, 30.0)))
        wts = p * (1.0 - p) + 1e-9
        penalty = l2 * np.concatenate([[0.0], w[1:]])
        grad = xb.T @ (p - yy) + penalty
        hess = xb.T @ (xb * wts[:, None])
        hess = hess + l2 * np.diag(np.concatenate([[0.0], np.ones(xb.shape[1] - 1)]))
        try:
            step = np.linalg.solve(hess, grad)
        except np.linalg.LinAlgError:
            break
        w = w - step
        if float(np.max(np.abs(step))) < 1e-8:
            break
    return w


def predict_logistic(x: np.ndarray, w: np.ndarray) -> np.ndarray:
    n = int(x.shape[0])
    xb = np.concatenate([np.ones((n, 1)), np.asarray(x, dtype=float)], axis=1)
    z = xb @ w
    return 1.0 / (1.0 + np.exp(-np.clip(z, -30.0, 30.0)))


def kmeans(x: np.ndarray, k: int, seed: int, iters: int = 40) -> tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(seed)
    n = int(x.shape[0])
    dim = int(x.shape[1]) if x.ndim == 2 else 0
    if n == 0:
        return np.array([], dtype=int), np.zeros((k, dim))
    idx = rng.choice(n, size=min(k, n), replace=False)
    cents = np.asarray(x[idx], dtype=float).copy()
    if cents.shape[0] < k:
        pad = np.repeat(cents[:1], k - cents.shape[0], axis=0)
        cents = np.vstack([cents, pad])
    labels = np.zeros(n, dtype=int)
    for _ in range(iters):
        d = ((x[:, None, :] - cents[None, :, :]) ** 2).sum(axis=2)
        labels = np.argmin(d, axis=1)
        for j in range(k):
            mask = labels == j
            if int(mask.sum()) == 0:
                cents[j] = x[int(rng.integers(0, n))]
            else:
                cents[j] = x[mask].mean(axis=0)
    return labels, cents


def pairwise_euclid(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    a2 = (a * a).sum(axis=1, keepdims=True)
    b2 = (b * b).sum(axis=1, keepdims=True).T
    return np.sqrt(np.maximum(a2 + b2 - 2.0 * a @ b.T, 0.0))


def auc_binary(y: Iterable[int], s: Iterable[float]) -> float:
    yy = np.asarray(list(y), dtype=int)
    ss = np.asarray(list(s), dtype=float)
    pos = ss[yy == 1]
    neg = ss[yy == 0]
    if pos.size == 0 or neg.size == 0:
        return float("nan")
    correct = float(np.sum(pos[:, None] > neg[None, :]))
    ties = float(np.sum(pos[:, None] == neg[None, :]))
    return (correct + 0.5 * ties) / float(pos.size * neg.size)
