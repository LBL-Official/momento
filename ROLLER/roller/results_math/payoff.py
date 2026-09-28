"""Explicit hypothetical payoff. Never overwrites observed path EV. Never invents settlement."""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_EVEN
from typing import Any

from roller.results_math.models import DERIVED, HYPOTHETICAL, INVALID_SEMANTICS, UNAVAILABLE
from roller.results_math.proportions import clopper_pearson, wilson_interval


def _d(v: float | int | Decimal) -> Decimal:
    return v if isinstance(v, Decimal) else Decimal(str(v))


def payoff_ev(
    p_win: float | Decimal,
    win_payoff_cents: float | int | Decimal,
    loss_payoff_cents: float | int | Decimal,
    p_loss: float | Decimal | None = None,
) -> Decimal:
    pw = _d(p_win)
    pl = _d(1) - pw if p_loss is None else _d(p_loss)
    return pw * _d(win_payoff_cents) + pl * _d(loss_payoff_cents)


def ev_from_probability(p: float, win_payoff_cents: float, loss_payoff_cents: float) -> float:
    """EV = l + p(w − l)."""
    return float(loss_payoff_cents) + float(p) * (float(win_payoff_cents) - float(loss_payoff_cents))


def transform_rate_interval_to_ev(
    interval: dict[str, Any] | None,
    win_payoff_cents: float,
    loss_payoff_cents: float,
) -> dict[str, Any] | None:
    if not interval or interval.get("lower") is None or interval.get("upper") is None:
        return None
    w = float(win_payoff_cents)
    loss = float(loss_payoff_cents)
    span = w - loss
    ev_lo = ev_from_probability(float(interval["lower"]), w, loss)
    ev_hi = ev_from_probability(float(interval["upper"]), w, loss)
    if span < 0:
        ev_lo, ev_hi = ev_hi, ev_lo
    return {
        "lower": ev_lo,
        "upper": ev_hi,
        "zero_inside_ci": ev_lo <= 0.0 <= ev_hi,
        "method": f"{interval.get('method', 'rate')}_transformed_ev",
        "confidence_level": interval.get("confidence_level"),
        "payoff_span_cents": span,
        "p_lower": interval.get("lower"),
        "p_upper": interval.get("upper"),
        "formula": "EV = l + p(w − l)",
        "note": "Finite-sample interval for book-price EV. Not P(EV > 0). Not a posterior.",
    }


def binary_trade_on_n(
    *,
    win_n: int | None,
    n: int | None,
    entry_cents: int | None,
) -> dict[str, Any]:
    """Headline backtest win rate and pre-fee binary breakeven on the same N.

    P(win) = wins / N. Breakeven before fees = entry/100 for a 100/0 contract.
    Hypothetical ¢/contract = 100·P(win) − entry. Non-win is treated as 0 settlement.
    LAST TRADE ≠ FILL. PATH FALSE is not Kalshi NO.
    """
    if win_n is None or n is None or int(n) <= 0 or entry_cents is None:
        return {
            "status": UNAVAILABLE,
            "reason": "Need wins, N, and an entry chip.",
        }
    p_win = int(win_n) / int(n)
    be = int(entry_cents) / 100.0
    ev = 100.0 * p_win - float(entry_cents)
    return {
        "status": HYPOTHETICAL,
        "label": "BACKTEST WIN · BREAKEVEN BEFORE FEES",
        "formula": "P(win)=wins/N · BE=entry/100 · EV=100·P(win)−entry · before fees",
        "n": int(n),
        "win_n": int(win_n),
        "entry_cents": int(entry_cents),
        "p_win": p_win,
        "breakeven_probability": be,
        "rate_margin_vs_breakeven": p_win - be,
        "ev_cents": ev,
        "before_fees": True,
        "note": (
            "Same-N win rate. Non-win is treated as 0 settlement for this ¢/contract. "
            "PATH FALSE is not LOSS_EXIT and is not Kalshi NO. LAST TRADE ≠ FILL. Fees are not subtracted."
        ),
    }


