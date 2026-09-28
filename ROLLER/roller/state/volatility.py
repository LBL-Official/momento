"""Backward margin volatility. Integer score changes only."""

from __future__ import annotations


def margin_volatility(margins: list[int]) -> dict:
    if len(margins) < 2:
        return {"abs_change_sum": 0, "max_abs_change": 0, "n_changes": 0, "status": "known_missing"}
    diffs = [abs(margins[i] - margins[i - 1]) for i in range(1, len(margins))]
    return {
        "abs_change_sum": int(sum(diffs)),
        "max_abs_change": int(max(diffs)),
        "n_changes": len(diffs),
        "status": "observed",
    }
