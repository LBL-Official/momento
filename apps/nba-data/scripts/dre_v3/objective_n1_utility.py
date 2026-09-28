"""Family N1 — expected utility of theoretical retained exposure.

W(h) = W0 + h × X_terminal
X_terminal ∈ {+20, −80} cents from the 80¢ entry proxy.
Does not assume a sale at the current bid.
"""

from __future__ import annotations

import numpy as np

from . import config as C


def u_crra(w: np.ndarray, gamma: float) -> np.ndarray:
    w = np.asarray(w, dtype=float)
    if np.any(w <= 0):
        raise RuntimeError("CRRA wealth non-positive")
    if abs(gamma - 1.0) < 1e-12:
        return np.log(w)
    return np.power(w, 1.0 - gamma) / (1.0 - gamma)


def u_cara(w_cents: np.ndarray, alpha_per_dollar: float) -> np.ndarray:
    w_d = np.asarray(w_cents, dtype=float) / 100.0
    return -np.exp(-alpha_per_dollar * w_d)


def expected_utility(p_yes: np.ndarray, h: np.ndarray, kind: str, param: float) -> np.ndarray:
    """Return (n, H) EU values. h is (H,) or (1,H)."""
    p = np.asarray(p_yes, dtype=float)[:, None]
    hh = np.asarray(h, dtype=float).reshape(1, -1)
    w_yes = C.W0_CENTS + hh * C.X_YES
    w_no = C.W0_CENTS + hh * C.X_NO
    if kind == "crra":
        u_y = u_crra(w_yes, param)
        u_n = u_crra(w_no, param)
    elif kind == "cara":
        u_y = u_cara(w_yes, param)
        u_n = u_cara(w_no, param)
    else:
        raise ValueError(kind)
    eu = p * u_y + (1.0 - p) * u_n
    if not np.all(np.isfinite(eu)):
        raise RuntimeError("N1 utility produced non-finite values")
    return eu


def realized_utility(y_yes: np.ndarray, h: np.ndarray, kind: str, param: float) -> np.ndarray:
    y = np.asarray(y_yes, dtype=float)
    hh = np.asarray(h, dtype=float)
    x = np.where(y >= 0.5, C.X_YES, C.X_NO)
    w = C.W0_CENTS + hh * x
    if kind == "crra":
        return u_crra(w, param)
    return u_cara(w, param)


N1_GRID = (
    [("crra", g) for g in C.CRRA_GAMMA] + [("cara", a) for a in C.CARA_ALPHA_PER_DOLLAR]
)

# Common VALIDATION yardstick. Do not compare raw U_γ across γ or mix cents with utility.
REF_KIND = "crra"
REF_PARAM = 2.0


def reference_score(y_yes: np.ndarray, h: np.ndarray) -> float:
    return float(np.mean(realized_utility(y_yes, h, REF_KIND, REF_PARAM)))
