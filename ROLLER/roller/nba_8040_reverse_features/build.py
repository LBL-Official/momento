"""Build the 604-row store and run the reverse-engineering sequence."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

import numpy as np
import pandas as pd

from roller.nba_8040_reverse_features.analyze import (
    ablation,
    composition_tables,
    temporal_normalization,
    within_period,
)
from roller.nba_8040_reverse_features.bars import load_ticker_bars
from roller.nba_8040_reverse_features.catalog import CATALOG, LABEL_SPECS, matrix_specs
from roller.nba_8040_reverse_features.classify import classify
from roller.nba_8040_reverse_features.event_path import build_event_path, write_event_path
from roller.nba_8040_reverse_features.features import build_features, write_features
from roller.nba_8040_reverse_features.instances import load_instances
from roller.nba_8040_reverse_features.knn import (
    cross_period_match,
    neighborhood_table,
    null_agreement,
    stability_splits,
)
from roller.nba_8040_reverse_features.labels import build_labels, write_labels
from roller.nba_8040_reverse_features.leakage import assert_predictive_columns
from roller.nba_8040_reverse_features.locks import NBA_Q2Q3_N, reports_dir
from roller.nba_8040_reverse_features.matrix import coverage_names, predictive_frame
from roller.nba_8040_reverse_features.pca import run_pca
from roller.nba_8040_reverse_features.plots import write_figures
from roller.nba_8040_reverse_features.report import write_report


def _jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    if isinstance(value, tuple):
        return [_jsonable(item) for item in value]
    if isinstance(value, (np.floating,)):
        return float(value)
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.bool_,)):
        return bool(value)
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def run() -> dict[str, Any]:
    instances = load_instances()
    bars = load_ticker_bars({row["ticker"] for row in instances})
    features = build_features(instances, bars)
    labels = build_labels(instances, bars)
    write_features(features)
    write_labels(labels)
    path_frame = build_event_path(instances, features, labels, bars)
    write_event_path(path_frame)

    predictive = [spec.name for spec in matrix_specs()]
    assert_predictive_columns(predictive)
    predictive_frame(features, predictive)
    covered = coverage_names(features, min_frac=0.90)

    composition = composition_tables(features, labels)
    within = within_period(features, labels)
    temporal = temporal_normalization(features, labels)
    ablate = ablation(features, labels)
    pca = run_pca(features, labels)
    neighborhood = neighborhood_table(features, labels, covered, ks=(5, 10, 20, 30), within=False)
    neighborhood += neighborhood_table(features, labels, covered, ks=(5, 10, 20, 30), within=True)
    matching = cross_period_match(features, labels, k=10)
    null = null_agreement(features, labels, k=10, seed=80)
    stability = stability_splits(features, labels)

    figures = write_figures(features, labels, pca)
    pca_points = pd.DataFrame(pca["points"])
    dest = reports_dir()
    dest.mkdir(parents=True, exist_ok=True)
    pca_points.to_parquet(dest / "pca_points.parquet", index=False)
    pca_summary = {key: value for key, value in pca.items() if key != "points"}

    analysis = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "store": {
            "n": int(len(features)),
            "lock_n": NBA_Q2Q3_N,
            "predictive_n": len(predictive),
            "coverage_n": len(covered),
            "coverage_features": covered,
            "catalog_n": len(CATALOG),
            "label_n": len(LABEL_SPECS),
        },
        "composition": composition,
        "within": within,
        "temporal": temporal,
        "ablation": ablate,
        "pca": pca_summary,
        "neighborhood": neighborhood,
        "matching": matching,
        "null": null,
        "stability": stability,
    }
    analysis["verdict"] = classify(analysis)
    write_report(analysis, figures)
    (dest / "analysis.json").write_text(
        json.dumps(_jsonable(analysis), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return analysis


def main() -> None:
    run()


if __name__ == "__main__":
    main()
