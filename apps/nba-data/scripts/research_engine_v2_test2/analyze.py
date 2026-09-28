#!/usr/bin/env python3
"""Phases 3–7: diagnostics, clusters, models, ablation, economics, registry.

TRAIN=BUILD, VAL=CHOOSE, OOS=VERIFY. sklearn research-venv only.
"""

from __future__ import annotations

import math
import sys
from collections import defaultdict

import numpy as np

from common import (
    BH_Q,
    BREAKEVEN_Q,
    BUCKET_GAP_PP,
    ECE_TOLERANCE,
    EV_UNCONDITIONAL,
    FILTER_THRESHOLDS,
    MIN_ACCEPTANCE,
    MIN_BUCKET_N,
    OUT,
    PRIMARY_ALIGN,
    Q_UNCONDITIONAL,
    SEED,
    ev_from_q,
    git_commit,
    read_parquet_rows,
    utc_now,
    wilson,
    write_json,
    write_parquet,
)

TARGET = "Y_40_CLOSE"
ID_COLS = {
    "observation_id",
    "event_id",
    "ticker",
    "team_code",
    "game_date",
    "dataset_split",
    "entry_decision_time",
    "possession_id",
    "alignment_confidence",
    "alignment_reason",
    "game_phase",
    "maker_fill_confidence",
    "possession_team",
    "game_regime",
    "coupling_regime",
    "mkt_alignment_quality",
    "mkt_dynamics_label",
    "observed_or_derived",
    "mkt_observed_or_derived",
    "coupling_observed_or_derived",
    "primary_set",
    "z_uses_future_possession",
    "l2_invented",
    "wall_clock_claimed_observed",
    "mkt_l2_available",
    "mkt_not_l2",
    "coupling_not_causal_proof",
    TARGET,
    "SURVIVE_40",
    "Y_40_WICK",
    "expiration_result_yes",
    "time_to_40_minutes",
}

GAME_STATE = [
    "quarter",
    "official_time_remaining_s",
    "game_elapsed_seconds",
    "game_completion_pct",
    "possession_number",
    "estimated_possessions_remaining",
    "score_differential",
]
PATH = [c for c in (
    # filled at runtime from columns
)]
MARKET_STATE = [
    "mkt_yes_bid_cents",
    "mkt_spread_cents",
    "mkt_distance_from_80_cents",
]
COUPLING = [
    "coupling_response_per_score_10p",
    "coupling_mkt_after_turnover_10p",
    "coupling_consistency_10p",
]


def numeric_cols(rows):
    skip = set(ID_COLS)
    cols = []
    sample = rows[0]
    for k, v in sample.items():
        if k in skip:
            continue
        if isinstance(v, (int, float)) or v is None:
            cols.append(k)
    # drop bool-like strings
    keep = []
    for c in cols:
        vals = [r.get(c) for r in rows if r.get(c) is not None]
        if not vals:
            continue
        if all(isinstance(x, (int, float, bool)) and not isinstance(x, bool) for x in vals[:20]):
            keep.append(c)
        elif all(isinstance(x, (int, float)) for x in vals[:30]):
            keep.append(c)
    return keep


def matrix(rows, cols):
    X = np.zeros((len(rows), len(cols)), dtype=float)
    mask = np.ones_like(X, dtype=bool)
    y = np.array([r[TARGET] for r in rows], dtype=float)
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


def impute(X, mask, med=None, fit=False):
    out = X.copy()
    p = X.shape[1]
    if fit:
        med = np.zeros(p)
        for j in range(p):
            vals = out[mask[:, j], j]
            med[j] = float(np.median(vals)) if len(vals) else 0.0
    for j in range(p):
        out[~mask[:, j], j] = med[j]
    return out, med


def robust_scale(X, q1=None, q3=None, med=None, fit=False):
    if fit:
        med = np.median(X, axis=0)
        q1 = np.quantile(X, 0.25, axis=0)
        q3 = np.quantile(X, 0.75, axis=0)
    iqr = np.where((q3 - q1) < 1e-9, 1.0, q3 - q1)
    return (X - med) / iqr, med, q1, q3


