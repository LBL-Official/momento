"""Pure clock isolation is not fabricated."""

from __future__ import annotations

from roller.greeks.theta import clock_isolation_status


def test_same_score_without_events_is_still_partial():
    out = clock_isolation_status(10, 10, n_events_in_window=0)
    assert out["status"] == "PARTIAL"
    assert out["pure_clock_isolation"] is False


def test_score_change_is_not_pure_clock():
    out = clock_isolation_status(10, 12, n_events_in_window=3)
    assert out["status"] == "PARTIAL"
    assert out["pure_clock_isolation"] is False
