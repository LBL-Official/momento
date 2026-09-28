#!/usr/bin/env python3
"""VALIDATION chooses. OOS is one frozen pass."""

from __future__ import annotations

import json
import sys

import numpy as np

from common import (
    BRIER_IMPROVE,
    ECE_TOLERANCE,
    OUT,
    REJECT_Q,
    ev_from_q,
    metrics_block,
    read_parquet_rows,
    utc_now,
    wilson,
    write_json,
)

NAMES = {
    "H0": "p0",
    "HS": "p_state",
    "H2_l2_mean": "p_l2",
    "H3_dtw": "p_dtw",
    "H4_functionals": "p_func",
    "H5_pca": "p_pca",
}


def split_idx(rows, name):
    return np.array([r["dataset_split"] == name for r in rows])


def bucket_sep(y, p, n_min=40):
    """High vs low predicted-q halves if n allows; else tertiles."""
    y = np.asarray(y)
    p = np.asarray(p)
    m = np.isfinite(p)
    y, p = y[m], p[m]
    if len(y) < n_min * 2:
        return None
    thr = float(np.median(p))
    hi = p >= thr
    lo = ~hi
    if hi.sum() < n_min or lo.sum() < n_min:
        return None
    qh = float(y[hi].mean())
    ql = float(y[lo].mean())
    ph, loh, hih = wilson(int(y[hi].sum()), int(hi.sum()))
    pl, lol, hil = wilson(int(y[lo].sum()), int(lo.sum()))
    disjoint = hih is not None and lol is not None and (hih < lol or hil < loh)
    return {
        "n_high": int(hi.sum()),
        "n_low": int(lo.sum()),
        "q_high": qh,
        "q_low": ql,
        "delta_q": qh - ql,
        "wilson_disjoint": bool(disjoint),
        "sep_8pp": abs(qh - ql) >= 0.08,
    }


def reject_ev(y, p, thresh):
    keep = p < thresh
    n = int(keep.sum())
    if n < 40:
        return None
    q = float(y[keep].mean())
    return {"n_kept": n, "q": q, "ev": ev_from_q(q), "accept_rate": n / len(y)}


def main() -> int:
    rows = read_parquet_rows(OUT / "path_functionals.parquet")
    pred = np.load(OUT / "predictions_cache.npz")
    z = np.load(OUT / "arrival_curves.npz")
    y = z["y"].astype(float)
    val = split_idx(rows, "VALIDATION")
    oos = split_idx(rows, "OOS")
    tr = split_idx(rows, "TRAIN")
    val_m = {}
    for name, key in NAMES.items():
        val_m[name] = metrics_block(y[val], pred[key][val])
        val_m[name]["buckets"] = bucket_sep(y[val], pred[key][val])
    b0 = val_m["H0"]["brier"]
    bs = val_m["HS"]["brier"]
    e0 = val_m["H0"]["ece"]
    path_names = ["H2_l2_mean", "H3_dtw", "H4_functionals", "H5_pca"]
    best = "H0"
    best_b = b0
    gates = {}
    for name in ["HS"] + path_names:
        b = val_m[name]["brier"]
        if b is not None and b < best_b:
            best, best_b = name, b
    # Path promotion requires beating H0 and HS
    promo = None
    for name in path_names:
        b = val_m[name]["brier"]
        e = val_m[name]["ece"]
        buck = val_m[name]["buckets"] or {}
        ok = (
            b is not None
            and b0 is not None
            and b <= BRIER_IMPROVE * b0
            and bs is not None
            and b <= bs - 0.001
            and e is not None
            and e0 is not None
            and e <= e0 + ECE_TOLERANCE
            and (buck.get("sep_8pp") or buck.get("wilson_disjoint"))
        )
        gates[name] = {
            "brier_vs_h0": b,
            "beats_h0_95": bool(b is not None and b0 is not None and b <= BRIER_IMPROVE * b0),
            "beats_hs": bool(b is not None and bs is not None and b <= bs - 0.001),
            "ece_ok": bool(e is not None and e0 is not None and e <= e0 + ECE_TOLERANCE),
            "bucket": buck,
            "promote": ok,
        }
        if ok and (promo is None or b < val_m[promo]["brier"]):
            promo = name
    selected = promo if promo else ("HS" if best == "HS" else "H0")
    if promo:
        selected = promo
    elif val_m["HS"]["brier"] is not None and val_m["HS"]["brier"] < b0:
        selected = "HS"
    else:
        selected = "H0"

    p_sel = pred[NAMES[selected]]
    reject = {}
    for t in REJECT_Q:
        reject[str(t)] = {
            "val": reject_ev(y[val], p_sel[val], t),
            "oos": reject_ev(y[oos], p_sel[oos], t),
        }
    hold_val = ev_from_q(float(y[val].mean()))
    chosen_thr = None
    for t in REJECT_Q:
        rv = reject[str(t)]["val"]
        if rv and rv["ev"] is not None and hold_val is not None and rv["ev"] >= hold_val:
            chosen_thr = t
            break

    oos_m = {name: metrics_block(y[oos], pred[key][oos]) for name, key in NAMES.items()}
    write_json(
        OUT / "model_results.json",
        {
            "written_utc": utc_now(),
            "selected": selected,
            "promoted_path_model": promo,
            "gates": gates,
            "train": {name: metrics_block(y[tr], pred[key][tr]) for name, key in NAMES.items()},
            "validation": val_m,
            "oos": oos_m,
            "oos_selected": metrics_block(y[oos], p_sel[oos]),
            "reject_rules": reject,
            "val_chosen_reject_threshold": chosen_thr,
            "val_hold_ev": hold_val,
            "oos_hold_ev": ev_from_q(float(y[oos].mean())),
            "oos_pass": "SINGLE_FROZEN_PASS",
        },
    )
    print(f"evaluate selected={selected} promo={promo} VAL brier={val_m[selected]['brier']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
