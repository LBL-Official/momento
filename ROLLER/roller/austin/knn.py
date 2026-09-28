"""Euclidean KNN in PCA space. Query is never a training neighbor."""

from __future__ import annotations

from typing import Any

import numpy as np

from roller.austin.config import DEFAULT, AustinConfig
from roller.austin.mathutil import pairwise_euclid
from roller.austin.outcomes import HOLD_EV_DEFINITION

CI_METHOD = "weighted bootstrap"
CI_DRAWS = 1000
CI_LEVEL = 0.95
CI_SEED = 80


def _weights(dist: np.ndarray, eps: float) -> np.ndarray:
    w = 1.0 / (dist + float(eps))
    s = float(w.sum())
    if s <= 0:
        return np.ones_like(dist) / max(1, dist.size)
    return w / s


def _weighted_median(values: np.ndarray, weights: np.ndarray) -> float:
    order = np.argsort(values)
    v = values[order]
    w = weights[order]
    cdf = np.cumsum(w)
    idx = int(np.searchsorted(cdf, 0.5, side="left"))
    idx = min(max(idx, 0), int(v.size) - 1)
    return float(v[idx])


def _neighbor_pnl(meta: dict[str, Any]) -> float | None:
    for key in ("pnl_hold_after_t", "final_pnl_hold_cents", "final_pnl_taker_8040_cents"):
        val = meta.get(key)
        if val is None or val == "":
            continue
        try:
            return float(val)
        except (TypeError, ValueError):
            continue
    return None


def weighted_bootstrap_ci(
    values: np.ndarray,
    weights: np.ndarray,
    *,
    level: float = CI_LEVEL,
    draws: int = CI_DRAWS,
    seed: int = CI_SEED,
) -> dict[str, Any]:
    n = int(values.size)
    if n == 0:
        return {
            "ci_level": level,
            "ci_lower_cents": None,
            "ci_upper_cents": None,
            "method": CI_METHOD,
            "draws": draws,
            "seed": seed,
        }
    w = np.asarray(weights, dtype=float)
    s = float(w.sum())
    p = np.ones(n) / n if s <= 0 else w / s
    rng = np.random.default_rng(int(seed))
    means = np.empty(int(draws), dtype=float)
    for i in range(int(draws)):
        idx = rng.choice(n, size=n, replace=True, p=p)
        means[i] = float(values[idx].mean())
    alpha = (1.0 - float(level)) / 2.0
    return {
        "ci_level": level,
        "ci_lower_cents": float(np.quantile(means, alpha)),
        "ci_upper_cents": float(np.quantile(means, 1.0 - alpha)),
        "method": CI_METHOD,
        "draws": int(draws),
        "seed": int(seed),
        "label": f"{int(level * 100)}% CI — {CI_METHOD}",
    }


def match_query(
    query_vec: np.ndarray,
    train_vecs: np.ndarray,
    train_meta: list[dict[str, Any]],
    *,
    k: int | None = None,
    cfg: AustinConfig = DEFAULT,
    exclude_trade_id: str | None = None,
    exclude_snapshot_id: str | None = None,
) -> dict[str, Any]:
    kk = int(k or cfg.k_default)
    empty = {
        "k": kk,
        "effective_neighbors": 0,
        "status": "INSUFFICIENT_SAMPLE",
        "neighbors": [],
        "distance_metric": "euclidean_pca",
        "weighting": "1 / (distance + epsilon)",
        "ev_definition": HOLD_EV_DEFINITION,
    }
    if train_vecs.size == 0 or not train_meta:
        return empty
    q = np.asarray(query_vec, dtype=float).reshape(1, -1)
    dist = pairwise_euclid(q, np.asarray(train_vecs, dtype=float))[0]
    order = np.argsort(dist)
    picked: list[int] = []
    for idx in order:
        meta = train_meta[int(idx)]
        if exclude_trade_id and str(meta.get("trade_id") or "") == str(exclude_trade_id):
            continue
        if exclude_snapshot_id and str(meta.get("snapshot_id") or "") == str(exclude_snapshot_id):
            continue
        picked.append(int(idx))
        if len(picked) >= kk:
            break
    if not picked:
        return empty
    d = dist[np.array(picked)]
    w = _weights(d, cfg.distance_epsilon)
    neighbors = []
    pnls = []
    survive = []
    t40s = []
    t40_after = []
    pnl_8040 = []
    w_8040 = []
    for rank, idx in enumerate(picked, start=1):
        meta = dict(train_meta[idx])
        meta["rank"] = rank
        meta["distance"] = float(d[rank - 1])
        meta["weight"] = float(w[rank - 1])
        neighbors.append(meta)
        hold = _neighbor_pnl(meta)
        pnls.append(0.0 if hold is None else hold)
        survive.append(0.0 if meta.get("csv_t40") else 1.0)
        t40s.append(1.0 if meta.get("csv_t40") else 0.0)
        t40_after.append(1.0 if meta.get("hit_40_after") else 0.0)
        if meta.get("pnl_8040_after_t") is not None and meta.get("pnl_8040_after_t_status") != "NOT_APPLICABLE":
            try:
                pnl_8040.append(float(meta["pnl_8040_after_t"]))
                w_8040.append(float(w[rank - 1]))
            except (TypeError, ValueError):
                pass
    pnl = np.array(pnls, dtype=float)
    support = "LOW HISTORICAL SUPPORT" if float(np.median(d)) > 3.0 or len(picked) < min(10, kk) else "OBSERVED"
    ess = float(1.0 / max(float(np.sum(w * w)), 1e-12))
    ci = weighted_bootstrap_ci(pnl, w, seed=cfg.seed)
    quant = {
        "PNL_p10": float(np.quantile(pnl, 0.10)),
        "PNL_p25": float(np.quantile(pnl, 0.25)),
        "PNL_p50": float(np.quantile(pnl, 0.50)),
        "PNL_p75": float(np.quantile(pnl, 0.75)),
        "PNL_p90": float(np.quantile(pnl, 0.90)),
    }
    ev_8040 = None
    if pnl_8040:
        ww = np.array(w_8040, dtype=float)
        s8040 = float(ww.sum())
        ev_8040 = float(np.mean(pnl_8040)) if s8040 <= 0 else float(np.sum((ww / s8040) * np.array(pnl_8040)))
    return {
        "k": kk,
        "effective_neighbors": len(picked),
        "effective_sample_size": ess,
        "status": "OBSERVED",
        "support": support,
        "distance_metric": "euclidean_pca",
        "weighting": "1 / (distance + epsilon)",
        "ev_definition": HOLD_EV_DEFINITION,
        "ev_formula": "20S − 80(1−S)",
        "mean_distance": float(np.mean(d)),
        "median_distance": float(np.median(d)),
        "nearest_distance": float(np.min(d)),
        "weighted_mean_PNL": float(np.sum(w * pnl)),
        "weighted_median_PNL": _weighted_median(pnl, w),
        "weighted_mean_EV": float(np.sum(w * pnl)),
        "weighted_median_EV": _weighted_median(pnl, w),
        "weighted_survival_rate": float(np.sum(w * np.array(survive))),
        "weighted_T40_rate": float(np.sum(w * np.array(t40_after))),
        "weighted_8040_after_t": ev_8040,
        "PNL_std": float(np.std(pnl, ddof=0)),
        **quant,
        "PNL_min": float(np.min(pnl)),
        "PNL_max": float(np.max(pnl)),
        "ci": ci,
        "neighbors": neighbors,
    }
