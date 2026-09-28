#!/usr/bin/env python3
"""Models 0–5. TRAIN=BUILD, VAL=CHOOSE, OOS=VERIFY. Seed 42. No sklearn."""

from __future__ import annotations

import math
import sys

import numpy as np

from common import (
    BRIER_IMPROVE,
    ECE_TOLERANCE,
    EV_UNCONDITIONAL,
    L2_LAMBDA,
    MIN_RISK_BUCKET_N,
    OUT,
    Q_UNCONDITIONAL,
    SEED,
    ev_from_q,
    sigmoid,
    split_rows,
    utc_now,
    wilson,
    write_json,
)
from eval_lib import apply_tree_leaf, depth2_tree, load_analysis_rows

TARGET = "Y_40_CLOSE"
MODEL3 = [
    "score_differential",
    "game_seconds_elapsed",
    "lead_size",
    "number_of_lead_changes",
    "current_lead_duration_s",
    "score_differential_stdev",
    "comeback_magnitude",
    "lead_decay",
    "vol_5m_cents",
    "momentum_5m_cents",
    "minutes_from_50_to_80",
    "distance_above_80_cents",
    "spread_cents",
    "points_per_game_minute",
]
TREE_COLS = [
    "quarter",
    "score_differential",
    "number_of_lead_changes",
    "current_lead_duration_s",
    "score_differential_stdev",
    "comeback_magnitude",
    "lead_decay",
    "vol_5m_cents",
    "momentum_5m_cents",
    "game_seconds_remaining",
]
RISK_BUCKETS = [
    (0.0, 0.10, "0-10%"),
    (0.10, 0.15, "10-15%"),
    (0.15, 0.20, "15-20%"),
    (0.20, 0.25, "20-25%"),
    (0.25, 0.30, "25-30%"),
    (0.30, 1.0 / 3.0, "30-33.33%"),
    (1.0 / 3.0, 0.40, "33.33-40%"),
    (0.40, 1.01, "40%+"),
]


def _xy(rows, cols):
    y = np.array([r[TARGET] for r in rows], dtype=float)
    X = np.zeros((len(rows), len(cols)))
    mask = np.ones_like(X, dtype=bool)
    for j, c in enumerate(cols):
        for i, r in enumerate(rows):
            v = r.get(c)
            if v is None or (isinstance(v, float) and math.isnan(v)):
                mask[i, j] = False
            else:
                try:
                    X[i, j] = float(v)
                except (TypeError, ValueError):
                    mask[i, j] = False
    return X, y, mask


def impute_scale(X, mask, medians=None, means=None, stds=None, fit=False):
    n, p = X.shape
    out = X.copy()
    if fit:
        medians = np.zeros(p)
        for j in range(p):
            vals = out[mask[:, j], j]
            medians[j] = float(np.median(vals)) if len(vals) else 0.0
    for j in range(p):
        out[~mask[:, j], j] = medians[j]
    if fit:
        means = out.mean(axis=0)
        stds = out.std(axis=0, ddof=0)
        stds = np.where(stds < 1e-12, 1.0, stds)
    scaled = (out - means) / stds
    return scaled, medians, means, stds


def add_intercept(X):
    return np.column_stack([np.ones(len(X)), X])


def fit_l2(X, y, l2=L2_LAMBDA, max_iter=80):
    n, p = X.shape
    w = np.zeros(p)
    pen = np.ones(p) * l2
    pen[0] = 0.0
    for _ in range(max_iter):
        p_hat = sigmoid(X @ w)
        wdiag = np.clip(p_hat * (1.0 - p_hat), 1e-6, None)
        H = X.T @ (wdiag[:, None] * X) + np.diag(pen)
        g = X.T @ (p_hat - y) + pen * w
        try:
            delta = np.linalg.solve(H, g)
        except np.linalg.LinAlgError:
            delta = np.linalg.lstsq(H, g, rcond=None)[0]
        w = w - delta
        if np.max(np.abs(delta)) < 1e-8:
            break
    return w


