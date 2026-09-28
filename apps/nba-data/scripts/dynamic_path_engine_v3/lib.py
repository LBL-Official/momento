"""Shared V3 modeling helpers. No sklearn."""

from __future__ import annotations

import math
from collections import defaultdict

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq

from common import L2_LAMBDA, SEED, ece, log_loss, roc_auc, sigmoid

TARGET = "H_40_5M"
MODEL2_COLS = [
    "minutes_since_entry",
    "distance_to_40_cents",
    "momentum_5m_cents",
    "vol_5m_cents",
    "mae_since_entry_cents",
    "consecutive_down",
    "path_efficiency",
    "velocity_toward_40_cents",
    "net_score_since_entry",
    "game_missing",
]
MINUTE_BINS = [(0, 2), (2, 5), (5, 10), (10, 15), (15, 20), (20, 30), (30, 45), (45, 90), (90, 1000)]
DIST_BINS = [(0, 5), (5, 10), (10, 15), (15, 20), (20, 25), (25, 30), (30, 40), (40, 200)]


def join_tables(left: pa.Table, right: pa.Table, keys=("trade_id", "state_timestamp")) -> pa.Table:
    drop = [c for c in right.column_names if c in set(left.column_names) and c not in keys]
    if drop:
        right = right.drop_columns(drop)
    lk = list(zip(left.column(keys[0]).to_pylist(), left.column(keys[1]).to_pylist()))
    rk = list(zip(right.column(keys[0]).to_pylist(), right.column(keys[1]).to_pylist()))
    rmap = {k: i for i, k in enumerate(rk)}
    take = np.zeros(len(lk), dtype=np.int64)
    hit = np.zeros(len(lk), dtype=bool)
    for i, k in enumerate(lk):
        j = rmap.get(k)
        if j is not None:
            take[i] = j
            hit[i] = True
    taken = right.take(pa.array(take))
    keep = [c for c in taken.column_names if c not in keys]
    arrays = list(left.columns)
    names = list(left.column_names)
    for c in keep:
        col = taken.column(c)
        if not hit.all():
            vals = col.to_pylist()
            merged = [vals[i] if hit[i] else None for i in range(len(vals))]
            arrays.append(pa.array(merged))
        else:
            arrays.append(col)
        names.append(c)
    return pa.Table.from_arrays(arrays, names=names)


def num_col(table: pa.Table, name: str, default=np.nan):
    if name not in table.column_names:
        return np.full(table.num_rows, default, dtype=float)
    vals = table.column(name).to_pylist()
    out = np.empty(len(vals), dtype=float)
    for i, v in enumerate(vals):
        if v is None or (isinstance(v, float) and math.isnan(v)):
            out[i] = default
        else:
            try:
                out[i] = float(v)
            except (TypeError, ValueError):
                out[i] = default
    return out


def str_col(table: pa.Table, name: str):
    if name not in table.column_names:
        return [None] * table.num_rows
    return table.column(name).to_pylist()


def load_panel():
    from common import OUT

    t = pq.read_table(OUT / "features_panel.parquet")
    n = t.num_rows
    game_status = str_col(t, "game_feature_status")
    game_missing = np.array([0.0 if s == "AVAILABLE" else 1.0 for s in game_status])
    X = np.column_stack(
        [
            num_col(t, "minutes_since_entry"),
            num_col(t, "distance_to_40_cents"),
            num_col(t, "momentum_5m_cents"),
            num_col(t, "vol_5m_cents"),
            num_col(t, "mae_since_entry_cents"),
            num_col(t, "consecutive_down"),
            num_col(t, "path_efficiency"),
            num_col(t, "velocity_toward_40_cents"),
            num_col(t, "net_score_since_entry"),
            game_missing,
        ]
    )
    y = num_col(t, TARGET, default=0.0)
    y = np.nan_to_num(y, nan=0.0)
    return {
        "table": t,
        "n": n,
        "X": X,
        "y": y.astype(int),
        "trade_id": str_col(t, "trade_id"),
        "split": str_col(t, "dataset_split"),
        "minutes": num_col(t, "minutes_since_entry"),
        "dist40": num_col(t, "distance_to_40_cents"),
        "bid_e4": num_col(t, "yes_bid_close_e4"),
        "state_ts": num_col(t, "state_timestamp"),
        "entry_ts": num_col(t, "entry_decision_time"),
        "eventual": num_col(t, "EVENTUAL_40", default=0.0),
        "game_date": str_col(t, "game_date"),
        "archetype": str_col(t, "path_archetype_rule"),
        "align": str_col(t, "alignment_confidence"),
        "game_status": game_status,
        "mom5": num_col(t, "momentum_5m_cents"),
        "vol5": num_col(t, "vol_5m_cents"),
        "mae": num_col(t, "mae_since_entry_cents"),
        "net_score": num_col(t, "net_score_since_entry"),
        "is_last": num_col(t, "is_last_alive", default=0.0),
        "panel_index": num_col(t, "panel_index", default=0.0),
        "H10": num_col(t, "H_40_10M", default=0.0),
        "H15": num_col(t, "H_40_15M", default=0.0),
    }


def split_mask(split_col, name):
    return np.array([s == name for s in split_col], dtype=bool)


def impute_scale(X, fit=False, medians=None, means=None, stds=None):
    n, p = X.shape
    out = X.copy()
    if fit:
        medians = np.zeros(p)
        for j in range(p):
            vals = out[np.isfinite(out[:, j]), j]
            medians[j] = float(np.median(vals)) if len(vals) else 0.0
    for j in range(p):
        miss = ~np.isfinite(out[:, j])
        out[miss, j] = medians[j]
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
    y = np.asarray(y, dtype=float)
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


