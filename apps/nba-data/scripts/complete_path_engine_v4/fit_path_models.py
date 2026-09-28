#!/usr/bin/env python3
"""Fit H0, HS, H2–H5 on TRAIN. No OOS retune."""

from __future__ import annotations

import json
import sys

import numpy as np

from common import (
    GRID_N,
    L2_LAMBDA,
    OUT,
    Q_UNCONDITIONAL,
    add_intercept,
    dtw_abs,
    downsample,
    fit_l2,
    impute_scale,
    metrics_block,
    read_parquet_rows,
    sigmoid,
    utc_now,
    write_json,
)

FUNC_COLS = [
    "duration_minutes",
    "total_variation_cents",
    "path_efficiency",
    "n_reversals",
    "frac_below_50",
    "frac_below_60",
    "frac_below_70",
    "minutes_from_50_to_80",
    "path_vol_proxy_cents",
    "score_tv",
    "n_lead_changes_pre80",
    "net_score_change_pre80",
]
STATE_COLS = [
    "state_entry_bid_cents",
    "state_spread_cents",
    "state_minutes_to_close",
    "state_vol_5m_cents",
    "score_diff_at_80",
]


def colmat(rows, names):
    X = np.full((len(rows), len(names)), np.nan)
    for j, name in enumerate(names):
        for i, r in enumerate(rows):
            v = r.get(name)
            if v is not None:
                try:
                    X[i, j] = float(v)
                except (TypeError, ValueError):
                    pass
    return X


def split_idx(rows, name):
    return np.array([r["dataset_split"] == name for r in rows])


def l2_to_mean(grid, mu):
    out = np.full(len(grid), np.nan)
    for i, row in enumerate(grid):
        m = np.isfinite(row) & np.isfinite(mu)
        if m.sum() < GRID_N // 2:
            continue
        out[i] = float(np.sqrt(np.mean((row[m] - mu[m]) ** 2)))
    return out


