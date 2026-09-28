"""Family N2 — tail-risk / CVaR of candle-path drawdown.

N2_LINEAR is the V2-style control (still linear in h → corners).
N2_EU subtracts scaled CVaR from expected utility (nonlinear in h).
"""

from __future__ import annotations

import numpy as np

from . import config as C
from .objective_n1_utility import expected_utility, realized_utility


def cvar_from_bins(p_bins: np.ndarray, q: float) -> np.ndarray:
    """CVaR_q of representative drawdown. p_bins (n, K) aligned to PATH_BINS."""
    dd = np.array([C.BIN_DD[b] for b in C.PATH_BINS], dtype=float)
    order = np.argsort(-dd)
    dd_s = dd[order]
    p_s = p_bins[:, order]
    cdf = np.cumsum(p_s, axis=1)
    # tail mass: worst outcomes until probability q
    tail = np.zeros_like(p_s)
    prev = np.zeros(len(p_bins))
    remain = np.full(len(p_bins), q)
    for j in range(p_s.shape[1]):
        take = np.minimum(p_s[:, j], remain)
        tail[:, j] = take
        remain = remain - take
        prev = cdf[:, j]
    mass = tail.sum(axis=1)
    mass = np.where(mass <= 0, np.nan, mass)
    cvar = (tail * dd_s.reshape(1, -1)).sum(axis=1) / mass
    if np.any(~np.isfinite(cvar) & np.isfinite(p_bins).all(axis=1)):
        # if q exceeds support, use max DD
        cvar = np.where(np.isfinite(cvar), cvar, dd_s[0])
    return cvar


def n2_linear(p_yes: np.ndarray, cvar: np.ndarray, lam: float, h: np.ndarray) -> np.ndarray:
    ev = p_yes * C.X_YES + (1.0 - p_yes) * C.X_NO
    hh = np.asarray(h, dtype=float).reshape(1, -1)
    val = ev[:, None] * hh - lam * cvar[:, None] * hh
    if not np.all(np.isfinite(val)):
        raise RuntimeError("N2 linear non-finite")
    return val


def n2_eu(p_yes: np.ndarray, cvar: np.ndarray, lam: float, h: np.ndarray, gamma: float = 2.0) -> np.ndarray:
    """EU minus a utility-unit penalty for a sure candle-path CVaR hit of size λ h CVaR.

    Does not subtract cents from utils. W0 − λ h CVaR stays inside the $50 snapshot.
    """
    from .objective_n1_utility import u_crra

    eu = expected_utility(p_yes, h, "crra", gamma)
    hh = np.asarray(h, dtype=float).reshape(1, -1)
    w_dd = C.W0_CENTS - lam * cvar[:, None] * hh
    if np.any(w_dd <= 0):
        raise RuntimeError("N2 EU wealth non-positive")
    u0 = u_crra(np.array([C.W0_CENTS]), gamma)[0]
    penalty = u0 - u_crra(w_dd, gamma)
    val = eu - penalty
    if not np.all(np.isfinite(val)):
        raise RuntimeError("N2 EU non-finite")
    return val


def n2_realized(y_yes, h, dd, lam, kind: str, gamma: float = 2.0):
    hh = np.asarray(h, dtype=float)
    x = np.where(np.asarray(y_yes) >= 0.5, C.X_YES, C.X_NO)
    if kind == "linear":
        return hh * x - lam * hh * np.nan_to_num(dd, nan=0.0)
    return realized_utility(y_yes, hh, "crra", gamma) - lam * hh * np.nan_to_num(dd, nan=0.0)
