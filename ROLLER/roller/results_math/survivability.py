"""Economic survivability facts. No quality score. No buy/sell."""

from __future__ import annotations

from typing import Any

from roller.results_math.formatting import format_signed_cents, format_signed_dollars
from roller.results_math.models import DERIVED, UNAVAILABLE


def _zero_inside(ci: dict[str, Any] | None) -> bool | None:
    if not ci or ci.get("lower") is None or ci.get("upper") is None:
        return None
    return float(ci["lower"]) <= 0.0 <= float(ci["upper"])


def survivability_summary(
    *,
    observed_ev_cents: float | None,
    observed_ci: dict[str, Any] | None,
    book_ev_cents: float | None,
    book_wilson_ev_ci: dict[str, Any] | None,
    break_even_cost_cents: float | None,
    capitalized_ev_dollars: float | None,
    capitalized_ci: dict[str, Any] | None,
    sharpe: float | None,
    sharpe_ci: dict[str, Any] | None,
    max_dd_dollars: float | None,
    terminal_status: str | None,
    observed_win: float | None,
    book_win: float | None,
    book_loss: float | None,
) -> dict[str, Any]:
    facts = {
        "gross_observed_ev_cents": observed_ev_cents,
        "book_price_ev_cents": book_ev_cents,
        "observed_ev_ci": observed_ci,
        "book_wilson_ev_ci": book_wilson_ev_ci,
        "break_even_total_cost_cents": break_even_cost_cents,
        "capitalized_expected_return_dollars": capitalized_ev_dollars,
        "capitalized_ev_ci": capitalized_ci,
        "sharpe": sharpe,
        "sharpe_ci": sharpe_ci,
        "max_historical_dd_dollars": max_dd_dollars,
        "terminal_availability": terminal_status,
    }
    parts: list[str] = []
    if observed_ev_cents is not None:
        zi = _zero_inside(observed_ci)
        ev_txt = format_signed_cents(observed_ev_cents)
        if zi is True:
            sign = "positive" if observed_ev_cents > 0 else "negative" if observed_ev_cents < 0 else "zero"
            parts.append(
                f"Observed path EV is {ev_txt} per contract. The estimate is {sign}, but the "
                "finite-sample confidence interval contains zero."
            )
        elif zi is False:
            side = "excludes zero on the positive side" if observed_ev_cents > 0 else "excludes zero on the negative side"
            parts.append(f"Observed path EV is {ev_txt} per contract and its finite-sample interval {side}.")
        else:
            parts.append(f"Observed path EV is {ev_txt} per contract.")
    if book_ev_cents is not None:
        chips = ""
        if book_win is not None and book_loss is not None:
            chips = f" under the specified {book_win:g}/{book_loss:g} payoff"
        rate = ""
        if observed_win is not None:
            rate = f" at a {observed_win * 100:.1f}% observed WIN rate"
        bzi = _zero_inside(book_wilson_ev_ci)
        if bzi is False and book_ev_cents > 0:
            parts.append(
                f"Book-price EV is positive at the point estimate{chips} and its finite-sample interval excludes zero."
            )
        elif bzi is True:
            parts.append(
                f"The specified book-price payoff produces {format_signed_cents(book_ev_cents)} "
                f"point-estimate EV{rate}{chips}, while the Wilson-transformed payoff interval also includes zero."
            )
        else:
            parts.append(f"Book-price EV is {format_signed_cents(book_ev_cents)}{chips}{rate}.")
    if capitalized_ev_dollars is not None:
        parts.append(
            f"At a hypothetical fixed allocation the capitalized observed-path mean is "
            f"{format_signed_dollars(capitalized_ev_dollars)}. This is a model-assumed capitalization of the "
            "observed candle-path distribution, not executed P&L."
        )
    if terminal_status == UNAVAILABLE:
        parts.append("Terminal settlement is unavailable and is not inferred from path WIN/LOSS.")
    if not parts:
        return {
            "status": UNAVAILABLE,
            "reason": "No economic objects available.",
            "facts": facts,
            "prose": "",
        }
    return {
        "status": DERIVED,
        "label": "DOES THE OBSERVED ECONOMICS SURVIVE? · facts only · not a quality score",
        "facts": facts,
        "prose": " ".join(parts),
        "note": "Descriptive only. Not a trade recommendation. Not ALPHA. Not TRADE QUALITY.",
    }
