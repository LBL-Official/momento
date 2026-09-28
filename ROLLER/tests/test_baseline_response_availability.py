"""V3 two-clock baseline test. observation_time < t is not enough."""

from __future__ import annotations

from roller.measurement.eligibility import baseline_eligible


def _row():
    return {
        "observation_time": "2025-12-20T10:00:00Z",
        "response_available_at": "2025-12-20T10:05:00Z",
        "measurement_name": "market_response_5m",
        "value": 10,
    }


def test_response_not_eligible_before_it_is_available():
    a = _row()
    assert baseline_eligible(a, observation_time_t="2025-12-20T10:02:00Z") is False


def test_equality_on_response_available_at_is_hidden():
    a = _row()
    assert baseline_eligible(a, observation_time_t="2025-12-20T10:05:00Z") is False


def test_eligible_only_after_both_clocks_pass():
    a = _row()
    assert baseline_eligible(a, observation_time_t="2025-12-20T10:06:00Z") is True