def brier(y, p):
    return float(np.mean((np.asarray(p) - np.asarray(y)) ** 2))


def ece(y, p, n_bins=10):
    y = np.asarray(y, float)
    p = np.asarray(p, float)
    bins = np.linspace(0, 1, n_bins + 1)
    tot = 0.0
    n = len(y)
    for i in range(n_bins):
        lo, hi = bins[i], bins[i + 1]
        m = (p >= lo) & (p <= hi if i == n_bins - 1 else p < hi)
        if m.sum() == 0:
            continue
        tot += (m.sum() / n) * abs(y[m].mean() - p[m].mean())
    return float(tot)


def roc_auc(y, p):
    y = np.asarray(y).astype(int)
    p = np.asarray(p, float)
    n1 = int(y.sum())
    n0 = len(y) - n1
    if n0 == 0 or n1 == 0:
        return None
    order = np.argsort(p)
    ranks = np.empty(len(p))
    ranks[order] = np.arange(1, len(p) + 1)
    u = ranks[y == 1].sum() - n1 * (n1 + 1) / 2.0
    return float(u / (n1 * n0))


def filter_eval(y, p, t):
    y = np.asarray(y, float)
    p = np.asarray(p, float)
    acc = p < t
    n = len(y)
    na = int(acc.sum())
    q = (y[acc].sum() / na) if na else None
    return {
        "threshold": t,
        "n_accepted": na,
        "acceptance_rate": na / n if n else 0,
        "actual_q": q,
        "ev": ev_from_q(q) if q is not None else None,
        "beats": bool(q is not None and ev_from_q(q) > ev_from_q(float(y.mean()))),
        "acc_ok": bool((na / n if n else 0) >= MIN_ACCEPTANCE),
    }


def bh_fdr(pvals, q=BH_Q):
    m = len(pvals)
    order = np.argsort(pvals)
    out = np.zeros(m, dtype=bool)
    thresh = 0
    for i, idx in enumerate(order, 1):
        if pvals[idx] <= q * i / m:
            thresh = i
    for i, idx in enumerate(order, 1):
        if i <= thresh:
            out[idx] = True
    return out


def two_prop(k1, n1, k0, n0):
    if n1 == 0 or n0 == 0:
        return 1.0
    p1, p0 = k1 / n1, k0 / n0
    p = (k1 + k0) / (n1 + n0)
    se = math.sqrt(p * (1 - p) * (1 / n1 + 1 / n0))
    if se < 1e-12:
        return 1.0
    z = abs(p1 - p0) / se
    # two-sided normal
    return float(2 * (1 - 0.5 * (1 + math.erf(z / math.sqrt(2)))))


