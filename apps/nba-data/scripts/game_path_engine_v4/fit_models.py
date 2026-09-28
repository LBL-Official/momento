#!/usr/bin/env python3
"""Models 0–4 on S_tau80. VALIDATION chooses. OOS is one frozen pass."""

from __future__ import annotations

import numpy as np

from common import (
    BRIER_IMPROVE,
    ECE_TOLERANCE,
    MODEL2_COLS,
    MODEL3_INTERACTIONS,
    MODELS,
    OBS,
    REP,
    add_intercept,
    brier,
    col_array,
    depth2_boost,
    ece,
    fit_elastic,
    fit_l2,
    impute_scale,
    metrics_block,
    predict_boost,
    read_parquet_rows,
    sigmoid,
    utc_now,
    write_json,
    write_parquet,
)


def split_mask(splits, name):
    return np.array([s == name for s in splits])


def design(rows, cols):
    return np.column_stack([col_array(rows, c) for c in cols])


def finite_diff_grad(w, medians, means, stds, cols, X_scaled_row, step=0.25):
    """Δq for +1 raw unit of each coordinate, others at TRAIN median."""
    p0 = float(sigmoid(X_scaled_row @ w))
    out = []
    for j, name in enumerate(cols):
        raw = np.array(medians, dtype=float)
        raw[j] = raw[j] + step
        z = (raw - means) / stds
        z = np.concatenate([[1.0], z])
        p1 = float(sigmoid(z @ w))
        out.append(
            {
                "coordinate": name,
                "step_raw": step,
                "dq": p1 - p0,
                "dq_per_unit": (p1 - p0) / step,
            }
        )
    return p0, out


