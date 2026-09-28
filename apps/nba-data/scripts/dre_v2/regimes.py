"""Interpretable regime buckets. SAFE/DANGER/ACUTE are not assumed."""

from __future__ import annotations

import numpy as np

from . import config as C

try:
    from sklearn.cluster import KMeans

    HAS_SK = True
except ImportError:
    HAS_SK = False


CLUSTER_FEATURES = [
    "current_price",
    "deterioration_absolute",
    "game_seconds_remaining",
    "score_differential_from_A1",
    "possessions_since_entry",
]


def price_bucket(px) -> str:
    if px is None:
        return "UNKNOWN"
    if px >= 70:
        return "P70_80"
    if px >= 60:
        return "P60_70"
    if px >= 50:
        return "P50_60"
    if px >= 40:
        return "P40_50"
    return "P_LT_40"


def det_bucket(d) -> str:
    if d is None:
        return "UNKNOWN"
    if d < 5:
        return "D0_5"
    if d < 15:
        return "D5_15"
    if d < 25:
        return "D15_25"
    return "D25P"


def period_bucket(p, ot) -> str:
    if ot:
        return "OT"
    if p is None:
        return "UNKNOWN"
    if p <= 2:
        return "Q1Q2"
    if p == 3:
        return "Q3"
    if p >= 4:
        return "Q4"
    return "UNKNOWN"


def score_bucket(diff) -> str:
    if diff is None:
        return "UNKNOWN"
    if diff > 5:
        return "A1_LEADING"
    if diff < -5:
        return "A1_TRAILING"
    return "CLOSE"


def assign_buckets(rows) -> None:
    for r in rows:
        r["regime_price"] = price_bucket(r.get("current_price"))
        r["regime_det"] = det_bucket(r.get("deterioration_absolute"))
        r["regime_period"] = period_bucket(r.get("period"), r.get("is_overtime"))
        r["regime_score"] = score_bucket(r.get("score_differential_from_A1"))
        r["regime_key"] = "|".join(
            [r["regime_price"], r["regime_det"], r["regime_period"], r["regime_score"]]
        )


def regime_table(rows) -> list[dict]:
    groups = {}
    for r in rows:
        key = (r.get("dataset_split"), r.get("regime_price"), r.get("regime_period"), r.get("regime_score"))
        g = groups.setdefault(key, [])
        g.append(r)
    out = []
    for (split, rp, rper, rs), xs in sorted(groups.items(), key=lambda kv: (kv[0][0] or "", kv[0][1] or "", kv[0][2] or "")):
        if len(xs) < 30:
            continue
        out.append(
            {
                "split": split,
                "price_bucket": rp,
                "period_bucket": rper,
                "score_bucket": rs,
                "n": len(xs),
                "emp_settle": _mean(xs, "y_settle_yes"),
                "emp_rec10_k5": _mean(xs, "y_rec_ge_10_k5"),
                "emp_det10_end": _mean(xs, "y_det_ge_10_end"),
                "mean_price": _mean(xs, "current_price"),
                "mean_h_M3_A": _mean(xs, "target_delta_M3_A"),
                "mean_h_M3_D": _mean(xs, "target_delta_M3_D"),
            }
        )
    return out


def fit_clusters(rows, k: int = 5) -> dict:
    assign_buckets(rows)
    if not HAS_SK:
        return {"status": "SKIP", "reason": "sklearn missing"}
    train = [r for r in rows if r["dataset_split"] == "TRAIN"]
    X_tr, idx_tr = _matrix(train)
    if X_tr is None or len(X_tr) < 200:
        return {"status": "INSUFFICIENT"}
    km = KMeans(n_clusters=k, random_state=C.RANDOM_SEED, n_init=10)
    km.fit(X_tr)
    for split_rows in (
        rows,
    ):
        X, idx = _matrix(split_rows)
        if X is None:
            continue
        labels = km.predict(X)
        for i, lab in zip(idx, labels):
            split_rows[i]["regime_cluster"] = int(lab)
    centers = []
    for i, c in enumerate(km.cluster_centers_):
        centers.append({CLUSTER_FEATURES[j]: float(c[j]) for j in range(len(CLUSTER_FEATURES))})
        centers[-1]["cluster"] = i
    return {
        "status": "FIT_TRAIN_ONLY",
        "k": k,
        "features": CLUSTER_FEATURES,
        "n_train": int(len(X_tr)),
        "centers": centers,
        "random_seed": C.RANDOM_SEED,
        "note": "Clusters fit on TRAIN only. VAL/OOS are transformed, not refit.",
    }


def _matrix(rows):
    xs, idx = [], []
    for i, r in enumerate(rows):
        vec = []
        ok = True
        for c in CLUSTER_FEATURES:
            v = r.get(c)
            if v is None:
                ok = False
                break
            vec.append(float(int(v) if isinstance(v, bool) else v))
        if ok:
            xs.append(vec)
            idx.append(i)
    if not xs:
        return None, []
    return np.asarray(xs, dtype=float), idx


def _mean(rows, key):
    vs = [r.get(key) for r in rows if r.get(key) is not None]
    if not vs:
        return None
    return float(np.mean(np.asarray(vs, dtype=float)))