def fit_elastic(X, y, l1=0.02, l2=0.5, lr=0.08, iters=600):
    n, p = X.shape
    w = np.zeros(p)
    rng = np.random.default_rng(SEED)
    w[1:] = rng.normal(0, 0.01, size=p - 1)
    for _ in range(iters):
        p_hat = sigmoid(X @ w)
        g = X.T @ (p_hat - y) / n
        g[1:] += l2 * w[1:]
        w = w - lr * g
        w[1:] = np.sign(w[1:]) * np.maximum(np.abs(w[1:]) - lr * l1, 0.0)
    return w


def brier(y, p):
    return float(np.mean((np.asarray(p) - np.asarray(y)) ** 2))


def log_loss(y, p):
    p = np.clip(np.asarray(p, dtype=float), 1e-12, 1 - 1e-12)
    y = np.asarray(y, dtype=float)
    return float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p)))


def roc_auc(y, p):
    y = np.asarray(y).astype(int)
    p = np.asarray(p, dtype=float)
    n1 = int(y.sum())
    n0 = len(y) - n1
    if n0 == 0 or n1 == 0:
        return None
    order = np.argsort(p, kind="mergesort")
    ranks = np.empty(len(p), dtype=float)
    ranks[order] = np.arange(1, len(p) + 1, dtype=float)
    sp = p[order]
    i = 0
    while i < len(p):
        j = i
        while j + 1 < len(p) and sp[j + 1] == sp[i]:
            j += 1
        if j > i:
            avg = 0.5 * (ranks[order[i]] + ranks[order[j]])
            ranks[order[i : j + 1]] = avg
        i = j + 1
    u = ranks[y == 1].sum() - n1 * (n1 + 1) / 2.0
    return float(u / (n1 * n0))


def average_precision(y, p):
    y = np.asarray(y).astype(int)
    p = np.asarray(p, dtype=float)
    n1 = int(y.sum())
    if n1 == 0:
        return None
    order = np.argsort(-p, kind="mergesort")
    yt = y[order]
    tp = np.cumsum(yt)
    fp = np.cumsum(1 - yt)
    prec = tp / np.maximum(tp + fp, 1)
    rec = tp / n1
    rec = np.concatenate([[0.0], rec])
    prec = np.concatenate([[1.0], prec])
    return float(np.sum((rec[1:] - rec[:-1]) * prec[1:]))


def ece(y, p, n_bins=10):
    y = np.asarray(y, dtype=float)
    p = np.asarray(p, dtype=float)
    bins = np.linspace(0.0, 1.0, n_bins + 1)
    total = 0.0
    n = len(y)
    for i in range(n_bins):
        lo, hi = bins[i], bins[i + 1]
        m = (p >= lo) & (p <= hi) if i == n_bins - 1 else (p >= lo) & (p < hi)
        k = int(m.sum())
        if k == 0:
            continue
        total += (k / n) * abs(float(y[m].mean()) - float(p[m].mean()))
    return float(total)


def risk_buckets(y, p):
    y = np.asarray(y, dtype=float)
    p = np.asarray(p, dtype=float)
    out = []
    for lo, hi, lab in RISK_BUCKETS:
        m = (p >= lo) & (p <= 1.0) if hi >= 1.0 else (p >= lo) & (p < hi)
        n = int(m.sum())
        k = int(y[m].sum()) if n else 0
        q, qlo, qhi = wilson(k, n) if n else (None, None, None)
        out.append(
            {
                "bucket": lab,
                "n": n,
                "y40": k,
                "actual_q": q,
                "wilson_lo": qlo,
                "wilson_hi": qhi,
                "mean_pred": None if n == 0 else float(p[m].mean()),
                "ev": ev_from_q(q) if q is not None else None,
                "delta_ev": None if q is None else ev_from_q(q) - EV_UNCONDITIONAL,
                "usable": n >= MIN_RISK_BUCKET_N,
            }
        )
    return out


