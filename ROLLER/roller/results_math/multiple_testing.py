"""Discovery audit. Do not auto-apply to every Results page."""

from __future__ import annotations

from typing import Any

from roller.results_math.models import DERIVED


def bonferroni(p_values: list[float], alpha: float = 0.05) -> list[float]:
    m = max(len(p_values), 1)
    return [min(1.0, p * m) for p in p_values]


def holm(p_values: list[float], alpha: float = 0.05) -> list[float]:
    m = len(p_values)
    if m == 0:
        return []
    order = sorted(range(m), key=lambda i: p_values[i])
    adj = [0.0] * m
    running = 0.0
    for rank, i in enumerate(order):
        val = min(1.0, p_values[i] * (m - rank))
        running = max(running, val)
        adj[i] = running
    return adj


def benjamini_hochberg(p_values: list[float]) -> list[float]:
    m = len(p_values)
    if m == 0:
        return []
    order = sorted(range(m), key=lambda i: p_values[i])
    adj = [0.0] * m
    prev = 1.0
    for rank in range(m, 0, -1):
        i = order[rank - 1]
        val = min(prev, p_values[i] * m / rank)
        adj[i] = val
        prev = val
    return adj


def disclose(n_hypotheses: int, *, family: str, method: str | None = None) -> dict[str, Any]:
    return {
        "status": DERIVED,
        "label": "MULTIPLE TESTING DISCLOSURE",
        "hypotheses_inspected": int(n_hypotheses),
        "family": family,
        "correction_method": method,
        "note": "Discovery result ≠ validated result. Best historical bucket is not a structural effect.",
    }
