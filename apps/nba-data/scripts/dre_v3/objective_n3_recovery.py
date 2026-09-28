"""Family N3 — recovery optionality inside a utility + linear path add-ons.

RecoveryValue = E[max(FutureMax − Current, 0) | X] from the exclusive path bins.
This is a candle-path option-like object, not an executable call.
"""

from __future__ import annotations

import numpy as np

from . import config as C
from .objective_n1_utility import expected_utility, realized_utility


def expected_path_moment(p_bins: np.ndarray, table: dict) -> np.ndarray:
    vec = np.array([table[b] for b in C.PATH_BINS], dtype=float)
    return p_bins @ vec


def n3_value(p_yes, rec, down, lam_r, lam_d, h, gamma: float = 2.0) -> np.ndarray:
    """Path moments enter as theoretical wealth adjustments, then CRRA is applied.

    W_yes = W0 + 20h + λ_R h E[UU]
    W_no  = W0 − 80h − λ_D h E[DD]

    λ_R, λ_D are weights on candle-path optionality, not fillable premia.
    """
    from .objective_n1_utility import u_crra

    p = np.asarray(p_yes, dtype=float)[:, None]
    hh = np.asarray(h, dtype=float).reshape(1, -1)
    w_yes = C.W0_CENTS + hh * C.X_YES + lam_r * rec[:, None] * hh
    w_no = C.W0_CENTS + hh * C.X_NO - lam_d * down[:, None] * hh
    if np.any(w_yes <= 0) or np.any(w_no <= 0):
        raise RuntimeError("N3 wealth non-positive")
    val = p * u_crra(w_yes, gamma) + (1.0 - p) * u_crra(w_no, gamma)
    if not np.all(np.isfinite(val)):
        raise RuntimeError("N3 non-finite")
    return val


def n3_realized(y_yes, h, uu, dd, lam_r, lam_d, gamma: float = 2.0):
    hh = np.asarray(h, dtype=float)
    return (
        realized_utility(y_yes, hh, "crra", gamma)
        + lam_r * hh * np.nan_to_num(uu, nan=0.0)
        - lam_d * hh * np.nan_to_num(dd, nan=0.0)
    )
