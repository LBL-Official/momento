"""AND = ticker-path set intersection. Funnel denominators are first-class.

A ∩ B == B ∩ A. Display order must not change the final identity set.
Cross-ticker / game-level mixes are not inferred here — caller raises
OPERATION_REQUIRED before calling intersect if scopes are incompatible.
"""

from __future__ import annotations

from typing import Iterable

from roller.research_query.models import FunnelStep


def intersect_tickers(
    layers: list[tuple[str, str, set[str]]],
    *,
    universe_n: int,
) -> tuple[set[str], list[FunnelStep]]:
    """layers: (condition_id, label, qualifying ticker set)."""
    if not layers:
        return set(), [FunnelStep(condition_id="universe", label="Universe", qualifying=universe_n)]
    identity: set[str] | None = None
    funnel: list[FunnelStep] = [
        FunnelStep(condition_id="universe", label="Universe", qualifying=universe_n)
    ]
    before = universe_n
    for cid, label, tickers in layers:
        funnel.append(
            FunnelStep(
                condition_id=cid,
                label=label,
                qualifying=len(tickers),
                population_before=before,
            )
        )
        identity = tickers if identity is None else identity & tickers
        before = len(identity)
    assert identity is not None
    funnel.append(
        FunnelStep(
            condition_id="intersection",
            label="Intersection",
            qualifying=len(identity),
            population_before=universe_n,
        )
    )
    return identity, funnel


def commute_ok(a: Iterable[str], b: Iterable[str]) -> bool:
    sa, sb = set(a), set(b)
    return (sa & sb) == (sb & sa)
