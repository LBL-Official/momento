"""Shared compatibility helpers. Does not classify letters."""

from __future__ import annotations

from . import config as C


def sign(x) -> int | None:
    if x is None:
        return None
    v = float(x)
    if v == 0.0:
        return 0
    return 1 if v > 0 else -1


def spearman(x, y) -> float | None:
    import pandas as pd

    a = pd.Series(x, dtype=float)
    b = pd.Series(y, dtype=float)
    m = a.notna() & b.notna()
    if int(m.sum()) < 3:
        return None
    return float(a[m].rank().corr(b[m].rank()))


def coverage_adequate(n_a: int, n_b: int) -> bool:
    return int(n_a) >= C.MIN_SIDE_TRADES and int(n_b) >= C.MIN_SIDE_TRADES
