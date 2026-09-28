"""Stop-equivalent hedge budget. Does not choose q*."""

from __future__ import annotations

from fractions import Fraction
from typing import Any

from roller.tk_ultra.models import UNAVAILABLE, frac_decimal, json_unavail

CENTS_DOMAIN = (Fraction(0), Fraction(100))


def locked_pnl(*, e_a: Fraction, b_avg: Fraction) -> Fraction:
    return Fraction(100) - e_a - b_avg


def stop_pnl(*, s_a: Fraction, e_a: Fraction) -> Fraction:
    return s_a - e_a


def b_stop_eq(*, s_a: Fraction) -> Fraction:
    return Fraction(100) - s_a


def improvement_vs_stop(*, b_stop: Fraction, b_avg: Fraction) -> Fraction:
    return b_stop - b_avg


def hedge_fraction(*, q_a: Fraction, q_b: Fraction) -> Fraction | None:
    if q_a <= 0:
        return None
    return q_b / q_a


def max_remaining_avg(
    *,
    f: Fraction | None,
    b_existing: Fraction | None,
    b_target: Fraction,
) -> Fraction | str:
    if f is None:
        return UNAVAILABLE
    if f >= 1:
        return UNAVAILABLE
    if f < 0:
        return UNAVAILABLE
    if f == 0:
        return b_target
    if b_existing is None:
        return UNAVAILABLE
    return (b_target - f * b_existing) / (1 - f)


def assess_budget(
    *,
    e_a: Fraction | None,
    s_a: Fraction | None,
    q_a: Fraction | None,
    q_b: Fraction | None,
    b_existing: Fraction | None,
    b_ask: Fraction | None,
) -> dict[str, Any]:
    reasons: list[str] = []
    if e_a is None or s_a is None:
        return {
            "stop_pnl_benchmark": UNAVAILABLE,
            "stop_equivalent_b_avg": UNAVAILABLE,
            "hedge_fraction": UNAVAILABLE,
            "remaining_fraction": UNAVAILABLE,
            "current_avg_b_price": json_unavail(b_existing),
            "max_remaining_avg_price": UNAVAILABLE,
            "hedge_runway_vs_ask": UNAVAILABLE,
            "cost_cushion_vs_existing_avg": UNAVAILABLE,
            "completed_now_b_avg": UNAVAILABLE,
            "locked_pnl_if_completed_now": UNAVAILABLE,
            "gross_improvement_vs_stop_if_completed_now": UNAVAILABLE,
            "fees": UNAVAILABLE,
            "slippage": UNAVAILABLE,
            "reason_codes": ["HEDGE_BUDGET_UNAVAILABLE"],
        }
    b_target = b_stop_eq(s_a=s_a)
    stop_loss = stop_pnl(s_a=s_a, e_a=e_a)
    q_a_v = q_a if q_a is not None else Fraction(1)
    q_b_v = q_b if q_b is not None else Fraction(0)
    frac = hedge_fraction(q_a=q_a_v, q_b=q_b_v)
    remaining = None if frac is None else (1 - frac)
    if q_b_v > 0 and b_existing is None:
        max_rem: Fraction | str = UNAVAILABLE
        reasons.append("EXISTING_B_AVG_UNAVAILABLE")
    else:
        max_rem = max_remaining_avg(f=frac, b_existing=b_existing, b_target=b_target)
        if max_rem != UNAVAILABLE:
            reasons.append("STOP_EQUIVALENT_BUDGET_AVAILABLE")
        if frac == 1:
            reasons.append("HEDGE_COMPLETE_NO_REMAINING")
    runway: Fraction | str = UNAVAILABLE
    cushion: Fraction | str = UNAVAILABLE
    if isinstance(max_rem, Fraction):
        if b_ask is not None:
            runway = max_rem - b_ask
            reasons.append("HEDGE_RUNWAY_POSITIVE" if runway > 0 else "HEDGE_RUNWAY_EXHAUSTED" if runway < 0 else "HEDGE_RUNWAY_PARITY")
        if b_existing is not None:
            cushion = max_rem - b_existing
    completed: Fraction | str = UNAVAILABLE
    locked: Fraction | str = UNAVAILABLE
    improve: Fraction | str = UNAVAILABLE
    if frac is not None and frac == 1 and b_existing is not None:
        completed = b_existing
    elif frac is not None and frac == 0 and b_ask is not None:
        completed = b_ask
    elif frac is not None and b_existing is not None and b_ask is not None and frac < 1:
        completed = frac * b_existing + (1 - frac) * b_ask
    if isinstance(completed, Fraction):
        locked = locked_pnl(e_a=e_a, b_avg=completed)
        improve = improvement_vs_stop(b_stop=b_target, b_avg=completed)
        if improve < 0:
            reasons.append("HEDGE_BUDGET_EXCEEDED")
    return {
        "a_entry": frac_decimal(e_a, 4),
        "a_stop_benchmark": frac_decimal(s_a, 4),
        "stop_pnl_benchmark": frac_decimal(stop_loss, 4),
        "stop_equivalent_b_avg": frac_decimal(b_target, 4),
        "current_a_qty": frac_decimal(q_a_v, 4),
        "current_b_qty": frac_decimal(q_b_v, 4),
        "hedge_fraction": frac_decimal(frac, 6) if frac is not None else UNAVAILABLE,
        "remaining_fraction": frac_decimal(remaining, 6) if remaining is not None else UNAVAILABLE,
        "current_avg_b_price": frac_decimal(b_existing, 4) if b_existing is not None else UNAVAILABLE,
        "max_remaining_avg_price": frac_decimal(max_rem, 6) if isinstance(max_rem, Fraction) else UNAVAILABLE,
        "hedge_runway_vs_ask": frac_decimal(runway, 6) if isinstance(runway, Fraction) else UNAVAILABLE,
        "cost_cushion_vs_existing_avg": frac_decimal(cushion, 6) if isinstance(cushion, Fraction) else UNAVAILABLE,
        "completed_now_b_avg": frac_decimal(completed, 6) if isinstance(completed, Fraction) else UNAVAILABLE,
        "locked_pnl_if_completed_now": frac_decimal(locked, 6) if isinstance(locked, Fraction) else UNAVAILABLE,
        "gross_improvement_vs_stop_if_completed_now": frac_decimal(improve, 6)
        if isinstance(improve, Fraction)
        else UNAVAILABLE,
        "fees": UNAVAILABLE,
        "slippage": UNAVAILABLE,
        "fill": UNAVAILABLE,
        "depth": UNAVAILABLE,
        "reason_codes": reasons,
    }