def decompose_on_n(
    *,
    win_n: int,
    loss_n: int,
    n: int,
    win_payoff_cents: int,
    loss_payoff_cents: int,
) -> dict[str, Any]:
    """Book-price EV on population N. Residual rows contribute 0, not a LOSS payoff."""
    if n <= 0:
        return {"status": UNAVAILABLE, "reason": "Population N is zero."}
    w = float(win_payoff_cents)
    loss = float(loss_payoff_cents)
    if w <= loss:
        return {
            "status": INVALID_SEMANTICS,
            "reason": "WIN payoff <= LOSS payoff. Breakeven is undefined.",
            "n": n,
            "win_n": win_n,
            "loss_n": loss_n,
        }
    p_w = win_n / n
    p_l = loss_n / n
    ev = payoff_ev(p_w, w, loss, p_l)
    be = breakeven_probability(w, loss)
    wilson = wilson_interval(win_n, n)
    exact = clopper_pearson(win_n, n)
    return {
        "status": HYPOTHETICAL,
        "label": "HYPOTHETICAL BOOK-PRICE EV · same N",
        "formula": "P(WIN)×(WIN−entry) + P(LOSS)×(LOSS−entry) on N. Residual payoff 0.",
        "n": n,
        "win_n": win_n,
        "loss_n": loss_n,
        "denominator": n,
        "win_probability": p_w,
        "loss_probability": p_l,
        "win_payoff_cents": w,
        "loss_payoff_cents": loss,
        "ev_cents": float(ev),
        "breakeven_probability": be,
        "rate_margin_vs_breakeven": None if be is None else p_w - be,
        "wilson": wilson,
        "clopper_pearson": exact,
        "wilson_ev_ci": transform_rate_interval_to_ev(wilson, w, loss),
        "exact_binomial_ev_ci": transform_rate_interval_to_ev(exact, w, loss),
        "note": (
            "Wins and losses use the same N. Unclassified rows are not scored as LOSS. "
            "Not a fill. P(WIN) ≠ EV."
        ),
    }


def breakeven_probability(win_payoff_cents: int | float, loss_payoff_cents: int | float) -> float | None:
    """p_BE = −l / (w − l) when w > l."""
    w = float(win_payoff_cents)
    loss = float(loss_payoff_cents)
    if w <= loss:
        return None
    return -loss / (w - loss)


def binary_settlement_payoffs(entry_cents: int) -> tuple[int, int]:
    """WIN = 100 − K, LOSS = −K. MODEL-ASSUMED 1/0 settlement, not observed settlement."""
    return 100 - int(entry_cents), -int(entry_cents)


def book_payoffs(entry_cents: int, win_cents: int, loss_cents: int) -> tuple[int, int]:
    return int(win_cents) - int(entry_cents), int(loss_cents) - int(entry_cents)


def decompose(
    *,
    win_n: int,
    loss_n: int,
    win_payoff_cents: int,
    loss_payoff_cents: int,
) -> dict[str, Any]:
    classified = win_n + loss_n
    if classified <= 0:
        return {"status": UNAVAILABLE, "reason": "No classified WIN/LOSS exits."}
    w = float(win_payoff_cents)
    loss = float(loss_payoff_cents)
    if w <= loss:
        return {
            "status": INVALID_SEMANTICS,
            "reason": "WIN payoff <= LOSS payoff. Breakeven and transformed EV CI are undefined.",
            "win_n": win_n,
            "loss_n": loss_n,
            "win_payoff_cents": w,
            "loss_payoff_cents": loss,
        }
    p_w = win_n / classified
    p_l = loss_n / classified
    ev = payoff_ev(p_w, w, loss, p_l)
    win_contrib = _d(p_w) * _d(w)
    loss_contrib = _d(p_l) * _d(loss)
    be = breakeven_probability(w, loss)
    wilson = wilson_interval(win_n, classified)
    exact = clopper_pearson(win_n, classified)
    wilson_ev = transform_rate_interval_to_ev(wilson, w, loss)
    exact_ev = transform_rate_interval_to_ev(exact, w, loss)
    margin = None if be is None else p_w - be
    return {
        "status": HYPOTHETICAL,
        "label": "HYPOTHETICAL PAYOFF EV",
        "formula": "P(WIN)×(WIN_price − entry) + P(LOSS)×(LOSS_price − entry)",
        "win_n": win_n,
        "loss_n": loss_n,
        "denominator": classified,
        "win_probability": p_w,
        "loss_probability": p_l,
        "win_payoff_cents": w,
        "loss_payoff_cents": loss,
        "win_contribution_cents": float(win_contrib),
        "loss_contribution_cents": float(loss_contrib),
        "ev_cents": float(ev),
        "breakeven_probability": be,
        "rate_margin_vs_breakeven": margin,
        "wilson": wilson,
        "clopper_pearson": exact,
        "wilson_ev_ci": wilson_ev,
        "exact_binomial_ev_ci": exact_ev,
        "note": "Applies specified payoffs to empirical WIN/LOSS rates. Not observed path EV. Not a fill. P(WIN) ≠ EV.",
    }


