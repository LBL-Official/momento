"""Distribution, drawdown, bootstrap, Pareto. Trades are not assumed IID."""

from __future__ import annotations

import math

import numpy as np
import pandas as pd


def _arr(x) -> np.ndarray:
    return np.asarray(x, dtype=float)


def max_drawdown(pnls: np.ndarray) -> float:
    if pnls.size == 0:
        return 0.0
    cum = np.cumsum(pnls)
    peak = np.maximum.accumulate(cum)
    return float((cum - peak).min())


def downside_dev(pnls: np.ndarray) -> float:
    if pnls.size == 0:
        return float("nan")
    d = np.minimum(pnls, 0.0)
    return float(np.sqrt(np.mean(d * d)))


def expected_shortfall(pnls: np.ndarray, q: float = 0.05) -> float:
    if pnls.size == 0:
        return float("nan")
    k = max(1, int(math.ceil(q * len(pnls))))
    worst = np.sort(pnls)[:k]
    return float(worst.mean())


def consecutive_losses(pnls: np.ndarray) -> int:
    best = cur = 0
    for p in pnls:
        if p < 0:
            cur += 1
            best = max(best, cur)
        else:
            cur = 0
    return best


def summarize(pnls, dates=None, baseline=None) -> dict:
    a = _arr(pnls)
    n = int(a.size)
    if n == 0:
        return {"n": 0}
    ordered = a
    if dates is not None:
        idx = np.argsort(np.asarray(dates, dtype=str))
        ordered = a[idx]
    p01 = float(np.quantile(a, 0.01))
    p05 = float(np.quantile(a, 0.05))
    mean = float(a.mean())
    out = {
        "n": n,
        "mean": round(mean, 6),
        "median": round(float(np.median(a)), 6),
        "std": round(float(a.std(ddof=1)) if n > 1 else 0.0, 6),
        "variance": round(float(a.var(ddof=1)) if n > 1 else 0.0, 6),
        "skew": round(float(((a - mean) ** 3).mean() / (a.std() ** 3 + 1e-12)), 6),
        "kurtosis": round(float(((a - mean) ** 4).mean() / (a.std() ** 4 + 1e-12)), 6),
        "downside_dev": round(downside_dev(a), 6),
        "worst": round(float(a.min()), 6),
        "best": round(float(a.max()), 6),
        "p01": round(p01, 6),
        "p05": round(p05, 6),
        "es05": round(expected_shortfall(a, 0.05), 6),
        "max_dd": round(max_drawdown(ordered), 6),
        "consec_losses": consecutive_losses(ordered),
        "win_rate": round(float((a > 0).mean()), 6),
        "catastrophic_rate": round(float((a <= -60).mean()), 6),
        "sum": round(float(a.sum()), 6),
    }
    if baseline is not None:
        b = _arr(baseline)
        out["inc_vs_original"] = round(float(a.mean() - b.mean()), 6)
        out["tail_p05_vs_original"] = round(float(p05 - np.quantile(b, 0.05)), 6)
        out["dd_vs_original"] = round(max_drawdown(ordered) - max_drawdown(b), 6)
    return out


def bootstrap_mean(pnls, n_boot: int = 400, seed: int = 7) -> dict:
    a = _arr(pnls)
    if a.size == 0:
        return {}
    rng = np.random.default_rng(seed)
    means = np.empty(n_boot)
    for i in range(n_boot):
        means[i] = a[rng.integers(0, a.size, a.size)].mean()
    lo, hi = np.quantile(means, [0.025, 0.975])
    return {
        "boot_mean": round(float(means.mean()), 6),
        "ci95_lo": round(float(lo), 6),
        "ci95_hi": round(float(hi), 6),
        "n_boot": n_boot,
        "method": "IID_TRADE_RESAMPLE",
        "note": "SAMPLING UNCERTAINTY only. Not regime uncertainty.",
    }


def block_bootstrap_mean(pnls, dates, n_boot: int = 400, seed: int = 11) -> dict:
    df = pd.DataFrame({"p": _arr(pnls), "d": np.asarray(dates, dtype=str)})
    blocks = [g["p"].to_numpy() for _, g in df.groupby("d")]
    if not blocks:
        return {}
    rng = np.random.default_rng(seed)
    means = np.empty(n_boot)
    n_b = len(blocks)
    for i in range(n_boot):
        pick = [blocks[j] for j in rng.integers(0, n_b, n_b)]
        means[i] = np.concatenate(pick).mean()
    lo, hi = np.quantile(means, [0.025, 0.975])
    return {
        "boot_mean": round(float(means.mean()), 6),
        "ci95_lo": round(float(lo), 6),
        "ci95_hi": round(float(hi), 6),
        "n_boot": n_boot,
        "n_blocks": n_b,
        "method": "BLOCK_BY_GAME_DATE",
        "note": "Preserves same-day correlation. Still not regime uncertainty.",
    }


def pareto_front(rows: list[dict], ev_key="mean", tail_key="p05") -> list[dict]:
    """Non-dominated: higher EV and higher p05 (less left-tail)."""
    out = []
    for i, a in enumerate(rows):
        dominated = False
        for j, b in enumerate(rows):
            if i == j:
                continue
            ge_ev = b[ev_key] >= a[ev_key]
            ge_tail = b[tail_key] >= a[tail_key]
            strict = b[ev_key] > a[ev_key] or b[tail_key] > a[tail_key]
            if ge_ev and ge_tail and strict:
                dominated = True
                break
        row = dict(a)
        row["pareto"] = not dominated
        out.append(row)
    return out


def plateau(hs: list[int], evs: list[float], tol: float = 0.15) -> dict:
    if not evs:
        return {"width": 0, "h_lo": None, "h_hi": None, "best_h": None}
    best = max(evs)
    keep = [h for h, e in zip(hs, evs) if abs(e - best) <= tol]
    return {
        "width": len(keep),
        "h_lo": min(keep) if keep else None,
        "h_hi": max(keep) if keep else None,
        "best_h": hs[int(np.argmax(evs))],
        "best_ev": round(best, 6),
        "tol": tol,
    }
