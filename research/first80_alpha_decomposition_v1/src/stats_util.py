"""Binomial CIs, exact tests, clustered bootstrap. Research only."""

from __future__ import annotations

import math

import numpy as np
from scipy.stats import binomtest, beta

import config as C


def wilson(k: int, n: int, z: float = 1.96) -> dict:
    if n <= 0:
        return {"p": None, "lo": None, "hi": None, "n": n, "k": k}
    p = k / n
    z2 = z * z
    den = 1.0 + z2 / n
    center = (p + z2 / (2 * n)) / den
    rad = z * math.sqrt((p * (1 - p) + z2 / (4 * n)) / n) / den
    return {
        "p": p,
        "lo": max(0.0, center - rad),
        "hi": min(1.0, center + rad),
        "n": int(n),
        "k": int(k),
        "method": "wilson",
    }


def clopper_pearson(k: int, n: int, alpha: float = 0.05) -> dict:
    if n <= 0:
        return {"p": None, "lo": None, "hi": None, "n": n, "k": k}
    p = k / n
    lo = 0.0 if k == 0 else float(beta.ppf(alpha / 2.0, k, n - k + 1))
    hi = 1.0 if k == n else float(beta.ppf(1.0 - alpha / 2.0, k + 1, n - k))
    return {"p": p, "lo": lo, "hi": hi, "n": int(n), "k": int(k), "method": "clopper_pearson"}


def exact_binomial(k: int, n: int, p0: float) -> dict:
    if n <= 0:
        return {"n": n, "k": k, "p_hat": None}
    res_one = binomtest(k, n, p0, alternative="greater")
    res_two = binomtest(k, n, p0, alternative="two-sided")
    se = math.sqrt(p0 * (1.0 - p0) / n)
    z = ((k / n) - p0) / se if se > 0 else None
    return {
        "n": int(n),
        "k": int(k),
        "p_hat": k / n,
        "p0": p0,
        "expected_k": p0 * n,
        "excess_k": k - p0 * n,
        "se_null": se,
        "z_approx": z,
        "p_one_sided": float(res_one.pvalue),
        "p_two_sided": float(res_two.pvalue),
        "method": "scipy.stats.binomtest",
    }


def rate_block(k: int, n: int, p0: float | None = None) -> dict:
    w = wilson(k, n)
    cp = clopper_pearson(k, n)
    out = {
        "n": int(n),
        "k": int(k),
        "estimate": None if n <= 0 else k / n,
        "wilson": w,
        "clopper_pearson": cp,
        "se_iid": None if n <= 0 else math.sqrt((k / n) * (1 - k / n) / n),
    }
    if p0 is not None and n > 0:
        out["vs_null"] = exact_binomial(k, n, p0)
        out["diff_from_null"] = (k / n) - p0
    return out


def cluster_bootstrap_mean(values: np.ndarray, cluster_ids: np.ndarray, fn, n: int = C.BOOTSTRAP_DRAWS, seed: int = C.RANDOM_SEED) -> dict:
    """Resample clusters with replacement. Not a causal CI."""
    rng = np.random.default_rng(seed)
    clusters = np.unique(cluster_ids)
    draws = []
    for _ in range(n):
        take = rng.choice(clusters, size=len(clusters), replace=True)
        mask = np.isin(cluster_ids, take)
        if mask.sum() == 0:
            continue
        draws.append(fn(values[mask], cluster_ids[mask]))
    arr = np.array(draws, float)
    arr = arr[np.isfinite(arr)]
    if len(arr) == 0:
        return {"status": "EMPTY", "n_valid": 0}
    return {
        "status": "OK",
        "n_draws": int(len(arr)),
        "mean": float(arr.mean()),
        "p05": float(np.quantile(arr, 0.05)),
        "p95": float(np.quantile(arr, 0.95)),
        "cluster": "resampled_ids",
        "seed": seed,
        "meaning": "Variation under resampling of observed clusters. Not a population causal CI.",
    }


def phi_coef(a: int, b: int, c: int, d: int) -> float | None:
    # [[a,b],[c,d]]
    den = math.sqrt((a + b) * (c + d) * (a + c) * (b + d))
    if den == 0:
        return None
    return (a * d - b * c) / den


def odds_ratio(a: int, b: int, c: int, d: int) -> float | None:
    if b == 0 or c == 0:
        return None
    return (a / b) / (c / d)


def mutual_information(a: int, b: int, c: int, d: int) -> float | None:
    n = a + b + c + d
    if n == 0:
        return None
    mi = 0.0
    rows = [(a, b), (c, d)]
    col0 = a + c
    col1 = b + d
    row_tot = [a + b, c + d]
    cells = [a, b, c, d]
    coords = [(0, 0), (0, 1), (1, 0), (1, 1)]
    cols = [col0, col1]
    for (i, j), x in zip(coords, cells):
        if x == 0:
            continue
        pxy = x / n
        px = row_tot[i] / n
        py = cols[j] / n
        if px > 0 and py > 0:
            mi += pxy * math.log(pxy / (px * py))
    return mi
