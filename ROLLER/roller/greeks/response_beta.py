"""Grouped response beta. Eligible forward responses only. No global black-box fit."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from roller.measurement.integers import mean_exact, parse_e4


def grouped_response_beta(rows: list[dict[str, Any]], *, x_field: str = "x", y_field: str = "value") -> dict[str, Any]:
    by_cond: dict[str, list[tuple[int, int]]] = defaultdict(list)
    for row in rows:
        x = parse_e4(row.get(x_field))
        y = parse_e4(row.get(y_field))
        if x is None or y is None:
            continue
        by_cond[str(row.get("condition_id") or "")] .append((x, y))
    groups = []
    for cond, pairs in sorted(by_cond.items()):
        xs = [p[0] for p in pairs]
        ys = [p[1] for p in pairs]
        groups.append(
            {
                "condition_id": cond,
                "n": len(pairs),
                "mean_x": mean_exact(xs),
                "mean_y": mean_exact(ys),
                "estimation_method": "grouped_means",
                "dependence_caveat": "observations nested in games; n is not independent trials",
            }
        )
    return {
        "response_variable": y_field,
        "explanatory_variable": x_field,
        "estimation_method": "conditional grouped estimates",
        "groups": groups,
        "note": "not a global regression; not an edge",
    }