def metrics(y, p):
    y = np.asarray(y, dtype=float)
    p = np.asarray(p, dtype=float)
    buckets = risk_buckets(y, p)
    usable = [b for b in buckets if b["usable"] and b["actual_q"] is not None]
    sep = False
    if len(usable) >= 2:
        for a, b in zip(usable, usable[1:]):
            if a["wilson_hi"] < b["wilson_lo"] or b["wilson_hi"] < a["wilson_lo"]:
                sep = True
            if abs((b["actual_q"] - a["actual_q"]) * 100) >= 8:
                sep = True
    return {
        "n": int(len(y)),
        "actual_q": float(y.mean()) if len(y) else None,
        "brier": brier(y, p),
        "log_loss": log_loss(y, p),
        "roc_auc": roc_auc(y, p),
        "pr_auc": average_precision(y, p),
        "ece": ece(y, p),
        "adjacent_separation": sep,
        "buckets": buckets,
    }


def _best_stump(X, residual, min_leaf):
    n, p = X.shape
    best = None
    parent_sse = float(np.sum((residual - residual.mean()) ** 2))
    for j in range(p):
        col = X[:, j]
        qs = np.unique(np.quantile(col, np.linspace(0.1, 0.9, 9)))
        for t in qs:
            left = col <= t
            nl, nr = int(left.sum()), int((~left).sum())
            if nl < min_leaf or nr < min_leaf:
                continue
            ml = residual[left].mean()
            mr = residual[~left].mean()
            sse = float(np.sum((residual[left] - ml) ** 2) + np.sum((residual[~left] - mr) ** 2))
            gain = parent_sse - sse
            if best is None or gain > best[0]:
                best = (gain, j, float(t), float(ml), float(mr))
    return best


def logit(p):
    p = np.clip(p, 1e-6, 1 - 1e-6)
    return np.log(p / (1.0 - p))


def fit_gbm(X, y, n_trees=30, shrinkage=0.08, min_leaf=40):
    y = np.asarray(y, dtype=float)
    F = np.full(len(y), logit(np.array([max(y.mean(), 1e-6)]))[0])
    trees = []
    intercept = float(F[0])
    for _ in range(n_trees):
        p = sigmoid(F)
        resid = y - p
        split = _best_stump(X, resid, min_leaf)
        if split is None or split[0] <= 0:
            break
        _gain, j, t, ml, mr = split
        trees.append({"j": j, "t": t, "left": ml, "right": mr})
        col = X[:, j]
        F = F + shrinkage * np.where(col <= t, ml, mr)
    return {"intercept": intercept, "trees": trees, "shrinkage": shrinkage}


def predict_gbm(X, model):
    F = np.full(len(X), model["intercept"])
    nu = model["shrinkage"]
    for tr in model["trees"]:
        F = F + nu * np.where(X[:, tr["j"]] <= tr["t"], tr["left"], tr["right"])
    return sigmoid(F)


