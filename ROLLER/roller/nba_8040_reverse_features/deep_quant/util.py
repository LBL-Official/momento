"""Shared math and IO. No trading semantics."""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from roller.nba_8040_reverse_features.errors import ReverseFeaturesError

NULL_SEED = 80
BOOT_SEED = 8040
KMEANS_SEED = 8040
PERMUTATIONS = 100
BOOTSTRAPS = 200
KS = (5, 10, 20, 30)
MATCH_QUANTILES = (0.25, 0.50, 0.75)


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def assert_hash(path: Path, expected: str, *, label: str) -> None:
    got = sha256_file(path)
    if got != expected:
        raise ReverseFeaturesError(
            "LOCK_MISMATCH",
            f"{label} hash {got} != frozen {expected}; file was rewritten",
        )


def jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [jsonable(item) for item in value]
    if isinstance(value, (np.floating,)):
        return float(value)
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.bool_,)):
        return bool(value)
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Path):
        return str(value)
    return str(value)


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(jsonable(payload), indent=2, sort_keys=True) + "\n", encoding="utf-8")


def cell(value: Any) -> str:
    if value is None:
        return "—"
    if isinstance(value, float):
        if math.isnan(value):
            return "—"
        return f"{value:.4f}"
    return str(value)


def md_table(rows: list[dict[str, Any]], columns: list[str]) -> str:
    if not rows:
        return "_none_\n"
    header = "| " + " | ".join(columns) + " |"
    rule = "| " + " | ".join("---" for _ in columns) + " |"
    body = ["| " + " | ".join(cell(row.get(col)) for col in columns) + " |" for row in rows]
    return "\n".join([header, rule, *body]) + "\n"


def wilson_interval(k: int, n: int, z: float = 1.96) -> tuple[float | None, float | None]:
    if n <= 0:
        return None, None
    p = k / n
    den = 1.0 + z * z / n
    center = (p + z * z / (2.0 * n)) / den
    half = z * math.sqrt((p * (1.0 - p) + z * z / (4.0 * n)) / n) / den
    return float(center - half), float(center + half)


def smd_arrays(left: np.ndarray, right: np.ndarray) -> float | None:
    a = np.asarray(left, dtype=float)
    b = np.asarray(right, dtype=float)
    a = a[np.isfinite(a)]
    b = b[np.isfinite(b)]
    if len(a) < 2 or len(b) < 2:
        return None
    pooled = math.sqrt((float(a.var()) + float(b.var())) / 2.0)
    if pooled < 1e-12:
        return 0.0
    return float((a.mean() - b.mean()) / pooled)


def overlap_coef(left: np.ndarray, right: np.ndarray, bins: int = 20) -> float | None:
    a = np.asarray(left, dtype=float)
    b = np.asarray(right, dtype=float)
    a = a[np.isfinite(a)]
    b = b[np.isfinite(b)]
    if len(a) < 2 or len(b) < 2:
        return None
    lo = float(min(a.min(), b.min()))
    hi = float(max(a.max(), b.max()))
    if hi <= lo:
        return 1.0
    ha, edges = np.histogram(a, bins=bins, range=(lo, hi), density=True)
    hb, _ = np.histogram(b, bins=bins, range=(lo, hi), density=True)
    width = np.diff(edges)
    return float(np.minimum(ha, hb).dot(width))


def binary_entropy(p: float) -> float:
    if p <= 0.0 or p >= 1.0:
        return 0.0
    return float(-p * math.log2(p) - (1.0 - p) * math.log2(1.0 - p))


def rankdata(values: np.ndarray) -> np.ndarray:
    order = np.argsort(values, kind="mergesort")
    ranks = np.empty(len(values), dtype=float)
    ranks[order] = np.arange(1, len(values) + 1, dtype=float)
    # average ties
    sorted_vals = values[order]
    i = 0
    while i < len(values):
        j = i + 1
        while j < len(values) and sorted_vals[j] == sorted_vals[i]:
            j += 1
        if j - i > 1:
            avg = 0.5 * (i + 1 + j)
            ranks[order[i:j]] = avg
        i = j
    return ranks


def spearman_corr(x: np.ndarray, y: np.ndarray) -> float | None:
    if len(x) < 3:
        return None
    rx = rankdata(x)
    ry = rankdata(y)
    sx = rx.std()
    sy = ry.std()
    if sx < 1e-12 or sy < 1e-12:
        return None
    return float(np.corrcoef(rx, ry)[0, 1])


def mann_whitney_auc(scores: np.ndarray, labels: np.ndarray) -> float | None:
    pos = scores[labels == 1]
    neg = scores[labels == 0]
    if len(pos) == 0 or len(neg) == 0:
        return None
    # P(score_pos > score_neg) + 0.5 P(eq)
    wins = 0.0
    for value in pos:
        wins += float((neg < value).sum() + 0.5 * (neg == value).sum())
    return float(wins / (len(pos) * len(neg)))


def pairwise_euclidean(matrix: np.ndarray) -> np.ndarray:
    # ||x-y||^2 = ||x||^2 + ||y||^2 - 2 x·y
    grams = matrix @ matrix.T
    sq = np.einsum("ij,ij->i", matrix, matrix)
    dist2 = sq[:, None] + sq[None, :] - 2.0 * grams
    np.maximum(dist2, 0.0, out=dist2)
    return np.sqrt(dist2)


def kmeans(matrix: np.ndarray, k: int, *, seed: int, iters: int = 40) -> np.ndarray:
    rng = np.random.default_rng(seed)
    n = len(matrix)
    if n < k:
        raise ReverseFeaturesError("DATA_REQUIRED", "k-means k exceeds n")
    centers = matrix[rng.choice(n, size=k, replace=False)].copy()
    labels = np.zeros(n, dtype=int)
    for _ in range(iters):
        d2 = ((matrix[:, None, :] - centers[None, :, :]) ** 2).sum(axis=2)
        labels = d2.argmin(axis=1)
        for j in range(k):
            members = matrix[labels == j]
            if len(members):
                centers[j] = members.mean(axis=0)
    return labels


def quantile_bins(series: pd.Series, edges: tuple[float, ...] = (1 / 3, 2 / 3)) -> pd.Series:
    values = series.astype(float)
    qs = values.quantile(list(edges))
    cuts = [-np.inf, *[float(qs.iloc[i]) for i in range(len(qs))], np.inf]
    # de-duplicate cuts if ties
    uniq = [cuts[0]]
    for item in cuts[1:]:
        if item > uniq[-1]:
            uniq.append(item)
    if len(uniq) < 3:
        return pd.Series(["mid"] * len(series), index=series.index)
    labels = ["low", "mid", "high"][: len(uniq) - 1]
    return pd.cut(values, bins=uniq, labels=labels, include_lowest=True).astype(str)
