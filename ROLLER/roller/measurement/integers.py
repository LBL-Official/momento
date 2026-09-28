"""Integer E4 helpers. No floating-point money."""

from __future__ import annotations

from typing import Any


def parse_e4(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def mean_exact(values: list[int]) -> dict[str, int | str]:
    if not values:
        return {"sum": 0, "n": 0, "quotient": 0, "remainder": 0, "mean_status": "insufficient_history"}
    total = int(sum(values))
    n = len(values)
    return {
        "sum": total,
        "n": n,
        "quotient": total // n,
        "remainder": total % n,
        "mean_status": "observed",
    }
