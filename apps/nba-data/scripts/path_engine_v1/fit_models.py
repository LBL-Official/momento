#!/usr/bin/env python3
"""Path Engine V1 models: 0 → 1 → 2A → 2B → (optional) 3.

TRAIN = BUILD (fit + chronological CV + optional Platt).
VALIDATION = CHOOSE.
OOS = VERIFY once. No retune. No Platt on VALIDATION.
"""

from __future__ import annotations

import math
import sys

import numpy as np

from common import (
    BRIER_IMPROVE,
    BREAKEVEN_Q,
    BUCKET_GAP_PP,
    ECE_TOLERANCE,
    EV_UNCONDITIONAL,
    FILTER_THRESHOLDS,
    L2_LAMBDA,
    MIN_ACCEPTANCE,
    MIN_BUCKET_N,
    MODEL2A,
    MODEL2B,
    OUT,
    Q_UNCONDITIONAL,
    UNIVARIATE_TRAIN,
    ev_from_q,
    read_parquet_rows,
    sigmoid,
    utc_now,
    wilson,
    write_json,
    write_parquet,
)

TARGET = "target_close_40"
BUCKETS = [(0.0, 0.10), (0.10, 0.20), (0.20, 0.30), (0.30, 0.40), (0.40, 1.01)]
BUCKET_LABELS = ["0-10%", "10-20%", "20-30%", "30-40%", "40%+"]


def _xy(rows, cols):
    y = np.array([r[TARGET] for r in rows], dtype=float)
    X = np.zeros((len(rows), len(cols)), dtype=float)
    mask = np.ones_like(X, dtype=bool)
    for j, c in enumerate(cols):
        for i, r in enumerate(rows):
            v = r.get(c)
            if v is None or (isinstance(v, float) and math.isnan(v)):
                mask[i, j] = False
            else:
                X[i, j] = float(v)
    return X, y, mask


def impute_and_scale(X, mask, medians=None, means=None, stds=None, fit=False):
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


def fit_l2_logistic(X, y, l2=L2_LAMBDA, max_iter=80):
    """Newton-Raphson. Intercept is column 0 and is not L2-penalized."""
    n, p = X.shape
    w = np.zeros(p)
    pen = np.ones(p) * l2
    pen[0] = 0.0
    for _ in range(max_iter):
        p_hat = sigmoid(X @ w)
        wdiag = np.clip(p_hat * (1.0 - p_hat), 1e-6, None)
        H = X.T @ (wdiag[:, None] * X)
        H = H + np.diag(pen)
        g = X.T @ (p_hat - y) + pen * w
        try:
            delta = np.linalg.solve(H, g)
        except np.linalg.LinAlgError:
            delta = np.linalg.lstsq(H, g, rcond=None)[0]
        w = w - delta
        if np.max(np.abs(delta)) < 1e-8:
            break
    return w


def predict_logistic(X, w):
    return sigmoid(X @ w)


def logit(p):
    p = np.clip(p, 1e-6, 1 - 1e-6)
    return np.log(p / (1.0 - p))


def fit_platt(p_raw, y):
    """Platt: sigmoid(a * logit(p) + b) on TRAIN CV predictions only."""
    z = logit(np.asarray(p_raw, dtype=float))
    X = add_intercept(z.reshape(-1, 1))
    w = fit_l2_logistic(X, np.asarray(y, dtype=float), l2=0.1)
    return float(w[1]), float(w[0])


def apply_platt(p_raw, a, b):
    return sigmoid(a * logit(np.asarray(p_raw, dtype=float)) + b)


def brier(y, p):
    y = np.asarray(y, dtype=float)
    p = np.asarray(p, dtype=float)
    return float(np.mean((p - y) ** 2))


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
        if i == n_bins - 1:
            m = (p >= lo) & (p <= hi)
        else:
            m = (p >= lo) & (p < hi)
        k = int(m.sum())
        if k == 0:
            continue
        total += (k / n) * abs(float(y[m].mean()) - float(p[m].mean()))
    return float(total)


