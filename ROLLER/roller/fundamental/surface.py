"""Surface support classification. Not a trading-quality rating."""

from __future__ import annotations

from typing import Any

SURFACE_CLASSES = (
    "ROBUST",
    "USABLE_WITH_LIMITATIONS",
    "SPARSE",
    "HEAVILY_FRAGMENTED",
    "NOT_SUPPORTED",
)


def _median(values: list[float]) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    mid = len(ordered) // 2
    if len(ordered) % 2:
        return float(ordered[mid])
    return (ordered[mid - 1] + ordered[mid]) / 2.0


def classify_surface(summary: dict[str, Any]) -> str:
    requested = int(summary.get("total_estimates_requested") or 0)
    supported = int(summary.get("supported_estimates") or 0)
    if requested <= 0 or supported <= 0:
        return "NOT_SUPPORTED"
    rate = supported / requested
    med_games = summary.get("median_n_unique_games")
    if rate < 0.15 or (med_games is not None and float(med_games) < 2):
        return "HEAVILY_FRAGMENTED"
    if rate < 0.40 or (med_games is not None and float(med_games) < 5):
        return "SPARSE"
    if rate < 0.75 or (med_games is not None and float(med_games) < 10):
        return "USABLE_WITH_LIMITATIONS"
    return "ROBUST"


def summarize_support_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    requested = len(rows)
    supported_rows = [r for r in rows if r.get("status") == "IMPLEMENTED"]
    unsupported = requested - len(supported_rows)
    games = [int(r.get("n_unique_games") or 0) for r in rows]
    obs = [int(r.get("n_observations") or 0) for r in rows]
    dates = [int(r.get("n_unique_dates") or 0) for r in rows]
    seasons = [int(r.get("n_unique_seasons") or 0) for r in rows]
    summary = {
        "total_estimates_requested": requested,
        "supported_estimates": len(supported_rows),
        "unsupported_estimates": unsupported,
        "null_rate": None if requested == 0 else unsupported / requested,
        "median_n_unique_games": _median([float(x) for x in games]),
        "median_n_observations": _median([float(x) for x in obs]),
        "median_n_unique_dates": _median([float(x) for x in dates]),
        "median_n_unique_seasons": _median([float(x) for x in seasons]),
    }
    summary["classification"] = classify_surface(summary)
    return summary
