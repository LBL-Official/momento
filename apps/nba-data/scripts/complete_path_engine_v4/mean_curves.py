#!/usr/bin/env python3
"""TRAIN mean arrival curves and permutation ISD. Descriptive science."""

from __future__ import annotations

import numpy as np

from common import GRID_N, N_PERM, OUT, SEED, read_parquet_rows, utc_now, write_json


def split_mask(rows, name):
    return np.array([r["dataset_split"] == name for r in rows], dtype=bool)


def mean_se(grid, mask):
    X = grid[mask]
    ok = np.isfinite(X).all(axis=1)
    X = X[ok]
    if len(X) == 0:
        return np.full(GRID_N, np.nan), np.full(GRID_N, np.nan), 0
    mu = X.mean(axis=0)
    se = X.std(axis=0, ddof=1) / np.sqrt(len(X)) if len(X) > 1 else np.zeros(GRID_N)
    return mu, se, int(len(X))


def isd(a, b):
    m = np.isfinite(a) & np.isfinite(b)
    if not m.any():
        return None
    return float(np.mean((a[m] - b[m]) ** 2))


def perm_p(grid, y, train, n_perm=N_PERM):
    mu_f, _, _ = mean_se(grid, train & (y == 1))
    mu_s, _, _ = mean_se(grid, train & (y == 0))
    obs = isd(mu_f, mu_s)
    if obs is None:
        return None, None
    rng = np.random.default_rng(SEED)
    idx = np.where(train)[0]
    yt = y[idx].copy()
    ge = 0
    for _ in range(n_perm):
        rng.shuffle(yt)
        yperm = y.copy()
        yperm[idx] = yt
        mf, _, _ = mean_se(grid, train & (yperm == 1))
        ms, _, _ = mean_se(grid, train & (yperm == 0))
        v = isd(mf, ms)
        if v is not None and v >= obs:
            ge += 1
    return obs, (ge + 1) / (n_perm + 1)


def pack(grid, y, train, val, oos, key):
    mf_tr, sf_tr, nf_tr = mean_se(grid, train & (y == 1))
    ms_tr, ss_tr, ns_tr = mean_se(grid, train & (y == 0))
    obs, p = perm_p(grid, y, train)
    out = {
        "train_n_fail": nf_tr,
        "train_n_surv": ns_tr,
        "mean_fail": mf_tr.tolist(),
        "mean_surv": ms_tr.tolist(),
        "se_fail": sf_tr.tolist(),
        "se_surv": ss_tr.tolist(),
        "isd_train": obs,
        "permutation_p_train": p,
        "n_perm": N_PERM,
        "val_isd_heldout_means": isd(
            mean_se(grid, val & (y == 1))[0], mean_se(grid, val & (y == 0))[0]
        ),
        "oos_isd_heldout_means": isd(
            mean_se(grid, oos & (y == 1))[0], mean_se(grid, oos & (y == 0))[0]
        ),
        "max_abs_mean_gap_train": None
        if not np.isfinite(mf_tr).all()
        else float(np.max(np.abs(mf_tr - ms_tr))),
    }
    # pointwise TRAIN overlap of mean±1.96se
    overlap = []
    for j in range(GRID_N):
        lo_f, hi_f = mf_tr[j] - 1.96 * sf_tr[j], mf_tr[j] + 1.96 * sf_tr[j]
        lo_s, hi_s = ms_tr[j] - 1.96 * ss_tr[j], ms_tr[j] + 1.96 * ss_tr[j]
        overlap.append(not (hi_f < lo_s or hi_s < lo_f))
    out["n_grid_nonoverlap_95"] = int(sum(not x for x in overlap))
    out["fraction_grid_overlap_95"] = float(np.mean(overlap))
    return out


def main() -> int:
    rows = read_parquet_rows(OUT / "path_functionals.parquet")
    z = np.load(OUT / "arrival_curves.npz")
    y = z["y"]
    train = split_mask(rows, "TRAIN")
    val = split_mask(rows, "VALIDATION")
    oos = split_mask(rows, "OOS")
    report = {
        "written_utc": utc_now(),
        "grid_n": GRID_N,
        "u": np.linspace(0, 1, GRID_N).tolist(),
        "full_window": pack(z["full_grid"], y, train, val, oos, "full"),
        "from50": pack(z["from50_grid"], y, train, val, oos, "from50"),
        "score": pack(z["score_grid"], y, train, val, oos, "score"),
        "note": "Permutation p is TRAIN-only. Overlapping mean curves are a negative location-shift result, not a bug.",
    }
    write_json(OUT / "mean_curves.json", report)
    fw = report["full_window"]
    print(
        f"mean_curves ISD={fw['isd_train']} p={fw['permutation_p_train']} "
        f"nonoverlap={fw['n_grid_nonoverlap_95']}/32"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