def risk_buckets(y, p):
    y = np.asarray(y, dtype=float)
    p = np.asarray(p, dtype=float)
    out = []
    for (lo, hi), lab in zip(BUCKETS, BUCKET_LABELS):
        if hi >= 1.0:
            m = (p >= lo) & (p <= 1.0)
        else:
            m = (p >= lo) & (p < hi)
        n = int(m.sum())
        k = int(y[m].sum()) if n else 0
        q, qlo, qhi = wilson(k, n) if n else (None, None, None)
        out.append(
            {
                "bucket": lab,
                "lo": lo,
                "hi": hi,
                "n": n,
                "y40": k,
                "actual_q": q,
                "wilson_lo": qlo,
                "wilson_hi": qhi,
                "mean_pred": None if n == 0 else float(p[m].mean()),
                "ev_actual": ev_from_q(q) if q is not None else None,
                "usable": n >= MIN_BUCKET_N,
            }
        )
    return out


def merge_small_buckets(buckets):
    """Merge adjacent buckets with n < MIN_BUCKET_N for display/tests."""
    merged = []
    buf = None
    for b in buckets:
        if buf is None:
            buf = dict(b)
            continue
        if buf["n"] < MIN_BUCKET_N or b["n"] < MIN_BUCKET_N:
            n = buf["n"] + b["n"]
            k = buf["y40"] + b["y40"]
            q, qlo, qhi = wilson(k, n) if n else (None, None, None)
            pred_sum = 0.0
            pred_n = 0
            for src in (buf, b):
                if src["mean_pred"] is not None and src["n"]:
                    pred_sum += src["mean_pred"] * src["n"]
                    pred_n += src["n"]
            buf = {
                "bucket": f"{buf['bucket']}+{b['bucket']}",
                "lo": buf["lo"],
                "hi": b["hi"],
                "n": n,
                "y40": k,
                "actual_q": q,
                "wilson_lo": qlo,
                "wilson_hi": qhi,
                "mean_pred": None if pred_n == 0 else pred_sum / pred_n,
                "ev_actual": ev_from_q(q) if q is not None else None,
                "usable": n >= MIN_BUCKET_N,
            }
        else:
            merged.append(buf)
            buf = dict(b)
    if buf is not None:
        merged.append(buf)
    return merged


def adjacent_separation(buckets) -> bool:
    usable = [b for b in buckets if b.get("usable") and b.get("actual_q") is not None]
    if len(usable) < 2:
        return False
    for a, b in zip(usable, usable[1:]):
        gap = abs(b["actual_q"] - a["actual_q"]) * 100.0
        ci_sep = a["wilson_hi"] < b["wilson_lo"] or b["wilson_hi"] < a["wilson_lo"]
        if ci_sep or gap >= BUCKET_GAP_PP:
            return True
    return False


def metrics_pack(y, p, label):
    y = np.asarray(y, dtype=float)
    p = np.asarray(p, dtype=float)
    buckets = risk_buckets(y, p)
    merged = merge_small_buckets(buckets)
    return {
        "label": label,
        "n": int(len(y)),
        "y40": int(y.sum()),
        "actual_q": float(y.mean()) if len(y) else None,
        "mean_pred": float(p.mean()) if len(p) else None,
        "brier": brier(y, p),
        "log_loss": log_loss(y, p),
        "roc_auc": roc_auc(y, p),
        "pr_auc": average_precision(y, p),
        "ece": ece(y, p),
        "ev_unconditional_on_split": ev_from_q(float(y.mean())) if len(y) else None,
        "buckets": buckets,
        "buckets_merged": merged,
        "adjacent_separation": adjacent_separation(merged),
    }


def filter_eval(y, p, threshold):
    y = np.asarray(y, dtype=float)
    p = np.asarray(p, dtype=float)
    accepted = p < threshold
    n = len(y)
    n_acc = int(accepted.sum())
    k_acc = int(y[accepted].sum()) if n_acc else 0
    q = (k_acc / n_acc) if n_acc else None
    return {
        "threshold": threshold,
        "n": n,
        "n_accepted": n_acc,
        "acceptance_rate": n_acc / n if n else 0.0,
        "y40_accepted": k_acc,
        "actual_q_accepted": q,
        "ev_accepted": ev_from_q(q) if q is not None else None,
        "ev_unconditional": ev_from_q(float(y.mean())) if n else None,
        "beats_unconditional_ev": (
            q is not None and ev_from_q(q) > ev_from_q(float(y.mean()))
        ),
        "meets_acceptance_floor": (n_acc / n if n else 0.0) >= MIN_ACCEPTANCE,
    }


