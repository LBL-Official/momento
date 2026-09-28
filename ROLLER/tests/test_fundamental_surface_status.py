"""Surface classifier is a support rating, not a trading grade."""

from __future__ import annotations

from roller.fundamental.surface import classify_surface, summarize_support_rows


def test_classifier_buckets():
    assert classify_surface({"total_estimates_requested": 0, "supported_estimates": 0}) == "NOT_SUPPORTED"
    assert classify_surface({"total_estimates_requested": 100, "supported_estimates": 0}) == "NOT_SUPPORTED"
    assert (
        classify_surface({"total_estimates_requested": 100, "supported_estimates": 10, "median_n_unique_games": 1})
        == "HEAVILY_FRAGMENTED"
    )
    assert (
        classify_surface({"total_estimates_requested": 100, "supported_estimates": 30, "median_n_unique_games": 4})
        == "SPARSE"
    )
    assert (
        classify_surface({"total_estimates_requested": 100, "supported_estimates": 60, "median_n_unique_games": 8})
        == "USABLE_WITH_LIMITATIONS"
    )
    assert (
        classify_surface({"total_estimates_requested": 100, "supported_estimates": 90, "median_n_unique_games": 20})
        == "ROBUST"
    )


def test_summarize_sets_classification():
    rows = [
        {"status": "IMPLEMENTED", "n_unique_games": 12, "n_observations": 20, "n_unique_dates": 8, "n_unique_seasons": 1},
        {"status": "INSUFFICIENT_SUPPORT", "n_unique_games": 1, "n_observations": 2, "n_unique_dates": 1, "n_unique_seasons": 1},
    ]
    out = summarize_support_rows(rows)
    assert out["total_estimates_requested"] == 2
    assert out["supported_estimates"] == 1
    assert out["classification"] in {
        "ROBUST",
        "USABLE_WITH_LIMITATIONS",
        "SPARSE",
        "HEAVILY_FRAGMENTED",
        "NOT_SUPPORTED",
    }
