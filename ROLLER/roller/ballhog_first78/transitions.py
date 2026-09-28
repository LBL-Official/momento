"""Neighbor branch rates on the 67¢ stop. Not a Markov chain."""

from __future__ import annotations

from typing import Any

from roller.ballhog.models import TRANSITION_SCHEMA


def build_transitions(alpha: dict[str, Any]) -> dict[str, Any]:
    stop = alpha.get("weighted_t67_rate")
    survival = alpha.get("weighted_survival_rate")
    missing = stop is None and survival is None
    branches = []
    if survival is not None:
        branches.append({"label": "SURVIVAL_HOLD_BRANCH", "rate": survival, "source": "austin_match.weighted_survival_rate"})
    if stop is not None:
        branches.append({"label": "T67_DAMAGING_BRANCH", "rate": stop, "source": "austin_first78.weighted_T40_rate_is_67_stop"})
    return {
        "schema": TRANSITION_SCHEMA,
        "method": "AUSTIN_NEIGHBOR_BRANCH_RATES",
        "availability": "UNAVAILABLE" if missing else "OBSERVED",
        "sample_support": alpha.get("effective_sample_size"),
        "support": alpha.get("support"),
        "horizon": "neighbor_outcome_from_Xt",
        "branches": branches,
        "note": "Empirical KNN-neighbor 67¢-stop and survival rates. Not a live hedge trigger.",
    }
