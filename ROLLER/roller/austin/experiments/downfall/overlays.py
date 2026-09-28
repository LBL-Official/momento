"""CI and support overlays. They do not change core state."""

from __future__ import annotations

from typing import Any

from roller.austin.experiments.downfall.economics import _mean, _status, summarize_entries
from roller.austin.experiments.downfall.ids import (
    BOOTSTRAP_B,
    BOOTSTRAP_SEED,
    CI_CROSSES_ZERO,
    CI_NEGATIVE,
    LOW_HISTORICAL_SUPPORT,
    RISK_STATES,
)
from roller.austin.experiments.statistics import clustered_mean_diff


def ci_overlay_analysis(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for state in RISK_STATES:
        group = [e for e in entries if e["core_state"] == state]
        left = [e for e in group if e.get("CI_state") == CI_NEGATIVE]
        right = [e for e in group if e.get("CI_state") == CI_CROSSES_ZERO]
        rows = left + right
        for e in rows:
            e["_pnl"] = e.get("OUTCOME_pnl_hold_after_state")
        ci = clustered_mean_diff(
            rows,
            value_key="OUTCOME_pnl_hold_after_state",
            positive_pred=lambda r: r.get("CI_state") == CI_NEGATIVE,
            negative_pred=lambda r: r.get("CI_state") == CI_CROSSES_ZERO,
            seed=BOOTSTRAP_SEED,
            draws=BOOTSTRAP_B,
        )
        out.append(
            {
                "core_state": state,
                "n_CI_NEGATIVE": len(left),
                "n_CI_CROSSES_ZERO": len(right),
                "mean_pnl_CI_NEGATIVE": summarize_entries(left)["mean_pnl_hold_after_state"],
                "mean_pnl_CI_CROSSES_ZERO": summarize_entries(right)["mean_pnl_hold_after_state"],
                "observed_delta": ci.get("observed_delta"),
                "ci": ci.get("ci"),
                "classification": _status(ci, n_a=len(left), n_b=len(right)),
                "note": "CI overlay does not modify core_state.",
            }
        )
    return out


def support_overlay_analysis(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for state in RISK_STATES:
        group = [e for e in entries if e["core_state"] == state]
        n = len(group)
        low = sum(1 for e in group if e.get("support_state") == LOW_HISTORICAL_SUPPORT)
        out.append(
            {
                "core_state": state,
                "N_trades": n,
                "LOW_HISTORICAL_SUPPORT_rate": None if not n else low / n,
                "mean_ESS": _mean([e.get("ESS") for e in group]),
                "mean_distance": _mean([e.get("mean_distance") for e in group]),
                "median_distance": _mean([e.get("median_distance") for e in group]),
                "mean_feature_coverage": _mean([e.get("feature_coverage") for e in group]),
                "note": "Low-support rows remain included.",
            }
        )
    return out


def flatten_ci(experiment_id: str, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for row in rows:
        ci = row.get("ci") or [None, None]
        out.append(
            {
                "source_experiment_id": experiment_id,
                **row,
                "ci_lo": None if not ci else ci[0],
                "ci_hi": None if not ci else ci[1],
            }
        )
    return out


CI_FIELDS = [
    "source_experiment_id",
    "core_state",
    "n_CI_NEGATIVE",
    "n_CI_CROSSES_ZERO",
    "mean_pnl_CI_NEGATIVE",
    "mean_pnl_CI_CROSSES_ZERO",
    "observed_delta",
    "ci_lo",
    "ci_hi",
    "classification",
    "note",
]
SUPPORT_FIELDS = [
    "source_experiment_id",
    "core_state",
    "N_trades",
    "LOW_HISTORICAL_SUPPORT_rate",
    "mean_ESS",
    "mean_distance",
    "median_distance",
    "mean_feature_coverage",
    "note",
]
