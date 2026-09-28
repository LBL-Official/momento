"""Canonical V1 dual-leg portfolio arithmetic.

Lock identity L(p) = 20 - p applies to every paired unit, not only full hedge.
"""

from __future__ import annotations

from typing import Any

ENTRY_CENTS = 80
LOCK_GAIN_CENTS = 20
EXECUTION_ASSUMPTION = "THEORETICAL"
BASIS = "CANDLE_PATH"


def lock_cents(hedge_price_cents: int) -> int:
    return LOCK_GAIN_CENTS - int(hedge_price_cents)


def rho(q_hedge: int, q_dir: int) -> float | None:
    n = int(q_dir)
    q = int(q_hedge)
    if n <= 0:
        return None
    if q < 0 or q > n:
        raise ValueError("q_hedge must be in [0, q_dir]")
    return q / n


def evaluate_candidate(
    *,
    q_dir: int,
    q_hedge: int,
    hedge_price_cents: int,
    a_t: float,
    a_l: float | None,
    weighted_t40_rate: float | None,
    research_unit_qty: int = 1,
) -> dict[str, Any]:
    n = int(q_dir)
    q = int(q_hedge)
    if n <= 0:
        raise ValueError("q_dir must be a positive integer")
    if q < 0 or q > n:
        raise ValueError("q_hedge must be in [0, q_dir]")
    p = int(hedge_price_cents)
    residual = n - q
    paired_lock = lock_cents(p)
    directional_retained = residual * float(a_t)
    paired_lock_value = q * paired_lock
    ev_before = n * float(a_t)
    portfolio_ev_after = directional_retained + paired_lock_value
    economic_cost = ev_before - portfolio_ev_after
    robust_before = None if a_l is None else n * float(a_l)
    robust_after = None if a_l is None else residual * float(a_l) + paired_lock_value
    t40 = None if weighted_t40_rate is None else float(weighted_t40_rate)
    risk_before = None if t40 is None else t40 * n
    risk_after = None if t40 is None else t40 * residual
    risk_removed = None if t40 is None else risk_before - risk_after
    ratio = rho(q, n)
    robust_after = None if a_l is None else residual * float(a_l) + paired_lock_value
    return {
        "research_unit_qty": int(research_unit_qty),
        "q_dir": n,
        "q_hedge": q,
        "rho": ratio,
        "residual_qty": residual,
        "hedge_price_cents": p,
        "assumed_hedge_price_cents": p,
        "paired_lock_cents": paired_lock,
        "austin_alpha_cents": float(a_t),
        "austin_alpha_per_unit": float(a_t),
        "austin_robust_alpha_cents": None if a_l is None else float(a_l),
        "austin_robust_alpha_per_unit": None if a_l is None else float(a_l),
        "ev_before": ev_before,
        "portfolio_ev_before": ev_before,
        "directional_alpha_exposure_retained": directional_retained,
        "paired_lock_value": paired_lock_value,
        "portfolio_EV_after": portfolio_ev_after,
        "portfolio_ev_after": portfolio_ev_after,
        "robust_EV_before": robust_before,
        "robust_portfolio_ev_before": robust_before,
        "robust_portfolio_EV_after": robust_after,
        "robust_portfolio_ev_after": robust_after,
        "directional_alpha_removed": q * float(a_t),
        "economic_EV_cost_of_hedge": economic_cost,
        "economic_ev_cost_of_hedge": economic_cost,
        "risk_metric": "T40_RISK_PROXY",
        "risk_metric_name": "T40_RISK_PROXY",
        "risk_before": risk_before,
        "risk_after": risk_after,
        "risk_removed": risk_removed,
        "is_robust_positive": robust_after is not None and float(robust_after) > 0,
        "price_relevant": q > 0,
        "execution_assumption": EXECUTION_ASSUMPTION,
        "basis": BASIS,
        "fill_claimed": False,
    }
