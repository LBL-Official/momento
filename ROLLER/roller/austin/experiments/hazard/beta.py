"""Jeffreys Beta-Binomial estimator. No scipy. Prior is not tuned."""

from __future__ import annotations

import math
from typing import Any

from roller.austin.experiments.hazard.ids import JEFFREYS_A, JEFFREYS_B, UNAVAILABLE


def _log_beta(a: float, b: float) -> float:
    return math.lgamma(a) + math.lgamma(b) - math.lgamma(a + b)


def _betacf(a: float, b: float, x: float, *, max_iter: int = 200, eps: float = 1e-12) -> float:
    am1 = 1.0
    bm1 = 1.0
    az = 1.0
    qab = a + b
    qap = a + 1.0
    qam = a - 1.0
    bz = 1.0 - qab * x / qap
    for m in range(1, max_iter + 1):
        em = float(m)
        tem = em + em
        d = em * (b - em) * x / ((qam + tem) * (a + tem))
        ap = az + d * am1
        bp = bz + d * bm1
        d = -(a + em) * (qab + em) * x / ((a + tem) * (qap + tem))
        app = ap + d * az
        bpp = bp + d * bz
        am1 = ap / bpp
        bm1 = bp / bpp
        azold = az
        az = app / bpp
        bz = 1.0
        if abs(az - azold) < eps * abs(az):
            return az
    return az


def regularized_incomplete_beta(x: float, a: float, b: float) -> float:
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    if a <= 0.0 or b <= 0.0:
        raise ValueError("beta parameters must be positive")
    ln = a * math.log(x) + b * math.log(1.0 - x) - _log_beta(a, b)
    front = math.exp(ln)
    if x < (a + 1.0) / (a + b + 2.0):
        return front * _betacf(a, b, x) / a
    return 1.0 - front * _betacf(b, a, 1.0 - x) / b


def beta_ppf(p: float, a: float, b: float) -> float:
    if p <= 0.0:
        return 0.0
    if p >= 1.0:
        return 1.0
    lo, hi = 0.0, 1.0
    for _ in range(80):
        mid = 0.5 * (lo + hi)
        if regularized_incomplete_beta(mid, a, b) < p:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


def jeffreys_estimate(event_n: int, support_n: int) -> dict[str, Any]:
    if support_n <= 0:
        return {
            "p_hat": None,
            "support_n": 0,
            "event_n": 0,
            "posterior_lower": None,
            "posterior_upper": None,
            "status": UNAVAILABLE,
            "alpha": None,
            "beta": None,
        }
    y = int(event_n)
    n = int(support_n)
    alpha = y + JEFFREYS_A
    beta = (n - y) + JEFFREYS_B
    return {
        "p_hat": alpha / (n + 1.0),
        "support_n": n,
        "event_n": y,
        "posterior_lower": beta_ppf(0.025, alpha, beta),
        "posterior_upper": beta_ppf(0.975, alpha, beta),
        "status": "OBSERVED",
        "alpha": alpha,
        "beta": beta,
    }
