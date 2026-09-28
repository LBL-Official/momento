"""PHASE 21 — markdown reports from measured tables. No invented numbers."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from roller.nba_8040_reverse_features.deep_quant.util import md_table
from roller.nba_8040_reverse_features.locks import library_root, reports_dir


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def write_inventory(rows: list[dict[str, Any]]) -> None:
    body = [
        "# Feature inventory",
        "",
        "Every column on the locked 604-row store. Nothing is dropped silently.",
        "Labels live in `labels/outcomes.parquet` and are listed as future.",
        "",
        md_table(
            rows,
            [
                "feature_name",
                "feature_class",
                "class_name",
                "timing",
                "source",
                "semantic_basis",
                "availability_status",
                "numeric_or_categorical",
                "encoding",
                "missing_pct",
                "available_n",
                "unique_count",
                "variance",
                "usable_in_pca",
                "usable_in_distance",
                "outcome_or_future",
                "missing_kind",
                "redundant_with",
            ],
        ),
    ]
    _write(reports_dir() / "FEATURE_INVENTORY.md", "\n".join(body))


def write_correlation(corr: dict[str, Any]) -> None:
    body = [
        "# Feature correlation",
        "",
        f"Fully observed columns used: {corr['n_features']}. N={corr['n']}.",
        corr["note"],
        "",
        "High-correlation pairs (`|r| ≥ 0.80`). Columns are not deleted.",
        "",
        md_table(corr["pairs"], ["left", "right", "pearson", "spearman", "kind"]),
    ]
    _write(reports_dir() / "FEATURE_CORRELATION.md", "\n".join(body))
    corr["pearson"].to_csv(reports_dir() / "feature_correlation_pearson.csv")
    corr["spearman"].to_csv(reports_dir() / "feature_correlation_spearman.csv")


def write_pca_report(suite: dict[str, Any]) -> None:
    pca = suite["pca"]
    var_rows = [
        {
            "component": f"PC{i+1}",
            "explained": pca["explained"][i],
            "cumulative": pca["cumulative"][i],
            "singular_value": pca["singular_values"][i],
        }
        for i in range(len(pca["explained"]))
    ]
    load_rows = []
    for i, name in enumerate(pca["names"]):
        row = {"feature": name}
        for j in range(min(6, pca["k"])):
            row[f"pc{j+1}"] = float(pca["loadings"][i, j])
        load_rows.append(row)
    body = [
        "# PCA report",
        "",
        "Fitted on pre-80 state only. Labels are not used in the SVD.",
        f"Primary representation: `{suite['primary_kind']}`.",
        f"N={pca['n']} rows, p={pca['p']} columns, k={pca['k']} stored components.",
        pca["scaling"],
        pca["sign_convention"],
        "",
        "## Representations",
        "",
        md_table(
            [
                {"kind": k, **{x: v[x] for x in ("n", "p", "note")}}
                for k, v in suite["representations"].items()
            ],
            ["kind", "n", "p", "note"],
        ),
        "## Variance",
        "",
        md_table(var_rows, ["component", "explained", "cumulative", "singular_value"]),
        "",
        str(pca["variance_thresholds"]),
        "",
        "## Reconstruction error",
        "",
        md_table(pca["reconstruction"][:8], ["k", "relative_frobenius_error"]),
        "",
        "## Top contributors",
        "",
    ]
    for block in pca["top"][:6]:
        body.append(f"### PC{block['pc']}")
        body.append("")
        body.append(md_table(block["contributors"], ["feature", "loading"]))
    body.extend(
        [
            "## Feature-class share of squared loadings",
            "",
            md_table(pca["class_share"][:6], sorted({k for row in pca["class_share"] for k in row})),
            "",
            "## Q2 vs Q3 on PCs (overlay after fit)",
            "",
            md_table(
                suite["composition"],
                ["pc", "q2_mean", "q3_mean", "q2_median", "q3_median", "smd", "overlap"],
            ),
            f"Composition label: **{suite['composition_label']}**",
            "",
            "## Outcome overlay (predetermined quintiles)",
            "",
            md_table(
                suite["outcome_overlay"],
                [
                    "pc",
                    "quantile",
                    "n",
                    "t40_rate",
                    "s_rate",
                    "t40_wilson_lo",
                    "t40_wilson_hi",
                    "t40_minus_base",
                ],
            ),
            "",
            "## Feature-class PCA",
            "",
        ]
    )
    for name, block in suite["class_pcas"].items():
        body.append(f"### {name}")
        body.append("")
        body.append(str({k: block[k] for k in block if k not in {"top", "composition", "used"}}))
        body.append("")
        if "composition" in block:
            body.append(md_table(block["composition"], ["pc", "q2_mean", "q3_mean", "smd", "overlap"]))
    _write(reports_dir() / "PCA_REPORT.md", "\n".join(body) + "\n")


def write_knn_report(knn: dict[str, Any], geom: dict[str, Any], null: dict[str, Any]) -> None:
    body = [
        "# KNN report",
        "",
        "Euclidean distance on the standardized complete-column matrix.",
        "Fixed k ∈ {5,10,20,30}. No k search.",
        "",
        md_table(knn["agreement"], ["k", "n", "mean_agreement", "mean_entropy", "mean_neighbor_t40", "mean_cross_period_share", "mean_distance"]),
        "",
        "## Distance geometry",
        "",
        f"Support label: **{geom['support']}** (median cross/within = {geom['median_cross_over_within']:.4f})",
        "",
        md_table(
            [
                {"leg": "Q2→Q3 nearest", **geom["q2_to_q3"]},
                {"leg": "Q3→Q2 nearest", **geom["q3_to_q2"]},
                {"leg": "within Q2", **geom["within_q2"]},
                {"leg": "within Q3", **geom["within_q3"]},
            ],
            ["leg", "p10", "p25", "p50", "p75", "p90", "mean"],
        ),
        "",
        "## Permutation null (T40 shuffled, distances fixed)",
        "",
        md_table(null["agreement"], ["k", "observed_agreement", "null_mean", "null_p50", "null_p025", "null_p975", "percentile_of_observed"]),
    ]
    _write(reports_dir() / "KNN_REPORT.md", "\n".join(body) + "\n")
    _write(reports_dir() / "NULL_REPORT.md", "\n".join(body) + "\n")


def write_matching_report(msum: list[dict], thresholds: list[dict], propensity: list[dict]) -> None:
    body = [
        "# Matching report",
        "",
        "Descriptive only. Q2 instances are placed next to nearest Q3 states and conversely.",
        "Same-instance matching is impossible because periods differ.",
        "",
        md_table(
            msum,
            [
                "source_period",
                "match_period",
                "k",
                "n",
                "source_t40",
                "matched_t40",
                "difference",
                "source_s",
                "matched_s",
                "median_nearest_distance",
            ],
        ),
        "## Distance-quantile thresholds (pre-specified, not outcome-tuned)",
        "",
        md_table(
            [row for row in thresholds if "difference" in row],
            [
                "direction",
                "quantile",
                "distance_cutoff",
                "n",
                "source_t40",
                "matched_t40",
                "difference",
                "source_s",
                "matched_s",
            ],
        ),
        "## Propensity (linear probability of Q2 from pre-80 state)",
        "",
        "Full-space linear probability of period is degenerate when clock is included "
        "(period is a near-linear function of game time). Matching below uses the "
        "non-time state only.",
        "",
        md_table(propensity, ["direction", "n", "source_t40", "matched_t40", "difference", "median_propensity_gap"]),
    ]
    _write(reports_dir() / "MATCHING_REPORT.md", "\n".join(body) + "\n")


def write_state_space(
    composition_label: str,
    geom: dict,
    ablation: list[dict],
    interactions: list[dict],
    temporal: dict,
    clusters: list[dict],
    balancing: dict,
) -> None:
    body = [
        "# State-space report",
        "",
        f"Unconditional PCA composition: **{composition_label}**",
        f"Distance support: **{geom['support']}**",
        "",
        "## Feature-class ablation (diagnostics, not a leaderboard)",
        "",
        md_table(
            ablation,
            [
                "set",
                "key",
                "n",
                "p",
                "pc1_smd_q2_q3",
                "pc1_overlap",
                "knn_k10_agreement",
                "q2_to_q3_t40_diff",
                "distance_support",
                "median_cross_over_within",
            ],
        ),
        "## Temporal variants",
        "",
    ]
    for name, block in temporal.items():
        body.append(f"### {name}")
        body.append(f"support={block['support']}  k10_agreement={block['knn_k10_agreement']:.4f}")
        body.append(md_table(block["composition"], ["pc", "q2_mean", "q3_mean", "smd", "overlap"]))
        body.append(md_table(block["matching"], ["source_period", "source_t40", "matched_t40", "difference"]))
    body.extend(
        [
            "## Predetermined tertile interactions",
            "",
            md_table(
                interactions,
                [
                    "left",
                    "right",
                    "left_bin",
                    "right_bin",
                    "period",
                    "n",
                    "t40_rate",
                    "t40_wilson_lo",
                    "t40_wilson_hi",
                ],
            ),
            "## Unsupervised state regions (k-means on PC1–PC3, labels unused in fit)",
            "",
            md_table(clusters, ["state_region", "n", "q2_share", "t40_rate", "s_rate"]),
            "",
            f"Period LPM AUC on full primary space: {balancing['full_space']['auc']}",
            f"LPM R²: {balancing['full_space']['r2']}",
        ]
    )
    _write(reports_dir() / "STATE_SPACE_REPORT.md", "\n".join(body) + "\n")


def write_stability(rows: list[dict], boot: dict) -> None:
    body = [
        "# Stability and bootstrap",
        "",
        "IN / VAL / OOS are the asked-six splits on the same 604. No 2026–27 rows.",
        "",
        md_table(
            rows,
            [
                "split",
                "n",
                "q2_n",
                "q3_n",
                "pc1_smd",
                "raw_t40_q2",
                "raw_t40_q3",
                "raw_t40_diff",
                "knn_k10_agreement",
            ],
        ),
        "## Bootstrap (resample rows, 200 draws, seed 8040)",
        "",
        str(boot),
        "",
    ]
    _write(reports_dir() / "STABILITY_REPORT.md", "\n".join(body) + "\n")


def write_master(payload: dict[str, Any]) -> None:
    hyp = payload["hypotheses"]
    verdict = payload["verdict"]
    pop = payload["population"]
    pca = payload["pca"]
    temporal_rows = [
        {
            "variant": name,
            "pc1_smd": block["composition"][0]["smd"],
            "support": block["support"],
            "k10_agreement": block["knn_k10_agreement"],
        }
        for name, block in payload["temporal"].items()
    ]
    hyp_lines = "\n".join(f"- **{row['id']}** — {row['status']}. {row['note']}" for row in hyp)
    body = f"""# NBA 80→40 deep quant analysis