def settlement_payoff(
    *,
    yes_n: int | None,
    no_n: int | None,
    missing: int,
    entry_cents: int,
) -> dict[str, Any]:
    if yes_n is None or no_n is None:
        return {
            "status": UNAVAILABLE,
            "reason": "TERMINAL DATA UNAVAILABLE. Missing settlement is not NO and is not path WIN.",
            "terminal_missing": missing,
        }
    avail = yes_n + no_n
    if avail <= 0:
        return {
            "status": UNAVAILABLE,
            "reason": "TERMINAL DATA UNAVAILABLE. Missing settlement is not NO and is not path WIN.",
            "terminal_missing": missing,
        }
    win_p, loss_p = binary_settlement_payoffs(entry_cents)
    d = decompose(win_n=yes_n, loss_n=no_n, win_payoff_cents=win_p, loss_payoff_cents=loss_p)
    d["label"] = "SETTLEMENT PAYOFF EV · measured Kalshi YES/NO only"
    d["status"] = DERIVED
    d["terminal_missing"] = missing
    d["note"] = "Uses measured settlement only. Path WIN/LOSS rates are not substituted."
    return d


def ev_vs_zero(ci: dict[str, Any] | None, estimate: float | None) -> dict[str, Any]:
    if estimate is None or ci is None or ci.get("lower") is None or ci.get("upper") is None:
        return {
            "status": UNAVAILABLE,
            "reason": "EV interval not available.",
            "p_ev_gt_zero": {"status": "NOT_COMPUTED", "reason": "Not a posterior probability."},
        }
    lo, hi = float(ci["lower"]), float(ci["upper"])
    zero_inside = lo <= 0.0 <= hi
    if lo > 0:
        verdict = "POSITIVE EV · CI EXCLUDES ZERO"
    elif hi < 0:
        verdict = "NEGATIVE EV · CI EXCLUDES ZERO"
    elif estimate > 0:
        verdict = "POSITIVE POINT ESTIMATE · NOT STATISTICALLY DISTINGUISHABLE FROM ZERO"
    elif estimate < 0:
        verdict = "NEGATIVE POINT ESTIMATE · NOT STATISTICALLY DISTINGUISHABLE FROM ZERO"
    else:
        verdict = "ZERO POINT ESTIMATE · CI INCLUDES ZERO"
    return {
        "status": DERIVED,
        "verdict": verdict,
        "estimate": estimate,
        "standard_error": ci.get("standard_error"),
        "t_statistic": ci.get("t_statistic"),
        "p_value": ci.get("p_value"),
        "df": ci.get("df"),
        "null": ci.get("null") or "EV = 0",
        "lower": lo,
        "upper": hi,
        "zero_inside_ci": zero_inside,
        "p_ev_gt_zero": {
            "status": "NOT_COMPUTED",
            "reason": "Frequentist test is H0: EV = 0. P(EV > 0) is not a posterior.",
        },
        "note": "Not a trading recommendation. Not P(profit).",
    }


BINARY_ENTRY_GRID = (50, 55, 60, 65, 70, 75, 80, 85)


def binary_entry_sensitivity(
    p_win: float | None,
    *,
    entries: tuple[int, ...] = BINARY_ENTRY_GRID,
) -> dict[str, Any]:
    """HYPOTHETICAL binary 100/0 at assumed entries. Not Kalshi settlement. Not book chips."""
    if p_win is None:
        return {"status": UNAVAILABLE, "reason": "Need an observed WIN rate."}
    rows = []
    for k in entries:
        ev = 100.0 * float(p_win) - float(k)
        be = k / 100.0
        rows.append(
            {
                "entry_cents": k,
                "breakeven": be,
                "observed_win": float(p_win),
                "margin": float(p_win) - be,
                "payoff_ev_cents": ev,
            }
        )
    return {
        "status": HYPOTHETICAL,
        "label": "HYPOTHETICAL BINARY 100/0 · observed WIN rate held fixed · not settlement",
        "observed_win": float(p_win),
        "rows": rows,
        "note": "Same historical WIN rate can be attractive at one entry and negative at another. P(WIN) ≠ EV.",
    }


