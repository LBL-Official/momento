"""Effect size. Do not label a raw difference significant without a defined test."""

from __future__ import annotations

from typing import Any

from roller.results_math.models import DERIVED, UNAVAILABLE
from roller.results_math.proportions import wilson_interval


def proportion_effect(
    p_a: float,
    n_a: int,
    successes_a: int,
    p_b: float,
    n_b: int,
    successes_b: int,
) -> dict[str, Any]:
    if n_a <= 0 or n_b <= 0:
        return {"status": UNAVAILABLE, "reason": "Need both samples."}
    delta = p_a - p_b
    rel = (delta / p_b) if p_b else None
    return {
        "status": DERIVED,
        "absolute_difference": delta,
        "relative_difference": rel,
        "n_a": n_a,
        "n_b": n_b,
        "successes_a": successes_a,
        "successes_b": successes_b,
        "wilson_a": wilson_interval(successes_a, n_a),
        "wilson_b": wilson_interval(successes_b, n_b),
        "note": "Difference is not labeled significant without a defined test.",
    }


def mean_effect(mean_a: float | None, mean_b: float | None, *, contracts: int | None = None) -> dict[str, Any]:
    if mean_a is None or mean_b is None:
        return {"status": UNAVAILABLE, "reason": "Need both means."}
    delta = mean_a - mean_b
    return {
        "status": DERIVED,
        "ev_difference_cents": delta,
        "capitalized_difference_cents": (delta * contracts) if contracts else None,
        "note": "Economic difference is not a trading recommendation.",
    }