def chronological_folds(rows, n_blocks=4):
    ordered = sorted(rows, key=lambda r: (r["game_date"] or "", r["entry_decision_time"] or 0))
    n = len(ordered)
    edges = [int(round(i * n / n_blocks)) for i in range(n_blocks + 1)]
    blocks = [ordered[edges[i] : edges[i + 1]] for i in range(n_blocks)]
    folds = []
    train_acc = []
    for i in range(n_blocks - 1):
        train_acc.extend(blocks[i])
        val = blocks[i + 1]
        if train_acc and val:
            folds.append((list(train_acc), val, f"cv{i+1}"))
    return folds


def fit_predict_logistic(train_rows, pred_rows, cols, platt=None, fit_platt=False):
    Xtr, ytr, mtr = _xy(train_rows, cols)
    Xs, med, mu, sd = impute_and_scale(Xtr, mtr, fit=True)
    Xtr_i = add_intercept(Xs)
    w = fit_l2_logistic(Xtr_i, ytr)
    p_tr = predict_logistic(Xtr_i, w)
    a = b = None
    if fit_platt and platt is None:
        # Caller supplies CV predictions for Platt; not fitted on full train labels here.
        pass
    if platt is not None:
        a, b = platt
        p_tr = apply_platt(p_tr, a, b)
    Xp, yp, mp = _xy(pred_rows, cols)
    Xps, _, _, _ = impute_and_scale(Xp, mp, medians=med, means=mu, stds=sd, fit=False)
    p = predict_logistic(add_intercept(Xps), w)
    if platt is not None:
        p = apply_platt(p, a, b)
    bundle = {
        "w": w,
        "medians": med,
        "means": mu,
        "stds": sd,
        "cols": cols,
        "platt": platt,
        "p_train": p_tr,
        "y_train": ytr,
    }
    return p, yp, bundle


def cv_platt_logistic(train_rows, cols):
    folds = chronological_folds(train_rows)
    cv_p = []
    cv_y = []
    for tr, va, _name in folds:
        p, y, _ = fit_predict_logistic(tr, va, cols, platt=None)
        cv_p.extend(p.tolist())
        cv_y.extend(y.tolist())
    cv_p = np.array(cv_p)
    cv_y = np.array(cv_y)
    raw_brier = brier(cv_y, cv_p)
    a, b = fit_platt(cv_p, cv_y)
    cal_p = apply_platt(cv_p, a, b)
    cal_brier = brier(cv_y, cal_p)
    use = cal_brier < raw_brier
    return {
        "cv_n": int(len(cv_y)),
        "cv_brier_raw": raw_brier,
        "cv_brier_platt": cal_brier,
        "platt_used": bool(use),
        "platt_a": a if use else None,
        "platt_b": b if use else None,
        "cv_ece_raw": ece(cv_y, cv_p),
        "cv_ece_platt": ece(cv_y, cal_p),
    }


def univariate_deciles(train_rows, col):
    vals = []
    ys = []
    for r in train_rows:
        v = r.get(col)
        if v is None:
            continue
        vals.append(float(v))
        ys.append(int(r[TARGET]))
    n = len(vals)
    if n < 40:
        return {"feature": col, "n": n, "status": "INSUFFICIENT_N"}
    qs = np.quantile(vals, np.linspace(0, 1, 11))
    # unique edges
    edges = [qs[0]]
    for q in qs[1:]:
        if q > edges[-1]:
            edges.append(float(q))
    if len(edges) < 3:
        return {"feature": col, "n": n, "status": "NO_VARIATION"}
    buckets = []
    arr = np.array(vals)
    yarr = np.array(ys)
    for i in range(len(edges) - 1):
        lo, hi = edges[i], edges[i + 1]
        if i == len(edges) - 2:
            m = (arr >= lo) & (arr <= hi)
        else:
            m = (arr >= lo) & (arr < hi)
        k = int(yarr[m].sum())
        nn = int(m.sum())
        q, qlo, qhi = wilson(k, nn) if nn else (None, None, None)
        buckets.append(
            {
                "decile": i + 1,
                "lo": float(lo),
                "hi": float(hi),
                "n": nn,
                "y40": k,
                "actual_q": q,
                "wilson_lo": qlo,
                "wilson_hi": qhi,
                "ev": ev_from_q(q) if q is not None else None,
            }
        )
    qs_only = [b["actual_q"] for b in buckets if b["actual_q"] is not None]
    diffs = [b - a for a, b in zip(qs_only, qs_only[1:])]
    up = sum(1 for d in diffs if d > 0.01)
    down = sum(1 for d in diffs if d < -0.01)
    if up >= max(3, len(diffs) - 2) and down <= 1:
        trend = "MONOTONE_UP"
    elif down >= max(3, len(diffs) - 2) and up <= 1:
        trend = "MONOTONE_DOWN"
    elif abs(up - down) <= 1:
        trend = "FLAT"
    else:
        trend = "NONMONOTONE"
    return {
        "feature": col,
        "n": n,
        "n_missing": len(train_rows) - n,
        "status": "TESTED",
        "trend": trend,
        "actual_q_low_bucket": buckets[0]["actual_q"] if buckets else None,
        "actual_q_high_bucket": buckets[-1]["actual_q"] if buckets else None,
        "buckets": buckets,
    }


