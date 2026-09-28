"""Inference assembly. Each CI names its statistical object."""

from __future__ import annotations

from typing import Any

from roller.results_math.bootstrap import bootstrap_returns
from roller.results_math.models import DERIVED, UNAVAILABLE
from roller.results_math.proportions import clopper_pearson, wilson_interval
from roller.results_math.returns import trade_sharpe
from roller.results_math.versions import BOOTSTRAP_ITERATIONS, BOOTSTRAP_SEED, CONFIDENCE_LEVEL, WILSON_Z


def inference_block(
    *,
    successes: int | None,
    n: int | None,
    returns: list[float],
    groups: list[list[float]] | None,
    ev_ci: dict[str, Any] | None,
    date_groups: list[list[float]] | None = None,
) -> dict[str, Any]:
    wilson = wilson_interval(successes, n) if successes is not None and n else None
    exact = clopper_pearson(successes, n) if successes is not None and n else None
    boot = bootstrap_returns(returns, groups=groups, date_groups=date_groups)
    return {
        "status": DERIVED,
        "confidence_level": CONFIDENCE_LEVEL,
        "wilson": wilson,
        "clopper_pearson": exact,
        "wilson_z": WILSON_Z,
        "mean_ci": ev_ci,
        "observation_ci": {
            "status": DERIVED if ev_ci else UNAVAILABLE,
            "label": "IID-like observation inference",
            "ci95": ev_ci,
        },
        "game_cluster_ci": boot.get("game_cluster"),
        "date_cluster_ci": boot.get("date_cluster"),
        "bootstrap": boot,
        "sharpe_point": trade_sharpe(returns),
        "bootstrap_iterations": BOOTSTRAP_ITERATIONS,
        "bootstrap_seed": BOOTSTRAP_SEED,
        "note": "Wilson is a CI for a binomial proportion, not for edge. t-interval assumes an IID-like mean. Cluster CIs are a separate object.",
    }
