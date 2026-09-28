from __future__ import annotations

import numpy as np
from sklearn.linear_model import LinearRegression
from sklearn.metrics import brier_score_loss, log_loss


def probability_metrics(y: np.ndarray, p: np.ndarray) -> dict:
    y = np.asarray(y).astype(int)
    p = np.clip(np.asarray(p).astype(float), 1e-6, 1 - 1e-6)
    if len(y) == 0:
        return {"n": 0}
    brier = float(brier_score_loss(y, p))
    ll = float(log_loss(y, p, labels=[0, 1]))
    # reliability / ECE
    bins = np.linspace(0, 1, 11)
    ece = 0.0
    reliability = []
    for i in range(10):
        lo, hi = bins[i], bins[i + 1]
        mask = (p >= lo) & (p < hi) if i < 9 else (p >= lo) & (p <= hi)
        n = int(mask.sum())
        if n == 0:
            reliability.append({"lo": lo, "hi": hi, "n": 0, "pred": None, "obs": None})
            continue
        pred = float(p[mask].mean())
        obs = float(y[mask].mean())
        ece += (n / len(y)) * abs(pred - obs)
        reliability.append({"lo": lo, "hi": hi, "n": n, "pred": pred, "obs": obs})
    lr = LinearRegression()
    lr.fit(p.reshape(-1, 1), y)
    return {
        "n": int(len(y)),
        "brier": brier,
        "log_loss": ll,
        "ece": float(ece),
        "calibration_slope": float(lr.coef_[0]),
        "calibration_intercept": float(lr.intercept_),
        "accuracy": float(((p >= 0.5).astype(int) == y).mean()),
        "mean_prediction": float(p.mean()),
        "base_rate": float(y.mean()),
        "reliability": reliability,
    }


def bootstrap_brier_ci(y: np.ndarray, p: np.ndarray, n_boot: int = 200, seed: int = 202425) -> dict:
    rng = np.random.default_rng(seed)
    y = np.asarray(y).astype(int)
    p = np.asarray(p).astype(float)
    if len(y) < 20:
        return {"brier_ci_low": None, "brier_ci_high": None}
    scores = []
    for _ in range(n_boot):
        idx = rng.integers(0, len(y), len(y))
        scores.append(brier_score_loss(y[idx], np.clip(p[idx], 1e-6, 1 - 1e-6)))
    lo, hi = np.quantile(scores, [0.025, 0.975])
    return {"brier_ci_low": float(lo), "brier_ci_high": float(hi)}
