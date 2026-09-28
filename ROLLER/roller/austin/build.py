"""Build Austin artifacts from the locked 604 book + warehouse paths."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from roller.austin.analyze import ablation_note, buckets, correlations, interactions
from roller.austin.config import DEFAULT
from roller.austin.dataset import build_dataset
from roller.austin.fees import fee_block
from roller.austin.leakage import assert_registry_clean
from roller.austin.integrity import run_integrity
from roller.austin.paths import (
    audit_path,
    calibration_path,
    hedge_path,
    integrity_audit_path,
    sizing_path,
    summary_path,
    walkforward_path,
)
from roller.austin.pca import fit_pca
from roller.austin.registry import load_registry
from roller.austin.store import save_pca_model, write_json
from roller.austin.walkforward import compare_models, run_walkforward
from roller.austin.sizing import all_bands


def run_build() -> dict[str, Any]:
    assert_registry_clean()
    registry = load_registry()
    data = build_dataset()
    snaps = data["snapshots"]
    names = list(registry["default_knn"])
    model = fit_pca(snaps, names, k=DEFAULT.pca_k)
    save_pca_model(model)
    wf = run_walkforward(snaps)
    models = compare_models(snaps)
    corr = correlations(snaps)
    buck = buckets(snaps)
    inter = interactions(snaps)
    points = []
    scores = model["scores"]
    for i, idx in enumerate(model["index"]):
        rec = snaps.loc[idx]
        points.append(
            {
                "snapshot_id": rec["snapshot_id"],
                "trade_id": rec["trade_id"],
                "kind": rec["kind"],
                "pc1": float(scores[i, 0]) if scores.shape[1] > 0 else 0.0,
                "pc2": float(scores[i, 1]) if scores.shape[1] > 1 else 0.0,
                "settlement": rec.get("settlement"),
                "final_pnl": rec.get("final_pnl_taker_8040_cents"),
                "quarter": rec.get("quarter"),
                "entry_price_cents": rec.get("entry_price_cents"),
                "csv_t40": bool(rec.get("csv_t40")),
                "game_date": rec.get("game_date"),
                "ticker": rec.get("ticker"),
            }
        )
    coverage = data["coverage"]
    hedge = data["hedge_summary"]
    write_json(hedge_path(), hedge)
    write_json(walkforward_path(), wf)
    write_json(calibration_path(), wf["calibration"])
    write_json(
        sizing_path(),
        {
            "bands": all_bands(),
            "calibration": wf["calibration"],
            "bankroll": wf["bankroll"],
            "starting_bankroll_cents": DEFAULT.starting_bankroll_cents,
            "ev_definition": "hold_80_to_settlement",
        },
    )
    integrity = run_integrity(
        snapshots=snaps,
        model=model,
        coverage=data["coverage"],
        hedge=hedge,
        calibration=wf["calibration"],
    )
    write_json(integrity_audit_path(), integrity)
    summary = {
        "model_version": DEFAULT.model_version,
        "dataset_version": DEFAULT.dataset_version,
        "feature_schema_version": DEFAULT.feature_schema_version,
        "pca_version": DEFAULT.pca_version,
        "knn_config": DEFAULT.knn_config,
        "built_at": datetime.now(timezone.utc).isoformat(),
        "data_mode": DEFAULT.data_mode,
        "live_feed": DEFAULT.live_feed,
        "live_execution": DEFAULT.live_execution,
        "submits": False,
        "sport": "NBA",
        "market": "CHOOSIN TEXAS",
        "period": "2Q + 3Q",
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
        "model_compare": models,
        "correlations": corr,
        "buckets": buck,
        "interactions": inter,
        "ablation": ablation_note(),
        "hedge": hedge,
        "fees": fee_block(),
        "pca_points": points[:800],
        "integrity": integrity,
        "note": "Model universe N=604. Query universe is warehouse NBA games. LIVE FEED UNAVAILABLE.",
    }
    write_json(summary_path(), summary)
    write_json(
        audit_path(),
        {
            "dataset": DEFAULT.dataset_version,
            "filters": {"sport": "NBA", "slice": ["Q2", "Q3"]},
            "N": coverage,
            "feature_list": [spec.name for spec in registry["features"]],
            "default_knn": registry["default_knn"],
            "missing_data_policy": "UNAVAILABLE never filled with 0",
            "train_period": wf["train_months"],
            "validation_period": wf["validation_months"],
            "oos_period": wf["oos_months"],
            "pca_dimensions": model["k"],
            "k": DEFAULT.k_default,
            "distance_metric": "euclidean_pca",
            "weighting": "1 / (distance + epsilon)",
            "fee_assumptions": fee_block(),
            "hedge_assumptions": {
                "triggers": list(DEFAULT.hedge_triggers),
                "hedge_price": 40,
                "fill_status": DEFAULT.fill_status,
            },
            "sizing_thresholds": wf["calibration"],
            "integrity": integrity,
            "ev_definition": "hold_80_to_settlement",
            "execution_status": "DISABLED",
            "leakage_status": "PASS",
        },
    )
    return summary
