"""Calibration diagnostics. No OOS refit."""

from __future__ import annotations

import numpy as np


def ece(y, p, bins: int = 10):
    y = np.asarray(y, dtype=float)
    p = np.asarray(p, dtype=float)
    if len(y) == 0:
        return None
    edges = np.linspace(0.0, 1.0, bins + 1)
    tot = 0.0
    n = 0
    for i in range(bins):
        right = p < edges[i + 1] if i < bins - 1 else p <= edges[i + 1]
        m = (p >= edges[i]) & right
        if not np.any(m):
            continue
        tot += abs(float(y[m].mean()) - float(p[m].mean())) * int(m.sum())
        n += int(m.sum())
    return tot / n if n else None
