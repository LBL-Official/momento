"""Realized-EV surface. All outputs are scenario math, not forecasts."""

from __future__ import annotations

from dataclasses import dataclass

from common import (
    ENTRY_CENTS,
    R_UNIT_CENTS,
    classify_region,
    ev_from_wl,
    p_break_even,
    winner_cents,
)
from fee_models import FeeQuote, get_model


@dataclass(frozen=True)
class TradePayoff:
    w_cents: float
    l_abs_cents: float
    w_R: float
    l_R: float
    p_be: float | None
    entry_fee_cents: float | None
    exit_fee_cents: float | None
    settlement_fee_cents: float | None
    fee_status: str
    fee_model_id: str


def quote_or_zero(q: FeeQuote) -> float | None:
    if q.status == "UNAVAILABLE":
        return None
    return float(q.amount_cents or 0.0)


def payoff(
    stop_cents: int,
    fee_model_id: str,
    contracts: int = 1,
    entry_cents: int = ENTRY_CENTS,
    entry_maker: bool = True,
    exit_maker: bool = False,
) -> TradePayoff:
    model = get_model(fee_model_id)
    entry = model.calculate_entry_fee(contracts, entry_cents, entry_maker)
    # Winner: hold to settlement — no exit trade fee in this research model.
    settle = model.calculate_settlement_fee(contracts)
    # Loser: taker (or stressed) exit at the assumed stop print.
    exit_q = model.calculate_exit_fee(contracts, stop_cents, exit_maker)
    if any(q.status == "UNAVAILABLE" for q in (entry, settle, exit_q)):
        w_gross = float(winner_cents(entry_cents))
        l_gross = float(entry_cents - stop_cents)
        return TradePayoff(
            w_cents=w_gross,
            l_abs_cents=l_gross,
            w_R=w_gross / R_UNIT_CENTS,
            l_R=l_gross / R_UNIT_CENTS,
            p_be=p_break_even(w_gross, l_gross),
            entry_fee_cents=None,
            exit_fee_cents=None,
            settlement_fee_cents=None,
            fee_status="UNAVAILABLE",
            fee_model_id=fee_model_id,
        )
    fe = float(entry.amount_cents or 0.0)
    fx = float(exit_q.amount_cents or 0.0)
    fs = float(settle.amount_cents or 0.0)
    w = winner_cents(entry_cents) - fe - fs
    l_abs = (entry_cents - stop_cents) + fe + fx
    return TradePayoff(
        w_cents=w,
        l_abs_cents=l_abs,
        w_R=w / R_UNIT_CENTS,
        l_R=l_abs / R_UNIT_CENTS,
        p_be=p_break_even(w, l_abs),
        entry_fee_cents=fe,
        exit_fee_cents=fx,
        settlement_fee_cents=fs,
        fee_status=model.status,
        fee_model_id=fee_model_id,
    )


def ev_filled_R(p_survive: float, pay: TradePayoff) -> float:
    return ev_from_wl(p_survive, pay.w_R, pay.l_R)


def ev_realized_R(
    p_survive: float,
    p_fill: float,
    alpha: float,
    pay: TradePayoff,
    c_entry_unfilled_R: float = 0.0,
    p_stop_fill: float = 1.0,
) -> float:
    """EV_realized = P(F)·α·EV_filled − C_unfilled.

    p_stop_fill < 1 does not invent a recovery: the residual is treated as
    the same loser payoff (conservative: stop still assumed to print at the
    scenario price). A missed stop is NOT modeled as a win.
    """
    ev_f = ev_filled_R(p_survive, pay)
    # If the stop does not fill, the research default keeps the loser on
    # the books at the scenario stop price (no invented worse/better fill).
    ev_f = ev_f * p_stop_fill + ev_f * (1.0 - p_stop_fill)
    return p_fill * alpha * ev_f - (1.0 - p_fill) * c_entry_unfilled_R


def ev_bankroll_fraction(ev_R: float, f_alloc: float) -> float:
    """Map R-units to bankroll fraction.

    1R = 20¢ on an 80¢ allocated contract → 0.25 of allocated capital.
    Bankroll increment ≈ f_alloc × EV_R × 0.25.
    """
    return f_alloc * ev_R * (R_UNIT_CENTS / 80.0)


def n_required(weekly_target: float, ev_bankroll: float) -> float | None:
    if ev_bankroll <= 0:
        return None
    return weekly_target / ev_bankroll


def surface_row(
    p_survive: float,
    p_fill: float,
    alpha: float,
    stop_cents: int,
    fee_model_id: str,
    p_stop_fill: float = 1.0,
    f_alloc: float = 0.05,
) -> dict:
    pay = payoff(stop_cents, fee_model_id)
    ev_f = ev_filled_R(p_survive, pay) if pay.fee_status != "UNAVAILABLE" else None
    ev_r = (
        ev_realized_R(p_survive, p_fill, alpha, pay, p_stop_fill=p_stop_fill)
        if ev_f is not None
        else None
    )
    ev_b = ev_bankroll_fraction(ev_r, f_alloc) if ev_r is not None else None
    return {
        "p_survive": p_survive,
        "p_entry_fill": p_fill,
        "p_stop_fill": p_stop_fill,
        "alpha_partial": alpha,
        "stop_cents": stop_cents,
        "fee_model_id": fee_model_id,
        "fee_model_status": pay.fee_status,
        "w_cents": pay.w_cents,
        "l_abs_cents": pay.l_abs_cents,
        "w_R": pay.w_R,
        "l_R": pay.l_R,
        "p_be_net": pay.p_be,
        "ev_filled_R": ev_f,
        "ev_realized_R": ev_r,
        "ev_bankroll_frac_at_f": ev_b,
        "f_alloc_research": f_alloc,
        "n_for_2pct_week": n_required(0.02, ev_b) if ev_b is not None else None,
        "n_for_1_5pct_week": n_required(0.015, ev_b) if ev_b is not None else None,
        "region": classify_region(ev_r) if ev_r is not None else "UNAVAILABLE",
        "label": "SIMULATED_EXECUTION_SCENARIO",
        "is_forecast": False,
    }
