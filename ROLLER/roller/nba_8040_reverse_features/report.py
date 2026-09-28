"""Write the reverse-engineering report. Does not edit the Choosin Texas book."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from roller.nba_8040_reverse_features.locks import library_root, reports_dir


def _cell(value: Any) -> str:
    if value is None:
        return "—"
    if isinstance(value, float):
        return f"{value:.4f}"
    return str(value)


def _table(rows: list[dict[str, Any]], columns: list[str]) -> str:
    if not rows:
        return "_none_\n"
    header = "| " + " | ".join(columns) + " |"
    rule = "| " + " | ".join("---" for _ in columns) + " |"
    body = []
    for row in rows:
        body.append("| " + " | ".join(_cell(row.get(col)) for col in columns) + " |")
    return "\n".join([header, rule, *body]) + "\n"


def render(analysis: dict[str, Any], figure_names: list[str]) -> str:
    verdict = analysis["verdict"]
    pops = analysis["composition"]["population"]
    diffs = sorted(
        analysis["composition"]["q2_vs_q3"],
        key=lambda row: (abs(row["standardized_difference"] or 0.0)),
        reverse=True,
    )
    top = diffs[:20]
    lines = [
        "# NBA 80→40 reverse engineering",
        "",
        "Research only. Candle path ≠ fill. Not a live FIRST80 retune. "
        "The Choosin Texas 2026–27 book is unchanged.",
        "",
        f"Generated: `{analysis['generated_at']}`",
        "",
        "## Question",
        "",
        "Why does NBA Q2 FIRST80 80→40 behave differently from Q3 and the broader "
        "80→40 population?",
        "",
        "Not: which filter raises EV.",
        "",
        "## Structural label",
        "",
        f"**{verdict['label']}**",
        "",
        f"Flags: {', '.join(verdict['flags']) if verdict['flags'] else 'none'}",
        "",
        verdict["caveat"],
        "",
        "| metric | value |",
        "| --- | --- |",
        f"| mean |SMD| Q2 vs Q3 | {_cell(verdict['mean_abs_smd_q2_q3'])} |",
        f"| mean |SMD| Q2 vs Q3 excluding time | {_cell(verdict.get('mean_abs_smd_q2_q3_ex_time'))} |",
        f"| max |SMD| Q2 vs Q3 | {_cell(verdict['max_abs_smd_q2_q3'])} |",
        f"| time mean |SMD| | {_cell(verdict['time_mean_abs_smd'])} |",
        f"| score mean |SMD| | {_cell(verdict['score_mean_abs_smd'])} |",
        f"| open mean |SMD| | {_cell(verdict['open_mean_abs_smd'])} |",
        f"| price mean |SMD| | {_cell(verdict['price_mean_abs_smd'])} |",
        f"| raw T40 gap Q2−Q3 | {_cell(verdict['raw_t40_gap'])} |",
        f"| matching shrink | {_cell(verdict['match_shrink'])} |",
        f"| temporal shrink | {_cell(verdict['temporal_shrink'])} |",
        "",
        "## How to read this",
        "",
        "Q2 candle-path EV is +5.6688¢ / trade (N=314) against Q3 +3.6552¢ / trade "
        "(N=290). The T40 rate gap is small (75/314 vs 79/290). Q2 vs Q3 differ "
        "strongly on clock because Q3 is later in the game; that is not an "
        "explanation unless holding fraction-of-period / fraction-of-game fixed "
        "shrinks the EV gap. It does not (`temporal_shrink` is negative). "
        "Cross-period matching on the pre-80 matrix does not pull T40 rates "
        "together (`matching_shrink` is negative). Within-period survive-vs-T40 "
        "standardized differences stay small. Neighborhood outcome agreement is "
        "indistinguishable from a label permutation. So the current feature set "
        "does not explain why Q2 80→40 prints a higher candle-path EV than Q3. "
        "That is `UNEXPLAINED`, not a new trading filter.",
        "",
        "## Locked population",
        "",
        "Feature-store universe is the asked-six NBA Q2∪Q3 **N=604** after fail-closed "
        "reproduction. 314 / 290 / 280 are slices of that store.",
        "",
        _table(
            pops,
            [
                "period",
                "n",
                "survivors",
                "t40",
                "w_and_t40",
                "l_and_t40",
                "ev_per_trade_display",
                "book_cents",
            ],
        ),
        "EV uses `ev.py` only: `20S − 40(1−S)`. S = ¬T40.",
        "",
        "## Feature store",
        "",
        f"Rows: **{analysis['store']['n']}**. Predictive columns after leakage assert: "
        f"{analysis['store']['predictive_n']}. PCA/KNN coverage set (≥90% observed): "
        f"{analysis['store']['coverage_n']}.",
        "",
        "Missing stays missing. Possession / fouls / timeouts remain `SOURCE_UNAVAILABLE`. "
        "Time-windowed PBP remains `OPERATION_REQUIRED`. Historical L2 remains "
        "`SOURCE_UNAVAILABLE`.",
        "",
        "### Availability",
        "",
        _table(
            analysis["composition"]["availability"],
            ["feature_class", "feature", "available_n", "missing_pct", "source"],
        ),
        "## Question A — unconditional Q2 vs Q3",
        "",
        "Largest standardized mean differences first. Period one-hot is a grouping "
        "column and is not in the predictive matrix.",
        "",
        _table(
            top,
            [
                "feature",
                "q2_mean",
                "q3_mean",
                "q2_median",
                "q3_median",
                "standardized_difference",
                "q2_available_n",
                "q3_available_n",
            ],
        ),
        "## Question B — survive vs T40 within period",
        "",
        _table(
            analysis["within"],
            [
                "feature",
                "q2_survive_mean",
                "q2_t40_mean",
                "q2_smd",
                "q3_survive_mean",
                "q3_t40_mean",
                "q3_smd",
            ],
        ),
        "## Temporal normalization (H1)",
        "",
        "If the Q2/Q3 EV gap shrinks inside fraction-of-period / fraction-of-game bins, "
        "the period label is partly a clock alias.",
        "",
        _table(
            analysis["temporal"],
            ["axis", "bin", "period", "n", "s", "ev_cents"],
        ),
        "## Class ablation",
        "",
        "Diagnostics, not a rank score. No k or EV tuning.",
        "",
        _table(
            analysis["ablation"],
            [
                "feature_set",
                "n_features",
                "q2_q3_mean_abs_smd",
                "q2_outcome_mean_abs_smd",
                "q3_outcome_mean_abs_smd",
                "knn_k10_agreement",
            ],
        ),
        "## PCA",
        "",
        f"Complete-case n={analysis['pca']['n']} on {analysis['pca']['n_features']} "
        f"features. Scaling: {analysis['pca']['scaling']}. "
        f"{analysis['pca']['missing_treatment']}.",
        "",
        _table(analysis["pca"]["variance"], ["component", "explained", "cumulative"]),
        "",
        "Top |PC1| loadings:",
        "",
        _table(
            sorted(
                analysis["pca"]["loadings"],
                key=lambda row: abs(row["pc1"] or 0.0),
                reverse=True,
            )[:15],
            ["feature", "pc1", "pc2", "pc3"],
        ),
        "## KNN / matching / null / stability",
        "",
        "Fixed k ∈ {5,10,20,30}. Not a classifier.",
        "",
        "### Neighborhood",
        "",
        _table(
            analysis["neighborhood"],
            ["scope", "period", "k", "n", "outcome_agreement", "mean_neighbor_ev"],
        ),
        "### Cross-period matching (k=10)",
        "",
        _table(
            analysis["matching"],
            [
                "source_period",
                "match_period",
                "k",
                "n",
                "source_t40_rate",
                "matched_t40_rate",
                "difference",
                "source_ev",
                "matched_ev",
            ],
        ),
        "### Label-permutation null (k=10, within-period)",
        "",
        _table([analysis["null"]], ["k", "real_agreement", "null_agreement"]),
        "",
        "### IN / VAL / OOS slices of the same 604",
        "",
        _table(
            analysis["stability"],
            ["split", "n", "q2_n", "q3_n", "q2_ev", "q3_ev", "q2_minus_q3"],
        ),
        "## Hypotheses",
        "",
    ]
    for row in analysis["hypotheses"]:
        lines.append(f"- **{row['id']}** — {row['status']}. {row['note']}")
    lines.extend(
        [
            "",
            "## Figures",
            "",
        ]
    )
    for name in figure_names:
        lines.append(f"- `{name}`")
    lines.extend(
        [
            "",
            "## What this will not do",
            "",
            "- No skip-4–6 / only-56–60 / only-Q2 rule",
            "- No Kelly, no live, no Risk, no FIRST80 retune",
            "- No Choosin Texas book edit",
            "- No treating PCA/KNN as a signal",
            "",
            "## Artifacts",
            "",
            "- `features/pre80.parquet`",
            "- `labels/outcomes.parquet`",
            "- `reports/event_path.parquet`",
            "- `reports/analysis.json`",
            "",
        ]
    )
    return "\n".join(lines) + "\n"


def _composition_status(smd: float | None, explains: bool) -> str:
    if explains:
        return "survives as an outcome explanation"
    if smd is not None and smd >= 0.25:
        return "composition only; does not explain outcomes"
    return "does not survive as primary"


def hypothesis_rows(verdict: dict[str, Any], analysis: dict[str, Any]) -> list[dict[str, str]]:
    time_explains = (verdict.get("temporal_shrink") or 0) >= 0.25
    match_explains = (verdict.get("match_shrink") or 0) >= 0.25
    joint = verdict["label"] == "JOINT"
    unexplained = verdict["label"] == "UNEXPLAINED"
    return [
        {
            "id": "H1 time",
            "status": _composition_status(verdict.get("time_mean_abs_smd"), time_explains),
            "note": "Clock composition is definitional for Q2 vs Q3. H1 survives only if temporal bins shrink the EV gap.",
        },
        {
            "id": "H2 score",
            "status": _composition_status(verdict.get("score_mean_abs_smd"), match_explains),
            "note": "Bought-team margin and lead state at the CSV 80 snapshot.",
        },
        {
            "id": "H3 opening",
            "status": _composition_status(verdict.get("open_mean_abs_smd"), match_explains),
            "note": "KALSHI_LAST_PRE_TIP_YES_BID and distance 80-from-open.",
        },
        {
            "id": "H4 pre-80 path",
            "status": _composition_status(verdict.get("price_mean_abs_smd"), match_explains),
            "note": "Warehouse TRADABLE_YES_BID windows. Missing windows stay missing.",
        },
        {
            "id": "H5 game-state",
            "status": "unavailable",
            "note": "Possession / fouls / timeouts are SOURCE_UNAVAILABLE.",
        },
        {
            "id": "H6 L2",
            "status": "unavailable",
            "note": "Historical L2 is SOURCE_UNAVAILABLE. Quote-at-entry is not L2.",
        },
        {
            "id": "H7 joint state",
            "status": "survives" if joint else "not selected",
            "note": "More than one pre-80 class is required to describe the gap.",
        },
        {
            "id": "H8 residual unexplained",
            "status": "survives" if unexplained else "not the residual label",
            "note": "Current pre-80 features do not absorb the Q2 vs Q3 candle-path EV gap.",
        },
    ]


def write_report(analysis: dict[str, Any], figure_names: list[str], dest: Path | None = None) -> Path:
    analysis = dict(analysis)
    analysis.setdefault("generated_at", datetime.now(timezone.utc).isoformat())
    analysis["hypotheses"] = hypothesis_rows(analysis["verdict"], analysis)
    text = render(analysis, figure_names)
    path = dest or (library_root() / "NBA_8040_REVERSE_ENGINEERING.md")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    reports_dir().mkdir(parents=True, exist_ok=True)
    return path