def brier(y, p):
    return float(np.mean((np.asarray(p) - np.asarray(y)) ** 2))


def clustered_metric(trade_ids, y, p, fn):
    buckets = defaultdict(list)
    y = np.asarray(y, dtype=float)
    p = np.asarray(p, dtype=float)
    for t, yi, pi in zip(trade_ids, y, p):
        buckets[t].append(fn(yi, pi))
    if not buckets:
        return None
    return float(np.mean([np.mean(v) for v in buckets.values()]))


def clustered_brier(trade_ids, y, p):
    return clustered_metric(trade_ids, y, p, lambda yi, pi: (yi - pi) ** 2)


def metrics_block(y, p, trade_ids=None):
    y = np.asarray(y, dtype=float)
    p = np.asarray(p, dtype=float)
    out = {
        "n_rows": int(len(y)),
        "event_rate": float(y.mean()) if len(y) else None,
        "brier": brier(y, p) if len(y) else None,
        "log_loss": log_loss(y, p) if len(y) else None,
        "auc": roc_auc(y, p) if len(y) else None,
        "ece": ece(y, p) if len(y) else None,
        "mean_p": float(p.mean()) if len(p) else None,
    }
    if trade_ids is not None:
        out["n_trades"] = len(set(trade_ids))
        out["clustered_brier"] = clustered_brier(trade_ids, y, p)
    return out


def bin_lookup(edges, rates, x, default):
    if x is None or not np.isfinite(x):
        return default
    for (lo, hi), r in zip(edges, rates):
        if lo <= x < hi:
            return r
    return default


def train_bin_rates(x, y, edges):
    rates = []
    counts = []
    for lo, hi in edges:
        m = np.isfinite(x) & (x >= lo) & (x < hi)
        k = int(y[m].sum()) if m.any() else 0
        n = int(m.sum())
        rates.append(float(k / n) if n else None)
        counts.append(n)
    return rates, counts


def quintile_edges(x, q=5):
    v = x[np.isfinite(x)]
    if len(v) < q:
        return None
    qs = np.quantile(v, np.linspace(0, 1, q + 1))
    qs[0] = -np.inf
    qs[-1] = np.inf
    # de-dup
    edges = []
    for i in range(len(qs) - 1):
        if qs[i] < qs[i + 1]:
            edges.append((float(qs[i]), float(qs[i + 1])))
    return edges


def spearman(a, b):
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    m = np.isfinite(a) & np.isfinite(b)
    a, b = a[m], b[m]
    if len(a) < 3:
        return None
    ra = np.argsort(np.argsort(a))
    rb = np.argsort(np.argsort(b))
    return float(np.corrcoef(ra, rb)[0, 1])


def kmeans(X, k, seed=SEED, iters=40):
    rng = np.random.default_rng(seed)
    n = len(X)
    k = min(k, n)
    cents = X[rng.choice(n, size=k, replace=False)].copy()
    labels = np.zeros(n, dtype=int)
    for _ in range(iters):
        d = ((X[:, None, :] - cents[None, :, :]) ** 2).sum(axis=2)
        labels = d.argmin(axis=1)
        for j in range(k):
            m = labels == j
            if m.any():
                cents[j] = X[m].mean(axis=0)
    return labels, cents


def assign_kmeans(X, cents):
    d = ((X[:, None, :] - cents[None, :, :]) ** 2).sum(axis=2)
    return d.argmin(axis=1)


def depth2_boost(X, y, n_trees=20, lr=0.08, min_leaf=40, seed=SEED):
    """Shallow logistic boosting. Small n_trees. TRAIN rows should be 1/trade."""
    rng = np.random.default_rng(seed)
    n, p = X.shape
    F = np.full(n, float(np.log((y.mean() + 1e-6) / (1 - y.mean() + 1e-6))))
    trees = []
    feats = list(range(p))
    for _ in range(n_trees):
        p_hat = sigmoid(F)
        resid = y - p_hat
        best = None
        for j in feats:
            xs = X[:, j]
            cand = np.unique(np.quantile(xs[np.isfinite(xs)], [0.2, 0.4, 0.6, 0.8]))
            for t in cand:
                left = np.isfinite(xs) & (xs <= t)
                right = np.isfinite(xs) & (xs > t)
                if left.sum() < min_leaf or right.sum() < min_leaf:
                    continue
                vl = float(resid[left].mean())
                vr = float(resid[right].mean())
                sse = ((resid[left] - vl) ** 2).sum() + ((resid[right] - vr) ** 2).sum()
                if best is None or sse < best[0]:
                    best = (sse, j, float(t), vl, vr)
        if best is None:
            break
        _, j, t, vl, vr = best
        pred = np.where(X[:, j] <= t, vl, vr)
        F = F + lr * pred
        trees.append({"j": int(j), "t": t, "vl": vl, "vr": vr, "lr": lr})
    return {"base": float(F[0] - sum(tr["lr"] * (tr["vl"] if True else 0) for tr in [])), "trees": trees, "init": float(np.log((y.mean() + 1e-6) / (1 - y.mean() + 1e-6)))}


def predict_boost(model, X):
    F = np.full(len(X), model["init"])
    for tr in model["trees"]:
        F = F + tr["lr"] * np.where(X[:, tr["j"]] <= tr["t"], tr["vl"], tr["vr"])
    return sigmoid(F)
