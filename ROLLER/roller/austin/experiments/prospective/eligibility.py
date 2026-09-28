"""Prospective eligibility. Events before the lock never enter scoring."""

from __future__ import annotations

INELIGIBLE = "INELIGIBLE_FOR_PHASE7"
BACKGROUND_ONLY = "BACKGROUND_ONLY"


def classify_event(observed_at: str | None, lock_timestamp: str | None) -> str:
    if not observed_at or not lock_timestamp:
        return INELIGIBLE
    if observed_at < lock_timestamp:
        return INELIGIBLE
    return "ELIGIBLE"


def assert_prediction_before_outcome(observed_at: str, outcome_available_at: str) -> bool:
    return observed_at < outcome_available_at
