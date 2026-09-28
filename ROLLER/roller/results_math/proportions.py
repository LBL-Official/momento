"""Binomial rates. Wilson default. Clopper–Pearson optional. Not a CI for edge."""

from __future__ import annotations

import math
from typing import Any

from roller.results_math.versions import CONFIDENCE_LEVEL, WILSON_Z


def rate(successes: int, n: int) -> dict[str, Any] | None:
    if n <= 0:
        return None
    return {
        "successes": int(successes),
        "denominator": int(n),
        "p_hat": successes / n,
        "percentage": 100.0 * successes / n,
    }


def wilson_interval(
    successes: int,
    n: int,
    *,
    z: float = WILSON_Z,
    confidence_level: float = CONFIDENCE_LEVEL,
) -> dict[str, Any] | None:
    if n <= 0:
        return None
    p = successes / n
    z2 = z * z
    denom = 1.0 + z2 / n
    center = (p + z2 / (2.0 * n)) / denom
    half = (z * math.sqrt(p * (1.0 - p) / n + z2 / (4.0 * n * n))) / denom
    return {
        "lower": max(0.0, center - half),
        "upper": min(1.0, center + half),
        "center": center,
        "confidence_level": confidence_level,
        "method": "wilson",
        "numerator": int(successes),
        "denominator": int(n),
        "p_hat": p,
        "z": z,
    }


def _log_pmf(k: int, n: int, p: float) -> float:
    if p <= 0.0:
        return 0.0 if k == 0 else float("-inf")
    if p >= 1.0:
        return 0.0 if k == n else float("-inf")
    return (
        math.lgamma(n + 1)
        - math.lgamma(k + 1)
        - math.lgamma(n - k + 1)
        + k * math.log(p)
        + (n - k) * math.log(1.0 - p)
    )


def _binom_cdf(k: int, n: int, p: float) -> float:
    """P(X <= k) for X ~ Bin(n, p)."""
    if k < 0:
        return 0.0
    if k >= n:
        return 1.0
    if p <= 0.0:
        return 1.0
    if p >= 1.0:
        return 0.0
    total = 0.0
    for i in range(k + 1):
        total += math.exp(_log_pmf(i, n, p))
        if total >= 1.0:
            return 1.0
    return min(1.0, total)


def _binom_sf(k: int, n: int, p: float) -> float:
    """P(X >= k)."""
    if k <= 0:
        return 1.0
    if k > n:
        return 0.0
    return 1.0 - _binom_cdf(k - 1, n, p)


def clopper_pearson(
    successes: int,
    n: int,
    *,
    confidence_level: float = CONFIDENCE_LEVEL,
) -> dict[str, Any] | None:
    if n <= 0:
        return None
    alpha = 1.0 - confidence_level
    x = int(successes)
    target = alpha / 2.0

    def _solve(fn, *, increasing: bool) -> float:
        lo, hi = 0.0, 1.0
        for _ in range(80):
            mid = (lo + hi) / 2.0
            val = fn(mid)
            if increasing:
                if val < target:
                    lo = mid
                else:
                    hi = mid
            elif val > target:
                lo = mid
            else:
                hi = mid
        return (lo + hi) / 2.0

    lower = 0.0 if x == 0 else _solve(lambda p: _binom_sf(x, n, p), increasing=True)
    upper = 1.0 if x == n else _solve(lambda p: _binom_cdf(x, n, p), increasing=False)
    return {
        "lower": lower,
        "upper": upper,
        "confidence_level": confidence_level,
        "method": "clopper_pearson",
        "numerator": x,
        "denominator": int(n),
        "p_hat": x / n,
    }
