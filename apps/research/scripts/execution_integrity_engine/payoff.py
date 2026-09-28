"""Trade-level payoff classes. Multiple dimensions, not one compressed string."""

from __future__ import annotations

from .enums import (
    AMBIGUOUS_OPPORTUNITY,
    AMBIGUOUS_SEQUENCE,
    GAP_MISS_FALLBACK,
    GAP_THROUGH,
    LEAK_HOLD,
    LOSS_AFTER_HEDGE,
    NO_HEDGE_OPPORTUNITY,
    NO_OBSERVATION,
    STOP_LOSS,
    WIN_AFTER_HEDGE,
    WIN_NO_INTERVENTION,
)


def payoff_class(won: bool, stop: bool, l2: dict, e1: dict) -> str:
    if e1.get("hedge_filled"):
        return WIN_AFTER_HEDGE if won else LOSS_AFTER_HEDGE
    if l2["opportunity_class"] == AMBIGUOUS_SEQUENCE:
        return AMBIGUOUS_OPPORTUNITY
    if l2["opportunity_class"] == GAP_THROUGH:
        return GAP_MISS_FALLBACK
    if l2["opportunity_class"] == NO_OBSERVATION:
        if stop:
            return STOP_LOSS
        return WIN_NO_INTERVENTION if won else LEAK_HOLD
    if stop:
        return STOP_LOSS
    if won:
        return WIN_NO_INTERVENTION
    return NO_HEDGE_OPPORTUNITY
