#!/usr/bin/env python3
"""Copy research artifacts into frontend/nba-research-engine-v2/public/data."""

from __future__ import annotations

import json
import shutil

from common import DASH_PUBLIC, OUT, utc_now, write_json, read_parquet_rows


COPY = [
    "summary.json",
    "observations_summary.json",
    "possession_validation.json",
    "overlay_summary.json",
    "phase1_gate.json",
    "features_summary.json",
    "feature_metadata.json",
    "diagnostics.json",
    "univariate_fdr.json",
    "clusters.json",
    "models.json",
    "selection.json",
    "experiment_registry.json",
    "economics.json",
    "portfolio.json",
    "pca_points.json",
    "chronological.json",
    "leakage_audit.json",
    "feature_availability.json",
    "pca_loadings.json",
    "clusters_extended.json",
    "umap_points.json",
    "ablation_extended.json",
    "permutation_importance_val.json",
    "survive_thresholds.json",
    "walk_forward.json",
    "portfolio_sim.json",
    "labels_summary.json",
]


def main() -> int:
    DASH_PUBLIC.mkdir(parents=True, exist_ok=True)
    copied = []
    for name in COPY:
        src = OUT / name
        if src.exists():
            shutil.copy2(src, DASH_PUBLIC / name)
            copied.append(name)

    feat_path = OUT / "features.parquet"
    trades = []
    if feat_path.exists():
        rows = read_parquet_rows(feat_path)
        keep = [
            "observation_id",
            "event_id",
            "ticker",
            "team_code",
            "game_date",
            "dataset_split",
            "Y_40_CLOSE",
            "SURVIVE_40",
            "Y_40_WICK",
            "alignment_confidence",
            "game_phase",
            "possession_id",
            "primary_set",
            "quarter",
            "possession_number",
            "score_differential",
            "game_completion_pct",
            "mkt_yes_bid_cents",
            "mkt_spread_cents",
            "mkt_alignment_quality",
            "coupling_regime",
            "game_regime",
        ]
        for r in rows:
            trades.append({k: r.get(k) for k in keep})
        write_json(DASH_PUBLIC / "trades_index.json", {"n": len(trades), "rows": trades})
        copied.append("trades_index.json")

    write_json(
        DASH_PUBLIC / "manifest.json",
        {"written_utc": utc_now(), "copied": copied},
    )
    print("dashboard data", copied)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
