#!/usr/bin/env python3
"""Model 3: discrete-time hazard with time basis. Cox not forced.

Also TRAIN K-means path summaries (descriptive; not a live feature).
"""

from __future__ import annotations

import sys

import numpy as np

from common import OUT, SEED, sigmoid, utc_now, write_json
from lib import (
    add_intercept,
    assign_kmeans,
    fit_l2,
    impute_scale,
    kmeans,
    load_panel,
    metrics_block,
    split_mask,
)

TIME_EDGES = [0, 5, 10, 20, 40, 90, 1000]


def time_basis(minutes):
    m = np.asarray(minutes, dtype=float)
    cols = []
    for a, b in zip(TIME_EDGES, TIME_EDGES[1:]):
        cols.append(((m >= a) & (m < b)).astype(float))
    return np.column_stack(cols)


def trade_summaries(d, mask):
    by = {}
    for i in np.where(mask)[0]:
        tid = d["trade_id"][i]
        rec = by.setdefault(
            tid,
            {
                "mae": None,
                "mfe": None,
                "peff": None,
                "vol": None,
                "mom": None,
                "down": None,
                "eventual": int(d["eventual"][i] or 0),
            },
        )
        rec["eventual"] = int(d["eventual"][i] or 0)
        rec["mae"] = d["mae"][i]
        rec["vol"] = d["vol5"][i]
        rec["mom"] = d["mom5"][i]
        # last-row overwrite: later panel_index wins because we iterate in order
    # pull last-row extras from table
    return by


def main() -> int:
    d = load_panel()
    tr = split_mask(d["split"], "TRAIN")
    y = d["y"]
    T = time_basis(d["minutes"])
    X = np.column_stack([T, d["X"]])
    Xs, med, mean, std = impute_scale(X[tr], fit=True)
    w = fit_l2(add_intercept(Xs), y[tr])
    Xall, _, _, _ = impute_scale(X, medians=med, means=mean, stds=std)
    p3 = sigmoid(add_intercept(Xall) @ w)

    (OUT / "models" / "discrete_hazard").mkdir(parents=True, exist_ok=True)
    (OUT / "models" / "survival").mkdir(parents=True, exist_ok=True)
    write_json(
        OUT / "models" / "discrete_hazard" / "params.json",
        {
            "written_utc": utc_now(),
            "kind": "discrete_time_logistic_with_time_dummies",
            "time_edges": TIME_EDGES,
            "weights": w.tolist(),
            "medians": med.tolist(),
            "means": mean.tolist(),
            "stds": std.tolist(),
            "cox_not_used": True,
            "cox_reason": "Time-varying distance_to_40 and post-entry path violate proportional hazards; discrete-time logistic is the workhorse.",
        },
    )
    np.savez(OUT / "models" / "discrete_hazard" / "predictions_cache.npz", p3=p3)
    tr_ids = [d["trade_id"][i] for i in np.where(tr)[0]]
    write_json(
        OUT / "models" / "survival" / "train_metrics.json",
        {"model3": metrics_block(y[tr], p3[tr], tr_ids)},
    )

    # Descriptive K-means on TRAIN last-alive path summaries (completed path — not a live Z_t feature).
    last = {}
    peff_col = (
        d["table"].column("path_efficiency").to_pylist()
        if "path_efficiency" in d["table"].column_names
        else [None] * d["n"]
    )
    mfe_col = (
        d["table"].column("mfe_since_entry_cents").to_pylist()
        if "mfe_since_entry_cents" in d["table"].column_names
        else [None] * d["n"]
    )
    down_col = (
        d["table"].column("consecutive_down").to_pylist()
        if "consecutive_down" in d["table"].column_names
        else [None] * d["n"]
    )
    for i in np.where(tr)[0]:
        last[d["trade_id"][i]] = i
    ids = list(last.keys())
    vecs = []
    y_trade = []
    for tid in ids:
        i = last[tid]
        row = [
            d["mae"][i] if np.isfinite(d["mae"][i]) else 0.0,
            float(mfe_col[i] or 0.0),
            float(peff_col[i] or 0.0),
            d["vol5"][i] if np.isfinite(d["vol5"][i]) else 0.0,
            d["mom5"][i] if np.isfinite(d["mom5"][i]) else 0.0,
            float(down_col[i] or 0.0),
        ]
        vecs.append(row)
        y_trade.append(int(d["eventual"][i] or 0))
    Xk = np.asarray(vecs, dtype=float)
    mu = Xk.mean(axis=0)
    sd = np.where(Xk.std(axis=0) < 1e-9, 1.0, Xk.std(axis=0))
    Z = (Xk - mu) / sd
    labels, cents = kmeans(Z, k=6, seed=SEED)
    clusters = []
    for j in range(6):
        m = labels == j
        n = int(m.sum())
        k = int(np.asarray(y_trade)[m].sum()) if n else 0
        clusters.append({"cluster": j, "n": n, "barrier_k": k, "q": None if not n else k / n})
    write_json(
        OUT / "models" / "survival" / "path_archetypes.json",
        {
            "written_utc": utc_now(),
            "method": "kmeans_k6_train_last_alive_summary",
            "not_a_live_feature": True,
            "centroids": cents.tolist(),
            "center": mu.tolist(),
            "scale": sd.tolist(),
            "clusters": clusters,
            "note": "Assigned to VAL/OOS completed paths for stability only. Not used in hazard Z_t.",
        },
    )
    # VAL/OOS assignment for stability
    stab = {}
    for split in ("VALIDATION", "OOS"):
        msk = split_mask(d["split"], split)
        last_s = {}
        for i in np.where(msk)[0]:
            last_s[d["trade_id"][i]] = i
        if not last_s:
            continue
        vecs_s = []
        y_s = []
        for tid, i in last_s.items():
            vecs_s.append(
                [
                    d["mae"][i] if np.isfinite(d["mae"][i]) else 0.0,
                    float(mfe_col[i] or 0.0),
                    float(peff_col[i] or 0.0),
                    d["vol5"][i] if np.isfinite(d["vol5"][i]) else 0.0,
                    d["mom5"][i] if np.isfinite(d["mom5"][i]) else 0.0,
                    float(down_col[i] or 0.0),
                ]
            )
            y_s.append(int(d["eventual"][i] or 0))
        Zs = (np.asarray(vecs_s) - mu) / sd
        lab = assign_kmeans(Zs, cents)
        outc = []
        for j in range(6):
            mm = lab == j
            n = int(mm.sum())
            k = int(np.asarray(y_s)[mm].sum()) if n else 0
            outc.append({"cluster": j, "n": n, "q": None if not n else k / n})
        stab[split] = outc
    write_json(OUT / "models" / "survival" / "archetype_stability.json", stab)
    print("fit_survival model3 + kmeans archetypes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