def main() -> int:
    try:
        from sklearn.calibration import CalibratedClassifierCV
        from sklearn.cluster import AgglomerativeClustering, KMeans
        from sklearn.decomposition import PCA
        from sklearn.linear_model import LogisticRegression
        from sklearn.metrics import adjusted_rand_score, davies_bouldin_score, silhouette_score
        from sklearn.mixture import GaussianMixture
        from sklearn.neighbors import KNeighborsClassifier
        from sklearn.ensemble import ExtraTreesClassifier, RandomForestClassifier
    except ImportError:
        print("Installing scikit-learn into the research venv is required.", file=sys.stderr)
        return 1

    rows = [
        r
        for r in read_parquet_rows(OUT / "features.parquet")
        if r.get("primary_set")
    ]
    train = [r for r in rows if r["dataset_split"] == "TRAIN"]
    val = [r for r in rows if r["dataset_split"] == "VALIDATION"]
    oos = [r for r in rows if r["dataset_split"] == "OOS"]
    cols = numeric_cols(rows)
    path_cols = [c for c in cols if c.endswith("p") and not c.startswith("mkt_") and not c.startswith("coupling_")]
    mkt_path_cols = [c for c in cols if c.startswith("mkt_") and c not in MARKET_STATE]
    gs_cols = [c for c in GAME_STATE if c in cols]
    ms_cols = [c for c in MARKET_STATE if c in cols]
    cp_cols = [c for c in COUPLING if c in cols]
    dyn_cols = [
        c
        for c in cols
        if c.startswith("net_score")
        or c.startswith("score_diff")
        or c.startswith("game_")
        or c.startswith("lead_reversal")
        or c.startswith("possession_outcome")
        or c.startswith("abs_score")
    ]

    # --- Phase 3 diagnostics ---
    miss = {}
    for c in cols:
        n_m = sum(1 for r in train if r.get(c) is None)
        miss[c] = n_m / max(1, len(train))
    Xtr, ytr, mtr = matrix(train, cols)
    Xi, med = impute(Xtr, mtr, fit=True)
    # Pearson
    with np.errstate(invalid="ignore"):
        corr = np.corrcoef(Xi, rowvar=False)
    corr = np.nan_to_num(corr, nan=0.0)
    # redundancy: |r|>0.9
    red = []
    for i in range(len(cols)):
        for j in range(i + 1, len(cols)):
            if abs(corr[i, j]) >= 0.9:
                red.append({"a": cols[i], "b": cols[j], "r": float(corr[i, j])})
    write_json(
        OUT / "diagnostics.json",
        {
            "written_utc": utc_now(),
            "n_train": len(train),
            "n_val": len(val),
            "n_oos": len(oos),
            "n_features": len(cols),
            "missingness": miss,
            "high_corr_pairs": red[:80],
            "DISCOVERED_AFTER_MULTIPLE_SEARCHES": True,
        },
    )

    # Univariate TRAIN + BH
    uni = []
    pvals = []
    for c in gs_cols + ["score_differential", "possession_number", "mkt_spread_cents"]:
        if c not in cols:
            continue
        vals = [(r.get(c), r[TARGET]) for r in train if r.get(c) is not None]
        if len(vals) < 40:
            continue
        xs = [v[0] for v in vals]
        medx = float(np.median(xs))
        hi = [v[1] for v, x in zip(vals, xs) if x >= medx]
        lo = [v[1] for v, x in zip(vals, xs) if x < medx]
        k1, n1 = int(sum(hi)), len(hi)
        k0, n0 = int(sum(lo)), len(lo)
        pv = two_prop(k1, n1, k0, n0)
        pvals.append(pv)
        uni.append({"feature": c, "split": "high_vs_low_median", "p": pv, "q_high": k1 / n1 if n1 else None, "q_low": k0 / n0 if n0 else None, "n_high": n1, "n_low": n0})
    sig = bh_fdr(np.array(pvals), BH_Q) if pvals else []
    for i, u in enumerate(uni):
        u["bh_pass"] = bool(sig[i]) if len(sig) else False
        u["class"] = "EXPLORATORY"
    write_json(OUT / "univariate_fdr.json", {"rows": uni, "bh_q": BH_Q})

    # --- Phase 4 clusters on scaled TRAIN ---
    Xs, meds, q1, q3 = robust_scale(Xi, fit=True)
    pca = PCA(n_components=min(12, Xs.shape[1]), random_state=SEED)
    Z = pca.fit_transform(Xs)
    pca_var = pca.explained_variance_ratio_.tolist()
    cluster_rows = []
    best_k = None
    best_sep = -1
    Xv, yv, mv = matrix(val, cols)
    Xvi, _ = impute(Xv, mv, med=med, fit=False)
    Xvs, *_ = robust_scale(Xvi, q1=q1, q3=q3, med=meds, fit=False)
    Xo, yo, mo = matrix(oos, cols)
    Xoi, _ = impute(Xo, mo, med=med, fit=False)
    Xos, *_ = robust_scale(Xoi, q1=q1, q3=q3, med=meds, fit=False)

    for k in range(2, 16):
        km = KMeans(n_clusters=k, random_state=SEED, n_init=10)
        lab = km.fit_predict(Xs)
        sil = float(silhouette_score(Xs, lab)) if len(set(lab)) > 1 else -1
        db = float(davies_bouldin_score(Xs, lab)) if len(set(lab)) > 1 else None
        val_lab = km.predict(Xvs)
        oos_lab = km.predict(Xos)
        profiles = []
        for c in range(k):
            tr_m = lab == c
            va_m = val_lab == c
            oo_m = oos_lab == c
            def qy(y, m):
                n = int(m.sum())
                if n == 0:
                    return None, 0
                return float(y[m].mean()), n
            qt, nt = qy(ytr, tr_m)
            qva, nva = qy(yv, va_m)
            qo, no = qy(yo, oo_m)
            profiles.append(
                {
                    "cluster": int(c),
                    "train_n": nt,
                    "train_q": qt,
                    "train_ev": ev_from_q(qt),
                    "val_n": nva,
                    "val_q": qva,
                    "val_ev": ev_from_q(qva),
                    "oos_n": no,
                    "oos_q": qo,
                    "oos_ev": ev_from_q(qo),
                }
            )
        qs = [p["train_q"] for p in profiles if p["train_q"] is not None and p["train_n"] >= MIN_BUCKET_N]
        sep = (max(qs) - min(qs)) if len(qs) >= 2 else 0
        cluster_rows.append({"k": k, "algo": "kmeans", "silhouette": sil, "davies_bouldin": db, "train_q_range": sep, "profiles": profiles})
        if sep > best_sep and sil > 0:
            best_sep = sep
            best_k = k
        try:
            gmm = GaussianMixture(
                n_components=k, random_state=SEED, covariance_type="diag", n_init=1
            )
            glab = gmm.fit_predict(Xs)
            gsil = float(silhouette_score(Xs, glab)) if len(set(glab)) > 1 else -1
            cluster_rows.append({"k": k, "algo": "gmm", "silhouette": gsil, "train_q_range": None})
        except Exception as exc:  # noqa: BLE001
            cluster_rows.append({"k": k, "algo": "gmm", "error": str(exc)})

    for hk in (2, 4, 6, 8):
        ag = AgglomerativeClustering(n_clusters=hk)
        alab = ag.fit_predict(Xs)
        cluster_rows.append(
            {
                "k": hk,
                "algo": "hierarchical",
                "silhouette": float(silhouette_score(Xs, alab)) if len(set(alab)) > 1 else -1,
            }
        )
    # Bootstrap assignment stability on TRAIN (K-Means best_k or 4).
    k_stab = best_k or 4
    km_base = KMeans(n_clusters=k_stab, random_state=SEED, n_init=10)
    lab_base = km_base.fit_predict(Xs)
    rng = np.random.RandomState(SEED)
    aris = []
    for b in range(10):
        idx = rng.choice(len(Xs), size=max(20, int(0.8 * len(Xs))), replace=False)
        km_b = KMeans(n_clusters=k_stab, random_state=SEED + b, n_init=5)
        km_b.fit(Xs[idx])
        lab_b = km_b.predict(Xs)
        aris.append(float(adjusted_rand_score(lab_base, lab_b)))
    oos_lab = km_base.predict(Xos)
    persist = []
    for c in range(k_stab):
        tr_m = lab_base == c
        oo_m = oos_lab == c
        persist.append(
            {
                "cluster": int(c),
                "train_n": int(tr_m.sum()),
                "train_q": float(ytr[tr_m].mean()) if tr_m.sum() else None,
                "oos_n": int(oo_m.sum()),
                "oos_q": float(yo[oo_m].mean()) if oo_m.sum() else None,
            }
        )
    write_json(
        OUT / "clusters.json",
        {
            "pca_explained_variance": pca_var,
            "best_k_by_train_q_range": best_k,
            "stability_k": k_stab,
            "bootstrap_ari_mean": float(np.mean(aris)) if aris else None,
            "bootstrap_ari": aris,
            "oos_persistence": persist,
            "results": cluster_rows,
            "note": "UMAP not used as proof. Clusters are exploratory. DISCOVERED AFTER MULTIPLE SEARCHES.",
        },
    )
    pca_points = []
    Ztr = Z[:, :2]
    for i, r in enumerate(train):
        pca_points.append(
            {
                "split": "TRAIN",
                "pc1": float(Ztr[i, 0]),
                "pc2": float(Ztr[i, 1]),
                "Y_40_CLOSE": int(r[TARGET]),
                "cluster": int(lab_base[i]),
            }
        )
    Zva = pca.transform(Xvs)[:, :2]
    for i, r in enumerate(val):
        pca_points.append(
            {
                "split": "VALIDATION",
                "pc1": float(Zva[i, 0]),
                "pc2": float(Zva[i, 1]),
                "Y_40_CLOSE": int(r[TARGET]),
            }
        )
    Zos = pca.transform(Xos)[:, :2]
    for i, r in enumerate(oos):
        pca_points.append(
            {
                "split": "OOS",
                "pc1": float(Zos[i, 0]),
                "pc2": float(Zos[i, 1]),
                "Y_40_CLOSE": int(r[TARGET]),
            }
        )
    write_json(OUT / "pca_points.json", {"points": pca_points, "note": "PCA visualization only. Not evidence."})

    # --- Phase 5 models ---
    def fit_eval(name, model, feature_names, tag):
        fn = [c for c in feature_names if c in cols]
        if len(fn) < 2:
            return None, None
        Xa, ya, ma = matrix(train, fn)
        Xi_, medi = impute(Xa, ma, fit=True)
        Xs_, meds_, q1_, q3_ = robust_scale(Xi_, fit=True)
        model.fit(Xs_, ya)
        def pred(split_rows):
            Xb, yb, mb = matrix(split_rows, fn)
            Xbi, _ = impute(Xb, mb, med=medi, fit=False)
            Xbs, *_ = robust_scale(Xbi, q1=q1_, q3=q3_, med=meds_, fit=False)
            if hasattr(model, "predict_proba"):
                pr = model.predict_proba(Xbs)[:, 1]
            else:
                pr = model.predict(Xbs).astype(float)
            return yb, pr
        yv_, pv = pred(val)
        yo_, po = pred(oos)
        yt_, pt = pred(train)
        pack = {
            "model": name,
            "feature_set": tag,
            "n_features": len(fn),
            "train": {"n": len(yt_), "brier": brier(yt_, pt), "auc": roc_auc(yt_, pt), "ece": ece(yt_, pt), "q": float(yt_.mean())},
            "validation": {"n": len(yv_), "brier": brier(yv_, pv), "auc": roc_auc(yv_, pv), "ece": ece(yv_, pv), "q": float(yv_.mean())},
            "oos": {"n": len(yo_), "brier": brier(yo_, po), "auc": roc_auc(yo_, po), "ece": ece(yo_, po), "q": float(yo_.mean())},
            "filters_val": [filter_eval(yv_, pv, t) for t in FILTER_THRESHOLDS],
            "filters_oos": [filter_eval(yo_, po, t) for t in FILTER_THRESHOLDS],
            "class": "EXPLORATORY",
        }
        # choose VAL filter
        elig = [f for f in pack["filters_val"] if f["acc_ok"] and f["beats"] and f["ev"] is not None]
        pack["chosen_threshold"] = None if not elig else max(elig, key=lambda f: f["ev"])["threshold"]
        if pack["chosen_threshold"] is not None:
            pack["oos_frozen_filter"] = next(f for f in pack["filters_oos"] if f["threshold"] == pack["chosen_threshold"])
        return pack, (yo_, po)

    model0 = {
        "model": "model0_unconditional",
        "feature_set": "none",
        "validation": {"brier": brier([r[TARGET] for r in val], np.full(len(val), Q_UNCONDITIONAL)), "auc": 0.5, "ece": ece([r[TARGET] for r in val], np.full(len(val), Q_UNCONDITIONAL))},
        "oos": {"brier": brier([r[TARGET] for r in oos], np.full(len(oos), Q_UNCONDITIONAL)), "auc": 0.5},
    }
    families = {
        "game_state": gs_cols,
        "game_path": path_cols + dyn_cols,
        "market_state": ms_cols,
        "market_path": mkt_path_cols,
        "coupling": cp_cols,
        "game_plus_market": gs_cols + path_cols + ms_cols + mkt_path_cols,
        "full": cols,
    }
    results = [model0]
    oos_preds = {}
    for tag, fn in families.items():
        pack, pred = fit_eval(
            "l2_logistic",
            LogisticRegression(penalty="l2", C=1.0, max_iter=400, random_state=SEED),
            fn,
            tag,
        )
        if pack:
            results.append(pack)
            oos_preds[f"l2_{tag}"] = pred
    # trees / knn on full only
    for name, est in [
        ("random_forest", RandomForestClassifier(n_estimators=200, max_depth=4, min_samples_leaf=25, random_state=SEED)),
        ("extra_trees", ExtraTreesClassifier(n_estimators=200, max_depth=4, min_samples_leaf=25, random_state=SEED)),
        ("knn", KNeighborsClassifier(n_neighbors=25, weights="distance")),
    ]:
        pack, pred = fit_eval(name, est, cols, "full")
        if pack:
            results.append(pack)
            oos_preds[name] = pred

    pack, pred = fit_eval(
        "l1_logistic",
        LogisticRegression(
            penalty="l1", solver="liblinear", C=1.0, max_iter=400, random_state=SEED
        ),
        cols,
        "full",
    )
    if pack:
        results.append(pack)
        oos_preds["l1_full"] = pred

    # TRAIN-CV isotonic calibration of L2 logistic (never on VAL/OOS).
    try:
        cal = CalibratedClassifierCV(
            LogisticRegression(penalty="l2", C=1.0, max_iter=400, random_state=SEED),
            method="isotonic",
            cv=3,
        )
        pack, pred = fit_eval("l2_logistic_isotonic_cv", cal, cols, "full")
        if pack:
            pack["note"] = "Isotonic fitted on TRAIN CV only. DISCOVERED AFTER MULTIPLE SEARCHES."
            results.append(pack)
    except Exception as exc:  # noqa: BLE001
        results.append({"model": "l2_logistic_isotonic_cv", "error": str(exc), "class": "EXPLORATORY"})

    # Ensemble: mean of logistic full + rf if both exist (VAL not OOS weights)
    log_full = next((r for r in results if r.get("model") == "l2_logistic" and r.get("feature_set") == "full"), None)
    rf = next((r for r in results if r.get("model") == "random_forest"), None)
    if log_full and rf and "l2_full" in oos_preds and "random_forest" in oos_preds:
        # Need VAL preds for choice — skip weight fit; equal blend diagnostic on OOS labeled as such
        y_o, p_log = oos_preds["l2_full"]
        _, p_rf = oos_preds["random_forest"]
        blend = 0.5 * p_log + 0.5 * p_rf
        results.append(
            {
                "model": "equal_blend_l2_rf",
                "feature_set": "full",
                "oos": {"brier": brier(y_o, blend), "auc": roc_auc(y_o, blend), "ece": ece(y_o, blend)},
                "note": "Equal blend, weights not fit on OOS. DISCOVERED AFTER MULTIPLE SEARCHES.",
                "class": "EXPLORATORY",
            }
        )

    write_json(OUT / "models.json", {"written_utc": utc_now(), "model0_q": Q_UNCONDITIONAL, "results": results})

    # Choose confirmatory: lowest VAL brier among logistic families that beat model0 brier
    m0b = model0["validation"]["brier"]
    cands = [
        r
        for r in results
        if r.get("model") == "l2_logistic" and r.get("validation", {}).get("brier") is not None
    ]
    chosen = min(cands, key=lambda r: r["validation"]["brier"]) if cands else None
    promote = False
    if chosen and chosen["validation"]["brier"] <= 0.95 * m0b:
        promote = True
    # Simple vs complex
    simple = next((r for r in results if r.get("feature_set") == "game_state" and r.get("model") == "l2_logistic"), None)
    fullm = log_full
    simple_wins = False
    if simple and fullm:
        simple_wins = simple["validation"]["brier"] <= fullm["validation"]["brier"] + 1e-6

    # Portfolio: concurrent same-day first-80
    from collections import Counter
    dates = Counter(r["game_date"] for r in rows)
    overlap = {
        "max_same_day": max(dates.values()) if dates else 0,
        "mean_same_day": float(np.mean(list(dates.values()))) if dates else 0,
        "days": len(dates),
        "note": "Research concurrency diagnostic. Not live capital. Not optimized on OOS.",
    }
    weekly = None
    ds = sorted(d for d in dates if d)
    if len(ds) >= 2:
        from datetime import datetime

        weeks = (datetime.strptime(ds[-1], "%Y-%m-%d") - datetime.strptime(ds[0], "%Y-%m-%d")).days / 7.0
        weekly = len(rows) / max(weeks, 1e-6)

    registry = []
    for r in results:
        registry.append(
            {
                "experiment_id": f"{r.get('model')}|{r.get('feature_set')}",
                "timestamp": utc_now(),
                "dataset_version": "NBA_RESEARCH_ENGINE_V2_TEST2",
                "feature_set": r.get("feature_set"),
                "target": TARGET,
                "model": r.get("model"),
                "train_period": f"<= { '2025-12-31' }",
                "validation_period": "2026-01-01..2026-03-15",
                "oos_period": ">2026-03-15",
                "random_seed": SEED,
                "git_commit_hash": git_commit(),
                "class": r.get("class", "EXPLORATORY"),
                "results": {k: r.get(k) for k in ("validation", "oos", "chosen_threshold", "oos_frozen_filter")},
                "DISCOVERED_AFTER_MULTIPLE_SEARCHES": True,
            }
        )
    write_json(OUT / "experiment_registry.json", {"rows": registry})

    tr_sorted = sorted(train, key=lambda r: r.get("game_date") or "")
    mid = max(1, len(tr_sorted) // 2)
    early, late = tr_sorted[:mid], tr_sorted[mid:]
    chrono = {
        "early_n": len(early),
        "late_n": len(late),
        "early_q": float(np.mean([r[TARGET] for r in early])) if early else None,
        "late_q": float(np.mean([r[TARGET] for r in late])) if late else None,
        "note": "Chronological TRAIN stability only. DISCOVERED AFTER MULTIPLE SEARCHES.",
    }
    write_json(OUT / "chronological.json", chrono)

    econ_rows = []
    for r in results:
        for split_name in ("validation", "oos"):
            blk = r.get(split_name) or {}
            q = blk.get("q")
            econ_rows.append(
                {
                    "model": r.get("model"),
                    "feature_set": r.get("feature_set"),
                    "split": split_name,
                    "n": blk.get("n"),
                    "q": q,
                    "ev": ev_from_q(q) if q is not None else None,
                    "brier": blk.get("brier"),
                    "auc": blk.get("auc"),
                    "ece": blk.get("ece"),
                    "chosen_threshold": r.get("chosen_threshold"),
                    "oos_frozen_filter": r.get("oos_frozen_filter") if split_name == "oos" else None,
                }
            )
    write_json(
        OUT / "economics.json",
        {
            "ev_unconditional": EV_UNCONDITIONAL,
            "q_unconditional": Q_UNCONDITIONAL,
            "breakeven_q": BREAKEVEN_Q,
            "research_fee_estimate": "NOT production FeeModel",
            "rows": econ_rows,
        },
    )
    write_json(
        OUT / "portfolio.json",
        {
            **overlap,
            "weekly_first80_primary": weekly,
            "expected_weekly_unfiltered": weekly,
            "capital_note": "Research bankroll parameters — not live MLB allocations.",
        },
    )
    write_json(
        OUT / "selection.json",
        {
            "chosen_logistic": None if chosen is None else chosen.get("feature_set"),
            "beats_model0_val_brier_gate": promote,
            "simple_game_state_wins_val_brier": simple_wins,
            "best_k": best_k,
            "portfolio": overlap,
            "weekly_first80_primary": weekly,
            "git": git_commit(),
        },
    )
    print(
        f"analyze primary n={len(rows)} train={len(train)} models={len(results)} "
        f"chosen={None if chosen is None else chosen.get('feature_set')} promote={promote} simple_wins={simple_wins}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