def main() -> int:
    rows = read_parquet_rows(OBS / "first80_game_state.parquet")
    y = np.array([r["Y_40_CLOSE"] for r in rows], dtype=float)
    splits = [r["dataset_split"] for r in rows]
    tr = split_mask(splits, "TRAIN")
    va = split_mask(splits, "VALIDATION")
    oo = split_mask(splits, "OOS")
    q_tr = float(y[tr].mean())
    p0 = np.full(len(y), q_tr)

    X2_raw = design(rows, MODEL2_COLS)
    X2_tr, med, mean, std = impute_scale(X2_raw[tr], fit=True)
    X2_all, _, _, _ = impute_scale(X2_raw, medians=med, means=mean, stds=std)
    w2 = fit_l2(add_intercept(X2_tr), y[tr])
    p2 = sigmoid(add_intercept(X2_all) @ w2)
    w2e = fit_elastic(add_intercept(X2_tr), y[tr])
    p2e = sigmoid(add_intercept(X2_all) @ w2e)

    X3_raw = design(rows, MODEL2_COLS + MODEL3_INTERACTIONS)
    X3_tr, med3, mean3, std3 = impute_scale(X3_raw[tr], fit=True)
    X3_all, _, _, _ = impute_scale(X3_raw, medians=med3, means=mean3, stds=std3)
    w3 = fit_l2(add_intercept(X3_tr), y[tr])
    p3 = sigmoid(add_intercept(X3_all) @ w3)

    pack = {
        "model0": metrics_block(y[va], p0[va]),
        "model2_l2": metrics_block(y[va], p2[va]),
        "model2_elastic": metrics_block(y[va], p2e[va]),
        "model3_interactions": metrics_block(y[va], p3[va]),
    }
    val_brier = {k: pack[k]["brier"] for k in pack}
    best = min(val_brier, key=lambda k: val_brier[k] if val_brier[k] is not None else 9e9)
    m0b = pack["model0"]["brier"]
    improve_src = min(
        x
        for x in (
            pack["model2_l2"]["brier"],
            pack["model2_elastic"]["brier"],
            pack["model3_interactions"]["brier"],
        )
        if x is not None
    )
    gbm_allowed = improve_src <= BRIER_IMPROVE * m0b
    p4 = None
    gbm_model = None
    if gbm_allowed:
        gbm_model = depth2_boost(X2_tr, y[tr], n_trees=15, lr=0.08, min_leaf=25)
        p4 = predict_boost(gbm_model, X2_all)
        pack["model4_gbm"] = metrics_block(y[va], p4[va])
        val_brier["model4_gbm"] = pack["model4_gbm"]["brier"]
        if pack["model4_gbm"]["brier"] < val_brier[best]:
            best = "model4_gbm"
        write_json(
            MODELS / "model4_nonlinear" / "params.json",
            {"trees": gbm_model["trees"], "init": gbm_model["init"], "skipped": False},
        )
    else:
        write_json(
            MODELS / "model4_nonlinear" / "params.json",
            {
                "skipped": True,
                "reason": "Model 2/3 did not beat 0.95 × Model 0 Brier on VALIDATION",
            },
        )

    pred = {"model0": p0, "model2_l2": p2, "model2_elastic": p2e, "model3_interactions": p3}
    if p4 is not None:
        pred["model4_gbm"] = p4
    p_sel = pred[best]
    ece0 = pack["model0"]["ece"]
    ece_sel = ece(y[va], p_sel[va])
    gates = {
        "val_brier": val_brier,
        "gbm_allowed": gbm_allowed,
        "ece_model0": ece0,
        "ece_selected": ece_sel,
        "ece_ok": ece_sel is None or ece0 is None or ece_sel <= (ece0 + ECE_TOLERANCE),
        "brier_improve_vs_m0": val_brier[best] <= BRIER_IMPROVE * m0b,
        "selected_on_validation": best,
    }

    def pack_split(mask):
        out = {k: metrics_block(y[mask], pred[k][mask]) for k in pred}
        return out

    median_row = np.concatenate([[1.0], np.zeros(len(MODEL2_COLS))])
    q_at_med, grad = finite_diff_grad(w2, med, mean, std, MODEL2_COLS, median_row, step=1.0)

    pred_rows = []
    for i, r in enumerate(rows):
        rec = {
            "trade_id": r["trade_id"],
            "dataset_split": r["dataset_split"],
            "Y_40_CLOSE": int(r["Y_40_CLOSE"]),
            "p_model0": float(p0[i]),
            "p_model2_l2": float(p2[i]),
            "p_model2_elastic": float(p2e[i]),
            "p_model3": float(p3[i]),
            "p_selected": float(p_sel[i]),
            "selected_model": best,
        }
        if p4 is not None:
            rec["p_model4_gbm"] = float(p4[i])
        pred_rows.append(rec)
    write_parquet(MODELS / "predictions.parquet", pred_rows)

    write_json(
        MODELS / "model0_baseline" / "results.json",
        {"written_utc": utc_now(), "q_train": q_tr, "metrics_val": pack["model0"]},
    )
    write_json(
        MODELS / "model2_regularized" / "results.json",
        {
            "written_utc": utc_now(),
            "features": MODEL2_COLS,
            "w_l2": w2.tolist(),
            "w_elastic": w2e.tolist(),
            "medians": med.tolist(),
            "means": mean.tolist(),
            "stds": std.tolist(),
            "val": {"l2": pack["model2_l2"], "elastic": pack["model2_elastic"]},
        },
    )
    write_json(
        MODELS / "model3_interactions" / "results.json",
        {
            "written_utc": utc_now(),
            "features": MODEL2_COLS + MODEL3_INTERACTIONS,
            "w_l2": w3.tolist(),
            "val": pack["model3_interactions"],
            "hessian_proxy": "preregistered interaction coefficients; not a numerical Hessian",
        },
    )
    payload = {
        "written_utc": utc_now(),
        "target": "Y_40_CLOSE",
        "selected_model": best,
        "gbm_built": p4 is not None,
        "gates": gates,
        "train": pack_split(tr),
        "validation": pack,
        "oos": pack_split(oo),
        "validation_selected": metrics_block(y[va], p_sel[va]),
        "oos_selected": metrics_block(y[oo], p_sel[oo]),
        "oos_pass": "SINGLE_FROZEN_PASS",
        "features_model2": MODEL2_COLS,
        "barrier_risk_gradient_at_train_median": {
            "q_hat": q_at_med,
            "partials_per_raw_unit": grad,
            "method": "local_finite_difference_on_l2_logistic",
        },
    }
    write_json(MODELS / "model_results.json", payload)
    write_json(REP / "validation_results.json", {"validation": pack, "selected": best, "gates": gates})
    write_json(REP / "oos_results.json", {"oos": pack_split(oo), "selected": best, "oos_selected": payload["oos_selected"]})
    print(
        f"models selected={best} VAL brier={pack[best]['brier'] if best in pack else val_brier[best]} "
        f"OOS brier={payload['oos_selected']['brier']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
