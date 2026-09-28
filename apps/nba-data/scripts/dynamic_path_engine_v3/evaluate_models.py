#!/usr/bin/env python3
"""VALIDATION chooses. OOS is one frozen pass. Do not retune."""

from __future__ import annotations

import sys

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq

from common import (
    BRIER_IMPROVE,
    ECE_TOLERANCE,
    OUT,
    ece,
    sigmoid,
    utc_now,
    write_json,
)
from lib import (
    MODEL2_COLS,
    add_intercept,
    clustered_brier,
    depth2_boost,
    impute_scale,
    load_panel,
    metrics_block,
    predict_boost,
    split_mask,
)


def cal_bins(y, p, n_bins=8):
    y = np.asarray(y, dtype=float)
    p = np.asarray(p, dtype=float)
    edges = np.quantile(p, np.linspace(0, 1, n_bins + 1))
    edges[0] = 0.0
    edges[-1] = 1.0
    out = []
    for i in range(n_bins):
        lo, hi = edges[i], edges[i + 1]
        m = (p >= lo) & (p <= hi) if i == n_bins - 1 else (p >= lo) & (p < hi)
        if int(m.sum()) == 0:
            continue
        out.append(
            {
                "lo": float(lo),
                "hi": float(hi),
                "n": int(m.sum()),
                "mean_p": float(p[m].mean()),
                "mean_y": float(y[m].mean()),
            }
        )
    return out


def main() -> int:
    d = load_panel()
    y = d["y"]
    haz = np.load(OUT / "models" / "logistic" / "predictions_cache.npz")
    surv = np.load(OUT / "models" / "discrete_hazard" / "predictions_cache.npz")
    p0, p0b, p2 = haz["p0"], haz["p0b"], haz["p2"]
    p3 = surv["p3"]
    val = split_mask(d["split"], "VALIDATION")
    oos = split_mask(d["split"], "OOS")
    tr = split_mask(d["split"], "TRAIN")

    def pack(mask):
        ids = [d["trade_id"][i] for i in np.where(mask)[0]]
        return {
            "model0": metrics_block(y[mask], p0[mask], ids),
            "model0b": metrics_block(y[mask], p0b[mask], ids),
            "model2": metrics_block(y[mask], p2[mask], ids),
            "model3": metrics_block(y[mask], p3[mask], ids),
        }

    val_m = pack(val)
    # Select among 0/0b/2/3 on clustered Brier (lower better)
    cand = ["model0", "model0b", "model2", "model3"]
    val_brier = {k: val_m[k]["clustered_brier"] for k in cand}
    best = min(val_brier, key=lambda k: val_brier[k] if val_brier[k] is not None else 9e9)
    m0b = val_m["model0"]["clustered_brier"]
    ece0 = val_m["model0"]["ece"]
    gates = {}
    p_gbm = None
    gbm_built = False
    # GBM only if 2 or 3 beats 0.95 × model0 clustered Brier
    cands_b = [
        x
        for x in (val_m["model2"]["clustered_brier"], val_m["model3"]["clustered_brier"])
        if x is not None
    ]
    improve_src = min(cands_b) if cands_b else None
    gbm_allowed = improve_src is not None and m0b is not None and improve_src <= BRIER_IMPROVE * m0b
    gates["gbm_allowed"] = gbm_allowed
    gates["val_brier"] = val_brier
    if gbm_allowed:
        rng = np.random.default_rng(42)
        tr_idx = np.where(tr)[0]
        by = {}
        for i in tr_idx:
            by.setdefault(d["trade_id"][i], []).append(i)
        one = np.array([rng.choice(v) for v in by.values()])
        Xs, med, mean, std = impute_scale(d["X"][one], fit=True)
        model = depth2_boost(Xs, y[one].astype(float), n_trees=15, lr=0.08, min_leaf=25)
        Xall, _, _, _ = impute_scale(d["X"], medians=med, means=mean, stds=std)
        p_gbm = predict_boost(model, Xall)
        ids_val = [d["trade_id"][i] for i in np.where(val)[0]]
        val_m["model4_gbm"] = metrics_block(y[val], p_gbm[val], ids_val)
        gates["gbm_val_clustered_brier"] = val_m["model4_gbm"]["clustered_brier"]
        if val_m["model4_gbm"]["clustered_brier"] < val_brier[best]:
            best = "model4_gbm"
        (OUT / "models" / "gbm").mkdir(parents=True, exist_ok=True)
        write_json(OUT / "models" / "gbm" / "params.json", {"trees": model["trees"], "init": model["init"]})
        gbm_built = True
    else:
        (OUT / "models" / "gbm").mkdir(parents=True, exist_ok=True)
        write_json(
            OUT / "models" / "gbm" / "params.json",
            {"skipped": True, "reason": "Model 2/3 did not beat 0.95 × Model 0 clustered Brier on VAL"},
        )

    pred = {"model0": p0, "model0b": p0b, "model2": p2, "model3": p3}
    if p_gbm is not None:
        pred["model4_gbm"] = p_gbm
    p_sel = pred[best]

    # ECE gate vs model0
    ece_sel = ece(y[val], p_sel[val])
    gates["ece_model0"] = ece0
    gates["ece_selected"] = ece_sel
    gates["ece_ok"] = ece_sel is None or ece0 is None or ece_sel <= (ece0 + ECE_TOLERANCE)
    gates["brier_improve_vs_m0"] = None if m0b is None else val_brier.get(best, 9) <= BRIER_IMPROVE * m0b
    gates["selected_on_validation"] = best
    # If selected is model0, research warning is baseline (no dynamic lift)
    oos_m = pack(oos)
    if gbm_built and p_gbm is not None:
        ids_o = [d["trade_id"][i] for i in np.where(oos)[0]]
        oos_m["model4_gbm"] = metrics_block(y[oos], p_gbm[oos], ids_o)

    ids_sel_oos = [d["trade_id"][i] for i in np.where(oos)[0]]
    oos_selected = metrics_block(y[oos], p_sel[oos], ids_sel_oos)
    val_selected = metrics_block(y[val], p_sel[val], [d["trade_id"][i] for i in np.where(val)[0]])

    table = pa.table(
        {
            "trade_id": d["trade_id"],
            "state_timestamp": d["state_ts"].astype(np.int64),
            "dataset_split": d["split"],
            "H_40_5M": y.astype(np.int64),
            "p_model0": p0,
            "p_model0b": p0b,
            "p_model2": p2,
            "p_model3": p3,
            "p_selected": p_sel,
            "selected_model": [best] * d["n"],
        }
    )
    pq.write_table(table, OUT / "predictions.parquet")

    write_json(
        OUT / "model_results.json",
        {
            "written_utc": utc_now(),
            "target": "H_40_5M",
            "selected_model": best,
            "gbm_built": gbm_built,
            "gates": gates,
            "train": pack(tr),
            "validation": val_m,
            "oos": oos_m,
            "validation_selected": val_selected,
            "oos_selected": oos_selected,
            "calibration_val_selected": cal_bins(y[val], p_sel[val]),
            "calibration_oos_selected": cal_bins(y[oos], p_sel[oos]),
            "oos_pass": "SINGLE_FROZEN_PASS",
            "features_model2": MODEL2_COLS,
        },
    )
    print(f"evaluate selected={best} VAL clustered_brier={val_selected['clustered_brier']} OOS={oos_selected['clustered_brier']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