Research only. Candle path ≠ fill. Association, not causation.
No trading filter. The Choosin Texas 2026–27 book is unchanged.

Generated: `{payload["generated_at"]}`

## 1. Executive Summary

Locked population N={pop["n"]} (Q2={pop["q2"]}, Q3={pop["q3"]}, Q2 regular season={pop["q2_regular_season"]}).
Primary PCA uses the complete-column representation: N={pca["n"]}, p={pca["p"]}.
Q2 vs Q3 PCA composition: **{payload["composition_label"]}**.
Distance support: **{payload["geometry"]["support"]}**.
Structural labels: **{", ".join(verdict["labels"])}**.

{verdict["critical_answer"]}

`RESEARCH ONLY — NO TRADING FILTER CREATED.`

## 2. Research Question

Why does NBA Q2 FIRST80 80→40 behave differently from Q3 on candle path?
Not: which filter raises a ledger number.

## 3. Population Lock

| lock | N |
| --- | ---: |
| Q2∪Q3 | {pop["n"]} |
| Q2 all-phase | {pop["q2"]} |
| Q3 all-phase | {pop["q3"]} |
| Q2 regular season | {pop["q2_regular_season"]} |

Instance = one FIRST80 trigger per event. `instance_id` is unique on all 604.

## 4. Instance Definition

