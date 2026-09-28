"""Route RV: A_bid vs B_ask. Not an order."""

from __future__ import annotations

from fractions import Fraction
from typing import Any

from roller.tk_ultra.models import UNAVAILABLE, frac_decimal


def synthetic_a_exit(b_ask: Fraction) -> Fraction:
    return Fraction(100) - b_ask


def gross_route_edge(*, a_bid: Fraction, b_ask: Fraction) -> Fraction:
    return Fraction(100) - b_ask - a_bid


def route_parity_b(a_bid: Fraction) -> Fraction:
    return Fraction(100) - a_bid


def preference(edge: Fraction) -> str:
    if edge > 0:
        return "BUY_B_BETTER"
    if edge < 0:
        return "SELL_A_BETTER"
    return "PARITY"


def assess_route(*, a_bid: Fraction | None, b_ask: Fraction | None) -> dict[str, Any]:
    if a_bid is None or b_ask is None:
        return {
            "direct_exit_price": frac_decimal(a_bid, 4) if a_bid is not None else UNAVAILABLE,
            "synthetic_exit_price": frac_decimal(synthetic_a_exit(b_ask), 4) if b_ask is not None else UNAVAILABLE,
            "gross_route_edge": UNAVAILABLE,
            "route_preference": UNAVAILABLE,
            "b_route_parity_price": frac_decimal(route_parity_b(a_bid), 4) if a_bid is not None else UNAVAILABLE,
            "route_execution_quality": "OBSERVATIONAL_ONLY",
            "reason_codes": ["QUOTE_UNAVAILABLE"],
        }
    edge = gross_route_edge(a_bid=a_bid, b_ask=b_ask)
    pref = preference(edge)
    reasons = {
        "BUY_B_BETTER": "BUY_B_GROSS_ROUTE_BETTER",
        "SELL_A_BETTER": "SELL_A_GROSS_ROUTE_BETTER",
        "PARITY": "ROUTE_PARITY",
    }
    notes = {
        "BUY_B_BETTER": (
            "Gross route prefers buying B versus selling A at the bid. "
            "Relative preference. Not an order."
        ),
        "SELL_A_BETTER": (
            "Gross route prefers selling A at the bid versus buying B at the ask. "
            "Relative preference. Not an order."
        ),
        "PARITY": "Gross route is at parity. Relative preference does not choose a leg. Not an order.",
    }
    return {
        "direct_exit_price": frac_decimal(a_bid, 4),
        "synthetic_exit_price": frac_decimal(synthetic_a_exit(b_ask), 4),
        "gross_route_edge": frac_decimal(edge, 4),
        "route_preference": pref,
        "preference_note": notes[pref],
        "b_route_parity_price": frac_decimal(route_parity_b(a_bid), 4),
        "route_execution_quality": "OBSERVATIONAL_ONLY",
        "a_bid_basis": "YES_BID",
        "b_ask_basis": "YES_ASK",
        "reason_codes": [reasons[pref]],
    }
