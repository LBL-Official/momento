"""Expectancy + path decomposition. Aggregates must reconcile to the ledger."""

from __future__ import annotations

import math

import numpy as np


def _finite(a) -> np.ndarray:
    return np.asarray(a, dtype=float)


def describe(pnls, n_boot: int = 400, seed: int = 7) -> dict:
    a = _finite(pnls)
    n = int(a.size)
    if n == 0:
        return {"n": 0, "status": "INSUFFICIENT_SAMPLE"}
    if n < 40:
        sample = "INSUFFICIENT_SAMPLE"
    else:
        sample = "OK"
    wins = a[a > 0]
    losses = a[a < 0]
    mean = float(a.mean())
    rng = np.random.default_rng(seed)
    boots = np.empty(n_boot)
    for i in range(n_boot):
        boots[i] = a[rng.integers(0, n, n)].mean()
    lo, hi = np.quantile(boots, [0.025, 0.975])
    return {
        "n": n,
        "sample_status": sample,
        "win_count": int((a > 0).sum()),
        "loss_count": int((a < 0).sum()),
        "win_rate": round(float((a > 0).mean()), 6),
        "mean_win": round(float(wins.mean()), 6) if wins.size else None,
        "mean_loss": round(float(losses.mean()), 6) if losses.size else None,
        "gross_expectancy": round(mean, 6),
        "net_expectancy": round(mean, 6),
        "median_pnl": round(float(np.median(a)), 6),
        "p05": round(float(np.quantile(a, 0.05)), 6),
        "p25": round(float(np.quantile(a, 0.25)), 6),
        "p50": round(float(np.quantile(a, 0.50)), 6),
        "p75": round(float(np.quantile(a, 0.75)), 6),
        "p95": round(float(np.quantile(a, 0.95)), 6),
        "std": round(float(a.std(ddof=1)) if n > 1 else 0.0, 6),
        "downside_dev": round(float(np.sqrt(np.mean(np.minimum(a, 0.0) ** 2))), 6),
        "maximum_loss": round(float(a.min()), 6),
        "maximum_gain": round(float(a.max()), 6),
        "sum": round(float(a.sum()), 6),
        "bootstrap": {
            "n_boot": n_boot,
            "ci95_lo": round(float(lo), 6),
            "ci95_hi": round(float(hi), 6),
            "method": "IID_TRADE_RESAMPLE",
            "note": "SAMPLING UNCERTAINTY. Not regime uncertainty.",
        },
        "se": round(float(a.std(ddof=1) / math.sqrt(n)), 6) if n > 1 else None,
    }


def decompose(pnls, labels) -> dict:
    a = _finite(pnls)
    labs = np.asarray(labels)
    n = len(a)
    rows = []
    recon = 0.0
    for lab in sorted(set(labs.tolist())):
        m = labs == lab
        k = int(m.sum())
        freq = k / n if n else 0.0
        mu = float(a[m].mean()) if k else 0.0
        contrib = freq * mu
        recon += contrib
        rows.append(
            {
                "path_class": lab,
                "n": k,
                "frequency": round(freq, 6),
                "mean_pnl": round(mu, 6) if k else None,
                "contribution_to_total_ev": round(contrib, 6),
            }
        )
    total = float(a.mean()) if n else 0.0
    return {
        "rows": rows,
        "total_ev": round(total, 6),
        "reconstructed_ev": round(recon, 6),
        "abs_error": round(abs(total - recon), 10),
        "identity_ok": abs(total - recon) < 1e-8,
    }


def concentration(pnls) -> dict:
    a = _finite(pnls)
    if a.size == 0:
        return {}
    total = a.sum()
    order = np.argsort(-a)
    ranked = a[order]
    cum = np.cumsum(ranked)
    def share(frac):
        k = max(1, int(math.ceil(frac * len(a))))
        return float(cum[k - 1] / total) if total != 0 else None
    return {
        "top_10pct_share_of_sum": share(0.10),
        "top_20pct_share_of_sum": share(0.20),
        "bottom_20pct_share_of_sum": float(np.sort(a)[: max(1, int(0.2 * len(a)))].sum() / total)
        if total
        else None,
        "note": "Share of total ¢ sum, not of EV. Do not editorialize.",
    }