First tradable `yes_bid_close ≥ 80` after a prior close `< 80`, spread ≤ 10¢.
Not a later 80 reprint. Not a game-level collapse.

## 5. Feature Inventory

See `reports/FEATURE_INVENTORY.md`. Every store column is listed.
Labels remain in `labels/outcomes.parquet`.

## 6. Data Availability

Observable: quote-at-entry, pre-80 TRADABLE_YES_BID path, modeled clock, score snapshot, pre-tip open.
Unavailable: historical L2, fills, possession/fouls/timeouts at the candle, PBP↔candle PIT, opposite ticker.

## 7. Missingness

{payload["missingness_note"]}

## 8. Analytical Matrix

`features/pre80_matrix.parquet` holds instance keys, every predictive column, and `miss_*` indicators.
Manifest: `reports/PCA_FEATURE_MANIFEST.json`.

## 9. Correlation Structure

See `reports/FEATURE_CORRELATION.md`. Correlated columns are retained.

## 10. PCA Method

`numpy.linalg.svd` on z-scored complete columns. No sklearn. No labels in the fit.

## 11. PCA Results

Dimensions for 50/75/90/95% variance: {pca["variance_thresholds"]}.
See `reports/PCA_REPORT.md`.

## 12. Feature-Class PCA

See the class sections of `PCA_REPORT.md`. PERIOD one-hot is class-only and is not in ALL_PRE80.