# --- tiny GBM (depth-2 trees, squared-error residuals) ---


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


def fit_gbm(X, y, n_trees=40, shrinkage=0.08, min_leaf=25):
    y = np.asarray(y, dtype=float)
    F = np.full(len(y), logit(np.array([y.mean()]))[0])
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


def choose_filter(val_y, val_p):
    rows = [filter_eval(val_y, val_p, t) for t in FILTER_THRESHOLDS]
    eligible = [
        r
        for r in rows
        if r["meets_acceptance_floor"]
        and r["ev_accepted"] is not None
        and r["beats_unconditional_ev"]
    ]
    chosen = None
    if eligible:
        chosen = max(eligible, key=lambda r: (r["ev_accepted"], r["acceptance_rate"]))
    return {
        "candidates": rows,
        "chosen_threshold": None if chosen is None else chosen["threshold"],
        "rule": "VAL only; pre-registered thresholds; require EV_accepted > EV_split and acceptance >= 50%",
    }


def promotion_gate(challenger, incumbent, challenger_p, challenger_y, name):
    brier_ok = challenger["brier"] <= BRIER_IMPROVE * incumbent["brier"]
    ece_ok = challenger["ece"] <= incumbent["ece"] + ECE_TOLERANCE
    sep_ok = bool(challenger["adjacent_separation"])
    filt = choose_filter(challenger_y, challenger_p)
    acc_ok = True
    if filt["chosen_threshold"] is not None:
        ch = next(c for c in filt["candidates"] if c["threshold"] == filt["chosen_threshold"])
        acc_ok = ch["meets_acceptance_floor"]
    else:
        # No implied filter: acceptance floor is vacuously about the full set (100%).
        acc_ok = True
    passed = brier_ok and ece_ok and sep_ok and acc_ok
    return {
        "name": name,
        "passed": passed,
        "brier_ok": brier_ok,
        "ece_ok": ece_ok,
        "separation_ok": sep_ok,
        "acceptance_ok": acc_ok,
        "brier_challenger": challenger["brier"],
        "brier_incumbent": incumbent["brier"],
        "ece_challenger": challenger["ece"],
        "ece_incumbent": incumbent["ece"],
        "filter": filt,
    }


def coef_table(bundle, cols):
    w = bundle["w"]
    rows = [{"feature": "intercept", "coef_standardized": float(w[0])}]
    for i, c in enumerate(cols):
        rows.append(
            {
                "feature": c,
                "coef_standardized": float(w[i + 1]),
                "train_mean": float(bundle["means"][i]),
                "train_std": float(bundle["stds"][i]),
            }
        )
    return rows


