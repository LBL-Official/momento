"""Minimum economically viable edge. Gross EV is not profit."""

from __future__ import annotations

from typing import Any

from roller.results_math.models import DERIVED, UNAVAILABLE


def economic_hurdle(gross_ev_cents: float | None) -> dict[str, Any]:
    if gross_ev_cents is None:
        return {
            "status": UNAVAILABLE,
            "reason": "No observed path EV to form a cost hurdle.",
            "platform_fees": {"status": UNAVAILABLE, "reason": "not measured"},
            "slippage": {"status": UNAVAILABLE, "reason": "not measured"},
            "fill_impact": {"status": UNAVAILABLE, "reason": "not measured"},
        }
    ev = float(gross_ev_cents)
    return {
        "status": DERIVED,
        "label": "MINIMUM ECONOMICALLY VIABLE EDGE · not profit",
        "observed_gross_ev_cents": ev,
        "break_even_total_cost_cents": ev,
        "max_cost_before_ev_zero_cents": ev,
        "platform_fees": {"status": UNAVAILABLE, "reason": "not measured"},
        "slippage": {"status": UNAVAILABLE, "reason": "not measured"},
        "fill_impact": {"status": UNAVAILABLE, "reason": "not measured"},
        "note": "Observed gross path EV is not profit. Fees, slippage, and fill impact are not measured.",
    }
