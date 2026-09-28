"""Neighbor branch rates. Not a trained Markov chain. Not Λα."""

from __future__ import annotations

from typing import Any

from roller.ballhog.models import TRANSITION_SCHEMA


def build_transitions(alpha: dict[str, Any]) -> dict[str, Any]:
    t40 = alpha.get("weighted_t40_rate")
    survival = alpha.get("weighted_survival_rate")
    n_eff = alpha.get("effective_sample_size")
    support = alpha.get("support")
    missing = t40 is None and survival is None
    branches = []
    if survival is not None:
        branches.append(
            {
                "label": "SURVIVAL_HOLD_BRANCH",
                "rate": survival,
                "source": "austin_match.weighted_survival_rate",
            }
        )
    if t40 is not None:
        branches.append(
            {
                "label": "T40_DAMAGING_BRANCH",
                "rate": t40,
                "source": "austin_match.weighted_T40_rate",
            }
        )
    return {
        "schema": TRANSITION_SCHEMA,
        "method": "AUSTIN_NEIGHBOR_BRANCH_RATES",
        "not": ["Markov_P_Xt1_given_Xt", "lambda_alpha", "hazard_model"],
        "availability": "UNAVAILABLE" if missing else "OBSERVED",
        "sample_support": n_eff,
        "support": support,
        "horizon": "neighbor_outcome_from_Xt",
        "branches": branches,
        "note": (
            "Empirical KNN-neighbor T40 / survival rates at the queried state. "
            "Not P(Xt+1|Xt). Not a live hedge trigger."
        ),
    }
