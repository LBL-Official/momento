#!/usr/bin/env python3
"""Spec upgrade: UMAP/HDBSCAN, K=2–20, walk-forward, GB, permutation, survive thresholds, portfolio.

Does not retune on OOS. UMAP/t-SNE are visualization only.
"""

from __future__ import annotations

import math
from collections import defaultdict
from datetime import datetime

import numpy as np

from analyze import (
    ID_COLS,
    TARGET,
    brier,
    ece,
    filter_eval,
    impute,
    matrix,
    numeric_cols,
    robust_scale,
    roc_auc,
)
from common import (
    EV_UNCONDITIONAL,
    MIN_ACCEPTANCE,
    MIN_BUCKET_N,
    OUT,
    Q_UNCONDITIONAL,
    SEED,
    ev_from_q,
    utc_now,
    wilson,
    write_json,
)

EXTRA_SKIP = {
    "Y_survive_40",
    "Y_hit_40",
    "Y_settle_yes",
    "mae_after_entry_cents",
    "possessions_until_stop",
    "minutes_until_stop",
    "mae_after_entry_role",
    "possessions_until_stop_role",
    "minutes_until_stop_role",
    "minutes_until_stop_resolution",
    "candle_derived_microstructure_proxy",
    "candle_not_l2",
    "pregame_win_probability",
    "team_strength_difference",
    "lineup_state",
    "order_book_imbalance",
    "true_l2_depth",
    "availability_pregame",
    "availability_l2",
    "availability_lineup",
    "entry_bid_high_cents",
    "entry_bid_low_cents",
    "entry_last_close_cents",
    "entry_volume_hundredths",
}