def main() -> int:
    np.random.seed(SEED)
    rows = load_analysis_rows()
    train = split_rows(rows, "TRAIN", primary_only=True)
    val = split_rows(rows, "VALIDATION", primary_only=True)
    oos = split_rows(rows, "OOS", primary_only=True)
    if not train or not val or not oos:
        print("empty split", file=sys.stderr)
        return 1

    ytr = np.array([r[TARGET] for r in train], dtype=float)
    yva = np.array([r[TARGET] for r in val], dtype=float)
    yoo = np.array([r[TARGET] for r in oos], dtype=float)
    p0 = np.full(1, Q_UNCONDITIONAL)

    def pack0(y):
        return metrics(y, np.full(len(y), Q_UNCONDITIONAL))

    m0 = {"train": pack0(ytr), "validation": pack0(yva), "oos": pack0(yoo)}

    Xtr, _, mtr = _xy(train, MODEL3)
    Xva, _, mva = _xy(val, MODEL3)
    Xoo, _, moo = _xy(oos, MODEL3)
    Xs_tr, med, mean, std = impute_scale(Xtr, mtr, fit=True)
    Xs_va, _, _, _ = impute_scale(Xva, mva, med, mean, std, fit=False)
    Xs_oo, _, _, _ = impute_scale(Xoo, moo, med, mean, std, fit=False)
    Ztr, Zva, Zoo = add_intercept(Xs_tr), add_intercept(Xs_va), add_intercept(Xs_oo)

    w_l2 = fit_l2(Ztr, ytr)
    w_en = fit_elastic(Ztr, ytr)
    p_l2 = {
        "train": sigmoid(Ztr @ w_l2),
        "validation": sigmoid(Zva @ w_l2),
        "oos": sigmoid(Zoo @ w_l2),
    }
    p_en = {
        "train": sigmoid(Ztr @ w_en),
        "validation": sigmoid(Zva @ w_en),
        "oos": sigmoid(Zoo @ w_en),
    }
    gbm = fit_gbm(Xs_tr, ytr)
    p_gbm = {
        "train": predict_gbm(Xs_tr, gbm),
        "validation": predict_gbm(Xs_va, gbm),
        "oos": predict_gbm(Xs_oo, gbm),
    }

    tree = depth2_tree(train, TREE_COLS)
    write_json(OUT / "models" / "tree_discovery.json", tree)

    def mm(p):
        return {
            "train": metrics(ytr, p["train"]),
            "validation": metrics(yva, p["validation"]),
            "oos": metrics(yoo, p["oos"]),
        }

    m_l2 = mm(p_l2)
    m_en = mm(p_en)
    m_gbm = mm(p_gbm)

    def gate(ch, inc):
        return {
            "brier_ok": ch["brier"] <= BRIER_IMPROVE * inc["brier"],
            "ece_ok": ch["ece"] <= inc["ece"] + ECE_TOLERANCE,
            "sep_ok": bool(ch["adjacent_separation"]),
            "passed": False,
        }

    g_l2 = gate(m_l2["validation"], m0["validation"])
    g_l2["passed"] = g_l2["brier_ok"] and g_l2["ece_ok"] and g_l2["sep_ok"]
    g_en = gate(m_en["validation"], m0["validation"])
    g_en["passed"] = g_en["brier_ok"] and g_en["ece_ok"] and g_en["sep_ok"]
    g_gbm = gate(m_gbm["validation"], m_l2["validation"] if g_l2["passed"] else m0["validation"])
    g_gbm["passed"] = g_gbm["brier_ok"] and g_gbm["ece_ok"] and g_gbm["sep_ok"]

    selected = "model0_unconditional"
    if g_l2["passed"]:
        selected = "model3_l2"
    if g_en["passed"] and m_en["validation"]["brier"] < (
        m_l2["validation"]["brier"] if selected == "model3_l2" else m0["validation"]["brier"]
    ):
        selected = "model3_elastic_net"
    if g_gbm["passed"]:
        selected = "model4_gbm"

    write_json(OUT / "models" / "baseline" / "metrics.json", m0)
    write_json(
        OUT / "models" / "logistic_l2" / "metrics.json",
        {**m_l2, "weights": w_l2.tolist(), "features": MODEL3, "gate": g_l2},
    )
    write_json(
        OUT / "models" / "elastic_net" / "metrics.json",
        {**m_en, "weights": w_en.tolist(), "features": MODEL3, "gate": g_en},
    )
    write_json(
        OUT / "models" / "gbm" / "metrics.json",
        {**m_gbm, "model": gbm, "features": MODEL3, "gate": g_gbm},
    )
    write_json(
        OUT / "models" / "model_selection.json",
        {
            "written_utc": utc_now(),
            "seed": SEED,
            "selected": selected,
            "gates": {"l2": g_l2, "elastic_net": g_en, "gbm": g_gbm},
            "note": "Selected model is not a live filter. Bucket engine remains primary interpretability layer.",
        },
    )
    print(f"models selected={selected} val_brier0={m0['validation']['brier']:.4f} l2={m_l2['validation']['brier']:.4f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
