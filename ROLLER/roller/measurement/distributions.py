"""Conditional distribution summaries. Not an edge."""

from __future__ import annotations

from typing import Any

from roller.measurement.integers import mean_exact


def _quantile(sorted_vals: list[int], q_num: int, q_den: int) -> int | None:
    if not sorted_vals:
        return None
    # index = floor((n-1) * q_num / q_den)
    n = len(sorted_vals)
    idx = ((n - 1) * q_num) // q_den
    return sorted_vals[idx]


def summarize_values(
    values: list[int],
    *,
    measurement: str,
    horizon: str,
    condition_id: str,
    measurement_version: str = "v1",
) -> dict[str, Any]:
    ordered = sorted(values)
    mean = mean_exact(values)
    return {
        "measurement": measurement,
        "horizon": horizon,
        "condition_id": condition_id,
        "measurement_version": measurement_version,
        "count": len(values),
        "mean": mean,
        "median": _quantile(ordered, 1, 2),
        "minimum": ordered[0] if ordered else None,
        "maximum": ordered[-1] if ordered else None,
        "quantile_05": _quantile(ordered, 5, 100),
        "quantile_25": _quantile(ordered, 25, 100),
        "quantile_50": _quantile(ordered, 50, 100),
        "quantile_75": _quantile(ordered, 75, 100),
        "quantile_95": _quantile(ordered, 95, 100),
        "standard_deviation": None,
        "standard_deviation_status": "NOT_IMPLEMENTED",
        "note": "distribution summary is not an edge",
    }
