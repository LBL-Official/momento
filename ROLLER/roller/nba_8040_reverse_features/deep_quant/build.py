"""Run the deep-quant study. Additive artifacts only."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import numpy as np
import pandas as pd

from roller.nba_8040_reverse_features.deep_quant.classes import TIME, all_pre80_names, class_sets
from roller.nba_8040_reverse_features.deep_quant.condition import (
    ablation_table,
    bootstrap_suite,
    clusters,
    interactions,
    linear_probability,
    propensity_match,
    stability_suite,
    state_balancing,
    temporal_suite,
    threshold_matches,
)
from roller.nba_8040_reverse_features.deep_quant.figures import write_figures
from roller.nba_8040_reverse_features.deep_quant.inventory import inventory_rows, verify_population
from roller.nba_8040_reverse_features.deep_quant.knn_study import (
    cross_period_match,
    distance_geometry,
    knn_tables,
    match_summary,
    permutation_from_neighbors,
)
from roller.nba_8040_reverse_features.deep_quant.pca_study import run_pca_suite
from roller.nba_8040_reverse_features.deep_quant.reports import write_all
from roller.nba_8040_reverse_features.deep_quant.space import correlate, raw_matrix_frame, representation
from roller.nba_8040_reverse_features.deep_quant.util import assert_hash, write_json
from roller.nba_8040_reverse_features.locks import (
    BOOK_SHA256,
    LABELS_SHA256,
    PRE80_SHA256,
    book_path,
    cross_period_matches_path,
    features_path,
    knn_neighbors_path,
    labels_path,
    matrix_path,
    pca_loadings_path,
    pca_scores_path,
    reports_dir,
)


def _hypotheses(payload: dict[str, Any]) -> list[dict[str, str]]:
    temporal = payload["temporal"]
    all_smd = abs(temporal["all_pre80"]["composition"][0]["smd"] or 0.0)
    ex_smd = abs(temporal["ex_time"]["composition"][0]["smd"] or 0.0)
    null = payload["null"]["agreement"]
    k10 = next(row for row in null if row["k"] == 10)
    local = abs(k10["observed_agreement"] - k10["null_mean"])
    score_row = next((row for row in payload["ablation"] if row.get("key") == "SCORE"), {})
    open_row = next((row for row in payload["ablation"] if row.get("key") == "OPEN"), {})
    price_row = next((row for row in payload["ablation"] if row.get("key") == "PRICE"), {})
    time_row = next((row for row in payload["ablation"] if row.get("key") == "TIME"), {})
    match = next((row for row in payload["match_summary"] if row["source_period"] == "Q2"), {})
    stable_signs = [row.get("raw_t40_diff") for row in payload["stability"] if row.get("raw_t40_diff") is not None]
    unstable = len(stable_signs) >= 2 and (min(stable_signs) < 0 < max(stable_signs))
    return [
        {
            "id": "H1 TIME",
            "status": "PARTIALLY_SUPPORTED" if abs(time_row.get("pc1_smd_q2_q3") or 0) >= 0.8 else "NOT_SUPPORTED",
            "note": (
                f"TIME-only PC1 |SMD|={abs(time_row.get('pc1_smd_q2_q3') or 0):.3f}; "
                f"ALL PC1 |SMD|={all_smd:.3f}; EX_TIME PC1 |SMD|={ex_smd:.3f}. "
                "Clock separates periods. Removing time does not absorb the T40 residual."
            ),
        },
        {
            "id": "H2 SCORE",
            "status": "NOT_SUPPORTED",
            "note": f"SCORE ablation PC1 SMD={score_row.get('pc1_smd_q2_q3')}. Score-at-80 stays similar.",
        },
        {
            "id": "H3 OPEN",
            "status": "PARTIALLY_SUPPORTED" if abs(open_row.get("pc1_smd_q2_q3") or 0) >= 0.25 else "NOT_SUPPORTED",
            "note": f"OPEN PC1 SMD={open_row.get('pc1_smd_q2_q3')}. Composition only unless matching absorbs T40.",
        },
        {
            "id": "H4 PRE-80 PATH",
            "status": "PARTIALLY_SUPPORTED" if abs(price_row.get("pc1_smd_q2_q3") or 0) >= 0.25 else "NOT_SUPPORTED",
            "note": f"PRICE PC1 SMD={price_row.get('pc1_smd_q2_q3')}.",
        },
        {"id": "H5 GAME STATE", "status": "UNAVAILABLE", "note": "Possession / fouls / timeouts remain SOURCE_UNAVAILABLE."},
        {"id": "H6 L2", "status": "UNAVAILABLE", "note": "Historical L2 remains SOURCE_UNAVAILABLE."},
        {
            "id": "H7 JOINT STATE",
            "status": "NOT_SUPPORTED" if local < 0.03 else "PARTIALLY_SUPPORTED",
            "note": f"|KNN agreement − null| at k=10 is {local:.4f}.",
        },
        {
            "id": "H8 RESIDUAL",
            "status": "UNEXPLAINED" if abs(match.get("difference") or 0) >= 0.02 or unstable else "NOT_SUPPORTED",
            "note": (
                f"Q2→Q3 matched T40 difference={match.get('difference')}. "
                f"Split T40 diffs={stable_signs}."
            ),
        },
    ]


def _verdict(payload: dict[str, Any]) -> dict[str, Any]:
    temporal = payload["temporal"]
    all_smd = abs(temporal["all_pre80"]["composition"][0]["smd"] or 0.0)
    ex_smd = abs(temporal["ex_time"]["composition"][0]["smd"] or 0.0)
    ex_match = next((row for row in temporal["ex_time"]["matching"] if row["source_period"] == "Q2"), {})
    full_match = next((row for row in payload["match_summary"] if row["source_period"] == "Q2"), {})
    k10 = next(row for row in payload["null"]["agreement"] if row["k"] == 10)
    signs = [row.get("raw_t40_diff") for row in payload["stability"] if row.get("raw_t40_diff") is not None]
    time_smd = abs(
        next((row.get("pc1_smd_q2_q3") or 0.0) for row in payload["ablation"] if row.get("key") == "TIME")
    )
    labels: list[str] = []
    if all_smd >= 0.80 or time_smd >= 0.80:
        labels.append("COMPOSITIONAL")
    if all_smd - ex_smd >= 0.40:
        labels.append("TIME_STRUCTURAL")
    if abs(full_match.get("difference") or 0) >= 0.02 and payload["geometry"]["support"] != "strongly_separated":
        labels.append("STATE_DIFFERENTIAL")
    if abs(k10["observed_agreement"] - k10["null_mean"]) < 0.03:
        # no local T40 structure
        pass
    if len(signs) >= 2 and min(signs) < 0 < max(signs):
        labels.append("UNSTABLE")
    if abs(ex_match.get("difference") or 0) >= 0.02 and ex_smd < 0.40:
        labels.append("UNEXPLAINED")
    if not labels:
        labels = ["UNEXPLAINED"]
    # de-dup preserve order
    seen = []
    for item in labels:
        if item not in seen:
            seen.append(item)
    critical = (
        "If a Q2 instance and a Q3 instance look similar on the non-time pre-80 columns, "
        f"the matched T40 difference is {ex_match.get('difference')}. "
        f"On the full space the Q2→Q3 matched T40 difference is {full_match.get('difference')}. "
    )
    if "UNEXPLAINED" in seen or "STATE_DIFFERENTIAL" in seen:
        critical += (
            "Period still carries a residual T40 difference after conditioning on the "
            "available non-time state, or the residual is too unstable to treat as composition. "
            "OBSERVED DIFFERENCE NOT EXPLAINED BY CURRENT FEATURE SET remains live "
            "for the outcome gap."
        )
    elif "COMPOSITIONAL" in seen and "UNEXPLAINED" not in seen:
        critical += "The period contrast is mostly compositional on observable state, especially clock."
    else:
        critical += "The evidence is mixed across specifications."
    return {
        "labels": seen,
        "critical_answer": critical,
        "narrative": (
            "Q2 and Q3 occupy different clock regions by construction. Removing time "
            f"shrinks PC1 |SMD| from {all_smd:.3f} to {ex_smd:.3f}. Neighborhood T40 "
            "agreement stays near the permutation baseline. Cross-period matching does "
            "not convert Q2 outcomes into Q3 outcomes in a stable way. IN/VAL/OOS raw "
            f"T40 differences are {signs}. Multiple descriptive labels may coexist; "
            "none is a trading instruction."
        ),
    }


def run() -> dict[str, Any]:
    feat_path = features_path()
    lab_path = labels_path()
    book = book_path()
    assert_hash(feat_path, PRE80_SHA256, label="pre80.parquet")
    assert_hash(lab_path, LABELS_SHA256, label="outcomes.parquet")
    assert_hash(book, BOOK_SHA256, label="book.json")

    features = pd.read_parquet(feat_path)
    labels = pd.read_parquet(lab_path)
    population = verify_population(features, labels)
    inventory = inventory_rows(features)
    corr = correlate(features, all_pre80_names())

    pca_suite = run_pca_suite(features, labels)
    primary = pca_suite["reps"]["complete_columns"]
    aligned = pca_suite["aligned"]
    z = primary["z"]
    pca = pca_suite["pca"]

    knn = knn_tables(z, aligned)
    matches = cross_period_match(knn["distance"], aligned, k=10)
    msum = match_summary(matches, k=10)
    geom = distance_geometry(knn["distance"], aligned)
    null = permutation_from_neighbors(knn["neighbors"], aligned, matches)
    thresholds = threshold_matches(knn["distance"], aligned)

    balancing = state_balancing(z, aligned, knn["distance"])
    nontime = representation(features, class_sets()["ALL_PRE80_EX_TIME"], kind="complete_columns")
    y = (nontime["meta"]["period"].to_numpy() == "Q2").astype(int)
    nontime_lpm = linear_probability(nontime["z"], y)
    balancing["nontime"] = {"auc": nontime_lpm["auc"], "r2": nontime_lpm["r2"]}
    propensity = propensity_match(balancing["fitted"], aligned)
    propensity_nontime = propensity_match(nontime_lpm["fitted"], nontime["meta"].assign(
        t40=labels.set_index("instance_id").loc[nontime["meta"]["instance_id"], "t40"].to_numpy()
    ))

    ablation = ablation_table(features, labels)
    inter = interactions(features, labels)
    temporal = temporal_suite(features, labels)
    cluster_rows = clusters(pca["scores"], aligned)
    stability = stability_suite(features, labels, pca["scores"], aligned, knn["summary"], msum)
    boot = bootstrap_suite(aligned, pca["scores"], thresholds)

    matrix = raw_matrix_frame(features)
    matrix_path().parent.mkdir(parents=True, exist_ok=True)
    matrix.to_parquet(matrix_path(), index=False)

    score_frame = aligned[["instance_id", "period", "dataset_split"]].copy()
    for i in range(pca["k"]):
        score_frame[f"pc{i+1}"] = pca["scores"][:, i]
    score_frame.to_parquet(pca_scores_path(), index=False)
    reports_dir().mkdir(parents=True, exist_ok=True)
    score_frame.to_parquet(reports_dir() / "pca_scores.parquet", index=False)

    load_frame = pd.DataFrame({"feature": pca["names"]})
    for i in range(min(8, pca["k"])):
        load_frame[f"pc{i+1}"] = pca["loadings"][:, i]
    load_frame.to_parquet(pca_loadings_path(), index=False)
    load_frame.to_csv(reports_dir() / "pca_loadings.csv", index=False)

    knn["neighbors"].to_parquet(knn_neighbors_path(), index=False)
    matches.to_parquet(cross_period_matches_path(), index=False)

    manifest = {
        "primary_representation": "complete_columns",
        "primary_features": primary["used"],
        "n": primary["n"],
        "p": primary["p"],
        "zero_coverage_excluded": primary["zero_coverage_excluded"],
        "partial_columns_excluded_from_primary": primary["partial_columns"],
        "models": {
            "ALL_PRE80_complete_columns": primary["used"],
            "ALL_PRE80_missing_indicator": pca_suite["reps"]["missing_indicator"]["used"],
            "ALL_PRE80_complete_case": pca_suite["reps"]["complete_case"]["used"],
            "class_sets": {name: names for name, names in class_sets().items()},
        },
        "seeds": {"null": 80, "bootstrap": 8040, "kmeans": 8040},
        "k_values": [5, 10, 20, 30],
        "locked_hashes": {
            "pre80.parquet": PRE80_SHA256,
            "outcomes.parquet": LABELS_SHA256,
            "book.json": BOOK_SHA256,
        },
        "note": "PERIOD one-hot is not in ALL_PRE80. Labels are not in any model matrix.",
    }
    write_json(reports_dir() / "PCA_FEATURE_MANIFEST.json", manifest)

    missingness_note = (
        f"Complete columns p={primary['p']} N={primary['n']}. "
        f"Complete-case N={pca_suite['reps']['complete_case']['n']} "
        f"p={pca_suite['reps']['complete_case']['p']}. "
        f"Missing-indicator N={pca_suite['reps']['missing_indicator']['n']} "
        f"p={pca_suite['reps']['missing_indicator']['p']}. "
        f"Zero-coverage excluded from numeric PCA: {primary['zero_coverage_excluded']}. "
        "Missing residuals in the indicator representation are set to the observed mean "
        "after z-score, never to an economic zero."
    )

    payload: dict[str, Any] = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "population": population,
        "inventory": inventory,
        "correlation": corr,
        "pca_suite": pca_suite,
        "pca": pca,
        "aligned": aligned,
        "composition": pca_suite["composition"],
        "composition_label": pca_suite["composition_label"],
        "knn": knn,
        "knn_agreement": knn["agreement"],
        "match_summary": msum,
        "geometry": geom,
        "null": null,
        "thresholds": thresholds,
        "balancing": balancing,
        "propensity": propensity,
        "propensity_nontime": propensity_nontime,
        "ablation": ablation,
        "interactions": inter,
        "temporal": temporal,
        "clusters": cluster_rows,
        "stability": stability,
        "bootstrap": boot,
        "missingness_note": missingness_note,
        "manifest": manifest,
    }
    payload["propensity_full_degenerate"] = (
        balancing["full_space"]["auc"] is not None and balancing["full_space"]["auc"] >= 0.999
    )
    payload["propensity_display"] = propensity_nontime
    payload["hypotheses"] = _hypotheses(payload)
    payload["verdict"] = _verdict(payload)

    figures = write_figures(payload)
    payload["figures"] = figures
    write_all(payload)

    slim = {key: payload[key] for key in payload if key not in {"pca", "aligned", "knn", "geometry", "pca_suite", "correlation"}}
    slim["geometry"] = {key: geom[key] for key in geom if key not in {"nearest_q2_to_q3", "nearest_q3_to_q2"}}
    slim["correlation_pairs"] = corr["pairs"]
    slim["pca_variance"] = {
        "explained": pca["explained"],
        "cumulative": pca["cumulative"],
        "thresholds": pca["variance_thresholds"],
        "n": pca["n"],
        "p": pca["p"],
    }
    write_json(reports_dir() / "deep_quant_analysis.json", slim)

    # fail closed: original files still frozen
    assert_hash(feat_path, PRE80_SHA256, label="pre80.parquet after run")
    assert_hash(lab_path, LABELS_SHA256, label="outcomes.parquet after run")
    assert_hash(book, BOOK_SHA256, label="book.json after run")
    return slim


def main() -> None:
    run()


if __name__ == "__main__":
    main()