def main() -> int:
    feat_path = OUT / "features_entry.parquet"
    if not feat_path.exists():
        print("missing features_entry.parquet", file=sys.stderr)
        return 1
    rows = [r for r in read_parquet_rows(feat_path) if r.get("feature_status") == "OK"]
    train = [r for r in rows if r["dataset_split"] == "TRAIN"]
    val = [r for r in rows if r["dataset_split"] == "VALIDATION"]
    oos = [r for r in rows if r["dataset_split"] == "OOS"]
    if not train or not val or not oos:
        print("split empty", file=sys.stderr)
        return 1

    # Model 1 univariate (TRAIN only). Exploratory included for TRAIN inspection.
    uni = [univariate_deciles(train, c) for c in UNIVARIATE_TRAIN]
    write_json(OUT / "univariate_train.json", {"written_utc": utc_now(), "rows": uni})

    # Model 0
    def const_p(n):
        return np.full(n, Q_UNCONDITIONAL)

    m0_train = metrics_pack([r[TARGET] for r in train], const_p(len(train)), "model0_train")
    m0_val = metrics_pack([r[TARGET] for r in val], const_p(len(val)), "model0_val")
    m0_oos = metrics_pack([r[TARGET] for r in oos], const_p(len(oos)), "model0_oos")
    write_json(
        OUT / "models" / "baseline" / "metrics.json",
        {
            "q_hat": Q_UNCONDITIONAL,
            "ev_gross": EV_UNCONDITIONAL,
            "train": m0_train,
            "validation": m0_val,
            "oos": m0_oos,
        },
    )

    # Model 2A
    cv_a = cv_platt_logistic(train, MODEL2A)
    platt_a = None
    if cv_a["platt_used"]:
        platt_a = (cv_a["platt_a"], cv_a["platt_b"])
    p2a_tr, ytr, bun_a = fit_predict_logistic(train, train, MODEL2A, platt=platt_a)
    p2a_va, yva, _ = fit_predict_logistic(train, val, MODEL2A, platt=platt_a)
    p2a_oo, yoo, _ = fit_predict_logistic(train, oos, MODEL2A, platt=platt_a)
    m2a_tr = metrics_pack(ytr, p2a_tr, "2a_train")
    m2a_va = metrics_pack(yva, p2a_va, "2a_val")
    m2a_oo = metrics_pack(yoo, p2a_oo, "2a_oos")
    write_json(
        OUT / "models" / "logistic_2a" / "metrics.json",
        {
            "n_predictors": len(MODEL2A),
            "predictors": MODEL2A,
            "cv": cv_a,
            "coefficients": coef_table(bun_a, MODEL2A),
            "train": m2a_tr,
            "validation": m2a_va,
            "oos": m2a_oo,
            "filters_val": [filter_eval(yva, p2a_va, t) for t in FILTER_THRESHOLDS],
            "filters_oos": [filter_eval(yoo, p2a_oo, t) for t in FILTER_THRESHOLDS],
        },
    )

    # Model 2B
    cv_b = cv_platt_logistic(train, MODEL2B)
    platt_b = (cv_b["platt_a"], cv_b["platt_b"]) if cv_b["platt_used"] else None
    p2b_tr, _, bun_b = fit_predict_logistic(train, train, MODEL2B, platt=platt_b)
    p2b_va, _, _ = fit_predict_logistic(train, val, MODEL2B, platt=platt_b)
    p2b_oo, _, _ = fit_predict_logistic(train, oos, MODEL2B, platt=platt_b)
    m2b_tr = metrics_pack(ytr, p2b_tr, "2b_train")
    m2b_va = metrics_pack(yva, p2b_va, "2b_val")
    m2b_oo = metrics_pack(yoo, p2b_oo, "2b_oos")
    gate_2b = promotion_gate(m2b_va, m2a_va, p2b_va, yva, "2B_vs_2A")
    write_json(
        OUT / "models" / "logistic_2b" / "metrics.json",
        {
            "n_predictors": len(MODEL2B),
            "predictors": MODEL2B,
            "cv": cv_b,
            "coefficients": coef_table(bun_b, MODEL2B),
            "train": m2b_tr,
            "validation": m2b_va,
            "oos": m2b_oo,
            "promotion_gate": gate_2b,
            "role": "exploratory" if not gate_2b["passed"] else "promoted_confirmatory",
            "filters_val": [filter_eval(yva, p2b_va, t) for t in FILTER_THRESHOLDS],
            "filters_oos": [filter_eval(yoo, p2b_oo, t) for t in FILTER_THRESHOLDS],
        },
    )

    chosen_logistic = "2B" if gate_2b["passed"] else "2A"
    p_va = p2b_va if chosen_logistic == "2B" else p2a_va
    p_oo = p2b_oo if chosen_logistic == "2B" else p2a_oo
    p_tr = p2b_tr if chosen_logistic == "2B" else p2a_tr
    cols_ch = MODEL2B if chosen_logistic == "2B" else MODEL2A
    m_va = m2b_va if chosen_logistic == "2B" else m2a_va
    m_oo = m2b_oo if chosen_logistic == "2B" else m2a_oo

    # Model 3: train on TRAIN, evaluate VAL gate, OOS only as diagnostic unless passed.
    Xtr, ytr_g, mtr = _xy(train, cols_ch)
    Xs, med, mu, sd = impute_and_scale(Xtr, mtr, fit=True)
    gbm = fit_gbm(Xs, ytr_g)
    p3_tr = predict_gbm(Xs, gbm)
    Xva, _, mva = _xy(val, cols_ch)
    Xvas, _, _, _ = impute_and_scale(Xva, mva, medians=med, means=mu, stds=sd, fit=False)
    p3_va = predict_gbm(Xvas, gbm)
    Xoo, _, moo = _xy(oos, cols_ch)
    Xoos, _, _, _ = impute_and_scale(Xoo, moo, medians=med, means=mu, stds=sd, fit=False)
    p3_oo = predict_gbm(Xoos, gbm)
    m3_va = metrics_pack(yva, p3_va, "3_val")
    m3_tr = metrics_pack(ytr_g, p3_tr, "3_train")
    m3_oo = metrics_pack(yoo, p3_oo, "3_oos_diagnostic")
    gate_3 = promotion_gate(m3_va, m_va, p3_va, yva, "3_vs_logistic")
    write_json(
        OUT / "models" / "tree" / "metrics.json",
        {
            "type": "depth2_gbm_numpy",
            "n_trees": len(gbm["trees"]),
            "shrinkage": gbm["shrinkage"],
            "features": cols_ch,
            "train": m3_tr,
            "validation": m3_va,
            "oos": m3_oo,
            "val_gate": gate_3,
            "selected": bool(gate_3["passed"]),
            "oos_role": "selected" if gate_3["passed"] else "DIAGNOSTIC_NOT_SELECTED",
        },
    )

    selected = "3" if gate_3["passed"] else chosen_logistic
    p_sel_va = p3_va if selected == "3" else p_va
    p_sel_oo = p3_oo if selected == "3" else p_oo
    p_sel_tr = p3_tr if selected == "3" else p_tr
    filt = choose_filter(yva, p_sel_va)
    filt_oos = None
    if filt["chosen_threshold"] is not None:
        filt_oos = filter_eval(yoo, p_sel_oo, filt["chosen_threshold"])

    # Weekly opportunity proxy from full sample dates.
    dates = sorted({r["game_date"] for r in rows if r.get("game_date")})
    if len(dates) >= 2:
        d0 = dates[0]
        d1 = dates[-1]
        from datetime import datetime

        delta = (
            datetime.strptime(d1, "%Y-%m-%d") - datetime.strptime(d0, "%Y-%m-%d")
        ).days / 7.0
        weekly_first80 = len(rows) / max(delta, 1e-6)
    else:
        weekly_first80 = None

    pred_rows = []
    pmap = {
        "TRAIN": (train, p2a_tr, p2b_tr, p3_tr, p_sel_tr),
        "VALIDATION": (val, p2a_va, p2b_va, p3_va, p_sel_va),
        "OOS": (oos, p2a_oo, p2b_oo, p3_oo, p_sel_oo),
    }
    for split, (subset, a, b, c, s) in pmap.items():
        for i, r in enumerate(subset):
            pred_rows.append(
                {
                    "observation_id": r["observation_id"],
                    "dataset_split": split,
                    "game_date": r["game_date"],
                    "ticker": r["ticker"],
                    "target_close_40": r[TARGET],
                    "q_model0": Q_UNCONDITIONAL,
                    "q_2a": float(a[i]),
                    "q_2b": float(b[i]),
                    "q_3": float(c[i]),
                    "q_selected": float(s[i]),
                    "selected_model": selected,
                }
            )
    write_parquet(OUT / "predictions.parquet", pred_rows)

    write_json(
        OUT / "model_selection.json",
        {
            "written_utc": utc_now(),
            "chosen_logistic": chosen_logistic,
            "2b_promoted": gate_2b["passed"],
            "model3_selected": gate_3["passed"],
            "selected_model": selected,
            "filter": filt,
            "filter_oos": filt_oos,
            "weekly_first80_historical": weekly_first80,
            "expected_weekly_if_filter": None
            if weekly_first80 is None or filt["chosen_threshold"] is None
            else weekly_first80
            * next(
                c["acceptance_rate"]
                for c in filt["candidates"]
                if c["threshold"] == filt["chosen_threshold"]
            ),
            "gates": {"2b": gate_2b, "3": gate_3},
            "notes": "VALIDATION used only to choose. OOS is one frozen pass.",
        },
    )
    print(
        f"models done  2A_val_brier={m2a_va['brier']:.4f}  "
        f"2B_val_brier={m2b_va['brier']:.4f}  "
        f"2B_promoted={gate_2b['passed']}  "
        f"M3_selected={gate_3['passed']}  "
        f"filter={filt['chosen_threshold']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
