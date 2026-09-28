"""Family N4 — asymmetric power loss on path downside vs upside.

Obj(h) = h × E[X] − a × h^p × E[DD^p] + b × h × E[UU]
p > 1 makes downside convex in exposure, which can create interior h*.
"""

from __future__ import annotations

import numpy as np

from . import config as C


def n4_value(p_yes, e_ddp, e_uu, a, b, p, h) -> np.ndarray:
    ev = p_yes * C.X_YES + (1.0 - p_yes) * C.X_NO
    hh = np.asarray(h, dtype=float).reshape(1, -1)
    val = ev[:, None] * hh - a * np.power(hh, p) * e_ddp[:, None] + b * hh * e_uu[:, None]
    if not np.all(np.isfinite(val)):
        raise RuntimeError("N4 non-finite")
    return val


def n4_realized(y_yes, h, dd, uu, a, b, p):
    hh = np.asarray(h, dtype=float)
    x = np.where(np.asarray(y_yes) >= 0.5, C.X_YES, C.X_NO)
    ddp = np.power(np.nan_to_num(dd, nan=0.0), p)
    return hh * x - a * np.power(hh, p) * ddp + b * hh * np.nan_to_num(uu, nan=0.0)


def expected_ddp(p_bins: np.ndarray, p: float) -> np.ndarray:
    vec = np.array([C.BIN_DD[b] ** p for b in C.PATH_BINS], dtype=float)
    return p_bins @ vec
