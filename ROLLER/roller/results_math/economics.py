"""Capitalize observed and hypothetical EVs. Integer contracts × rational mean."""

from __future__ import annotations

from typing import Any

from roller.results_math.means import median as sample_median
from roller.results_math.means import quantiles, sample_std
from roller.results_math.models import DERIVED, HYPOTHETICAL, MODEL_ASSUMED, UNAVAILABLE
from roller.results_math.sizing import dollars_from_cents, size_allocation


def _scale(cents: float | int | None, contracts: int | None) -> float | None:
    if cents is None or contracts is None:
        return None
    return float(cents) * int(contracts)


def capitalize(
    *,
    observed_sum_cents: int | None,
    observed_n: int,
    observed_mean_cents: float | None,
    observed_std_cents: float | None,
    observed_ci: dict[str, Any] | None,
    max_dd_cents: int | None,
    book_ev_cents: float | None,
    settlement_ev_cents: float | None,
    book_ci: dict[str, Any] | None = None,
    entry_cents: int | None,
    bankroll_cents: int,
    allocation_cents: int,
    quantiles_cents: dict[str, float | None] | None = None,
    returns_cents: list[float] | None = None,
    mean_observed_entry_cents: float | None = None,
) -> dict[str, Any]:
    sizing = size_allocation(
        bankroll_cents=bankroll_cents,
        allocation_cents=allocation_cents,
        entry_cents=entry_cents,
    )
    if sizing.get("status") == UNAVAILABLE:
        return sizing
    n_c = int(sizing["contracts"])
    alloc = int(sizing["allocation_cents"])
    bank = int(sizing["bankroll_cents"])

    if observed_sum_cents is not None and observed_n > 0:
        # Exact: (Σ πᵢ × contracts) / n  — do not multiply rounded mean.
        observed_dollar_cents = (observed_sum_cents * n_c) / observed_n
    elif observed_mean_cents is not None:
        observed_dollar_cents = observed_mean_cents * n_c
    else:
        observed_dollar_cents = None

    book_dollar_cents = _scale(book_ev_cents, n_c)
    set_dollar_cents = _scale(settlement_ev_cents, n_c)
    std_dollar = _scale(observed_std_cents, n_c)
    dd_dollar = _scale(max_dd_cents, n_c)

    def _pct(numer: float | None, denom: int) -> float | None:
        if numer is None or denom <= 0:
            return None
        return float(numer) / denom

    q_dollars = None
    if quantiles_cents:
        q_dollars = {k: dollars_from_cents(_scale(v, n_c)) for k, v in quantiles_cents.items()}

    dollar_returns = [float(r) * n_c / 100.0 for r in (returns_cents or [])]
    distribution = None
    if dollar_returns:
        qs = quantiles(dollar_returns)
        distribution = {
            "status": DERIVED,
            "label": "HYPOTHETICAL CAPITALIZATION OF OBSERVED DISTRIBUTION · not live P&L",
            "n": len(dollar_returns),
            "expected_dollars": dollars_from_cents(observed_dollar_cents),
            "median_dollars": sample_median(dollar_returns),
            "std_dollars": sample_std(dollar_returns),
            "p5_dollars": qs.get("p5"),
            "p25_dollars": qs.get("p25"),
            "p50_dollars": qs.get("p50"),
            "p75_dollars": qs.get("p75"),
            "p95_dollars": qs.get("p95"),
            "worst_dollars": min(dollar_returns),
            "best_dollars": max(dollar_returns),
        }

    se_cents = observed_ci.get("standard_error") if observed_ci else None
    se_dollar = _scale(se_cents, n_c)
    ci_dollars = None
    if observed_ci and observed_ci.get("lower") is not None:
        ci_dollars = {
            "lower": dollars_from_cents(_scale(observed_ci.get("lower"), n_c)),
            "upper": dollars_from_cents(_scale(observed_ci.get("upper"), n_c)),
            "method": observed_ci.get("method"),
            "standard_error_dollars": dollars_from_cents(se_dollar),
        }

    return {
        "status": MODEL_ASSUMED,
        "sizing": sizing,
        "observed": {
            "status": DERIVED if observed_dollar_cents is not None else UNAVAILABLE,
            "label": "CAPITALIZED OBSERVED PATH EV · candle-path distribution · not the 70¢ binary trade P&L",
            "ev_per_contract_cents": observed_mean_cents,
            "expected_allocation_cents": observed_dollar_cents,
            "expected_allocation_dollars": dollars_from_cents(observed_dollar_cents),
            "expected_pct_allocation": _pct(observed_dollar_cents, alloc),
            "expected_pct_bankroll": _pct(observed_dollar_cents, bank),
            "std_allocation_cents": std_dollar,
            "std_allocation_dollars": dollars_from_cents(std_dollar),
            "se_allocation_cents": se_dollar,
            "se_allocation_dollars": dollars_from_cents(se_dollar),
            "max_dd_allocation_cents": dd_dollar,
            "max_dd_allocation_dollars": dollars_from_cents(dd_dollar),
            "max_dd_pct_allocation": _pct(dd_dollar, alloc),
            "max_dd_pct_bankroll": _pct(dd_dollar, bank),
            "quantiles_dollars": q_dollars,
            "distribution": distribution,
            "ev_ci_dollars": ci_dollars,
        },
        "prices": {
            "reference_cents": entry_cents,
            "mean_observed_entry_cents": mean_observed_entry_cents,
            "sizing_cents": entry_cents,
            "note": "Contracts use the reference/sizing price, not the mean observed touch.",
        },
        "book": {
            "status": HYPOTHETICAL if book_dollar_cents is not None else UNAVAILABLE,
            "label": "BOOK-PRICE EXPECTED $ / ALLOCATION · hypothetical chips · not observed path EV",
            "ev_per_contract_cents": book_ev_cents,
            "expected_allocation_cents": book_dollar_cents,
            "expected_allocation_dollars": dollars_from_cents(book_dollar_cents),
            "ev_ci_dollars": (
                {
                    "lower": dollars_from_cents(_scale(book_ci.get("lower"), n_c)),
                    "upper": dollars_from_cents(_scale(book_ci.get("upper"), n_c)),
                    "method": book_ci.get("method"),
                    "zero_inside_ci": book_ci.get("zero_inside_ci"),
                    "note": "FINITE-SAMPLE INTERVAL · NOT A FORECAST · NOT A MAXIMUM LOSS",
                }
                if book_ci and book_ci.get("lower") is not None
                else None
            ),
        },
        "settlement": {
            "status": DERIVED if set_dollar_cents is not None else UNAVAILABLE,
            "label": "SETTLEMENT EV capitalized · measured terminal only",
            "ev_per_contract_cents": settlement_ev_cents,
            "expected_allocation_cents": set_dollar_cents,
            "expected_allocation_dollars": dollars_from_cents(set_dollar_cents),
        },
    }