## 13. Q2/Q3 State Composition

{payload["composition_label"]}

{md_table(payload["composition"], ["pc", "q2_mean", "q3_mean", "smd", "overlap"])}

## 14. Outcome Overlay

Predetermined quintiles on PCs fitted without T40. See PCA report.

## 15. KNN Method

Euclidean on the same z-matrix. k ∈ {{5,10,20,30}}. Distances do not use labels.

## 16. KNN Results

{md_table(payload["knn_agreement"], ["k", "mean_agreement", "mean_entropy", "mean_cross_period_share"])}

## 17. Cross-Period Matching

{md_table(payload["match_summary"], ["source_period", "n", "source_t40", "matched_t40", "difference"])}

## 18. Distance Geometry

Support **{payload["geometry"]["support"]}**. Median cross/within = {payload["geometry"]["median_cross_over_within"]:.4f}.

## 19. Local Outcome Homogeneity

Neighborhood T40 entropy and agreement are in `KNN_REPORT.md`.

## 20. Permutation Null

{md_table(payload["null"]["agreement"], ["k", "observed_agreement", "null_mean", "null_p025", "null_p975", "percentile_of_observed"])}

## 21. Conditional Q2/Q3 Analysis

Pre-specified nearest-neighbor distance quantiles 0.25 / 0.50 / 0.75.

{md_table([r for r in payload["thresholds"] if "difference" in r], ["direction", "quantile", "n", "source_t40", "matched_t40", "difference"])}

## 22. State Balancing

Linear probability of Q2 membership from pre-80 state (not T40).
Full-space AUC={payload["balancing"]["full_space"]["auc"]}, R²={payload["balancing"]["full_space"]["r2"]}.
Non-time AUC={payload["balancing"]["nontime"]["auc"]}.

{md_table(payload.get("propensity_display") or payload["propensity"], ["direction", "n", "source_t40", "matched_t40", "difference"])}

## 23. Feature-Class Ablation

{md_table(payload["ablation"], ["set", "key", "p", "pc1_smd_q2_q3", "knn_k10_agreement", "q2_to_q3_t40_diff", "distance_support"])}

## 24. Interaction Structure

Predetermined tertiles only. See `STATE_SPACE_REPORT.md`.

## 25. Temporal Normalization

{md_table(temporal_rows, ["variant", "pc1_smd", "support", "k10_agreement"])}

## 26. Season Stability

{md_table(payload["stability"], ["split", "n", "q2_n", "q3_n", "pc1_smd", "raw_t40_diff", "knn_k10_agreement"])}

## 27. Bootstrap Uncertainty

{payload["bootstrap"]}

## 28. Information Gap

OBSERVABLE: market at 80, pre-80 path, modeled clock, score snapshot, pre-tip open, quote-at-entry, window volatility.
UNAVAILABLE: L2, fills, possession/fouls/timeouts, PBP↔candle PIT, hidden order flow.

## 29. H1–H8 Assessment

{hyp_lines}

## 30. Final Structural Conclusion

**{", ".join(verdict["labels"])}**

{verdict["narrative"]}

## 31. Research Limitations

N=604 is the asked-six lock, not a resample. Clock is `PERIOD_BOUNDED_LINEAR_GAME_CLOCK`, not warehouse PIT.
Complete-column PCA drops zero-coverage window summaries (`std_1m`, `accel_1m`, …) rather than filling them.
IN/VAL/OOS cells are modest. Candle path is not a fill.

## 32. Explicit Non-Trading Conclusion

This study does not produce a rule, a book edit, a live signal, or a claimed edge.
`RESEARCH ONLY — NO TRADING FILTER CREATED.`
"""
    _write(library_root() / "NBA_8040_DEEP_QUANT_ANALYSIS.md", body)


def write_all(payload: dict[str, Any]) -> None:
    write_inventory(payload["inventory"])
    write_correlation(payload["correlation"])
    write_pca_report(payload["pca_suite"])
    write_knn_report(payload["knn"], payload["geometry"], payload["null"])
    write_matching_report(
        payload["match_summary"],
        payload["thresholds"],
        payload.get("propensity_display") or payload["propensity"],
    )
    write_state_space(
        payload["composition_label"],
        payload["geometry"],
        payload["ablation"],
        payload["interactions"],
        payload["temporal"],
        payload["clusters"],
        payload["balancing"],
    )
    write_stability(payload["stability"], payload["bootstrap"])
    write_master(payload)