def main() -> int:
    rows = read_parquet_rows(OUT / "path_functionals.parquet")
    z = np.load(OUT / "arrival_curves.npz")
    y = z["y"].astype(float)
    grid = z["full_grid"]
    means = json.loads((OUT / "mean_curves.json").read_text())
    mu_f = np.array(means["full_window"]["mean_fail"], dtype=float)
    mu_s = np.array(means["full_window"]["mean_surv"], dtype=float)
    tr = split_idx(rows, "TRAIN")
    p0 = np.full(len(y), Q_UNCONDITIONAL)

    Xs, med_s, mean_s, std_s = impute_scale(colmat(rows, STATE_COLS)[tr], fit=True)
    ws = fit_l2(add_intercept(Xs), y[tr])
    Xsa, _, _, _ = impute_scale(colmat(rows, STATE_COLS), medians=med_s, means=mean_s, stds=std_s)
    ps = sigmoid(add_intercept(Xsa) @ ws)

    Xf, med_f, mean_f, std_f = impute_scale(colmat(rows, FUNC_COLS)[tr], fit=True)
    wf = fit_l2(add_intercept(Xf), y[tr])
    Xfa, _, _, _ = impute_scale(colmat(rows, FUNC_COLS), medians=med_f, means=mean_f, stds=std_f)
    pf = sigmoid(add_intercept(Xfa) @ wf)

    d_fail = l2_to_mean(grid, mu_f)
    d_surv = l2_to_mean(grid, mu_s)
    dX = np.column_stack([d_fail, d_surv, d_surv - d_fail])
    Xd, med_d, mean_d, std_d = impute_scale(dX[tr], fit=True)
    wd = fit_l2(add_intercept(Xd), y[tr])
    Xda, _, _, _ = impute_scale(dX, medians=med_d, means=mean_d, stds=std_d)
    p_l2 = sigmoid(add_intercept(Xda) @ wd)

    # PCA on TRAIN complete grids
    G = grid[tr].copy()
    gmean = np.nanmean(G, axis=0)
    for j in range(GRID_N):
        miss = ~np.isfinite(G[:, j])
        G[miss, j] = gmean[j]
    G = G - gmean
    _, s, Vt = np.linalg.svd(G, full_matrices=False)
    kpc = 5
    pcs_tr = G @ Vt[:kpc].T
    Xp, med_p, mean_p, std_p = impute_scale(pcs_tr, fit=True)
    wp = fit_l2(add_intercept(Xp), y[tr])
    Gall = grid.copy()
    for j in range(GRID_N):
        miss = ~np.isfinite(Gall[:, j])
        Gall[miss, j] = gmean[j]
    Gall = Gall - gmean
    pcs_all = Gall @ Vt[:kpc].T
    Xpa, _, _, _ = impute_scale(pcs_all, medians=med_p, means=mean_p, stds=std_p)
    p_pca = sigmoid(add_intercept(Xpa) @ wp)

    fail_i = np.where(tr & (y == 1) & np.isfinite(grid).all(axis=1))[0]
    surv_i = np.where(tr & (y == 0) & np.isfinite(grid).all(axis=1))[0]
    d_f = l2_to_mean(grid, mu_f)
    d_s = l2_to_mean(grid, mu_s)
    med_fail = fail_i[int(np.nanargmin(d_f[fail_i]))] if len(fail_i) else None
    med_surv = surv_i[int(np.nanargmin(d_s[surv_i]))] if len(surv_i) else None
    raw = np.load(OUT / "raw_full_paths.npy", allow_pickle=True)
    rf = downsample(raw[med_fail]) if med_fail is not None and len(raw[med_fail]) else None
    rs = downsample(raw[med_surv]) if med_surv is not None and len(raw[med_surv]) else None
    dtw_f = np.full(len(y), np.nan)
    dtw_s = np.full(len(y), np.nan)
    for i in range(len(y)):
        seq = downsample(raw[i]) if len(raw[i]) else None
        if seq is None or rf is None or rs is None or len(seq) < 2:
            continue
        dtw_f[i] = dtw_abs(seq, rf)
        dtw_s[i] = dtw_abs(seq, rs)
    dtwX = np.column_stack([dtw_f, dtw_s, dtw_s - dtw_f])
    Xt, med_t, mean_t, std_t = impute_scale(dtwX[tr], fit=True)
    wt = fit_l2(add_intercept(Xt), y[tr])
    Xta, _, _, _ = impute_scale(dtwX, medians=med_t, means=mean_t, stds=std_t)
    p_dtw = sigmoid(add_intercept(Xta) @ wt)

    np.savez(
        OUT / "predictions_cache.npz",
        p0=p0,
        p_state=ps,
        p_func=pf,
        p_l2=p_l2,
        p_pca=p_pca,
        p_dtw=p_dtw,
        d_fail=d_fail,
        d_surv=d_surv,
    )
    write_json(
        OUT / "model_fit.json",
        {
            "written_utc": utc_now(),
            "train": {
                "H0": metrics_block(y[tr], p0[tr]),
                "HS": metrics_block(y[tr], ps[tr]),
                "H2_l2_mean": metrics_block(y[tr], p_l2[tr]),
                "H3_dtw": metrics_block(y[tr], p_dtw[tr]),
                "H4_functionals": metrics_block(y[tr], pf[tr]),
                "H5_pca": metrics_block(y[tr], p_pca[tr]),
            },
            "medoid_fail_index": None if med_fail is None else int(med_fail),
            "medoid_surv_index": None if med_surv is None else int(med_surv),
            "pca_singular_values": s[:kpc].tolist(),
            "l2_lambda": L2_LAMBDA,
        },
    )
    print("fit TRAIN brier", {k: v["brier"] for k, v in json.loads((OUT / "model_fit.json").read_text())["train"].items()})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
