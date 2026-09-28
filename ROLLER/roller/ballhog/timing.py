"""Timing from Austin evidence + policy.v1. 35–45 is not a price trigger."""

from __future__ import annotations

from typing import Any

from roller.ballhog.policy import BallhogPolicy

TIMING_STATES = ("RETAIN", "WATCH", "BEGIN_REDUCTION", "REDUCE", "NEUTRALIZE", "UNAVAILABLE")


def timing_decision(alpha: dict[str, Any], policy: BallhogPolicy) -> dict[str, Any]:
    rules = policy.timing
    reasons: list[str] = []
    a_l = alpha.get("a_l")
    delta = alpha.get("alpha_delta_from_entry")
    support = str(alpha.get("support") or "")
    if alpha.get("availability") != "OBSERVED" or alpha.get("a_t") is None:
        return {
            "timing_state": "UNAVAILABLE",
            "reason_codes": ["SOURCE_UNAVAILABLE"],
            "current_hedge_price": "UNAVAILABLE",
            "note": "Austin conditional alpha missing. Timing not inferred from 35–45 grid.",
        }
    low_support = support == "LOW HISTORICAL SUPPORT"
    if low_support:
        reasons.append("INSUFFICIENT_SUPPORT")
    robust_pos = a_l is not None and float(a_l) > 0
    if robust_pos:
        reasons.append("ROBUST_ALPHA_REMAINS_POSITIVE")
    delta_neg = delta is not None and float(delta) < 0
    delta_nonneg = delta is None or float(delta) >= 0
    if delta_neg:
        reasons.append("ALPHA_DETERIORATING")

    state = "WATCH"
    if rules.get("neutralize_if_robust_unhedged_nonpositive") and a_l is not None and float(a_l) <= 0:
        state = "NEUTRALIZE"
    elif (
        rules.get("retain_requires_robust_unhedged_positive")
        and robust_pos
        and (not rules.get("retain_requires_nonnegative_alpha_delta") or delta_nonneg)
        and (not rules.get("retain_requires_observed_support") or support == "OBSERVED")
    ):
        state = "RETAIN"
    elif rules.get("watch_if_low_support") and low_support and robust_pos:
        state = "WATCH"
    elif rules.get("begin_reduction_if_alpha_delta_negative") and robust_pos and delta_neg:
        state = "BEGIN_REDUCTION"
    elif robust_pos:
        state = "WATCH"
    else:
        state = "NEUTRALIZE"

    return {
        "timing_state": state,
        "reason_codes": reasons,
        "current_hedge_price": "UNAVAILABLE",
        "alpha_delta_from_entry": delta,
        "robust_unhedged": a_l,
        "support": support,
        "note": (
            "35–45 is a counterfactual hedge-price corridor, not an observed A2 print "
            "and not if A1<=55 / A2<=45."
        ),
    }
