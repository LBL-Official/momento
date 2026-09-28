"""Leakage guards. Feature timestamp <= decision timestamp. No outcomes in PCA."""

from __future__ import annotations

from typing import Any

from roller.austin.errors import AustinError
from roller.austin.registry import load_registry


FORBIDDEN_FEATURE_NAMES = frozenset(
    {
        "final_pnl",
        "final_pnl_per_contract",
        "final_pnl_trade",
        "settlement",
        "terminal_yes",
        "future_price",
        "future_score",
        "t40_outcome",
        "hedge_fill_observed",
        "hit_40_after",
    }
)


def assert_registry_clean(registry: dict[str, Any] | None = None) -> None:
    reg = registry or load_registry()
    leaked = []
    for spec in reg["features"]:
        if spec.outcome_derived and (spec.used_in_pca or spec.used_in_knn):
            leaked.append(spec.name)
        if spec.name in FORBIDDEN_FEATURE_NAMES and (spec.used_in_pca or spec.used_in_knn):
            leaked.append(spec.name)
    if leaked:
        raise AustinError("LEAKAGE", f"outcome features in PCA/KNN: {leaked}")


def assert_feature_timestamp(availability: str, decision: str) -> None:
    if availability > decision:
        raise AustinError("LEAKAGE", f"feature_timestamp {availability} > decision {decision}")


def assert_train_before_eval(train_date: str, eval_date: str) -> None:
    if not train_date or not eval_date or train_date >= eval_date:
        raise AustinError("LEAKAGE", f"train {train_date!r} is not strictly before eval {eval_date!r}")