def main() -> int:
    from sklearn.cluster import AgglomerativeClustering, KMeans
    from sklearn.decomposition import PCA
    from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier
    from sklearn.inspection import permutation_importance
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import calinski_harabasz_score, davies_bouldin_score, silhouette_score
    from sklearn.mixture import GaussianMixture
    from sklearn.neighbors import KNeighborsClassifier

    from common import read_parquet_rows

    rows = [r for r in read_parquet_rows(OUT / "features_v2.parquet") if r.get("primary_set")]
    train = [r for r in rows if r["dataset_split"] == "TRAIN"]
    val = [r for r in rows if r["dataset_split"] == "VALIDATION"]
    oos = [r for r in rows if r["dataset_split"] == "OOS"]
    skip = set(ID_COLS) | EXTRA_SKIP
    sample = rows[0]
    cols = []
    for k, v in sample.items():
        if k in skip:
            continue
        if k.startswith("candle_"):
            continue  # secondary; possession-primary clustering
        vals = [r.get(k) for r in train if r.get(k) is not None]
        if vals and all(isinstance(x, (int, float)) and not isinstance(x, bool) for x in vals[:12]):
            cols.append(k)
    candle_cols = [
        k
        for k in sample
        if k.startswith("candle_feat_") and k not in skip
    ]

    Xtr, ytr, mtr = matrix(train, cols)
    Xi, med = impute(Xtr, mtr, fit=True)
    Xs, meds, q1, q3 = robust_scale(Xi, fit=True)
    Xv, yv, mv = matrix(val, cols)
    Xvi, _ = impute(Xv, mv, med=med, fit=False)
    Xvs, *_ = robust_scale(Xvi, q1=q1, q3=q3, med=meds, fit=False)
    Xo, yo, mo = matrix(oos, cols)
    Xoi, _ = impute(Xo, mo, med=med, fit=False)
    Xos, *_ = robust_scale(Xoi, q1=q1, q3=q3, med=meds, fit=False)

    pca = PCA(n_components=min(12, Xs.shape[1]), random_state=SEED)
    Z = pca.fit_transform(Xs)
    loadings = []
    for i, name in enumerate(cols):
        loadings.append({"feature": name, "pc1": float(pca.components_[0, i]), "pc2": float(pca.components_[1, i])})
    loadings.sort(key=lambda r: abs(r["pc1"]), reverse=True)
    write_json(
        OUT / "pca_loadings.json",
        {
            "explained_variance": pca.explained_variance_ratio_.tolist(),
            "cumulative": np.cumsum(pca.explained_variance_ratio_).tolist(),
            "top_pc1": loadings[:25],
            "note": "Do not treat components as economic classes unless loadings support it.",
        },
    )

    cluster_rows = []
    for k in range(2, 21):
        km = KMeans(n_clusters=k, random_state=SEED, n_init=10)
        lab = km.fit_predict(Xs)
        sil = float(silhouette_score(Xs, lab)) if len(set(lab)) > 1 else None
        ch = float(calinski_harabasz_score(Xs, lab)) if len(set(lab)) > 1 else None
        db = float(davies_bouldin_score(Xs, lab)) if len(set(lab)) > 1 else None
        val_lab = km.predict(Xvs)
        oos_lab = km.predict(Xos)
        profiles = []
        for c in range(k):
            def qy(y, m):
                n = int(m.sum())
                return (None, 0) if n == 0 else (float(y[m].mean()), n)

            qt, nt = qy(ytr, lab == c)
            qva, nva = qy(yv, val_lab == c)
            qo, no = qy(yo, oos_lab == c)
            lo, hi = (None, None)
            if nt:
                _, lo, hi = wilson(int(round(qt * nt)), nt)
            profiles.append(
                {
                    "cluster": c,
                    "train_n": nt,
                    "train_q": qt,
                    "train_survive": None if qt is None else 1 - qt,
                    "train_ev": ev_from_q(qt),
                    "train_wilson": [lo, hi],
                    "val_n": nva,
                    "val_q": qva,
                    "oos_n": no,
                    "oos_q": qo,
                    "oos_ev": ev_from_q(qo),
                }
            )
        qs = [p["train_q"] for p in profiles if p["train_q"] is not None and p["train_n"] >= MIN_BUCKET_N]
        cluster_rows.append(
            {
                "k": k,
                "algo": "kmeans",
                "silhouette": sil,
                "calinski_harabasz": ch,
                "davies_bouldin": db,
                "train_q_range": (max(qs) - min(qs)) if len(qs) >= 2 else 0,
                "profiles": profiles,
            }
        )
        try:
            gmm = GaussianMixture(n_components=k, covariance_type="diag", random_state=SEED, n_init=1)
            gmm.fit(Xs)
            cluster_rows.append(
                {
                    "k": k,
                    "algo": "gmm_diag",
                    "aic": float(gmm.aic(Xs)),
                    "bic": float(gmm.bic(Xs)),
                    "silhouette": float(silhouette_score(Xs, gmm.predict(Xs))),
                }
            )
        except Exception as exc:  # noqa: BLE001
            cluster_rows.append({"k": k, "algo": "gmm_diag", "error": str(exc)})

    for link in ("ward", "average", "complete"):
        ag = AgglomerativeClustering(n_clusters=4, linkage=link)
        alab = ag.fit_predict(Xs)
        cluster_rows.append(
            {
                "k": 4,
                "algo": f"hierarchical_{link}",
                "silhouette": float(silhouette_score(Xs, alab)),
            }
        )

    umap_note = "UMAP not used as proof."
    umap_points = []
    try:
        import umap  # type: ignore

        reducer = umap.UMAP(n_neighbors=15, min_dist=0.1, random_state=SEED)
        U = reducer.fit_transform(Xs)
        for i, r in enumerate(train):
            umap_points.append({"split": "TRAIN", "x": float(U[i, 0]), "y": float(U[i, 1]), "Y_40_CLOSE": int(r[TARGET])})
        umap_note = "UMAP exploratory visualization only. Not evidence of tradable clusters."
    except Exception as exc:  # noqa: BLE001
        umap_note = f"UMAP unavailable ({exc}). Visualization skipped."

    hdb = {"status": "UNAVAILABLE"}
    try:
        import hdbscan  # type: ignore

        cl = hdbscan.HDBSCAN(min_cluster_size=30, min_samples=10)
        lab = cl.fit_predict(Xs)
        ncl = len(set(lab) - {-1})
        hdb = {
            "status": "RAN",
            "n_clusters": ncl,
            "n_noise": int((lab == -1).sum()),
            "note": "Density clusters; not a production taxonomy.",
        }
    except Exception as exc:  # noqa: BLE001
        hdb = {"status": "UNAVAILABLE", "error": str(exc)}

    write_json(
        OUT / "clusters_extended.json",
        {
            "kmeans_2_to_20": [r for r in cluster_rows if r.get("algo") == "kmeans"],
            "other": [r for r in cluster_rows if r.get("algo") != "kmeans"],
            "hdbscan": hdb,
            "umap_note": umap_note,
            "note": "Do not select K solely on silhouette. DISCOVERED AFTER MULTIPLE SEARCHES.",
        },
    )
    write_json(OUT / "umap_points.json", {"points": umap_points, "note": umap_note})

    # Possession-primary vs candle-secondary vs combined — VAL Brier vs Model 0.
    def fit_brier(fn, name):
        fn = [c for c in fn if c]
        if len(fn) < 2:
            return {"model": name, "n_features": len(fn), "skipped": True}
        Xa, ya, ma = matrix(train, fn)
        Xi_, medi = impute(Xa, ma, fit=True)
        Xs_, meds_, q1_, q3_ = robust_scale(Xi_, fit=True)
        m = LogisticRegression(C=1.0, max_iter=400, random_state=SEED)
        m.fit(Xs_, ya)

        def pred(split_rows):
            Xb, yb, mb = matrix(split_rows, fn)
            Xbi, _ = impute(Xb, mb, med=medi, fit=False)
            Xbs, *_ = robust_scale(Xbi, q1=q1_, q3=q3_, med=meds_, fit=False)
            return yb, m.predict_proba(Xbs)[:, 1]

        yv_, pv = pred(val)
        yo_, po = pred(oos)
        return {
            "model": "l2_logistic",
            "feature_set": name,
            "n_features": len(fn),
            "validation": {"brier": brier(yv_, pv), "auc": roc_auc(yv_, pv), "ece": ece(yv_, pv)},
            "oos": {"brier": brier(yo_, po), "auc": roc_auc(yo_, po)},
        }

    gs = [c for c in ("quarter", "official_time_remaining_s", "game_elapsed_seconds", "game_completion_pct", "possession_number", "estimated_possessions_remaining", "score_differential") if c in cols]
    ablations = [
        fit_brier(gs, "game_state_only"),
        fit_brier([c for c in cols if c.endswith("p") and not c.startswith("mkt_")], "possession_dynamics_only"),
        fit_brier([c for c in cols if c.startswith("mkt_") and not any(c.endswith(f"{w}p") for w in (1, 3, 5, 10, 20, 30))], "market_state_only"),
        fit_brier(candle_cols, "price_path_candle_secondary"),
        fit_brier([c for c in cols if "std" in c or "vol" in c or "entropy" in c or "instab" in c], "volatility_only"),
        fit_brier(gs + [c for c in cols if c.startswith("mkt_")], "game_plus_market"),
        fit_brier(cols, "possession_primary_full"),
        fit_brier(cols + candle_cols, "possession_plus_candle"),
    ]
    gb = GradientBoostingClassifier(max_depth=2, n_estimators=80, learning_rate=0.05, min_samples_leaf=25, random_state=SEED)
    Xa, ya, ma = matrix(train, cols)
    Xi_, medi = impute(Xa, ma, fit=True)
    Xs_, meds_, q1_, q3_ = robust_scale(Xi_, fit=True)
    gb.fit(Xs_, ya)
    Xbv, ybv, mbv = matrix(val, cols)
    Xbvi, _ = impute(Xbv, mbv, med=medi, fit=False)
    Xbvs, *_ = robust_scale(Xbvi, q1=q1_, q3=q3_, med=meds_, fit=False)
    pval = gb.predict_proba(Xbvs)[:, 1]
    Xbo, ybo, mbo = matrix(oos, cols)
    Xboi, _ = impute(Xbo, mbo, med=medi, fit=False)
    Xbos, *_ = robust_scale(Xboi, q1=q1_, q3=q3_, med=meds_, fit=False)
    poos = gb.predict_proba(Xbos)[:, 1]
    ablations.append(
        {
            "model": "gradient_boosting",
            "feature_set": "possession_primary_full",
            "validation": {"brier": brier(ybv, pval), "auc": roc_auc(ybv, pval), "ece": ece(ybv, pval)},
            "oos": {"brier": brier(ybo, poos), "auc": roc_auc(ybo, poos)},
            "note": "Conservative depth=2. Not tuned on OOS.",
        }
    )
    # KNN neighborhood hypothesis
    knn = KNeighborsClassifier(n_neighbors=25, weights="distance")
    knn.fit(Xs_, ya)
    knn_val = knn.predict_proba(Xbvs)[:, 1]
    knn_oos = knn.predict_proba(Xbos)[:, 1]
    ablations.append(
        {
            "model": "knn_25",
            "feature_set": "possession_primary_full",
            "validation": {"brier": brier(ybv, knn_val), "auc": roc_auc(ybv, knn_val)},
            "oos": {"brier": brier(ybo, knn_oos), "auc": roc_auc(ybo, knn_oos)},
            "note": "Neighborhood hypothesis. K not tuned on OOS.",
        }
    )
    write_json(OUT / "ablation_extended.json", {"model0_val_brier": brier(yv, np.full(len(yv), Q_UNCONDITIONAL)), "results": ablations})

    # Permutation importance on VAL for game-state logistic (held-out).
    fn = gs
    Xa, ya, ma = matrix(train, fn)
    Xi_, medi = impute(Xa, ma, fit=True)
    Xs_, meds_, q1_, q3_ = robust_scale(Xi_, fit=True)
    lr = LogisticRegression(C=1.0, max_iter=400, random_state=SEED)
    lr.fit(Xs_, ya)
    Xbv, ybv, mbv = matrix(val, fn)
    Xbvi, _ = impute(Xbv, mbv, med=medi, fit=False)
    Xbvs, *_ = robust_scale(Xbvi, q1=q1_, q3=q3_, med=meds_, fit=False)
    pi = permutation_importance(lr, Xbvs, ybv, n_repeats=10, random_state=SEED, scoring="neg_brier_score")
    imp = sorted(
        [{"feature": fn[i], "mean": float(pi.importances_mean[i]), "std": float(pi.importances_std[i])} for i in range(len(fn))],
        key=lambda r: abs(r["mean"]),
        reverse=True,
    )
    write_json(OUT / "permutation_importance_val.json", {"held_out": "VALIDATION", "model": "l2_logistic_game_state", "rows": imp})

    # Survive-probability thresholds (P_survive = 1 - q_hat). VAL chooses, OOS frozen.
    p_surv_val = 1.0 - lr.predict_proba(Xbvs)[:, 1]
    Xbo, ybo, mbo = matrix(oos, fn)
    Xboi, _ = impute(Xbo, mbo, med=medi, fit=False)
    Xbos, *_ = robust_scale(Xboi, q1=q1_, q3=q3_, med=meds_, fit=False)
    p_surv_oos = 1.0 - lr.predict_proba(Xbos)[:, 1]
    y_surv_val = 1.0 - ybv
    y_surv_oos = 1.0 - ybo
    surv_rows = []
    for t in (0.50, 0.67, 0.70, 0.75, 0.80):
        def pack(y, p, split):
            acc = p >= t
            n = int(acc.sum())
            s = float(y[acc].mean()) if n else None
            q = None if s is None else 1 - s
            return {
                "split": split,
                "p_survive_min": t,
                "n": n,
                "acceptance": n / len(y) if len(y) else 0,
                "survive": s,
                "q": q,
                "ev": ev_from_q(q),
            }

        surv_rows.append({"val": pack(y_surv_val, p_surv_val, "VALIDATION"), "oos": pack(y_surv_oos, p_surv_oos, "OOS")})
    write_json(OUT / "survive_thresholds.json", {"model": "l2_logistic_game_state", "rows": surv_rows})

    # Walk-forward inside TRAIN+VAL only.
    tv = sorted(train + val, key=lambda r: r.get("game_date") or "")
    months = sorted({(r.get("game_date") or "")[:7] for r in tv if r.get("game_date")})
    wf = []
    for i in range(2, len(months)):
        tr_m, va_m = months[:i], months[i]
        tr_rows = [r for r in tv if (r.get("game_date") or "")[:7] in set(tr_m)]
        va_rows = [r for r in tv if (r.get("game_date") or "")[:7] == va_m]
        if len(tr_rows) < 80 or len(va_rows) < 20:
            continue
        pack = fit_brier(gs, f"wf_{va_m}")
        # refit explicitly
        Xa, ya, ma = matrix(tr_rows, gs)
        Xi_, medi = impute(Xa, ma, fit=True)
        Xs_, meds_, q1_, q3_ = robust_scale(Xi_, fit=True)
        m = LogisticRegression(C=1.0, max_iter=400, random_state=SEED)
        m.fit(Xs_, ya)
        Xb, yb, mb = matrix(va_rows, gs)
        Xbi, _ = impute(Xb, mb, med=medi, fit=False)
        Xbs, *_ = robust_scale(Xbi, q1=q1_, q3=q3_, med=meds_, fit=False)
        pr = m.predict_proba(Xbs)[:, 1]
        wf.append(
            {
                "train_months": tr_m,
                "validate_month": va_m,
                "n_train": len(tr_rows),
                "n_val": len(va_rows),
                "brier": brier(yb, pr),
                "auc": roc_auc(yb, pr),
                "model0_brier": brier(yb, np.full(len(yb), Q_UNCONDITIONAL)),
            }
        )
    write_json(OUT / "walk_forward.json", {"folds": wf, "note": "TRAIN+VAL only. Final OOS untouched."})

    # Portfolio: research $50, 12.5% = $6.25, max 5 concurrent. Not live MLB.
    dates = defaultdict(list)
    for r in rows:
        dates[r.get("game_date")].append(r)
    concurrent = [len(v) for v in dates.values()]
    skipped = 0
    taken = 0
    for day, lst in dates.items():
        cap = 5
        taken += min(len(lst), cap)
        skipped += max(0, len(lst) - cap)
    write_json(
        OUT / "portfolio_sim.json",
        {
            "research_bankroll_usd": 50,
            "allocation_pct": 12.5,
            "entry_budget_usd": 6.25,
            "max_concurrent": 5,
            "max_same_day_observed": max(concurrent) if concurrent else 0,
            "mean_same_day": float(np.mean(concurrent)) if concurrent else 0,
            "unfiltered_taken_if_cap5": taken,
            "unfiltered_skipped_if_cap5": skipped,
            "weekly_primary": len(rows)
            / max(
                1e-6,
                (
                    datetime.strptime(sorted(d for d in dates if d)[-1], "%Y-%m-%d")
                    - datetime.strptime(sorted(d for d in dates if d)[0], "%Y-%m-%d")
                ).days
                / 7.0,
            ),
            "note": "Research parameters. Not live MLB allocations. Not optimized on OOS. Fees NOT production FeeModel.",
        },
    )

    # Label summaries
    mae = [r.get("mae_after_entry_cents") for r in rows if r.get("mae_after_entry_cents") is not None]
    write_json(
        OUT / "labels_summary.json",
        {
            "Y_survive_40": sum(int(r["Y_survive_40"]) for r in rows),
            "Y_hit_40": sum(int(r["Y_hit_40"]) for r in rows),
            "Y_settle_yes": sum(int(r["Y_settle_yes"]) for r in rows),
            "n_primary": len(rows),
            "mae_after_median_cents": float(np.median(mae)) if mae else None,
            "possessions_until_stop_median": float(
                np.median([r["possessions_until_stop"] for r in rows if r.get("possessions_until_stop") is not None])
            ),
        },
    )
    print("upgrade_analyze done", "kmeans", 19, "wf", len(wf), "umap", len(umap_points), "hdb", hdb.get("status"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
