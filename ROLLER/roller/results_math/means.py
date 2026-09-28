"""Mean, median, sample variance/std, quantiles, skew, kurtosis, t critical."""

from __future__ import annotations

import math
from typing import Any

from roller.results_math.versions import CONFIDENCE_LEVEL

# Student-t 0.975 two-sided. Interpolate; asymptotic z for large df.
_T975: tuple[tuple[int, float], ...] = (
    (1, 12.706204736432095),
    (2, 4.302652729749462),
    (3, 3.1824463052837076),
    (4, 2.7764451051977987),
    (5, 2.570581835636314),
    (6, 2.446911851144699),
    (7, 2.364624251778338),
    (8, 2.306004135204166),
    (9, 2.262157162798205),
    (10, 2.228138851986277),
    (12, 2.178812829667228),
    (15, 2.131449545559323),
    (20, 2.085963447265865),
    (25, 2.059538552753294),
    (30, 2.0422724563012373),
    (40, 2.021075390306273),
    (60, 2.000297822021512),
    (80, 1.990063421509341),
    (100, 1.9839715184496334),
    (120, 1.979930405265311),
    (1000, 1.9623414611334483),
)


def t_critical_975(df: int) -> float | None:
    if df < 1:
        return None
    if df >= 10_000:
        return 1.959963984540054
    prev_df, prev_t = _T975[0]
    if df <= prev_df:
        return prev_t
    for nxt_df, nxt_t in _T975[1:]:
        if df <= nxt_df:
            w = (df - prev_df) / (nxt_df - prev_df)
            return prev_t + w * (nxt_t - prev_t)
        prev_df, prev_t = nxt_df, nxt_t
    return 1.959963984540054


def mean(xs: list[int] | list[float]) -> float | None:
    if not xs:
        return None
    return sum(xs) / len(xs)


def median(xs: list[int] | list[float]) -> float | None:
    if not xs:
        return None
    s = sorted(xs)
    n = len(s)
    mid = n // 2
    if n % 2:
        return float(s[mid])
    return (s[mid - 1] + s[mid]) / 2.0


def sample_variance(xs: list[int] | list[float]) -> float | None:
    n = len(xs)
    if n < 2:
        return None
    m = sum(xs) / n
    return sum((x - m) ** 2 for x in xs) / (n - 1)


def sample_std(xs: list[int] | list[float]) -> float | None:
    v = sample_variance(xs)
    if v is None:
        return None
    return math.sqrt(v)


def quantile(xs: list[int] | list[float], p: float) -> float | None:
    """Linear interpolation, Hyndman-Fan type 7 (index = p*(n-1))."""
    if not xs or not 0.0 <= p <= 1.0:
        return None
    s = sorted(xs)
    n = len(s)
    if n == 1:
        return float(s[0])
    idx = p * (n - 1)
    lo = int(math.floor(idx))
    hi = int(math.ceil(idx))
    if lo == hi:
        return float(s[lo])
    w = idx - lo
    return s[lo] * (1.0 - w) + s[hi] * w


def quantiles(xs: list[int] | list[float]) -> dict[str, float | None]:
    keys = (0.01, 0.05, 0.10, 0.25, 0.50, 0.75, 0.90, 0.95, 0.99)
    names = ("p1", "p5", "p10", "p25", "p50", "p75", "p90", "p95", "p99")
    return {name: quantile(xs, p) for name, p in zip(names, keys)}


def skewness(xs: list[int] | list[float]) -> float | None:
    """Bias-adjusted Fisher-Pearson G1."""
    n = len(xs)
    if n < 3:
        return None
    s = sample_std(xs)
    m = mean(xs)
    if s is None or m is None or s == 0:
        return None
    g = sum(((x - m) / s) ** 3 for x in xs)
    return (n / ((n - 1) * (n - 2))) * g


def excess_kurtosis(xs: list[int] | list[float]) -> float | None:
    """Bias-adjusted excess kurtosis G2."""
    n = len(xs)
    if n < 4:
        return None
    s = sample_std(xs)
    m = mean(xs)
    if s is None or m is None or s == 0:
        return None
    m4 = sum(((x - m) / s) ** 4 for x in xs)
    num = n * (n + 1) * m4
    den = (n - 1) * (n - 2) * (n - 3)
    adj = 3.0 * (n - 1) ** 2 / ((n - 2) * (n - 3))
    return num / den - adj


def _log_beta(a: float, b: float) -> float:
    return math.lgamma(a) + math.lgamma(b) - math.lgamma(a + b)


def _betacf(a: float, b: float, x: float) -> float:
    """Modified Lentz continued fraction for incomplete beta."""
    max_iter = 200
    eps = 3e-12
    fpmin = 1e-30
    qab = a + b
    qap = a + 1.0
    qam = a - 1.0
    c = 1.0
    d = 1.0 - qab * x / qap
    if abs(d) < fpmin:
        d = fpmin
    d = 1.0 / d
    h = d
    for m in range(1, max_iter + 1):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        if abs(d) < fpmin:
            d = fpmin
        c = 1.0 + aa / c
        if abs(c) < fpmin:
            c = fpmin
        d = 1.0 / d
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        if abs(d) < fpmin:
            d = fpmin
        c = 1.0 + aa / c
        if abs(c) < fpmin:
            c = fpmin
        d = 1.0 / d
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < eps:
            return h
    return h


def regularized_incomplete_beta(x: float, a: float, b: float) -> float:
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    if a <= 0.0 or b <= 0.0:
        return float("nan")
    front = math.exp(a * math.log(x) + b * math.log(1.0 - x) - _log_beta(a, b))
    if x < (a + 1.0) / (a + b + 2.0):
        return front * _betacf(a, b, x) / a
    return 1.0 - front * _betacf(b, a, 1.0 - x) / b


def student_t_two_sided_pvalue(t_stat: float, df: int) -> float | None:
    """Two-sided p-value for H0: mean = 0. I_{df/(df+t²)}(df/2, 1/2)."""
    if df < 1 or not math.isfinite(t_stat):
        return None
    x = df / (df + t_stat * t_stat)
    p = regularized_incomplete_beta(x, df / 2.0, 0.5)
    if not math.isfinite(p):
        return None
    return min(1.0, max(0.0, p))


def t_interval(
    xs: list[int] | list[float],
    *,
    confidence_level: float = CONFIDENCE_LEVEL,
) -> dict[str, Any] | None:
    n = len(xs)
    if n < 2:
        return None
    m = mean(xs)
    s = sample_std(xs)
    tcrit = t_critical_975(n - 1)
    if m is None or s is None or tcrit is None:
        return None
    se = s / math.sqrt(n)
    t_stat = None if se == 0 else m / se
    p_value = student_t_two_sided_pvalue(t_stat, n - 1) if t_stat is not None else None
    half = tcrit * se
    lo, hi = m - half, m + half
    return {
        "estimate": m,
        "lower": lo,
        "upper": hi,
        "confidence_level": confidence_level,
        "method": "student_t",
        "n": n,
        "std": s,
        "standard_error": se,
        "t_statistic": t_stat,
        "p_value": p_value,
        "df": n - 1,
        "null": "EV = 0",
        "zero_inside_ci": lo <= 0.0 <= hi,
        "t_critical": tcrit,
        "assumption": "IID-like mean. Sports observations are not assumed independent.",
    }
