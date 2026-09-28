"""Fit PCA/KNN for the NBA 2Q/3Q 78/67 book."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import numpy as np
import pandas as pd

from roller.austin.analyze import buckets, interactions
from roller.austin.fees import fee_block
from roller.austin.mathutil import pearson, spearman
from roller.austin.pca import fit_pca
from roller.austin.sizing import all_bands
from roller.austin_first78.config import CFG, EV_DEFINITION
from roller.austin_first78.dataset import build_dataset
from roller.austin_first78.paths import (
    audit_path,
    calibration_path,
    hedge_path,
    integrity_audit_path,
    sizing_path,
    summary_path,
    walkforward_path,
)
from roller.austin_first78.store import save_pca_model, write_json
from roller.austin_first78.walkforward import run_walkforward

TARGETS = (
    "pnl_hold_after_t",
    "final_pnl_taker_7867_cents",
    "won",
    "t67",
    "hit_67_after",
)


def _correlations(snapshots: pd.DataFrame) -> list[dict[str, Any]]:
    names = list(CFG.default_knn)
    path = snapshots[snapshots["kind"] != "entry"]
    entry = snapshots[snapshots["kind"] == "entry"]
    travel = {"price_travel", "score_travel", "score_differential_travel", "time_since_entry", "current_price_cents"}
    rows = []
    for name in names:
        work = path if name in travel else entry
        if name not in work.columns:
            continue
        x = pd.to_numeric(work[name], errors="coerce").to_numpy()
        for target in TARGETS:
            if target not in work.columns:
                continue
            y = pd.to_numeric(work[target], errors="coerce").to_numpy()
            mask = np.isfinite(x) & np.isfinite(y)
            status = "VALUE"
            if int(mask.sum()) < 3 or float(np.nanstd(x[mask])) <= 1e-12 or float(np.nanstd(y[mask])) <= 1e-12:
                status = "INSUFFICIENT_SAMPLE"
            rows.append(
                {
                    "feature": name,
                    "target": target,
                    "pearson": None if status != "VALUE" else pearson(x, y),
                    "spearman": None if status != "VALUE" else spearman(x, y),
                    "sample_count": int(mask.sum()),
                    "status": status,
                    "note": "CORRELATION ≠ CAUSATION",
                }
            )
    return rows


def run_build() -> dict[str, Any]:
    data = build_dataset()
    snaps = data["snapshots"]
    names = list(CFG.default_knn)
    model = fit_pca(snaps, names, k=CFG.pca_k, cfg=CFG)
    save_pca_model(model)
    wf = run_walkforward(snaps)
    points = []
    scores = model["scores"]
    for i, idx in enumerate(model["index"]):
        rec = snaps.loc[idx]
        points.append(
            {
                "snapshot_id": rec["snapshot_id"],
                "trade_id": rec["trade_id"],
                "kind": rec["kind"],
                "pc1": float(scores[i, 0]) if scores.shape[1] else 0.0,
                "pc2": float(scores[i, 1]) if scores.shape[1] > 1 else 0.0,
                "settlement": rec.get("settlement"),
                "quarter": rec.get("quarter"),
                "entry_price_cents": rec.get("entry_price_cents"),
                "ticker": rec.get("ticker"),
            }
        )
    hedge = data["hedge_summary"]
    coverage = data["coverage"]
    write_json(hedge_path(), hedge)
    write_json(walkforward_path(), wf)
    write_json(calibration_path(), wf["calibration"])
    write_json(
        sizing_path(),
        {
            "bands": all_bands(cfg=CFG),
            "calibration": wf["calibration"],
            "bankroll": wf["bankroll"],
            "starting_bankroll_cents": CFG.starting_bankroll_cents,
            "ev_definition": EV_DEFINITION,
            "role": "ENTRY_SIZING_REFERENCE",
            "decision": None,
        },
    )
    integrity = {
        "dataset_version": CFG.dataset_version,
        "n_trades": coverage["n_trades"],
        "n_is_604": coverage["n_trades"] == 604,
        "knn_includes_distance_from_78": "distance_from_78" in names,
        "knn_includes_distance_from_80": "distance_from_80" in names,
        "buy_skip": False,
        "live_execution": False,
        "live_feed": "UNAVAILABLE",
    }
    write_json(integrity_audit_path(), integrity)
    summary = {
        "model_version": CFG.model_version,
        "dataset_version": CFG.dataset_version,
        "feature_schema_version": CFG.feature_schema_version,
        "pca_version": CFG.pca_version,
        "knn_config": CFG.knn_config,
        "built_at": datetime.now(timezone.utc).isoformat(),
        "data_mode": CFG.data_mode,
        "live_feed": CFG.live_feed,
        "live_execution": False,
        "submits": False,
        "sport": "NBA",
        "market": "CHOOSIN TEXAS",
        "period": "2Q + 3Q",
        "rule": "FIRST78_67",
        "coverage": coverage,
        "pca": {
            "k": model["k"],
            "n": model["n"],
            "explained": model["explained"],
            "cumulative": model["cumulative"],
            "loadings": model["loadings"],
            "names": model["names"],
        },
        "walkforward": {
            "train_n": wf["train_n"],
            "validation_n": wf["validation_n"],
            "oos_n": wf["oos_n"],
            "train_months": wf["train_months"],
            "validation_months": wf["validation_months"],
            "oos_months": wf["oos_months"],
            "calibration": wf["calibration"],
            "folds": wf["folds"],
        },
        "correlations": _correlations(snaps),
        "buckets": buckets(snaps),
        "interactions": interactions(snaps),
        "ablation": {"sets": ["full_default"], "default": names, "note": "This fit uses distance_from_78."},
        "model_compare": [],
        "hedge": hedge,
        "fees": fee_block(),
        "pca_points": points[:800],
        "integrity": integrity,
        "note": "NBA 2Q/3Q 78/67 query desk. Candle path is not a fill. Live feed UNAVAILABLE.",
    }
    write_json(summary_path(), summary)
    write_json(
        audit_path(),
        {
            "dataset": CFG.dataset_version,
            "filters": {"sport": "NBA", "slice": ["Q2", "Q3"], "entry_cents": 78, "stop_cents": 67},
            "N": coverage,
            "default_knn": names,
            "missing_data_policy": "UNAVAILABLE never filled with 0",
            "train_period": wf["train_months"],
            "validation_period": wf["validation_months"],
            "oos_period": wf["oos_months"],
            "pca_dimensions": model["k"],
            "k": CFG.k_default,
            "distance_metric": "euclidean_pca",
            "hedge_assumptions": {"triggers": [69, 68], "hedge_price": 67, "fill_status": "FILL_UNAVAILABLE"},
            "sizing_thresholds": wf["calibration"],
            "integrity": integrity,
            "ev_definition": EV_DEFINITION,
            "execution_status": "DISABLED",
            "buy_skip": False,
        },
    )
    return summary