def binary_entry_continuum(
    p_win: float | None,
    *,
    lo: int = 1,
    hi: int = 99,
) -> dict[str, Any]:
    """HYPOTHETICAL binary 100/0 at every integer entry. Not settlement. Not a forecast."""
    if p_win is None or not 0.0 <= float(p_win) <= 1.0:
        return {"status": UNAVAILABLE, "reason": "Need an observed WIN rate."}
    p = float(p_win)
    be_entry = 100.0 * p
    rows = []
    for k in range(int(lo), int(hi) + 1):
        rows.append(
            {
                "entry_cents": k,
                "breakeven": k / 100.0,
                "observed_win": p,
                "margin": p - k / 100.0,
                "payoff_ev_cents": 100.0 * p - float(k),
            }
        )
    return {
        "status": HYPOTHETICAL,
        "label": "HYPOTHETICAL BINARY 100/0 · 1¢ entry continuum · not settlement",
        "observed_win": p,
        "breakeven_entry_cents": be_entry,
        "lo_cents": int(lo),
        "hi_cents": int(hi),
        "rows": rows,
        "note": "Increasing entry by 1¢ decreases binary EV by exactly 1¢. Not a future probability.",
    }


PAYOFF_ENTRY_GRID = (55, 60, 65, 70, 75, 80, 85)
PAYOFF_WIN_GRID = (80, 85, 90, 95, 100)
PAYOFF_LOSS_GRID = (0, 15, 25, 35, 50)


def payoff_chip_sensitivity(
    p_win: float | None,
    *,
    entries: tuple[int, ...] = PAYOFF_ENTRY_GRID,
    win_exits: tuple[int, ...] = PAYOFF_WIN_GRID,
    loss_exits: tuple[int, ...] = PAYOFF_LOSS_GRID,
) -> dict[str, Any]:
    if p_win is None:
        return {"status": UNAVAILABLE, "reason": "Need an observed WIN rate."}
    p = float(p_win)
    cells = []
    for entry in entries:
        for win_px in win_exits:
            for loss_px in loss_exits:
                w, loss = book_payoffs(entry, win_px, loss_px)
                if w <= loss:
                    cells.append(
                        {
                            "entry_cents": entry,
                            "win_price_cents": win_px,
                            "loss_price_cents": loss_px,
                            "status": INVALID_SEMANTICS,
                            "reason": "WIN payoff <= LOSS payoff",
                        }
                    )
                    continue
                cells.append(
                    {
                        "entry_cents": entry,
                        "win_price_cents": win_px,
                        "loss_price_cents": loss_px,
                        "win_payoff_cents": w,
                        "loss_payoff_cents": loss,
                        "ev_cents": ev_from_probability(p, w, loss),
                        "breakeven_probability": breakeven_probability(w, loss),
                    }
                )
    return {
        "status": HYPOTHETICAL,
        "label": "HYPOTHETICAL PAYOFF SENSITIVITY · not a discovered edge · not ranked",
        "observed_win": p,
        "n_cells": len(cells),
        "cells": cells,
        "note": "No optimizer. No ALPHA. No ranking.",
    }


def book_entry_sensitivity(
    p_win: float | None,
    win_price_cents: int | None,
    loss_price_cents: int | None,
    *,
    entries: tuple[int, ...] = BINARY_ENTRY_GRID,
) -> dict[str, Any]:
    if p_win is None or win_price_cents is None or loss_price_cents is None:
        return {"status": UNAVAILABLE, "reason": "Need WIN rate and book chip prices."}
    rows = []
    for k in entries:
        rw, rl = book_payoffs(k, win_price_cents, loss_price_cents)
        ev = payoff_ev(p_win, rw, rl)
        be = breakeven_probability(rw, rl)
        rows.append(
            {
                "entry_cents": k,
                "win_payoff_cents": rw,
                "loss_payoff_cents": rl,
                "breakeven": be,
                "observed_win": float(p_win),
                "margin": (float(p_win) - be) if be is not None else None,
                "payoff_ev_cents": float(ev),
            }
        )
    return {
        "status": HYPOTHETICAL,
        "label": "HYPOTHETICAL BOOK-PRICE · chips fixed · entry varies",
        "win_price_cents": win_price_cents,
        "loss_price_cents": loss_price_cents,
        "rows": rows,
    }


def format_cents(value: Decimal | float, places: int = 2) -> str:
    q = Decimal(10) ** -places
    return str(_d(value).quantize(q, rounding=ROUND_HALF_EVEN))
